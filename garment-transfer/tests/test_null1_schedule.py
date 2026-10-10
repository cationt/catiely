"""CPU-only DD schedule checks; no torch, runtime import or model weights."""
import contextlib
import copy
import importlib.util
import io
import json
import math
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

import numpy as np


SCRIPT = Path(__file__).resolve().parents[1] / "tools/null1/dd_schedule.py"
SPEC = importlib.util.spec_from_file_location("null1_dd_schedule", SCRIPT)
dd = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(dd)


class DifferentialScheduleTests(unittest.TestCase):
    def test_fixed_step_counts_and_terminal_not_evaluated(self):
        reports = dd.all_reports()
        self.assertEqual([s["steps"] for s in reports["schedules"]], [4, 50, 40])
        for schedule in reports["schedules"]:
            self.assertEqual(len(schedule["rows"]), schedule["steps"])
            self.assertEqual(len(schedule["sigmas"]), schedule["steps"] + 1)
            self.assertEqual(schedule["terminal_sigma"], 0)
            self.assertGreater(schedule["ts_to"], 0)
            thresholds = [r["threshold"] for r in schedule["rows"]]
            self.assertEqual(thresholds[0], 1)
            self.assertGreater(thresholds[-1], 0)
            self.assertTrue(all(a > b for a, b in zip(thresholds, thresholds[1:])))

    def test_klein_four_source_equation_fixture(self):
        schedule = dd.schedule_report("klein4b_4steps")
        self.assertEqual((schedule["width"], schedule["height"]), (704, 1490))
        self.assertEqual(schedule["image_seq_len"], 4098)
        self.assertAlmostEqual(schedule["mu"], 2.291349484080522, places=12)
        # Independent double evaluation of pinned Flux2Scheduler/DD equations.
        expected = [1, .9673647533171841, .9080888281329161, .7670547650304415]
        np.testing.assert_allclose([r["threshold"] for r in schedule["rows"]], expected, rtol=0, atol=2e-7)
        self.assertAlmostEqual(schedule["sigma_min"], .0007533399352379832, places=9)

    def test_klein_base_fifty_is_comfy_diagnostic(self):
        schedule = dd.schedule_report("klein_base_50steps_comfy")
        self.assertEqual(schedule["image_seq_len"], 4096)
        self.assertAlmostEqual(schedule["mu"], 2.0233511571292637, places=12)
        expected = [.45623118327264567, .396302262988735, .3250848878107214,
                    .23905792110034868, .13306585895752]
        np.testing.assert_allclose([r["threshold"] for r in schedule["rows"]][-5:], expected, rtol=0, atol=2e-7)
        self.assertIn("not native DD", schedule["role"])
        self.assertNotAlmostEqual(schedule["sigma_min"], .001, places=6)

    def test_qie_matches_independent_simple_schedule(self):
        schedule = dd.schedule_report("qie_40steps")
        self.assertEqual(schedule["simple_indices"], list(range(999, 0, -25)))
        minimum = 3.1 * .001 / (1 + 2.1 * .001)
        expected = []
        for i in range(40):
            t = (1000 - 25 * i) / 1000
            sigma = 3.1 * t / (1 + 2.1 * t)
            expected.append((sigma - minimum) / (1 - minimum))
        np.testing.assert_allclose([r["threshold"] for r in schedule["rows"]], expected, rtol=0, atol=2e-7)
        self.assertAlmostEqual(schedule["ts_to"], minimum, places=8)

    def test_nonzero_terminal_takes_precedence_over_model_minimum(self):
        rows = dd.differential_thresholds([1, .6, .2], .01)
        self.assertEqual(len(rows), 2)
        self.assertEqual(rows[0]["threshold"], 1)
        self.assertAlmostEqual(rows[1]["threshold"], .5, places=6)

    def test_invalid_or_degenerate_schedules_fail(self):
        for sigmas, minimum in [([1], .01), ([1, math.nan, 0], .01),
                                ([1, 1, 0], .01), ([0, 1], .01),
                                ([1, -.1], .01), ([1, 0], 1),
                                ([1, 0], math.inf), ([1, 0], -.1)]:
            with self.subTest(sigmas=sigmas, minimum=minimum), self.assertRaises(ValueError):
                dd.differential_thresholds(sigmas, minimum)

    def test_unknown_configuration_is_not_accepted(self):
        with self.assertRaises(ValueError):
            dd.schedule_report("qie20")

    def test_report_copy_does_not_mutate_pins_or_configuration(self):
        original = copy.deepcopy(dd.SOURCES)
        report = dd.all_reports()
        report["sources"]["flux_model_sampling"]["shift"] = 99
        report["schedules"][0]["steps"] = 999
        self.assertEqual(dd.SOURCES, original)
        self.assertEqual(dd.schedule_report("klein4b_4steps")["steps"], 4)

    def test_source_hash_mismatch_is_fatal(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "comfy_extras/nodes_differential_diffusion.py"
            source.parent.mkdir()
            source.write_text("changed", encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "source pin mismatch"):
                dd.verify_sources(root)

    def test_cli_json_keeps_provenance_and_refuses_overwrite(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "schedule.json"
            captured = io.StringIO()
            with contextlib.redirect_stdout(captured):
                self.assertEqual(dd.main(["--route", "qie_40steps", "--out", str(output)]), 0)
            payload = json.loads(output.read_text(encoding="utf-8"))
            self.assertEqual(payload["sources"]["commit"], "daeb5e53681e2b10a3f0727d9ec5bc90784bee10")
            self.assertEqual(len(payload["schedules"]), 1)
            self.assertIn("DD threshold", captured.getvalue())
            before = output.read_bytes()
            with contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit) as error:
                dd.main(["--out", str(output)])
            self.assertEqual(error.exception.code, 2)
            self.assertEqual(output.read_bytes(), before)

    def test_report_never_imports_torch(self):
        # Block a new torch import explicitly, even when a wider test process has it installed.
        with patch.dict(sys.modules, {"torch": None}):
            self.assertEqual(len(dd.all_reports()["schedules"]), 3)


if __name__ == "__main__":
    unittest.main()
