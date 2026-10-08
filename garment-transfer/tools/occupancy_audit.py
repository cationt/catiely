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
  garment_over_front_occluders       fração de FRONT_OCCLUDERS_CORE coberta por G → violação de z-order (eixo D; válida em O_engine e O_composed).
  coverage_of_band_min_near_occluders fração de BAND_MIN na coroa (k px) ao redor dos oclusores coberta por G → tecido existe junto ao oclusor (detecta recorte local).
  front_occluder_pixel_identity      fração de FRONT_OCCLUDERS_CORE idêntica a A (|dif|≤tol). ELIMINATÓRIA só em O_composed (ou em O_engine de rota com paste-back
                                     nativo, flag --engine-is-paste-back); em O_engine de rotas que regeneram o quadro é apenas DIAGNÓSTICA (o round-trip do VAE
                                     altera quase todos os pixels — lente 4, achado 3).
  occluder_mask_iou                  (O_engine) IoU entre a máscara do oclusor re-segmentada em O_engine (--occluder-mask-engine, ex. SAM 3 por pontos DWPose) e FO → estrutural.
  hand_keypoint_shift                (O_engine) deslocamento mediano normalizado dos keypoints de mão/antebraço (--keypoints-a/--keypoints-engine JSON) → mão intacta/movida.
  duplicate_limb                     (O_engine) contagem de mãos/antebraços detectados > A (--keypoints-*: campo "counts") → membro duplicado (eliminatório).
  band_min_change_magnitude          ΔE médio (Lab aprox.) entre A e O em BAND_MIN → evita falso "nascimento" (pele levemente alterada segmentada como tecido).
  composition_seam                   (O_composed vs O_engine) |grad| médio da diferença na coroa de FO → o que a colagem introduziu.
  unchanged_in_band_without_garment  fração de (BAND_MAX_BODY ∪ FREE_SPACE) \ G \ franja idêntica a A → nada mudou onde não há tecido.
  uncovered_coverable_identity       fração de (BODY_COVERABLE \ G \ franja) idêntica a A → pele não coberta intacta.
  unexplained_change_in_uncertain    fração de UNCERTAIN que não é G nem idêntica a A → conteúdo inventado.
  protected_pixel_identity           C1 estrito.

  changed_fraction_in_G              fração de G que difere de A (> τ) → evita PASS com G afirmando tecido onde nada mudou (G_without_change).
  excess_forbidden_frac_of_forbidden excesso normalizado pela área PROIBIDA (complementa a normalização pela área do tecido).
  fraction_excluded_by_fringe        quanto da banda a franja C3 exclui da checagem "nada mudou" (controle de diluição).

Distribuição NULA (obrigatória antes de vereditos sobre O_engine): --a-ref = A após encode/decode do VAE da rota (denoise 0, mesma
resolução/reprojeção); os limiares de identidade e --tol devem ser derivados dessa nula (p99.5) e do pipeline em same_garment_noop,
nunca fixados a priori. Pré-checagem de consistência das máscaras congeladas → INCONCLUSIVO:annotation_inconsistent (não é culpa do motor).
Saturação da borda do envelope é FLAG de revisão da anotação (annotation_review_required), não causa de FAIL.
Congelamento verificável: --manifest + --case-id conferem sha256 das referências antes de auditar (divergência → FAIL:frozen_reference_mismatch);
--prereg-sha grava o hash do PREREG.md no JSON. G_source é registrado em cada veredito.

Veredito por alvo: PASS / FAIL (causas) / INCONCLUSIVO (referência ausente ou inconsistente). Limiares explícitos; defaults provisórios a calibrar.
"""
import argparse, json, sys, os
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


def _srgb_to_lab(img):
    x = img.astype(np.float32) / 255.0
    x = np.where(x <= 0.04045, x / 12.92, ((x + 0.055) / 1.055) ** 2.4)
    M = np.array([[0.4124, 0.3576, 0.1805], [0.2126, 0.7152, 0.0722], [0.0193, 0.1192, 0.9505]], dtype=np.float32)
    xyz = x @ M.T
    xyz /= np.array([0.95047, 1.0, 1.08883], dtype=np.float32)
    f = np.where(xyz > 0.008856, np.cbrt(xyz), 7.787 * xyz + 16.0 / 116.0)
    L = 116.0 * f[..., 1] - 16.0
    a = 500.0 * (f[..., 0] - f[..., 1])
    b = 200.0 * (f[..., 1] - f[..., 2])
    return np.stack([L, a, b], axis=-1)


def delta_e(A, O):
    la, lo = _srgb_to_lab(A), _srgb_to_lab(O)
    return np.sqrt(((la - lo) ** 2).sum(axis=-1))


def keypoint_metrics(kp_a, kp_e, scale):
    """kp_* = {"hands": [[x,y,score],...], "forearms": [...], "counts": {"hands": n, "forearms": n}}; scale = diagonal da caixa da pessoa em px."""
    out = {}
    for part in ("hands", "forearms"):
        pa, pe = kp_a.get(part, []), kp_e.get(part, [])
        n = min(len(pa), len(pe))
        if n:
            d = [float(np.hypot(pa[i][0] - pe[i][0], pa[i][1] - pe[i][1])) / max(scale, 1.0) for i in range(n) if pa[i][2] > 0.3 and pe[i][2] > 0.3]
            if d:
                out[f"{part}_keypoint_shift_median"] = float(np.median(d))
    ca, ce = kp_a.get("counts", {}), kp_e.get("counts", {})
    out["duplicate_limb"] = bool(any(ce.get(k, 0) > ca.get(k, 0) for k in ("hands", "forearms")))
    return out


def grad_mag(img):
    g = img.astype(np.float32).mean(axis=2)
    gx = np.zeros_like(g); gy = np.zeros_like(g)
    gx[:, 1:] = np.abs(np.diff(g, axis=1)); gy[1:, :] = np.abs(np.diff(g, axis=0))
    return gx + gy


def check_mask_consistency(M):
    """Pré-checagem das referências congeladas: inconsistência → INCONCLUSIVO:annotation_inconsistent (não é culpa do motor)."""
    issues = []
    FO, BMIN, BMAXB, FS, UNC, BC, PR = (M.get(k) for k in ("FO", "BMIN", "BMAXB", "FS", "UNC", "BC", "PR"))
    if FO is not None:
        for name, m in (("BAND_MIN", BMIN), ("BAND_MAX_BODY", BMAXB), ("FREE_SPACE", FS), ("UNCERTAIN", UNC)):
            if m is not None and (m & FO).any():
                issues.append(f"{name} ∩ FRONT_OCCLUDERS ≠ ∅ (oclusor frontal não pode ser região ocupável)")
    if BMIN is not None and UNC is not None and (BMIN & UNC).any():
        issues.append("BAND_MIN ∩ UNCERTAIN ≠ ∅")
    if BMIN is not None and (BC is not None or FS is not None):
        allowed = np.zeros_like(BMIN)
        for m in (BC, FS, BMAXB):
            if m is not None:
                allowed |= m
        if (BMIN & ~allowed).mean() > 0.02:
            issues.append("BAND_MIN não contido em BODY_COVERABLE ∪ FREE_SPACE ∪ BAND_MAX_BODY (> 2 %)")
    if PR is not None:
        for name, m in (("BAND_MIN", BMIN), ("BAND_MAX_BODY", BMAXB), ("FREE_SPACE", FS), ("UNCERTAIN", UNC)):
            if m is not None and (PR & m).any():
                issues.append(f"PROTECTED ∩ {name} ≠ ∅")
    return issues


def audit_target(A, O, G, M, args):
    A_ref = M.get("A_REF", A)  # referência nula (ex.: VAE round-trip de A) para O_engine; A original para O_composed
    same = (np.abs(A_ref - O).max(axis=2) <= args.tol)
    res = {"n_garment_pixels": int(G.sum()), "causes": [], "inconclusive": [], "flags": [], "reference_quality": {}}
    res["G_source"] = M.get("G_SOURCE", "unspecified")
    res["identity_reference"] = "vae_roundtrip_A" if "A_REF" in M else "A"
    mc = check_mask_consistency(M)
    if mc:
        res["reference_quality"]["annotation_inconsistent"] = mc
        res["inconclusive"].append("annotation_inconsistent")
    n_g = max(int(G.sum()), 1)
    FO, BMIN, BMAXB, FS, UNC, BC, PR = (M.get(k) for k in ("FO", "BMIN", "BMAXB", "FS", "UNC", "BC", "PR"))
    fringe = dilate(G, args.contact_fringe_px) & ~G if args.contact_fringe_px > 0 else np.zeros_like(G)

    # eixo A — a peça nasceu / ocupação
    if BMIN is not None and BMIN.sum() > 0:
        res["coverage_of_band_min"] = float((G & BMIN).sum() / BMIN.sum())
        if res["coverage_of_band_min"] < args.min_coverage_band_min:
            res["causes"].append("garment_not_created:coverage_below_min")
        res["band_min_change_magnitude"] = float(delta_e(A_ref, O)[BMIN].mean())
        if res["band_min_change_magnitude"] < args.min_band_min_delta_e:
            res["causes"].append("garment_not_created:no_change_in_band_min")
    if G.sum() > 0:
        res["changed_fraction_in_G"] = float((~same)[G].mean())
        if res["changed_fraction_in_G"] < args.min_changed_fraction_in_g and not M.get("noop_mode"):
            res["causes"].append("garment_not_created:G_without_change")
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
            res["flags"].append("annotation_review_required:envelope_too_tight_probable")  # propriedade da anotação, não do motor
            res["inconclusive"].append("envelope_too_tight_probable")
        forb = ~allowed
        res["excess_forbidden_frac_of_forbidden"] = float((G & forb).sum() / max(int(forb.sum()), 1))
    else:
        res["inconclusive"].append("band_max_missing")

    # eixo D — oclusão / z-order
    if FO is not None and FO.sum() > 0:
        res["front_occluder_pixel_identity"] = float(same[FO].mean())
        res["garment_over_front_occluders"] = float((G & FO).sum() / FO.sum())
        if M.get("pixel_identity_is_eliminatory") and res["front_occluder_pixel_identity"] < args.min_occluder_identity:
            res["causes"].append("bad_occlusion:front_occluder_altered")
        elif not M.get("pixel_identity_is_eliminatory"):
            res["front_occluder_pixel_identity_note"] = "diagnóstico em O_engine de rota que regenera o quadro (VAE round-trip); eliminatória só em O_composed"
        if M.get("OCC_ENGINE") is not None:
            inter = (M["OCC_ENGINE"] & FO).sum(); union = (M["OCC_ENGINE"] | FO).sum()
            res["occluder_mask_iou"] = float(inter / max(union, 1))
            if res["occluder_mask_iou"] < args.min_occluder_mask_iou:
                res["causes"].append("bad_occlusion:occluder_mask_iou_low")
        if res["garment_over_front_occluders"] > args.max_garment_over_occluders:
            res["causes"].append("bad_occlusion:garment_over_occluder")
        crown = dilate(FO, args.crown_px) & ~FO
        if BMIN is not None and (crown & BMIN).sum() > 0:
            res["coverage_of_band_min_near_occluders"] = float((G & crown & BMIN).sum() / (crown & BMIN).sum())
            if res["coverage_of_band_min_near_occluders"] < args.min_coverage_near_occluders:
                res["causes"].append("occluder_cutout:no_fabric_near_occluder")
    else:
        res["inconclusive"].append("front_occluders_missing")

    # eixo E — nada mudou onde não há tecido
    if (BMAXB is not None or FS is not None):
        tot = np.zeros_like(G)
        for m in (BMAXB, FS):
            if m is not None:
                tot |= m
        res["fraction_excluded_by_fringe"] = float((fringe & tot).sum() / max(int(tot.sum()), 1))
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

    # por elemento (layer_graph)
    if M.get("LAYERS"):
        per = {}
        for el in M["LAYERS"]:
            em = el.get("mask_arr")
            if em is None or em.sum() == 0:
                continue
            r = {"relation": el["relation"], "garment_over_element": float((G & em).sum() / em.sum())}
            if el["relation"] == "front_certain" and r["garment_over_element"] > args.max_garment_over_occluders:
                r["verdict"] = "FAIL:visibility_violation"; res["causes"].append(f"visibility_violation:{el['element']}")
            elif el["relation"] == "behind_must_cover":
                r["coverage"] = float((G & em).sum() / em.sum())
                r["verdict"] = "PASS" if r["coverage"] >= args.min_coverage_band_min else "FAIL:not_covered"
                if r["verdict"] != "PASS": res["causes"].append(f"garment_not_created:element_not_covered:{el['element']}")
            elif el["relation"] in ("split_by_garment_edge", "behind_may_cover", "uncertain"):
                r["verdict"] = "REPORT_ONLY"
            else:
                r["verdict"] = "PASS"
            per[el["element"]] = r
        res["per_element"] = per

    if M.get("KP_A") and M.get("KP_E"):
        res.update(keypoint_metrics(M["KP_A"], M["KP_E"], M.get("scale_px", 1.0)))
        if res.get("duplicate_limb"):
            res["causes"].append("duplicate_limb")
        for part in ("hands", "forearms"):
            v = res.get(f"{part}_keypoint_shift_median")
            if v is not None and v > args.max_keypoint_shift:
                res["causes"].append(f"body_reconstruction_probable:{part}_moved")

    if res["n_garment_pixels"] == 0:
        res["causes"].append("garment_not_created:empty_mask")
    if "annotation_inconsistent" in res["inconclusive"]:
        res["verdict"] = "INCONCLUSIVO"  # precedência: referência inconsistente invalida PASS e FAIL (métricas ficam só como diagnóstico)
    else:
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
    ap.add_argument("--occluder-mask-engine", help="máscara dos oclusores re-segmentada em O_engine (SAM 3 por pontos DWPose) → occluder_mask_iou")
    ap.add_argument("--keypoints-a", help="JSON de keypoints de mãos/antebraços em A (DWPose) com counts")
    ap.add_argument("--keypoints-engine", help="JSON de keypoints em O_engine")
    ap.add_argument("--person-scale-px", type=float, default=None, help="diagonal da caixa da pessoa em A (normaliza deslocamentos)")
    ap.add_argument("--layer-graph", help="JSON: [{element, relation, mask: path}] por elemento (relações: front_certain, behind_must_cover, behind_may_cover, split_by_garment_edge, uncertain)")
    ap.add_argument("--engine-is-paste-back", action="store_true", help="rota F2 com paste-back nativo: identidade de pixel em FO é eliminatória também em O_engine")
    ap.add_argument("--a-ref", help="referência NULA para O_engine: A após encode/decode do VAE da rota (denoise 0, mesma resolução/reprojeção). Isola a edição do piso do VAE. O_composed usa sempre A.")
    ap.add_argument("--g-source", default="unspecified", help="origem de G: sam3_text | sam3_points | human | other (nunca a máscara do motor)")
    ap.add_argument("--noop-mode", action="store_true", help="caso same_garment_noop: desliga 'G_without_change'")
    ap.add_argument("--manifest", help="manifest.jsonl para verificar sha256 das referências congeladas (com --case-id)")
    ap.add_argument("--case-id")
    ap.add_argument("--prereg-sha", help="sha256 do PREREG.md commitado antes do run (gravado no JSON)")
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
    ap.add_argument("--min-coverage-near-occluders", type=float, default=0.90)
    ap.add_argument("--min-occluder-mask-iou", type=float, default=0.90)
    ap.add_argument("--max-keypoint-shift", type=float, default=0.02, help="fração da diagonal da pessoa; calibrar no controle negativo")
    ap.add_argument("--min-band-min-delta-e", type=float, default=8.0, help="ΔE mínimo médio em BAND_MIN (calibrar: > p95 do controle noop)")
    ap.add_argument("--min-changed-fraction-in-g", type=float, default=0.90, help="fração de G que deve diferir de A (> τ_null) em modo add")
    ap.add_argument("--json-out")
    args = ap.parse_args()

    A = load_rgb(args.a)
    shape = A.shape[:2]
    frozen_check = None
    if args.manifest and args.case_id:
        import hashlib
        rows = [json.loads(l) for l in open(args.manifest, encoding="utf-8") if l.strip()]
        row = next((r for r in rows if r["case_id"] == args.case_id), None)
        frozen_check = {"case_found": row is not None, "mismatches": [], "freeze_tag": None, "freeze_commit": None}
        if row:
            fa = row.get("expected", {}).get("frozen_annotation", {})
            frozen_check["freeze_tag"] = fa.get("freeze_tag"); frozen_check["freeze_commit"] = fa.get("freeze_commit")
            def walk(o):
                if isinstance(o, dict):
                    if "sha256" in o and o.get("local_path"):
                        yield o
                    for v in o.values(): yield from walk(v)
                elif isinstance(o, list):
                    for v in o: yield from walk(v)
            repo_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            for sres in walk(fa):
                fp = os.path.join(repo_root, sres["local_path"])
                if not os.path.exists(fp):
                    frozen_check["mismatches"].append(f"ausente:{sres['local_path']}")
                elif hashlib.sha256(open(fp, "rb").read()).hexdigest() != sres["sha256"]:
                    frozen_check["mismatches"].append(f"sha256:{sres['local_path']}")
    M = {"FO": load_bin(args.front_occluders, shape), "BMIN": load_bin(args.band_min, shape),
         "BMAXB": load_bin(args.band_max_body, shape), "FS": load_bin(args.free_space, shape),
         "UNC": load_bin(args.uncertain, shape), "BC": load_bin(args.body_coverable, shape), "PR": load_bin(args.protected, shape)}
    out = {"thresholds": {k: getattr(args, k) for k in vars(args) if k.startswith(("min_", "max_", "tol", "contact", "crown"))},
           "prereg_sha": args.prereg_sha, "frozen_reference_check": frozen_check}
    if frozen_check and (not frozen_check["case_found"] or frozen_check["mismatches"]):
        out["verdict_engine"] = out["verdict_composed"] = "FAIL:frozen_reference_mismatch"
        print(json.dumps(out, indent=1)); sys.exit(1)
    M["G_SOURCE"] = args.g_source; M["noop_mode"] = bool(args.noop_mode)
    if args.layer_graph:
        layers = json.load(open(args.layer_graph, encoding="utf-8"))
        for el in layers:
            el["mask_arr"] = load_bin(el.get("mask"), shape) if el.get("mask") else None
        M["LAYERS"] = layers
    if args.keypoints_a and args.keypoints_engine:
        M["KP_A"] = json.load(open(args.keypoints_a, encoding="utf-8")); M["KP_E"] = json.load(open(args.keypoints_engine, encoding="utf-8"))
        M["scale_px"] = args.person_scale_px or float(np.hypot(*shape))

    Oe = load_rgb(args.o_engine)
    if Oe.shape != A.shape:
        print(json.dumps({"verdict": "FAIL:canvas_mismatch", "target": "engine"})); sys.exit(1)
    Ge = load_bin(args.garment_mask, shape)
    Me = dict(M); Me["pixel_identity_is_eliminatory"] = bool(args.engine_is_paste_back); Me["OCC_ENGINE"] = load_bin(args.occluder_mask_engine, shape)
    if args.a_ref:
        Aref = load_rgb(args.a_ref)
        if Aref.shape != A.shape:
            print(json.dumps({"verdict": "FAIL:canvas_mismatch", "target": "a_ref"})); sys.exit(1)
        Me["A_REF"] = Aref
    out["engine"] = audit_target(A, Oe, Ge, Me, args)

    if args.o_composed:
        Oc = load_rgb(args.o_composed)
        if Oc.shape != A.shape:
            print(json.dumps({"verdict": "FAIL:canvas_mismatch", "target": "composed"})); sys.exit(1)
        Gc = load_bin(args.garment_mask_composed, shape) if args.garment_mask_composed else Ge
        Mc = dict(M); Mc["pixel_identity_is_eliminatory"] = True; Mc.pop("KP_A", None); Mc.pop("KP_E", None)
        out["composed"] = audit_target(A, Oc, Gc, Mc, args)
        FO = M.get("FO")
        if FO is not None and FO.sum() > 0:
            crown = dilate(FO, args.crown_px) & ~FO
            out["composed"]["composition_seam"] = float(np.abs(grad_mag(Oc) - grad_mag(Oe))[crown].mean())

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
