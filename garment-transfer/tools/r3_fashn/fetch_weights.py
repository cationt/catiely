#!/usr/bin/env python3
"""fetch_weights.py — download determinístico (revisão + arquivo pinados) e verificação (tamanho + sha256) dos pesos da rota R3 (FASHN VTON 1.5).

Lições da R1-EI aplicadas: nada de `hf download --include`; cada arquivo é baixado com `huggingface_hub.hf_hub_download(repo_id, filename,
revision=<commit>)` para um diretório local e conferido contra o manifesto. Nenhum download implícito fica para o benchmark: o parser
humano (SegFormer) também é baixado aqui para um diretório local, e o runner carrega-o desse diretório em modo offline.

Componentes (chaves de `components` em r3_manifest.json): tryon (model.safetensors), dwpose (yolox_l.onnx, dw-ll_ucoco_384.onnx),
human_parser (config.json, preprocessor_config.json, model.safetensors).

Uso:
  python fetch_weights.py --weights-dir <dir> [--only tryon|dwpose|human_parser] [--verify-sha]
  python fetch_weights.py --weights-dir <dir> --verify-only --verify-sha [--json-out x.json]
Layout produzido (o mesmo que o pipeline upstream espera + parser local):
  <weights-dir>/model.safetensors
  <weights-dir>/dwpose/yolox_l.onnx, dw-ll_ucoco_384.onnx
  <weights-dir>/fashn-human-parser/config.json, preprocessor_config.json, model.safetensors
Exit 0 ok · 1 verificação falhou · 2 uso/erro de download.
"""
import argparse, hashlib, json, os, sys

HERE = os.path.dirname(os.path.abspath(__file__))


def sha256_file(p):
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 22), b""):
            h.update(chunk)
    return h.hexdigest()


def components(manifest, only=None):
    comps = manifest["components"]
    return {k: v for k, v in comps.items() if only is None or k == only}


def local_path(weights_dir, comp, rel):
    sub = comp.get("local_subdir", "")
    return os.path.join(weights_dir, *([sub] if sub else []), *rel.split("/"))


def verify(weights_dir, manifest, only=None, check_sha=False):
    rep = {"weights_dir": weights_dir, "ok": True, "total_bytes": 0, "components": {}}
    for name, comp in components(manifest, only).items():
        c = {"repo": comp["repo"], "revision": comp["revision"], "files": {}, "ok": True}
        for rel, info in comp["files"].items():
            p = local_path(weights_dir, comp, rel); e = {"path": p}
            if not os.path.exists(p):
                e["status"] = "ausente"; c["ok"] = False
            else:
                e["size_bytes"] = os.path.getsize(p); rep["total_bytes"] += e["size_bytes"]
                if e["size_bytes"] != info["size_bytes"]:
                    e["status"] = "tamanho_divergente"; c["ok"] = False
                elif check_sha and info.get("sha256"):
                    e["sha256"] = sha256_file(p); e["status"] = "ok" if e["sha256"] == info["sha256"] else "sha256_divergente"; c["ok"] &= e["status"] == "ok"
                else:
                    e["status"] = "ok"
            c["files"][rel] = e
        rep["components"][name] = c; rep["ok"] &= c["ok"]
    return rep


def fetch(weights_dir, manifest, only=None):
    from huggingface_hub import hf_hub_download
    got = []
    for name, comp in components(manifest, only).items():
        sub = comp.get("local_subdir", "")
        dest = os.path.join(weights_dir, sub) if sub else weights_dir
        os.makedirs(dest, exist_ok=True)
        for rel in comp["files"]:
            print(f"[fetch_weights] {comp['repo']}@{comp['revision'][:12]} {rel} → {dest}", flush=True)
            got.append(hf_hub_download(repo_id=comp["repo"], filename=rel, revision=comp["revision"], local_dir=dest))
    return got


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--weights-dir", required=True); ap.add_argument("--manifest", default=os.path.join(HERE, "r3_manifest.json"))
    ap.add_argument("--only", choices=["tryon", "dwpose", "human_parser"]); ap.add_argument("--verify-only", action="store_true")
    ap.add_argument("--verify-sha", action="store_true"); ap.add_argument("--json-out")
    a = ap.parse_args()
    manifest = json.load(open(a.manifest, encoding="utf-8"))
    if not a.verify_only:
        try:
            fetch(a.weights_dir, manifest, a.only)
        except Exception as e:
            print(f"[fetch_weights] ERRO no download: {e}", file=sys.stderr); sys.exit(2)
    rep = verify(a.weights_dir, manifest, a.only, check_sha=a.verify_sha)
    js = json.dumps(rep, indent=1, ensure_ascii=False); print(js)
    if a.json_out:
        open(a.json_out, "w", encoding="utf-8").write(js)
    print(f"[fetch_weights] {'OK' if rep['ok'] else 'FALHA'}: {rep['total_bytes']/2**30:.3f} GiB verificados" + (" (sha256)" if a.verify_sha else " (tamanhos)"))
    sys.exit(0 if rep["ok"] else 1)


if __name__ == "__main__":
    main()
