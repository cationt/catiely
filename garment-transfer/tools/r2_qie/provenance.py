"""Verify existing local files only. Never install or download anything."""
import hashlib
import importlib.metadata
import os
import platform
import subprocess
from pathlib import Path

from common import HERE, read_json, require, sha256


def default_paths():
    local = Path(os.environ.get("LOCALAPPDATA", Path.home() / "AppData/Local"))
    return (local / "Comfy-Desktop/ComfyUI-Installs/ComfyUI/ComfyUI",
            local / "Comfy-Desktop/ComfyUI-Shared")


def path_for(entry, core, shared):
    return ({"core": core, "shared": shared}[entry["root"]] / entry["path"]).resolve()


def gguf_identity(root):
    paths = sorted((root / ".tracking").read_text(encoding="utf-8-sig").splitlines())
    require(len(paths) == 17 and len(set(paths)) == 17, "GGUF tracking changed")
    hashes = {}
    for name in paths:
        path = (root / name).resolve()
        require(path.is_relative_to(root.resolve()), "GGUF tracking escapes root")
        hashes[name] = sha256(path)
    payload = "".join(f"{hashes[p]}  {p}\n" for p in paths)
    # Refuse extra executable Python files, even if omitted from .tracking.
    extra = {p.relative_to(root).as_posix() for p in root.rglob("*.py")} - set(paths)
    require(not extra, f"untracked GGUF Python source: {sorted(extra)}")
    return {"tracking_sha256": sha256(root / ".tracking"),
            "aggregate_sha256": hashlib.sha256(payload.encode()).hexdigest(), "files": hashes}


def verify(core, shared):
    manifest = read_json(HERE / "manifest.json")
    runtime = manifest["runtime"]
    require(platform.python_version() == runtime["python"], "run with pinned ComfyUI venv Python")
    packages = {p: importlib.metadata.version(p) for p in runtime["packages"]}
    require(packages == runtime["packages"], f"package versions changed: {packages}")
    command = ["git", "--git-dir", str(core / ".git"), "--work-tree", str(core)]
    head = subprocess.check_output(command + ["rev-parse", "HEAD"], text=True).strip()
    require(head == runtime["core_commit"], "ComfyUI core commit changed")
    require(not subprocess.check_output(command + ["status", "--porcelain", "--untracked-files=no"], text=True).strip(), "ComfyUI tracked tree is dirty")
    for relative, expected in runtime["core_sha256"].items():
        require(sha256(core / relative) == expected, f"core file changed: {relative}")
    gguf = gguf_identity(core / runtime["gguf"]["path"])
    for key in ("tracking_sha256", "aggregate_sha256"):
        require(gguf[key] == runtime["gguf"][key], f"GGUF {key} mismatch")
    desktop = Path(os.environ["LOCALAPPDATA"]) / runtime["desktop"]["relative_to_localappdata"]
    require(sha256(desktop) == runtime["desktop"]["sha256"], "Desktop binary changed")
    source = manifest["source_template"]
    require(sha256(core / source["installed_path"]) == source["sha256"], "installed official template changed")
    template_bytes = (core / source["installed_path"]).read_bytes()
    blob = hashlib.sha1(b"blob " + str(len(template_bytes)).encode() + b"\0" + template_bytes).hexdigest()
    require(blob == source["blob_oid"], "template differs from pinned official Git blob")
    require(sha256(core / source["blueprint_path"]) == source["blueprint_sha256"], "local blueprint changed")
    records = {}
    for group in ("inputs", "weights"):
        records[group] = {}
        for role, entry in manifest[group].items():
            path = path_for(entry, core, shared)
            require(path.is_file(), f"missing {role}: {path}; no download/fallback")
            stat = path.stat()
            require("size" not in entry or stat.st_size == entry["size"], f"wrong {role} size")
            actual = sha256(path)
            require(actual == entry["sha256"], f"wrong {role} SHA256")
            records[group][role] = {"path": str(path), "sha256": actual, "size": stat.st_size, "mtime_ns": stat.st_mtime_ns}
    from PIL import Image, ImageOps
    for record in records["inputs"].values():
        with Image.open(record["path"]) as image:
            require(getattr(image, "n_frames", 1) == 1, "input must be a single image")
            record["stored_dimensions"] = list(image.size)
            record["dimensions"] = list(ImageOps.exif_transpose(image).size)
    harness = {p.name: sha256(p) for p in HERE.iterdir() if p.suffix in {".py", ".ps1", ".json"}}
    return {"manifest_sha256": sha256(HERE / "manifest.json"), "harness_sha256": harness,
            "core": str(core), "shared": str(shared),
            "core_commit": head, "runtime": runtime, "packages": packages, "gguf": gguf, **records}


def verify_unchanged(provenance):
    require(sha256(HERE / "manifest.json") == provenance["manifest_sha256"], "manifest changed during batch")
    for name, checksum in provenance["harness_sha256"].items():
        require(sha256(HERE / name) == checksum, f"harness changed during batch: {name}")
    for group in ("inputs", "weights"):
        for record in provenance[group].values():
            stat = Path(record["path"]).stat()
            require(stat.st_size == record["size"] and stat.st_mtime_ns == record["mtime_ns"], "pinned asset changed during batch")
