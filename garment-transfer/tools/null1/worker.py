"""Operator-only isolated workers. --inspect reads metadata; --execute is explicit."""
import argparse
import importlib.util
import json
import sys
import time
from pathlib import Path

from common import (HERE, ZONES, read_json, require, rgb, save_mask, save_new, sha256,
                    write_new, zones_from_labels)
from offline import install
from provenance import runtime, unchanged


def deterministic_torch():
    import torch
    torch.manual_seed(42)
    require(torch.cuda.is_available(), "CUDA required; no CPU fallback")
    torch.cuda.manual_seed_all(42)
    torch.backends.cudnn.benchmark = False
    torch.backends.cudnn.deterministic = True
    torch.backends.cuda.matmul.allow_tf32 = False
    torch.backends.cudnn.allow_tf32 = False
    torch.use_deterministic_algorithms(True)
    return torch


def generate_zones(job, evidence):
    torch = deterministic_torch()
    import numpy as np
    from fashn_human_parser import FashnHumanParser
    from fashn_human_parser.labels import LABELS_TO_IDS
    expected = {"background": 0, "face": 1, "hair": 2, "arms": 12, "hands": 13,
                "legs": 14, "feet": 15, "torso": 16}
    require(all(LABELS_TO_IDS.get(k) == v for k, v in expected.items()), "parser taxonomy changed")
    parser = FashnHumanParser(model_id=str(Path(job["w3"])/"models/fashn-vton-1.5/fashn-human-parser"), device="cuda")
    labels = parser.predict(rgb(job["a"]))
    # One deterministic forward, original A canvas; no VTON, DWPose or masks from O.
    require(labels.shape == (1536, 725), "parser output grid changed")
    zones = zones_from_labels(labels)
    from PIL import Image
    save_new(Image.fromarray(labels.astype(np.uint8)), Path(job["out"])/"labels.png")
    for name, values in zones.items():
        save_mask(values, Path(job["out"])/(name+".png"))
    assigned = np.logical_or.reduce(list(zones.values()))
    evidence.update(zone_ids=ZONES, counts={k: int(v.sum()) for k, v in zones.items()},
                    unassigned_pixels=int((~assigned).sum()), device="cuda", dtype="float32",
                    seed=42, deterministic_algorithms=True, tf32=False,
                    masks_sha256={k: sha256(Path(job["out"])/(k+".png")) for k in zones})
    del parser
    torch.cuda.synchronize()


def generate_r1ei(job, evidence):
    torch = deterministic_torch()
    from diffusers import AutoencoderKLFlux2
    from diffusers.pipelines.flux2.image_processor import Flux2ImageProcessor
    from PIL import Image
    crop = rgb(job["a"]).crop((-136, 193, 860, 1189)).resize((1024, 1024), Image.Resampling.LANCZOS)
    save_new(crop, Path(job["out"])/"A_crop_1024.png")
    processor = Flux2ImageProcessor(vae_scale_factor=16)
    vae = AutoencoderKLFlux2.from_pretrained(str(Path(job["w3"])/"models/FLUX.2-klein-base-4B"),
                                            subfolder="vae", torch_dtype=torch.bfloat16,
                                            local_files_only=True).eval().to("cuda")
    require(vae.dtype == torch.bfloat16 and not vae.use_tiling, "VAE dtype/tiling changed")
    with torch.inference_mode():
        pixels = processor.preprocess(crop).to(device="cuda", dtype=torch.bfloat16)
        latent = vae.encode(pixels).latent_dist.mode()
        decoded = vae.decode(latent, return_dict=False)[0]
        result = processor.postprocess(decoded, output_type="pil")[0]
    save_new(result, Path(job["out"])/"native.png")
    evidence.update(device="cuda", dtype="bfloat16", posterior="mode", tiling=False,
                    crop_box=[-136, 193, 860, 1189], seed=42, deterministic_algorithms=True,
                    native_sha256=sha256(Path(job["out"])/"native.png"))


def generate_fashn(job, evidence):
    # Load only the pinned transforms module; never import the VTON pipeline.
    import numpy as np
    from PIL import Image
    spec = importlib.util.spec_from_file_location("null1_fashn_transforms", evidence["runtime"]["transforms"])
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    image = rgb(job["a"])
    pre = module.AspectPreserveResize(target_size=(864, 864), mode="fit", backend="pil")
    pad = module.ResizePad((576, 864), backend="opencv")
    image = pre(image, allow_upsampling=False)
    require(image.size == (407, 864), "FASHN pre-resize changed")
    padded = Image.fromarray(pad(np.asarray(image), mem_padding=True))
    require(padded.size == (576, 864), "FASHN padded canvas changed")
    save_new(padded, Path(job["out"])/"padded.png")
    result = pad.unpad(padded)
    require(result.size == (407, 864), "FASHN unpad changed")
    save_new(result, Path(job["out"])/"native.png")
    evidence.update(device="cpu", vae=None, dimensions=[407, 864], canvas=[576, 864],
                    native_sha256=sha256(Path(job["out"])/"native.png"))


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--inspect", choices=["comfy", "r1ei", "r3"])
    ap.add_argument("--execute", type=Path)
    args = ap.parse_args()
    require(bool(args.inspect) != bool(args.execute), "choose --inspect or --execute request.json")
    install()
    if args.inspect:
        print(json.dumps(runtime(args.inspect)))
        return 0
    job = read_json(args.execute)
    evidence = {"run_id": job["run_id"], "kind": job["kind"], "verdict": "FAIL:incomplete",
                "network": "loopback_only_python_audit", "a_sha256": sha256(job["a"])}
    start = time.perf_counter()
    try:
        require(job["action"] == "generate", "explicit generation request required")
        unchanged(job["provenance"])
        evidence["runtime"] = runtime("r1ei" if job["kind"] == "r1ei" else "r3")
        {"zones": generate_zones, "r1ei": generate_r1ei, "fashn": generate_fashn}[job["kind"]](job, evidence)
        unchanged(job["provenance"])
        evidence["verdict"] = "ok"
        return 0
    except Exception as error:
        evidence.update(verdict="FAIL:worker", error=f"{type(error).__name__}: {error}")
        print(evidence["error"], file=sys.stderr)
        return 1
    finally:
        evidence["wall_s"] = time.perf_counter()-start
        write_new(Path(job["out"])/"worker.json", evidence)


if __name__ == "__main__":
    sys.exit(main())
