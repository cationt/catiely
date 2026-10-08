#!/usr/bin/env python3
"""verify_provenance.py — verificação de provenance do clone Easy-Insert robusta a EOL (Windows core.autocrlf).

Bug reproduzido (2026-10-08): com autocrlf=true, `utils.py` do working tree virou CRLF (sha256 7aa544c6…) enquanto o pin é do blob LF
(d84f0cbc…). Aqui a verificação é feita (1) pelos **blob OIDs do commit** (`git ls-tree <commit>`), que independem do working tree, e
(2) pelo sha256 do conteúdo **normalizado CRLF→LF** de cada arquivo do working tree. Ambos têm de bater com o manifesto.

Uso: python verify_provenance.py --clone-dir <dir> [--manifest tools/r1ei/r1ei_manifest.json] [--json-out x.json]
Exit 0 ok · 1 divergência · 2 uso.
"""
import argparse, hashlib, json, os, subprocess, sys

HERE = os.path.dirname(os.path.abspath(__file__))
FILES = ("utils.py", "inference_diffusers.py", "README.md", "LICENSE", "requirements.txt")


def sha256_bytes(b):
    return hashlib.sha256(b).hexdigest()


def sha256_normalized(path):
    """sha256 do arquivo com CRLF→LF (e CR solto→LF); devolve (sha_raw, sha_lf, eol_changed)."""
    b = open(path, "rb").read()
    lf = b.replace(b"\r\n", b"\n").replace(b"\r", b"\n")
    return sha256_bytes(b), sha256_bytes(lf), lf != b


def git_blob_oids(clone_dir, commit):
    try:
        out = subprocess.run(["git", "-C", clone_dir, "ls-tree", commit] + list(FILES), capture_output=True, text=True, timeout=30)
        if out.returncode != 0:
            return None
        oids = {}
        for line in out.stdout.splitlines():
            parts = line.split()
            if len(parts) >= 4:
                oids[parts[3]] = parts[2]
        return oids
    except Exception:
        return None


def verify_clone(clone_dir, manifest):
    ei = manifest["easy_insert"]; rep = {"clone_dir": clone_dir, "commit_pin": ei["commit"], "files": {}, "ok": True, "method": []}
    oids = git_blob_oids(clone_dir, ei["commit"])
    if oids:
        rep["method"].append("git_blob_oid")
        for f in FILES:
            exp = ei.get("files_git_blob_oid", {}).get(f)
            got = oids.get(f)
            rep["files"].setdefault(f, {})["blob_oid"] = got; rep["files"][f]["blob_oid_ok"] = (exp is not None and got == exp)
            rep["ok"] &= rep["files"][f]["blob_oid_ok"]
        try:
            head = subprocess.run(["git", "-C", clone_dir, "rev-parse", "HEAD"], capture_output=True, text=True, timeout=30).stdout.strip()
            rep["head"] = head; rep["head_ok"] = (head == ei["commit"]); rep["ok"] &= rep["head_ok"]
        except Exception:
            rep["head"] = None
    elif os.path.isdir(os.path.join(clone_dir, ".git")):
        # é um repositório git mas o commit pinado não pôde ser listado (pin errado, clone raso sem o commit, git ausente): divergência
        rep["method"].append("git_ls_tree_failed"); rep["ok"] = False
    else:
        rep["method"].append("no_git")
    rep["method"].append("sha256_lf_normalized")
    for f in FILES:
        p = os.path.join(clone_dir, f)
        e = rep["files"].setdefault(f, {})
        if not os.path.exists(p):
            e["status"] = "ausente"; rep["ok"] = False; continue
        raw, lf, changed = sha256_normalized(p)
        e.update({"sha256_raw": raw, "sha256_lf": lf, "eol_converted_in_working_tree": changed, "sha256_lf_ok": lf == ei["files_sha256"][f]})
        e["status"] = "ok" if e["sha256_lf_ok"] else "sha256_divergente"
        rep["ok"] &= e["sha256_lf_ok"]
    return rep


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--clone-dir", required=True); ap.add_argument("--manifest", default=os.path.join(HERE, "r1ei_manifest.json")); ap.add_argument("--json-out")
    a = ap.parse_args()
    rep = verify_clone(a.clone_dir, json.load(open(a.manifest, encoding="utf-8")))
    js = json.dumps(rep, indent=1, ensure_ascii=False); print(js)
    if a.json_out:
        open(a.json_out, "w", encoding="utf-8").write(js)
    print("[verify_provenance] " + ("OK" if rep["ok"] else "DIVERGENCIA"), "metodo:", "+".join(rep["method"]))
    sys.exit(0 if rep["ok"] else 1)


if __name__ == "__main__":
    main()
