"""Print pinned ComfyUI DifferentialDiffusion schedules, using CPU arithmetic only.

This is a diagnostic of the future DD release instants, not O_null1 inference.
The 50-step entry describes DD in ComfyUI for Klein Base at the R1-EI crop
resolution. The existing R1-EI Diffusers runner does not implement DD.
No torch import, network access, model loading or arbitrary threshold selection.
"""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
import math
from pathlib import Path

import numpy as np


SOURCES = {
    "repository": "https://github.com/Comfy-Org/ComfyUI",
    "commit": "daeb5e53681e2b10a3f0727d9ec5bc90784bee10",
    "files_sha256": {
        "comfy_extras/nodes_differential_diffusion.py": "13e29fc85f24aaa79b68a0e1901c83705609f2871ae9506d3aa3c96bcd364c58",
        "comfy_extras/nodes_flux.py": "71c9d804a9acfb7a828fecb8fcc4b93e28f4417f0c4259a68910f4027059741f",
        "comfy/model_sampling.py": "8afdc665272589a567792bb652389df7d4a83f69574c2b7e5b3d533d55592990",
        "comfy/samplers.py": "f2c264ca9d394612f828e3ffe167c856a278a10e1711b269f0ba65dccb66393f",
        "comfy/supported_models.py": "5943d81bc0257b9b72b065a4ecb2f57c51c826e91f86c333b98fbe8a830e0cef",
        "comfy_extras/nodes_model_advanced.py": "34c5065756d925791c7a238f084eefd5ff912e1e84976a2dbe94432deea8ffcc",
        "comfy_extras/nodes_post_processing.py": "4ee06e8e5911c844ba49d97e54c90081c539d57e6dc53f1185900e3a79ce4c98",
    },
    "klein_measured_workflow_sha256": "41552539f13643fa5e9480622671aa184c4e0adc19e69f97896016c4ce59b5d2",
    "equation": "(ts - ts_to) / (ts_from - ts_to)",
    "sigma_to": "max(model_sampling.sigma_min, step_sigmas[-1])",
    "timestep": "identity for ModelSamplingFlux and AuraFlow multiplier=1",
    "flux2_mu": {
        "a1": 8.73809524e-05, "b1": 1.89833333,
        "a2": 0.00016927, "b2": 0.45666666,
        "large_sequence_cutoff": 4300, "interpolation_steps": [10, 200],
    },
    "flux_model_sampling": {"shift": 2.02, "timesteps": 10000},
    "qie_model_sampling": {"shift": 3.1, "timesteps": 1000, "multiplier": 1.0},
    "arithmetic": "CPU NumPy float32 transcription of the pinned equations; not a ComfyUI execution or bitwise PyTorch claim",
}

CONFIGURATIONS = {
    "klein4b_4steps": {
        "steps": 4, "sampler": "euler", "scheduler": "Flux2Scheduler",
        "width": 704, "height": 1490,
        "resolution_basis": "A 725x1536 -> ImageScaleToTotalPixels nearest-exact 1MP, resolution_steps=1; GetImageSize precedes the VAE crop",
        "role": "Klein 4B measured workflow schedule; DD release-instant diagnostic",
    },
    "klein_base_50steps_comfy": {
        "steps": 50, "sampler": "euler", "scheduler": "Flux2Scheduler",
        "width": 1024, "height": 1024,
        "resolution_basis": "Klein Base DD diagnostic at the 1024x1024 R1-EI crop resolution",
        "role": "ComfyUI DD diagnostic from docs/06 E2b; not native DD or a 50-step measurement of the R1-EI Diffusers runner",
    },
    "qie_40steps": {
        "steps": 40, "sampler": "euler", "scheduler": "simple",
        "width": 688, "height": 1504,
        "resolution_basis": "R2 measured primary 1MP resolution; Simple does not depend on width/height",
        "role": "QIE primary 40-step schedule, AuraFlow shift=3.1; also the same schedule at 544x960",
    },
}


def verify_sources(core: Path) -> dict[str, str]:
    """Verify exact installed source bytes without importing the installed runtime."""
    verified = {}
    for relative, expected in SOURCES["files_sha256"].items():
        actual = hashlib.sha256((core / relative).read_bytes()).hexdigest()
        if actual != expected:
            raise ValueError(f"source pin mismatch: {relative}: {actual} != {expected}")
        verified[relative] = actual
    return verified


def compute_empirical_mu(image_seq_len: int, steps: int) -> float:
    """The pinned Flux2Scheduler equation; its scalar coefficients use Python float."""
    p = SOURCES["flux2_mu"]
    if image_seq_len > p["large_sequence_cutoff"]:
        return p["a2"] * image_seq_len + p["b2"]
    m_200 = p["a2"] * image_seq_len + p["b2"]
    m_10 = p["a1"] * image_seq_len + p["b1"]
    a = (m_200 - m_10) / 190.0
    b = m_200 - 200.0 * a
    return a * steps + b


def _flux_shift(t, mu: float) -> np.ndarray:
    t = np.asarray(t, dtype=np.float32)
    exp_mu = np.float32(math.exp(mu))
    with np.errstate(divide="ignore"):
        return exp_mu / (exp_mu + (np.float32(1) / t - np.float32(1)))


def _discrete_flow_sigma(t) -> np.ndarray:
    t = np.asarray(t, dtype=np.float32)
    # In torch, each Python scalar below is converted to the tensor's float32.
    shift = SOURCES["qie_model_sampling"]["shift"]
    return np.float32(shift) * t / (np.float32(1) + np.float32(shift - 1) * t)


def differential_thresholds(sigmas, sigma_min: float) -> list[dict]:
    """Evaluate the pinned DD formula once per Euler step (exclude terminal sigma)."""
    sigmas = np.asarray(sigmas, dtype=np.float32)
    if sigmas.ndim != 1 or len(sigmas) < 2 or not np.isfinite(sigmas).all():
        raise ValueError("schedule must be a finite vector with a terminal sigma")
    if np.any(sigmas < 0) or np.any(np.diff(sigmas) >= 0):
        raise ValueError("schedule must be nonnegative and strictly decreasing")
    minimum = np.float32(sigma_min)
    if not np.isfinite(minimum) or minimum < 0:
        raise ValueError("sigma_min must be finite and nonnegative")
    ts_from = sigmas[0]
    ts_to = max(minimum, sigmas[-1])
    if ts_from <= ts_to:
        raise ValueError("invalid DD interval: ts_from must exceed ts_to")
    values = (sigmas[:-1] - ts_to) / (ts_from - ts_to)
    return [{"step": i + 1, "sigma": float(sigma), "ts": float(sigma),
             "threshold": float(threshold)}
            for i, (sigma, threshold) in enumerate(zip(sigmas[:-1], values))]


def schedule_report(label: str) -> dict:
    if label not in CONFIGURATIONS:
        raise ValueError(f"unknown frozen schedule: {label}")
    config = copy.deepcopy(CONFIGURATIONS[label])
    steps = config["steps"]
    details = {}
    if config["scheduler"] == "Flux2Scheduler":
        sequence = round(config["width"] * config["height"] / (16 * 16))
        mu = compute_empirical_mu(sequence, steps)
        sigmas = _flux_shift(np.linspace(1, 0, steps + 1, dtype=np.float32), mu)
        p = SOURCES["flux_model_sampling"]
        sigma_min = _flux_shift(np.float32(1) / np.float32(p["timesteps"]), p["shift"])
        details = {"image_seq_len": sequence, "mu": mu,
                   "model_sampling_class": "ModelSamplingFlux", "model_sampling_shift": p["shift"]}
    else:
        # ModelSamplingDiscreteFlow's ascending grade, sampled by Simple from its end.
        timesteps = SOURCES["qie_model_sampling"]["timesteps"]
        grade = _discrete_flow_sigma(np.arange(1, timesteps + 1, dtype=np.float32) / np.float32(timesteps))
        indices = [timesteps - (1 + int(i * (timesteps / steps))) for i in range(steps)]
        sigmas = np.asarray([grade[i] for i in indices] + [0.0], dtype=np.float32)
        sigma_min = grade[0]
        details = {"simple_indices": indices, "model_sampling_class": "ModelSamplingDiscreteFlow",
                   "model_sampling_patch": "ModelSamplingAuraFlow", "shift": 3.1, "multiplier": 1.0}
    return {
        "label": label, **config, **details,
        "sigma_min": float(sigma_min), "ts_from": float(sigmas[0]),
        "ts_to": float(max(sigma_min, sigmas[-1])),
        "terminal_sigma": float(sigmas[-1]),
        "sigmas": [float(v) for v in sigmas],
        "release_rule": "R(p) >= threshold at the indicated step; no mask levels are chosen here",
        "rows": differential_thresholds(sigmas, sigma_min),
    }


def all_reports() -> dict:
    return {"schema_version": 1, "artifact": "dd_schedule_diagnostic",
            "numpy_version": np.__version__,
            "sources": copy.deepcopy(SOURCES),
            "schedules": [schedule_report(label) for label in CONFIGURATIONS]}


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--route", choices=["all", *CONFIGURATIONS], default="all")
    parser.add_argument("--out", type=Path, help="new JSON file (existing files are never overwritten)")
    parser.add_argument("--verify-core", type=Path, help="optional read-only verification of pinned installed source bytes")
    args = parser.parse_args(argv)
    try:
        report = all_reports()
        if args.verify_core:
            report["verified_sources"] = verify_sources(args.verify_core)
        if args.route != "all":
            report["schedules"] = [schedule_report(args.route)]
        if args.out:
            with args.out.open("x", encoding="utf-8", newline="\n") as stream:
                json.dump(report, stream, indent=2, allow_nan=False)
                stream.write("\n")
    except (OSError, ValueError) as exc:
        parser.error(str(exc))
    print("DifferentialDiffusion: (ts - ts_to) / (ts_from - ts_to)")
    print("CPU diagnostic only; no sampling, model loading, O_null1 or mask-level selection.")
    print(SOURCES["arithmetic"])
    for schedule in report["schedules"]:
        print(f"\n{schedule['label']}: {schedule['sampler']}/{schedule['scheduler']}, {schedule['steps']} steps")
        print(schedule["role"])
        print(f"ts_from={schedule['ts_from']:.12g}; ts_to={schedule['ts_to']:.12g}; terminal_sigma={schedule['terminal_sigma']:.12g}")
        print("step\tsigma=ts\tDD threshold")
        for row in schedule["rows"]:
            print(f"{row['step']}\t{row['sigma']:.9f}\t{row['threshold']:.9f}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
