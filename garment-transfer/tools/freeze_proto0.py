#!/usr/bin/env python3
"""freeze_proto0.py — gera FREEZE.json: o registro verificável do congelamento ANTES do primeiro run do Prototype 0.

Uso:
  python tools/freeze_proto0.py --manifest benchmark/proto0_cases.jsonl --prereg benchmark/proto0/PREREG.md \
      --roles benchmark/proto0/g0_case_roles.json --null-stats runs/proto0/null/ROTA/null_stats.json \
      --tag proto0-frozen-v1 --out benchmark/proto0/FREEZE.json [--data-root .] [--allow-dirty]

Grava sha256 do manifesto, do PREREG, do roles e das nulas normativas (--null-stats repetível); o sha256 real de TODOS os arquivos referenciados pelo manifesto (A, B, GT, máscaras),
comparado ao declarado; o commit git atual (e se a árvore está suja); a tag. `frozen` só é true se não há placeholders, nem arquivos
ausentes/divergentes, nem árvore suja (salvo --allow-dirty). Com `frozen: false` o auditor (perfil g0) emite FAIL:frozen_reference_mismatch.
Depois de gravar, o FREEZE.json deve ser commitado e a tag criada apontando para esse commit; qualquer alteração posterior em PREREG,
manifesto ou roles é detectada pelos auditores (--freeze).
"""
import argparse, json, os, sys
from datetime import datetime, timezone

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import freeze_check as fz  # noqa: E402


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--manifest", required=True); ap.add_argument("--prereg", required=True); ap.add_argument("--roles", required=True)
    ap.add_argument("--tag", required=True, help="freeze_tag (ex.: proto0-frozen-v1)")
    ap.add_argument("--out", required=True)
    ap.add_argument("--null-stats", action="append", default=[], help="JSON normativo O_null1 por rota/caso; repetível, obrigatório no FREEZE")
    ap.add_argument("--data-root", default=None, help="raiz dos local_path (padrão: raiz do repositório)")
    ap.add_argument("--allow-dirty", action="store_true", help="não exigir árvore git limpa (apenas testes)")
    ap.add_argument("--allow-placeholders", action="store_true", help="grava mesmo com placeholders, com frozen=false")
    ap.add_argument("--skip-validator", action="store_true", help="não executar benchmark/validate_manifest.py antes (apenas testes com manifestos sintéticos)")
    args = ap.parse_args()
    root = fz.repo_root_from(__file__); data_root = args.data_root or root
    rows = fz.load_manifest(args.manifest)
    roles = json.load(open(args.roles, encoding="utf-8"))
    referenced, mism_all = [], []
    null_stats_files = []
    if not args.null_stats:
        mism_all.append("null_stats_missing")
    for path in args.null_stats:
        if not os.path.isfile(path):
            mism_all.append("null_stats_missing:" + path)
            continue
        try:
            with open(path, encoding="utf-8") as stream:
                ns = json.load(stream)
            from occupancy_audit import read_null_stats
            # Valida o mesmo contrato do consumidor, incluindo A ligada a um caso congelado.
            a_hashes = {r.get("A", {}).get("sha256") for r in rows}
            if ns["sha256"]["a"] not in a_hashes:
                raise ValueError("null_stats_a_not_in_manifest")
            _, scalar, zone_tolerances = read_null_stats(path, ns["sha256"]["a"], ns["counts"]["canvas"])
            if any(value > 12 for value in (scalar, *zone_tolerances.values())):
                raise ValueError("null_distribution_not_credible:ceiling_12")
            null_stats_files.append({"path": path, "sha256": fz.sha256_file(path), "a_sha256": ns["sha256"]["a"], "route_config": ns["route_config"]})
        except (OSError, ValueError, KeyError, TypeError, AttributeError) as e:
            mism_all.append("null_stats_invalid:" + path + ":" + str(e))
    if not args.skip_validator:  # defesa em profundidade: o manifesto congelado tem de passar no validador (schema v6 + papéis + reuso de máscaras)
        import subprocess
        vcmd = [sys.executable, os.path.join(root, "benchmark", "validate_manifest.py"), args.manifest, "--roles", args.roles]
        vr = subprocess.run(vcmd, capture_output=True, text=True)
        if vr.returncode != 0:
            mism_all.append("validator:exit_" + str(vr.returncode) + ":" + (vr.stdout.strip().splitlines() or ["?"])[-1][:200])
    for r in rows:
        fa = (r.get("expected", {}) or {}).get("frozen_annotation", {}) or {}
        if not fa.get("protected_mask"):
            mism_all.append(f"{r['case_id']}:sem_protected_mask (o contrato exact de O_composed exige PROTECTED congelado)")
    for r in rows:
        checked, mism = fz.verify_row_files(r, data_root)
        for c in checked:
            c["case_id"] = r["case_id"]
        referenced.extend(checked); mism_all.extend(f"{r['case_id']}:{m}" for m in mism)
    ids = {r["case_id"] for r in rows}
    dups = fz.duplicate_case_ids(rows)
    if dups:
        mism_all.append("manifest:case_id_duplicado:" + ",".join(dups))
    core = roles.get("core_cases", [])
    roles_issues = [c for c in core if c not in ids]
    if roles_issues:
        mism_all.append("roles:core_cases_desconhecidos:" + ",".join(roles_issues))
    missing_roles = sorted(ids - set(roles.get("roles", {}).keys()))
    if missing_roles:
        mism_all.append("roles:casos_sem_papel:" + ",".join(missing_roles))
    dirty = fz.git_dirty(root)
    frozen = (not mism_all) and (not dirty or args.allow_dirty)
    out_allow_dirty = bool(args.allow_dirty and dirty)
    if mism_all and not args.allow_placeholders:
        print("NÃO CONGELADO — divergências:\n  " + "\n  ".join(mism_all[:50]), file=sys.stderr)
        if not any("placeholder" in m for m in mism_all) or not args.allow_placeholders:
            sys.exit(1)
    out = {"version": 1, "gate": roles.get("gate", "G0"), "freeze_tag": args.tag, "created_utc": datetime.now(timezone.utc).isoformat(),
           "git_commit": fz.git_head(root), "git_dirty": dirty, "allow_dirty_used": out_allow_dirty, "frozen": bool(frozen),
           "files": {"manifest": {"path": args.manifest, "sha256": fz.sha256_file(args.manifest)},
                     "prereg": {"path": args.prereg, "sha256": fz.sha256_file(args.prereg)},
                     "roles": {"path": args.roles, "sha256": fz.sha256_file(args.roles)}},
           "core_cases": core, "n_cases": len(rows), "referenced_files": referenced, "null_stats_files": null_stats_files, "divergences": mism_all}
    with open(args.out, "w", encoding="utf-8") as f:
        json.dump(out, f, indent=1, ensure_ascii=False)
    print(f"[freeze_proto0] {args.out}: frozen={out['frozen']} commit={out['git_commit']} dirty={dirty} casos={len(rows)} arquivos={len(referenced)} divergências={len(mism_all)}")
    sys.exit(0 if frozen else 1)


if __name__ == "__main__":
    main()
