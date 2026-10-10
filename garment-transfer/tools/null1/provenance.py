"""Read-only local verification; never imports torch or installs anything."""
import importlib.metadata as metadata
import importlib.util
import os
import platform
import subprocess
import sys
from pathlib import Path

from common import HERE, read_json, require, sha256


def roots(w3, core, shared):
    return {"w3": Path(w3), "core": Path(core), "shared": Path(shared),
            "r1_site": Path(w3)/"r1ei/.venv/Lib/site-packages"}


def package_dir(name):
    spec = importlib.util.find_spec(name)  # top-level only: does not import its __init__
    require(spec is not None and spec.origin, f"package missing: {name}")
    return Path(spec.origin).parent


def runtime(name):
    manifest = read_json(HERE/"manifest.json")
    require(platform.python_version() == manifest["runtime"][name]["python_version"], "Python version pin mismatch: " + name)
    versions = {k: metadata.version(k) for k in manifest["runtime"][name]["packages"]}
    require(versions == manifest["runtime"][name]["packages"], f"runtime pin mismatch: {name}: {versions}")
    result = {"python": sys.version, "executable": sys.executable, "packages": versions}
    if name == "r1ei":
        site = package_dir("diffusers").parent
        for entry in manifest["files"]:
            if entry["root"] == "r1_site":
                require(sha256(site/entry["path"], entry["lf"]) == entry["sha256"], "imported Diffusers source mismatch")
    if name == "r3":
        parser = package_dir("fashn_human_parser")
        for rel, expected in manifest["parser_files"].items():
            require(sha256(parser/rel, lf=True) == expected, f"parser source pin mismatch: {rel}")
        transforms = package_dir("fashn_vton")/"preprocessing/transforms.py"
        require(sha256(transforms, lf=True) == manifest["transforms_sha256_lf"], "ResizePad source pin mismatch")
        result.update(parser_dir=str(parser), transforms=str(transforms))
    return result


def frozen():
    manifest = read_json(HERE/"manifest.json")
    for item in manifest["workflows"].values():
        require(sha256(HERE/item["file"], lf=True) == item["sha256"], "frozen workflow changed")
    return manifest


def core_identity(core, expected):
    command = ["git", "--git-dir", str(core/".git"), "--work-tree", str(core)]
    head = subprocess.check_output([*command, "rev-parse", "HEAD"], text=True, timeout=30).strip()
    require(head == expected, "ComfyUI core commit changed")
    dirty = subprocess.check_output([*command, "status", "--porcelain", "--untracked-files=no"], text=True, timeout=30).strip()
    require(not dirty, "ComfyUI tracked tree is dirty")
    return head


def verify(paths):
    manifest = frozen()
    core_head = core_identity(paths["core"], manifest["core_commit"])
    records = []
    for entry in manifest["files"]:
        path = paths[entry["root"]]/entry["path"]
        require(sha256(path, entry["lf"]) == entry["sha256"], f"asset/source pin mismatch: {path}")
        records.append({**entry, "resolved_path": str(path.resolve()), "size": path.stat().st_size})
    a = paths[manifest["a"]["root"]]/manifest["a"]["path"]
    require(sha256(a) == manifest["a"]["sha256"], "A differs from Klein/R1-EI reference")
    records.append({"resolved_path": str(a), "sha256": sha256(a), "lf": False})
    environments = {"comfy": runtime("comfy")}
    for name in ("r1ei", "r3"):
        python = paths["w3"]/name/".venv/Scripts/python.exe"
        process = subprocess.run([str(python), "-B", str(HERE/"worker.py"), "--inspect", name],
                                 capture_output=True, text=True, encoding="utf-8", timeout=60,
                                 env=dict(os.environ, PYTHONUTF8="1"),
                                 creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        require(process.returncode == 0, f"runtime verify failed {name}: {process.stderr}")
        import json
        environments[name] = json.loads(process.stdout)
    return {"manifest_sha256": sha256(HERE/"manifest.json", lf=True), "files": records,
            "environments": environments, "a": str(a), "a_sha256": sha256(a),
            "core": str(paths["core"]), "core_commit": core_head}


def unchanged(provenance):
    if "core" in provenance:
        core_identity(Path(provenance["core"]), provenance["core_commit"])
    for item in provenance["files"]:
        require(sha256(item["resolved_path"], item["lf"]) == item["sha256"], "asset changed since preflight")
    for name, expected in provenance.get("implementation_sha256", {}).items():
        require(sha256(HERE/name, lf=True) == expected, "implementation changed since preflight")
