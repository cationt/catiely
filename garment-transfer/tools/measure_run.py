#!/usr/bin/env python3
"""
measure_run.py — Harness reproduzível de medição de tempo/VRAM/RAM/commit para uma solicitação completa.

Uso típico (Windows ou Linux):
    python tools/measure_run.py --label qwen_edit_2509_q5 --budget-s 3600 --out runs/ -- python run_pipeline.py --a A.png --b B.png

O comando após "--" é executado como subprocesso. Enquanto roda, este script amostra:
  - VRAM usada/total da GPU (NVML, se pynvml estiver instalado) e processos na GPU
  - RSS e Commit (private bytes) do processo-filho e de toda a árvore de processos
  - RAM total do sistema usada / disponível, commit total (Windows: via psutil.virtual_memory + swap)
  - Hard faults (Windows: psutil Process.memory_info().num_page_faults é cumulativo; derivamos a taxa)
  - Tempo de parede total; mata a árvore ao exceder --budget-s (deadline rígido, não reinicia o relógio)

Saída: JSON com série temporal (amostras) + sumário (picos, duração, exit code, deadline_hit).
Nível de evidência produzido: MEDIDO NO HARDWARE onde foi executado — registre o inventário (tools/inventory_windows.ps1).

Dependências: psutil (obrigatório), pynvml (opcional; sem ele, VRAM fica como null).
"""
import argparse
import json
import os
import platform
import shlex
import subprocess
import sys
import time
from datetime import datetime, timezone

try:
    import psutil
except ImportError:  # pragma: no cover
    print("ERRO: instale psutil (pip install psutil)", file=sys.stderr)
    sys.exit(2)

try:
    import pynvml  # type: ignore
    _NVML = True
except Exception:
    _NVML = False


def nvml_init():
    if not _NVML:
        return None
    try:
        pynvml.nvmlInit()
        n = pynvml.nvmlDeviceGetCount()
        return [pynvml.nvmlDeviceGetHandleByIndex(i) for i in range(n)]
    except Exception:
        return None


def nvml_sample(handles):
    out = []
    if not handles:
        return out
    for i, h in enumerate(handles):
        try:
            mem = pynvml.nvmlDeviceGetMemoryInfo(h)
            name = pynvml.nvmlDeviceGetName(h)
            if isinstance(name, bytes):
                name = name.decode()
            util = None
            try:
                util = pynvml.nvmlDeviceGetUtilizationRates(h).gpu
            except Exception:
                pass
            procs = []
            try:
                for p in pynvml.nvmlDeviceGetComputeRunningProcesses(h):
                    procs.append({"pid": p.pid, "used_mb": (p.usedGpuMemory or 0) / 2**20})
            except Exception:
                pass
            out.append({
                "index": i, "name": name,
                "used_mb": mem.used / 2**20, "total_mb": mem.total / 2**20,
                "util_pct": util, "procs": procs,
            })
        except Exception as e:  # pragma: no cover
            out.append({"index": i, "error": str(e)})
    return out


def tree_mem(root: psutil.Process):
    """RSS, private/commit e page faults da árvore de processos (filho + descendentes)."""
    rss = 0
    priv = 0
    faults = 0
    pids = []
    try:
        procs = [root] + root.children(recursive=True)
    except psutil.Error:
        return {"rss_mb": None, "private_mb": None, "page_faults": None, "pids": []}
    for p in procs:
        try:
            mi = p.memory_full_info() if hasattr(p, "memory_full_info") else p.memory_info()
            rss += getattr(mi, "rss", 0)
            # Windows: private == commit charge do processo; Linux: uss como aproximação
            priv += getattr(mi, "private", getattr(mi, "uss", 0)) or 0
            faults += getattr(mi, "num_page_faults", 0) or 0
            pids.append(p.pid)
        except psutil.Error:
            continue
    return {"rss_mb": rss / 2**20, "private_mb": priv / 2**20, "page_faults": faults, "pids": pids}


def sys_mem():
    vm = psutil.virtual_memory()
    sm = psutil.swap_memory()
    d = {
        "ram_total_mb": vm.total / 2**20,
        "ram_used_mb": vm.used / 2**20,
        "ram_available_mb": vm.available / 2**20,
        "swap_total_mb": sm.total / 2**20,
        "swap_used_mb": sm.used / 2**20,
    }
    # Commit charge total (Windows expõe via psutil >= 5.x em virtual_memory? não; usamos used+swap_used como proxy e marcamos)
    d["commit_proxy_mb"] = d["ram_used_mb"] + d["swap_used_mb"]
    return d


def kill_tree(proc: psutil.Process):
    try:
        for c in proc.children(recursive=True):
            try:
                c.kill()
            except psutil.Error:
                pass
        proc.kill()
    except psutil.Error:
        pass


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--label", required=True, help="rótulo da medição (rota/config)")
    ap.add_argument("--budget-s", type=float, default=3600.0, help="deadline rígido em segundos (padrão 3600)")
    ap.add_argument("--interval-s", type=float, default=1.0, help="intervalo de amostragem")
    ap.add_argument("--out", default="runs", help="diretório de saída")
    ap.add_argument("--state", default="cold", choices=["cold", "warm", "cached"], help="estado declarado dos modelos antes da execução")
    ap.add_argument("--note", default="", help="observação livre (ex.: pagefile 32 GB, ComfyUI --reserve-vram 1)")
    ap.add_argument("cmd", nargs=argparse.REMAINDER, help="comando a executar após --")
    args = ap.parse_args()

    cmd = args.cmd
    if cmd and cmd[0] == "--":
        cmd = cmd[1:]
    if not cmd:
        ap.error("forneça o comando após --")

    os.makedirs(args.out, exist_ok=True)
    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    out_path = os.path.join(args.out, f"{ts}_{args.label}.json")

    handles = nvml_init()
    baseline = {"sys": sys_mem(), "gpu": nvml_sample(handles)}

    t0 = time.perf_counter()
    started_at = datetime.now(timezone.utc).isoformat()
    popen = subprocess.Popen(cmd)
    proc = psutil.Process(popen.pid)

    samples = []
    deadline_hit = False
    peak = {"vram_used_mb": 0.0, "tree_rss_mb": 0.0, "tree_private_mb": 0.0, "sys_ram_used_mb": 0.0, "swap_used_mb": 0.0}
    last_faults = None
    try:
        while True:
            el = time.perf_counter() - t0
            tm = tree_mem(proc)
            sm = sys_mem()
            gpu = nvml_sample(handles)
            fault_rate = None
            if tm["page_faults"] is not None and last_faults is not None:
                fault_rate = (tm["page_faults"] - last_faults) / max(args.interval_s, 1e-6)
            last_faults = tm["page_faults"]
            s = {"t_s": round(el, 3), "tree": tm, "sys": sm, "gpu": gpu, "page_fault_rate": fault_rate}
            samples.append(s)
            for g in gpu:
                if g.get("used_mb") is not None:
                    peak["vram_used_mb"] = max(peak["vram_used_mb"], g["used_mb"])
            if tm["rss_mb"] is not None:
                peak["tree_rss_mb"] = max(peak["tree_rss_mb"], tm["rss_mb"])
                peak["tree_private_mb"] = max(peak["tree_private_mb"], tm["private_mb"] or 0)
            peak["sys_ram_used_mb"] = max(peak["sys_ram_used_mb"], sm["ram_used_mb"])
            peak["swap_used_mb"] = max(peak["swap_used_mb"], sm["swap_used_mb"])

            if popen.poll() is not None:
                break
            if el > args.budget_s:
                deadline_hit = True
                kill_tree(proc)
                break
            time.sleep(args.interval_s)
    except KeyboardInterrupt:
        kill_tree(proc)
        raise
    finally:
        wall = time.perf_counter() - t0
        rc = popen.poll()
        result = {
            "label": args.label,
            "state": args.state,
            "note": args.note,
            "command": " ".join(shlex.quote(c) for c in cmd),
            "started_at_utc": started_at,
            "wall_s": round(wall, 3),
            "budget_s": args.budget_s,
            "deadline_hit": deadline_hit,
            "exit_code": rc,
            "verdict": "FAIL:budget_exceeded" if deadline_hit else ("ok" if rc == 0 else f"FAIL:exit_{rc}"),
            "host": {
                "platform": platform.platform(),
                "python": sys.version.split()[0],
                "cpu_count": psutil.cpu_count(logical=True),
                "ram_total_mb": psutil.virtual_memory().total / 2**20,
                "nvml_available": bool(handles),
            },
            "baseline": baseline,
            "peak": peak,
            "n_samples": len(samples),
            "samples": samples,
        }
        with open(out_path, "w", encoding="utf-8") as f:
            json.dump(result, f, indent=1)
        print(json.dumps({k: result[k] for k in ("label", "wall_s", "deadline_hit", "exit_code", "verdict", "peak")}, indent=1))
        print(f"[measure_run] gravado em {out_path}")
        if handles:
            try:
                pynvml.nvmlShutdown()
            except Exception:
                pass


if __name__ == "__main__":
    main()
