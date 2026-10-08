#!/usr/bin/env python3
"""make_masks.py — máscaras binárias (L, 0/255) na grade de uma imagem, para a MEDIÇÃO DE VIABILIDADE da R1-EI.

Para a viabilidade (tempo/VRAM/RAM/commit) bastam máscaras grosseiras: o custo do pipeline não depende da forma da máscara (o recorte é
sempre reamostrado para 1024²). A QUALIDADE (G0) exige as máscaras anotadas e congeladas do benchmark — não estas.

Uso:
  python make_masks.py --image A.png --bbox 0.28,0.22,0.72,0.68 --out A_insert_mask.png      # bbox normalizada xyxy (0–1)
  python make_masks.py --image B.png --bbox-px 120,80,620,700 --out B_ref_mask.png            # bbox em pixels xyxy
  python make_masks.py --image A.png --from-mask qualquer_mascara.png --out A_insert_mask.png   # reamostra (NEAREST) + binariza
Sempre grava um PNG modo L estritamente 0/255 com o tamanho exato da imagem.
"""
import argparse, sys
from PIL import Image


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--image", required=True); ap.add_argument("--out", required=True)
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--bbox", help="x0,y0,x1,y1 normalizados (0–1)"); g.add_argument("--bbox-px", help="x0,y0,x1,y1 em pixels"); g.add_argument("--from-mask", help="PNG de máscara existente")
    args = ap.parse_args()
    W, H = Image.open(args.image).size
    if args.from_mask:
        m = Image.open(args.from_mask).convert("L")
        if m.size != (W, H):
            m = m.resize((W, H), Image.NEAREST)
        m = m.point(lambda p: 255 if p >= 128 else 0)
    else:
        if args.bbox:
            x0, y0, x1, y1 = (float(v) for v in args.bbox.split(","))
            if not all(0.0 <= v <= 1.0 for v in (x0, y0, x1, y1)):
                sys.exit("bbox normalizada fora de [0,1]")
            x0, x1 = int(round(x0 * W)), int(round(x1 * W)); y0, y1 = int(round(y0 * H)), int(round(y1 * H))
        else:
            x0, y0, x1, y1 = (int(v) for v in args.bbox_px.split(","))
        if not (0 <= x0 < x1 <= W and 0 <= y0 < y1 <= H):
            sys.exit(f"bbox inválida para imagem {W}x{H}: {(x0, y0, x1, y1)}")
        m = Image.new("L", (W, H), 0); m.paste(255, (x0, y0, x1, y1))
    m.save(args.out)
    bb = m.getbbox(); print(f"[make_masks] {args.out}: {W}x{H}, bbox={bb}, área={sum(m.histogram()[128:]) / (W * H):.1%}")


if __name__ == "__main__":
    main()
