"""D-059/a Part 2: CPU derivation; pinned ComfyUI crop reference, no VAE/reprojection.

This is calibration evidence for review, never a per-case G0 null or a D-060 decision.
"""
import importlib.metadata
import platform
import shutil
import sys
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
from PIL import Image

from common import (HERE, ZONES, NORMATIVE_ZONES, distribution, mask, read_json, require,
                    rgb, save_mask, save_new, sha256, tolerance, write_new)

sys.path.insert(0, str(HERE.parent))
from null_geometry import forward_grid, forward_mask, validity_support

PART2 = ("klein_g0", "qie_g0", "r1ei_g0", "klein_1mp_fallback", "fashn_g0")


def verify_lot(root, pin):
    """Entire exact file set, byte hashes, no writes or inference."""
    root = Path(root).resolve(strict=True)
    expected = pin["files"]
    actual = {p.relative_to(root).as_posix(): p for p in root.rglob("*") if p.is_file()}
    require(len(actual) == pin["file_count"] and set(actual) == set(expected), "source lot file set mismatch")
    for rel, path in actual.items():
        require(not path.is_symlink() and path.resolve().is_relative_to(root), "source lot link escapes pin")
        require(sha256(path) == expected[rel], "source lot SHA256 mismatch: " + rel)
    return {"path": str(root), "file_count": len(actual), "sha256_verified": True}


def safe_output(source, output):
    source, output = Path(source).resolve(), Path(output).resolve()
    require(not (output == source or output.is_relative_to(source) or source.is_relative_to(output)),
            "Derive output must be separate from the immutable source lot")
    require(not output.exists(), "Derive output already exists")
    return output


def cpu_runtime(pin):
    actual = {"python_version": platform.python_version(),
              "packages": {name: importlib.metadata.version(name) for name in pin["packages"]}}
    require(actual == pin, "Derive CPU runtime pin mismatch")
    return actual


def eroded_validity(support, radius):
    """Informative only: existing auditor's 4-connected erosion, unchanged edges.

    Only invalid padding inside the grid is eroded, not the outside of the image.
    R1-EI padding is vertical strips, so this removes radius columns at each seam.
    """
    result = support.copy()
    for _ in range(radius):
        previous = result.copy()
        result[1:] &= previous[:-1]
        result[:-1] &= previous[1:]
        result[:,1:] &= previous[:,:-1]
        result[:,:-1] &= previous[:,1:]
    return result


def summarize_delta(delta, support, zones):
    require(support.any(), "empty internal reconstruction support")
    scalar = tolerance(distribution(delta[support]))
    stats = {"support": distribution(delta[support]), "by_zone": {}}
    counts = {"canvas": int(delta.size), "support": int(support.sum()),
              "tail_support": .005*int(support.sum()), "by_zone": {}}
    measured, applied, roles, fractions = {}, {}, {}, {}
    for name, zone in zones.items():
        selected = support & zone
        n = int(selected.sum())
        stat = distribution(delta[selected])
        tol = tolerance(stat)
        normative = name in NORMATIVE_ZONES and .005*n >= 100
        effective = tol if normative else scalar
        counts["by_zone"][name] = {"total": int(zone.sum()), "support": n, "tail": .005*n}
        stats["by_zone"][name] = stat
        measured[name], applied[name], roles[name] = tol, effective, normative
        fractions[name] = None if n == 0 else float((delta[selected] > effective).mean())
    return {"tol_p995_support": scalar,
            "tol_p995_by_zone": {k: measured[k] for k in NORMATIVE_ZONES},
            "zone_tolerance_normative": {k: roles[k] for k in NORMATIVE_ZONES},
            "tol_applied_by_zone": {k: applied[k] for k in NORMATIVE_ZONES},
            "frac_above_tol": {"support": float((delta[support]>scalar).mean()), "by_zone": fractions},
            "frac_above_tol_definition": "strict >; per-zone uses tol_applied_by_zone (scalar when tail <100)",
            "support_fraction": float(support.mean()), "counts": counts, "statistics": stats,
            "clothing": "reported only; no normative tolerance"}


def ceiling_excess(stats):
    values = {"support": stats["tol_p995_support"]}
    values.update({k:v for k,v in stats["tol_p995_by_zone"].items() if stats["zone_tolerance_normative"][k]})
    return {k:v for k,v in values.items() if v is not None and v > 12}


def prediction_check(stats, prediction):
    values = {"support": stats["tol_p995_support"], **stats["tol_p995_by_zone"]}
    deviations, missing = {}, []
    for zone, bounds in prediction.items():
        value = values[zone]
        if value is None:
            missing.append(zone)
            continue
        low, high = bounds
        distance = max(low-value, value-high, 0)
        if distance:
            deviations[zone] = {"measured": value, "expected": bounds, "distance": distance}
    return {"expected": prediction, "deviations": deviations, "missing": missing,
            "investigate_before_accepting": bool(missing) or any(x["distance"]>1 for x in deviations.values())}


def klein_informative(stats, a_path, a_forward, output, support_path, zone_paths, grid, upper_bounds):
    """D-059a: Pillow comparisons are informational, never the normative reference."""
    pillow = rgb(a_path).crop(grid["box_on_A"])
    fwd, native = np.asarray(rgb(a_forward)).astype(np.int32), np.asarray(rgb(output)).astype(np.int32)
    pixels = np.asarray(pillow).astype(np.int32)
    support = mask(support_path,pillow.size)
    zones = {k:mask(path,pillow.size) for k,path in zone_paths.items()}
    pillow_stats = summarize_delta(np.abs(native-pixels).max(axis=2),support,zones)
    decoder_stats = summarize_delta(np.abs(fwd-pixels).max(axis=2),support,zones)
    pillow_path = Path(output).parent/"A_Pillow_crop.png"
    save_new(pillow,pillow_path)
    stats["informative"] = {
        "pillow_reference":{"normative":False, **pillow_stats},
        "executor_minus_pillow":{"normative":False, **decoder_stats},
        "a_pillow_crop_sha256":sha256(pillow_path)}
    def values(summary):
        return {"support":summary["statistics"]["support"], **summary["statistics"]["by_zone"]}
    measured, historical = values(stats), values(pillow_stats)
    exceeded, missing = {}, []
    for zone, ceiling in upper_bounds.items():
        current, previous = measured[zone],historical[zone]
        if current is None or previous is None:
            missing.append(zone)
        elif current["p995"] > ceiling or current["p995"] > previous["p995"]:
            exceeded[zone] = {"p995":current["p995"],"pillow_p995":previous["p995"],"upper_bound":ceiling}
    stats["prediction_check"] = {"rule":"D-059a: any excess over Pillow or preregistered upper bound stops; no +1 allowance",
                                 "upper_bounds":upper_bounds,"exceeded":exceeded,"missing":missing,
                                 "investigate_before_accepting":bool(exceeded or missing),
                                 "stop_before_accepting":bool(exceeded or missing)}


def crop_reference(directory, paths, a_path, port, deadline, provenance):
    """Use the pinned workflow/executor, never a local PyAV decoder implementation."""
    from comfy_null import generate
    from provenance import unchanged
    directory.mkdir(exist_ok=False)
    record = {"run_id":directory.parent.name+"_klein_crop", "mode":"Derive", "device":"cpu",
              "kind":"A_forward", "decision":"D-059a", "verdict":"FAIL:incomplete",
              "a_sha256":sha256(a_path), "executor_provenance":provenance}
    try:
        unchanged(provenance)
        generate("klein_crop",directory,paths,a_path,port,deadline,record)
        unchanged(provenance)
        record["verdict"] = "ok"
        return directory/"native.png", record
    except Exception as error:
        record.update(verdict="FAIL:reference",error=f"{type(error).__name__}: {error}")
        raise
    finally:
        write_new(directory/"sidecar.json",record)


def null_statistics_v2(a_path, a_forward, output, support_path, zone_paths, grid, config):
    A, O = rgb(a_forward), rgb(output)
    require(A.size == O.size == (grid["width"],grid["height"]), "internal grid mismatch")
    for path in (a_forward, output):
        with Image.open(path) as im:
            require(im.mode == "RGB", "internal evidence must be RGB8")
    support = mask(support_path, A.size)
    require(set(zone_paths) == set(ZONES), "all five internal zone masks required")
    zones = {name:mask(path,A.size) for name,path in zone_paths.items()}
    delta = np.abs(np.asarray(O).astype(np.int32)-np.asarray(A).astype(np.int32)).max(axis=2)
    stats = summarize_delta(delta,support,zones)
    stats.update(schema_version=2, kind="O_null1", normative=True, grid=grid,
                 metric="max_RGB(abs(uint8(O_null1)-uint8(A_forward)))",
                 quantile="numpy percentile linear; tolerance=max(1,ceil(p99.5))",
                 identity_reference="A_forward", route_config=config,
                 sha256={"a":sha256(a_path), "a_forward":sha256(a_forward),
                         "o_null1":sha256(output), "support":sha256(support_path),
                         "zones":{k:sha256(v) for k,v in zone_paths.items()}},
                 gate_eligible=False, status="DERIVED_PENDING_D060_NOT_A_G0_CASE_NULL")
    if config["route"] == "r1ei_g0":
        stats["informative_erosions"] = {
            str(r): {"normative":False, "radius_internal_px":r,
                     "method":"4-connected validity erosion; image edges unchanged",
                     **summarize_delta(delta,eroded_validity(support,r),zones)} for r in (4,8)}
    return stats


def copy_new(source, output):
    with Path(source).open("rb") as inp, Path(output).open("xb") as out:
        shutil.copyfileobj(inp,out)
    require(sha256(source) == sha256(output), "copy changed artifact")


def one_part2(name, output, source, a_path, manifest, identity, runtime, reference_executor=None):
    output.mkdir(exist_ok=False)
    rec = {"run_id":output.parent.name+"_"+name, "route":name, "mode":"Derive", "device":"cpu",
           "verdict":"FAIL:incomplete", "gate_eligible":False, "decision":"D-059a" if name=="klein_g0" else "D-059", "normative":True}
    start = time.monotonic()
    try:
        spec = manifest["part2"]["configurations"][name]
        a = rgb(a_path)
        grid = forward_grid(spec["base_route"],a.size,spec["geometry"])
        source_config = read_json(source/spec["output"].split("/")[0]/"null_stats.json")["route_config"]
        config = {"route":name, "source_lot":manifest["part2"]["source_lot"]["batch_id"],
                  "source_tuple":source_config, "pair":spec,
                  "runtime":runtime, "ComfyUI":manifest["part2"]["comfyui_identity"],
                  "PyAV":runtime.get("packages",{}).get("av"), "Pillow":runtime.get("packages",{}).get("Pillow"),
                  "calibration_scope":"pinned A only; not a G0 case null",
                  "implementation_sha256":identity, "manifest_sha256":sha256(HERE/"manifest.json",lf=True)}
        rec["route_config"] = config
        fwd = output/"A_forward.png"
        if name == "klein_g0":
            require(spec["reference"] == "executor:klein_crop" and reference_executor is not None,
                    "D-059a requires the pinned CPU crop executor; no Pillow fallback")
            reference, record = reference_executor(output/"reference")
            require(record["verdict"] == "ok" and record["a_sha256"] == sha256(a_path)
                    and record["native_sha256"] == sha256(reference), "invalid CPU reference sidecar")
            copy_new(reference,fwd)
            config["a_forward_executor"] = record
            config["a_forward_sidecar_sha256"] = sha256(output/"reference/sidecar.json")
        else:
            copy_new(source/spec["reference"],fwd)
        copy_new(source/spec["output"],output/"O_null1.png")
        save_mask(validity_support(grid),output/"support.png")
        zone_paths = {}
        for name_zone in ZONES:
            zone_paths[name_zone] = output/(name_zone+".png")
            save_mask(forward_mask(mask(source/"zones"/(name_zone+".png"),a.size),grid),zone_paths[name_zone])
        stats = null_statistics_v2(a_path,fwd,output/"O_null1.png",output/"support.png",zone_paths,grid,config)
        stats["prediction_check"] = prediction_check(stats,spec.get("prediction",{}))
        if name == "klein_g0":
            klein_informative(stats,a_path,fwd,output/"O_null1.png",output/"support.png",zone_paths,grid,
                              spec["prediction_upper_bounds"])
        if name == "fashn_g0":
            require(stats["statistics"]["support"]["max"] == 0, "identity definition diverged")
            stats.update(operator="identity_no_reconstruction", provisional_until_O_null2=True,
                         measured=False, status="NOT_MEASURED_IDENTITY_BY_DEFINITION_PENDING_O_NULL2")
        else:
            stats["operator"] = "difference_of_preserved_internal_artifacts"
            stats["measured"] = True
        rejected = ceiling_excess(stats)
        investigate = stats["prediction_check"]["investigate_before_accepting"]
        stop = stats["prediction_check"].get("stop_before_accepting",False)
        stats["ceiling_excess"] = rejected
        if stop:
            stats["status"] = "INCONCLUSIVE:klein_above_pillow_or_prediction"
        elif rejected:
            stats["status"] = "INCONCLUSIVE:null_distribution_not_credible"
        elif investigate:
            stats["status"] = "INCONCLUSIVE:prediction_mismatch"
        write_new(output/"null_stats.json",stats)
        rec.update(verdict=("INCONCLUSIVE:klein_above_pillow_or_prediction" if stop else
                            "INCONCLUSIVE:null_distribution_not_credible" if rejected else
                            "INCONCLUSIVE:prediction_mismatch" if investigate else "ok"),
                   stop_batch=stop,
                   status=stats["status"], grid=grid, null_stats_sha256=sha256(output/"null_stats.json"),
                   artifacts_sha256=stats["sha256"], prediction_check=stats["prediction_check"])
        return rec
    except Exception as error:
        rec.update(verdict="FAIL:derive",error=f"{type(error).__name__}: {error}")
        raise
    finally:
        rec["total_s"] = time.monotonic()-start
        write_new(output/"sidecar.json",rec)


def derive(args, paths):
    from orchestrate import code_identity, local_git
    from provenance import frozen, verify_cpu_crop
    manifest = frozen()
    part2 = manifest["part2"]
    require(part2["order"] == list(PART2), "PART2 order differs from manifest")
    source = HERE.parents[1]/part2["source_lot"]["path"]
    batch_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")+"_part2_"+uuid.uuid4().hex[:12]
    output = safe_output(source,args.out/batch_id)
    output.mkdir(parents=True,exist_ok=False)
    batch = {"batch_id":batch_id,"mode":"Derive","schema_version":2,"routes":[],"inconclusive_routes":[],
             "source_lot":str(source),"verdict":"FAIL:incomplete","gate_eligible":False,"device":"cpu"}
    a_path = paths[manifest["a"]["root"]]/manifest["a"]["path"]
    try:
        batch["git"] = local_git()
        require(not batch["git"]["dirty"], "Derive requires committed clean preparation")
        batch["source_verified_before"] = verify_lot(source,part2["source_lot"])
        require(sha256(a_path) == manifest["a"]["sha256"], "A differs from pinned benchmark")
        runtime = cpu_runtime(part2["runtime"])
        executor_provenance = verify_cpu_crop(paths)
        identity = code_identity()
        executor_provenance["implementation_sha256"] = identity
        batch["implementation_sha256"] = identity
        def execute_reference(directory):
            return crop_reference(directory,paths,a_path,args.port,args.deadline_s,executor_provenance)
        for name in PART2:
            require(code_identity() == identity, "implementation changed during Derive")
            rec = one_part2(name,output/name,source,a_path,manifest,identity,runtime,execute_reference)
            batch["routes"].append({"route":name,"verdict":rec["verdict"],"sidecar":str(output/name/"sidecar.json")})
            require(rec["verdict"] in ("ok","INCONCLUSIVE:null_distribution_not_credible",
                                        "INCONCLUSIVE:prediction_mismatch","INCONCLUSIVE:klein_above_pillow_or_prediction"),
                    "invalid Derive verdict")
            if rec["verdict"].startswith("INCONCLUSIVE"):
                batch["inconclusive_routes"].append(name)
            if rec.get("stop_batch"):
                batch["stopped_for_review"] = {"route":name,"reason":rec["verdict"]}
                break
        batch["source_verified_after"] = verify_lot(source,part2["source_lot"])
        require(sha256(a_path) == manifest["a"]["sha256"] and code_identity() == identity, "inputs/code changed")
        batch["verdict"] = "INCONCLUSIVE" if batch["inconclusive_routes"] else "ok"
    except Exception as error:
        batch.update(verdict="FAIL:derive_batch_stopped",error=f"{type(error).__name__}: {error}")
    finally:
        # Also check the preserved lot on failure. Never repair or touch it.
        try:
            batch["source_verified_final"] = verify_lot(source,part2["source_lot"])
        except Exception as error:
            batch.update(verdict="FAIL:source_lot_changed",source_error=str(error))
        write_new(output/"batch.json",batch)
    print(f"Derive {batch['verdict']}; evidence for review: {output}")
    return 1 if batch["verdict"].startswith("FAIL") else 3 if batch["inconclusive_routes"] else 0
