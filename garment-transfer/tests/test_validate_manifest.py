#!/usr/bin/env python3
"""Testes do validador do manifesto (schema v6 + regras do gate G0). Rodar: python3 tests/test_validate_manifest.py
Cada teste copia linhas de benchmark/proto0_cases.jsonl para um manifesto temporário, aplica UMA mutação e confere
código de saída e mensagem do validador — são controles do VALIDADOR (ele tem de pegar o erro), não dos casos."""
import copy, json, os, subprocess, sys, tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
VALIDATOR = os.path.join(ROOT, "benchmark", "validate_manifest.py")
CASES = os.path.join(ROOT, "benchmark", "proto0_cases.jsonl")
EXAMPLE = os.path.join(ROOT, "benchmark", "manifest.example.jsonl")
ROLES = os.path.join(ROOT, "benchmark", "proto0", "g0_case_roles.json")


def load_rows():
    return [json.loads(l) for l in open(CASES, encoding="utf-8") if l.strip()]


def by_id(rows):
    return {r["case_id"]: r for r in rows}


def write_jsonl(path, rows):
    with open(path, "w", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    return path


def write_json(path, obj):
    json.dump(obj, open(path, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    return path


def run(manifest, *args):
    r = subprocess.run([sys.executable, VALIDATOR, manifest, *args], capture_output=True, text=True)
    return r.returncode, r.stdout + r.stderr


def main():
    fails = 0

    def expect(name, rc_out, rc, *must_contain):
        nonlocal fails
        got_rc, out = rc_out
        missing = [s for s in must_contain if s not in out]
        ok = got_rc == rc and not missing
        tail = out.strip().splitlines()[-1] if out.strip() else ""
        print(("ok   " if ok else "FAIL ") + name + f" → exit {got_rc} (esperado {rc})" + ("" if ok else f"; faltou {missing}") + f" | {tail[:110]}")
        if not ok:
            fails += 1
            print("      ---- saída ----\n" + "\n".join("      " + l for l in out.strip().splitlines()[-12:]))

    with tempfile.TemporaryDirectory() as d:
        base = load_rows()
        roles = json.load(open(ROLES, encoding="utf-8"))

        # 1 manifesto atual, esqueleto → 0 erros
        expect("proto0_cases_allow_placeholders", run(CASES, "--allow-placeholders"), 0, "0 erro(s)", "G0 core: 6 casos congelados", "NÃO CONGELADO")
        # 2 sem --allow-placeholders → placeholders são erro
        expect("proto0_cases_sem_allow_placeholders", run(CASES), 1, "placeholder", "NÃO CONGELADO")

        # 3 máscara de outro caso sem shares_A_with (hard_02 tem A própria; pega BC de hard_01)
        rows = copy.deepcopy(base); b = by_id(rows)
        b["proto0_hard_02"]["expected"]["frozen_annotation"]["body_coverable_mask"]["local_path"] = "benchmark/proto0/proto0_hard_01_BC.png"
        expect("mascara_reaproveitada_sem_shares", run(write_jsonl(f"{d}/m3.jsonl", rows), "--allow-placeholders"), 1,
               "máscara reaproveitada de outro caso sem shares_A_with / A diferente", "proto0_hard_02")

        # 4 mesma A em duas linhas sem shares_A_with mútuo
        rows = copy.deepcopy(base); b = by_id(rows)
        b["proto0_hard_02"]["A"]["local_path"] = b["proto0_hard_05"]["A"]["local_path"]
        expect("mesma_A_sem_shares_mutuo", run(write_jsonl(f"{d}/m4.jsonl", rows), "--allow-placeholders"), 1,
               "não o lista em provenance.shares_A_with", "proto0_hard_02", "proto0_hard_05")

        # 5 shares_A_with apontando para caso com A diferente
        rows = copy.deepcopy(base); b = by_id(rows)
        b["proto0_hard_02"]["provenance"]["shares_A_with"] = ["proto0_hard_05"]
        expect("shares_para_A_diferente", run(write_jsonl(f"{d}/m5.jsonl", rows), "--allow-placeholders"), 1,
               "shares_A_with lista 'proto0_hard_05' mas a imagem A difere")

        # 6 roles com 5 casos core
        r5 = copy.deepcopy(roles)
        r5["core_cases"].remove("proto0_hard_05"); r5["roles"]["proto0_hard_05"] = "replication"
        r5["progression"]["HARD->EXTREME"]["cases"].remove("proto0_hard_05")
        expect("roles_5_core", run(CASES, "--allow-placeholders", "--roles", write_json(f"{d}/r6.json", r5)), 1,
               "core_cases tem 5 casos; core_rule.of = 6")

        # 7 dois casos core compartilhando A (hard_01 e hard_01_pair_b)
        r7 = copy.deepcopy(roles)
        r7["core_cases"] = [c if c != "proto0_hard_02" else "proto0_hard_01_pair_b" for c in r7["core_cases"]]
        r7["roles"]["proto0_hard_02"] = "replication"; r7["roles"]["proto0_hard_01_pair_b"] = "gate_core"
        r7["progression"]["HARD->EXTREME"]["cases"] = [c if c != "proto0_hard_02" else "proto0_hard_01_pair_b" for c in r7["progression"]["HARD->EXTREME"]["cases"]]
        expect("roles_core_compartilha_A", run(CASES, "--allow-placeholders", "--roles", write_json(f"{d}/r7.json", r7)), 1,
               "independência", "proto0_hard_01", "proto0_hard_01_pair_b")

        # 8 self-captured-consent sem consent_record_id → erro de schema
        rows = copy.deepcopy(base); b = by_id(rows)
        assert "self-captured-consent" in b["proto0_easy_01"]["A"]["license"]
        del b["proto0_easy_01"]["A"]["consent_record_id"]
        expect("consent_record_id_obrigatorio", run(write_jsonl(f"{d}/m8.jsonl", rows), "--allow-placeholders"), 1,
               "'consent_record_id' is a required property", "proto0_easy_01")

        # 9 split_by_garment_edge sem máscaras de split
        rows = copy.deepcopy(base); b = by_id(rows)
        zo = b["proto0_hard_03"]["expected"]["frozen_annotation"]["z_order"]
        el = [z for z in zo if z["relation"] == "split_by_garment_edge"][0]
        del el["split_must_cover_mask"]; del el["split_must_stay_visible_mask"]
        expect("split_sem_mascaras", run(write_jsonl(f"{d}/m9.jsonl", rows), "--allow-placeholders"), 1,
               "split_by_garment_edge exige split_must_cover_mask", "split_must_cover_mask' is a required property")

        # 10 caso proto0 ausente do arquivo de papéis
        r10 = copy.deepcopy(roles); del r10["roles"]["proto0_easy_02"]
        expect("roles_caso_sem_papel", run(CASES, "--allow-placeholders", "--roles", write_json(f"{d}/r10.json", r10)), 1,
               "caso proto0 'proto0_easy_02' sem papel")

        # 10b protected_mask null em caso proto0 → erro (obrigatório; o auditor resolve a partir do manifesto)
        rows = copy.deepcopy(base); b = by_id(rows)
        b["proto0_easy_01"]["expected"]["frozen_annotation"]["protected_mask"] = None
        expect("protected_mask_obrigatorio_proto0", run(write_jsonl(f"{d}/m10b.jsonl", rows), "--allow-placeholders"), 1,
               "protected_mask é null — obrigatório em proto0")

        # 11 (bônus) exemplo de manifesto continua válido; split dev não exige papéis
        expect("manifest_example", run(EXAMPLE, "--allow-placeholders"), 0, "0 erro(s)")
        # 12 (bônus) caso com negative_control mas papel não-controle
        r12 = copy.deepcopy(roles); r12["roles"]["proto0_ctrl_noop_01"] = "replication"
        expect("roles_controle_com_papel_errado", run(CASES, "--allow-placeholders", "--roles", write_json(f"{d}/r12.json", r12)), 1,
               "deveria ser auditor_control")


        # ---- lente adversarial (validador): consentimento vazio / variantes de licença / url-only / máscara B-dependente / roles
        rows = copy.deepcopy(base); bid = by_id(rows)
        bid["proto0_easy_01"]["A"]["license"] = "self-captured-consent (termo assinado)"; bid["proto0_easy_01"]["A"]["consent_record_id"] = ""
        expect("consent_record_id_vazio", run(write_jsonl(os.path.join(d, "m_consent_empty.jsonl"), rows), "--allow-placeholders"), 1, "consent_record_id")
        rows = copy.deepcopy(base); bid = by_id(rows)
        bid["proto0_easy_01"]["A"]["license"] = "Self-Captured-Consent"; bid["proto0_easy_01"]["A"].pop("consent_record_id", None)
        expect("licenca_variante_maiuscula_exige_consent", run(write_jsonl(os.path.join(d, "m_consent_case.jsonl"), rows), "--allow-placeholders"), 1, "consent_record_id")
        rows = copy.deepcopy(base); bid = by_id(rows)
        bid["proto0_easy_01"]["A"]["license"] = "self captured consent"; bid["proto0_easy_01"]["A"]["consent_record_id"] = "N/A"
        expect("licenca_variante_espaco_consent_na", run(write_jsonl(os.path.join(d, "m_consent_na.jsonl"), rows), "--allow-placeholders"), 1, "consent_record_id")
        rows = copy.deepcopy(base); bid = by_id(rows)
        bc = bid["proto0_hard_02"]["expected"]["frozen_annotation"]["body_coverable_mask"]; bc.pop("local_path"); bc["source_type"] = "url"; bc["url"] = "https://x/proto0_hard_01_BC.png"
        expect("mascara_url_only_rejeitada", run(write_jsonl(os.path.join(d, "m_url.jsonl"), rows), "--allow-placeholders"), 1, "sem local_path")
        rows = copy.deepcopy(base); bid = by_id(rows)
        bid["proto0_hard_04"]["expected"]["frozen_annotation"]["plausible_occupancy_band"]["min_mask"]["local_path"] = "benchmark/proto0/proto0_hard_03_BMIN.png"
        expect("mascara_dependente_de_B_com_B_diferente", run(write_jsonl(os.path.join(d, "m_bdep.jsonl"), rows), "--allow-placeholders"), 1, "depende da peça B")
        rows = copy.deepcopy(base); bid = by_id(rows)
        bid["proto0_hard_02"]["expected"]["frozen_annotation"]["body_coverable_mask"]["local_path"] = "benchmark/proto0/../../../etc/proto0_hard_02_BC.png"
        expect("caminho_com_dotdot_rejeitado", run(write_jsonl(os.path.join(d, "m_dotdot.jsonl"), rows), "--allow-placeholders"), 1, "'..'")
        rows = copy.deepcopy(base); bid = by_id(rows)
        bid["proto0_hard_01_pair_b"]["expected"]["frozen_annotation"]["front_occluders_mask"]["local_path"] = "runs/evil/proto0_hard_01_FO.png"
        expect("reuso_de_arquivo_que_nao_e_o_do_dono", run(write_jsonl(os.path.join(d, "m_notowner.jsonl"), rows), "--allow-placeholders"), 1, "difere do arquivo congelado do dono")
        rows = copy.deepcopy(base); bid = by_id(rows)
        bid["proto0_medium_01"]["coverage"]["occlusion"] = ["none", "furniture"]
        expect("occlusion_mistura_none", run(write_jsonl(os.path.join(d, "m_nonemix.jsonl"), rows), "--allow-placeholders"), 1, "mistura 'none'")
        r7 = copy.deepcopy(roles); r7["core_cases"] = r7["core_cases"] + ["proto0_easy_02"]; r7["core_rule"]["of"] = 7; r7["roles"]["proto0_easy_02"] = "gate_core"
        expect("roles_of_7_rejeitado", run(CASES, "--allow-placeholders", "--roles", write_json(os.path.join(d, "roles7.json"), r7)), 1, "exatamente 6")
        rl = copy.deepcopy(roles); rl["core_rule"].pop("levels_counted")
        expect("roles_sem_levels_counted", run(CASES, "--allow-placeholders", "--roles", write_json(os.path.join(d, "roles_nolevels.json"), rl)), 1, "levels_counted")
        rx = copy.deepcopy(roles); rx["core_rule"]["levels_counted"] = ["EASY", "MEDIUM", "HARD", "EXTREME"]
        expect("roles_levels_com_EXTREME", run(CASES, "--allow-placeholders", "--roles", write_json(os.path.join(d, "roles_extreme.json"), rx)), 1, "EXTREME")
        # manifesto proto0 sem roles disponível: copiar validador+schema para um diretório sem proto0/
        vd = os.path.join(d, "vcopy", "benchmark"); os.makedirs(vd)
        import shutil; shutil.copy(VALIDATOR, os.path.join(vd, "validate_manifest.py")); shutil.copy(os.path.join(ROOT, "benchmark", "manifest.schema.json"), os.path.join(vd, "manifest.schema.json"))
        rr = subprocess.run([sys.executable, os.path.join(vd, "validate_manifest.py"), CASES, "--allow-placeholders"], capture_output=True, text=True)
        expect("roles_ausente_e_erro", (rr.returncode, rr.stdout + rr.stderr), 1, "sem arquivo de papéis")

    print(f"\n{'TODOS OK' if not fails else str(fails) + ' FALHA(S)'}")
    sys.exit(1 if fails else 0)


if __name__ == "__main__":
    main()
