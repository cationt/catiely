#!/usr/bin/env python3
"""freeze_check.py — verificação de proveniência/congelamento compartilhada por occupancy_audit.py, garment_fidelity_audit.py e g0_gate.py.

Princípio: nenhum veredito sobre um motor é emitido antes de provar que (a) o manifesto, o PREREG e o arquivo de papéis (roles) são
EXATAMENTE os congelados (sha256 registrados em FREEZE.json), (b) todos os arquivos referenciados pelo caso (A, B, GT, máscaras) têm o
sha256 declarado no manifesto, e (c) as entradas efetivamente passadas ao auditor (A, B, máscaras) são esses mesmos arquivos.
Divergência → FAIL:frozen_reference_mismatch (antes de avaliar o motor). Placeholders (sha com dígitos iguais) → manifesto NÃO congelado.
"""
import hashlib, json, os, subprocess


def sha256_file(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def is_placeholder_sha(h):
    return (not h) or len(set(h)) == 1


def repo_root_from(file_in_tools):
    return os.path.dirname(os.path.dirname(os.path.abspath(file_in_tools)))


def git_head(root):
    try:
        return subprocess.run(["git", "-C", root, "rev-parse", "HEAD"], capture_output=True, text=True, timeout=10).stdout.strip() or None
    except Exception:
        return None


def git_dirty(root):
    try:
        return bool(subprocess.run(["git", "-C", root, "status", "--porcelain"], capture_output=True, text=True, timeout=10).stdout.strip())
    except Exception:
        return None


def walk_sources(obj, prefix=""):
    """Itera (campo, image_source) sobre qualquer dict com sha256 (+ local_path/url)."""
    if isinstance(obj, dict):
        if "sha256" in obj and ("local_path" in obj or "url" in obj or "source_type" in obj):
            yield prefix, obj
        for k, v in obj.items():
            yield from walk_sources(v, f"{prefix}/{k}" if prefix else k)
    elif isinstance(obj, list):
        for i, v in enumerate(obj):
            yield from walk_sources(v, f"{prefix}[{i}]")


def load_manifest(path):
    return [json.loads(l) for l in open(path, encoding="utf-8") if l.strip()]


def find_row(rows, case_id):
    return next((r for r in rows if r.get("case_id") == case_id), None)


def resolve_path(local_path, data_root):
    return local_path if os.path.isabs(local_path) else os.path.join(data_root, local_path)


def verify_row_files(row, data_root):
    """Confere sha256 de TODOS os image_sources do caso (A, B, GT, máscaras, z_order, split, b_garment_mask).
    Retorna (checked:list, mismatches:list). Placeholder conta como mismatch ('placeholder')."""
    checked, mismatches = [], []
    for field, src in walk_sources(row):
        lp = src.get("local_path")
        declared = src.get("sha256", "")
        entry = {"field": field, "local_path": lp, "sha256_declared": declared}
        if is_placeholder_sha(declared):
            entry["status"] = "placeholder"; mismatches.append(f"placeholder:{field}")
        elif not lp:
            entry["status"] = "no_local_path"  # url-only: não verificável localmente
        else:
            fp = resolve_path(lp, data_root)
            if not os.path.exists(fp):
                entry["status"] = "missing"; mismatches.append(f"ausente:{field}:{lp}")
            else:
                real = sha256_file(fp); entry["sha256_actual"] = real
                if real != declared:
                    entry["status"] = "sha256_mismatch"; mismatches.append(f"sha256:{field}:{lp}")
                else:
                    entry["status"] = "ok"
        checked.append(entry)
    return checked, mismatches


def verify_input_matches(path_given, src, label):
    """A entrada efetivamente passada (ex.: --a, --band-min) deve ser o arquivo congelado do manifesto (mesmo sha256)."""
    if path_given is None or src is None:
        return None
    declared = src.get("sha256", "")
    if is_placeholder_sha(declared):
        return f"placeholder:{label}"
    if not os.path.exists(path_given):
        return f"ausente:{label}:{path_given}"
    if sha256_file(path_given) != declared:
        return f"input_sha256:{label}:{path_given}"
    return None


def verify_freeze(freeze_path, manifest_path=None, prereg_path=None, roles_path=None):
    """Compara os sha256 atuais de manifesto/PREREG/roles com os registrados em FREEZE.json.
    Retorna (info:dict, mismatches:list)."""
    info = {"freeze_path": freeze_path, "freeze_sha256": None, "freeze_tag": None, "freeze_commit": None, "frozen": None}
    mism = []
    if not freeze_path or not os.path.exists(freeze_path):
        return info, [f"ausente:freeze:{freeze_path}"]
    info["freeze_sha256"] = sha256_file(freeze_path)
    fz = json.load(open(freeze_path, encoding="utf-8"))
    info["freeze_tag"] = fz.get("freeze_tag"); info["freeze_commit"] = fz.get("git_commit"); info["frozen"] = fz.get("frozen")
    if fz.get("frozen") is not True:
        mism.append("not_frozen:FREEZE.json marca frozen=false (placeholders ou divergências no congelamento)")
    files = fz.get("files", {})
    for key, path in (("manifest", manifest_path), ("prereg", prereg_path), ("roles", roles_path)):
        rec = files.get(key)
        if path is None:
            continue
        if rec is None:
            mism.append(f"freeze_sem_registro:{key}"); continue
        if not os.path.exists(path):
            mism.append(f"ausente:{key}:{path}"); continue
        actual = sha256_file(path)
        info[f"{key}_sha256"] = actual
        if actual != rec.get("sha256"):
            mism.append(f"sha256:{key}:{path} (congelado {str(rec.get('sha256'))[:12]}…, atual {actual[:12]}…)")
    return info, mism
