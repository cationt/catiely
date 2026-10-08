#!/usr/bin/env python3
"""summarize_runs.py — gera o registro legível por máquina (benchmark/measurements/*.json) a partir dos JSONs do measure_run.py
(e, se existirem, dos sidecars do runner), com medianas por estado e TODOS os runs listados (nenhum descartado).

Uso: python summarize_runs.py --runs-dir <W3Root\\runs> --label-prefix r1ei_kleinbase4b_easyinsert_bf16_1024_normal [--sidecars-dir <W3Root\\r1ei\\outputs>]
                              --candidate "R1-EI ..." --out benchmark/measurements/r1ei_...json [--config-json extra.json]
Métricas por run: wall_s, peak.vram_used_mb, peak.tree_rss_mb, peak.tree_private_mb, peak.sys_ram_used_mb, peak.swap_used_mb, peak.commit_total_mb,
exit_code, deadline_hit, verdict, commit_source. Sidecars: phases, vram_peak_overall_mb, versions, gpu.
"""
import argparse, glob, json, os, shlex, statistics as st, sys
from pathlib import PureWindowsPath

KEYS = {"wall_s": ("wall_s",), "vram_used_mb": ("peak", "vram_used_mb"), "tree_rss_mb": ("peak", "tree_rss_mb"), "tree_private_mb": ("peak", "tree_private_mb"),
        "sys_ram_used_mb": ("peak", "sys_ram_used_mb"), "swap_used_mb": ("peak", "swap_used_mb"), "commit_total_mb": ("peak", "commit_total_mb")}


def dig(d, path):
    for k in path:
        if not isinstance(d, dict) or k not in d:
            return None
        d = d[k]
    return d


def load_runs(runs_dir, label_prefix):
    runs = {"cold": [], "warm": []}
    for p in sorted(glob.glob(os.path.join(runs_dir, "*.json"))):
        try:
            with open(p, encoding="utf-8-sig") as f:
                j = json.load(f)
        except Exception:
            continue
        lab = str(j.get("label", ""))
        if lab != label_prefix and not lab.startswith(label_prefix + "_"):
            continue
        state = j.get("state") or ("cold" if "cold" in lab else "warm" if "warm" in lab else None)
        if state not in runs:
            continue
        rec = {"file": os.path.basename(p), "label": lab, "exit_code": j.get("exit_code"), "deadline_hit": j.get("deadline_hit"), "verdict": j.get("verdict"),
               "commit_source": dig(j, ("commit_measurement", "source")), "command": j.get("command")}
        for k, path in KEYS.items():
            rec[k] = dig(j, path)
        runs[state].append(rec)
    return runs


def summarize(runs):
    out = {}
    for state, lst in runs.items():
        if not lst:
            continue
        med = {}
        for k in KEYS:
            vals = [r[k] for r in lst if isinstance(r.get(k), (int, float))]
            if vals:
                med[k] = st.median(vals)
        out[state] = {"n": len(lst), "runs": lst, "median": med,
                      "all_exit_zero": all(r["exit_code"] == 0 for r in lst), "any_deadline": any(bool(r["deadline_hit"]) for r in lst),
                      "wall_s_min_max": [min(r["wall_s"] for r in lst), max(r["wall_s"] for r in lst)] if all(r.get("wall_s") is not None for r in lst) else None}
    return out


def load_sidecars(sidecars_dir, runs):
    """Associe somente --out dos runs selecionados; nunca varra todos os PNGs.

    measure_run serializa command com shlex.quote, inclusive no Windows.
    PureWindowsPath aceita separadores Windows/POSIX ao recuperar o basename.
    """
    res = []
    for lst in runs.values():
        for run in lst:
            cmd = shlex.split(run.get("command") or "")
            if "--out" not in cmd or cmd.index("--out") + 1 >= len(cmd):
                res.append({"measure_file": run["file"], "status": "unlinked:no_command_out"})
                continue
            name = PureWindowsPath(cmd[cmd.index("--out") + 1]).name + ".json"
            p = os.path.join(sidecars_dir, name)
            if not os.path.isfile(p):
                res.append({"measure_file": run["file"], "file": name, "status": "missing"})
                continue
            with open(p, encoding="utf-8-sig") as f:
                j = json.load(f)
            mode = ("segfree" if "--segmentation-free" in cmd else "masked" if "--masked" in cmd
                    else cmd[cmd.index("--mode") + 1] if "--mode" in cmd else None)
            if mode is not None and j.get("mode") != mode:
                raise ValueError("sidecar com modo divergente do run: " + name)
            res.append({"measure_file": run["file"], "file": name, "status": "linked", "verdict": j.get("verdict"), "mode": j.get("mode"), "phases": j.get("phases"), "vram_peak_overall_mb": j.get("vram_peak_overall_mb"),
                        "vram_reserved_peak_denoise_mb": j.get("vram_reserved_peak_denoise_mb"), "versions": j.get("versions"), "gpu": j.get("gpu"), "pin_check_ok": (j.get("pin_check") or {}).get("ok"),
                        "inputs_sha256": j.get("inputs_sha256"), "input_check": j.get("input_check"), "params": j.get("params"), "torch_vram": j.get("torch_vram")})
    return res


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--runs-dir", required=True); ap.add_argument("--label-prefix", required=True); ap.add_argument("--sidecars-dir")
    ap.add_argument("--candidate", required=True); ap.add_argument("--config-json", help="JSON com descrição da configuração/hardware a embutir")
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    runs = load_runs(a.runs_dir, a.label_prefix)
    if not runs["cold"] and not runs["warm"]:
        print("[summarize_runs] nenhum JSON com o prefixo informado", file=sys.stderr); sys.exit(2)
    rec = {"record_version": 1, "evidence_level": "MEDIDO NO HARDWARE-ALVO", "candidate": a.candidate, "config_label": a.label_prefix,
           "generated_from": {"runs_dir": a.runs_dir, "n_files": sum(len(v) for v in runs.values()), "sidecars_dir": a.sidecars_dir}, "runs": summarize(runs)}
    if a.config_json:
        rec.update(json.load(open(a.config_json, encoding="utf-8")))
    if a.sidecars_dir and os.path.isdir(a.sidecars_dir):
        rec["sidecars"] = load_sidecars(a.sidecars_dir, runs)
    os.makedirs(os.path.dirname(os.path.abspath(a.out)) or ".", exist_ok=True)
    json.dump(rec, open(a.out, "w", encoding="utf-8"), indent=1, ensure_ascii=False)
    for state, s in rec["runs"].items():
        print(f"[summarize_runs] {state}: n={s['n']} wall mediana={s['median'].get('wall_s')} VRAM={s['median'].get('vram_used_mb')} commit={s['median'].get('commit_total_mb')} exit0={s['all_exit_zero']} deadline={s['any_deadline']}")
    print(f"[summarize_runs] → {a.out}")


if __name__ == "__main__":
    main()
