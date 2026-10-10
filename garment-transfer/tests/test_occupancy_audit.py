#!/usr/bin/env python3
"""Testes metamórficos/regressão do auditor de ocupação (CPU). Rodar: python tests/test_occupancy_audit.py
São controles do AUDITOR (não das rotas): cada teste constrói entradas sintéticas com veredito ESPERADO.
Cobre os blockers da auditoria externa: NOT_APPLICABLE vs MISSING_REQUIRED_EVIDENCE; evidência obrigatória por manifesto; tol_engine (nula) vs
tol_composed=0 (exact); franja C3 limitada; split_by_garment_edge julgável; consistência de BAND_MIN pequeno; A/PREREG/manifesto alterados após o freeze."""
import json, os, shutil, sys, tempfile
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _fixtures import build_case_dir, run_audit, perfect_output, engine_output, noisy, save_rgb, save_mask, Checker, GARMENT_RGB, build_masks, AUDIT, make_adj, ADJ_YES, ADJ_NO  # noqa: E402
import subprocess  # noqa: E402


def main():
    c = Checker()
    with tempfile.TemporaryDirectory() as d:
        fx = build_case_dir(d); hard, easy = fx["hard"], fx["easy"]; F = fx["files"]
        Gs = os.path.join(d, "G_split.png"); save_mask(Gs, hard["G_split"])
        Ge = os.path.join(d, "G_easy.png"); save_mask(Ge, easy["G"])
        aref_h = noisy(hard["A"], 3, 11); Aref_h = os.path.join(d, "aref_hard.png"); save_rgb(Aref_h, aref_h)
        aref_e = noisy(easy["A"], 3, 12); Aref_e = os.path.join(d, "aref_easy.png"); save_rgb(Aref_e, aref_e)
        O_hard = os.path.join(d, "o_hard.png"); save_rgb(O_hard, engine_output(hard, aref_h, hard["G_split"], 1))
        O_easy = os.path.join(d, "o_easy.png"); save_rgb(O_easy, engine_output(easy, aref_e, None, 2))

        # B-01: EASY sem oclusor (manifesto occlusion=["none"], sem front_certain) → PASS, eixo D NOT_APPLICABLE (não INCONCLUSIVO)
        j, rc = run_audit(fx, "synth_easy_01", O_easy, Ge, a_ref=Aref_e)
        c.ok("B01_easy_sem_oclusor_PASS", j["verdict_engine"] == "PASS" and rc == 0, (j["verdict_engine"], j["engine"].get("missing_required_evidence"), j["engine"]["causes"]))
        c.ok("B01_eixoD_NOT_APPLICABLE", j["engine"]["evidence"].get("front_occluders") == "NOT_APPLICABLE" and j["occlusion_status"] == "manifest_declares_none", j["engine"]["evidence"])
        c.ok("B01_gate_eligible", j["gate_eligible"] is True, j.get("gate_eligible"))

        # B-02: HARD com front_certain — evidência obrigatória ausente → INCONCLUSIVO:missing_required_evidence, nunca PASS
        j, rc = run_audit(fx, "synth_hard_01", O_hard, Gs, a_ref=Aref_h, with_occ=False)
        c.ok("B02_sem_OCC_ENGINE_nao_PASS", j["verdict_engine"] == "INCONCLUSIVO" and rc == 3 and "occluder_mask_engine" in j["engine"]["missing_required_evidence"], (j["verdict_engine"], j["engine"]["missing_required_evidence"]))
        j, rc = run_audit(fx, "synth_hard_01", O_hard, Gs, a_ref=Aref_h, with_kp=False)
        c.ok("B02_sem_keypoints_nao_PASS", j["verdict_engine"] == "INCONCLUSIVO" and "keypoints" in j["engine"]["missing_required_evidence"], j["engine"]["missing_required_evidence"])
        j, rc = run_audit(fx, "synth_hard_01", O_hard, Gs, a_ref=Aref_h, with_occ=False, with_kp=False)
        c.ok("B02_evidence_marcada_MISSING", j["engine"]["evidence"].get("occluder_mask_engine") == "MISSING_REQUIRED_EVIDENCE" and j["engine"]["evidence"].get("keypoints") == "MISSING_REQUIRED_EVIDENCE", j["engine"]["evidence"])
        # perfil minimal: a garantia vale também — FO não vazia sem OCC_ENGINE/keypoints → nunca PASS
        args_min = ["--front-occluders", F["hard_FO.png"], "--band-min", F["hard_BMIN_split.png"], "--band-max-body", F["hard_BMAXB.png"], "--free-space", F["hard_FS.png"],
                    "--uncertain", F["hard_UNC.png"], "--body-coverable", F["hard_BC.png"], "--protected", F["hard_PR.png"], "--tol-engine", "4"]
        j, rc = run_audit(fx, "synth_hard_01", O_hard, Gs, profile="minimal", with_occ=False, with_kp=False, extra=args_min)
        c.ok("B02_minimal_front_certain_sem_evidencia_nao_PASS", j["verdict_engine"] != "PASS" and "occluder_mask_engine" in j["engine"]["missing_required_evidence"], (j["verdict_engine"], j["engine"]["missing_required_evidence"]))

        # completo → PASS
        j, rc = run_audit(fx, "synth_hard_01", O_hard, Gs, a_ref=Aref_h)
        c.ok("B02_hard_completo_PASS", j["verdict_engine"] == "PASS" and rc == 0 and j["gate_eligible"], (j["verdict_engine"], j["engine"]["causes"], j["engine"]["missing_required_evidence"], j["engine"]["inconclusive"]))
        c.ok("B06_split_julgado_por_mascaras_PASS", j["engine"]["per_element"]["upper_arm_L"]["verdict"] == "PASS" and j["engine"]["per_element"]["upper_arm_L"]["judged_by"] == "frozen_masks", j["engine"]["per_element"]["upper_arm_L"])
        c.ok("B08_provenance_registrada", all(j["provenance"].get(k) for k in ("manifest_sha256", "prereg_sha256", "freeze_sha256", "freeze_tag")) and "run_commit_sha" in j["provenance"], j["provenance"])
        c.ok("B04_identidade_de_B_nao_reivindicada", "NOT_EVALUATED_HERE" in j["engine"]["garment_identity"], j["engine"]["garment_identity"])

        # B-03: tolerâncias separadas — composed exact: +1 RGB em PROTECTED reprova; engine passa
        Oc = perfect_output(hard, hard["G_split"]).copy(); Oc[2, 2] = np.clip(Oc[2, 2].astype(int) + 1, 0, 255)
        Oc_p = os.path.join(d, "o_comp_plus1.png"); save_rgb(Oc_p, Oc)
        j, rc = run_audit(fx, "synth_hard_01", O_hard, Gs, a_ref=Aref_h, o_composed=Oc_p)
        c.ok("B03_composed_exact_plus1_FAIL", j["verdict_composed"] == "FAIL" and "unauthorized_change:protected_exact" in j["composed"]["causes"] and j["composed"]["protected_max_err"] == 1 and j["tol_composed"] == 0,
             (j["verdict_composed"], j["composed"]["causes"], j["composed"].get("protected_max_err")))
        c.ok("B03_engine_PASS_com_tol_da_nula_normativa", j["verdict_engine"] == "PASS" and j["tol_engine_source"] == "null_stats" and j["tol_engine"] == 4 and j["engine"]["identity_reference"] == "A", (j["verdict_engine"], j["tol_engine"], j["tol_engine_source"]))
        j, rc = run_audit(fx, "synth_hard_01", O_hard, Gs, a_ref=Aref_h, o_composed=Oc_p, extra=["--composed-contract", "near_exact", "--tol-composed", "2"])
        c.ok("B03_composed_near_exact_tol2_PASS", j["verdict_composed"] == "PASS" and j["tol_composed"] == 2, (j["verdict_composed"], j["composed"]["causes"]))
        # composed exact perfeito → PASS (identidade 1.0 em FO e PR)
        Oc_ok = os.path.join(d, "o_comp_ok.png"); save_rgb(Oc_ok, perfect_output(hard, hard["G_split"]))
        j, rc = run_audit(fx, "synth_hard_01", O_hard, Gs, a_ref=Aref_h, o_composed=Oc_ok)
        c.ok("B03_composed_exact_perfeito_PASS", j["verdict_composed"] == "PASS" and j["composed"]["front_occluder_pixel_identity"] == 1.0, (j["verdict_composed"], j["composed"]["causes"]))
        # g0 sem fonte nula → INCONCLUSIVO (não FAIL/PASS)
        j, rc = run_audit(fx, "synth_hard_01", O_hard, Gs)
        c.ok("B03_g0_sem_nula_INCONCLUSIVO", j["verdict_engine"] == "INCONCLUSIVO" and "null_distribution" in j["engine"]["missing_required_evidence"], (j["verdict_engine"], j["engine"]["missing_required_evidence"]))
        # Nula 12 aceita identidade RGB, mas não lava a violação cromática da franja contra A.
        aref12 = noisy(hard["A"], 12, 21); Aref12 = os.path.join(d, "aref12.png"); save_rgb(Aref12, aref12)
        O12 = os.path.join(d, "o12.png"); save_rgb(O12, engine_output(hard, aref12, hard["G_split"], 22, extra_noise=0))
        j, rc = run_audit(fx, "synth_hard_01", O12, Gs, a_ref=Aref12)
        c.ok("B03_nula12_nao_substitui_A_nas_metricas", j["verdict_engine"] == "FAIL" and j["tol_engine"] == 12 and j["engine"]["protected_pixel_identity"] == 1.0 and j["engine"]["causes"] == ["contact_fringe_violation:luminance_or_chroma"], (j["verdict_engine"], j["engine"]["causes"], j["tol_engine"]))
        j, rc = run_audit(fx, "synth_hard_01", O12, Gs, profile="minimal", extra=args_min)
        c.ok("B03_ruido12_minimal_tol4_FAIL_deriva", j["verdict_engine"] == "FAIL" and any(x.startswith(("background_drift", "body_reconstruction")) for x in j["engine"]["causes"]), j["engine"]["causes"])

        # B-05: franja C3 não isenta — sombra leve passa; pintura arbitrária reprova
        fr = (np.zeros((120, 80), bool)); fr[31:33, 24:56] = True; fr[87:89, 24:56] = True  # linhas acima/abaixo do tecido (dentro da franja de 2 px)
        base = perfect_output(hard, hard["G_split"], base=aref_h)
        shadow = base.copy(); shadow[fr] = np.clip(shadow[fr].astype(int) * 0.85, 0, 255)  # ΔL ≈ −6..−8
        Osh = os.path.join(d, "o_shadow.png"); save_rgb(Osh, shadow)
        j, rc = run_audit(fx, "synth_hard_01", Osh, Gs, a_ref=Aref_h)
        c.ok("B05_sombra_leve_na_franja_PASS", j["verdict_engine"] == "PASS" and j["engine"]["fringe_px"] > 0, (j["verdict_engine"], j["engine"]["causes"], j["engine"].get("fringe_delta_l_p95")))
        paint = base.copy(); paint[fr] = (0, 255, 0)
        Opt = os.path.join(d, "o_paint.png"); save_rgb(Opt, paint)
        j, rc = run_audit(fx, "synth_hard_01", Opt, Gs, a_ref=Aref_h)
        c.ok("B05_pintura_arbitraria_na_franja_FAIL", j["verdict_engine"] == "FAIL" and any(x.startswith("contact_fringe_violation") for x in j["engine"]["causes"]), j["engine"]["causes"])

        # B-06: split_by_garment_edge efetivamente julgado
        G_all = hard["G"] | hard["EL_ARM"]; Ga = os.path.join(d, "G_all.png"); save_mask(Ga, G_all)
        Oall = os.path.join(d, "o_all.png"); save_rgb(Oall, engine_output(hard, aref_h, G_all, 3))
        j, rc = run_audit(fx, "synth_hard_01", Oall, Ga, a_ref=Aref_h)
        c.ok("B06_tecido_sobre_parte_visivel_FAIL", j["verdict_engine"] == "FAIL" and any("split_edge_violation:fabric_over_visible_part" in x for x in j["engine"]["causes"]), j["engine"]["causes"])
        G_none = hard["G_split"] & ~hard["MC"]; Gn = os.path.join(d, "G_none.png"); save_mask(Gn, G_none)
        Onone = os.path.join(d, "o_none.png"); save_rgb(Onone, engine_output(hard, aref_h, G_none, 4))
        j, rc = run_audit(fx, "synth_hard_01", Onone, Gn, a_ref=Aref_h)
        c.ok("B06_must_cover_nao_coberto_FAIL", j["verdict_engine"] == "FAIL" and any("must_cover_not_covered" in x for x in j["engine"]["causes"]), j["engine"]["causes"])
        # sem máscaras split e sem adjudicação → INCONCLUSIVO; adjudicação cega no → FAIL; yes → PASS; não cega → INCONCLUSIVO
        j, rc = run_audit(fx, "synth_hard_nosplit", O_hard, Gs, a_ref=Aref_h)
        c.ok("B06_split_sem_referencia_INCONCLUSIVO", j["verdict_engine"] == "INCONCLUSIVO" and any(x.startswith("split_edge_reference") for x in j["engine"]["missing_required_evidence"]), (j["verdict_engine"], j["engine"]["missing_required_evidence"]))
        adj_no = make_adj(d, "adj_no_hard.json", "synth_hard_nosplit", O_hard, ADJ_NO); adj_yes = make_adj(d, "adj_yes_hard.json", "synth_hard_nosplit", O_hard, ADJ_YES)
        j, rc = run_audit(fx, "synth_hard_nosplit", O_hard, Gs, a_ref=Aref_h, extra=["--human-adjudication", adj_no])
        c.ok("B06_adjudicacao_cega_no_FAIL", j["verdict_engine"] == "FAIL" and any("split_edge_violation:human_blind" in x for x in j["engine"]["causes"]), j["engine"]["causes"])
        j, rc = run_audit(fx, "synth_hard_nosplit", O_hard, Gs, a_ref=Aref_h, extra=["--human-adjudication", adj_yes])
        c.ok("B06_adjudicacao_cega_yes_PASS", j["verdict_engine"] == "PASS" and j["engine"]["per_element"]["upper_arm_L"]["judged_by"] == "human_blind", (j["verdict_engine"], j["engine"]["per_element"]["upper_arm_L"], j["engine"]["missing_required_evidence"]))
        j, rc = run_audit(fx, "synth_hard_nosplit", O_hard, Gs, a_ref=Aref_h, extra=["--human-adjudication", make_adj(d, "adj_nb.json", "synth_hard_nosplit", O_hard, ADJ_YES, blind=False)])
        c.ok("B06_adjudicacao_nao_cega_INCONCLUSIVO", j["verdict_engine"] == "INCONCLUSIVO" and any("adjudication_invalid:not_blind" in x for x in j["engine"]["missing_required_evidence"]), (j["verdict_engine"], j["engine"]["missing_required_evidence"]))
        # L2: adjudicação sem catch trials / sem ligação à saída / de outra saída → INCONCLUSIVO, nunca PASS
        j, rc = run_audit(fx, "synth_hard_nosplit", O_hard, Gs, a_ref=Aref_h, extra=["--human-adjudication", make_adj(d, "adj_noct.json", "synth_hard_nosplit", O_hard, ADJ_YES, catch_trials_passed=False)])
        c.ok("L2_adjudicacao_sem_catch_trials_INCONCLUSIVO", j["verdict_engine"] == "INCONCLUSIVO" and any("catch_trials" in x for x in j["engine"]["missing_required_evidence"]), (j["verdict_engine"], j["engine"]["missing_required_evidence"]))
        j, rc = run_audit(fx, "synth_hard_nosplit", O_hard, Gs, a_ref=Aref_h, extra=["--human-adjudication", os.path.join(d, "adj_unbound.json")])
        c.ok("L2_adjudicacao_nao_ligada_a_saida_INCONCLUSIVO", j["verdict_engine"] == "INCONCLUSIVO" and any("output_sha256_mismatch" in x or "case_id_mismatch" in x for x in j["engine"]["missing_required_evidence"]), (j["verdict_engine"], j["engine"]["missing_required_evidence"]))
        j, rc = run_audit(fx, "synth_hard_nosplit", O_hard, Gs, a_ref=Aref_h, extra=["--human-adjudication", make_adj(d, "adj_other.json", "synth_hard_nosplit", O_easy, ADJ_YES)])
        c.ok("L2_adjudicacao_de_outra_saida_INCONCLUSIVO", j["verdict_engine"] == "INCONCLUSIVO" and any("output_sha256_mismatch" in x for x in j["engine"]["missing_required_evidence"]), (j["verdict_engine"], j["engine"]["missing_required_evidence"]))

        # B-09: consistência — BAND_MIN pequeno (1 % do canvas) com metade fora do permitido → INCONCLUSIVO:annotation_inconsistent
        m = build_masks(True)
        small = np.zeros((120, 80), bool); small[100:110, 30:38] = True  # 80 px: 40 dentro de nada permitido (fundo) — totalmente fora
        small_half = np.zeros((120, 80), bool); small_half[80:90, 30:38] = True  # rows 80:85 dentro de BMAXB/BC (30:90)… ajustar: 80:90 → dentro até 90 → use 85:95
        small_half = np.zeros((120, 80), bool); small_half[85:95, 30:38] = True  # 85:90 dentro (40 px), 90:95 fora (40 px) → 50 % fora
        for n, arr in (("BMIN_small", small_half),):
            save_mask(os.path.join(d, f"{n}.png"), arr)
        args_small = ["--front-occluders", F["hard_FO.png"], "--band-min", os.path.join(d, "BMIN_small.png"), "--band-max-body", F["hard_BMAXB.png"], "--free-space", F["hard_FS.png"],
                      "--uncertain", F["hard_UNC.png"], "--body-coverable", F["hard_BC.png"], "--protected", F["hard_PR.png"], "--tol-engine", "4"]
        j, rc = run_audit(fx, "synth_hard_01", O_hard, Gs, profile="minimal", extra=args_small)
        q = j["engine"]["reference_quality"]
        c.ok("B09_BAND_MIN_pequeno_inconsistente_detectado", j["verdict_engine"] == "INCONCLUSIVO" and "annotation_inconsistent" in j["engine"]["inconclusive"] and 0.4 < q.get("band_min_outside_allowed_frac", 0) < 0.6,
             (j["verdict_engine"], q))

        # B-08: congelamento — A trocada após o freeze → FAIL:frozen_reference_mismatch antes de avaliar
        A_sw = os.path.join(d, "A_swapped.png"); Asw = hard["A"].copy(); Asw[100, 70] = (0, 0, 0); save_rgb(A_sw, Asw)
        j, rc = run_audit(fx, "synth_hard_01", O_hard, Gs, a_ref=Aref_h, a=A_sw)
        c.ok("B08_A_trocada_FAIL_frozen_mismatch", j["verdict_engine"] == "FAIL:frozen_reference_mismatch" and rc == 1 and "engine" not in j and any(x.startswith("input_sha256:A") for x in j["frozen_reference_check"]["mismatches"]),
             (j["verdict_engine"], j["frozen_reference_check"]["mismatches"]))
        # arquivo congelado (máscara) alterado no disco após o freeze
        bak = open(F["hard_FO.png"], "rb").read()
        save_mask(F["hard_FO.png"], hard["FO"] | (np.arange(120)[:, None] == 119))
        j, rc = run_audit(fx, "synth_hard_01", O_hard, Gs, a_ref=Aref_h)
        c.ok("B08_mascara_alterada_FAIL_frozen_mismatch", j["verdict_engine"] == "FAIL:frozen_reference_mismatch" and any("sha256:" in x for x in j["frozen_reference_check"]["mismatches"]), j["frozen_reference_check"]["mismatches"][:3])
        open(F["hard_FO.png"], "wb").write(bak)
        # PREREG alterado após o freeze
        pr_bak = open(fx["prereg"], encoding="utf-8").read(); open(fx["prereg"], "a", encoding="utf-8").write("\n(limiar alterado depois do run)\n")
        j, rc = run_audit(fx, "synth_hard_01", O_hard, Gs, a_ref=Aref_h)
        c.ok("B08_PREREG_alterado_FAIL_frozen_mismatch", j["verdict_engine"] == "FAIL:frozen_reference_mismatch" and any(x.startswith("sha256:prereg") for x in j["frozen_reference_check"]["mismatches"]), j["frozen_reference_check"]["mismatches"][:3])
        open(fx["prereg"], "w", encoding="utf-8").write(pr_bak)
        # manifesto alterado após o freeze
        mf_bak = open(fx["manifest"], encoding="utf-8").read(); open(fx["manifest"], "a", encoding="utf-8").write("\n")
        j, rc = run_audit(fx, "synth_hard_01", O_hard, Gs, a_ref=Aref_h)
        c.ok("B08_manifesto_alterado_FAIL_frozen_mismatch", j["verdict_engine"] == "FAIL:frozen_reference_mismatch" and any(x.startswith("sha256:manifest") for x in j["frozen_reference_check"]["mismatches"]), j["frozen_reference_check"]["mismatches"][:3])
        open(fx["manifest"], "w", encoding="utf-8").write(mf_bak)
        j, rc = run_audit(fx, "synth_hard_01", O_hard, Gs, a_ref=Aref_h)
        c.ok("B08_restaurado_volta_a_PASS", j["verdict_engine"] == "PASS", j["verdict_engine"])
        # --prereg é arquivo (sha calculado internamente); string --prereg-sha não existe mais
        r = subprocess.run([sys.executable, AUDIT, "--a", F["hard_A.png"], "--o-engine", O_hard, "--garment-mask", Gs, "--prereg-sha", "abc"], capture_output=True, text=True)
        c.ok("B08_prereg_sha_string_rejeitado", r.returncode == 2 and "unrecognized" in r.stderr, r.stderr.strip()[-120:])

        # controles do auditor que continuam valendo
        GB = os.path.join(d, "G_fake.png"); save_mask(GB, hard["BMIN_split"])
        j, rc = run_audit(fx, "synth_hard_01", F["hard_A.png"], GB, a_ref=Aref_h)
        c.ok("CTRL_identity_output_FAIL_garment_not_created", j["verdict_engine"] == "FAIL" and any(x.startswith("garment_not_created") for x in j["engine"]["causes"]), j["engine"]["causes"])
        G3 = hard["G_split"] | hard["FO"]; G3p = os.path.join(d, "G3.png"); save_mask(G3p, G3)
        O3 = os.path.join(d, "o3.png"); save_rgb(O3, engine_output(hard, aref_h, G3, 5))
        j, rc = run_audit(fx, "synth_hard_01", O3, G3p, a_ref=Aref_h)
        c.ok("CTRL_tecido_sobre_oclusor_FAIL", j["verdict_engine"] == "FAIL" and any(x.startswith(("bad_occlusion", "visibility_violation")) for x in j["engine"]["causes"]), j["engine"]["causes"])
        j, rc = run_audit(fx, "synth_hard_01", O_hard, Gs, a_ref=Aref_h, with_kp=False, extra=["--keypoints-a", os.path.join(d, "kpA.json"), "--keypoints-engine", os.path.join(d, "kpE_dup.json")])
        c.ok("CTRL_membro_duplicado_FAIL", j["verdict_engine"] == "FAIL" and "duplicate_limb" in j["engine"]["causes"], j["engine"]["causes"])
        allowed = (hard["BMIN_split"] | hard["BMAXB"] | hard["FS"] | hard["UNC"]) & ~hard["MV"] & ~(hard["EL_ARM"] & ~hard["MC"] & ~hard["MV"])
        G6 = os.path.join(d, "G6.png"); save_mask(G6, allowed)
        O6 = os.path.join(d, "o6.png"); save_rgb(O6, engine_output(hard, aref_h, allowed, 6))
        j, rc = run_audit(fx, "synth_hard_01", O6, G6, a_ref=Aref_h)
        c.ok("CTRL_envelope_cheio_nao_e_FAIL_do_motor", j["verdict_engine"] == "INCONCLUSIVO" and "envelope_too_tight_probable" in j["engine"]["inconclusive"] and not j["engine"]["causes"],
             (j["verdict_engine"], j["engine"]["causes"], j["engine"]["inconclusive"]))

        # B-01/B-02: estado de oclusão desconhecido (minimal, sem manifesto, sem FO, sem flag) → INCONCLUSIVO; com --occlusion-none → PASS
        args_easy = ["--band-min", F["easy_BMIN.png"], "--band-max-body", F["easy_BMAXB.png"], "--free-space", F["easy_FS.png"], "--uncertain", F["easy_UNC.png"],
                     "--body-coverable", F["easy_BC.png"], "--protected", F["easy_PR.png"], "--tol-engine", "4"]
        j, rc = run_audit(fx, "synth_easy_01", O_easy, Ge, profile="minimal", extra=args_easy)
        c.ok("B01_minimal_oclusao_desconhecida_INCONCLUSIVO", j["verdict_engine"] == "INCONCLUSIVO" and "occlusion_status_unknown" in j["engine"]["missing_required_evidence"], (j["verdict_engine"], j["engine"]["missing_required_evidence"]))
        j, rc = run_audit(fx, "synth_easy_01", O_easy, Ge, profile="minimal", extra=args_easy + ["--occlusion-none"])
        c.ok("B01_minimal_occlusion_none_PASS", j["verdict_engine"] == "PASS" and j["engine"]["evidence"].get("front_occluders") == "NOT_APPLICABLE", (j["verdict_engine"], j["engine"]["causes"], j["engine"]["missing_required_evidence"]))
        # FO não vazia passada num caso cujo manifesto declara none → contradição de anotação
        j, rc = run_audit(fx, "synth_easy_01", O_easy, Ge, a_ref=Aref_e, extra=["--front-occluders", F["hard_FO.png"]])
        c.ok("B01_FO_em_caso_none_INCONCLUSIVO_anotacao", j["verdict_engine"] == "INCONCLUSIVO" and "annotation_inconsistent" in j["engine"]["inconclusive"], (j["verdict_engine"], j["engine"]["inconclusive"]))
        # B-08b: layer_graph explícito com máscara diferente da congelada → FAIL:frozen_reference_mismatch
        lg = [{"element": "hand_R", "relation": "front_certain", "mask": F["hard_FS.png"]}, {"element": "torso_front_skin", "relation": "behind_must_cover", "mask": F["hard_TORSO.png"]},
              {"element": "upper_arm_L", "relation": "split_by_garment_edge", "mask": F["hard_EL_ARM.png"], "split_must_cover_mask": F["hard_MC.png"], "split_must_stay_visible_mask": F["hard_MV.png"]}]
        lgp = os.path.join(d, "lg_foreign.json"); json.dump(lg, open(lgp, "w"))
        j, rc = run_audit(fx, "synth_hard_01", O_hard, Gs, a_ref=Aref_h, extra=["--layer-graph", lgp])
        c.ok("B08_layer_graph_com_mascara_estranha_FAIL_frozen", j["verdict_engine"] == "FAIL:frozen_reference_mismatch" and any("layer_graph:hand_R" in x for x in j["frozen_reference_check"]["mismatches"]), j["frozen_reference_check"]["mismatches"][:3])
        lg[0]["mask"] = F["hard_EL_hand_R.png"]; json.dump(lg, open(lgp, "w"))
        j, rc = run_audit(fx, "synth_hard_01", O_hard, Gs, a_ref=Aref_h, extra=["--layer-graph", lgp])
        c.ok("B08_layer_graph_explicito_congelado_PASS", j["verdict_engine"] == "PASS", (j["verdict_engine"], j.get("frozen_reference_check", {}).get("mismatches")))
        # B-03b: nula não credível (A_ref = O com corpo reconstruído → tol enorme) → INCONCLUSIVO, não PASS
        fake = os.path.join(d, "aref_fake.png"); fk = noisy(hard["A"], 40, 31); save_rgb(fake, fk)
        Ofk = os.path.join(d, "o_fake.png"); save_rgb(Ofk, engine_output(hard, fk, hard["G_split"], 32))
        j, rc = run_audit(fx, "synth_hard_01", Ofk, Gs, a_ref=fake)
        c.ok("B03_nula_nao_credivel_INCONCLUSIVO", j["verdict_engine"] == "INCONCLUSIVO:null_stats_inconsistent_with_a_ref" and rc == 3, (j["verdict_engine"], j.get("flags")))
        # B-03c: composto sem PROTECTED → INCONCLUSIVO (nunca PASS); 16 bits / alfa → INCONCLUSIVO:format_mismatch
        j, rc = run_audit(fx, "synth_hard_01", O_hard, Gs, profile="minimal", with_occ=True, with_kp=True, o_composed=Oc_ok,
                          extra=[a for a in args_min if a != F["hard_PR.png"] and a != "--protected"])
        c.ok("B03_composto_sem_PROTECTED_nao_PASS", j["verdict_composed"] == "INCONCLUSIVO" and "protected" in j["composed"]["missing_required_evidence"], (j["verdict_composed"], j["composed"]["missing_required_evidence"]))
        from PIL import Image as _I
        im16 = _I.fromarray((perfect_output(hard, hard["G_split"])[..., 0].astype(np.uint16) * 257).astype(np.int32)).convert("I;16"); p16 = os.path.join(d, "o_comp16.png"); im16.save(p16)
        j, rc = run_audit(fx, "synth_hard_01", O_hard, Gs, a_ref=Aref_h, o_composed=p16)
        c.ok("B03_composto_16bits_INCONCLUSIVO_format", str(j["verdict_composed"]).startswith("INCONCLUSIVO:format_mismatch") and rc == 3, (j["verdict_composed"], j.get("format_issue")))
        rgba = np.dstack([perfect_output(hard, hard["G_split"]), np.full((120, 80), 255, np.uint8)]); rgba[0, 0, 3] = 0; pa = os.path.join(d, "o_comp_rgba.png"); _I.fromarray(rgba, "RGBA").save(pa)
        j, rc = run_audit(fx, "synth_hard_01", O_hard, Gs, a_ref=Aref_h, o_composed=pa)
        c.ok("B03_composto_RGBA_INCONCLUSIVO_format", str(j["verdict_composed"]).startswith("INCONCLUSIVO:format_mismatch"), (j["verdict_composed"], j.get("format_issue")))
        nsp = os.path.join(d, "null_bad.json"); open(nsp, "w").write("{}")
        j, rc = run_audit(fx, "synth_hard_01", O_hard, Gs, extra=["--null-stats", nsp])
        c.ok("B03_null_stats_invalido_INCONCLUSIVO", str(j["verdict_engine"]).startswith("INCONCLUSIVO:null_stats_invalid") and rc == 3, j["verdict_engine"])
        # L1 (lente adversarial): oclusão declarada sem front_certain NÃO é NOT_APPLICABLE → INCONCLUSIVO:annotation_inconsistent
        j, rc = run_audit(fx, "synth_easy_badoccl", O_easy, Ge, a_ref=Aref_e)
        c.ok("L1_oclusao_declarada_sem_front_certain_nao_PASS", j["verdict_engine"] == "INCONCLUSIVO" and "annotation_inconsistent" in j["engine"]["inconclusive"] and j["engine"]["evidence"].get("front_occluders") != "NOT_APPLICABLE",
             (j["verdict_engine"], j["engine"]["inconclusive"], j["engine"]["evidence"]))
        # L1: layer_graph explícito que omite o elemento split congelado, ou o rotula de outra relação → FAIL:frozen_reference_mismatch
        lg2 = [e for e in lg if e["element"] != "upper_arm_L"]; lgp2 = os.path.join(d, "lg_drop.json"); json.dump(lg2, open(lgp2, "w"))
        j, rc = run_audit(fx, "synth_hard_01", Oall, Ga, a_ref=Aref_h, extra=["--layer-graph", lgp2])
        c.ok("L1_layer_graph_omite_elemento_congelado_FAIL_frozen", j["verdict_engine"] == "FAIL:frozen_reference_mismatch" and any("elemento_congelado_omitido:upper_arm_L" in x for x in j["frozen_reference_check"]["mismatches"]), j["frozen_reference_check"]["mismatches"][:3])
        lg3 = json.loads(json.dumps(lg)); [e for e in lg3 if e["element"] == "upper_arm_L"][0]["relation"] = "behind_may_cover"; lgp3 = os.path.join(d, "lg_relabel.json"); json.dump(lg3, open(lgp3, "w"))
        j, rc = run_audit(fx, "synth_hard_01", Oall, Ga, a_ref=Aref_h, extra=["--layer-graph", lgp3])
        c.ok("L1_layer_graph_relacao_divergente_FAIL_frozen", j["verdict_engine"] == "FAIL:frozen_reference_mismatch" and any("relacao_divergente" in x for x in j["frozen_reference_check"]["mismatches"]), j["frozen_reference_check"]["mismatches"][:3])
        lg4 = json.loads(json.dumps(lg)); el4 = [e for e in lg4 if e["element"] == "upper_arm_L"][0]; el4.pop("split_must_cover_mask"); el4.pop("split_must_stay_visible_mask"); lgp4 = os.path.join(d, "lg_nosplit.json"); json.dump(lg4, open(lgp4, "w"))
        j, rc = run_audit(fx, "synth_hard_01", Oall, Ga, a_ref=Aref_h, extra=["--layer-graph", lgp4, "--human-adjudication", make_adj(d, "adj_all.json", "synth_hard_01", Oall, ADJ_YES)])
        c.ok("L1_layer_graph_omite_mascaras_split_FAIL_frozen", j["verdict_engine"] == "FAIL:frozen_reference_mismatch" and any("mascara_congelada_omitida" in x for x in j["frozen_reference_check"]["mismatches"]), j["frozen_reference_check"]["mismatches"][:3])
        # L1: keypoints vazios não são evidência
        kpv = os.path.join(d, "kp_void.json"); json.dump({"counts": {}}, open(kpv, "w"))
        j, rc = run_audit(fx, "synth_hard_01", O_hard, Gs, a_ref=Aref_h, with_kp=False, extra=["--keypoints-a", kpv, "--keypoints-engine", kpv])
        c.ok("L1_keypoints_vazios_INCONCLUSIVO", j["verdict_engine"] == "INCONCLUSIVO" and any(x.startswith("keypoints") for x in j["engine"]["missing_required_evidence"]), (j["verdict_engine"], j["engine"]["missing_required_evidence"]))
        kpz = os.path.join(d, "kp_zero.json"); json.dump({"hands": [], "forearms": [], "counts": {"hands": 0, "forearms": 0}}, open(kpz, "w"))
        j, rc = run_audit(fx, "synth_hard_01", O_hard, Gs, a_ref=Aref_h, with_kp=False, extra=["--keypoints-a", kpz, "--keypoints-engine", kpz])
        c.ok("L1_keypoints_zero_deteccoes_INCONCLUSIVO", j["verdict_engine"] == "INCONCLUSIVO" and any(x.startswith("keypoints") for x in j["engine"]["missing_required_evidence"]), (j["verdict_engine"], j["engine"]["missing_required_evidence"]))
        # L2: largura da franja vem do manifesto; CLI diferente → FAIL:frozen_reference_mismatch
        j, rc = run_audit(fx, "synth_hard_01", O_hard, Gs, a_ref=Aref_h, extra=["--contact-fringe-px", "40"])
        c.ok("L2_franja_cli_diferente_do_congelado_FAIL_frozen", j["verdict_engine"] == "FAIL:frozen_reference_mismatch" and any(x.startswith("contact_fringe_px") for x in j["frozen_reference_check"]["mismatches"]), j["frozen_reference_check"]["mismatches"][:2])
        c.ok("L2_franja_resolvida_do_manifesto", run_audit(fx, "synth_hard_01", O_hard, Gs, a_ref=Aref_h)[0]["thresholds"]["contact_fringe_px"] == 2, "")
        # L2: franja larga (minimal) não lava reconstrução: dilui a região de identidade → INCONCLUSIVO, nunca PASS
        drift = engine_output(hard, aref_h, hard["G_split"], 41).astype(int); mask_out = ~hard["G_split"] & ~hard["PR"]; drift[mask_out] = np.clip(drift[mask_out] * 0.85, 0, 255)
        Odr = os.path.join(d, "o_drift.png"); save_rgb(Odr, drift.astype(np.uint8))
        args_min40 = [a for a in args_min] + ["--contact-fringe-px", "40", "--a-ref", Aref_h, "--a-ref-full-canvas"]
        args_min40 = [a for a in args_min40 if a not in ("--tol-engine", "4")]
        j, rc = run_audit(fx, "synth_hard_01", Odr, Gs, profile="minimal", extra=args_min40)
        c.ok("L2_franja_larga_nao_lava_deriva", j["verdict_engine"] != "PASS" and ("identity_region_diluted_by_fringe" in j["engine"]["missing_required_evidence"] or j["verdict_engine"] == "FAIL"), (j["verdict_engine"], j["engine"]["missing_required_evidence"], j["engine"].get("fraction_excluded_by_fringe")))
        j, rc = run_audit(fx, "synth_hard_01", Odr, Gs, a_ref=Aref_h)
        c.ok("L2_deriva_com_franja_congelada_FAIL", j["verdict_engine"] == "FAIL", (j["verdict_engine"], j["engine"]["causes"][:3]))
        # L2: sombra de contato sobre a parte visível do braço dentro da franja → PASS (regras da franja e do split não se contradizem)
        sh = perfect_output(hard, hard["G_split"], base=aref_h).astype(int); fr_mv = (hard["MV"] | (hard["EL_ARM"] & ~hard["MC"] & ~hard["MV"])) & (np.zeros((120, 80), bool) | True)
        ring = np.zeros((120, 80), bool); ring[:, :] = False
        from occupancy_audit import dilate as _dil
        ring = _dil(hard["G_split"], 2) & ~hard["G_split"] & (hard["MV"] | (hard["EL_ARM"] & ~hard["MC"] & ~hard["MV"]))
        sh[ring] = np.clip(sh[ring] * 0.85, 0, 255); Osh2 = os.path.join(d, "o_shadow_arm.png"); save_rgb(Osh2, sh.astype(np.uint8))
        j, rc = run_audit(fx, "synth_hard_01", Osh2, Gs, a_ref=Aref_h)
        c.ok("L2_sombra_sobre_braco_na_franja_PASS", j["verdict_engine"] == "PASS" and ring.sum() > 0, (j["verdict_engine"], j["engine"]["causes"], int(ring.sum())))
        # L2: máscara 0/1 → INCONCLUSIVO:mask_not_binary com JSON e exit 3; tamanho errado → INCONCLUSIVO:grid_mismatch
        bad01 = os.path.join(d, "bmin01.png"); Image_ = __import__("PIL.Image", fromlist=["Image"]); Image_.fromarray(hard["BMIN_split"].astype(np.uint8)).save(bad01)
        a01 = [a for a in args_min]; a01[a01.index(F["hard_BMIN_split.png"])] = bad01
        j, rc = run_audit(fx, "synth_hard_01", O_hard, Gs, profile="minimal", extra=a01)
        c.ok("L2_mascara_0_1_INCONCLUSIVO_com_JSON", str(j["verdict_engine"]).startswith("INCONCLUSIVO:mask_not_binary") and rc == 3, (j["verdict_engine"], j.get("mask_error")))
        small = os.path.join(d, "bmin_small.png"); save_mask(small, np.zeros((60, 40), bool))
        a_sm = [a for a in args_min]; a_sm[a_sm.index(F["hard_BMIN_split.png"])] = small
        j, rc = run_audit(fx, "synth_hard_01", O_hard, Gs, profile="minimal", extra=a_sm)
        c.ok("L2_mascara_tamanho_errado_INCONCLUSIVO_com_JSON", str(j["verdict_engine"]).startswith("INCONCLUSIVO:grid_mismatch") and rc == 3, (j["verdict_engine"], j.get("mask_error")))
        # L2: anotação contraditória (BAND_MIN ∩ must_stay_visible) → INCONCLUSIVO, não FAIL do motor
        a_bm = [a for a in args_min]; a_bm[a_bm.index(F["hard_BMIN_split.png"])] = F["hard_BMIN.png"]
        lg_ok = [{"element": "hand_R", "relation": "front_certain", "mask": F["hard_EL_hand_R.png"]}, {"element": "torso_front_skin", "relation": "behind_must_cover", "mask": F["hard_TORSO.png"]},
                 {"element": "upper_arm_L", "relation": "split_by_garment_edge", "mask": F["hard_EL_ARM.png"], "split_must_cover_mask": F["hard_MC.png"], "split_must_stay_visible_mask": F["hard_MV.png"]}]
        lgok = os.path.join(d, "lg_ok.json"); json.dump(lg_ok, open(lgok, "w"))
        j, rc = run_audit(fx, "synth_hard_01", O_hard, Gs, profile="minimal", extra=a_bm + ["--layer-graph", lgok])
        c.ok("L2_BMIN_sobre_parte_visivel_INCONCLUSIVO", j["verdict_engine"] == "INCONCLUSIVO" and any("must_stay_visible" in x for x in j["engine"]["reference_quality"].get("annotation_inconsistent", [])), (j["verdict_engine"], j["engine"]["reference_quality"]))
        # L2: textura apagada na franja estruturada → FAIL structure/structure_erased
        tex = build_masks(True); texA = tex["A"].copy(); rng2 = np.random.default_rng(7)
        ringT = _dil(tex["G_split"], 2) & ~tex["G_split"] & ~tex["FO"] & ~tex["PR"]
        texA[ringT] = np.clip(texA[ringT].astype(int) + rng2.integers(-25, 26, texA[ringT].shape), 0, 255).astype(np.uint8)
        At = os.path.join(d, "A_tex.png"); save_rgb(At, texA); Oer = perfect_output(tex, tex["G_split"], base=texA).copy(); Oer[ringT] = (200, 200, 200)
        Oerp = os.path.join(d, "o_erased.png"); save_rgb(Oerp, Oer)
        j, rc = run_audit(fx, "synth_hard_01", Oerp, Gs, profile="minimal", a=At, extra=[x for x in args_min if x not in ("--tol-engine", "4")] + ["--tol-engine", "4"])
        c.ok("L2_textura_apagada_na_franja_FAIL", j["verdict_engine"] == "FAIL" and any(x.startswith("contact_fringe_violation:structure") for x in j["engine"]["causes"]), j["engine"]["causes"][:4])
    return c.done("test_occupancy_audit")


if __name__ == "__main__":
    sys.exit(main())
