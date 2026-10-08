#!/usr/bin/env python3
"""Valida um manifest.jsonl contra manifest.schema.json e aplica checagens que o schema não expressa.

Uso:
    python benchmark/validate_manifest.py manifest.jsonl [--check-files] [--allow-placeholders]

Checagens:
  - schema JSON (draft 2020-12), incl. if/then: modo add exige envelope congelado (min_mask) e z_order.
  - anti-vazamento por ids (person/garment/source) entre splits.
  - z-order: front_certain exige máscara; front_occluders_mask presente se houver front_certain.
  - sha256 placeholder (todos os dígitos iguais) → ERRO, salvo --allow-placeholders (esqueleto antes do congelamento; o relatório marca o manifesto como NÃO CONGELADO).
  - --check-files: todo local_path deve existir e ter sha256 igual ao declarado (congelamento verificável).
  - duplicatas: mesmo sha256 (ou mesmo phash declarado) com ids diferentes → ERRO.
  - semântica: operation contendo 'background' exige free_space_mask; z_order com 'uncertain'/'split' exige uncertain_occupancy_mask; frozen_annotation.annotated_on não pode ser posterior a provenance.added_on quando ambos existem (congelado antes).
"""
import json, sys, collections, os, hashlib, argparse
try:
    import jsonschema
except ImportError:
    print("pip install jsonschema", file=sys.stderr); sys.exit(2)

here = os.path.dirname(os.path.abspath(__file__))
root = os.path.dirname(here)
ap = argparse.ArgumentParser()
ap.add_argument("path", nargs="?", default=os.path.join(here, "manifest.example.jsonl"))
ap.add_argument("--check-files", action="store_true")
ap.add_argument("--allow-placeholders", action="store_true")
args = ap.parse_args()

schema = json.load(open(os.path.join(here, "manifest.schema.json"), encoding="utf-8"))
rows = [json.loads(l) for l in open(args.path, encoding="utf-8") if l.strip()]
v = jsonschema.Draft202012Validator(schema)
errors = 0; warnings = 0; placeholders = 0

def iter_sources(obj):
    if isinstance(obj, dict):
        if "sha256" in obj and "source_type" in obj:
            yield obj
        for val in obj.values():
            yield from iter_sources(val)
    elif isinstance(obj, list):
        for it in obj:
            yield from iter_sources(it)

for i, r in enumerate(rows):
    for e in v.iter_errors(r):
        errors += 1; print(f"[{i}] {r.get('case_id')}: {e.message} @ {'/'.join(map(str, e.path))}")
    # placeholders / arquivos
    for sres in iter_sources(r):
        h = sres.get("sha256", "")
        if h and len(set(h)) == 1:
            placeholders += 1
            if not args.allow_placeholders:
                errors += 1; print(f"{r['case_id']}: sha256 placeholder em {sres.get('local_path') or sres.get('url')} (use --allow-placeholders só para esqueleto NÃO congelado)")
        if args.check_files and sres.get("local_path"):
            fp = os.path.join(root, sres["local_path"])
            if not os.path.exists(fp):
                errors += 1; print(f"{r['case_id']}: arquivo ausente {sres['local_path']}")
            else:
                real = hashlib.sha256(open(fp, "rb").read()).hexdigest()
                if real != h:
                    errors += 1; print(f"{r['case_id']}: sha256 divergente para {sres['local_path']} (declarado {h[:12]}…, real {real[:12]}…)")
    fa = r.get("expected", {}).get("frozen_annotation", {})
    zo = fa.get("z_order", [])
    if any(z.get("relation") == "front_certain" for z in zo) and not fa.get("front_occluders_mask"):
        errors += 1; print(f"{r['case_id']}: há elementos front_certain mas front_occluders_mask é null (deve ser a união das máscaras front_certain)")
    for z in zo:
        if z.get("relation") == "front_certain" and not z.get("mask"):
            errors += 1; print(f"{r['case_id']}: elemento {z.get('element')} front_certain sem máscara")
    if any(z.get("relation") in ("uncertain", "split_by_garment_edge") and z.get("element") != "hair_front" for z in zo) and not fa.get("uncertain_occupancy_mask"):
        warnings += 1; print(f"AVISO {r['case_id']}: z_order tem uncertain/split mas uncertain_occupancy_mask é null")
    op = r.get("coverage", {}).get("operation", "")
    if "background" in op and not fa.get("free_space_mask"):
        warnings += 1; print(f"AVISO {r['case_id']}: operation={op} mas free_space_mask é null (tecido sobre fundo cairá em região proibida)")
    band = fa.get("plausible_occupancy_band", {})
    if band.get("max_mask") and band.get("max_body_mask") and band["max_mask"].get("local_path") == band["max_body_mask"].get("local_path"):
        warnings += 1; print(f"AVISO {r['case_id']}: max_mask (legado) aponta para o mesmo arquivo que max_body_mask; remova o legado")
    ao, ad = fa.get("annotated_on"), r.get("provenance", {}).get("added_on")
    if ao and ad and ao > ad:
        errors += 1; print(f"{r['case_id']}: annotated_on ({ao}) posterior a added_on ({ad}) — anotação deve preceder")
    if r.get("spec", {}).get("mode") in ("add", "add_over_layer") and r.get("spec", {}).get("garment_of_category_present_in_A") is True:
        warnings += 1; print(f"AVISO {r['case_id']}: mode=add mas garment_of_category_present_in_A=true")

# anti-vazamento por ids
for key in ("person_group_id", "garment_group_id", "source_group_id"):
    seen = collections.defaultdict(set)
    for r in rows:
        g = r.get("provenance", {}).get(key)
        if g: seen[g].add(r["split"])
    for g, splits in seen.items():
        if len(splits) > 1:
            errors += 1; print(f"VAZAMENTO {key}={g} aparece em splits {sorted(splits)}")
# duplicatas por hash real / phash com ids diferentes
by_hash = collections.defaultdict(set)
for r in rows:
    h = r.get("A", {}).get("sha256", ""); ph = r.get("provenance", {}).get("phash")
    pid = r.get("provenance", {}).get("person_group_id")
    if h and len(set(h)) > 1: by_hash[("sha", h)].add(pid)
    if ph: by_hash[("phash", ph)].add(pid)
for k, pids in by_hash.items():
    if len(pids) > 1:
        errors += 1; print(f"DUPLICATA {k[0]}={k[1][:12]}… com person_group_id diferentes {sorted(map(str, pids))}")
ids = [r["case_id"] for r in rows]
if len(ids) != len(set(ids)):
    errors += 1; print("case_id duplicado")
frozen = "CONGELADO" if (placeholders == 0 and args.check_files) else ("NÃO CONGELADO (placeholders ou arquivos não verificados)")
print(f"{len(rows)} casos, {errors} erro(s), {warnings} aviso(s) — estado: {frozen}")
sys.exit(1 if errors else 0)
