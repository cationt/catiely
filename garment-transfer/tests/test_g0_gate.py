#!/usr/bin/env python3
"""Testes do agregador do Gate G0 (regras pré-registradas; 6 casos core congelados). Rodar: python tests/test_g0_gate.py"""
import json, os, subprocess, sys, tempfile
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _fixtures import build_case_dir, run_audit, perfect_output, engine_output, noisy, save_rgb, save_mask, Checker, GATE, FIDELITY, make_adj, ADJ_YES, ADJ_NO  # noqa: E402

CORE = ["synth_easy_01", "synth_core_a", "synth_hard_01", "synth_core_b", "synth_core_c", "synth_core_d"]


def fid(fx, case_id, o, g, adj, out):
    F = fx["files"]; kind = "easy" if case_id.startswith("synth_easy") else "hard"
    r = subprocess.run([sys.executable, FIDELITY, "--profile", "g0", "--a", F[f"{kind}_A.png"], "--b", F[f"{kind}_B.png"], "--manifest", fx["manifest"], "--case-id", case_id,
                        "--data-root", fx["d"], "--prereg", fx["prereg"], "--freeze", fx["freeze"], "--roles", fx["roles"], "--allow-dirty-freeze", "--o-engine", o, "--garment-mask", g,
                        "--adjudication", adj, "--json-out", out], capture_output=True, text=True)
    assert r.returncode in (0, 1, 3), r.stderr[-800:]


def gate(fx, index_path, extra=()):
    r = subprocess.run([sys.executable, GATE, "--roles", fx["roles"], "--freeze", fx["freeze"], "--manifest", fx["manifest"], "--prereg", fx["prereg"], "--index", index_path, "--allow-dirty-freeze", *extra],
                       capture_output=True, text=True)
    assert r.returncode in (0, 1, 3), r.stderr[-800:]
    return json.loads(r.stdout), r.returncode


def main():
    c = Checker()
    with tempfile.TemporaryDirectory() as d:
        fx = build_case_dir(d); hard, easy = fx["hard"], fx["easy"]; F = fx["files"]
        Gs = os.path.join(d, "G_split.png"); save_mask(Gs, hard["G_split"]); Ge = os.path.join(d, "G_easy.png"); save_mask(Ge, easy["G"])
        GB = os.path.join(d, "G_fake.png"); save_mask(GB, hard["BMIN_split"])
        aref_h = noisy(hard["A"], 3, 11); Aref_h = os.path.join(d, "aref_h.png"); save_rgb(Aref_h, aref_h)
        aref_e = noisy(easy["A"], 3, 12); Aref_e = os.path.join(d, "aref_e.png"); save_rgb(Aref_e, aref_e)
        runs = os.path.join(d, "runs"); os.makedirs(runs)

        def produce(case_id, seed, mode="pass"):
            kind = "easy" if case_id.startswith("synth_easy") else "hard"; m = easy if kind == "easy" else hard; G = Ge if kind == "easy" else Gs
            o = os.path.join(runs, f"{case_id}_s{seed}.png")
            aref = aref_e if kind == "easy" else aref_h
            if mode == "creation_fail":
                save_rgb(o, noisy(aref, 1, seed)); g = GB if kind == "hard" else Ge
            else:
                save_rgb(o, engine_output(m, aref, m["G_split"] if kind == "hard" else None, seed)); g = G
            occ = os.path.join(runs, f"{case_id}_s{seed}.occ.json"); fdj = os.path.join(runs, f"{case_id}_s{seed}.fid.json")
            extra = ["--json-out", occ]
            if mode == "composed_fail":
                oc = perfect_output(m, m["G_split"] if kind == "hard" else None).copy(); oc[2, 2] = np.clip(oc[2, 2].astype(int) + 5, 0, 255); ocp = os.path.join(runs, f"{case_id}_s{seed}_comp.png"); save_rgb(ocp, oc)
                extra += ["--o-composed", ocp]
            run_audit(fx, case_id, o, g, a_ref=(Aref_e if kind == "easy" else Aref_h), extra=extra, with_occ=(mode != "missing_occ"))
            adj = make_adj(runs, f"{case_id}_s{seed}.adj.json", case_id, o, ADJ_NO if mode == "fid_fail" else ADJ_YES)
            fid(fx, case_id, o, g, adj, fdj)
            return {"case_id": case_id, "seed": seed, "occupancy": occ, "fidelity": fdj}

        def write_index(entries, name):
            p = os.path.join(d, name); json.dump(entries, open(p, "w")); return p

        # 1. tudo PASS → gate PASS; progressão permitida
        idx_all = [produce(cid, s) for cid in CORE for s in (1, 2, 3)] + [produce("synth_hard_nosplit", 1)]
        j, rc = gate(fx, write_index(idx_all, "idx_all.json"))
        c.ok("GATE_6x3_PASS", j["verdict"] == "PASS" and rc == 0 and j["core_summary"]["n_pass"] == 6, (j["verdict"], j["verdict_reason"], j["integrity"][:3]))
        c.ok("GATE_nao_core_reportado_nao_contado", "synth_hard_nosplit" in j["non_core"] and j["non_core"]["synth_hard_nosplit"]["role"] == "replication", list(j["non_core"].keys()))
        c.ok("GATE_progressao_permitida", all(v["allowed"] for v in j["progression"].values()), j["progression"])
        no_freeze = dict(fx, freeze=os.path.join(d, "missing_FREEZE.json"))
        j, rc = gate(no_freeze, write_index(idx_all, "idx_no_freeze.json"))
        c.ok("NULL1_gate_sem_FREEZE_INCONCLUSIVO", rc == 3 and j["verdict"] == "INCONCLUSIVO" and
             any(x.startswith("ausente:freeze") for x in j["integrity"]), j["integrity"][:2])
        # Relatórios legados/cross-check isolado e hashes não congelados não contornam a nula normativa.
        sample = idx_all[0]
        for mode in ("old_a_ref", "unknown_null", "other_a", "other_route", "relaxed_cap", "scalar_above_cap", "zone_above_cap"):
            with open(sample["occupancy"], encoding="utf-8") as stream:
                report = json.load(stream)
            if mode == "old_a_ref":
                report["auditor_version"] = "5"; report["tol_engine_source"] = "a_ref_p99.5"
            elif mode == "unknown_null":
                report["provenance"]["null_stats_sha256"] = "0" * 64
            elif mode == "other_a":
                report["provenance"]["a_sha256"] = "0" * 64
            elif mode == "other_route":
                report["provenance"]["null_route_config"] = {"route": "other"}
            elif mode == "relaxed_cap":
                report["thresholds"]["max_tol_engine"] = 30
            elif mode == "scalar_above_cap":
                report["tol_engine"] = 13
            else:
                report["tol_engine_by_zone"]["occluders"] = 13
            changed = os.path.join(runs, mode + ".json")
            with open(changed, "w", encoding="utf-8") as stream:
                json.dump(report, stream)
            index = [dict(sample, occupancy=changed)] + idx_all[1:]
            j, rc = gate(fx, write_index(index, "idx_" + mode + ".json"))
            c.ok("NULL1_gate_rejeita_" + mode, rc == 3 and j["verdict"] == "INCONCLUSIVO" and
                 any(x.startswith(("json_sem_estrutura_do_auditor", "nula_normativa_nao_congelada", "teto_nula_invalido")) for x in j["integrity"]), j["integrity"][:3])
        # 2. seed ausente num caso core → INCONCLUSIVO
        j, rc = gate(fx, write_index([e for e in idx_all if not (e["case_id"] == "synth_core_b" and e["seed"] == 3)], "idx_missing.json"))
        c.ok("GATE_seed_ausente_INCONCLUSIVO", j["verdict"] == "INCONCLUSIVO" and rc == 3 and j["core"]["synth_core_b"]["missing_seeds"] == [3], (j["verdict"], j["verdict_reason"]))
        # 3. occupancy INCONCLUSIVO (sem OCC_ENGINE) num caso core → INCONCLUSIVO, nunca PASS
        idx = [e for e in idx_all if e["case_id"] != "synth_core_c"] + [produce("synth_core_c", s, "missing_occ") for s in (1, 2, 3)]
        j, rc = gate(fx, write_index(idx, "idx_inc.json"))
        c.ok("GATE_evidencia_ausente_INCONCLUSIVO", j["verdict"] == "INCONCLUSIVO" and "synth_core_c" in j["verdict_reason"], (j["verdict"], j["verdict_reason"]))
        # 4. occupancy PASS mas fidelity FAIL em 3 casos → não PASS
        idx = [e for e in idx_all if e["case_id"] not in ("synth_core_a", "synth_core_b", "synth_core_c")] + [produce(cid, s, "fid_fail") for cid in ("synth_core_a", "synth_core_b", "synth_core_c") for s in (1, 2, 3)]
        j, rc = gate(fx, write_index(idx, "idx_fid.json"))
        c.ok("GATE_fidelidade_FAIL_bloqueia_PASS", j["verdict"] != "PASS" and rc == 1 and j["core_summary"]["n_pass"] == 3 and "fidelity" in j["core"]["synth_core_a"]["majority_failure_kinds"], (j["verdict"], j["core_summary"]))
        # 5. 3 casos sem criação → FALHA-CRIAÇÃO
        idx = [e for e in idx_all if e["case_id"] not in ("synth_core_a", "synth_core_b", "synth_core_c")] + [produce(cid, s, "creation_fail") for cid in ("synth_core_a", "synth_core_b", "synth_core_c") for s in (1, 2, 3)]
        j, rc = gate(fx, write_index(idx, "idx_cre.json"))
        c.ok("GATE_FALHA_CRIACAO", j["verdict"] == "FALHA-CRIAÇÃO" and rc == 1, (j["verdict"], j["verdict_reason"]))
        c.ok("GATE_progressao_MEDIUM_HARD_bloqueada", j["progression"]["MEDIUM->HARD"]["allowed"] is False and j["progression"]["EASY->MEDIUM"]["allowed"] is True, j["progression"])
        # 6. roles alterado depois do freeze → INCONCLUSIVO (integridade)
        rb = open(fx["roles"]).read(); json.dump(dict(json.loads(rb), core_cases=CORE[:5] + ["synth_hard_nosplit"]), open(fx["roles"], "w"))
        j, rc = gate(fx, write_index(idx_all, "idx_all2.json"))
        c.ok("GATE_roles_alterado_INCONCLUSIVO", j["verdict"] == "INCONCLUSIVO" and any(x.startswith("sha256:roles") for x in j["integrity"]), j["integrity"][:3])
        open(fx["roles"], "w").write(rb)
        # 7. JSON de auditor produzido em perfil minimal não é elegível
        o = os.path.join(runs, "min.png"); save_rgb(o, engine_output(hard, hard["A"], hard["G_split"], 9)); occ_min = os.path.join(runs, "min.occ.json")
        run_audit(fx, "synth_hard_01", o, Gs, profile="minimal", extra=["--front-occluders", F["hard_FO.png"], "--band-min", F["hard_BMIN_split.png"], "--band-max-body", F["hard_BMAXB.png"],
                                                                      "--body-coverable", F["hard_BC.png"], "--tol-engine", "4", "--json-out", occ_min])
        idx = [e for e in idx_all if e["case_id"] != "synth_hard_01"] + [{"case_id": "synth_hard_01", "seed": s, "occupancy": occ_min, "fidelity": [e for e in idx_all if e["case_id"] == "synth_hard_01"][0]["fidelity"]} for s in (1, 2, 3)]
        j, rc = gate(fx, write_index(idx, "idx_min.json"))
        c.ok("GATE_perfil_minimal_nao_elegivel", j["verdict"] == "INCONCLUSIVO" and any(x.startswith("profile_nao_g0") for x in j["integrity"]), j["integrity"][:3])
        # 8. seeds fora do PREREG / duplicadas não contam; 7 entradas → integridade
        extra = [dict(e, seed=e["seed"] + 3) for e in idx_all if e["case_id"] == "synth_core_a"]
        j, rc = gate(fx, write_index(idx_all + extra, "idx_extra.json"))
        c.ok("GATE_seeds_fora_do_prereg_INCONCLUSIVO", j["verdict"] == "INCONCLUSIVO" and any(x.startswith("seed_fora_do_prereg") for x in j["integrity"]), j["integrity"][:3])
        # 9. JSON adulterado (verdict PASS com causas) → integridade
        src = [e for e in idx_all if e["case_id"] == "synth_core_b" and e["seed"] == 1][0]
        jj = json.load(open(src["occupancy"])); jj["engine"]["causes"] = ["garment_not_created:coverage_below_min"]; jj["engine"]["verdict"] = "FAIL"; jj["verdict_engine"] = "PASS"
        tp = os.path.join(runs, "tampered.occ.json"); json.dump(jj, open(tp, "w"))
        idx = [e for e in idx_all if not (e["case_id"] == "synth_core_b" and e["seed"] == 1)] + [dict(src, occupancy=tp)]
        j, rc = gate(fx, write_index(idx, "idx_tamper.json"))
        c.ok("GATE_json_adulterado_INCONCLUSIVO", j["verdict"] == "INCONCLUSIVO" and any(x.startswith("json_incoerente") for x in j["integrity"]), j["integrity"][:3])
        # 10. run de um caso rotulado como outro caso → case_id divergente
        src2 = [e for e in idx_all if e["case_id"] == "synth_core_c" and e["seed"] == 1][0]
        idx = [e for e in idx_all if not (e["case_id"] == "synth_core_d" and e["seed"] == 1)] + [dict(src2, case_id="synth_core_d")]
        j, rc = gate(fx, write_index(idx, "idx_relabel.json"))
        c.ok("GATE_relabel_de_caso_INCONCLUSIVO", j["verdict"] == "INCONCLUSIVO" and any(x.startswith("case_id_divergente") for x in j["integrity"]), j["integrity"][:3])
        # L2: reuso de um run como três seeds → integridade (run_duplicada)
        one = [e for e in idx_all if e["case_id"] == "synth_core_a" and e["seed"] == 1][0]
        idx = [e for e in idx_all if e["case_id"] != "synth_core_a"] + [dict(one, seed=s_) for s_ in (1, 2, 3)]
        j, rc = gate(fx, write_index(idx, "idx_reuse.json"))
        c.ok("L2_reuso_de_run_como_3_seeds_INCONCLUSIVO", j["verdict"] == "INCONCLUSIVO" and any(x.startswith("run_duplicada") for x in j["integrity"]), j["integrity"][:3])
        # L2: fidelidade de outra saída (sha divergente entre auditores) → integridade
        o1 = [e for e in idx_all if e["case_id"] == "synth_core_b" and e["seed"] == 1][0]; o2 = [e for e in idx_all if e["case_id"] == "synth_core_b" and e["seed"] == 2][0]
        idx = [e for e in idx_all if not (e["case_id"] == "synth_core_b" and e["seed"] == 2)] + [dict(o2, fidelity=o1["fidelity"])]
        j, rc = gate(fx, write_index(idx, "idx_fidswap.json"))
        c.ok("L2_fidelidade_de_outra_saida_INCONCLUSIVO", j["verdict"] == "INCONCLUSIVO" and any(x.startswith(("saida_divergente_entre_auditores", "run_duplicada")) for x in j["integrity"]), j["integrity"][:3])
        # L2: O composto FAIL vincula o caso
        idx = [e for e in idx_all if e["case_id"] != "synth_core_d"] + [produce("synth_core_d", s_, "composed_fail") for s_ in (1, 2, 3)]
        j, rc = gate(fx, write_index(idx, "idx_comp.json"))
        c.ok("L2_composto_FAIL_vincula", j["verdict"] != "PASS" and j["core"]["synth_core_d"]["case_verdict"] == "FAIL" and any(c_.startswith("composed:") for c_ in j["core"]["synth_core_d"]["seeds"]["1"]["causes"] if isinstance(c_, str)), (j["verdict"], j["core"]["synth_core_d"]["case_verdict"], j["core"]["synth_core_d"]["seeds"]["1"]["causes"][:2]))
        # L2: roles com uma única seed → integridade (regra ≥2/3 inexequível)
        rb = open(fx["roles"]).read(); r1 = json.loads(rb); r1["core_rule"]["seeds"] = [1]
        for sp in r1["progression"].values(): sp["of_seeds"] = 1; sp["min_seeds_axis_A"] = 1
        json.dump(r1, open(fx["roles"], "w"))
        j, rc = gate(fx, write_index([e for e in idx_all if e["seed"] == 1], "idx_one.json"))
        c.ok("L2_roles_uma_seed_INCONCLUSIVO", j["verdict"] == "INCONCLUSIVO" and any("roles_invalido:seeds" in x or x.startswith("sha256:roles") for x in j["integrity"]), j["integrity"][:3])
        open(fx["roles"], "w").write(rb)
    return c.done("test_g0_gate")


if __name__ == "__main__":
    sys.exit(main())
