#!/usr/bin/env python3
"""hf_fetch.py — download pinado dos pesos da R1-EI via huggingface_hub.snapshot_download (allow_patterns + revision) e verificação.

Por que não `hf download --include a b c`: no huggingface_hub 1.27 o CLI (typer) lê um único valor por `--include`; os padrões seguintes
viram `filenames` posicionais e o CLI avisa "Ignoring --include since filenames have been explicitly set" — a base veio incompleta
(~8,2 GB) e o LoRA com "Fetching 0 files" (reproduzido em 2026-10-08). snapshot_download com lista `allow_patterns` não tem esse problema.

Uso:
  python hf_fetch.py --what base --dest <dir> [--verify-sha]
  python hf_fetch.py --what lora --dest <dir> [--verify-sha]
  python hf_fetch.py --what base --dest <dir> --verify-only --verify-sha     # só confere o que já está no disco
Exit 0 ok · 1 verificação falhou · 2 uso/erro de download.
"""
import argparse, hashlib, json, os, sys

HERE = os.path.dirname(os.path.abspath(__file__))

BASE_PATTERNS = ["transformer/*", "text_encoder/*", "tokenizer/*", "vae/*", "scheduler/*", "model_index.json"]
LORA_PATTERNS = ["*.safetensors", "*.json"]


def allow_patterns_for(what):
    return list(BASE_PATTERNS) if what == "base" else list(LORA_PATTERNS)


def repo_and_revision(manifest, what):
    sec = manifest["base_model"] if what == "base" else manifest["lora"]
    return sec["repo"], sec["revision"]


def sha256_file(p):
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 22), b""):
            h.update(chunk)
    return h.hexdigest()


def expected_files(manifest, what):
    """{relpath: {"size_bytes", "sha256"}} dos arquivos que o runner exige (base) ou o LoRA."""
    if what == "base":
        exp = {k: dict(v) for k, v in manifest["base_model"]["files_needed_by_runner"].items()}
        for rel in manifest["base_model"]["small_files_needed"]:
            exp.setdefault(rel, {})
        return exp
    l = manifest["lora"]
    return {l["file"]: {"size_bytes": l["size_bytes"], "sha256": l["sha256"]}}


def verify_download(dest, manifest, what, check_sha=False):
    rep = {"dest": dest, "what": what, "files": {}, "ok": True, "total_bytes": 0}
    for rel, info in expected_files(manifest, what).items():
        p = os.path.join(dest, *rel.split("/")); e = {"path": p}
        if not os.path.exists(p):
            e["status"] = "ausente"; rep["ok"] = False
        else:
            e["size_bytes"] = os.path.getsize(p); rep["total_bytes"] += e["size_bytes"]
            if info.get("size_bytes") is not None and e["size_bytes"] != info["size_bytes"]:
                e["status"] = "tamanho_divergente"; rep["ok"] = False
            elif check_sha and info.get("sha256"):
                e["sha256"] = sha256_file(p); e["status"] = "ok" if e["sha256"] == info["sha256"] else "sha256_divergente"; rep["ok"] &= e["status"] == "ok"
            else:
                e["status"] = "ok" if info.get("size_bytes") is not None else "presente"
        rep["files"][rel] = e
    return rep


def fetch(what, dest, manifest):
    from huggingface_hub import snapshot_download
    repo, rev = repo_and_revision(manifest, what)
    path = snapshot_download(repo_id=repo, revision=rev, local_dir=dest, allow_patterns=allow_patterns_for(what), max_workers=4)
    return path


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--what", choices=["base", "lora"], required=True); ap.add_argument("--dest", required=True)
    ap.add_argument("--manifest", default=os.path.join(HERE, "r1ei_manifest.json"))
    ap.add_argument("--verify-only", action="store_true"); ap.add_argument("--verify-sha", action="store_true"); ap.add_argument("--json-out")
    a = ap.parse_args()
    manifest = json.load(open(a.manifest, encoding="utf-8"))
    if not a.verify_only:
        repo, rev = repo_and_revision(manifest, a.what)
        print(f"[hf_fetch] snapshot_download {repo} @ {rev} → {a.dest} allow_patterns={allow_patterns_for(a.what)}")
        try:
            fetch(a.what, a.dest, manifest)
        except Exception as e:
            print(f"[hf_fetch] ERRO no download: {e}", file=sys.stderr); sys.exit(2)
    rep = verify_download(a.dest, manifest, a.what, check_sha=a.verify_sha)
    js = json.dumps(rep, indent=1, ensure_ascii=False); print(js)
    if a.json_out:
        open(a.json_out, "w", encoding="utf-8").write(js)
    print(f"[hf_fetch] {'OK' if rep['ok'] else 'FALHA'} {a.what}: {rep['total_bytes']/2**30:.3f} GiB verificados" + (" (sha256)" if a.verify_sha else " (tamanhos)"))
    sys.exit(0 if rep["ok"] else 1)


if __name__ == "__main__":
    main()
