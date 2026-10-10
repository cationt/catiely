#!/usr/bin/env python3
"""O_null1 contract and audit regressions, synthetic CPU inputs only."""
import json
import os
import subprocess
import sys
import tempfile
import unittest

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _fixtures import AUDIT, FREEZE, build_case_dir, perfect_output, run_audit, save_mask, save_rgb
from occupancy_audit import derive_tol_from_null, read_null_stats
from null1.common import null_statistics


class NullContractTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = self.temp.name
        self.fx = build_case_dir(self.root)
        self.a = self.fx["files"]["easy_A.png"]
        self.output = os.path.join(self.root, "output.png")
        self.mask = os.path.join(self.root, "garment.png")
        save_rgb(self.output, perfect_output(self.fx["easy"]))
        save_mask(self.mask, self.fx["easy"]["G"])
        self.stats = self.fx["nulls"]["easy"]

    def audit(self, *options, profile="minimal"):
        args = [sys.executable, AUDIT, "--a", self.a, "--o-engine", self.output, "--garment-mask", self.mask,
                "--profile", profile, "--occlusion-none", "--contact-fringe-px", "2"]
        if profile == "g0":
            args += ["--manifest", self.fx["manifest"], "--case-id", "synth_easy_01", "--prereg", self.fx["prereg"],
                     "--roles", self.fx["roles"], "--freeze", self.fx["freeze"], "--data-root", self.root, "--allow-dirty-freeze"]
        else:
            for arg, mask in (("band-min", "BMIN"), ("band-max-body", "BMAXB"), ("free-space", "FS"),
                              ("body-coverable", "BC"), ("protected", "PR"), ("uncertain", "UNC")):
                args += ["--" + arg, self.fx["files"][f"easy_{mask}.png"]]
        proc = subprocess.run(args + list(options), capture_output=True, text=True)
        self.assertIn(proc.returncode, (0, 1, 3), proc.stderr)
        return json.loads(proc.stdout), proc.returncode

    def mutate_stats(self, change):
        with open(self.stats, encoding="utf-8") as stream:
            data = json.load(stream)
        change(data)
        path = os.path.join(self.root, "modified_null.json")
        with open(path, "w", encoding="utf-8") as stream:
            json.dump(data, stream)
        return path

    def test_copied_pixels_do_not_dilute_p995(self):
        a = np.zeros((100, 100, 3), np.uint8)
        reconstructed = a.copy(); reconstructed[0, :20] = 10
        support = np.zeros((100, 100), bool); support[0, :20] = True
        self.assertEqual(derive_tol_from_null(a, reconstructed, support=support), 10)
        self.assertEqual(derive_tol_from_null(a, reconstructed, support=np.ones_like(support)), 1)

    def test_support_is_not_implicitly_full_canvas(self):
        with self.assertRaisesRegex(ValueError, "support"):
            derive_tol_from_null(np.zeros((2, 2, 3)), np.zeros((2, 2, 3)))
        data, rc = self.audit("--a-ref", self.a)
        self.assertEqual(rc, 3)
        self.assertEqual(data["verdict_engine"], "INCONCLUSIVO:a_ref_support_required")

    def test_empty_support_is_rejected(self):
        mask = os.path.join(self.root, "empty.png")
        save_mask(mask, np.zeros((120, 80), bool))
        data, rc = self.audit("--a-ref", self.a, "--a-ref-support", mask)
        self.assertEqual((rc, data["verdict_engine"]), (3, "INCONCLUSIVO:a_ref_support_invalid"))

    def test_a_ref_crosscheck_uses_only_support(self):
        ref = self.fx["easy"]["A"].copy(); ref[100, 0] += 9
        ref_path = os.path.join(self.root, "ref.png"); save_rgb(ref_path, ref)
        support = np.zeros((120, 80), bool); support[100, 0] = True
        support_path = os.path.join(self.root, "support.png"); save_mask(support_path, support)
        data, rc = self.audit("--a-ref", ref_path, "--a-ref-support", support_path, "--null-stats", self.stats)
        self.assertEqual((rc, data["verdict_engine"]), (3, "INCONCLUSIVO:null_stats_inconsistent_with_a_ref"))

    def test_normative_null_stats_take_precedence(self):
        data, rc = self.audit("--a-ref", self.a, "--a-ref-full-canvas", "--null-stats", self.stats, "--tol-engine", "1")
        self.assertEqual(rc, 0)
        self.assertEqual((data["tol_engine"], data["tol_engine_source"]), (4, "null_stats"))
        self.assertEqual(data["engine"]["identity_reference"], "A")

    def test_crosscheck_plus_one_is_allowed(self):
        ref = os.path.join(self.root, "ref5.png"); save_rgb(ref, self.fx["easy"]["A"] + 5)
        data, rc = self.audit("--a-ref", ref, "--a-ref-full-canvas", "--null-stats", self.stats)
        self.assertEqual(rc, 0)
        self.assertEqual(data["tol_engine"], 4)

    def test_zone_above_cap_rejects_null(self):
        for zone in ("skin", "background", "hair_face", "occluders"):
            def change(data):
                data["tol_p995_by_zone"][zone] = 13
                data["counts"]["by_zone"][zone] = {"total": 1, "support": 1}
                data["statistics"]["by_zone"][zone] = {key: 13 for key in ("p50", "p95", "p99", "p995", "max")}
            with self.subTest(zone=zone):
                path = self.mutate_stats(change)
                data, rc = self.audit("--null-stats", path)
                self.assertEqual((rc, data["verdict_engine"]), (3, "INCONCLUSIVO"))
                self.assertIn("null_distribution", data["engine"]["missing_required_evidence"])

    def test_scalar_above_cap_rejects_null(self):
        path = self.mutate_stats(lambda data: data.update(tol_p995_support=13))
        data, rc = self.audit("--null-stats", path)
        self.assertEqual((rc, data["verdict_engine"]), (3, "INCONCLUSIVO"))

    def test_ceiling_cannot_be_changed_by_cli(self):
        for ceiling in (11, 13, 30):
            with self.subTest(ceiling=ceiling):
                data, rc = self.audit("--null-stats", self.stats, "--max-tol-engine", str(ceiling))
                self.assertEqual((rc, data["verdict_engine"]), (3, "INCONCLUSIVO:max_tol_engine_must_be_12"))

    def test_zone_absent_falls_back_to_scalar(self):
        path = self.mutate_stats(lambda data: data["tol_p995_by_zone"].pop("skin"))
        data, rc = self.audit("--null-stats", path)
        self.assertEqual(rc, 0)
        self.assertEqual(data["tol_engine_by_zone"]["skin"], 4)

    def test_zone_tolerances_drive_corresponding_tests(self):
        for zone, mask, metric in (("hair_face", "PR", "protected_pixel_identity"),
                                   ("skin", "BC", "uncovered_coverable_identity"),
                                   ("background", "FS", "unchanged_in_band_without_garment")):
            with self.subTest(zone=zone):
                output = perfect_output(self.fx["easy"])
                selection = self.fx["easy"][mask] & ~self.fx["easy"]["G"]
                output[selection] += 3
                save_rgb(self.output, output)
                low = self.mutate_stats(lambda data: data["tol_p995_by_zone"].update({zone: 1}))
                data, rc = self.audit("--null-stats", low)
                self.assertEqual(rc, 1)
                self.assertLess(data["engine"][metric], 1)
                data, rc = self.audit("--null-stats", self.stats)
                self.assertEqual(rc, 0)
                self.assertEqual(data["engine"][metric], 1)

    def test_g0_requires_frozen_normative_stats(self):
        data, rc = self.audit("--a-ref", self.a, "--a-ref-full-canvas", profile="g0")
        self.assertEqual(rc, 3)
        self.assertFalse(data["gate_eligible"])
        changed = self.mutate_stats(lambda data: data["route_config"].update(note="not_frozen"))
        data, rc = self.audit("--null-stats", changed, profile="g0")
        self.assertEqual((rc, data["verdict_engine"]), (1, "FAIL:frozen_reference_mismatch"))
        data, rc = self.audit("--null-stats", self.stats, profile="g0")
        self.assertEqual(rc, 0)
        self.assertTrue(data["gate_eligible"])

    def test_explicit_tolerance_restricted_to_minimal(self):
        data, rc = self.audit("--null-stats", self.stats, "--tol-engine", "4", profile="g0")
        self.assertEqual((rc, data["verdict_engine"]), (3, "INCONCLUSIVO:tol_engine_explicit_only_minimal"))

    def test_a_sha_is_bound_to_null(self):
        path = self.mutate_stats(lambda data: data["sha256"].update(a="0" * 64))
        data, rc = self.audit("--null-stats", path)
        self.assertEqual((rc, data["verdict_engine"]), (3, "INCONCLUSIVO:null_stats_invalid"))

    def test_generator_contract_is_consumed_without_translation(self):
        zones = {zone: self.stats + "." + zone + ".png" for zone in ("skin", "background", "hair_face", "occluders", "clothing")}
        generated = null_statistics(self.a, self.stats + ".png", self.stats + ".support.png", zones, {"route": "synthetic"})
        path = os.path.join(self.root, "generator_stats.json")
        with open(path, "w", encoding="utf-8") as stream:
            json.dump(generated, stream)
        parsed, scalar, by_zone = read_null_stats(path, generated["sha256"]["a"], 120 * 80)
        self.assertEqual(parsed, generated)
        self.assertEqual(scalar, 4)
        self.assertEqual(by_zone, dict.fromkeys(("skin", "background", "hair_face", "occluders"), 4))

    def test_occluder_identity_uses_occluder_tolerance(self):
        hard = self.fx["hard"]
        output = perfect_output(hard, hard["G_split"]); output[hard["FO"]] += 3
        save_rgb(self.output, output); save_mask(self.mask, hard["G_split"])
        with open(self.fx["nulls"]["hard"], encoding="utf-8") as stream:
            stats = json.load(stream)
        changed = os.path.join(self.root, "hard_low.json")
        stats["tol_p995_by_zone"]["occluders"] = 1
        with open(changed, "w", encoding="utf-8") as stream:
            json.dump(stats, stream)
        for path, expected in ((changed, 0.0), (self.fx["nulls"]["hard"], 1.0)):
            data, _ = run_audit(self.fx, "synth_hard_01", self.output, self.mask, profile="minimal", extra=[
                "--front-occluders", self.fx["files"]["hard_FO.png"], "--null-stats", path])
            self.assertEqual(data["engine"]["front_occluder_pixel_identity"], expected)

    def test_missing_support_file_is_inconclusive(self):
        data, rc = self.audit("--a-ref", self.a, "--a-ref-support", os.path.join(self.root, "missing.png"))
        self.assertEqual((rc, data["verdict_engine"]), (3, "INCONCLUSIVO:a_ref_support_invalid"))

    def test_freeze_requires_normative_null_stats(self):
        proc = subprocess.run([sys.executable, FREEZE, "--manifest", self.fx["manifest"], "--prereg", self.fx["prereg"],
                               "--roles", self.fx["roles"], "--tag", "synthetic", "--out", os.path.join(self.root, "missing_FREEZE.json"),
                               "--data-root", self.root, "--allow-dirty", "--skip-validator"], capture_output=True, text=True)
        self.assertEqual(proc.returncode, 1)
        self.assertIn("null_stats_missing", proc.stderr)

    def test_freeze_rejects_scalar_or_zone_above_ceiling(self):
        for target in ("support", "skin", "background", "hair_face", "occluders"):
            def change(data):
                if target == "support":
                    data["tol_p995_support"] = 13
                else:
                    data["tol_p995_by_zone"][target] = 13
                    data["counts"]["by_zone"][target] = {"total": 1, "support": 1}
                    data["statistics"]["by_zone"][target] = {key: 13 for key in ("p50", "p95", "p99", "p995", "max")}
            with self.subTest(target=target):
                path = self.mutate_stats(change)
                proc = subprocess.run([sys.executable, FREEZE, "--manifest", self.fx["manifest"], "--prereg", self.fx["prereg"],
                                       "--roles", self.fx["roles"], "--tag", "synthetic", "--out", os.path.join(self.root, "invalid_FREEZE.json"),
                                       "--data-root", self.root, "--allow-dirty", "--skip-validator", "--null-stats", path], capture_output=True, text=True)
                self.assertEqual(proc.returncode, 1)
                self.assertIn("null_distribution_not_credible:ceiling_12", proc.stderr)

    def test_malformed_null_stats_return_inconclusive(self):
        changes = (lambda data: data.update(sha256=None), lambda data: data.update(tol_p995_by_zone=[]),
                   lambda data: data.update(tol_p995_support=float("nan")), lambda data: data.update(tol_p995_support=True))
        for change in changes:
            with self.subTest(change=change):
                data, rc = self.audit("--null-stats", self.mutate_stats(change))
                self.assertEqual((rc, data["verdict_engine"]), (3, "INCONCLUSIVO:null_stats_invalid"))


if __name__ == "__main__":
    unittest.main()
