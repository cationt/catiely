"""One owned server per route; fresh graph, strict history, deadline, no retry."""
import asyncio
import json
import os
import re
import shutil
import socket
import subprocess
import sys
import time
import uuid
from pathlib import Path

from common import HERE, geometry, read_json, require, rgb, sha256, write_new
from provenance import frozen


def refuse_existing_server(port):
    import psutil
    for process in psutil.process_iter(["pid", "name", "cmdline"]):
        args = process.info["cmdline"] or []
        if process.pid == os.getpid():
            continue
        if any(Path(a).name == "launch_server.py" for a in args):
            raise RuntimeError("another managed ComfyUI is running; close it before Generate")
        if "python" in (process.info["name"] or "").lower() and any(Path(a).name == "main.py" for a in args):
            try:
                cwd = process.cwd()
            except psutil.Error:
                cwd = "ComfyUI unknown"
            require("comfy" not in (" ".join(args)+cwd).lower(), "close existing ComfyUI before Generate")
    with socket.socket() as probe:
        if hasattr(socket, "SO_EXCLUSIVEADDRUSE"):
            probe.setsockopt(socket.SOL_SOCKET, socket.SO_EXCLUSIVEADDRUSE, 1)
        probe.bind(("127.0.0.1", port))


def owned_pids(pid):
    import psutil
    return {pid, *(p.pid for p in psutil.Process(pid).children(recursive=True))}


def assert_owner(session):
    import psutil
    process = psutil.Process(session["pid"])
    require(process.create_time() == session["created"], "PID reused")
    require(session["launch_path"] in process.cmdline(), "wrong server process")
    listeners = [c for c in psutil.net_connections(kind="tcp") if c.status == psutil.CONN_LISTEN and c.laddr.port == session["port"]]
    require(listeners and all(c.pid in owned_pids(process.pid) and c.laddr.ip == "127.0.0.1" for c in listeners), "server endpoint is not exclusively owned")


def stop_owned(process, created):
    import psutil
    try:
        owner = psutil.Process(process.pid)
        require(owner.create_time() == created, "refuse to stop reused PID")
        children = owner.children(recursive=True)
        for item in [*children, owner]:
            try:
                item.terminate()
            except psutil.NoSuchProcess:
                pass
        _, alive = psutil.wait_procs([*children, owner], timeout=5)
        for item in alive:
            item.kill()
        _, alive = psutil.wait_procs(alive, timeout=5)
        require(not alive, "owned processes survived termination")
    except psutil.NoSuchProcess:
        pass
    process.wait(timeout=5)


async def request(http, session, path, method="GET", **kwargs):
    assert_owner(session)
    require(path.startswith("/") and not path.startswith("//"), "unsafe endpoint")
    async with http.request(method, f"http://127.0.0.1:{session['port']}{path}", allow_redirects=False, **kwargs) as response:
        require(response.status == 200, f"HTTP {response.status}: {await response.text()}")
        return await response.json()


def validate_history(record, prompt_id, graph):
    status = record.get("status", {})
    messages = status.get("messages")
    require(isinstance(messages, list) and messages, "status.messages required")
    cached = []
    cache_event = False
    for event in messages:
        require(isinstance(event, list) and len(event) == 2 and isinstance(event[1], dict), "malformed history event")
        kind, payload = event
        require(payload.get("prompt_id") == prompt_id, "history event belongs to another prompt")
        require(kind not in ("execution_error", "execution_interrupted"), "ComfyUI execution failed")
        if kind == "execution_cached":
            cache_event = True
            require(isinstance(payload.get("nodes"), list), "missing cache nodes")
            cached.extend(payload["nodes"])
    require(cache_event and not cached, "fresh null server must report execution_cached=[]")
    require(status.get("completed") is True and status.get("status_str") == "success", "incomplete history")
    recorded_prompt = record.get("prompt")
    require(isinstance(recorded_prompt, list) and len(recorded_prompt) >= 3, "missing history prompt")
    require(recorded_prompt[1] == prompt_id, "history prompt mismatch")
    require(execution_graph(recorded_prompt[2]) == graph, "history graph changed")
    return cached


def execution_graph(graph):
    # Pinned execution.py attaches LoadImage's fingerprint at node.is_changed.
    # Strip only that execution metadata; never class_type, inputs or edges.
    require(isinstance(graph, dict), "invalid history graph")
    require(all(isinstance(node, dict) for node in graph.values()), "invalid history node")
    return {key: {k: v for k, v in node.items() if k != "is_changed"} for key, node in graph.items()}


async def prompt(session, a_path, directory, route, deadline, evidence):
    import aiohttp
    manifest = frozen()
    graph = read_json(HERE/manifest["workflows"][route]["file"])
    name = f"A_{session['server_id']}{Path(a_path).suffix}"
    graph["A"]["inputs"]["image"] = name
    prefix = "null1_"+session["server_id"]
    graph["save"]["inputs"]["filename_prefix"] = prefix
    write_new(directory/"workflow_api.json", graph)
    async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=15), trust_env=False) as http:
        start = time.monotonic()
        last = None
        while time.monotonic()-start < min(180, deadline):
            require(session["process"].poll() is None, "ComfyUI startup failed; inspect server.log")
            try:
                queue = await request(http, session, "/queue")
                require(queue.get("queue_running") == [] and queue.get("queue_pending") == [], "server not idle")
                bootstrap = read_json(session["bootstrap"])
                require(bootstrap["server_id"] == session["server_id"] and bootstrap["pid"] in owned_pids(session["pid"]), "bootstrap identity mismatch")
                require(bootstrap["loaded_models"] == 0, "cold model manager not empty")
                break
            except (OSError, ValueError, RuntimeError) as error:
                last = str(error)
                await asyncio.sleep(.25)
        else:
            raise RuntimeError(f"ComfyUI startup deadline: {last}")
        evidence["startup_s"] = time.monotonic()-start
        evidence["bootstrap"] = bootstrap
        with Path(a_path).open("rb") as stream:
            form = aiohttp.FormData()
            form.add_field("image", stream, filename=name, content_type="application/octet-stream")
            form.add_field("type", "input")
            form.add_field("overwrite", "false")
            upload = await request(http, session, "/upload/image", "POST", data=form)
        require(upload.get("name") == name and upload.get("subfolder", "") == "" and upload.get("type") == "input", "upload identity changed")
        uploaded = directory/"server/input"/name
        require(sha256(uploaded) == sha256(a_path), "uploaded A differs")
        evidence["uploaded_a_sha256"] = sha256(uploaded)
        started = time.monotonic()
        submitted = await request(http, session, "/prompt", "POST", json={"prompt": graph, "client_id": uuid.uuid4().hex})
        prompt_id = submitted.get("prompt_id")
        require(isinstance(prompt_id, str) and prompt_id and not submitted.get("node_errors"), "prompt rejected")
        evidence["prompt_id"] = prompt_id
        while time.monotonic()-start < deadline:
            require(session["process"].poll() is None, "ComfyUI died during encode/decode")
            history = await request(http, session, "/history/"+prompt_id)
            if prompt_id in history:
                record = history[prompt_id]
                write_new(directory/"history.json", record)
                evidence["execution_cached"] = validate_history(record, prompt_id, graph)
                break
            await asyncio.sleep(.25)
        else:
            raise RuntimeError("O_null1 deadline; stop without retry")
        evidence["wall_s"] = time.monotonic()-started
        images = record.get("outputs", {}).get("save", {}).get("images", [])
        require(len(images) == 1, "exactly one null output required")
        item = images[0]
        require(item.get("type") == "output" and item.get("subfolder", "") == "", "wrong output location")
        require(re.fullmatch(re.escape(prefix)+r"_\d+_\.png", item.get("filename", "")), "wrong output identity")
        source = directory/"server/output"/item["filename"]
        from PIL import Image
        with Image.open(source) as im:
            require(im.mode == "RGB" and list(im.size) == geometry(route)["internal"], "native output mode/grid mismatch")
            require(execution_graph(json.loads(im.info.get("prompt", "{}"))) == graph, "PNG graph metadata mismatch")
            im.verify()
        with source.open("rb") as origin, (directory/"native.png").open("xb") as destination:
            shutil.copyfileobj(origin, destination)
        evidence["native_sha256"] = sha256(directory/"native.png")
        evidence["vae"] = read_json(session["vae_evidence"])
        require(evidence["vae"]["spatial_compression"] == (16 if route == "klein" else 8), "unexpected VAE compression")
        uploaded.unlink()


def generate(route, directory, paths, a_path, port, deadline, evidence):
    import psutil
    refuse_existing_server(port)
    server_id = uuid.uuid4().hex
    for folder in ("input", "output", "user", "temp"):
        (directory/"server"/folder).mkdir(parents=True, exist_ok=False)
    core = paths["core"]
    vae = core/"models/vae/flux2-vae.safetensors" if route == "klein" else paths["shared"]/"models/diffusion_models/vae/qwen_image_vae.safetensors"
    model_paths = directory/"server/model_paths.yaml"
    write_new(model_paths, {"null1": {"is_default": True, "vae": str(vae.parent)}})
    flags = ["--listen", "127.0.0.1", "--port", str(port), "--verbose", "DEBUG", "--log-stdout", "--bf16-vae",
             "--disable-auto-launch", "--disable-api-nodes", "--disable-all-custom-nodes", "--extra-model-paths-config", str(model_paths),
             "--front-end-root", str(core/".venv/Lib/site-packages/comfyui_frontend_package/static")]
    for folder in ("input", "output", "user", "temp"):
        flags += ["--"+folder+"-directory", str(directory/"server"/folder)]
    session = {"action": "generate", "server_id": server_id, "core": str(core), "vae": str(vae), "flags": flags, "port": port,
               "bootstrap": str(directory/"server/bootstrap.json"), "vae_evidence": str(directory/"server/vae.json"),
               "launch_path": str(directory/"server/launch.json")}
    write_new(session["launch_path"], session)
    with (directory/"server.log").open("xb") as log:
        process = subprocess.Popen([sys.executable, "-u", str(HERE/"launch_server.py"), session["launch_path"]],
                                   cwd=core, stdout=log, stderr=subprocess.STDOUT, env=dict(os.environ, PYTHONUTF8="1"),
                                   creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        created = psutil.Process(process.pid).create_time()
        session.update(process=process, pid=process.pid, created=created)
        evidence.update(server_id=server_id, process_pid=process.pid, flags=flags)
        try:
            asyncio.run(prompt(session, a_path, directory, route, deadline, evidence))
        finally:
            stop_owned(process, created)
    log_text = (directory/"server.log").read_text(encoding="utf-8", errors="replace")
    require(not re.search(r"out of memory|OutOfMemoryError|retrying with tiled|tiling directly", log_text, re.I), "VAE OOM/fallback invalidates null")
    evidence["log_sha256"] = sha256(directory/"server.log")
    evidence["load_evidence"] = [s for s in log_text.splitlines() if re.search(r"VAE|loaded|Prompt executed", s)]
