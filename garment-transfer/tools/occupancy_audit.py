#!/usr/bin/env python3
"""
occupancy_audit.py — Auditoria NÃO CIRCULAR de ocupação/visibilidade/z-order para o Prototype 0 (ADDITION / OCCUPANCY STRESS TEST).

Referências aceitas (todas CONGELADAS ANTES da geração e nunca derivadas da saída avaliada):
  --front-occluders  PNG binário (grade de A): partes de A que DEVEM permanecer à frente da roupa nova (mãos, antebraço cruzado, cabelo, objetos).
  --body-coverable   PNG binário: superfície de A que a roupa PODE cobrir.
  --band-min         PNG binário: região onde certamente deve haver tecido (anotação humana ou GT).
  --band-max         PNG binário: região onde pode haver tecido (anotação humana ou GT). Fora dela, tecido = excesso.
  --protected        PNG binário (opcional): C1 estrito (rosto, fundo distante...) — igualdade exata de pixels.

Entrada avaliada:
  --a  imagem A original;  --o  saída O (mesma grade);
  --garment-mask  PNG binário: máscara do tecido NOVO em O, produzida por um segmentador INDEPENDENTE do gerador
                  (ex.: SAM 3 com texto/exemplar, ou anotação humana da saída). O script NÃO a deriva da própria rota.

Métricas:
  front_occluder_pixel_identity : fração de pixels de FRONT_OCCLUDERS idênticos a A (|dif|≤tol) → oclusão/z-order (D).
  garment_over_front_occluders  : fração de FRONT_OCCLUDERS coberta por tecido novo → violação de z-order (D).
  coverage_of_band_min          : fração de band_min coberta pelo tecido novo → "a peça nasceu" (A).
  excess_beyond_band_max        : área de tecido fora de band_max / área de tecido total → ocupação indevida (A/E).
  garment_outside_coverable_and_freespace : tecido fora de (body_coverable ∪ band_max) → invadiu região proibida.
  protected_pixel_identity      : igualdade em C1 estrito (E), se fornecido.

Veredito: PASS se todos os limiares passam; FAIL com causas; INCONCLUSIVO se faltar referência congelada para um critério.
Limiares são parâmetros explícitos (calibrar no dev set; defaults provisórios).
"""
import argparse, json, sys
import numpy as np
from PIL import Image


def load_bin(path, shape):
    if path is None:
        return None
    m = np.asarray(Image.open(path).convert("L"))
    if m.shape != shape:
        raise SystemExit(f"FAIL:grid_mismatch {path} {m.shape} vs {shape}")
    return m >= 128


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--a", required=True); ap.add_argument("--o", required=True)
    ap.add_argument("--garment-mask", required=True)
    ap.add_argument("--front-occluders"); ap.add_argument("--body-coverable")
    ap.add_argument("--band-min"); ap.add_argument("--band-max"); ap.add_argument("--protected")
    ap.add_argument("--tol", type=int, default=2, help="tolerância por canal para identidade de pixels em oclusores/protegidos")
    ap.add_argument("--min-occluder-identity", type=float, default=0.98)
    ap.add_argument("--max-garment-over-occluders", type=float, default=0.02)
    ap.add_argument("--min-coverage-band-min", type=float, default=0.90)
    ap.add_argument("--max-excess-beyond-band-max", type=float, default=0.10)
    ap.add_argument("--max-garment-in-forbidden", type=float, default=0.02)
    ap.add_argument("--json-out")
    args = ap.parse_args()

    A = np.asarray(Image.open(args.a).convert("RGB"), dtype=np.int16)
    O = np.asarray(Image.open(args.o).convert("RGB"), dtype=np.int16)
    if A.shape != O.shape:
        print(json.dumps({"verdict": "FAIL:canvas_mismatch"})); sys.exit(1)
    shape = A.shape[:2]
    G = load_bin(args.garment_mask, shape)
    FO = load_bin(args.front_occluders, shape)
    BC = load_bin(args.body_coverable, shape)
    BMIN = load_bin(args.band_min, shape)
    BMAX = load_bin(args.band_max, shape)
    PR = load_bin(args.protected, shape)

    same = (np.abs(A - O).max(axis=2) <= args.tol)
    res = {"n_garment_pixels": int(G.sum()), "causes": [], "inconclusive": []}
    n_g = max(int(G.sum()), 1)

    if FO is not None and FO.sum() > 0:
        res["front_occluder_pixel_identity"] = float(same[FO].mean())
        res["garment_over_front_occluders"] = float((G & FO).sum() / FO.sum())
        if res["front_occluder_pixel_identity"] < args.min_occluder_identity: res["causes"].append("bad_occlusion:front_occluder_altered")
        if res["garment_over_front_occluders"] > args.max_garment_over_occluders: res["causes"].append("bad_occlusion:garment_over_occluder")
    else:
        res["inconclusive"].append("front_occluders_missing")

    if BMIN is not None and BMIN.sum() > 0:
        res["coverage_of_band_min"] = float((G & BMIN).sum() / BMIN.sum())
        if res["coverage_of_band_min"] < args.min_coverage_band_min: res["causes"].append("garment_not_created:coverage_below_min")
    else:
        res["inconclusive"].append("band_min_missing")

    if BMAX is not None:
        res["excess_beyond_band_max"] = float((G & ~BMAX).sum() / n_g)
        if res["excess_beyond_band_max"] > args.max_excess_beyond_band_max: res["causes"].append("occupancy_excess:beyond_band_max")
    else:
        res["inconclusive"].append("band_max_missing")

    if BC is not None and BMAX is not None:
        allowed = BC | BMAX
        res["garment_in_forbidden"] = float((G & ~allowed).sum() / n_g)
        if res["garment_in_forbidden"] > args.max_garment_in_forbidden: res["causes"].append("occupancy_forbidden_region")

    if PR is not None and PR.sum() > 0:
        res["protected_pixel_identity"] = float(same[PR].mean())
        res["protected_max_err"] = int(np.abs(A - O)[PR].max())
        if res["protected_pixel_identity"] < 1.0: res["causes"].append("unauthorized_change:protected")

    if res["n_garment_pixels"] == 0:
        res["causes"].append("garment_not_created:empty_mask")

    if res["causes"]:
        res["verdict"] = "FAIL"
    elif res["inconclusive"]:
        res["verdict"] = "INCONCLUSIVO"
    else:
        res["verdict"] = "PASS"
    res["thresholds"] = {k: getattr(args, k) for k in ("tol", "min_occluder_identity", "max_garment_over_occluders", "min_coverage_band_min", "max_excess_beyond_band_max", "max_garment_in_forbidden")}
    js = json.dumps(res, indent=1); print(js)
    if args.json_out: open(args.json_out, "w", encoding="utf-8").write(js)
    sys.exit(0 if res["verdict"] == "PASS" else (3 if res["verdict"] == "INCONCLUSIVO" else 1))


if __name__ == "__main__":
    main()
