#!/usr/bin/env python3
"""
measure_run.py — Harness reproduzível de medição de tempo/VRAM/RAM/commit para uma solicitação completa.

Uso típico (Windows ou Linux):
    python tools/measure_run.py --label qwen_edit_2509_q5 --budget-s 3600 --out runs/ -- python run_pipeline.py --a A.png --b B.png

O comando após "--" é executado como subprocesso. Enquanto roda, este script amostra:
  - VRAM usada/total da GPU (NVML, se pynvml estiver instalado) e processos na GPU
  - RSS e "private" da árvore de processos (filho + descendentes):
      `tree.private_mb` = private bytes (Windows) / USS (Linux) — commit do processo SÓ no Windows;
      a origem fica em `tree.private_source` ∈ {"private_bytes", "uss", "rss_fallback"}
  - RAM total do sistema usada / disponível e swap/pagefile usado (psutil)
  - Commit charge do SISTEMA (`sys.commit`):
      * Windows: contador REAL via ctypes `psapi.GetPerformanceInfo` (PERFORMANCE_INFORMATION):
        `total_mb` = CommitTotal (Committed Bytes), `limit_mb` = CommitLimit (RAM + pagefile),
        `peak_mb` = CommitPeak; `source` = "GetPerformanceInfo".
      * Não-Windows, ou falha da chamada: PROXY `ram_used + swap_used` com
        `source` = "proxy_ram_used_plus_swap" e o campo explícito `commit_proxy_mb`.
        Esse proxy NÃO é o commit charge do Windows e não serve para dimensionar pagefile;
        o JSON final declara isso em `commit_measurement.is_real_commit_counter`.
  - Hard faults (Windows: psutil Process.memory_info().num_page_faults é cumulativo; derivamos a taxa)
  - Tempo de parede total; mata a árvore ao exceder --budget-s (deadline rígido, não reinicia o relógio)

Saída: JSON com série temporal (amostras) + sumário (picos, duração, exit code, deadline_hit, commit_measurement).
Picos: `peak.commit_total_mb` + `peak.commit_source`; `peak.tree_private_mb` + `peak.tree_private_source`.
Nível de evidência produzido: MEDIDO NO HARDWARE onde foi executado — registre o inventário (tools/inventory_windows.ps1).

Dependências: psutil (obrigatório para executar; `commit_info()` é importável sem ele), pynvml (opcional; sem ele, VRAM fica como null).
"""
import argparse
import ctypes
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
    psutil = None  # verificado em main(); commit_info()/_win_performance_info() não dependem de psutil

try:
    import pynvml  # type: ignore
    _NVML = True
except Exception:
    _NVML = False


COMMIT_SOURCE_REAL = "GetPerformanceInfo"
COMMIT_SOURCE_PROXY = "proxy_ram_used_plus_swap"


class PERFORMANCE_INFORMATION(ctypes.Structure):
    """psapi.h PERFORMANCE_INFORMATION. DWORD é fixado em c_uint32 (em Linux, wintypes.DWORD = c_ulong = 8 bytes,
    o que quebraria o layout); contagens de páginas são SIZE_T."""
    _fields_ = [
        ("cb", ctypes.c_uint32),
        ("CommitTotal", ctypes.c_size_t),
        ("CommitLimit", ctypes.c_size_t),
        ("CommitPeak", ctypes.c_size_t),
        ("PhysicalTotal", ctypes.c_size_t),
        ("PhysicalAvailable", ctypes.c_size_t),
        ("SystemCache", ctypes.c_size_t),
        ("KernelTotal", ctypes.c_size_t),
        ("KernelPaged", ctypes.c_size_t),
        ("KernelNonpaged", ctypes.c_size_t),
        ("PageSize", ctypes.c_size_t),
        ("HandleCount", ctypes.c_uint32),
        ("ProcessCount", ctypes.c_uint32),
        ("ThreadCount", ctypes.c_uint32),
    ]


def _win_performance_info():
    """Windows: commit charge real do sistema via psapi.GetPerformanceInfo. Lança exceção em qualquer falha."""
    psapi = ctypes.WinDLL("psapi", use_last_error=True)  # AttributeError fora do Windows
    fn = psapi.GetPerformanceInfo
    fn.argtypes = [ctypes.POINTER(PERFORMANCE_INFORMATION), ctypes.c_uint32]
    fn.restype = ctypes.c_int
    pi = PERFORMANCE_INFORMATION()
    pi.cb = ctypes.sizeof(pi)
    if not fn(ctypes.byref(pi), pi.cb):
        raise ctypes.WinError(ctypes.get_last_error())
    page = int(pi.PageSize)
    if page <= 0:
        raise RuntimeError("GetPerformanceInfo devolveu PageSize inválido")
    to_mb = lambda pages: int(pages) * page / 2**20
    return {
        "total_mb": to_mb(pi.CommitTotal),
        "limit_mb": to_mb(pi.CommitLimit),
        "peak_mb": to_mb(pi.CommitPeak),
        "source": COMMIT_SOURCE_REAL,
    }


def _commit_proxy(ram_used_mb, swap_used_mb):
    proxy = (ram_used_mb or 0.0) + (swap_used_mb or 0.0)
    return {
        "total_mb": proxy,
        "limit_mb": None,
        "peak_mb": None,
        "source": COMMIT_SOURCE_PROXY,
        "commit_proxy_mb": proxy,  # presente SÓ no fallback; nunca quando o contador real é usado
    }


def commit_info(ram_used_mb, swap_used_mb, system=None):
    """Commit charge do sistema em MB.

    Windows: contador real (GetPerformanceInfo). Não-Windows ou falha: proxy ram_used+swap_used
    (com `commit_proxy_mb` e, em caso de falha no Windows, `fallback_reason`).
    `system` permite forçar a plataforma (testes); por padrão usa platform.system() no momento da chamada.
    """
    if system is None:
        system = platform.system()
    if system == "Windows":
        try:
            return _win_performance_info()
        except Exception as e:
            fb = _commit_proxy(ram_used_mb, swap_used_mb)
            fb["fallback_reason"] = f"{type(e).__name__}: {e}"
            return fb
    return _commit_proxy(ram_used_mb, swap_used_mb)


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


_PRIVATE_SOURCE_RANK = {"private_bytes": 0, "uss": 1, "rss_fallback": 2}


def tree_mem(root):
    """RSS, private e page faults da árvore de processos (filho + descendentes).

    private_mb: private bytes (Windows) / USS (Linux) — commit do processo só no Windows.
    private_source: "private_bytes" | "uss" | "rss_fallback" (se misto entre processos, reporta o mais fraco).
    """
    rss = 0
    priv = 0
    faults = 0
    pids = []
    sources = set()
    try:
        procs = [root] + root.children(recursive=True)
    except psutil.Error:
        return {"rss_mb": None, "private_mb": None, "private_source": None, "page_faults": None, "pids": []}
    for p in procs:
        try:
            try:
                mi = p.memory_full_info()
            except (psutil.AccessDenied, AttributeError, NotImplementedError):
                mi = p.memory_info()  # Linux: smaps pode exigir privilégio; perde uss, mantém rss
            rss += getattr(mi, "rss", 0) or 0
            if hasattr(mi, "private"):          # Windows: private bytes == commit charge do processo
                priv += mi.private or 0
                sources.add("private_bytes")
            elif hasattr(mi, "uss"):            # Linux/macOS: USS (não é commit)
                priv += mi.uss or 0
                sources.add("uss")
            else:
                priv += getattr(mi, "rss", 0) or 0
                sources.add("rss_fallback")
            faults += getattr(mi, "num_page_faults", 0) or 0
            pids.append(p.pid)
        except psutil.Error:
            continue
    src = max(sources, key=lambda s: _PRIVATE_SOURCE_RANK[s]) if sources else None
    return {"rss_mb": rss / 2**20, "private_mb": priv / 2**20, "private_source": src, "page_faults": faults, "pids": pids}


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
    d["commit"] = commit_info(d["ram_used_mb"], d["swap_used_mb"])
    return d


def kill_tree(proc, popen=None, timeout_s=10.0):
    """Mata descendentes e o filho; espera (reap) para que exit_code e 'morto' sejam reais. Devolve pids sobreviventes."""
    try:
        children = proc.children(recursive=True)
    except psutil.Error:
        children = []
    for c in children:
        try:
            c.kill()
        except psutil.Error:
            pass
    try:
        proc.kill()
    except psutil.Error:
        pass
    alive = []
    if popen is not None:
        try:
            popen.wait(timeout=timeout_s)  # reap pelo Popen (não pelo psutil) para preservar o returncode
        except Exception:
            alive.append(popen.pid)
    try:
        _, still = psutil.wait_procs(children, timeout=timeout_s)
        alive.extend(p.pid for p in still)
    except psutil.Error:
        pass
    return alive


def _single_source(sources, mixed_prefix="mixed:"):
    sources = sorted(s for s in sources if s)
    if not sources:
        return None
    if len(sources) == 1:
        return sources[0]
    return mixed_prefix + ",".join(sources)


def commit_measurement_summary(commit_source):
    is_real = commit_source == COMMIT_SOURCE_REAL
    if is_real:
        note = ("commit charge real do sistema (Committed Bytes) via psapi.GetPerformanceInfo; "
                "sys.commit.limit_mb = Commit Limit (RAM + pagefile). Serve para dimensionar pagefile.")
    elif commit_source == COMMIT_SOURCE_PROXY:
        note = ("PROXY ram_used + swap_used (psutil), gravado em sys.commit.commit_proxy_mb. NÃO é o commit charge do Windows "
                "(fora do Windows não existe contador equivalente; no Windows indica falha do GetPerformanceInfo — ver "
                "sys.commit.fallback_reason). Não use para dimensionar pagefile.")
    elif commit_source and commit_source.startswith("mixed:"):
        note = "fontes misturadas entre amostras (GetPerformanceInfo falhou em parte da execução); tratar o pico como NÃO confiável."
    else:
        note = "sem amostras."
    return {"source": commit_source, "is_real_commit_counter": is_real, "note": note}


def main():
    if psutil is None:
        print("ERRO: instale psutil (pip install psutil)", file=sys.stderr)
        sys.exit(2)
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
    kill_survivors = []
    peak = {
        "vram_used_mb": 0.0, "tree_rss_mb": 0.0,
        "tree_private_mb": 0.0, "tree_private_source": None,
        "sys_ram_used_mb": 0.0, "swap_used_mb": 0.0,
        "commit_total_mb": 0.0, "commit_source": None,
    }
    commit_sources = set()
    private_sources = set()
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
                private_sources.add(tm["private_source"])
            peak["sys_ram_used_mb"] = max(peak["sys_ram_used_mb"], sm["ram_used_mb"])
            peak["swap_used_mb"] = max(peak["swap_used_mb"], sm["swap_used_mb"])
            c = sm["commit"]
            if c.get("total_mb") is not None:
                peak["commit_total_mb"] = max(peak["commit_total_mb"], c["total_mb"])
            commit_sources.add(c.get("source"))

            if popen.poll() is not None:
                break
            if el > args.budget_s:
                deadline_hit = True
                kill_survivors = kill_tree(proc, popen)
                break
            time.sleep(args.interval_s)
    except KeyboardInterrupt:
        kill_tree(proc, popen)
        raise
    finally:
        wall = time.perf_counter() - t0
        rc = popen.poll()
        peak["commit_source"] = _single_source(commit_sources)
        peak["tree_private_source"] = _single_source(private_sources)
        result = {
            "label": args.label,
            "state": args.state,
            "note": args.note,
            "command": " ".join(shlex.quote(c) for c in cmd),
            "child_pid": popen.pid,
            "started_at_utc": started_at,
            "wall_s": round(wall, 3),
            "budget_s": args.budget_s,
            "deadline_hit": deadline_hit,
            "kill_survivors": kill_survivors,
            "exit_code": rc,
            "verdict": "FAIL:budget_exceeded" if deadline_hit else ("ok" if rc == 0 else f"FAIL:exit_{rc}"),
            "host": {
                "platform": platform.platform(),
                "os": platform.system(),
                "python": sys.version.split()[0],
                "cpu_count": psutil.cpu_count(logical=True),
                "ram_total_mb": psutil.virtual_memory().total / 2**20,
                "nvml_available": bool(handles),
            },
            "commit_measurement": commit_measurement_summary(peak["commit_source"]),
            "baseline": baseline,
            "peak": peak,
            "n_samples": len(samples),
            "samples": samples,
        }
        with open(out_path, "w", encoding="utf-8") as f:
            json.dump(result, f, indent=1)
        print(json.dumps({k: result[k] for k in ("label", "wall_s", "deadline_hit", "exit_code", "verdict", "commit_measurement", "peak")}, indent=1))
        print(f"[measure_run] gravado em {out_path}")
        if handles:
            try:
                pynvml.nvmlShutdown()
            except Exception:
                pass


if __name__ == "__main__":
    main()
