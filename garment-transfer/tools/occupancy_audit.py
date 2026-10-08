#!/usr/bin/env python3
r"""
occupancy_audit.py (v5) — Auditoria NÃO CIRCULAR de ocupação / visibilidade / z-order para o Prototype 0 (ADDITION / OCCUPANCY STRESS TEST).

Princípio: as REFERÊNCIAS são congeladas ANTES da geração (anotação humana, GT real ou caso sintético) e nunca derivadas da saída.
A única informação pós-geração é a máscara G do tecido novo, produzida por um segmentador INDEPENDENTE do gerador (SAM 3 por
texto/exemplar, ou anotação humana da saída) — e a sua confiabilidade deve ser calibrada (IoU vs anotação manual) no dev set.

ESCOPO (explícito): este auditor implementa, da definição operacional de "ocupado por tecido da peça" (`00` §4.4), as evidências
(i) G independente e (ii) mudança real acima do piso nulo. A evidência (iii) — IDENTIDADE DA PEÇA B (categoria/atributos congelados,
cromaticidade, embedding) — NÃO é avaliada aqui: é obrigatória no G0 e vive em `tools/garment_fidelity_audit.py`. Um PASS deste
auditor NÃO é um PASS do caso; `tools/g0_gate.py` exige ambos.

Alvos: a auditoria roda em DOIS alvos, separadamente — a saída BRUTA do motor reprojetada (O_engine: mede o que o motor fez)
e a saída COMPOSTA final (O_composed: mede a entrega). Métricas de oclusor em O_composed são trivialmente perfeitas quando a casca
cola C1 de volta; por isso o veredito sobre o MOTOR usa O_engine.

Tolerâncias separadas:
  tol_engine   — derivada da distribuição NULA da rota: p99,5 de |A_ref − A| (A_ref = A após encode/decode do VAE, --a-ref) ou
                 lida de --null-stats (JSON {"tol_p995": n}). No perfil g0, --tol-engine explícito SEM fonte nula é evidência ausente.
  tol_composed — 0 quando o contrato de O_composed é `exact` (padrão): qualquer pixel de PROTECTED alterado (protected_max_err > 0) reprova.

Evidência obrigatória depende do manifesto (perfil g0, padrão):
  --manifest/--case-id obrigatórios; as máscaras não passadas são resolvidas a partir do manifesto; as passadas são conferidas por sha256.
  Se o caso tem elemento `front_certain` (z_order) → são obrigatórios: --front-occluders, --layer-graph (com todos os elementos
  front_certain e máscara), --occluder-mask-engine e --keypoints-a/--keypoints-engine. Ausência → INCONCLUSIVO:missing_required_evidence.
  Se o manifesto declara coverage.occlusion == ["none"] e não há front_certain → eixo D = NOT_APPLICABLE (não é INCONCLUSIVO).
  Sem manifesto (perfil minimal): o estado de oclusão vem de --layer-graph, da máscara FO não vazia ou de --occlusion-none; sem nenhum
  deles → INCONCLUSIVO:missing_required_evidence:occlusion_status_unknown. Em NENHUM perfil há PASS com front_certain e evidência ausente.
  Elementos `split_by_garment_edge` exigem máscaras congeladas split_must_cover / split_must_stay_visible OU adjudicação humana cega
  (--human-adjudication) do elemento; sem isso → missing_required_evidence.

Franja C3 (--contact-fringe-px): NÃO é isenta. Em fringe = dilate(G) \ G (fora de FO/PROTECTED) exige-se |ΔL*| ≤ --max-fringe-delta-l,
Δchroma(a*,b*) ≤ --max-fringe-delta-chroma em ≥ (1 − --max-fringe-violation-frac) dos pixels e preservação estrutural (correlação dos
gradientes ≥ --min-fringe-structure-corr; em franja plana, sem textura inventada). Violação → FAIL contact_fringe_violation:*.

Congelamento verificável (antes de avaliar o motor): --freeze FREEZE.json (gerado por tools/freeze_proto0.py) confere sha256 do
manifesto, do PREREG (--prereg: o sha é calculado aqui, não recebido como string) e do roles; todos os image_sources do caso (A, B, GT,
máscaras) são conferidos; --a (e --b) devem ser os arquivos congelados. Divergência → FAIL:frozen_reference_mismatch. O JSON grava
sha256 do manifesto, do PREREG, do FREEZE, freeze_tag, freeze_commit e o commit atual do repositório.

Veredito por alvo: FAIL (causas) > INCONCLUSIVO (referência inconsistente / evidência obrigatória ausente) > PASS.
Exit: 0 PASS · 1 FAIL · 3 INCONCLUSIVO · 2 erro de uso.
"""
import argparse, json, sys, os, math
import numpy as np
from PIL import Image

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import freeze_check as fz  # noqa: E402

VERSION = "5"
G0_ELIMINATORY = {  # métricas que decidem o gate (PREREG §5) — evidência correspondente é obrigatória quando aplicável
    "front_certain": ["front_occluders_mask", "layer_graph", "occluder_mask_engine", "keypoints"],
    "always": ["garment_mask", "band_min", "envelope", "body_coverable", "protected", "null_distribution"],
    "split_by_garment_edge": ["split_masks_or_blind_adjudication"],
}


# ----------------------------------------------------------------------------------------------------------------------- utilitários
def load_rgb(path):
    return np.asarray(Image.open(path).convert("RGB"), dtype=np.int16)


def image_format_issue(path):
    """O_engine/O_composed devem ser RGB 8 bits sem alfa: convert('RGB') esconderia alterações em 16 bits ou no canal alfa."""
    im = Image.open(path)
    if im.mode != "RGB":
        return f"mode={im.mode}"
    depth = getattr(im, "bits", None) or (im.info.get("bits") if hasattr(im, "info") else None)
    if depth not in (None, 8):
        return f"bits={depth}"
    return None


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
    """dilatação binária 4-conexa iterada (sem scipy)."""
    if mask is None or r <= 0:
        return mask
    cur = mask.copy()
    for _ in range(int(r)):
        cur = _shift_or(cur, cur.copy())
    return cur


def erode(mask, r=1):
    return ~dilate(~mask, r)


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


def grad_mag(img):
    g = img.astype(np.float32).mean(axis=2)
    gx = np.zeros_like(g); gy = np.zeros_like(g)
    gx[:, 1:] = np.abs(np.diff(g, axis=1)); gy[1:, :] = np.abs(np.diff(g, axis=0))
    return gx + gy


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


def derive_tol_from_null(A, A_ref, q=99.5):
    d = np.abs(A_ref.astype(np.int32) - A.astype(np.int32)).max(axis=2)
    return int(max(1, int(np.ceil(np.percentile(d, q)))))


# ----------------------------------------------------------------------------------------------------------------- consistência
def check_mask_consistency(M):
    """Pré-checagem das referências congeladas: inconsistência → INCONCLUSIVO:annotation_inconsistent (não é culpa do motor).
    A tolerância de BAND_MIN fora de BODY_COVERABLE ∪ FREE_SPACE ∪ BAND_MAX_BODY é bad_pixels / |BAND_MIN| (nunca média sobre o canvas)."""
    issues, stats = [], {}
    FO, BMIN, BMAXB, FS, UNC, BC, PR = (M.get(k) for k in ("FO", "BMIN", "BMAXB", "FS", "UNC", "BC", "PR"))
    if FO is not None:
        for name, m in (("BAND_MIN", BMIN), ("BAND_MAX_BODY", BMAXB), ("FREE_SPACE", FS), ("UNCERTAIN", UNC)):
            if m is not None and (m & FO).any():
                issues.append(f"{name} ∩ FRONT_OCCLUDERS ≠ ∅ (oclusor frontal não pode ser região ocupável)")
    if BMIN is not None and UNC is not None and (BMIN & UNC).any():
        issues.append("BAND_MIN ∩ UNCERTAIN ≠ ∅")
    if BMIN is not None and BMIN.sum() > 0 and (BC is not None or FS is not None or BMAXB is not None):
        allowed = np.zeros_like(BMIN)
        for m in (BC, FS, BMAXB):
            if m is not None:
                allowed |= m
        bad = int((BMIN & ~allowed).sum())
        stats["band_min_outside_allowed_frac"] = bad / int(BMIN.sum())
        if stats["band_min_outside_allowed_frac"] > 0.02:
            issues.append(f"BAND_MIN não contido em BODY_COVERABLE ∪ FREE_SPACE ∪ BAND_MAX_BODY ({stats['band_min_outside_allowed_frac']:.1%} de BAND_MIN; limite 2 %)")
    if PR is not None:
        for name, m in (("BAND_MIN", BMIN), ("BAND_MAX_BODY", BMAXB), ("FREE_SPACE", FS), ("UNCERTAIN", UNC)):
            if m is not None and (PR & m).any():
                issues.append(f"PROTECTED ∩ {name} ≠ ∅")
    for el in M.get("LAYERS") or []:
        em, mc, mv = el.get("mask_arr"), el.get("must_cover_arr"), el.get("must_stay_visible_arr")
        if el.get("relation") == "split_by_garment_edge" and mc is not None and mv is not None:
            if (mc & mv).any():
                issues.append(f"split {el['element']}: must_cover ∩ must_stay_visible ≠ ∅")
            if em is not None and ((mc | mv) & ~em).any():
                issues.append(f"split {el['element']}: must_cover ∪ must_stay_visible não contido na máscara do elemento")
            if FO is not None and (mc & FO).any():
                issues.append(f"split {el['element']}: must_cover ∩ FRONT_OCCLUDERS ≠ ∅")
        if el.get("relation") == "front_certain" and em is not None and FO is not None and (em & ~FO).mean() > 0 and (em & ~FO).sum() / max(int(em.sum()), 1) > 0.02:
            issues.append(f"front_certain {el['element']} não contido em FRONT_OCCLUDERS ({(em & ~FO).sum() / max(int(em.sum()), 1):.1%})")
    return issues, stats


# ------------------------------------------------------------------------------------------------------------------ franja C3
def masked_grad_mag(img, valid):
    """|∇| por diferenças finitas contando só pares de pixels ambos em `valid` (exclui a borda tecido/não-tecido da franja)."""
    g = img.astype(np.float32).mean(axis=2)
    gx = np.zeros_like(g); gy = np.zeros_like(g)
    vx = valid[:, 1:] & valid[:, :-1]; vy = valid[1:, :] & valid[:-1, :]
    gx[:, 1:] = np.where(vx, np.abs(np.diff(g, axis=1)), 0.0); gy[1:, :] = np.where(vy, np.abs(np.diff(g, axis=0)), 0.0)
    return gx + gy


def fringe_metrics(A_ref, O, fringe, tol, args, G):
    out, causes = {"fringe_px": int(fringe.sum())}, []
    if out["fringe_px"] == 0:
        return out, causes
    la, lo = _srgb_to_lab(A_ref), _srgb_to_lab(O)
    dL = np.abs(lo[..., 0] - la[..., 0])[fringe]
    dC = np.hypot(lo[..., 1] - la[..., 1], lo[..., 2] - la[..., 2])[fringe]
    out["fringe_delta_l_p95"] = float(np.percentile(dL, 95)); out["fringe_delta_chroma_p95"] = float(np.percentile(dC, 95))
    viol = (dL > args.max_fringe_delta_l) | (dC > args.max_fringe_delta_chroma)
    out["fringe_violation_frac"] = float(viol.mean())
    if out["fringe_violation_frac"] > args.max_fringe_violation_frac:
        causes.append("contact_fringe_violation:luminance_or_chroma")
    # preservação estrutural: correlação dos gradientes só onde A tem estrutura acima do ruído da nula (ga > 3·tol);
    # em franja plana (sem estrutura), não pode nascer textura (gradiente médio de O não pode crescer > 3·tol).
    valid = ~G
    ga, go = masked_grad_mag(A_ref, valid)[fringe], masked_grad_mag(O, valid)[fringe]
    structured = ga > 3.0 * max(tol, 1)
    out["fringe_structured_px"] = int(structured.sum())
    if structured.sum() >= 30 and go[structured].std() > 1e-6 and ga[structured].std() > 1e-6:
        corr = float(np.corrcoef(ga[structured], go[structured])[0, 1])
        out["fringe_structure_corr"] = corr
        if corr < args.min_fringe_structure_corr:
            causes.append("contact_fringe_violation:structure")
    else:
        out["fringe_structure_corr"] = None
    out["fringe_texture_added"] = float(go.mean() - ga.mean())
    if out["fringe_texture_added"] > 3.0 * max(tol, 1):
        causes.append("contact_fringe_violation:structure_added")
    return out, causes


# -------------------------------------------------------------------------------------------------------------- split elements
def split_element_metrics(G, same, el, args, adjud):
    r = {"relation": "split_by_garment_edge"}
    mc, mv, em = el.get("must_cover_arr"), el.get("must_stay_visible_arr"), el.get("mask_arr")
    key = f"split_edge:{el['element']}"
    if mc is None or mv is None:
        ans = (adjud or {}).get("answers", {}).get(key)
        if ans is None:
            r["verdict"] = "INCONCLUSIVO:missing_required_evidence"; return r, [], [f"split_edge_reference:{el['element']}"]
        r["judged_by"] = "human_blind"; r["answer"] = ans
        if ans == "no":
            r["verdict"] = "FAIL:split_edge_violation"; return r, [f"split_edge_violation:human_blind:{el['element']}"], []
        if ans == "yes":
            r["verdict"] = "PASS"; return r, [], []
        r["verdict"] = "INCONCLUSIVO:ambiguous"; return r, [], [f"split_edge_ambiguous:{el['element']}"]
    r["judged_by"] = "frozen_masks"
    causes = []
    r["must_cover_coverage"] = float((G & mc).sum() / max(int(mc.sum()), 1))
    if r["must_cover_coverage"] < args.min_coverage_band_min:
        causes.append(f"split_edge_violation:must_cover_not_covered:{el['element']}")
    r["fabric_over_must_stay_visible"] = float((G & mv).sum() / max(int(mv.sum()), 1))
    if r["fabric_over_must_stay_visible"] > args.max_garment_over_occluders:
        causes.append(f"split_edge_violation:fabric_over_visible_part:{el['element']}")
    vis = mv & ~G
    if vis.sum() > 0:
        r["must_stay_visible_identity"] = float(same[vis].mean())
        if r["must_stay_visible_identity"] < args.min_unchanged_without_garment:
            causes.append(f"split_edge_violation:visible_part_altered:{el['element']}")
    if em is not None:
        bz = em & ~mc & ~mv
        r["boundary_zone_px"] = int(bz.sum())
        if bz.sum() > 0:
            r["boundary_zone_consistency"] = float((G | same)[bz].mean())  # cada pixel é tecido OU idêntico a A
            if r["boundary_zone_consistency"] < args.min_unchanged_without_garment:
                causes.append(f"split_edge_violation:boundary_zone_inconsistent:{el['element']}")
    r["verdict"] = "FAIL:split_edge_violation" if causes else "PASS"
    return r, causes, []


# ---------------------------------------------------------------------------------------------------------------- auditoria
def audit_target(A, O, G, M, args, tol, target):
    A_ref = M.get("A_REF", A) if target == "engine" else A
    same = (np.abs(A_ref - O).max(axis=2) <= tol)
    res = {"target": target, "tol": int(tol), "n_garment_pixels": int(G.sum()), "causes": [], "inconclusive": [], "missing_required_evidence": [],
           "flags": [], "reference_quality": {}, "evidence": dict(M.get("EVIDENCE", {}))}
    res["G_source"] = M.get("G_SOURCE", "unspecified")
    res["identity_reference"] = "vae_roundtrip_A" if (target == "engine" and "A_REF" in M) else "A"
    res["garment_identity"] = "NOT_EVALUATED_HERE — ver tools/garment_fidelity_audit.py (obrigatório no G0)"
    mc, mstats = check_mask_consistency(M)
    mc = list(M.get("ANNOTATION_ISSUES", [])) + mc
    res["reference_quality"].update(mstats)
    if mc:
        res["reference_quality"]["annotation_inconsistent"] = mc
        res["inconclusive"].append("annotation_inconsistent")
    n_g = max(int(G.sum()), 1)
    FO, BMIN, BMAXB, FS, UNC, BC, PR = (M.get(k) for k in ("FO", "BMIN", "BMAXB", "FS", "UNC", "BC", "PR"))
    has_fc = M.get("HAS_FRONT_CERTAIN")
    res["missing_required_evidence"].extend(M.get("MISSING", []))
    fringe = (dilate(G, args.contact_fringe_px) & ~G) if args.contact_fringe_px > 0 else np.zeros_like(G)
    if FO is not None:
        fringe &= ~FO
    if PR is not None:
        fringe &= ~PR

    # eixo A — a peça nasceu / ocupação
    if BMIN is not None and BMIN.sum() > 0:
        res["coverage_of_band_min"] = float((G & BMIN).sum() / BMIN.sum())
        if res["coverage_of_band_min"] < args.min_coverage_band_min:
            res["causes"].append("garment_not_created:coverage_below_min")
        res["band_min_change_magnitude"] = float(delta_e(A_ref, O)[BMIN].mean())
        if res["band_min_change_magnitude"] < args.min_band_min_delta_e:
            res["causes"].append("garment_not_created:no_change_in_band_min")
    else:
        res["missing_required_evidence"].append("band_min")
    if G.sum() > 0:
        res["changed_fraction_in_G"] = float((~same)[G].mean())
        if res["changed_fraction_in_G"] < args.min_changed_fraction_in_g and not M.get("noop_mode"):
            res["causes"].append("garment_not_created:G_without_change")
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
        gb = boundary(G)
        if FO is not None:
            env_boundary &= ~dilate(FO, 2); gb &= ~dilate(FO, 2)  # parar na borda de um oclusor é esperado
        res["fabric_boundary_on_band_max_fraction"] = float((gb & env_boundary).sum() / max(int(gb.sum()), 1))
        if res["fabric_boundary_on_band_max_fraction"] > args.max_boundary_saturation:
            res["flags"].append("annotation_review_required:envelope_too_tight_probable")
            res["inconclusive"].append("envelope_too_tight_probable")
        forb = ~allowed
        res["excess_forbidden_frac_of_forbidden"] = float((G & forb).sum() / max(int(forb.sum()), 1))
    if BMAXB is None and FS is None:
        res["missing_required_evidence"].append("envelope")

    # eixo D — oclusão / z-order
    if has_fc is True:
        if FO is None or FO.sum() == 0:
            res["missing_required_evidence"].append("front_occluders_mask")
        else:
            res["front_occluder_pixel_identity"] = float(same[FO].mean())
            res["garment_over_front_occluders"] = float((G & FO).sum() / FO.sum())
            elim = M.get("pixel_identity_is_eliminatory")
            thr = 1.0 if (target == "composed" and args.composed_contract == "exact") else args.min_occluder_identity
            if elim and res["front_occluder_pixel_identity"] < thr:
                res["causes"].append("bad_occlusion:front_occluder_altered")
            elif not elim:
                res["front_occluder_pixel_identity_note"] = "diagnóstico em O_engine de rota que regenera o quadro (VAE round-trip); eliminatória em O_composed"
            if M.get("OCC_ENGINE") is not None:
                inter = (M["OCC_ENGINE"] & FO).sum(); union = (M["OCC_ENGINE"] | FO).sum()
                res["occluder_mask_iou"] = float(inter / max(union, 1))
                if res["occluder_mask_iou"] < args.min_occluder_mask_iou:
                    res["causes"].append("bad_occlusion:occluder_mask_iou_low")
            elif target == "engine":
                res["missing_required_evidence"].append("occluder_mask_engine")
            if res["garment_over_front_occluders"] > args.max_garment_over_occluders:
                res["causes"].append("bad_occlusion:garment_over_occluder")
            crown = dilate(FO, args.crown_px) & ~FO
            if BMIN is not None and (crown & BMIN).sum() > 0:
                res["coverage_of_band_min_near_occluders"] = float((G & crown & BMIN).sum() / (crown & BMIN).sum())
                if res["coverage_of_band_min_near_occluders"] < args.min_coverage_near_occluders:
                    res["causes"].append("occluder_cutout:no_fabric_near_occluder")
        if target == "engine" and not (M.get("KP_A") and M.get("KP_E")):
            res["missing_required_evidence"].append("keypoints")
        if target == "engine" and M.get("OCC_ENGINE") is None:
            res["missing_required_evidence"].append("occluder_mask_engine")
        if not M.get("LAYERS"):
            res["missing_required_evidence"].append("layer_graph")
    elif has_fc is False:
        res["evidence"]["front_occluders"] = "NOT_APPLICABLE"
        if FO is not None and FO.sum() > 0:  # anotador passou FO mas nenhum elemento é front_certain → contradição
            res["inconclusive"].append("annotation_inconsistent"); res["reference_quality"].setdefault("annotation_inconsistent", []).append("FO não vazio sem elemento front_certain")
    else:
        res["missing_required_evidence"].append("occlusion_status_unknown")

    # eixo E — nada mudou onde não há tecido; franja C3 com limite
    tot = None
    for m in (BMAXB, FS):
        if m is not None:
            tot = m if tot is None else (tot | m)
    if tot is not None:
        res["fraction_excluded_by_fringe"] = float((fringe & tot).sum() / max(int(tot.sum()), 1))
        sel = tot & ~G & ~fringe
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
    elif M.get("PROFILE") == "g0":
        res["missing_required_evidence"].append("body_coverable")
    if UNC is not None and UNC.sum() > 0:
        inv = UNC & ~G & ~same & ~fringe
        res["unexplained_change_in_uncertain"] = float(inv.sum() / UNC.sum())
        if res["unexplained_change_in_uncertain"] > args.max_unexplained_uncertain:
            res["causes"].append("unexplained_synthesis_in_uncertain")
    fr, fcauses = fringe_metrics(A_ref, O, fringe, tol, args, G)
    res.update(fr); res["causes"].extend(fcauses)
    if PR is not None and PR.sum() > 0:
        res["protected_pixel_identity"] = float(same[PR].mean())
        res["protected_max_err"] = int(np.abs(A - O)[PR].max())
        if target == "composed" and args.composed_contract == "exact":
            if res["protected_max_err"] > 0:
                res["causes"].append("unauthorized_change:protected_exact")
        elif res["protected_pixel_identity"] < args.min_protected_identity:
            res["causes"].append("unauthorized_change:protected")
    elif target == "composed" or M.get("PROFILE") == "g0":
        res["missing_required_evidence"].append("protected")  # sem PROTECTED não há como julgar o contrato exact de O_composed

    # por elemento (layer_graph)
    if M.get("LAYERS"):
        per = {}
        for el in M["LAYERS"]:
            em = el.get("mask_arr")
            if el["relation"] == "split_by_garment_edge":
                r, c, miss = split_element_metrics(G, same, el, args, M.get("ADJUD"))
                res["causes"].extend(c)
                for m_ in miss:
                    (res["missing_required_evidence"] if m_.startswith("split_edge_reference") else res["inconclusive"]).append(m_)
                per[el["element"]] = r; continue
            if em is None or em.sum() == 0:
                per[el["element"]] = {"relation": el["relation"], "verdict": "INCONCLUSIVO:missing_required_evidence"}
                res["missing_required_evidence"].append(f"element_mask:{el['element']}"); continue
            r = {"relation": el["relation"], "garment_over_element": float((G & em).sum() / em.sum())}
            if el["relation"] == "front_certain":
                if r["garment_over_element"] > args.max_garment_over_occluders:
                    r["verdict"] = "FAIL:visibility_violation"; res["causes"].append(f"visibility_violation:{el['element']}")
                else:
                    r["verdict"] = "PASS"
            elif el["relation"] == "behind_must_cover":
                r["coverage"] = r["garment_over_element"]
                r["verdict"] = "PASS" if r["coverage"] >= args.min_coverage_band_min else "FAIL:not_covered"
                if r["verdict"] != "PASS":
                    res["causes"].append(f"garment_not_created:element_not_covered:{el['element']}")
            elif el["relation"] == "behind_may_cover":
                r["verdict"] = "REPORT_ONLY (depende de atributo de B — garment_fidelity_audit)"
            else:
                r["verdict"] = "REPORT_ONLY"
            per[el["element"]] = r
        res["per_element"] = per
        if has_fc is True and M.get("FRONT_CERTAIN_EXPECTED"):
            missing_el = [e for e in M["FRONT_CERTAIN_EXPECTED"] if e not in per or per[e].get("relation") != "front_certain"]
            if missing_el:
                res["missing_required_evidence"].append("layer_graph_elements:" + ",".join(missing_el))

    if target == "engine" and M.get("KP_A") and M.get("KP_E"):
        res.update(keypoint_metrics(M["KP_A"], M["KP_E"], M.get("scale_px", 1.0)))
        if res.get("duplicate_limb"):
            res["causes"].append("duplicate_limb")
        for part in ("hands", "forearms"):
            v = res.get(f"{part}_keypoint_shift_median")
            if v is not None and v > args.max_keypoint_shift:
                res["causes"].append(f"body_reconstruction_probable:{part}_moved")

    if res["n_garment_pixels"] == 0:
        res["causes"].append("garment_not_created:empty_mask")
    res["missing_required_evidence"] = sorted(set(res["missing_required_evidence"]))
    for item in res["missing_required_evidence"]:
        res["evidence"][item.split(":")[0]] = "MISSING_REQUIRED_EVIDENCE"
    blocking = [m for m in res["missing_required_evidence"] if m in ("null_distribution", "occlusion_status_unknown")]
    if "annotation_inconsistent" in res["inconclusive"]:
        res["verdict"] = "INCONCLUSIVO"; res["verdict_reason"] = "annotation_inconsistent"
    elif blocking:
        res["verdict"] = "INCONCLUSIVO"; res["verdict_reason"] = "missing_required_evidence:" + ",".join(blocking)  # sem nula/estado de oclusão não há como julgar identidade
    elif res["causes"]:
        res["verdict"] = "FAIL"; res["verdict_reason"] = "causes"
    elif res["missing_required_evidence"]:
        res["verdict"] = "INCONCLUSIVO"; res["verdict_reason"] = "missing_required_evidence"
    elif res["inconclusive"]:
        res["verdict"] = "INCONCLUSIVO"; res["verdict_reason"] = ";".join(res["inconclusive"])
    else:
        res["verdict"] = "PASS"; res["verdict_reason"] = "all_required_evidence_present"
    return res


# ------------------------------------------------------------------------------------------------------------------- main
MANIFEST_MASK_FIELDS = {  # arg → caminho no frozen_annotation
    "front_occluders": ("front_occluders_mask",), "band_min": ("plausible_occupancy_band", "min_mask"),
    "band_max_body": ("plausible_occupancy_band", "max_body_mask"), "free_space": ("free_space_mask",),
    "uncertain": ("uncertain_occupancy_mask",), "body_coverable": ("body_coverable_mask",), "protected": ("protected_mask",),
}


def _get(d, path):
    for k in path:
        if not isinstance(d, dict):
            return None
        d = d.get(k)
    return d


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--a", required=True)
    ap.add_argument("--b", help="B (opcional): conferido por sha256 contra o manifesto")
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
    ap.add_argument("--layer-graph", help="JSON: [{element, relation, mask, split_must_cover_mask?, split_must_stay_visible_mask?}]; se omitido com --manifest, é derivado do z_order")
    ap.add_argument("--human-adjudication", help="JSON cego {blind:true, evaluator_id, answers:{'split_edge:<el>': yes|no|ambiguous}} — só para split sem máscaras congeladas")
    ap.add_argument("--engine-is-paste-back", action="store_true", help="rota F2 com paste-back nativo: identidade de pixel em FO é eliminatória também em O_engine")
    ap.add_argument("--a-ref", help="referência NULA para O_engine: A após encode/decode do VAE da rota (denoise 0, mesma resolução/reprojeção). Deriva tol_engine (p99,5).")
    ap.add_argument("--null-stats", help="JSON da distribuição nula da rota {\"tol_p995\": n} (alternativa a --a-ref para tol_engine)")
    ap.add_argument("--tol-engine", type=int, default=None, help="tolerância explícita em O_engine (só perfil minimal; no g0 exige fonte nula)")
    ap.add_argument("--tol", type=int, default=None, help="(legado) = --tol-engine")
    ap.add_argument("--composed-contract", choices=["exact", "near_exact"], default="exact", help="exact: tol_composed=0 e protected_max_err>0 reprova")
    ap.add_argument("--tol-composed", type=int, default=0, help="só usado em near_exact")
    ap.add_argument("--profile", choices=["g0", "minimal"], default="g0", help="g0: evidência obrigatória por manifesto, PREREG/FREEZE e nula; minimal: dev/testes (nunca para o gate)")
    ap.add_argument("--occlusion-none", action="store_true", help="declara explicitamente que o caso não tem oclusor frontal (quando não há manifesto)")
    ap.add_argument("--g-source", default="unspecified", help="origem de G: sam3_text | sam3_points | human | other (nunca a máscara do motor)")
    ap.add_argument("--noop-mode", action="store_true", help="caso same_garment_noop: desliga 'G_without_change'")
    ap.add_argument("--manifest", help="manifest.jsonl congelado (com --case-id)"); ap.add_argument("--case-id")
    ap.add_argument("--data-root", help="raiz dos local_path do manifesto (padrão: raiz do repositório)")
    ap.add_argument("--prereg", help="arquivo PREREG.md commitado antes do run (sha256 calculado aqui)")
    ap.add_argument("--freeze", help="FREEZE.json gerado por tools/freeze_proto0.py")
    ap.add_argument("--roles", help="g0_case_roles.json (conferido contra FREEZE.json)")
    ap.add_argument("--commit-sha", help="commit do run (padrão: git rev-parse HEAD)")
    ap.add_argument("--contact-fringe-px", type=int, default=8)
    ap.add_argument("--crown-px", type=int, default=6)
    ap.add_argument("--min-occluder-identity", type=float, default=0.95, help="em O_engine com paste-back; em O_composed exact aplica-se 1.0")
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
    ap.add_argument("--min-changed-fraction-in-g", type=float, default=0.90)
    ap.add_argument("--max-fringe-delta-l", type=float, default=12.0, help="franja C3: |ΔL*| máximo por pixel (provisório)")
    ap.add_argument("--max-fringe-delta-chroma", type=float, default=6.0, help="franja C3: Δ(a*,b*) máximo por pixel (provisório)")
    ap.add_argument("--max-fringe-violation-frac", type=float, default=0.05)
    ap.add_argument("--min-fringe-structure-corr", type=float, default=0.6)
    ap.add_argument("--max-tol-engine", type=int, default=12, help="teto de credibilidade da nula: p99,5 de |A_ref − A| acima disso → nula não aceita (INCONCLUSIVO)")
    ap.add_argument("--json-out")
    args = ap.parse_args()
    if args.tol is not None and args.tol_engine is None:
        args.tol_engine = args.tol

    repo_root = fz.repo_root_from(__file__)
    data_root = args.data_root or repo_root
    out = {"auditor_version": VERSION, "profile": args.profile, "composed_contract": args.composed_contract,
           "thresholds": {k: getattr(args, k) for k in vars(args) if k.startswith(("min_", "max_", "contact", "crown"))},
           "provenance": {"run_commit_sha": args.commit_sha or fz.git_head(repo_root), "manifest_path": args.manifest, "case_id": args.case_id,
                          "prereg_path": args.prereg, "freeze_path": args.freeze, "roles_path": args.roles},
           "frozen_reference_check": {"mismatches": [], "checked_files": []}, "gate_eligible": False}
    prov = out["provenance"]; frc = out["frozen_reference_check"]
    missing_global = []

    def bail(verdict, code):
        out["verdict_engine"] = out["verdict_composed"] = verdict
        js = json.dumps(out, indent=1, ensure_ascii=False); print(js)
        if args.json_out:
            open(args.json_out, "w", encoding="utf-8").write(js)
        sys.exit(code)

    # --- congelamento / proveniência (antes de qualquer avaliação do motor)
    row = None
    if args.profile == "g0":
        for need, val in (("manifest", args.manifest), ("case_id", args.case_id), ("prereg", args.prereg), ("freeze", args.freeze)):
            if not val:
                missing_global.append(f"provenance:{need}")
    if args.prereg:
        if os.path.exists(args.prereg):
            prov["prereg_sha256"] = fz.sha256_file(args.prereg)
        else:
            frc["mismatches"].append(f"ausente:prereg:{args.prereg}")
    if args.manifest:
        if os.path.exists(args.manifest):
            prov["manifest_sha256"] = fz.sha256_file(args.manifest)
            rows = fz.load_manifest(args.manifest)
            row = fz.find_row(rows, args.case_id) if args.case_id else None
            if row is None:
                frc["mismatches"].append(f"caso_ausente_no_manifesto:{args.case_id}")
        else:
            frc["mismatches"].append(f"ausente:manifest:{args.manifest}")
    if args.roles and os.path.exists(args.roles):
        prov["roles_sha256"] = fz.sha256_file(args.roles)
    if args.freeze:
        info, mism = fz.verify_freeze(args.freeze, args.manifest, args.prereg, args.roles)
        prov.update({k: v for k, v in info.items() if k != "freeze_path"})
        frc["mismatches"].extend(mism)
    if row is not None:
        fa = row.get("expected", {}).get("frozen_annotation", {}) or {}
        prov["freeze_tag_manifest"] = fa.get("freeze_tag"); prov["freeze_commit_manifest"] = fa.get("freeze_commit")
        checked, mism = fz.verify_row_files(row, data_root)
        frc["checked_files"] = checked; frc["mismatches"].extend(mism)
        for label, given, src in (("A", args.a, row.get("A")), ("B", args.b, row.get("B"))):
            m = fz.verify_input_matches(given, src, label)
            if m:
                frc["mismatches"].append(m)
            if given and os.path.exists(given):
                prov[f"{label.lower()}_sha256"] = fz.sha256_file(given)
        # máscaras: resolver do manifesto quando não passadas; conferir quando passadas
        for arg, path in MANIFEST_MASK_FIELDS.items():
            src = _get(fa, path)
            given = getattr(args, arg)
            if src and src.get("local_path"):
                if given is None:
                    setattr(args, arg, fz.resolve_path(src["local_path"], data_root))
                else:
                    m = fz.verify_input_matches(given, src, arg)
                    if m:
                        frc["mismatches"].append(m)
    if frc["mismatches"]:
        bail("FAIL:frozen_reference_mismatch", 1)

    # --- carregar A e máscaras
    A = load_rgb(args.a); shape = A.shape[:2]
    M = {"FO": load_bin(args.front_occluders, shape), "BMIN": load_bin(args.band_min, shape), "BMAXB": load_bin(args.band_max_body, shape),
         "FS": load_bin(args.free_space, shape), "UNC": load_bin(args.uncertain, shape), "BC": load_bin(args.body_coverable, shape),
         "PR": load_bin(args.protected, shape), "PROFILE": args.profile, "G_SOURCE": args.g_source, "noop_mode": bool(args.noop_mode), "EVIDENCE": {}}

    # --- layer graph (explícito ou derivado do manifesto) e estado de oclusão
    layers = None
    if args.layer_graph:
        layers = json.load(open(args.layer_graph, encoding="utf-8")); src_lg = "layer_graph_arg"
        if row is not None:  # layer graph explícito só é aceito como BIJEÇÃO do z_order congelado: mesmos elementos, mesma relação, toda máscara congelada presente e conferida
            zo = {z.get("element"): z for z in ((row.get("expected", {}).get("frozen_annotation", {}) or {}).get("z_order", []) or [])}
            lg_mism = []
            seen = set()
            for el in layers:
                z = zo.get(el.get("element"))
                if z is None:
                    lg_mism.append(f"layer_graph:elemento_nao_congelado:{el.get('element')}"); continue
                seen.add(el.get("element"))
                if el.get("relation") != z.get("relation"):
                    lg_mism.append(f"layer_graph:relacao_divergente:{el.get('element')}:{el.get('relation')}!={z.get('relation')}")
                for key in ("mask", "split_must_cover_mask", "split_must_stay_visible_mask"):
                    src_ = z.get(key)
                    if isinstance(src_, dict) and src_.get("local_path"):
                        if not el.get(key):
                            lg_mism.append(f"layer_graph:{el.get('element')}:{key}:mascara_congelada_omitida"); continue
                        m = fz.verify_input_matches(el[key], src_, f"layer_graph:{el.get('element')}:{key}")
                        if m:
                            lg_mism.append(m)
                    elif el.get(key):
                        lg_mism.append(f"layer_graph:{el.get('element')}:{key}:sem_referencia_congelada")
            for name in zo:
                if name not in seen:
                    lg_mism.append(f"layer_graph:elemento_congelado_omitido:{name}")
            if lg_mism:
                frc["mismatches"].extend(lg_mism)
                bail("FAIL:frozen_reference_mismatch", 1)
    elif row is not None:
        zo = (row.get("expected", {}).get("frozen_annotation", {}) or {}).get("z_order", []) or []
        layers = []
        for z in zo:
            e = {"element": z.get("element"), "relation": z.get("relation")}
            for key, name in (("mask", "mask"), ("split_must_cover_mask", "split_must_cover_mask"), ("split_must_stay_visible_mask", "split_must_stay_visible_mask")):
                s = z.get(key)
                e[name] = fz.resolve_path(s["local_path"], data_root) if isinstance(s, dict) and s.get("local_path") else None
            layers.append(e)
        src_lg = "manifest_z_order"
    if layers:
        for el in layers:
            el["mask_arr"] = load_bin(el.get("mask"), shape) if el.get("mask") else None
            el["must_cover_arr"] = load_bin(el.get("split_must_cover_mask"), shape) if el.get("split_must_cover_mask") else None
            el["must_stay_visible_arr"] = load_bin(el.get("split_must_stay_visible_mask"), shape) if el.get("split_must_stay_visible_mask") else None
        M["LAYERS"] = layers; M["EVIDENCE"]["layer_graph"] = f"PRESENT:{src_lg}"
    if row is not None:
        zo = (row.get("expected", {}).get("frozen_annotation", {}) or {}).get("z_order", []) or []
        fc = [z["element"] for z in zo if z.get("relation") == "front_certain"]
        M["FRONT_CERTAIN_EXPECTED"] = fc
        occl = row.get("coverage", {}).get("occlusion")
        if fc:
            M["HAS_FRONT_CERTAIN"] = True; M["EVIDENCE"]["occlusion_status"] = f"front_certain_from_manifest:{','.join(fc)}"
            if occl == ["none"]:
                M["ANNOTATION_ISSUES"] = ["manifesto declara occlusion=['none'] mas z_order tem front_certain"]
        elif occl == ["none"]:
            M["HAS_FRONT_CERTAIN"] = False; M["EVIDENCE"]["occlusion_status"] = "manifest_declares_none"
        else:  # oclusão declarada (ou ausente) sem nenhum elemento front_certain: anotação contraditória — nunca NOT_APPLICABLE
            M["HAS_FRONT_CERTAIN"] = None; M["EVIDENCE"]["occlusion_status"] = f"manifest_occlusion_{occl}_without_front_certain"
            M["ANNOTATION_ISSUES"] = [f"coverage.occlusion={occl} sem elemento front_certain no z_order (NOT_APPLICABLE exige occlusion==['none'])"]
            out.setdefault("flags", []).append("occlusion_listed_without_front_certain_element")
    elif layers:
        fc = [e["element"] for e in layers if e.get("relation") == "front_certain"]
        M["HAS_FRONT_CERTAIN"] = bool(fc); M["EVIDENCE"]["occlusion_status"] = "from_layer_graph"; M["FRONT_CERTAIN_EXPECTED"] = fc
    elif M["FO"] is not None and M["FO"].sum() > 0:
        M["HAS_FRONT_CERTAIN"] = True; M["EVIDENCE"]["occlusion_status"] = "from_front_occluders_mask"
    elif args.occlusion_none:
        M["HAS_FRONT_CERTAIN"] = False; M["EVIDENCE"]["occlusion_status"] = "declared_none_by_flag"
    else:
        M["HAS_FRONT_CERTAIN"] = None; M["EVIDENCE"]["occlusion_status"] = "UNKNOWN"
    out["occlusion_status"] = M["EVIDENCE"]["occlusion_status"]
    if args.human_adjudication:
        adj = json.load(open(args.human_adjudication, encoding="utf-8"))
        if adj.get("blind") is True:
            M["ADJUD"] = adj
        else:
            missing_global.append("adjudication_not_blind")
    if args.keypoints_a and args.keypoints_engine:
        kpa = json.load(open(args.keypoints_a, encoding="utf-8")); kpe = json.load(open(args.keypoints_engine, encoding="utf-8"))
        def _valid_kp(k):
            if not isinstance(k, dict) or not isinstance(k.get("counts"), dict):
                return False
            if not all(isinstance(k["counts"].get(p), int) for p in ("hands", "forearms")):
                return False
            return sum(1 for p in ("hands", "forearms") for pt in k.get(p, []) if len(pt) >= 3 and pt[2] > 0.3) >= 1
        if _valid_kp(kpa) and _valid_kp(kpe):
            M["KP_A"] = kpa; M["KP_E"] = kpe
            M["scale_px"] = args.person_scale_px or float(np.hypot(*shape)); M["EVIDENCE"]["keypoints"] = "PRESENT"
        else:
            missing_global.append("keypoints_empty_or_invalid")  # JSON vazio/sem detecções não é evidência de mão intacta

    # --- tolerâncias
    fi = image_format_issue(args.o_engine)
    if fi:
        out["format_issue"] = f"engine:{fi}"; bail("INCONCLUSIVO:format_mismatch:engine", 3)
    prov["o_engine_sha256"] = fz.sha256_file(args.o_engine)
    Oe = load_rgb(args.o_engine)
    if Oe.shape != A.shape:
        bail("FAIL:canvas_mismatch:engine", 1)
    Me = dict(M); Me["pixel_identity_is_eliminatory"] = bool(args.engine_is_paste_back); Me["OCC_ENGINE"] = load_bin(args.occluder_mask_engine, shape)
    if Me["OCC_ENGINE"] is not None:
        Me["EVIDENCE"] = dict(M["EVIDENCE"], occluder_mask_engine="PRESENT")
    tol_src = None
    if args.a_ref:
        Aref = load_rgb(args.a_ref)
        if Aref.shape != A.shape:
            bail("FAIL:canvas_mismatch:a_ref", 1)
        Me["A_REF"] = Aref; tol_engine = derive_tol_from_null(A, Aref); tol_src = "a_ref_p99.5"
        prov["a_ref_sha256"] = fz.sha256_file(args.a_ref)
        # credibilidade da nula: um round-trip de VAE não move p99,5 dos pixels além de --max-tol-engine; acima disso a "nula" não é nula
        if tol_engine > args.max_tol_engine:
            out.setdefault("flags", []).append(f"null_distribution_not_credible:tol_p995={tol_engine}>{args.max_tol_engine}")
            missing_global.append("null_distribution")
    elif args.null_stats:
        try:
            ns = json.load(open(args.null_stats, encoding="utf-8")); tol_engine = int(math.ceil(float(ns["tol_p995"]))); tol_src = "null_stats"
        except (OSError, ValueError, TypeError, KeyError, json.JSONDecodeError) as e:
            out["null_stats_error"] = str(e); bail("INCONCLUSIVO:null_stats_invalid", 3)
        if tol_engine > args.max_tol_engine or tol_engine < 1:
            out.setdefault("flags", []).append(f"null_distribution_not_credible:tol_p995={tol_engine}")
            missing_global.append("null_distribution")
    elif args.tol_engine is not None:
        tol_engine = int(args.tol_engine); tol_src = "explicit"
        if args.profile == "g0":
            missing_global.append("null_distribution")
    else:
        tol_engine = 2; tol_src = "default_uncalibrated"; missing_global.append("null_distribution")
    out["tol_engine"] = tol_engine; out["tol_engine_source"] = tol_src
    tol_composed = 0 if args.composed_contract == "exact" else int(args.tol_composed)
    out["tol_composed"] = tol_composed
    Me["MISSING"] = list(missing_global)

    Ge = load_bin(args.garment_mask, shape)
    out["engine"] = audit_target(A, Oe, Ge, Me, args, tol_engine, "engine")

    if args.o_composed:
        fi = image_format_issue(args.o_composed)
        if fi:
            out["format_issue"] = f"composed:{fi}"; bail("INCONCLUSIVO:format_mismatch:composed", 3)
        prov["o_composed_sha256"] = fz.sha256_file(args.o_composed)
        Oc = load_rgb(args.o_composed)
        if Oc.shape != A.shape:
            bail("FAIL:canvas_mismatch:composed", 1)
        Gc = load_bin(args.garment_mask_composed, shape) if args.garment_mask_composed else Ge
        Mc = dict(M); Mc["pixel_identity_is_eliminatory"] = True; Mc.pop("KP_A", None); Mc.pop("KP_E", None); Mc["MISSING"] = [m for m in missing_global if m != "null_distribution"]
        out["composed"] = audit_target(A, Oc, Gc, Mc, args, tol_composed, "composed")
        FO = M.get("FO")
        if FO is not None and FO.sum() > 0:
            crown = dilate(FO, args.crown_px) & ~FO
            out["composed"]["composition_seam"] = float(np.abs(grad_mag(Oc) - grad_mag(Oe))[crown].mean())

    out["verdict_engine"] = out["engine"]["verdict"]
    out["verdict_composed"] = out.get("composed", {}).get("verdict")
    out["gate_eligible"] = bool(args.profile == "g0" and not frc["mismatches"] and not missing_global and row is not None and prov.get("freeze_sha256"))
    js = json.dumps(out, indent=1, ensure_ascii=False)
    print(js)
    if args.json_out:
        open(args.json_out, "w", encoding="utf-8").write(js)
    worst = [v for v in (out["verdict_engine"], out["verdict_composed"]) if v]
    sys.exit(1 if "FAIL" in worst else (3 if "INCONCLUSIVO" in worst else 0))


if __name__ == "__main__":
    main()
