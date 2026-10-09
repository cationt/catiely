"""One prompt per process. History is mandatory; websocket times the sampler.

Exit 23 = cached_result, 2 = all other failures. No retry or fallback.
"""
import argparse
import asyncio
import json
import os
import re
import shutil
import time
import uuid
from pathlib import Path

from common import (CachedResult, EXIT_CACHED_RESULT, EXIT_FAILURE, HERE, cache_policy,
                    digest_json, execution_graph, frozen, read_json, render, require, sha256,
                    validate_history, write_new)


def assert_owner(session):
    import psutil
    process = psutil.Process(session["pid"])
    require(process.create_time() == session["process_created"], "server PID reused")
    require(str(HERE / "launch_server.py") in process.cmdline(), "wrong server executable command")
    require(session["launch_path"] in process.cmdline(), "wrong server session")
    listeners = [c for c in psutil.net_connections(kind="tcp")
                 if c.status == psutil.CONN_LISTEN and c.laddr.port == session["port"]]
    require(listeners and all(c.pid == session["pid"] and c.laddr.ip == "127.0.0.1" for c in listeners), "endpoint not exclusively owned by new server")


async def request(http, session, path, **kwargs):
    require(path.startswith("/") and not path.startswith("//"), "invalid local endpoint")
    method = kwargs.pop("method", "GET")
    async with http.request(method, f"http://127.0.0.1:{session['port']}{path}", allow_redirects=False, **kwargs) as response:
        require(response.status == 200, f"HTTP {response.status}: {await response.text()}")
        return await response.json()


async def upload_inputs(session, alias_id):
    """Unique byte copies staged via upload/image; caller always cleans aliases."""
    import aiohttp
    require(re.fullmatch(r"[a-zA-Z0-9_-]+", alias_id) is not None, "unsafe alias ID")
    assert_owner(session)
    result = {}
    async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=60), trust_env=False) as http:
        for role, original in session["provenance"]["inputs"].items():
            source = Path(original["path"])
            require(sha256(source) == original["sha256"], f"{role} source changed")
            name = f"{role}_{alias_id}{source.suffix}"
            target = Path(session["input_dir"]) / name
            require(not target.exists(), "alias already exists")
            # Multipart sends the unchanged source bytes; disk copy is made by ComfyUI.
            with source.open("rb") as stream:
                form = aiohttp.FormData()
                form.add_field("image", stream, filename=name, content_type="application/octet-stream")
                form.add_field("type", "input")
                form.add_field("overwrite", "false")
                response = await request(http, session, "/upload/image", method="POST", data=form)
            require(response.get("name") == name and response.get("subfolder", "") == "" and response.get("type") == "input", "upload identity changed")
            require(sha256(target) == original["sha256"], "uploaded copy SHA256 differs")
            result[role] = {"name": name, "path": str(target), "sha256": sha256(target), "original_sha256": original["sha256"]}
    return result


def cleanup_aliases(session, alias_id):
    root = Path(session["input_dir"]).resolve()
    require(re.fullmatch(r"[a-zA-Z0-9_-]+", alias_id) is not None, "unsafe cleanup ID")
    for role, original in session["provenance"]["inputs"].items():
        path = root / f"{role}_{alias_id}{Path(original['path']).suffix}"
        require(path.resolve().parent == root, "alias escapes owned input directory")
        path.unlink(missing_ok=True)


def validate_output(record, graph, session, plan, output_path):
    save = next(i for i, n in graph.items() if n["class_type"] == "SaveImage")
    images = record.get("outputs", {}).get(save, {}).get("images", [])
    require(len(images) == 1, "exactly one output required")
    item = images[0]
    name = item.get("filename", "")
    require(item.get("type") == "output" and item.get("subfolder", "") == "", "unexpected output location")
    require(re.fullmatch(re.escape(plan["output_prefix"]) + r"_\d+_\.png", name) is not None, "stale/wrong output prefix")
    source = (Path(session["output_dir"]) / name).resolve()
    require(source.parent == Path(session["output_dir"]).resolve(), "output escapes server directory")
    require(source.is_file(), "server output is missing")
    if plan.get("control"):
        require(str(source) == plan["control_source"] and sha256(source) == plan["control_sha256"], "wrong cached smoke output")
    else:
        require(not plan["preexisting_outputs"], "run prefix already existed")
        require(source.stat().st_mtime_ns >= plan["prepared_at_ns"], "output predates run")
    from PIL import Image
    with Image.open(source) as image:
        require(image.format == "PNG" and getattr(image, "n_frames", 1) == 1, "output is not one PNG")
        require(list(image.size) == plan["expected_dimensions"], "output dimensions differ")
        require(execution_graph(json.loads(image.info.get("prompt", "{}"))) == graph, "PNG workflow metadata mismatch")
        image.verify()
    with source.open("rb") as stream, output_path.open("xb") as target:
        shutil.copyfileobj(stream, target)
    require(sha256(source) == sha256(output_path), "output copy differs")
    return {"path": str(output_path), "sha256": sha256(output_path), "server_path": str(source),
            "dimensions": plan["expected_dimensions"], "cached_smoke_control": bool(plan.get("control"))}


def log_evidence(session, offset, destination, wait_for_prompt=False):
    deadline = time.monotonic() + (2 if wait_for_prompt else 0)
    while True:
        with Path(session["process_log"]).open("rb") as stream:
            stream.seek(offset)
            raw = stream.read()
        if b"Prompt executed in " in raw or time.monotonic() >= deadline:
            break
        time.sleep(0.02)
    with destination.open("xb") as stream:
        stream.write(raw)
    text = raw.decode("utf-8", errors="replace")
    relevant = [line for line in text.splitlines() if re.search(r"loaded|loading|dynamic|Prompt executed|memory|VRAM|out of memory|OOM", line, re.I)]
    times = re.findall(r"Prompt executed in ([0-9.]+) seconds", text)
    # Pinned core switches log formatting after 600 seconds.
    clock_times = re.findall(r"Prompt executed in (\d{2}):(\d{2}):(\d{2})", text)
    logged_s = float(times[-1]) if times else (sum(int(v) * scale for v, scale in zip(clock_times[-1], (3600, 60, 1))) if clock_times else None)
    return {"path": str(destination), "sha256": sha256(destination), "relevant_lines": relevant,
            "prompt_executed_s": logged_s,
            "prompt_log_resolution_s": 1 if clock_times else 0.01,
            "oom_detected": bool(re.search(r"out of memory|OutOfMemoryError", text, re.I))}


async def execute(plan, session, evidence):
    import aiohttp
    manifest, template, policy, freeze_sha = frozen(plan["configuration"], plan["smoke"])
    evidence.update(policy)
    graph = render(template, plan["aliases"]["A"]["name"], plan["aliases"]["B"]["name"], plan["output_prefix"])
    require(graph == plan["workflow"], "plan differs from frozen workflow")
    require(session["provenance"]["manifest_sha256"] == sha256(HERE / "manifest.json"), "manifest changed")
    require(plan["state"] in ("cold", "warm"), "invalid state")
    require(not plan.get("control") or (plan["smoke"] and plan["state"] == "warm"), "cache control forbidden in benchmark")
    for role, alias in plan["aliases"].items():
        require(sha256(alias["path"]) == alias["sha256"] == alias["original_sha256"] == manifest["inputs"][role]["sha256"], "input copy changed")
    evidence.update(workflow_sha256=freeze_sha, rendered_workflow_sha256=digest_json(graph), effective_nodes=graph,
                    inputs=plan["aliases"], manifest_sha256=sha256(HERE / "manifest.json"))
    assert_owner(session)
    sampler = next(i for i, n in graph.items() if n["class_type"] == "KSampler")
    decode = next(i for i, n in graph.items() if n["class_type"] == "VAEDecode")
    evidence["steps"] = graph[sampler]["inputs"]["steps"]
    client_id = uuid.uuid4().hex
    async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=60), trust_env=False) as http:
        stats = await request(http, session, "/system_stats")
        require(stats.get("system", {}).get("comfyui_version") == manifest["runtime"]["core_version"], "wrong ComfyUI version")
        evidence["system_stats"] = stats
        queue = await request(http, session, "/queue")
        require(queue.get("queue_running") == [] and queue.get("queue_pending") == [], "server not idle")
        async with http.ws_connect(f"http://127.0.0.1:{session['port']}/ws?clientId={client_id}", max_msg_size=16 * 1024 * 1024) as ws:
            started = time.perf_counter()
            response = await request(http, session, "/prompt", method="POST", json={"prompt": graph, "client_id": client_id})
            prompt_id = response.get("prompt_id")
            require(isinstance(prompt_id, str) and prompt_id and not response.get("node_errors"), "prompt rejected")
            evidence["prompt_id"] = prompt_id
            times, events = {}, []
            deadline = started + 3550
            record = None
            while time.perf_counter() < deadline:
                try:
                    message = await ws.receive(timeout=1)
                except asyncio.TimeoutError:
                    message = None
                if message is not None:
                    require(message.type not in (aiohttp.WSMsgType.CLOSED, aiohttp.WSMsgType.ERROR), "websocket closed")
                    if message.type == aiohttp.WSMsgType.TEXT:
                        event = json.loads(message.data)
                        data = event.get("data", {})
                        if data.get("prompt_id") == prompt_id:
                            elapsed = time.perf_counter() - started
                            events.append({"t_s": elapsed, **event})
                            if event.get("type") == "executing" and data.get("node") is not None:
                                times.setdefault(data["node"], elapsed)
                            # Even failures must read history/status.messages for audit.
                history = await request(http, session, f"/history/{prompt_id}")
                if prompt_id in history:
                    record = history[prompt_id]
                    # Drain already-buffered executing messages before computing timing.
                    for _ in range(100):
                        try:
                            message = await ws.receive(timeout=0.02)
                        except asyncio.TimeoutError:
                            break
                        if message.type == aiohttp.WSMsgType.TEXT:
                            event = json.loads(message.data)
                            data = event.get("data", {})
                            if data.get("prompt_id") == prompt_id:
                                elapsed = time.perf_counter() - started
                                events.append({"t_s": elapsed, **event})
                                if event.get("type") == "executing" and data.get("node") is not None:
                                    times.setdefault(data["node"], elapsed)
                    break
            require(record is not None, "client deadline exceeded")
            evidence["history"] = record
            evidence["websocket_events"] = events
            stored = record.get("prompt", [])
            require(len(stored) >= 3 and stored[1] == prompt_id and execution_graph(stored[2]) == graph, "history workflow/prompt mismatch")
            evidence.update(validate_history(record, prompt_id, graph, plan["state"], plan.get("control", False)))
            if not plan.get("control"):
                require(sampler in times and decode in times and times[decode] > times[sampler], "missing sampler timing events")
                evidence["sampling_s"] = times[decode] - times[sampler]
                evidence["per_step_s"] = evidence["sampling_s"] / evidence["steps"]
            else:
                evidence.update(sampling_s=None, per_step_s=None)
            evidence["sampling_clock"] = "client monotonic receive timestamps: KSampler executing -> VAEDecode executing; includes sampler load/offload and event latency"
            evidence["output"] = validate_output(record, graph, session, plan, Path(plan["run_dir"]) / "output.png")
            evidence["wall_s"] = time.perf_counter() - started
            assert_owner(session)


def run(plan_path):
    plan = read_json(plan_path)
    run_dir = Path(plan["run_dir"])
    sidecar = run_dir / "sidecar.json"
    require(not sidecar.exists() and not (run_dir / "output.png").exists() and not (run_dir / "server.log").exists(), "run already used")
    session = read_json(plan["session_path"])
    evidence = {"schema_version": 1, "run_id": plan["run_id"], "configuration": plan["configuration"],
                "state": plan["state"], "smoke": plan["smoke"], "client_pid": os.getpid(),
                "server": session, "startup_s": session["startup_s"],
                "cold_pagecache_unflushed": plan["state"] == "cold", "verdict": "FAIL:incomplete",
                "execution_cached": None, "cached_nodes": None, "cache_validation_verdict": "unavailable"}
    rc = EXIT_FAILURE
    try:
        asyncio.run(execute(plan, session, evidence))
        evidence["verdict"] = "ok"
        rc = 0
    except CachedResult as error:
        evidence.update(error.evidence)
        evidence["verdict"] = "FAIL:cached_result"
        rc = EXIT_CACHED_RESULT
    except Exception as error:
        evidence["verdict"] = "FAIL:" + type(error).__name__
        evidence["error"] = str(error)
    finally:
        try:
            evidence["server_log"] = log_evidence(session, plan["log_offset"], run_dir / "server.log", wait_for_prompt=(rc == 0))
            if evidence["verdict"] == "ok":
                require(evidence["server_log"]["prompt_executed_s"] is not None, "missing Prompt executed log")
                require(not evidence["server_log"]["oom_detected"], "OOM in server log")
        except Exception as error:
            evidence["log_error"] = str(error)
            if rc == 0:
                evidence["verdict"], rc = "FAIL:server_log", EXIT_FAILURE
        write_new(sidecar, evidence)
    print(json.dumps({k: evidence.get(k) for k in ("run_id", "verdict", "wall_s", "sampling_s", "per_step_s", "cached_nodes")}))
    return rc


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--plan", required=True)
    raise SystemExit(run(parser.parse_args().plan))
