#!/usr/bin/env python3
"""
pixel_preservation_check.py — Auditoria de preservação determinística (classe C1) entre A e O.

Compara A e O na MESMA grade (dimensões idênticas) e no mesmo espaço de cor (sRGB 8 bits, PNG sem perda),
restrito à máscara de C1 fornecida (branco = protegido). Não alinha, não registra, não reamostra:
qualquer deslocamento aparece como erro.

Saída: nº de pixels alterados (|dif|>0), nº acima de tolerância, erro máximo por canal, MAE/RMSE em C1,
mapa de diferença (PNG) e veredito segundo o contrato (exact / near_exact com tolerância).

Uso:
    python tools/pixel_preservation_check.py --a A.png --o O.png --mask C1.png --mode exact --diff-out diff.png
    python tools/pixel_preservation_check.py --a A.png --o O.png --mask C1.png --mode near_exact --tol 2 --max-frac 0.001

Dependências: numpy, Pillow.
"""
import argparse
import json
import sys

import numpy as np
from PIL import Image


def load_rgb(path):
    im = Image.open(path)
    if im.mode not in ("RGB", "RGBA"):
        im = im.convert("RGB")
    if im.mode == "RGBA":
        im = im.convert("RGB")
    return np.asarray(im, dtype=np.int16)


def load_mask(path, shape):
    m = Image.open(path).convert("L")
    arr = np.asarray(m)
    if arr.shape != shape[:2]:
        raise SystemExit(f"FAIL:grid_mismatch mask {arr.shape} vs image {shape[:2]} (não reamostrar: corrigir a pipeline)")
    return arr >= 128


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--a", required=True)
    ap.add_argument("--o", required=True)
    ap.add_argument("--mask", required=True, help="PNG; branco = C1 (protegido)")
    ap.add_argument("--mode", choices=["exact", "near_exact"], default="exact")
    ap.add_argument("--tol", type=int, default=0, help="tolerância por canal (0-255) em near_exact")
    ap.add_argument("--max-frac", type=float, default=0.0, help="fração máxima de pixels C1 acima da tolerância em near_exact")
    ap.add_argument("--diff-out", default=None)
    ap.add_argument("--json-out", default=None)
    args = ap.parse_args()

    A = load_rgb(args.a)
    O = load_rgb(args.o)
    if A.shape != O.shape:
        print(json.dumps({"verdict": "FAIL:canvas_mismatch", "a_shape": A.shape, "o_shape": O.shape}))
        sys.exit(1)
    m = load_mask(args.mask, A.shape)
    n_c1 = int(m.sum())
    if n_c1 == 0:
        print(json.dumps({"verdict": "INCONCLUSIVO:empty_c1"}))
        sys.exit(3)

    d = np.abs(A - O)  # HxWx3
    dmax = d.max(axis=2)  # pior canal por pixel
    changed = (dmax > 0) & m
    over = (dmax > args.tol) & m
    res = {
        "n_c1_pixels": n_c1,
        "n_changed": int(changed.sum()),
        "frac_changed": float(changed.sum() / n_c1),
        "n_over_tol": int(over.sum()),
        "frac_over_tol": float(over.sum() / n_c1),
        "max_err_channel": int(d[m].max()) if n_c1 else 0,
        "mae_c1": float(d[m].mean()),
        "rmse_c1": float(np.sqrt((d[m].astype(np.float64) ** 2).mean())),
        "mode": args.mode, "tol": args.tol, "max_frac": args.max_frac,
    }
    if args.mode == "exact":
        res["verdict"] = "PASS" if res["n_changed"] == 0 else "FAIL:unauthorized_change"
    else:
        res["verdict"] = "PASS" if res["frac_over_tol"] <= args.max_frac else "FAIL:unauthorized_change"

    if args.diff_out:
        vis = np.zeros(A.shape[:2] + (3,), dtype=np.uint8)
        vis[..., 1] = np.where(m, 40, 0)  # verde escuro = C1
        amp = np.clip(dmax * 8, 0, 255).astype(np.uint8)
        vis[..., 0] = np.where(m, amp, 0)  # vermelho = erro em C1 (amplificado 8x)
        vis[..., 2] = np.where(~m, 60, 0)  # azul escuro = fora de C1 (não auditado aqui)
        Image.fromarray(vis).save(args.diff_out)
        res["diff_out"] = args.diff_out
    js = json.dumps(res, indent=1)
    print(js)
    if args.json_out:
        with open(args.json_out, "w", encoding="utf-8") as f:
            f.write(js)
    sys.exit(0 if res["verdict"] == "PASS" else 1)


if __name__ == "__main__":
    main()
