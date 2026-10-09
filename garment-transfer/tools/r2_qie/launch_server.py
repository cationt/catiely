"""External ComfyUI bootstrap: offline guard and startup assertions, no vendor edits.

Only the operator's setup/bench command invokes this module. Import is CPU-safe.
"""
import ipaddress
import json
import os
import runpy
import sys
from pathlib import Path


def is_loopback(host):
    if host in ("localhost", None):
        return True
    try:
        return ipaddress.ip_address(host).is_loopback
    except ValueError:
        return False


def network_guard(event, args):
    if event in ("socket.connect", "socket.sendto"):
        address = args[-1]
        if not isinstance(address, tuple) or not is_loopback(address[0]):
            raise RuntimeError(f"R2 offline guard blocked {event}: {address}")
    if event == "socket.getaddrinfo" and not is_loopback(args[0]):
        raise RuntimeError("R2 offline guard blocked external DNS")
    if event == "socket.bind":
        address = args[1]
        if isinstance(address, tuple) and not is_loopback(address[0]):
            raise RuntimeError("R2 requires loopback bind")


def main():
    session_path = Path(sys.argv[1]).resolve()
    session = json.loads(session_path.read_text(encoding="utf-8"))
    core = Path(session["core"])
    for key in ("HF_HUB_OFFLINE", "TRANSFORMERS_OFFLINE", "HF_DATASETS_OFFLINE", "HF_HUB_DISABLE_TELEMETRY", "DO_NOT_TRACK"):
        os.environ[key] = "1"
    sys.addaudithook(network_guard)

    def startup_evidence(event, args):
        if event != "socket.bind" or args[1] != ("127.0.0.1", session["port"]):
            return
        folders = sys.modules["folder_paths"]
        manager = sys.modules["comfy.model_management"]
        memory = sys.modules["comfy.memory_management"]
        classes = sys.modules["nodes"].NODE_CLASS_MAPPINGS
        expected_modules = {"UnetLoaderGGUF": core / "custom_nodes/ComfyUI-GGUF/nodes.py",
                            "CLIPLoader": core / "nodes.py", "VAELoader": core / "nodes.py"}
        for name, expected_module in expected_modules.items():
            actual_module = Path(sys.modules[classes[name].__module__].__file__).resolve()
            if actual_module != expected_module.resolve():
                raise RuntimeError(f"unexpected loader implementation: {name}: {actual_module}")
        resolved = {}
        for role, category in (("unet", "diffusion_models"), ("clip", "text_encoders"), ("vae", "vae")):
            expected = Path(session["provenance"]["weights"][role]["path"]).resolve()
            actual = Path(folders.get_full_path_or_raise(category, expected.name)).resolve()
            if actual != expected:
                raise RuntimeError(f"wrong asset resolution: {role}: {actual}")
            resolved[role] = str(actual)
        if manager.current_loaded_models or not memory.aimdo_enabled:
            raise RuntimeError("cold startup requires empty model manager and active DynamicVRAM")
        evidence = {"pid": os.getpid(), "server_id": session["server_id"], "loaded_models": 0,
                    "dynamic_vram": True, "resolved_weights": resolved, "network_guard": "loopback_only_python_audit"}
        with Path(session["bootstrap"]).open("x", encoding="utf-8") as stream:
            json.dump(evidence, stream, indent=2)
    sys.addaudithook(startup_evidence)
    sys.path.insert(0, str(core))
    os.chdir(core)
    sys.argv = [str(core / "main.py"), *session["flags"]]
    runpy.run_path(str(core / "main.py"), run_name="__main__")


if __name__ == "__main__":
    main()
