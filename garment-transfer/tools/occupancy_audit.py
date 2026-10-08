#!/usr/bin/env python3
r"""
occupancy_audit.py — Auditoria NÃO CIRCULAR de ocupação / visibilidade / z-order para o Prototype 0 (ADDITION / OCCUPANCY STRESS TEST).

Princípio: as REFERÊNCIAS são congeladas ANTES da geração (anotação humana, GT real ou caso sintético) e nunca derivadas da saída.
A única informação pós-geração é a máscara G do tecido novo, produzida por um segmentador INDEPENDENTE do gerador (SAM 3 por
texto/exemplar, ou anotação humana da saída) — e a sua confiabilidade deve ser calibrada (IoU vs anotação manual) no dev set.

Alvos: a auditoria roda em DOIS alvos, separadamente — a saída BRUTA do motor reprojetada (O_engine: mede o que o motor fez)
e a saída COMPOSTA final (O_composed: mede a entrega). Métricas de oclusor em O_composed são trivialmente perfeitas quando a casca
cola C1 de volta; por isso o veredito sobre o MOTOR usa O_engine.

Máscaras congeladas (PNG binário, grade de A; todas opcionais exceto G e band_min/band_max para o veredito de criação):
  --protected        PROTECTED: C1 estrito (rosto, fundo distante, objetos) — identidade exata em O_composed; tolerância em O_engine.
  --front-occluders  FRONT_OCCLUDERS_CORE: núcleo de partes de A que DEVEM ficar à frente da roupa (mãos, antebraço cruzado, cabelo frontal, objetos).
  --band-min         BAND_MIN: onde certamente deve haver tecido novo.
  --band-max-body    BAND_MAX_BODY: pele/roupa antiga de A que a peça PODE cobrir (condicional a atributos de B).
  --free-space       FREE_SPACE: fundo/objetos atrás que o volume da peça PODE ocupar.
  --uncertain        UNCERTAIN_OCCUPANCY: zona em que a existência de tecido é decidida pelo motor (axila, inter-membro, folga).
  --body-coverable   BODY_COVERABLE: superfície observada de A que a peça poderia cobrir (capacidade, não predição) → regra "coverable não coberto fica igual a A".
  --contact-fringe-px  largura (px) da franja C3 ao redor do tecido medido onde mudança limitada de luminância é permitida.

Entrada avaliada:
  --a  A original;  --o-engine  saída bruta do motor reprojetada à grade de A;  --o-composed  saída composta final (opcional);
  --garment-mask  G: tecido NOVO em O (segmentador independente ou anotação humana).  --garment-mask-composed opcional (se difere).

Métricas (por alvo):
  coverage_of_band_min              fração de BAND_MIN coberta por G → "a peça nasceu" (eixo A).
  excess_on_body / excess_on_background / excess_forbidden  tecido fora de BAND_MIN decomposto por componente (fração do tecido e px²).
  fabric_boundary_on_band_max_fraction  fração do perímetro de G coincidente com a borda do envelope → envelope apertado / tecido cortado.
  front_occluder_pixel_identity      fração de FRONT_OCCLUDERS_CORE idêntica a A (|dif|≤tol) → z-order (eixo D).
  garment_over_front_occluders       fração de FRONT_OCCLUDERS_CORE coberta por G → violação de z-order.
  occluder_border_coherence_proxy    descontinuidade média de gradiente na coroa de w px ao redor dos oclusores (O vs A) → junção falsa.
  unchanged_in_band_without_garment  fração de (BAND_MAX_BODY ∪ FREE_SPACE) \ G \ franja idêntica a A → nada mudou onde não há tecido.
  uncovered_coverable_identity       fração de (BODY_COVERABLE \ G \ franja) idêntica a A → pele não coberta intacta.
  unexplained_change_in_uncertain    fração de UNCERTAIN que não é G nem idêntica a A → conteúdo inventado.
  protected_pixel_identity           C1 estrito.

Veredito por alvo: PASS / FAIL (causas) / INCONCLUSIVO (referência congelada ausente). Limiares explícitos; defaults provisórios a calibrar.
"""
import argparse, json, sys
import numpy as np
from PIL import Image


def load_rgb(path):
    return np.asarray(Image.open(path).convert("RGB"), dtype=np.int16)


def load_bin(path, shape):
    if path is None:
        return None
    m = np.asarray(Image.open(path).convert("L"))
    if m.shape != shape:
        raise SystemExit(f"FAIL:grid_mismatch {path} {m.shape} vs {shape}")
    return m >= 128


def _shift_or(mask, out):
    out |= mask
    out[1:, :] |= mask[:-1, :]; out[:-1, :] |= mask[1:, :]
    out[:, 1:] |= mask[:, :-1]; out[:, :-1] |= mask[:, 1:]
    return out


def dilate(mask, r):
    """dilatação binária 4-conexa iterada (sem dependência de scipy)."""
    if mask is None or r <= 0:
        return mask
    cur = mask.copy()
    for _ in range(int(r)):
        cur = _shift_or(cur, cur.copy())
    return cur


def erode(mask, r=1):
    inv = ~mask
    return ~dilate(inv, r)


def boundary(mask):
    return mask & ~erode(mask, 1)


def grad_mag(img):
    g = img.astype(np.float32).mean(axis=2)
    gx = np.zeros_like(g); gy = np.zeros_like(g)
    gx[:, 1:] = np.abs(np.diff(g, axis=1)); gy[1:, :] = np.abs(np.diff(g, axis=0))
    return gx + gy


def audit_target(A, O, G, M, args):
    same = (np.abs(A - O).max(axis=2) <= args.tol)
    res = {"n_garment_pixels": int(G.sum()), "causes": [], "inconclusive": []}
    n_g = max(int(G.sum()), 1)
    FO, BMIN, BMAXB, FS, UNC, BC, PR = (M.get(k) for k in ("FO", "BMIN", "BMAXB", "FS", "UNC", "BC", "PR"))
    fringe = dilate(G, args.contact_fringe_px) & ~G if args.contact_fringe_px > 0 else np.zeros_like(G)

    # eixo A — a peça nasceu / ocupação
    if BMIN is not None and BMIN.sum() > 0:
        res["coverage_of_band_min"] = float((G & BMIN).sum() / BMIN.sum())
        if res["coverage_of_band_min"] < args.min_coverage_band_min:
            res["causes"].append("garment_not_created:coverage_below_min")
    else:
        res["inconclusive"].append("band_min_missing")
    allowed_parts = [m for m in (BMIN, BMAXB, FS, UNC) if m is not None]
    if allowed_parts:
        allowed = np.zeros_like(G)
        for m in allowed_parts:
            allowed |= m
        res["excess_forbidden_frac"] = float((G & ~allowed).sum() / n_g)
        res["excess_forbidden_px"] = int((G & ~allowed).sum())
        if res["excess_forbidden_frac"] > args.max_garment_in_forbidden:
            res["causes"].append("occupancy_forbidden_region")
        if BMIN is not None:
            outside_min = G & ~BMIN
            if BMAXB is not None:
                res["excess_on_body_frac"] = float((outside_min & BMAXB).sum() / n_g)
            if FS is not None:
                res["excess_on_background_frac"] = float((outside_min & FS).sum() / n_g)
            if UNC is not None:
                res["fabric_in_uncertain_frac"] = float((outside_min & UNC).sum() / n_g)
        env_boundary = boundary(allowed)
        if FO is not None:
            env_boundary &= ~dilate(FO, 2)  # parar na borda de um oclusor frontal é esperado, não "envelope apertado"
        gb = boundary(G)
        if FO is not None:
            gb &= ~dilate(FO, 2)
        res["fabric_boundary_on_band_max_fraction"] = float((gb & env_boundary).sum() / max(int(gb.sum()), 1))
        if res["fabric_boundary_on_band_max_fraction"] > args.max_boundary_saturation:
            res["causes"].append("envelope_too_tight_probable")
    else:
        res["inconclusive"].append("band_max_missing")

    # eixo D — oclusão / z-order
    if FO is not None and FO.sum() > 0:
        res["front_occluder_pixel_identity"] = float(same[FO].mean())
        res["garment_over_front_occluders"] = float((G & FO).sum() / FO.sum())
        if res["front_occluder_pixel_identity"] < args.min_occluder_identity:
            res["causes"].append("bad_occlusion:front_occluder_altered")
        if res["garment_over_front_occluders"] > args.max_garment_over_occluders:
            res["causes"].append("bad_occlusion:garment_over_occluder")
        crown = dilate(FO, args.crown_px) & ~FO
        if crown.sum() > 0:
            gA, gO = grad_mag(A), grad_mag(O)
            res["occluder_border_coherence_proxy"] = float(np.abs(gO[crown] - gA[crown]).mean())
    else:
        res["inconclusive"].append("front_occluders_missing")

    # eixo E — nada mudou onde não há tecido
    band_wo = None
    for m in (BMAXB, FS):
        if m is not None:
            band_wo = m if band_wo is None else (band_wo | m)
    if band_wo is not None:
        sel = band_wo & ~G & ~fringe
        if FO is not None:
            sel &= ~FO
        if sel.sum() > 0:
            res["unchanged_in_band_without_garment"] = float(same[sel].mean())
            if res["unchanged_in_band_without_garment"] < args.min_unchanged_without_garment:
                res["causes"].append("background_drift_or_unauthorized_change:in_band_without_garment")
    if BC is not None:
        sel = BC & ~G & ~fringe
        if FO is not None:
            sel &= ~FO
        if sel.sum() > 0:
            res["uncovered_coverable_identity"] = float(same[sel].mean())
            if res["uncovered_coverable_identity"] < args.min_unchanged_without_garment:
                res["causes"].append("body_reconstruction_probable:uncovered_skin_changed")
    if UNC is not None and UNC.sum() > 0:
        inv = UNC & ~G & ~same & ~fringe
        res["unexplained_change_in_uncertain"] = float(inv.sum() / UNC.sum())
        if res["unexplained_change_in_uncertain"] > args.max_unexplained_uncertain:
            res["causes"].append("unexplained_synthesis_in_uncertain")
    if PR is not None and PR.sum() > 0:
        res["protected_pixel_identity"] = float(same[PR].mean())
        res["protected_max_err"] = int(np.abs(A - O)[PR].max())
        if res["protected_pixel_identity"] < args.min_protected_identity:
            res["causes"].append("unauthorized_change:protected")

    if res["n_garment_pixels"] == 0:
        res["causes"].append("garment_not_created:empty_mask")
    res["verdict"] = "FAIL" if res["causes"] else ("INCONCLUSIVO" if res["inconclusive"] else "PASS")
    return res


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--a", required=True)
    ap.add_argument("--o-engine", required=True, help="saída bruta do motor, reprojetada à grade de A")
    ap.add_argument("--o-composed", help="saída composta final (opcional)")
    ap.add_argument("--garment-mask", required=True, help="G em O_engine (segmentador independente / anotação)")
    ap.add_argument("--garment-mask-composed", help="G em O_composed, se diferir")
    ap.add_argument("--protected"); ap.add_argument("--front-occluders")
    ap.add_argument("--band-min"); ap.add_argument("--band-max-body"); ap.add_argument("--free-space")
    ap.add_argument("--uncertain"); ap.add_argument("--body-coverable")
    ap.add_argument("--contact-fringe-px", type=int, default=8)
    ap.add_argument("--crown-px", type=int, default=6)
    ap.add_argument("--tol", type=int, default=2)
    ap.add_argument("--min-occluder-identity", type=float, default=0.95, help="em O_engine; em O_composed aplica-se 1.0 via --min-protected-identity")
    ap.add_argument("--max-garment-over-occluders", type=float, default=0.02)
    ap.add_argument("--min-coverage-band-min", type=float, default=0.90)
    ap.add_argument("--max-garment-in-forbidden", type=float, default=0.02)
    ap.add_argument("--max-boundary-saturation", type=float, default=0.10)
    ap.add_argument("--min-unchanged-without-garment", type=float, default=0.98)
    ap.add_argument("--max-unexplained-uncertain", type=float, default=0.10)
    ap.add_argument("--min-protected-identity", type=float, default=1.0)
    ap.add_argument("--json-out")
    args = ap.parse_args()

    A = load_rgb(args.a)
    shape = A.shape[:2]
    M = {"FO": load_bin(args.front_occluders, shape), "BMIN": load_bin(args.band_min, shape),
         "BMAXB": load_bin(args.band_max_body, shape), "FS": load_bin(args.free_space, shape),
         "UNC": load_bin(args.uncertain, shape), "BC": load_bin(args.body_coverable, shape), "PR": load_bin(args.protected, shape)}
    out = {"thresholds": {k: getattr(args, k) for k in vars(args) if k.startswith(("min_", "max_", "tol", "contact", "crown"))}}

    Oe = load_rgb(args.o_engine)
    if Oe.shape != A.shape:
        print(json.dumps({"verdict": "FAIL:canvas_mismatch", "target": "engine"})); sys.exit(1)
    Ge = load_bin(args.garment_mask, shape)
    out["engine"] = audit_target(A, Oe, Ge, M, args)

    if args.o_composed:
        Oc = load_rgb(args.o_composed)
        if Oc.shape != A.shape:
            print(json.dumps({"verdict": "FAIL:canvas_mismatch", "target": "composed"})); sys.exit(1)
        Gc = load_bin(args.garment_mask_composed, shape) if args.garment_mask_composed else Ge
        out["composed"] = audit_target(A, Oc, Gc, M, args)

    out["verdict_engine"] = out["engine"]["verdict"]
    out["verdict_composed"] = out.get("composed", {}).get("verdict")
    js = json.dumps(out, indent=1)
    print(js)
    if args.json_out:
        open(args.json_out, "w", encoding="utf-8").write(js)
    worst = [v for v in (out["verdict_engine"], out["verdict_composed"]) if v]
    sys.exit(1 if "FAIL" in worst else (3 if "INCONCLUSIVO" in worst else 0))


if __name__ == "__main__":
    main()
