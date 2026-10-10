"""O_null1 preparation/verification/generation. Default Plan never opens a model."""
import argparse
import json
import os
import shutil
import subprocess
import sys
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path

from common import (HERE, ZONES, geometry, null_statistics, read_json, reproject, require,
                    rgb, save_mask, save_new, sha256, support_for_geometry, write_new)
from dd_schedule import all_reports, verify_sources
from offline import install
from provenance import frozen, roots, unchanged, verify


def plan():
    manifest = frozen()
    result = {"status": "PREPARED_NOT_MEASURED", "action": "Plan: no server, parser, weights or real images executed",
              "a_sha256": manifest["a"]["sha256"], "routes": {}, "dd_schedules": all_reports()}
    for route, config in manifest["routes"].items():
        geo = geometry(route)
        support = support_for_geometry(tuple(manifest["a_size"]), geo)
        result["routes"][route] = {**config, "geometry": geo, "planned_support_pixels": int(support.sum()),
                                   "planned_support_fraction": float(support.mean()),
                                   "workflow": manifest["workflows"].get(route)}
    return result


def local_git():
    def git(*args):
        process = subprocess.run(["git", "-C", str(HERE), *args], capture_output=True, text=True, timeout=30)
        require(process.returncode == 0, "cannot record git provenance")
        return process.stdout.strip()
    return {"head": git("rev-parse", "HEAD"), "branch": git("branch", "--show-current"),
            "dirty": bool(git("status", "--porcelain"))}


def worker(job, python, directory, deadline):
    from comfy_null import stop_owned
    import psutil
    request = directory/"request.json"
    write_new(request, job)
    with (directory/"worker.log").open("xb") as log:
        process = subprocess.Popen([str(python), "-u", "-B", str(HERE/"worker.py"), "--execute", str(request)],
                                   stdout=log, stderr=subprocess.STDOUT, env=dict(os.environ, PYTHONUTF8="1"),
                                   creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        created = psutil.Process(process.pid).create_time()
        try:
            rc = process.wait(timeout=deadline)
        except (subprocess.TimeoutExpired, KeyboardInterrupt):
            stop_owned(process, created)
            raise RuntimeError("worker deadline/interruption; no retry")
    require(rc == 0, f"worker exit {rc}; inspect {directory/'worker.log'}")
    record = read_json(directory/"worker.json")
    require(record.get("verdict") == "ok" and record.get("run_id") == job["run_id"]
            and record.get("a_sha256") == job["provenance"]["a_sha256"], "invalid/missing worker sidecar")
    return record


def code_identity():
    return {p.name: sha256(p, lf=True) for p in sorted(HERE.iterdir()) if p.suffix in (".py", ".json", ".ps1")}


def validate_ceiling(stats):
    excessive = {k: v for k, v in {"support": stats["tol_p995_support"], **stats["tol_p995_by_zone"]}.items()
                 if v is not None and v > 12}
    return excessive


def one_route(route, directory, paths, provenance, zones_dir, parser_record, run_id, port, deadline):
    directory.mkdir(exist_ok=False)
    record = {"kind": "O_null1", "route": route, "run_id": run_id, "verdict": "FAIL:incomplete",
              "generated_for_review_only": True, "network": "loopback_only_python_audit"}
    started = time.monotonic()
    try:
        unchanged(provenance)
        manifest = frozen()
        config = {**manifest["routes"][route], "geometry": geometry(route), "route": route,
                  "manifest_sha256": provenance["manifest_sha256"], "implementation_sha256": code_identity(),
                  "core_commit": manifest["core_commit"] if route in ("klein", "qie") else None,
                  "workflow": manifest["workflows"].get(route),
                  "runtime": provenance["environments"]["comfy" if route in ("klein", "qie") else "r1ei" if route == "r1ei" else "r3"],
                  "seed": 42, "batch": 1, "num_images": 1,
                  "zones": {"source": "pinned R3 parser on original A", "ids": ZONES,
                            "code_commit": manifest["provenance"]["parser_code_commit"],
                            "weights_revision": manifest["provenance"]["parser_weights"]["revision"],
                            "device": "cuda", "dtype": "float32", "deterministic_algorithms": True,
                            "tf32": False, "seed": 42}}
        record["route_config"] = config
        if route in ("klein", "qie"):
            from comfy_null import generate
            generate(route, directory, paths, provenance["a"], port, deadline, record)
        else:
            name = "r1ei" if route == "r1ei" else "r3"
            job = {"action": "generate", "kind": route, "run_id": run_id, "out": str(directory),
                   "w3": str(paths["w3"]), "a": provenance["a"], "provenance": provenance}
            record["worker"] = worker(job, paths["w3"]/name/".venv/Scripts/python.exe", directory, deadline)
        unchanged(provenance)
        result, support, geo = reproject(rgb(provenance["a"]), rgb(directory/"native.png"), route)
        save_new(result, directory/"O_null1.png")
        save_mask(support, directory/"support.png")
        zone_paths = {}
        for zone in ZONES:
            path = directory/(zone+".png")
            with (zones_dir/(zone+".png")).open("rb") as source, path.open("xb") as target:
                shutil.copyfileobj(source, target)
            require(sha256(path) == parser_record["masks_sha256"][zone], "parser masks changed")
            zone_paths[zone] = path
        stats = null_statistics(provenance["a"], directory/"O_null1.png", directory/"support.png", zone_paths, config)
        rejected = validate_ceiling(stats)
        if rejected:
            stats["status"] = "INCONCLUSIVE:null_distribution_not_credible"
        write_new(directory/"null_stats.json", stats)
        record.update(null_stats_sha256=sha256(directory/"null_stats.json"), artifacts_sha256=stats["sha256"],
                      support_fraction=stats["support_fraction"], counts=stats["counts"],
                      tol_p995_support=stats["tol_p995_support"], tol_p995_by_zone=stats["tol_p995_by_zone"],
                      null_validation="INCONCLUSIVE" if rejected else "within_ceiling_pending_review")
        if rejected:
            record["verdict"] = "INCONCLUSIVE:null_distribution_not_credible"
            raise ValueError(f"null above ceiling 12: {rejected}; preserved for review; stop")
        record["verdict"] = "ok"
        return record
    except Exception as error:
        if record["verdict"] == "FAIL:incomplete":
            record["verdict"] = "FAIL:route"
        record["error"] = f"{type(error).__name__}: {error}"
        raise
    finally:
        record["total_s"] = time.monotonic()-started
        write_new(directory/"sidecar.json", record)


def generate(args, paths):
    batch_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")+"_"+uuid.uuid4().hex[:12]
    output = args.out.resolve()/batch_id
    output.mkdir(parents=True, exist_ok=False)
    batch = {"batch_id": batch_id, "kind": "O_null1", "verdict": "FAIL:incomplete", "routes": [],
             "out": str(output), "phase": "generation_for_Claude_review"}
    try:
        batch["git"] = local_git()
        require(not batch["git"]["dirty"], "Generate requires committed clean preparation")
        provenance = verify(paths)
        require(verify_sources(paths["core"]), "DD source verification failed")
        provenance["implementation_sha256"] = code_identity()
        write_new(output/"provenance.json", provenance)
        write_new(output/"dd_schedule.json", all_reports())
        # Refuse an old server before loading even the parser.
        from comfy_null import refuse_existing_server
        refuse_existing_server(args.port)
        zones_dir = output/"zones"
        zones_dir.mkdir()
        job = {"action": "generate", "kind": "zones", "run_id": batch_id+"_zones", "out": str(zones_dir),
               "w3": str(paths["w3"]), "a": provenance["a"], "provenance": provenance}
        parser_record = {"run_id": job["run_id"], "kind": "zones", "verdict": "FAIL:incomplete"}
        try:
            parser_record = worker(job, paths["w3"]/"r3/.venv/Scripts/python.exe", zones_dir, args.deadline_s)
        except Exception as error:
            parser_record.update(verdict="FAIL:worker", error=f"{type(error).__name__}: {error}")
            raise
        finally:
            write_new(zones_dir/"sidecar.json", parser_record)
        for route in ("klein", "qie", "r1ei", "fashn"):
            require(code_identity() == provenance["implementation_sha256"], "implementation changed after preflight")
            rec = one_route(route, output/route, paths, provenance, zones_dir, parser_record,
                            batch_id+"_"+route, args.port, args.deadline_s)
            batch["routes"].append({"route": route, "sidecar": str(output/route/"sidecar.json"), "verdict": rec["verdict"]})
        batch["verdict"] = "ok"
        print(f"O_null1 generated for review: {output}")
        return 0
    except Exception as error:
        batch.update(verdict="FAIL:batch_stopped", error=f"{type(error).__name__}: {error}")
        print(f"{batch['error']}\nPreserved evidence: {output}", file=sys.stderr)
        return 1
    finally:
        write_new(output/"batch.json", batch)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--mode", choices=["Plan", "Verify", "Generate"], default="Plan")
    ap.add_argument("--w3-root", type=Path, default=Path.home()/"OneDrive/Documentos/w3-measure")
    appdata = Path(os.environ.get("LOCALAPPDATA", str(Path.home()/"AppData/Local")))
    ap.add_argument("--core", type=Path, default=appdata/"Comfy-Desktop/ComfyUI-Installs/ComfyUI/ComfyUI")
    ap.add_argument("--shared", type=Path, default=appdata/"Comfy-Desktop/ComfyUI-Shared")
    ap.add_argument("--out", type=Path, default=HERE.parents[1]/"runs/proto0/null")
    ap.add_argument("--port", type=int, default=8197)
    ap.add_argument("--deadline-s", type=int, default=3600, help="administrative timeout per worker/route; not a quality threshold")
    args = ap.parse_args(argv)
    require(1024 <= args.port <= 65535 and args.deadline_s > 0, "invalid port/deadline")
    install()
    if args.mode == "Plan":
        print(json.dumps(plan(), indent=2, ensure_ascii=False))
        return 0
    paths = roots(args.w3_root.resolve(), args.core.resolve(), args.shared.resolve())
    if args.mode == "Verify":
        provenance = verify(paths)
        verify_sources(paths["core"])
        print(json.dumps({"verdict": "ok", "action": "local hashes/metadata only; no setup, model import or inference", **provenance}, indent=2))
        return 0
    return generate(args, paths)


if __name__ == "__main__":
    sys.exit(main())
