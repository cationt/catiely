#!/usr/bin/env python3
"""Regressoes R3 CPU: hashes, sidecars e fail-fast PowerShell com harness falso (sem modelos/GPU)."""
import importlib.util
import json
import os
from pathlib import Path
import shlex
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
R3 = ROOT / "tools" / "r3_fashn"


def module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


vi = module("r3_inputs", R3 / "verify_inputs.py")
sr = module("r3_summary", ROOT / "tools" / "r1ei" / "summarize_runs.py")


def write_json(path, data):
    path.write_text(json.dumps(data), encoding="utf-8")


class Inputs(unittest.TestCase):
    def test_identity_and_decision(self):
        with tempfile.TemporaryDirectory() as tmp:
            d = Path(tmp)
            a, b = d / "A.png", d / "B.png"
            a.write_bytes(b"person"); b.write_bytes(b"two-piece")
            expected = json.loads(vi.EXPECTED.read_text(encoding="utf-8"))
            expected["inputs_sha256"] = {"person": vi.sha256_file(a), "garment": vi.sha256_file(b)}
            ep, dp = d / "expected.json", d / "decision.json"
            write_json(ep, expected); write_json(dp, expected)
            with patch.object(vi, "EXPECTED", ep):
                self.assertTrue(vi.verify(a, b, dp)["ok"])
                for key, value in (("category", "one-pieces"), ("category", "bottoms"),
                                   ("garment_photo_type", "flat-lay"), ("scope", "full_outfit"),
                                   ("inputs_sha256", None)):
                    with self.subTest(key=key, value=value):
                        write_json(dp, dict(expected, **{key: value}))
                        with self.assertRaises(ValueError):
                            vi.verify(a, b, dp)
                write_json(dp, expected)
                for target in (a, b):
                    original = target.read_bytes()
                    target.write_bytes(b"x" * len(original))  # mesmo nome e tamanho
                    with self.assertRaises(ValueError):
                        vi.verify(a, b, dp)
                    target.write_bytes(original)
                with self.assertRaises(ValueError):
                    vi.verify(b, a, dp)
                b.unlink()
                with self.assertRaises(OSError):
                    vi.verify(a, b, dp)

    def test_runner_rejects_fake_baseline_before_loading_models(self):
        from PIL import Image
        with tempfile.TemporaryDirectory() as tmp:
            d = Path(tmp)
            for name in ("A.png", "B.png"):
                Image.new("RGB", (8, 8)).save(d / name)
            write_json(d / "decision.json", {})
            cmd = [sys.executable, str(R3 / "run_fashn_vton.py"), "--person", str(d / "A.png"),
                   "--garment", str(d / "B.png"), "--weights-dir", str(d / "absent"),
                   "--category", "tops", "--segmentation-free", "--out", str(d / "out.png"), "--dry-run"]
            r = subprocess.run(cmd + ["--inputs-decision", str(d / "decision.json")], capture_output=True, text=True)
            self.assertEqual(r.returncode, 2, r.stderr)
            rec = json.loads((d / "out.png.json").read_text(encoding="utf-8"))
            self.assertEqual(rec["verdict"], "FAIL:entradas_baseline_divergentes")
            self.assertNotIn("pin_check", rec)
            r = subprocess.run(cmd + ["--ort-provider", "cpu"], capture_output=True, text=True)
            self.assertEqual(r.returncode, 2)
            self.assertIn("unrecognized arguments", r.stderr)


class Sidecars(unittest.TestCase):
    def test_links_only_selected_runs_in_mixed_directory(self):
        with tempfile.TemporaryDirectory() as tmp:
            d = Path(tmp); prefix = "r3_fashn15_bf16_576x864_segfree"
            for label, name, mode in ((prefix, "chosen file", "segfree"),
                                      (prefix.replace("segfree", "masked"), "masked", "masked"),
                                      (prefix + "extra", "wrong-prefix", "segfree")):
                out = "C:\\path with spaces\\" + name + ".png"
                command = shlex.join(["python", "runner.py", "--out", out,
                                      "--segmentation-free" if mode == "segfree" else "--masked"])
                write_json(d / (name + ".json"), {"label": label + "_cold", "state": "cold", "command": command})
                write_json(d / (name + ".png.json"), {"mode": mode, "verdict": "ok"})
            for name, verdict in (("smoke", "SMOKE_OK"), ("orphan", "ok"), (prefix + "_cold_stale", "ok")):
                write_json(d / (name + ".png.json"), {"mode": "segfree", "verdict": verdict})
            runs = sr.load_runs(d, prefix)
            self.assertEqual(len(runs["cold"]), 1)
            sidecars = sr.load_sidecars(d, runs)
            self.assertEqual([s["file"] for s in sidecars], ["chosen file.png.json"])
            self.assertEqual(sidecars[0]["measure_file"], "chosen file.json")
            write_json(d / "chosen file.png.json", {"mode": "masked", "verdict": "ok"})
            with self.assertRaises(ValueError):
                sr.load_sidecars(d, runs)
            (d / "chosen file.png.json").unlink()
            self.assertEqual(sr.load_sidecars(d, runs)[0]["status"], "missing")
            runs["cold"][0]["command"] = None
            self.assertEqual(sr.load_sidecars(d, runs)[0]["status"], "unlinked:no_command_out")


# Este substituto apenas escreve JSONs e conta chamadas. Nao chama measure_run real, runner, torch ou NVML.
FAKE_MEASURE = r'''
import json, os, pathlib, sys
scenario = os.environ['R3_TEST_SCENARIO']
root = pathlib.Path(os.environ['R3_TEST_ROOT'])
with (root / 'calls.txt').open('a') as f: f.write('called\n')
if scenario == 'native_error': sys.exit(7)
args = sys.argv
label = args[args.index('--label')+1]
state = args[args.index('--state')+1]
runs = pathlib.Path(args[args.index('--out')+1])
child = args[args.index('--')+1:]
out = pathlib.Path(child[child.index('--out')+1] + '.json')
report = dict(label=label, state=state, exit_code=0, deadline_hit=False, verdict='ok')
sidecar = dict(mode='masked' if '--masked' in child else 'segfree', verdict='ok')
if scenario == 'child_error': report['exit_code'] = 6
if scenario == 'deadline': report['deadline_hit'] = True
if scenario == 'measure_verdict': report['verdict'] = 'FAIL:exit_6'
if scenario == 'missing_exit': del report['exit_code']
if scenario == 'missing_deadline': del report['deadline_hit']
if scenario == 'sidecar_oom': sidecar['verdict'] = 'FAIL:exception:OutOfMemoryError'
if scenario == 'sidecar_smoke': sidecar['verdict'] = 'SMOKE_OK'
if scenario == 'sidecar_dry': sidecar['verdict'] = 'DRY_RUN_OK'
if scenario == 'sidecar_mode': sidecar['mode'] = 'masked'
if scenario != 'missing_report':
    (runs / ('fixture_' + label + '.json')).write_text('{' if scenario == 'bad_report' else json.dumps(report))
if scenario != 'missing_sidecar':
    out.write_text('{' if scenario == 'bad_sidecar' else json.dumps(sidecar))
'''


@unittest.skipUnless(shutil.which("powershell"), "Windows PowerShell 5.1 indisponivel")
class PowerShell(unittest.TestCase):
    def ps(self, path, env=None):
        return subprocess.run(["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", str(path)],
                              capture_output=True, text=True, env=env)

    def test_ps51_parser_and_dual_smoke(self):
        with tempfile.TemporaryDirectory() as tmp:
            script = Path(tmp) / "parse.ps1"
            text = "$ErrorActionPreference = 'Stop'\nif ($PSVersionTable.PSVersion.Major -ne 5) { throw 'Requires PS5.1' }\n"
            for name in ("setup_r3.ps1", "bench_r3.ps1"):
                path = str(R3 / name).replace("'", "''")
                text += f"$tokens=$null; $errors=$null; [void][System.Management.Automation.Language.Parser]::ParseFile('{path}', [ref]$tokens, [ref]$errors)\nif ($errors.Count) {{ throw ($errors | Out-String) }}\n"
            script.write_text(text, encoding="utf-8-sig")
            result = self.ps(script)
            self.assertEqual(result.returncode, 0, result.stderr)
        setup = (R3 / "setup_r3.ps1").read_text(encoding="utf-8-sig")
        smokes = [line for line in setup.splitlines() if "& $py" in line and " --smoke" in line]
        self.assertEqual(len(smokes), 2)
        self.assertTrue(any("--masked" in line for line in smokes))
        self.assertTrue(any("--segmentation-free" in line for line in smokes))

    def test_bench_stops_before_next_run_on_every_failure(self):
        bench = (R3 / "bench_r3.ps1").read_text(encoding="utf-8-sig")
        function = "function Run-One" + bench.split("function Run-One", 1)[1].split("function Flush-Cache", 1)[0]
        scenarios = ("ok", "native_error", "child_error", "deadline", "measure_verdict", "missing_report",
                     "bad_report", "missing_exit", "missing_deadline", "sidecar_oom", "sidecar_smoke",
                     "sidecar_dry", "sidecar_mode", "missing_sidecar", "bad_sidecar")
        for scenario in scenarios:
            with self.subTest(scenario=scenario), tempfile.TemporaryDirectory(prefix="r3 test ") as tmp:
                d = Path(tmp)
                (d / "tools").mkdir(); (d / "runs").mkdir(); (d / "outputs").mkdir()
                (d / "tools" / "measure_run.py").write_text(FAKE_MEASURE, encoding="utf-8")
                harness = "$ErrorActionPreference='Stop'\n"
                values = {"GT": tmp, "py": sys.executable, "runs": str(d / "runs"), "outs": str(d / "outputs"),
                          "inputs": tmp, "WeightsDir": tmp, "dec": str(d / "decision.json"), "Category": "tops",
                          "GarmentPhotoType": "model", "labelBase": "r3_fashn15_bf16_576x864", "batchId": "unique", "noteBase": "test"}
                for key, value in values.items():
                    harness += "$" + key + "='" + value.replace("'", "''") + "'\n"
                harness += "$N=2; $BudgetS=1; $RamMap=''\n" + function
                harness += "Run-One 'segfree' 'cold' 1\nRun-One 'masked' 'warm' 1\n"
                script = d / "harness.ps1"; script.write_text(harness, encoding="utf-8-sig")
                r = self.ps(script, dict(os.environ, R3_TEST_ROOT=tmp, R3_TEST_SCENARIO=scenario))
                calls = (d / "calls.txt").read_text().splitlines()
                self.assertEqual(len(calls), 2 if scenario == "ok" else 1, r.stderr)
                self.assertEqual(r.returncode == 0, scenario == "ok", r.stderr)


if __name__ == "__main__":
    unittest.main()
