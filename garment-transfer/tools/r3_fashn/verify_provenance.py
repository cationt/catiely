#!/usr/bin/env python3
"""verify_provenance.py (R3) — provenance dos clones de código (fashn-vton-1.5 e fashn-human-parser) robusta a EOL (core.autocrlf).

Para cada repositório em `code_repos` do manifesto: (1) blob OIDs do commit pinado via `git ls-tree -r <commit>` (independem do working
tree); (2) sha256 do conteúdo normalizado CRLF→LF de cada arquivo listado; (3) HEAD == commit pinado. Tudo tem de bater.
Lição da R1-EI: com autocrlf=true o working tree vira CRLF e o sha256 bruto diverge do blob LF — por isso (1) e (2).

Uso: python verify_provenance.py --clone-dir <dir> --repo vton|human_parser [--manifest r3_manifest.json] [--json-out x.json]
Exit 0 ok · 1 divergência · 2 uso.
"""
import argparse, hashlib, json, os, subprocess, sys

HERE = os.path.dirname(os.path.abspath(__file__))


def sha256_normalized(path):
    b = open(path, "rb").read()
    lf = b.replace(b"\r\n", b"\n").replace(b"\r", b"\n")
    return hashlib.sha256(b).hexdigest(), hashlib.sha256(lf).hexdigest(), lf != b


def git_blob_oids(clone_dir, commit):
    try:
        out = subprocess.run(["git", "-C", clone_dir, "ls-tree", "-r", commit], capture_output=True, text=True, timeout=60)
        if out.returncode != 0:
            return None
        oids = {}
        for line in out.stdout.splitlines():
            parts = line.split(None, 3)
            if len(parts) == 4:
                oids[parts[3]] = parts[2]
        return oids
    except Exception:
        return None


def verify_clone(clone_dir, repo_entry):
    files = repo_entry["files"]; commit = repo_entry["commit"]
    rep = {"clone_dir": clone_dir, "repo": repo_entry["github"], "commit_pin": commit, "files": {}, "ok": True, "method": []}
    oids = git_blob_oids(clone_dir, commit)
    if oids:
        rep["method"].append("git_blob_oid")
        for f, info in files.items():
            got = oids.get(f); e = rep["files"].setdefault(f, {})
            e["blob_oid"] = got; e["blob_oid_ok"] = (got is not None and got == info["blob_oid"]); rep["ok"] &= e["blob_oid_ok"]
        try:
            head = subprocess.run(["git", "-C", clone_dir, "rev-parse", "HEAD"], capture_output=True, text=True, timeout=30).stdout.strip()
            rep["head"] = head; rep["head_ok"] = (head == commit); rep["ok"] &= rep["head_ok"]
        except Exception:
            rep["head"] = None; rep["head_ok"] = False; rep["ok"] = False
    elif os.path.isdir(os.path.join(clone_dir, ".git")):
        rep["method"].append("git_ls_tree_failed"); rep["ok"] = False
    else:
        rep["method"].append("no_git")
    rep["method"].append("sha256_lf_normalized")
    for f, info in files.items():
        p = os.path.join(clone_dir, *f.split("/")); e = rep["files"].setdefault(f, {})
        if not os.path.exists(p):
            e["status"] = "ausente"; rep["ok"] = False; continue
        raw, lf, changed = sha256_normalized(p)
        e.update({"sha256_raw": raw, "sha256_lf": lf, "eol_converted_in_working_tree": changed, "sha256_lf_ok": lf == info["sha256"]})
        e["status"] = "ok" if e["sha256_lf_ok"] else "sha256_divergente"; rep["ok"] &= e["sha256_lf_ok"]
    return rep


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--clone-dir", required=True); ap.add_argument("--repo", choices=["vton", "human_parser"], required=True)
    ap.add_argument("--manifest", default=os.path.join(HERE, "r3_manifest.json")); ap.add_argument("--json-out")
    a = ap.parse_args()
    man = json.load(open(a.manifest, encoding="utf-8"))
    rep = verify_clone(a.clone_dir, man["code_repos"][a.repo])
    js = json.dumps(rep, indent=1, ensure_ascii=False); print(js)
    if a.json_out:
        open(a.json_out, "w", encoding="utf-8").write(js)
    print("[verify_provenance] " + ("OK" if rep["ok"] else "DIVERGENCIA"), "metodo:", "+".join(rep["method"]))
    sys.exit(0 if rep["ok"] else 1)


if __name__ == "__main__":
    main()
