#!/usr/bin/env python3
"""Valida um manifest.jsonl contra manifest.schema.json (v6) e aplica checagens que o schema não expressa.

Uso:
    python benchmark/validate_manifest.py manifest.jsonl [--check-files] [--allow-placeholders] [--roles PATH]

Checagens:
  - schema JSON (draft 2020-12), incl. if/then: modo add exige envelope congelado (min_mask) e z_order;
    license com 'self-captured-consent' exige consent_record_id; split_by_garment_edge exige as duas máscaras de split.
  - anti-vazamento por ids (person/garment/source) entre splits.
  - z-order: front_certain exige máscara; front_occluders_mask presente se houver front_certain;
    split_by_garment_edge exige split_must_cover_mask e split_must_stay_visible_mask (erro legível além do schema).
  - placeholders → ERRO, salvo --allow-placeholders (esqueleto antes do congelamento; o relatório marca NÃO CONGELADO):
      sha256 com todos os dígitos iguais · consent_record_id contendo 'PLACEHOLDER' · qualquer string contendo 'A PREENCHER' ou igual a 'TBD'.
  - --check-files: todo local_path deve existir e ter sha256 igual ao declarado (congelamento verificável).
  - duplicatas: mesmo sha256 (ou mesmo phash declarado) com ids diferentes → ERRO.
  - semântica: operation contendo 'background' exige free_space_mask; z_order com 'uncertain'/'split' exige uncertain_occupancy_mask;
    frozen_annotation.annotated_on não pode ser posterior a provenance.added_on quando ambos existem (congelado antes).
  - reuso de máscaras entre casos (anti-contaminação): toda image_source com local_path sob `expected` deve ter basename
    prefixado por `<case_id>_`; caso contrário o prefixo deve ser de um caso listado em provenance.shares_A_with cuja A seja
    EXATAMENTE o mesmo arquivo (mesmo local_path; mesmo sha256 quando ambos reais). Linhas com a mesma A devem listar-se
    mutuamente em shares_A_with; listar caso com A diferente ou caso inexistente → ERRO.
  - papéis do gate G0 (--roles; padrão benchmark/proto0/g0_case_roles.json quando há linhas split=proto0 e o arquivo existe):
    todo caso proto0 tem papel; exatamente core_rule.of casos gate_core, iguais a core_cases; níveis em levels_counted;
    nenhum par de casos core compartilha A (independência); auditor_control ⇔ negative_control ≠ none; progression ⊂ core.
Saída: código 1 se houver erros, 2 em erro de uso.
"""
import json, sys, collections, os, hashlib, argparse, re, re
try:
    import jsonschema
except ImportError:
    print("pip install jsonschema", file=sys.stderr); sys.exit(2)

here = os.path.dirname(os.path.abspath(__file__))
root = os.path.dirname(here)
DEFAULT_ROLES = os.path.join(here, "proto0", "g0_case_roles.json")
G0_CORE_OF = 6  # pré-registrado: seis casos core (EASY–HARD)
KNOWN_ROLES = ("gate_core", "replication", "attribution_fidelity", "attribution_pose_delta", "attribution_sleeve_pair",
               "extreme_report_only", "ground_truth", "auditor_control")
NC_NONE = (None, "none")


def a_size_of(row):
    """(largura, altura) da imagem A quando existe em disco (para conferir a grade das máscaras)."""
    lp = (row.get("A") or {}).get("local_path")
    if not lp:
        return None
    fp = os.path.join(root, lp)
    try:
        from PIL import Image
        with Image.open(fp) as im:
            return im.size
    except Exception:
        return None


def mask_file_issue(fp, a_size):
    """Máscara congelada deve ser PNG modo L/1 estritamente binário (0/255) na grade de A."""
    try:
        from PIL import Image
        import numpy as np
    except Exception:
        return None  # sem PIL/numpy: checagem indisponível (o auditor repete a verificação em tempo de run)
    try:
        with Image.open(fp) as im:
            if im.mode not in ("L", "1"):
                return f"modo {im.mode} (esperado L/1)"
            if a_size and im.size != a_size:
                return f"tamanho {im.size} ≠ A {a_size}"
            arr = np.asarray(im.convert("L"))
    except Exception as e:
        return f"não é PNG legível ({e})"
    if ((arr > 0) & (arr < 255)).any():
        return "valores não binários (esperado 0/255)"
    return None


def iter_sources(obj, path=""):
    """Gera (caminho, image_source) para todo objeto com sha256+source_type, em qualquer profundidade."""
    if isinstance(obj, dict):
        if "sha256" in obj and "source_type" in obj:
            yield path, obj
        for k, val in obj.items():
            yield from iter_sources(val, f"{path}/{k}" if path else k)
    elif isinstance(obj, list):
        for i, it in enumerate(obj):
            yield from iter_sources(it, f"{path}[{i}]")


def iter_strings(obj, path=""):
    if isinstance(obj, dict):
        for k, val in obj.items():
            yield from iter_strings(val, f"{path}/{k}" if path else k)
    elif isinstance(obj, list):
        for i, it in enumerate(obj):
            yield from iter_strings(it, f"{path}[{i}]")
    elif isinstance(obj, str):
        yield path, obj


def is_placeholder_sha(h):
    return bool(h) and len(set(h)) == 1


def schema_error_text(e):
    """Mensagem legível: para anyOf [image_source | null] desce ao sub-erro do ramo image_source (não ao 'is not of type null')."""
    best = e
    while best.context:
        cands = [c for c in best.context if c.validator != "type"] or list(best.context)
        best = max(cands, key=lambda c: len(c.absolute_path))
    msg = best.message
    if len(msg) > 220:
        msg = msg[:220] + "…"
    path = "/".join(map(str, e.absolute_path))
    return f"{msg} @ {path}"


def owner_prefix(basename, case_ids):
    """case_id mais longo tal que basename começa com '<case_id>_'; None se nenhum."""
    cands = [c for c in case_ids if basename.startswith(c + "_")]
    return max(cands, key=len) if cands else None


def same_A(r1, r2):
    a1, a2 = r1.get("A", {}), r2.get("A", {})
    if not a1.get("local_path") or a1.get("local_path") != a2.get("local_path"):
        return False
    h1, h2 = a1.get("sha256", ""), a2.get("sha256", "")
    if h1 and h2 and not is_placeholder_sha(h1) and not is_placeholder_sha(h2) and h1 != h2:
        return False
    return True


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("path", nargs="?", default=os.path.join(here, "manifest.example.jsonl"))
    ap.add_argument("--check-files", action="store_true")
    ap.add_argument("--allow-placeholders", action="store_true")
    ap.add_argument("--roles", default=None,
                    help="JSON de papéis do gate G0 (padrão: benchmark/proto0/g0_case_roles.json quando há linhas split=proto0)")
    args = ap.parse_args(argv)

    schema = json.load(open(os.path.join(here, "manifest.schema.json"), encoding="utf-8"))
    rows = [json.loads(l) for l in open(args.path, encoding="utf-8") if l.strip()]
    v = jsonschema.Draft202012Validator(schema)
    errors = 0; warnings = 0; placeholders = 0
    by_id = {}
    for r in rows:
        by_id.setdefault(r.get("case_id"), r)
    case_ids = [r.get("case_id") for r in rows]

    def err(msg):
        nonlocal errors
        errors += 1; print(msg)

    def warn(msg):
        nonlocal warnings
        warnings += 1; print("AVISO " + msg)

    for i, r in enumerate(rows):
        cid = r.get("case_id")
        for e in sorted(v.iter_errors(r), key=lambda e: list(e.absolute_path)):
            err(f"[{i}] {cid}: {schema_error_text(e)}")
        # placeholders / arquivos
        for spath, sres in iter_sources(r):
            h = sres.get("sha256", "")
            if is_placeholder_sha(h):
                placeholders += 1
                if not args.allow_placeholders:
                    err(f"{cid}: sha256 placeholder em {sres.get('local_path') or sres.get('url')} (use --allow-placeholders só para esqueleto NÃO congelado)")
            cr = sres.get("consent_record_id")
            if isinstance(cr, str) and "PLACEHOLDER" in cr.upper():
                placeholders += 1
                if not args.allow_placeholders:
                    err(f"{cid}: consent_record_id placeholder em {spath}")
            lic = (sres.get("license") or "")
            if re.search(r"self[-_ ]?captured[-_ ]?consent", lic, re.I):
                if not isinstance(cr, str) or not cr.strip() or cr.strip().lower() in ("tbd", "n/a", "na", "none", "null", "-"):
                    err(f"{cid}: license self-captured-consent exige consent_record_id não vazio em {spath} (valor: {cr!r})")
            if args.check_files and sres.get("local_path"):
                fp = os.path.join(root, sres["local_path"])
                if not os.path.exists(fp):
                    err(f"{cid}: arquivo ausente {sres['local_path']}")
                else:
                    real = hashlib.sha256(open(fp, "rb").read()).hexdigest()
                    if real != h:
                        err(f"{cid}: sha256 divergente para {sres['local_path']} (declarado {h[:12]}…, real {real[:12]}…)")
                    if spath.startswith("expected") and fp.lower().endswith(".png") and "ground_truth" not in spath:
                        issue = mask_file_issue(fp, a_size_of(r))
                        if issue:
                            err(f"{cid}: máscara {sres['local_path']} inválida — {issue}")
        for spath, sval in iter_strings(r):
            if "A PREENCHER" in sval or sval.strip() == "TBD":
                placeholders += 1
                if not args.allow_placeholders:
                    err(f"{cid}: valor placeholder ('A PREENCHER'/'TBD') em {spath}")
        fa = r.get("expected", {}).get("frozen_annotation", {}) or {}
        zo = fa.get("z_order", []) or []
        if r.get("split") == "proto0" and not fa.get("protected_mask"):
            err(f"{cid}: frozen_annotation.protected_mask é null — obrigatório em proto0 (C1 estrito, <case>_PR.png; o auditor resolve a partir do manifesto)")
        if any(z.get("relation") == "front_certain" for z in zo) and not fa.get("front_occluders_mask"):
            err(f"{cid}: há elementos front_certain mas front_occluders_mask é null (deve ser a união das máscaras front_certain)")
        if any(z.get("relation") == "front_certain" for z in zo) and r.get("coverage", {}).get("occlusion") == ["none"]:
            err(f"{cid}: coverage.occlusion=['none'] mas z_order tem elemento front_certain (contradição: eixo D não pode ser NOT_APPLICABLE)")
        occl = r.get("coverage", {}).get("occlusion")
        if isinstance(occl, list) and "none" in occl and len(occl) > 1:
            err(f"{cid}: coverage.occlusion mistura 'none' com outros valores ({occl})")
        if isinstance(occl, list) and len(occl) == 0:
            err(f"{cid}: coverage.occlusion vazio — declare ['none'] ou os oclusores")
        if not any(z.get("relation") == "front_certain" for z in zo) and occl != ["none"] and r.get("spec", {}).get("mode") in ("add", "add_over_layer"):
            err(f"{cid}: coverage.occlusion={occl} sem nenhum elemento front_certain no z_order — ou anote o oclusor como front_certain (com máscara) ou declare occlusion=['none']")
        if not any(z.get("relation") == "front_certain" for z in zo) and fa.get("front_occluders_mask"):
            err(f"{cid}: front_occluders_mask presente sem nenhum elemento front_certain (deve ser a união das máscaras front_certain)")
        for z in zo:
            if z.get("relation") == "front_certain" and not z.get("mask"):
                err(f"{cid}: elemento {z.get('element')} front_certain sem máscara")
            if z.get("relation") == "split_by_garment_edge":
                if not z.get("split_must_cover_mask") or not z.get("split_must_stay_visible_mask"):
                    err(f"{cid}: elemento {z.get('element')} split_by_garment_edge exige split_must_cover_mask (lado que a peça DEVE cobrir) e split_must_stay_visible_mask (lado que DEVE ficar visível/idêntico a A)")
            elif z.get("split_must_cover_mask") or z.get("split_must_stay_visible_mask"):
                warn(f"{cid}: elemento {z.get('element')} tem máscaras de split mas relation={z.get('relation')} (só fazem sentido em split_by_garment_edge)")
        if any(z.get("relation") in ("uncertain", "split_by_garment_edge") and z.get("element") != "hair_front" for z in zo) and not fa.get("uncertain_occupancy_mask"):
            warn(f"{cid}: z_order tem uncertain/split mas uncertain_occupancy_mask é null")
        op = r.get("coverage", {}).get("operation", "")
        if "background" in op and not fa.get("free_space_mask"):
            warn(f"{cid}: operation={op} mas free_space_mask é null (tecido sobre fundo cairá em região proibida)")
        band = fa.get("plausible_occupancy_band", {}) or {}
        if band.get("max_mask") and band.get("max_body_mask") and band["max_mask"].get("local_path") == band["max_body_mask"].get("local_path"):
            warn(f"{cid}: max_mask (legado) aponta para o mesmo arquivo que max_body_mask; remova o legado")
        ao, ad = fa.get("annotated_on"), r.get("provenance", {}).get("added_on")
        if ao and ad and ao > ad:
            err(f"{cid}: annotated_on ({ao}) posterior a added_on ({ad}) — anotação deve preceder")
        if r.get("spec", {}).get("mode") in ("add", "add_over_layer") and r.get("spec", {}).get("garment_of_category_present_in_A") is True:
            warn(f"{cid}: mode=add mas garment_of_category_present_in_A=true")

    # ---- shares_A_with: reciprocidade e coerência de A --------------------------------------------------------
    by_A = collections.defaultdict(list)
    for r in rows:
        lp = r.get("A", {}).get("local_path")
        if lp: by_A[("path", lp)].append(r["case_id"])
        h = r.get("A", {}).get("sha256", "")
        if h and not is_placeholder_sha(h): by_A[("sha", h)].append(r["case_id"])
    for r in rows:
        cid = r.get("case_id")
        if not cid:
            continue
        shares = r.get("provenance", {}).get("shares_A_with", []) or []
        for other in shares:
            if other == cid:
                err(f"{cid}: shares_A_with contém o próprio case_id")
            elif other not in by_id:
                err(f"{cid}: shares_A_with aponta para caso inexistente '{other}'")
            elif not same_A(r, by_id[other]):
                err(f"{cid}: shares_A_with lista '{other}' mas a imagem A difere ({r.get('A', {}).get('local_path')} vs {by_id[other].get('A', {}).get('local_path')})")
        for key, group in by_A.items():
            if cid in group:
                for other in group:
                    if other != cid and other not in shares:
                        err(f"{cid}: usa a mesma A ({key[0]}={str(key[1])[-40:]}) que '{other}' mas não o lista em provenance.shares_A_with (deve ser o conjunto completo, em ambas as linhas)")

    # ---- reuso de máscaras entre casos ----------------------------------------------------------------------
    B_DEPENDENT = ("_BMIN", "_BMAX", "_BMAXB", "_FS", "_UNC", "_BG", "_GSTAR", "_GT")  # dependem da peça B (banda, espaço livre, incerteza, máscara em B, GT)
    def mask_suffix(base, owner):
        stem = base[len(owner) + 1:] if owner and base.startswith(owner + "_") else base
        return "_" + stem.split(".")[0]
    owned_paths = {}  # (owner, basename) → local_path declarado pelo dono
    for r in rows:
        for spath, sres in iter_sources(r.get("expected", {}), "expected"):
            lp = sres.get("local_path")
            if lp and owner_prefix(os.path.basename(lp), case_ids) == r.get("case_id"):
                owned_paths[(r.get("case_id"), os.path.basename(lp))] = (lp, sres.get("sha256", ""))
    for r in rows:
        cid = r.get("case_id")
        if not cid:
            continue
        shares = r.get("provenance", {}).get("shares_A_with", []) or []
        for spath, sres in iter_sources(r.get("expected", {}), "expected"):
            lp = sres.get("local_path")
            if not lp:
                err(f"{cid}: {spath} sem local_path — toda referência congelada sob expected precisa de arquivo local verificável (url-only não é congelável)")
                continue
            norm = os.path.normpath(lp).replace(os.sep, "/")
            if os.path.isabs(lp) or norm.startswith("..") or "/../" in "/" + norm + "/":
                err(f"{cid}: {spath} = {lp} — caminho absoluto ou com '..' não é permitido (deve ser relativo à raiz do repositório)")
                continue
            if r.get("split") == "proto0" and not norm.startswith("benchmark/proto0/"):
                err(f"{cid}: {spath} = {lp} — arquivos congelados de proto0 devem estar em benchmark/proto0/")
            base = os.path.basename(lp)
            owner = owner_prefix(base, case_ids)
            if owner == cid:
                continue
            if owner is None:
                err(f"{cid}: {spath} = {base} não tem prefixo '<case_id>_' de nenhum caso do manifesto (máscara congelada deve ser nomeada pelo caso dono)")
                continue
            if owner not in shares or not same_A(r, by_id[owner]):
                err(f"{cid}: {spath} = {base} — máscara reaproveitada de outro caso sem shares_A_with / A diferente (dona: {owner})")
                continue
            own = owned_paths.get((owner, base))
            if own is None:
                err(f"{cid}: {spath} = {base} — o caso dono '{owner}' não declara esse arquivo; reuso só do arquivo congelado do dono")
            else:
                if own[0] != lp:
                    err(f"{cid}: {spath} = {lp} — caminho difere do arquivo congelado do dono ({own[0]})")
                h1, h2 = sres.get("sha256", ""), own[1]
                if not is_placeholder_sha(h1) and not is_placeholder_sha(h2) and h1 != h2:
                    err(f"{cid}: {spath} = {base} — sha256 difere do arquivo congelado do dono '{owner}'")
            suf = mask_suffix(base, owner)
            if any(suf == bd or suf.startswith(bd + "_") for bd in B_DEPENDENT):
                if (by_id[owner].get("B", {}) or {}).get("local_path") != (r.get("B", {}) or {}).get("local_path"):
                    err(f"{cid}: {spath} = {base} depende da peça B (banda/espaço livre/incerteza/máscara em B) e a B difere da do dono '{owner}' — precisa de arquivo próprio")

    # ---- anti-vazamento por ids ----------------------------------------------------------------------------
    for key in ("person_group_id", "garment_group_id", "source_group_id"):
        seen = collections.defaultdict(set)
        for r in rows:
            g = r.get("provenance", {}).get(key)
            if g: seen[g].add(r["split"])
        for g, splits in seen.items():
            if len(splits) > 1:
                err(f"VAZAMENTO {key}={g} aparece em splits {sorted(splits)}")
    # duplicatas por hash real / phash com ids diferentes
    by_hash = collections.defaultdict(set)
    for r in rows:
        h = r.get("A", {}).get("sha256", ""); ph = r.get("provenance", {}).get("phash")
        pid = r.get("provenance", {}).get("person_group_id")
        if h and not is_placeholder_sha(h): by_hash[("sha", h)].add(pid)
        if ph: by_hash[("phash", ph)].add(pid)
    for k, pids in by_hash.items():
        if len(pids) > 1:
            err(f"DUPLICATA {k[0]}={k[1][:12]}… com person_group_id diferentes {sorted(map(str, pids))}")
    if len(case_ids) != len(set(case_ids)):
        err("case_id duplicado")

    # ---- papéis do gate G0 ------------------------------------------------------------------------------------
    proto0 = [r for r in rows if r.get("split") == "proto0"]
    roles_path = args.roles
    if roles_path is None and proto0 and os.path.exists(DEFAULT_ROLES):
        roles_path = DEFAULT_ROLES
    core_line = None
    if roles_path:
        if not os.path.exists(roles_path):
            print(f"arquivo de papéis não encontrado: {roles_path}", file=sys.stderr); return 2
        roles_doc = json.load(open(roles_path, encoding="utf-8"))
        if not proto0:
            print(f"(roles) manifesto sem linhas split=proto0; papéis de {os.path.relpath(roles_path, root)} não aplicados")
        else:
            roles = roles_doc.get("roles", {}) or {}
            core_rule = roles_doc.get("core_rule", {}) or {}
            core_cases = list(roles_doc.get("core_cases", []) or [])
            levels = set(core_rule.get("levels_counted", []) or [])
            of = core_rule.get("of")
            proto_ids = {r["case_id"] for r in proto0}
            if roles_doc.get("gate") != "G0":
                warn(f"(roles) gate={roles_doc.get('gate')!r}, esperado 'G0'")
            if roles_doc.get("frozen_before_first_run") is not True:
                err("(roles) frozen_before_first_run deve ser true — o conjunto core é fixado antes de qualquer run")
            if not levels:
                err("(roles) core_rule.levels_counted ausente/vazio — deve ser exatamente EASY, MEDIUM, HARD")
            elif levels - {"EASY", "MEDIUM", "HARD"}:
                err(f"(roles) core_rule.levels_counted contém níveis fora de EASY/MEDIUM/HARD: {sorted(levels - {'EASY', 'MEDIUM', 'HARD'})} (EXTREME é só reporte)")
            if of != G0_CORE_OF:
                err(f"(roles) core_rule.of = {of!r}; o gate G0 pré-registra exatamente {G0_CORE_OF} casos core")
            seeds_ = core_rule.get("seeds") or []
            if not isinstance(seeds_, list) or len(set(seeds_)) < 3:
                err(f"(roles) core_rule.seeds = {seeds_!r}; a regra 'mediana sobre seeds (≥ 2/3)' exige ≥ 3 seeds distintas")
            for step, spec in (roles_doc.get("progression", {}) or {}).items():
                if isinstance(seeds_, list) and spec.get("of_seeds") != len(seeds_):
                    err(f"(roles) progression {step}: of_seeds={spec.get('of_seeds')} ≠ nº de seeds ({len(seeds_)})")
            for cid in sorted(proto_ids):
                if cid not in roles:
                    err(f"(roles) caso proto0 '{cid}' sem papel em {os.path.basename(roles_path)}")
            for cid, role in roles.items():
                if cid not in proto_ids:
                    err(f"(roles) papel declarado para caso inexistente no manifesto: '{cid}'")
                if role not in KNOWN_ROLES:
                    err(f"(roles) papel desconhecido '{role}' em '{cid}' (válidos: {', '.join(KNOWN_ROLES)})")
            core_by_role = sorted(c for c, role in roles.items() if role == "gate_core")
            if not isinstance(of, int) or of <= 0:
                err("(roles) core_rule.of ausente ou inválido")
            else:
                if len(core_cases) != of:
                    err(f"(roles) core_cases tem {len(core_cases)} casos; core_rule.of = {of}")
                if len(core_by_role) != of:
                    err(f"(roles) {len(core_by_role)} casos com papel gate_core; core_rule.of = {of}")
            if sorted(core_cases) != core_by_role:
                err(f"(roles) core_cases {sorted(core_cases)} ≠ casos com papel gate_core {core_by_role}")
            if len(set(core_cases)) != len(core_cases):
                err("(roles) core_cases com repetição")
            mp = core_rule.get("min_pass")
            if isinstance(mp, int) and isinstance(of, int) and not (0 < mp <= of):
                err(f"(roles) core_rule.min_pass={mp} fora de (0, {of}]")
            for cid in core_cases:
                r = by_id.get(cid)
                if r is None:
                    err(f"(roles) caso core '{cid}' não existe no manifesto"); continue
                if r.get("split") != "proto0":
                    err(f"(roles) caso core '{cid}' não é split=proto0")
                if levels and r.get("level") not in levels:
                    err(f"(roles) caso core '{cid}' tem nível {r.get('level')} fora de levels_counted {sorted(levels)}")
                if r.get("expected", {}).get("negative_control") not in NC_NONE:
                    err(f"(roles) caso core '{cid}' é controle (negative_control={r['expected'].get('negative_control')}) — controles não contam no core")
            present_core = [c for c in core_cases if c in by_id]
            for i1 in range(len(present_core)):
                for i2 in range(i1 + 1, len(present_core)):
                    a, b = present_core[i1], present_core[i2]
                    if same_A(by_id[a], by_id[b]):
                        err(f"(roles) independência: casos core '{a}' e '{b}' compartilham a mesma A ({by_id[a]['A'].get('local_path')})")
            for r in proto0:
                cid = r["case_id"]; role = roles.get(cid)
                is_ctrl = r.get("expected", {}).get("negative_control") not in NC_NONE
                if role == "auditor_control" and not is_ctrl:
                    err(f"(roles) '{cid}' tem papel auditor_control mas expected.negative_control é none")
                if is_ctrl and role is not None and role != "auditor_control":
                    err(f"(roles) '{cid}' tem negative_control={r['expected'].get('negative_control')} mas papel {role} (deveria ser auditor_control)")
            for step, spec in (roles_doc.get("progression", {}) or {}).items():
                for cid in spec.get("cases", []) or []:
                    if cid not in core_cases:
                        err(f"(roles) progression {step}: caso '{cid}' não pertence a core_cases")
                mc = spec.get("min_cases")
                if isinstance(mc, int) and mc > len(spec.get("cases", []) or []):
                    err(f"(roles) progression {step}: min_cases={mc} maior que o número de casos listados")
            core_line = f"G0 core: {len(core_cases)} casos congelados: {', '.join(core_cases)} (regra ≥ {mp}/{of}; seeds {core_rule.get('seeds')})"
    elif proto0:
        err("manifesto proto0 sem arquivo de papéis do gate (use --roles ou crie benchmark/proto0/g0_case_roles.json) — sem papéis congelados não há G0")

    if core_line:
        print(core_line)
    if placeholders == 0 and args.check_files:
        frozen = "CONGELADO"
    elif placeholders:
        frozen = f"NÃO CONGELADO ({placeholders} placeholder(s))"
    else:
        frozen = "NÃO CONGELADO (arquivos não verificados; use --check-files)"
    print(f"{len(rows)} casos, {errors} erro(s), {warnings} aviso(s) — estado: {frozen}")
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
