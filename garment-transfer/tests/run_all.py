#!/usr/bin/env python3
"""Roda todos os testes CPU do harness (sem GPU, sem modelos). Uso: python tests/run_all.py"""
import os, subprocess, sys
HERE = os.path.dirname(os.path.abspath(__file__))
files = sorted(f for f in os.listdir(HERE) if f.startswith("test_") and f.endswith(".py"))
rc_all = 0
for f in files:
    print(f"\n===== {f} =====", flush=True)
    r = subprocess.run([sys.executable, os.path.join(HERE, f)])
    rc_all |= (r.returncode != 0)
    print(f"----- {f}: exit {r.returncode}")
print("\nRESULTADO GERAL:", "OK" if rc_all == 0 else "FALHAS")
sys.exit(rc_all)
