"""Operator-only lifecycle. --dry-run never verifies hardware or starts a server."""
import argparse
import asyncio
import json
import os
import socket
import subprocess
import sys
import time
import uuid
from pathlib import Path
from urllib.request import ProxyHandler, build_opener

from client import assert_owner, cleanup_aliases, log_evidence, upload_inputs
from common import (HERE, PRIMARY, SECONDARY, digest_json, frozen, owned_pids, read_json, render,
                    require, sha256, validate_measure, warm_consistency, write_new)
from provenance import default_paths, verify, verify_unchanged


def refuse_existing_server(port):
    import psutil
    for process in psutil.process_iter(["pid", "name", "cmdline"]):
        command = process.info["cmdline"] or []
        if process.info["pid"] == os.getpid():
            continue
        if any(Path(a).name == "launch_server.py" for a in command):
            raise RuntimeError("another R2 ComfyUI server is already running")
        if "python" in (process.info["name"] or "").lower() and any(Path(a).name == "main.py" for a in command):
            # Also inspect relative main.py via cwd; fail closed if ownership is unclear.
            try:
                cwd = process.cwd()
            except psutil.Error:
                cwd = "ComfyUI unknown"
            require("comfy" not in (" ".join(command) + cwd).lower(), "old ComfyUI process is running; close it first")
    with socket.socket() as probe:
        if hasattr(socket, "SO_EXCLUSIVEADDRUSE"):
            probe.setsockopt(socket.SOL_SOCKET, socket.SO_EXCLUSIVEADDRUSE, 1)
        probe.bind(("127.0.0.1", port))


class Server:
    def __init__(self, root, provenance, port):
        self.process = None
        self.session = None
        self.root, self.provenance, self.port = root, provenance, port

    def start(self):
        import psutil
        refuse_existing_server(self.port)
        verify_unchanged(self.provenance)
        server_id = uuid.uuid4().hex
        directory = self.root / "servers" / server_id
        directory.mkdir(parents=True, exist_ok=False)
        for name in ("input", "output", "user", "temp"):
            (directory / name).mkdir()
        core = Path(self.provenance["core"])
        model_paths = {"is_default": True}
        for role, category in (("unet", "diffusion_models"), ("clip", "text_encoders"), ("vae", "vae")):
            model_paths[category] = str(Path(self.provenance["weights"][role]["path"]).parent)
        paths_file = directory / "model_paths.yaml"
        # JSON is valid YAML; escapes Windows paths without interpolation bugs.
        write_new(paths_file, {"r2_pinned": model_paths})
        flags = ["--listen", "127.0.0.1", "--port", str(self.port), "--verbose", "DEBUG", "--log-stdout",
                 "--disable-auto-launch", "--disable-api-nodes", "--disable-all-custom-nodes",
                 "--whitelist-custom-nodes", "ComfyUI-GGUF", "--extra-model-paths-config", str(paths_file),
                 "--front-end-root", str(core / ".venv/Lib/site-packages/comfyui_frontend_package/static"),
                 "--input-directory", str(directory / "input"), "--output-directory", str(directory / "output"),
                 "--user-directory", str(directory / "user"), "--temp-directory", str(directory / "temp")]
        session = {"server_id": server_id, "core": str(core), "port": self.port, "flags": flags,
                   "provenance": self.provenance, "process_log": str(directory / "process.log"),
                   "bootstrap": str(directory / "bootstrap.json"), "launch_path": str(directory / "launch.json"),
                   "session_path": str(directory / "session.json"),
                   "input_dir": str(directory / "input"), "output_dir": str(directory / "output")}
        write_new(session["launch_path"], session)
        started = time.perf_counter()
        with Path(session["process_log"]).open("xb") as log:
            self.process = subprocess.Popen([sys.executable, "-u", str(HERE / "launch_server.py"), session["launch_path"]],
                                            stdout=log, stderr=subprocess.STDOUT, cwd=core,
                                            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        session["pid"] = self.process.pid
        session["process_created"] = psutil.Process(self.process.pid).create_time()
        self.session = session
        opener = build_opener(ProxyHandler({}))
        last_error = None
        while time.perf_counter() - started < 180:
            require(self.process.poll() is None, f"server failed; inspect {session['process_log']}")
            try:
                assert_owner(session)
                with opener.open(f"http://127.0.0.1:{self.port}/queue", timeout=2) as response:
                    queue = json.load(response)
                require(queue.get("queue_running") == [] and queue.get("queue_pending") == [], "new server is not idle")
                bootstrap = read_json(session["bootstrap"])
                require(bootstrap["pid"] in owned_pids(session["pid"]) and bootstrap["server_id"] == server_id, "bootstrap binding mismatch")
                session["server_python_pid"] = bootstrap["pid"]
                require(bootstrap["loaded_models"] == 0 and bootstrap["dynamic_vram"] is True, "cold/DynamicVRAM preflight failed")
                session["startup_s"] = time.perf_counter() - started
                session["startup_evidence"] = bootstrap
                session["startup_log"] = log_evidence(session, 0, directory / "startup.log")
                write_new(session["session_path"], session)
                return self
            except (OSError, ValueError, RuntimeError) as error:
                last_error = f"{type(error).__name__}: {error}"
                time.sleep(0.25)
        raise RuntimeError(f"server startup deadline; last readiness error: {last_error}; benchmark not started")

    def stop(self):
        if self.process is None:
            return
        import psutil
        try:
            process = psutil.Process(self.process.pid)
            require(process.create_time() == self.session["process_created"], "refuse to kill reused PID")
            children = process.children(recursive=True)
            for child in children:
                child.terminate()
            process.terminate()
            _, alive = psutil.wait_procs([process, *children], timeout=5)
            for child in alive:
                child.kill()
            _, alive = psutil.wait_procs(alive, timeout=5)
            require(not alive, "owned server processes survived termination")
        except psutil.NoSuchProcess:
            pass
        self.process.wait(timeout=5)


def expected_dimensions(provenance, config):
    if config == SECONDARY:
        return [544, 960]
    w, h = provenance["inputs"]["A"]["dimensions"]
    # Official FluxKontextImageScale table, pinned source in manifest.
    resolutions = [(672,1568),(688,1504),(720,1456),(752,1392),(800,1328),(832,1248),
                   (880,1184),(944,1104),(1024,1024),(1104,944),(1184,880),(1248,832),
                   (1328,800),(1392,752),(1456,720),(1504,688),(1568,672)]
    _, width, height = min((abs(w/h - x/y), x, y) for x, y in resolutions)
    return [width, height]


def one_run(root, server, config, state, index, smoke=False, control=None):
    verify_unchanged(server.session["provenance"])
    run_id = f"{config}_{state}_{index}_{uuid.uuid4().hex}"
    directory = root / "runs" / run_id
    directory.mkdir(parents=True, exist_ok=False)
    alias_id = control["alias_id"] if control else run_id
    plan = None
    log_offset = Path(server.session["process_log"]).stat().st_size
    _, _, policy, _ = frozen(config, smoke)
    try:
        aliases = asyncio.run(upload_inputs(server.session, alias_id))
        _, template, _, _ = frozen(config, smoke)
        prefix = control["output_prefix"] if control else run_id
        plan = {"run_id": run_id, "run_dir": str(directory), "session_path": server.session["session_path"],
                "configuration": config, "state": state, "smoke": smoke, "control": bool(control),
                "alias_id": alias_id, "aliases": aliases, "output_prefix": prefix,
                "workflow": render(template, aliases["A"]["name"], aliases["B"]["name"], prefix),
                "expected_dimensions": expected_dimensions(server.session["provenance"], config),
                "prepared_at_ns": time.time_ns(),
                "preexisting_outputs": [p.name for p in Path(server.session["output_dir"]).glob(prefix + "*.png")],
                "log_offset": log_offset}
        if control:
            plan.update(control_source=control["source"], control_sha256=control["sha256"])
        else:
            require(not plan["preexisting_outputs"], "refuse previous output")
        plan_path = directory / "plan.json"
        write_new(plan_path, plan)
        command = [sys.executable, str(HERE / "client.py"), "--plan", str(plan_path)]
        if not smoke:
            measured = directory / "measure"
            command = [sys.executable, str(HERE.parent / "measure_run.py"), "--label", run_id,
                       "--state", state, "--budget-s", "3600", "--interval-s", "0.5", "--out", str(measured),
                       "--note", "R2 external ComfyUI; tree_private excludes engine; cold_pagecache_unflushed; client wall excludes startup", "--", *command]
        with (directory / "client.log").open("xb") as output:
            process = subprocess.Popen(command, stdout=output, stderr=subprocess.STDOUT,
                                       creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
            try:
                rc = process.wait(timeout=3650)
            except (subprocess.TimeoutExpired, KeyboardInterrupt):
                # measure_run normally enforces 3600; contain its tree if it hangs.
                import psutil
                owner = psutil.Process(process.pid)
                children = owner.children(recursive=True)
                for child in children:
                    child.kill()
                owner.kill()
                psutil.wait_procs([owner, *children], timeout=5)
                raise
        require(rc == 0, f"client/measure exit {rc}; stop, no retry")
        sidecar = read_json(directory / "sidecar.json")
        require(sidecar.get("run_id") == run_id and sidecar.get("state") == state and sidecar.get("verdict") == "ok", "missing/invalid sidecar")
        require(sidecar.get("server", {}).get("server_id") == server.session["server_id"], "wrong server in sidecar")
        require(sha256(directory / "output.png") == sidecar["output"]["sha256"], "output/sidecar mismatch")
        if not smoke:
            reports = list(measured.glob("*.json"))
            require(len(reports) == 1, "missing/ambiguous measure report")
            report = read_json(reports[0])
            validate_measure(report, sidecar, run_id, state)
            require(report.get("commit_measurement", {}).get("is_real_commit_counter") is True, "real Windows commit counter required")
        return {"sidecar": sidecar, "path": str(directory / "sidecar.json"), "alias_id": alias_id,
                "output_prefix": prefix, "source": sidecar["output"]["server_path"], "sha256": sidecar["output"]["sha256"]}
    finally:
        cleanup_aliases(server.session, alias_id)
        # Watchdog may kill the client before it can write its sidecar/log.
        if not (directory / "sidecar.json").exists():
            write_new(directory / "sidecar.json", {"run_id": run_id, "state": state, "verdict": "FAIL:client_incomplete",
                      "server_id": server.session["server_id"], "plan": plan, **policy,
                      "execution_cached": None, "cached_nodes": None, "cache_validation_verdict": "unavailable"})
        if not (directory / "server.log").exists():
            log_evidence(server.session, log_offset, directory / "server.log")


def dry_run(config):
    manifest, graph, policy, checksum = frozen(config)
    print(json.dumps({"configuration": config, "workflow_sha256": checksum, **policy,
                      "accepted_model_classes": sorted(__import__("common").MODEL_CLASSES),
                      "sampler": next(n["inputs"] for n in graph.values() if n["class_type"] == "KSampler"),
                      "cold": manifest["configurations"][config]["cold"], "warm": manifest["configurations"][config]["warm"],
                      "action": "dry-run only: no server, uploads, setup or inference"}, indent=2))


def main():
    core, shared = default_paths()
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=["dry-run", "setup", "bench"])
    parser.add_argument("--core", type=Path, default=core)
    parser.add_argument("--shared", type=Path, default=shared)
    parser.add_argument("--work-root", type=Path, default=Path.home() / "OneDrive/Documentos/w3-measure/r2")
    parser.add_argument("--configuration", choices=[PRIMARY, SECONDARY], default=PRIMARY)
    parser.add_argument("--port", type=int, default=8191)
    parser.add_argument("--setup-report", type=Path)
    args = parser.parse_args()
    dry_run(args.configuration)
    if args.action == "dry-run":
        return 0
    require(os.name == "nt", "operator setup/benchmark requires Windows")
    require(1024 <= args.port <= 65535, "invalid port")
    provenance = verify(args.core.resolve(), args.shared.resolve())
    if args.action == "bench":
        require(args.setup_report is not None, "pass the reviewed successful setup report explicitly")
        report = read_json(args.setup_report)
        require(report.get("verdict") == "ok" and report.get("action") == "setup", "setup/smoke not passed")
        require(report.get("provenance_digest") == digest_json(provenance), "setup provenance differs; run setup again")
    root = args.work_root.resolve() / (args.action + "_" + uuid.uuid4().hex)
    root.mkdir(parents=True, exist_ok=False)
    write_new(root / "provenance.json", provenance)
    results, server = [], None
    summary = {"action": args.action, "configuration": args.configuration, "provenance_digest": digest_json(provenance),
               "verdict": "FAIL:incomplete", "root": str(root)}
    try:
        if args.action == "setup":
            server = Server(root, provenance, args.port)
            server.start()
            first = one_run(root, server, PRIMARY, "cold", 1, smoke=True)
            results.append(first)
            results.append(one_run(root, server, PRIMARY, "warm", 2, smoke=True, control=first))
            results.append(one_run(root, server, PRIMARY, "warm", 3, smoke=True))
            require(results[0]["sidecar"]["effective_nodes"] == results[1]["sidecar"]["effective_nodes"], "smoke control payload changed")
        else:
            # The third fresh cold server is retained for all three primary warms.
            for index in range(1, 4):
                if server:
                    server.stop()
                    server = None
                server = Server(root, provenance, args.port)
                server.start()
                results.append(one_run(root, server, args.configuration, "cold", index))
            if args.configuration == PRIMARY:
                for index in range(1, 4):
                    results.append(one_run(root, server, args.configuration, "warm", index))
            summary.update(warm_consistency([r["sidecar"] for r in results]))
        summary["verdict"] = "ok"
    except Exception as error:
        summary.update(verdict="FAIL:" + type(error).__name__, error=str(error))
        raise
    finally:
        try:
            if server:
                server.stop()
        except Exception as error:
            summary.update(verdict="FAIL:server_cleanup", cleanup_error=str(error))
            raise
        finally:
            summary["runs"] = [r["path"] for r in results]
            if args.action == "bench":
                summary.update(warm_consistency([r["sidecar"] for r in results]))
                if summary["warm_cache_divergence"]:
                    print("REVIEW REQUIRED: warm execution_cached sets differ; runs preserved, no automatic invalidation.")
            summary["h4_verdict"] = "NOT_DECIDED: review real measurements, OOM/thrashing and D-056 separately"
            write_new(root / "report.json", summary)
            print(f"Report: {root / 'report.json'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
