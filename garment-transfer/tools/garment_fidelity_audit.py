#!/usr/bin/env python3
r"""
garment_fidelity_audit.py — evidência (iii) da definição operacional de "ocupado por tecido da PEÇA B" (`00` §4.4): IDENTIDADE DA PEÇA.
Obrigatório no Gate G0: um caso só PASSA se `occupancy_audit.py` (G independente + mudança real) E este auditor passam (`tools/g0_gate.py`).

Evidências (todas congeladas/independentes do gerador):
  1. Atributos congelados no manifesto (`expected.garment_attributes`, estado observado, `expected_visible_in_O: yes`) adjudicados por
     avaliador humano CEGO (--adjudication JSON {blind:true, evaluator_id, date, catch_trials_passed, answers:{<atributo>: yes|no|ambiguous}}).
     `category` = no → FAIL wrong_category (eliminatório); outro atributo = no → FAIL attribute_mismatch:<nome>; ambiguous → INCONCLUSIVO.
     Atributo com valor placeholder ("A PREENCHER", "TBD", estado unknown) → INCONCLUSIVO:missing_required_evidence:attributes_not_frozen.
  2. Cromaticidade (determinística): Lab (a*,b*) do tecido G em O′ vs. máscara congelada da peça em B (--b-garment-mask / manifesto
     `expected.b_garment_mask`): distância dos centróides de croma e interseção de histogramas de matiz (36 bins, pixels com croma > 5).
     Falha se distância > --max-chroma-distance OU interseção < --min-hue-intersection (provisórios; calibrar no `same_garment_noop`).
     L* é reportado, não eliminatório (iluminação de A ≠ B).
  3. Embedding (opcional, só relatório): --embedding-o/--embedding-b/--embedding-random (.npy ou JSON) → cos(o,b) − cos(o,random).
Proveniência: mesmas regras de `occupancy_audit.py` (--manifest/--case-id/--prereg/--freeze; sha256 de A/B/máscaras; FAIL:frozen_reference_mismatch).
Exit: 0 PASS · 1 FAIL · 3 INCONCLUSIVO.
"""
import argparse, json, os, sys
import numpy as np
from PIL import Image

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import freeze_check as fz  # noqa: E402
from occupancy_audit import load_rgb, load_bin, _srgb_to_lab  # noqa: E402

PLACEHOLDER_MARKERS = ("A PREENCHER", "TBD", "PLACEHOLDER")


def load_vec(path):
    if path.endswith(".npy"):
        return np.load(path).astype(np.float64).ravel()
    return np.asarray(json.load(open(path)), dtype=np.float64).ravel()


def cos(a, b):
    return float(a @ b / (np.linalg.norm(a) * np.linalg.norm(b) + 1e-12))


def chroma_stats(img, mask):
    lab = _srgb_to_lab(img)[mask]
    L, a, b = lab[:, 0], lab[:, 1], lab[:, 2]
    c = np.hypot(a, b)
    hue = np.degrees(np.arctan2(b, a)) % 360.0
    sel = c > 5.0
    hist = np.histogram(hue[sel], bins=36, range=(0, 360))[0].astype(np.float64)
    hist = hist / hist.sum() if hist.sum() > 0 else hist
    return {"L_mean": float(L.mean()), "a_mean": float(a.mean()), "b_mean": float(b.mean()), "chroma_mean": float(c.mean()),
            "chromatic_frac": float(sel.mean()), "hue_hist": hist}


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--manifest"); ap.add_argument("--case-id"); ap.add_argument("--data-root")
    ap.add_argument("--prereg"); ap.add_argument("--freeze"); ap.add_argument("--roles")
    ap.add_argument("--allow-dirty-freeze", action="store_true", help="SÓ TESTES: aceita FREEZE.json gerado em árvore git suja")
    ap.add_argument("--a", help="A (conferido por sha256)"); ap.add_argument("--b", help="B (para cromaticidade; conferido por sha256)")
    ap.add_argument("--b-garment-mask", help="máscara congelada da peça em B (padrão: manifesto expected.b_garment_mask)")
    ap.add_argument("--o-engine", help="O′ (saída bruta reprojetada)"); ap.add_argument("--garment-mask", help="G em O′ (segmentador independente)")
    ap.add_argument("--adjudication", help="JSON cego de atributos")
    ap.add_argument("--attributes", help="JSON de atributos congelados (só perfil minimal; no g0 vêm do manifesto)")
    ap.add_argument("--embedding-o"); ap.add_argument("--embedding-b"); ap.add_argument("--embedding-random")
    ap.add_argument("--profile", choices=["g0", "minimal"], default="g0")
    ap.add_argument("--max-chroma-distance", type=float, default=12.0); ap.add_argument("--min-hue-intersection", type=float, default=0.40)
    ap.add_argument("--min-chroma-inlier-fraction", type=float, default=0.60, help="fração mínima de pixels de G a ≤ max-chroma-distance do centróide (a*,b*) de B")
    ap.add_argument("--max-achromatic-delta-l", type=float, default=30.0, help="peças acromáticas: |ΔL*| médio acima disto não é iluminação (branco vs preto)")
    ap.add_argument("--min-embedding-margin", type=float, default=0.0, help="só relatório/flag")
    ap.add_argument("--json-out")
    args = ap.parse_args()
    root = fz.repo_root_from(__file__); data_root = args.data_root or root
    out = {"auditor": "garment_fidelity_audit", "version": "1", "profile": args.profile, "causes": [], "inconclusive": [], "missing_required_evidence": [],
           "flags": [], "evidence": {}, "provenance": {"run_commit_sha": fz.git_head(root), "run_tree_dirty": fz.git_dirty(root), "manifest_path": args.manifest, "case_id": args.case_id,
                                                        "prereg_path": args.prereg, "freeze_path": args.freeze, "roles_path": args.roles, "allow_dirty_freeze": bool(args.allow_dirty_freeze)},
           "frozen_reference_check": {"mismatches": []}, "gate_eligible": False,
           "thresholds": {"max_chroma_distance": args.max_chroma_distance, "min_hue_intersection": args.min_hue_intersection,
                          "min_chroma_inlier_fraction": args.min_chroma_inlier_fraction, "max_achromatic_delta_l": args.max_achromatic_delta_l}}
    prov, frc = out["provenance"], out["frozen_reference_check"]

    def finish(verdict, code):
        out["verdict"] = verdict
        js = json.dumps(out, indent=1, ensure_ascii=False); print(js)
        if args.json_out:
            open(args.json_out, "w", encoding="utf-8").write(js)
        sys.exit(code)

    row = None
    if args.profile == "g0":
        for need, val in (("manifest", args.manifest), ("case_id", args.case_id), ("prereg", args.prereg), ("freeze", args.freeze), ("roles", args.roles)):
            if not val:
                out["missing_required_evidence"].append(f"provenance:{need}")
    if args.prereg and os.path.exists(args.prereg):
        prov["prereg_sha256"] = fz.sha256_file(args.prereg)
    elif args.prereg:
        frc["mismatches"].append(f"ausente:prereg:{args.prereg}")
    if args.manifest:
        if os.path.exists(args.manifest):
            prov["manifest_sha256"] = fz.sha256_file(args.manifest)
            rows = fz.load_manifest(args.manifest)
            dups = fz.duplicate_case_ids(rows)
            if dups:
                frc["mismatches"].append("case_id_duplicado:" + ",".join(dups))
            row = fz.find_row(rows, args.case_id) if args.case_id else None
            if row is None:
                frc["mismatches"].append(f"caso_ausente_ou_duplicado_no_manifesto:{args.case_id}")
        else:
            frc["mismatches"].append(f"ausente:manifest:{args.manifest}")
    if args.roles:
        if os.path.exists(args.roles):
            prov["roles_sha256"] = fz.sha256_file(args.roles)
        else:
            frc["mismatches"].append(f"ausente:roles:{args.roles}")
    if args.freeze:
        info, mism = fz.verify_freeze(args.freeze, args.manifest, args.prereg, args.roles, allow_dirty=args.allow_dirty_freeze)
        prov.update({k: v for k, v in info.items() if k != "freeze_path"}); frc["mismatches"].extend(mism)
    attributes = None
    if row is not None:
        checked, mism = fz.verify_row_files(row, data_root); frc["checked_files"] = checked; frc["mismatches"].extend(mism)
        fa_ = row.get("expected", {}).get("frozen_annotation", {}) or {}
        if args.freeze and fa_.get("freeze_tag") and prov.get("freeze_tag") and fa_["freeze_tag"] != prov["freeze_tag"]:
            frc["mismatches"].append(f"freeze_tag:manifesto={fa_['freeze_tag']}!=FREEZE={prov['freeze_tag']}")
        for label, given, src in (("A", args.a, row.get("A")), ("B", args.b, row.get("B"))):
            m = fz.verify_input_matches(given, src, label)
            if m:
                frc["mismatches"].append(m)
        bg = row.get("expected", {}).get("b_garment_mask")
        if isinstance(bg, dict) and bg.get("local_path"):
            if args.b_garment_mask is None:
                args.b_garment_mask = fz.resolve_path(bg["local_path"], data_root)
            else:
                m = fz.verify_input_matches(args.b_garment_mask, bg, "b_garment_mask")
                if m:
                    frc["mismatches"].append(m)
        attributes = row.get("expected", {}).get("garment_attributes", [])
    frc["mismatches"] = sorted(set(frc["mismatches"]))
    if frc["mismatches"]:
        finish("FAIL:frozen_reference_mismatch", 1)
    if attributes is None and args.attributes:
        attributes = json.load(open(args.attributes, encoding="utf-8"))
    if attributes is None:
        out["missing_required_evidence"].append("attributes")
        attributes = []

    # 1. atributos congelados + adjudicação cega
    judged = {}
    required = [a for a in attributes if a.get("expected_visible_in_O", "yes") == "yes"]
    if not any(a.get("name") == "category" for a in required):
        out["missing_required_evidence"].append("attributes:category")  # sem categoria congelada a adjudicação é vazia e wrong_category inalcançável
    not_frozen = [a["name"] for a in required if a.get("state") == "unknown" or any(mk in str(a.get("value", "")).upper() for mk in PLACEHOLDER_MARKERS)]
    if not_frozen:
        out["missing_required_evidence"].append("attributes_not_frozen:" + ",".join(not_frozen))
    adj = None
    if args.adjudication:
        adj = json.load(open(args.adjudication, encoding="utf-8"))
        o_sha = fz.sha256_file(args.o_engine) if args.o_engine and os.path.exists(args.o_engine) else None
        prov["o_engine_sha256"] = o_sha
        problems = fz.validate_adjudication(adj, args.case_id, o_sha, strict=(args.profile == "g0"))
        if problems:
            out["missing_required_evidence"].extend("adjudication_invalid:" + pb for pb in problems); adj = None
    if adj is None:
        if required:
            out["missing_required_evidence"].append("blind_adjudication")
    else:
        out["evidence"]["blind_adjudication"] = {"evaluator_id": adj.get("evaluator_id"), "date": adj.get("date")}
        for a in required:
            name = a["name"]; ans = adj.get("answers", {}).get(name)
            judged[name] = {"expected": a.get("value"), "answer": ans}
            if ans is None:
                out["missing_required_evidence"].append(f"adjudication:{name}")
            elif ans == "no":
                out["causes"].append("wrong_category" if name == "category" else f"attribute_mismatch:{name}")
            elif ans != "yes":
                out["inconclusive"].append(f"attribute_ambiguous:{name}")
    out["attributes_judged"] = judged

    # 2. cromaticidade
    if args.o_engine and os.path.exists(args.o_engine):
        prov["o_engine_sha256"] = fz.sha256_file(args.o_engine)
    if args.garment_mask and os.path.exists(args.garment_mask):
        prov["garment_mask_sha256"] = fz.sha256_file(args.garment_mask)
    if args.o_engine and args.garment_mask and args.b and args.b_garment_mask:
        O = load_rgb(args.o_engine); G = load_bin(args.garment_mask, O.shape[:2])
        B = load_rgb(args.b); BG = load_bin(args.b_garment_mask, B.shape[:2])
        if G.sum() == 0 or BG.sum() == 0:
            out["inconclusive"].append("chroma:empty_mask")
        else:
            so, sb = chroma_stats(O, G), chroma_stats(B, BG)
            out["chroma"] = {"o": {k: v for k, v in so.items() if k != "hue_hist"}, "b": {k: v for k, v in sb.items() if k != "hue_hist"}}
            out["chroma"]["centroid_distance_ab"] = float(np.hypot(so["a_mean"] - sb["a_mean"], so["b_mean"] - sb["b_mean"]))
            out["chroma"]["hue_hist_intersection"] = float(np.minimum(so["hue_hist"], sb["hue_hist"]).sum())
            out["chroma"]["delta_L_mean"] = float(so["L_mean"] - sb["L_mean"])
            achromatic = so["chromatic_frac"] < 0.2 and sb["chromatic_frac"] < 0.2
            out["chroma"]["both_achromatic"] = bool(achromatic)
            # fração de pixels de G dentro de ΔE_ab ≤ limiar do centróide de B (robusto a misturas simétricas em torno do centróide)
            lab_o = _srgb_to_lab(O)[G]
            d_ab = np.hypot(lab_o[:, 1] - sb["a_mean"], lab_o[:, 2] - sb["b_mean"])
            out["chroma"]["inlier_fraction"] = float((d_ab <= args.max_chroma_distance).mean())
            if out["chroma"]["centroid_distance_ab"] > args.max_chroma_distance:
                out["causes"].append("garment_identity:chroma_mismatch")
            if not achromatic and out["chroma"]["hue_hist_intersection"] < args.min_hue_intersection:
                out["causes"].append("garment_identity:hue_distribution_mismatch")
            if out["chroma"]["inlier_fraction"] < args.min_chroma_inlier_fraction:
                out["causes"].append("garment_identity:chroma_inlier_fraction_low")
            if achromatic and abs(out["chroma"]["delta_L_mean"]) > args.max_achromatic_delta_l:
                out["causes"].append("garment_identity:achromatic_lightness_mismatch")  # branco vs preto não é iluminação
            out["evidence"]["chroma"] = "PRESENT"
    elif args.profile == "g0":
        out["missing_required_evidence"].append("chroma_evidence(b, b_garment_mask, o_engine, garment_mask)")

    # 3. embedding (relatório)
    if args.embedding_o and args.embedding_b:
        eo, eb = load_vec(args.embedding_o), load_vec(args.embedding_b)
        emb = {"cos_o_b": cos(eo, eb)}
        if args.embedding_random:
            er = load_vec(args.embedding_random); emb["cos_o_random"] = cos(eo, er); emb["margin"] = emb["cos_o_b"] - emb["cos_o_random"]
            if emb["margin"] < args.min_embedding_margin:
                out["flags"].append("embedding_margin_below_random (relatório; não eliminatório)")
        out["embedding"] = emb

    out["missing_required_evidence"] = sorted(set(out["missing_required_evidence"]))
    out["gate_eligible"] = bool(args.profile == "g0" and row is not None and prov.get("freeze_sha256") and not out["missing_required_evidence"])
    if out["causes"]:
        finish("FAIL", 1)
    if out["missing_required_evidence"] or out["inconclusive"]:
        finish("INCONCLUSIVO", 3)
    finish("PASS", 0)


if __name__ == "__main__":
    main()
