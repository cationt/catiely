#!/usr/bin/env python3
r"""
g0_gate.py — aplica os critérios PRÉ-REGISTRADOS do Gate G0 (docs/06 §7, PREREG §6) sobre os JSONs dos auditores, por rota × braço.

Regras (todas lidas de g0_case_roles.json congelado — nunca escolhidas depois de ver resultados):
  * Só os `core_cases` (6, EASY–HARD) contam para "≥ 4/6". Todos os outros casos são reportados pelo seu papel (replication,
    attribution_*, extreme_report_only, ground_truth, auditor_control) e NUNCA entram na contagem.
  * Por caso e seed: PASS exige `occupancy_audit` PASS (alvo engine) E `garment_fidelity_audit` PASS. Qualquer INCONCLUSIVO em um
    caso core torna o gate INCONCLUSIVO (evidência obrigatória ausente / referência inconsistente), nunca PASS silencioso.
  * Por caso: mediana sobre as seeds (≥ 2 de 3 seeds PASS) decide; a pior seed é reportada.
  * Classificação: PASS (≥ min_pass/of); FALHA-CRIAÇÃO (≥ 3 casos com não-criação majoritária); FALHA-OCLUSÃO (≥ 2 casos com falha de
    oclusão/z-order majoritária); senão FALHA (preservação/fidelidade; FALHA-ACOPLAMENTO exige comparação entre braços — fora deste script).
  * Progressão EASY→MEDIUM→HARD→EXTREME: eixo A (criação: coverage ≥ limiar, ΔE acima do no-op, G com mudança) em ≥ min_seeds/of_seeds nos
    casos controladores de cada transição.
  * Integridade: todos os JSONs devem ter profile g0, `gate_eligible: true`, o MESMO sha256 de FREEZE.json que este script calcula, e
    case_id coerente com o índice. FREEZE.json é conferido contra manifesto/PREREG/roles (sha256). Qualquer divergência → INCONCLUSIVO.

Uso:
  python tools/g0_gate.py --roles benchmark/proto0/g0_case_roles.json --freeze benchmark/proto0/FREEZE.json \
     --manifest benchmark/proto0_cases.jsonl --prereg benchmark/proto0/PREREG.md --index runs/proto0/klein4b_E2a/index.json --json-out ...
  index.json = [{"case_id": ..., "seed": 1, "occupancy": "<json>", "fidelity": "<json>"}, ...]
Exit: 0 PASS · 1 FALHA-* · 3 INCONCLUSIVO.
"""
import argparse, json, os, sys, collections

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import freeze_check as fz  # noqa: E402

CREATION = ("garment_not_created",)
OCCLUSION = ("bad_occlusion", "visibility_violation", "duplicate_limb", "occluder_cutout", "split_edge_violation")


def classify_cause(c):
    if c.startswith(CREATION):
        return "creation"
    if c.startswith(OCCLUSION):
        return "occlusion"
    if c.startswith(("wrong_category", "attribute_mismatch", "garment_identity")):
        return "fidelity"
    return "preservation"


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--roles", required=True); ap.add_argument("--freeze", required=True)
    ap.add_argument("--manifest", required=True); ap.add_argument("--prereg", required=True)
    ap.add_argument("--index", required=True); ap.add_argument("--route", default=""); ap.add_argument("--arm", default="")
    ap.add_argument("--json-out")
    args = ap.parse_args()
    roles = json.load(open(args.roles, encoding="utf-8"))
    out = {"gate": roles.get("gate", "G0"), "route": args.route, "arm": args.arm, "integrity": [], "core": {}, "non_core": {}, "progression": {}}
    info, mism = fz.verify_freeze(args.freeze, args.manifest, args.prereg, args.roles)
    out["freeze"] = info; out["integrity"].extend(mism)
    freeze_sha = info.get("freeze_sha256")
    core = roles["core_cases"]; rule = roles["core_rule"]; seeds = set(rule.get("seeds", [1, 2, 3]))
    if not (1 <= int(rule.get("min_pass", 0)) <= int(rule.get("of", 0))) or len(core) != int(rule.get("of", 0)) or len(set(core)) != len(core):
        out["integrity"].append(f"roles_invalido:min_pass={rule.get('min_pass')} of={rule.get('of')} core={len(core)}")
    if roles.get("frozen_before_first_run") is not True:
        out["integrity"].append("roles_invalido:frozen_before_first_run")
    idx = json.load(open(args.index, encoding="utf-8"))
    by_case = collections.defaultdict(dict)
    for e in idx:
        rec = {"seed": e["seed"]}
        for kind in ("occupancy", "fidelity"):
            p = e.get(kind)
            if not p or not os.path.exists(p):
                rec[kind] = None; out["integrity"].append(f"ausente:{kind}:{e['case_id']}:seed{e['seed']}"); continue
            j = json.load(open(p, encoding="utf-8")); rec[kind] = j
            if j.get("profile") != "g0":
                out["integrity"].append(f"profile_nao_g0:{kind}:{e['case_id']}:seed{e['seed']}")
            if not j.get("gate_eligible"):
                out["integrity"].append(f"nao_elegivel:{kind}:{e['case_id']}:seed{e['seed']}")
            if j.get("provenance", {}).get("freeze_sha256") != freeze_sha:
                out["integrity"].append(f"freeze_divergente:{kind}:{e['case_id']}:seed{e['seed']}")
            if j.get("provenance", {}).get("case_id") != e["case_id"]:
                out["integrity"].append(f"case_id_divergente:{kind}:{e['case_id']}:seed{e['seed']}")
            # coerência interna do JSON (adulteração): veredito PASS exige causas vazias e nenhuma evidência ausente
            if kind == "occupancy":
                eng = j.get("engine", {})
                if j.get("verdict_engine") == "PASS" and (eng.get("causes") or eng.get("missing_required_evidence") or eng.get("verdict") != "PASS"):
                    out["integrity"].append(f"json_incoerente:{kind}:{e['case_id']}:seed{e['seed']}")
            else:
                if j.get("verdict") == "PASS" and (j.get("causes") or j.get("missing_required_evidence") or j.get("inconclusive")):
                    out["integrity"].append(f"json_incoerente:{kind}:{e['case_id']}:seed{e['seed']}")
        if e["seed"] not in seeds:
            out["integrity"].append(f"seed_fora_do_prereg:{e['case_id']}:seed{e['seed']}"); continue
        if e["seed"] in by_case[e["case_id"]]:
            out["integrity"].append(f"seed_duplicada:{e['case_id']}:seed{e['seed']}")
        by_case[e["case_id"]][e["seed"]] = rec

    def seed_eval(rec):
        occ, fid = rec.get("occupancy"), rec.get("fidelity")
        if occ is None or fid is None:
            return {"status": "INCONCLUSIVO", "causes": ["missing_audit_json"], "axis_A": None}
        ve = occ.get("verdict_engine"); vf = fid.get("verdict")
        eng = occ.get("engine", {})
        causes = list(eng.get("causes", [])) + list(fid.get("causes", []))
        axis_a = (not any(c.startswith(CREATION) for c in eng.get("causes", []))) and eng.get("coverage_of_band_min") is not None
        flags = list(occ.get("flags", [])) + list(eng.get("flags", []))
        if ve == "PASS" and vf == "PASS" and not any(f.startswith(("occlusion_listed_without_front_certain", "null_distribution_not_credible")) for f in flags):
            st = "PASS"
        elif ve == "PASS" and vf == "PASS":
            st = "INCONCLUSIVO"; causes.append("flags:" + ";".join(flags))
        elif "INCONCLUSIVO" in (ve, vf) or str(ve).startswith("FAIL:frozen") or str(vf).startswith("FAIL:frozen"):
            st = "INCONCLUSIVO"
            if str(ve).startswith("FAIL:frozen") or str(vf).startswith("FAIL:frozen"):
                causes.append("frozen_reference_mismatch")
            else:
                causes += [f"missing:{m}" for m in eng.get("missing_required_evidence", []) + fid.get("missing_required_evidence", [])]
                causes += eng.get("inconclusive", []) + fid.get("inconclusive", [])
        else:
            st = "FAIL"
        return {"status": st, "causes": causes, "axis_A": bool(axis_a), "verdict_occupancy_engine": ve, "verdict_fidelity": vf}

    def case_eval(cid):
        recs = by_case.get(cid, {})
        per_seed = {s: seed_eval(recs[s]) for s in sorted(recs)}
        missing = sorted(seeds - set(recs))
        n_pass = sum(1 for v in per_seed.values() if v["status"] == "PASS")
        n_inc = sum(1 for v in per_seed.values() if v["status"] == "INCONCLUSIVO")
        need = (len(seeds) // 2) + 1
        res = {"seeds": per_seed, "missing_seeds": missing, "n_pass": n_pass, "n_inconclusive": n_inc}
        if missing or n_inc:
            res["case_verdict"] = "INCONCLUSIVO"
        else:
            res["case_verdict"] = "PASS" if n_pass >= need else "FAIL"
        worst = min(per_seed.items(), key=lambda kv: ({"PASS": 2, "FAIL": 0, "INCONCLUSIVO": 1}[kv[1]["status"]], -len(kv[1]["causes"])), default=None)
        res["worst_seed"] = worst[0] if worst else None
        axis_a_seeds = sum(1 for v in per_seed.values() if v["axis_A"])
        res["axis_A_seeds_pass"] = axis_a_seeds
        kinds = collections.Counter()
        for v in per_seed.values():
            if v["status"] == "FAIL":
                for k in {classify_cause(c) for c in v["causes"]}:
                    kinds[k] += 1
        res["majority_failure_kinds"] = [k for k, n in kinds.items() if n >= need]
        return res

    for cid in core:
        out["core"][cid] = case_eval(cid)
    for cid, role in roles.get("roles", {}).items():
        if cid in core or cid not in by_case:
            continue
        r = case_eval(cid); r["role"] = role; out["non_core"][cid] = r
    for cid in by_case:
        if cid not in roles.get("roles", {}):
            out["integrity"].append(f"caso_sem_papel_no_roles:{cid}")

    # progressão
    for trans, spec in roles.get("progression", {}).items():
        ok_cases = [c for c in spec["cases"] if out["core"].get(c, {}).get("axis_A_seeds_pass", 0) >= spec["min_seeds_axis_A"]]
        out["progression"][trans] = {"cases_meeting_axis_A": ok_cases, "allowed": len(ok_cases) >= spec["min_cases"]}

    # veredito
    core_verdicts = [out["core"][c]["case_verdict"] for c in core]
    n_pass = core_verdicts.count("PASS"); n_inc = core_verdicts.count("INCONCLUSIVO")
    out["core_summary"] = {"n_pass": n_pass, "n_fail": core_verdicts.count("FAIL"), "n_inconclusive": n_inc, "of": rule["of"], "min_pass": rule["min_pass"]}
    if out["integrity"]:
        out["verdict"] = "INCONCLUSIVO"; out["verdict_reason"] = "integrity:" + ";".join(out["integrity"][:10])
    elif n_inc:
        out["verdict"] = "INCONCLUSIVO"; out["verdict_reason"] = "core_cases_inconclusive:" + ",".join(c for c in core if out["core"][c]["case_verdict"] == "INCONCLUSIVO")
    elif n_pass >= rule["min_pass"]:
        out["verdict"] = "PASS"; out["verdict_reason"] = f"{n_pass}/{rule['of']} casos core PASS (occupancy + fidelity)"
    else:
        creation = sum(1 for c in core if "creation" in out["core"][c]["majority_failure_kinds"])
        occl = sum(1 for c in core if "occlusion" in out["core"][c]["majority_failure_kinds"])
        if creation >= 3:
            out["verdict"] = "FALHA-CRIAÇÃO"
        elif occl >= 2:
            out["verdict"] = "FALHA-OCLUSÃO"
        else:
            out["verdict"] = "FALHA"
        out["verdict_reason"] = f"{n_pass}/{rule['of']} PASS; não-criação majoritária em {creation}; oclusão em {occl}; FALHA-ACOPLAMENTO exige comparação entre braços (E1′/E1″/E2/E4)"
    js = json.dumps(out, indent=1, ensure_ascii=False); print(js)
    if args.json_out:
        open(args.json_out, "w", encoding="utf-8").write(js)
    sys.exit(0 if out["verdict"] == "PASS" else (3 if out["verdict"] == "INCONCLUSIVO" else 1))


if __name__ == "__main__":
    main()
