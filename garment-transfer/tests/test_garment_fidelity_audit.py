#!/usr/bin/env python3
"""Testes do auditor de identidade da peça B (evidência iii). Rodar: python tests/test_garment_fidelity_audit.py"""
import json, os, subprocess, sys, tempfile
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _fixtures import build_case_dir, perfect_output, engine_output, noisy, save_rgb, save_mask, Checker, FIDELITY, GARMENT_RGB  # noqa: E402


def run(fx, case_id, extra=(), profile="g0", a=None, b=None):
    F = fx["files"]
    args = [sys.executable, FIDELITY, "--profile", profile, "--a", a or F["hard_A.png"], "--b", b or F["hard_B.png"]]
    if profile == "g0":
        args += ["--manifest", fx["manifest"], "--case-id", case_id, "--data-root", fx["d"], "--prereg", fx["prereg"], "--freeze", fx["freeze"], "--roles", fx["roles"]]
    args += list(extra)
    r = subprocess.run(args, capture_output=True, text=True)
    assert r.returncode in (0, 1, 3), r.stderr[-1500:]
    return json.loads(r.stdout), r.returncode


def main():
    c = Checker()
    with tempfile.TemporaryDirectory() as d:
        fx = build_case_dir(d); hard = fx["hard"]; F = fx["files"]
        Gs = os.path.join(d, "G_split.png"); save_mask(Gs, hard["G_split"])
        O = os.path.join(d, "o_hard.png"); save_rgb(O, engine_output(hard, hard["A"], hard["G_split"], 1))
        chroma = ["--o-engine", O, "--garment-mask", Gs]
        adj_yes, adj_no, adj_nb = (os.path.join(d, f) for f in ("adj_yes.json", "adj_no.json", "adj_notblind.json"))

        j, rc = run(fx, "synth_hard_01", chroma + ["--adjudication", adj_yes])
        c.ok("FID_completo_PASS", j["verdict"] == "PASS" and rc == 0 and j["gate_eligible"] and j["evidence"].get("chroma") == "PRESENT", (j["verdict"], j["causes"], j["missing_required_evidence"], j.get("chroma")))
        j, rc = run(fx, "synth_hard_01", chroma)
        c.ok("FID_sem_adjudicacao_INCONCLUSIVO", j["verdict"] == "INCONCLUSIVO" and "blind_adjudication" in j["missing_required_evidence"], (j["verdict"], j["missing_required_evidence"]))
        j, rc = run(fx, "synth_hard_01", chroma + ["--adjudication", adj_no])
        c.ok("FID_categoria_no_FAIL_wrong_category", j["verdict"] == "FAIL" and "wrong_category" in j["causes"], j["causes"])
        j, rc = run(fx, "synth_hard_01", chroma + ["--adjudication", adj_nb])
        c.ok("FID_adjudicacao_nao_cega_INCONCLUSIVO", j["verdict"] == "INCONCLUSIVO" and "adjudication_not_blind" in j["missing_required_evidence"], (j["verdict"], j["missing_required_evidence"]))
        j, rc = run(fx, "synth_hard_01", ["--adjudication", adj_yes])
        c.ok("FID_g0_sem_cromaticidade_INCONCLUSIVO", j["verdict"] == "INCONCLUSIVO" and any(x.startswith("chroma_evidence") for x in j["missing_required_evidence"]), (j["verdict"], j["missing_required_evidence"]))
        # peça em O′ vermelha vs B azul → FAIL identidade (B congelada e conferida por sha)
        Ored = perfect_output(hard, hard["G_split"]).copy(); Ored[hard["G_split"]] = (200, 40, 40); Ored_p = os.path.join(d, "o_red.png"); save_rgb(Ored_p, Ored)
        j, rc = run(fx, "synth_hard_01", ["--o-engine", Ored_p, "--garment-mask", Gs, "--adjudication", adj_yes])
        c.ok("FID_cromaticidade_divergente_FAIL", j["verdict"] == "FAIL" and any(x.startswith("garment_identity") for x in j["causes"]), (j["causes"], j.get("chroma", {}).get("centroid_distance_ab")))
        # atributos com placeholder → INCONCLUSIVO (perfil minimal com --attributes)
        attrs = [{"name": "category", "value": "A PREENCHER PELO ANOTADOR", "state": "unknown", "expected_visible_in_O": "yes"}]
        ap = os.path.join(d, "attrs_ph.json"); json.dump(attrs, open(ap, "w"))
        j, rc = run(fx, "synth_hard_01", ["--attributes", ap, "--adjudication", adj_yes] + chroma + ["--b-garment-mask", F["hard_BG.png"]], profile="minimal")
        c.ok("FID_atributos_placeholder_INCONCLUSIVO", j["verdict"] == "INCONCLUSIVO" and any(x.startswith("attributes_not_frozen") for x in j["missing_required_evidence"]), (j["verdict"], j["missing_required_evidence"]))
        # B trocada após o freeze → FAIL:frozen_reference_mismatch
        Bsw = hard["B"].copy(); Bsw[0, 0] = (1, 2, 3); Bp = os.path.join(d, "B_swapped.png"); save_rgb(Bp, Bsw)
        j, rc = run(fx, "synth_hard_01", chroma + ["--adjudication", adj_yes], b=Bp)
        c.ok("FID_B_trocada_FAIL_frozen_mismatch", j["verdict"] == "FAIL:frozen_reference_mismatch" and any(x.startswith("input_sha256:B") for x in j["frozen_reference_check"]["mismatches"]), j["frozen_reference_check"]["mismatches"])
        c.ok("FID_provenance_registrada", all(j["provenance"].get(k) for k in ("manifest_sha256", "prereg_sha256", "freeze_sha256")), j["provenance"])
    return c.done("test_garment_fidelity_audit")


if __name__ == "__main__":
    sys.exit(main())
