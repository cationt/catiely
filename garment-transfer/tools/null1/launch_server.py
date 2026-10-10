"""Private ComfyUI for one null roundtrip. Invoked only by Generate, never Plan/Verify."""
import os
import runpy
import sys
from pathlib import Path

from common import read_json, require, write_new
from offline import install


def fail_fast(error):
    # Pinned ComfyUI normally catches OOM and retries tiled VAE. Disallow that
    # operational fallback without altering encode/decode on the successful path.
    raise error


def main():
    session = read_json(sys.argv[1])
    require(session["action"] == "generate", "explicit Generate required")
    install()
    core = Path(session["core"])

    def startup(event, args):
        if event != "socket.bind" or args[1] != ("127.0.0.1", session["port"]):
            return
        torch = sys.modules["torch"]
        folders = sys.modules["folder_paths"]
        manager = sys.modules["comfy.model_management"]
        classes = sys.modules["nodes"].NODE_CLASS_MAPPINGS
        require(torch.cuda.is_available(), "CUDA required; no CPU fallback")
        require(not manager.current_loaded_models, "private ComfyUI must start with no loaded model")
        loader = classes["VAELoader"]
        require(Path(sys.modules[loader.__module__].__file__).resolve() == (core/"nodes.py").resolve(), "unexpected VAELoader")
        selected = Path(folders.get_full_path_or_raise("vae", Path(session["vae"]).name)).resolve()
        require(selected == Path(session["vae"]).resolve(), "wrong VAE selected by ComfyUI")
        torch.manual_seed(42)
        torch.cuda.manual_seed_all(42)
        manager.raise_non_oom = fail_fast
        original = loader.load_vae

        def checked_load(instance, *arguments, **kwargs):
            result = original(instance, *arguments, **kwargs)
            vae = result[0]
            require(vae.device.type == "cuda" and vae.vae_dtype == torch.bfloat16, "VAE device/dtype mismatch")
            write_new(session["vae_evidence"], {"device": str(vae.device), "dtype": str(vae.vae_dtype),
                      "class": type(vae.first_stage_model).__name__, "spatial_compression": vae.spacial_compression_encode(),
                      "path": str(selected), "oom_fallback": "disabled: exceptions re-raised"})
            return result
        loader.load_vae = checked_load
        write_new(session["bootstrap"], {"pid": os.getpid(), "server_id": session["server_id"],
                  "loaded_models": 0, "vae": str(selected), "network": "loopback_only_python_audit"})

    sys.addaudithook(startup)
    sys.path.insert(0, str(core))
    os.chdir(core)
    sys.argv = [str(core/"main.py"), *session["flags"]]
    runpy.run_path(str(core/"main.py"), run_name="__main__")


if __name__ == "__main__":
    main()
