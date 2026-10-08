#!/usr/bin/env python3
"""Testes do harness tools/measure_run.py (CPU, sem GPU). Rodar: python tests/test_measure_run.py

Cobertura:
  (a) ponta a ponta: comando curto → JSON com `commit_measurement.source`; em não-Windows a fonte é o proxy
      (`proxy_ram_used_plus_swap`) e `is_real_commit_counter` é false;
  (b) deadline: `--budget-s 0.6` com `sleep(5)` → `deadline_hit` true, veredito `FAIL:budget_exceeded`, filho morto;
  (c) unitário: `commit_info()` com plataforma monkeypatched devolve o proxy com `commit_proxy_mb` (ramo de fallback);
      também valida o layout de PERFORMANCE_INFORMATION.
Dependências: stdlib + psutil. Sem psutil, (a)/(b) são pulados com aviso e exit 0; (c) roda mesmo assim.
"""
import importlib.util
import json
import os
import platform
import subprocess
import sys
import tempfile
import time

HERE = os.path.dirname(os.path.abspath(__file__))
REAL_OS = platform.system()  # capturado ANTES de qualquer monkeypatch de platform.system
TOOL = os.path.join(os.path.dirname(HERE), "tools", "measure_run.py")

FAILS = 0


def report(name, ok, detail=""):
    global FAILS
    print(("ok   " if ok else "FAIL ") + name + (f" → {detail}" if detail else ""))
    if not ok:
        FAILS += 1


def have_psutil():
    r = subprocess.run([sys.executable, "-c", "import psutil"], capture_output=True, text=True)
    return r.returncode == 0


def load_module():
    spec = importlib.util.spec_from_file_location("measure_run_under_test", TOOL)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def run_measure(tmp, label, budget_s, child_code):
    args = [sys.executable, TOOL, "--label", label, "--budget-s", str(budget_s), "--interval-s", "0.2",
            "--out", tmp, "--", sys.executable, "-c", child_code]
    r = subprocess.run(args, capture_output=True, text=True, timeout=60)
    outs = sorted(f for f in os.listdir(tmp) if f.endswith(f"_{label}.json"))
    if r.returncode != 0 or not outs:
        return None, r
    with open(os.path.join(tmp, outs[-1]), encoding="utf-8") as f:
        return json.load(f), r


def child_dead(pid):
    try:
        import psutil
    except ImportError:
        return True
    if not psutil.pid_exists(pid):
        return True
    try:
        return psutil.Process(pid).status() == psutil.STATUS_ZOMBIE
    except psutil.Error:
        return True


def test_unit_commit_info():
    """(c) ramo de fallback de commit_info() com plataforma monkeypatched + layout do struct."""
    import ctypes
    mr = load_module()
    orig = mr.platform.system
    try:
        # 1) não-Windows → proxy puro
        mr.platform.system = lambda: "Linux"
        c = mr.commit_info(1000.0, 250.0)
        ok = (c["source"] == "proxy_ram_used_plus_swap" and c["total_mb"] == 1250.0 and c["commit_proxy_mb"] == 1250.0
              and c["limit_mb"] is None and c["peak_mb"] is None and "fallback_reason" not in c)
        report("unit_commit_info_fallback_linux", ok, {k: c[k] for k in ("source", "total_mb", "commit_proxy_mb")})
        # 2) "Windows" forçado numa máquina sem psapi → falha capturada → proxy + fallback_reason
        mr.platform.system = lambda: "Windows"
        c2 = mr.commit_info(10.0, 5.0)
        if REAL_OS == "Windows":
            ok2 = c2["source"] == "GetPerformanceInfo" and "commit_proxy_mb" not in c2 and c2["limit_mb"] and c2["total_mb"] > 0
            report("unit_commit_info_real_counter_windows", ok2, {k: c2.get(k) for k in ("source", "total_mb", "limit_mb")})
        else:
            ok2 = (c2["source"] == "proxy_ram_used_plus_swap" and c2["commit_proxy_mb"] == 15.0 and c2["total_mb"] == 15.0
                   and "fallback_reason" in c2)
            report("unit_commit_info_fallback_on_failure", ok2, {k: c2.get(k) for k in ("source", "commit_proxy_mb", "fallback_reason")})
        # 3) argumento explícito `system` também força o ramo
        c3 = mr.commit_info(1.0, 1.0, system="Darwin")
        report("unit_commit_info_system_kwarg", c3["source"] == "proxy_ram_used_plus_swap" and c3["commit_proxy_mb"] == 2.0)
    finally:
        mr.platform.system = orig
    # 4) layout: DWORD=4 bytes, 10×SIZE_T, 3×DWORD → 104 bytes em 64 bits (56 em 32 bits)
    expected = 104 if ctypes.sizeof(ctypes.c_size_t) == 8 else 56
    size = ctypes.sizeof(mr.PERFORMANCE_INFORMATION)
    report("unit_performance_information_sizeof", size == expected, f"{size} bytes (esperado {expected})")
    report("unit_performance_information_fields",
           [f for f, _ in mr.PERFORMANCE_INFORMATION._fields_] ==
           ["cb", "CommitTotal", "CommitLimit", "CommitPeak", "PhysicalTotal", "PhysicalAvailable", "SystemCache",
            "KernelTotal", "KernelPaged", "KernelNonpaged", "PageSize", "HandleCount", "ProcessCount", "ThreadCount"])
    # 5) sumário final: proxy → is_real false; real → true
    s_proxy = mr.commit_measurement_summary("proxy_ram_used_plus_swap")
    s_real = mr.commit_measurement_summary("GetPerformanceInfo")
    report("unit_commit_measurement_summary",
           s_proxy["is_real_commit_counter"] is False and s_real["is_real_commit_counter"] is True
           and s_proxy["source"] == "proxy_ram_used_plus_swap" and "note" in s_proxy)


def test_e2e_short_run(tmp):
    """(a) execução curta → JSON com commit_measurement e amostras coerentes."""
    res, r = run_measure(tmp, "t", 30, "import time; time.sleep(0.5)")
    if res is None:
        report("e2e_short_run", False, f"rc={r.returncode} stderr={r.stderr[-400:]}")
        return
    cm = res.get("commit_measurement", {})
    report("e2e_short_run_verdict", res["verdict"] == "ok" and res["deadline_hit"] is False and res["exit_code"] == 0,
           f"verdict={res['verdict']} exit={res['exit_code']}")
    report("e2e_commit_measurement_present", "source" in cm and "is_real_commit_counter" in cm and "note" in cm, cm.get("source"))
    sample_commit = res["samples"][0]["sys"]["commit"]
    report("e2e_sample_has_sys_commit", all(k in sample_commit for k in ("total_mb", "limit_mb", "peak_mb", "source")),
           list(sample_commit.keys()))
    report("e2e_no_toplevel_commit_proxy", "commit_proxy_mb" not in res["samples"][0]["sys"])
    if REAL_OS != "Windows":
        report("e2e_linux_source_is_proxy",
               cm["source"] == "proxy_ram_used_plus_swap" and cm["is_real_commit_counter"] is False
               and sample_commit["source"] == "proxy_ram_used_plus_swap" and "commit_proxy_mb" in sample_commit
               and abs(sample_commit["commit_proxy_mb"] - (res["samples"][0]["sys"]["ram_used_mb"] + res["samples"][0]["sys"]["swap_used_mb"])) < 1e-6
               and res["peak"]["commit_source"] == "proxy_ram_used_plus_swap",
               f"source={cm['source']} is_real={cm['is_real_commit_counter']}")
    else:
        report("e2e_windows_source_is_real",
               cm["source"] == "GetPerformanceInfo" and cm["is_real_commit_counter"] is True
               and "commit_proxy_mb" not in sample_commit and sample_commit["limit_mb"] > 0,
               f"source={cm['source']}")
    tree = res["samples"][0]["tree"]
    report("e2e_tree_private_source",
           tree.get("private_source") in ("private_bytes", "uss", "rss_fallback")
           and res["peak"].get("tree_private_source") in ("private_bytes", "uss", "rss_fallback"),
           f"{tree.get('private_source')} / peak={res['peak'].get('tree_private_source')}")
    report("e2e_peak_commit_fields", "commit_total_mb" in res["peak"] and res["peak"]["commit_total_mb"] > 0
           and "commit_source" in res["peak"])
    report("e2e_child_dead_after_normal_exit", child_dead(res["child_pid"]))


def test_e2e_budget(tmp):
    """(b) deadline rígido: sleep(5) com budget 0.6 s → FAIL:budget_exceeded e filho morto."""
    t0 = time.perf_counter()
    res, r = run_measure(tmp, "budget", 0.6, "import time; time.sleep(5)")
    dt = time.perf_counter() - t0
    if res is None:
        report("e2e_budget", False, f"rc={r.returncode} stderr={r.stderr[-400:]}")
        return
    report("e2e_budget_deadline_hit", res["deadline_hit"] is True and res["verdict"] == "FAIL:budget_exceeded",
           f"deadline_hit={res['deadline_hit']} verdict={res['verdict']} wall={res['wall_s']}")
    report("e2e_budget_returned_quickly", dt < 4.0, f"{dt:.2f}s (filho dormiria 5 s)")
    report("e2e_budget_exit_code_recorded", res["exit_code"] is not None and res["exit_code"] != 0 and res["kill_survivors"] == [],
           f"exit_code={res['exit_code']} survivors={res['kill_survivors']}")
    report("e2e_budget_child_dead", child_dead(res["child_pid"]), f"pid={res['child_pid']}")


def main():
    print(f"[test_measure_run] python={sys.version.split()[0]} os={REAL_OS}")
    test_unit_commit_info()
    if not have_psutil():
        print("SKIP: psutil não está instalado — testes ponta a ponta (a)/(b) pulados; só o teste unitário (c) foi executado. "
              "Instale com `pip install psutil`.")
    else:
        with tempfile.TemporaryDirectory() as tmp:
            test_e2e_short_run(tmp)
            test_e2e_budget(tmp)
    if FAILS:
        print(f"[test_measure_run] {FAILS} falha(s)")
        sys.exit(1)
    print("[test_measure_run] todos os testes ok")
    sys.exit(0)


if __name__ == "__main__":
    main()
