#!/usr/bin/env python3
"""Relatório de cobertura: contagem por nível/split e por valor de cada eixo; lista valores obrigatórios ausentes."""
import json, sys, collections, os
here = os.path.dirname(os.path.abspath(__file__))
path = sys.argv[1] if len(sys.argv) > 1 else os.path.join(here, "manifest.example.jsonl")
rows = [json.loads(l) for l in open(path, encoding="utf-8") if l.strip()]
REQUIRED = {
  "category": ["top","cropped_top","long_sleeve_top","jacket","skirt_mini","skirt_midi","skirt_maxi","shorts","pants","dress_tight","dress_loose","set_two_piece"],
  "construction": ["straps_thin","asymmetric","slit","open_front","buttons","zipper","pleats","none_special"],
  "material": ["solid","print_large","print_small","logo_text","satin_shiny","sheer_non_explicit","knit","denim"],
  "occlusion": ["none","hands_on_garment","arms_crossing","hair_over_garment","object_in_front","self_occlusion_legs"],
  "reference_modality": ["worn_other_person","catalog_ghost","flat_lay"],
  "reference_pose_delta": ["similar","moderate","very_different"],
  "operation": ["replace","add_over_skin","add_over_background","add_over_layer","replace_and_expose_skin"],
  "perspective": ["eye_level","low_angle","high_angle","foreshortened_limb"],
}
MIN = 3
by = collections.Counter((r["split"], r["level"]) for r in rows)
print("casos por (split, nível):")
for k in sorted(by): print(f"  {k}: {by[k]}")
final = [r for r in rows if r["split"] == "final_test"]
print(f"\ncobertura em final_test ({len(final)} casos), mínimo {MIN} por valor obrigatório:")
for axis, vals in REQUIRED.items():
    cnt = collections.Counter()
    for r in final:
        v = r["coverage"].get(axis)
        if isinstance(v, list):
            for x in v: cnt[x] += 1
        elif v is not None:
            cnt[v] += 1
    missing = [v for v in vals if cnt[v] < MIN]
    print(f"  {axis}: {dict(cnt)}  FALTAM(<{MIN}): {missing}")
