#!/usr/bin/env python3
"""Valida um manifest.jsonl contra manifest.schema.json e checa anti-vazamento entre splits."""
import json, sys, collections, os
try:
    import jsonschema
except ImportError:
    print("pip install jsonschema", file=sys.stderr); sys.exit(2)

here = os.path.dirname(os.path.abspath(__file__))
schema = json.load(open(os.path.join(here, "manifest.schema.json"), encoding="utf-8"))
path = sys.argv[1] if len(sys.argv) > 1 else os.path.join(here, "manifest.example.jsonl")
rows = [json.loads(l) for l in open(path, encoding="utf-8") if l.strip()]
v = jsonschema.Draft202012Validator(schema)
errors = 0
for i, r in enumerate(rows):
    for e in v.iter_errors(r):
        errors += 1
        print(f"[{i}] {r.get('case_id')}: {e.message} @ {'/'.join(map(str, e.path))}")
# anti-vazamento
for key in ("person_group_id", "garment_group_id", "source_group_id"):
    seen = collections.defaultdict(set)
    for r in rows:
        g = r.get("provenance", {}).get(key)
        if g:
            seen[g].add(r["split"])
    for g, splits in seen.items():
        if len(splits) > 1:
            errors += 1
            print(f"VAZAMENTO {key}={g} aparece em splits {sorted(splits)}")
ids = [r["case_id"] for r in rows]
if len(ids) != len(set(ids)):
    errors += 1; print("case_id duplicado")
print(f"{len(rows)} casos, {errors} erro(s)")
sys.exit(1 if errors else 0)
