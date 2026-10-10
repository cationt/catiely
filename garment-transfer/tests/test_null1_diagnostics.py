"""D-058: synthetic CPU controls and mocked batch lifecycle; never runs ComfyUI/GPU."""
import copy
import sys
import tempfile
import unittest
from contextlib import ExitStack
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import numpy as np
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools/null1"))
import common as n
import comfy_null
import launch_server
import orchestrate
import provenance
import worker

ORDER = ("klein", "klein_resample_only", "klein_vae_native", "qie", "qie_resample_only",
         "qie_vae_native", "r1ei", "r1ei_resample_only", "fashn")
INCONCLUSIVE = "INCONCLUSIVE:null_distribution_not_credible"


class Controls(unittest.TestCase):
    def test_order_roles_and_original_workflow_pins(self):
        manifest = provenance.frozen()
        self.assertEqual(tuple(manifest["route_order"]), ORDER)
        self.assertEqual(tuple(orchestrate.plan()["routes"]), ORDER)
        self.assertEqual(manifest["workflows"]["klein"]["sha256"], "5ab1fbb9fdf7b9036213b4c0203f60f7f00c03b3ee0172aa6f8677d82683bd04")
        self.assertEqual(manifest["workflows"]["qie"]["sha256"], "6f336c222c68b9fd141d44d95a88d7c7f551e2177d6a6f9e8178e2e0222164a6")
        for route in ORDER:
            self.assertEqual(manifest["routes"][route]["normative"], route in n.NORMATIVE_ROUTES)

    def test_native_geometry_is_integer_crop_and_exact_paste(self):
        pixels = np.random.default_rng(1).integers(0, 256, (1536, 725, 3), dtype=np.uint8)
        A = Image.fromarray(pixels)
        native = A.crop((2, 0, 722, 1536))
        for route in ("klein_vae_native", "qie_vae_native"):
            geo = n.geometry(route)
            self.assertEqual(geo["internal"], [720, 1536])
            self.assertEqual(geo["box_on_A"], [2, 0, 722, 1536])
            with patch.object(Image.Image, "resize", side_effect=AssertionError("no resize")):
                O, support, _ = n.reproject(A, native, route)
            np.testing.assert_array_equal(np.asarray(O), pixels)
            self.assertEqual(support.sum(), 720 * 1536)
            self.assertFalse(support[:, :2].any())
            self.assertFalse(support[:, 722:].any())
            self.assertTrue(support[:, 2:722].all())

    def test_resample_comfy_inverses_equal_normative_inverses(self):
        A = Image.new("RGB", (725, 1536), (2, 5, 7))
        for base in ("klein", "qie"):
            geo = n.geometry(base)
            w, h = geo["internal"]
            native = Image.fromarray(np.random.default_rng(5).integers(0, 256, (h, w, 3), dtype=np.uint8))
            normal, support, _ = n.reproject(A, native, base)
            diagnostic, dsupport, dgeo = n.reproject(A, native, base+"_resample_only")
            self.assertEqual(dgeo, geo)
            np.testing.assert_array_equal(np.asarray(normal), np.asarray(diagnostic))
            np.testing.assert_array_equal(support, dsupport)

    def test_control_graph_edges_and_no_vae_in_resample_graphs(self):
        for base in ("klein", "qie"):
            resample = n.read_json(n.HERE / (base+"_resample_only_api.json"))
            expected = {"LoadImage", "SaveImage", "ImageScaleToTotalPixels", "ImageCrop"} if base == "klein" else {"LoadImage", "SaveImage", "FluxKontextImageScale"}
            self.assertEqual({node["class_type"] for node in resample.values()}, expected)
            self.assertEqual(resample["scale"]["inputs"]["image"], ["A", 0])
            if base == "klein":
                self.assertEqual(resample["crop"]["inputs"], {"image": ["scale", 0], "width": 704, "height": 1488, "x": 0, "y": 1})
                self.assertEqual(resample["scale"]["inputs"], n.read_json(n.HERE/"klein_api.json")["scale"]["inputs"])
            self.assertEqual(resample["save"]["inputs"]["images"], ["crop" if base == "klein" else "scale", 0])
            native = n.read_json(n.HERE / (base+"_vae_native_api.json"))
            self.assertNotIn("scale", native)
            self.assertEqual(native["crop"]["inputs"], {"image": ["A", 0], "width": 720, "height": 1536, "x": 2, "y": 0})
            self.assertEqual(native["encode"]["inputs"]["pixels"], ["crop", 0])
            self.assertEqual(native["decode"]["inputs"]["samples"], ["encode", 0])
            self.assertEqual(native["save"]["inputs"]["images"], ["decode", 0])

    def test_optional_vae_evidence_only_for_graphs_without_loader(self):
        paths = {"core": Path("synthetic-core"), "shared": Path("synthetic-shared")}
        for base, compression in (("klein", 16), ("qie", 8)):
            name = base+"_resample_only"
            graph = n.read_json(n.HERE/(name+"_api.json"))
            self.assertEqual(comfy_null.workflow_vae(name, paths), (None, None))
            self.assertIsNone(comfy_null.vae_evidence({}, graph))
            self.assertIsNone(launch_server.configure_vae({}, Path("unused"), None, None, None, None))
            native = n.read_json(n.HERE/(base+"_vae_native_api.json"))
            self.assertEqual(comfy_null.workflow_vae(base+"_vae_native", paths), comfy_null.workflow_vae(base, paths))
            with self.assertRaisesRegex(ValueError, "evidence required"):
                comfy_null.vae_evidence({}, native)
            with tempfile.TemporaryDirectory() as tmp:
                evidence = Path(tmp)/"vae.json"
                n.write_new(evidence, {"spatial_compression": compression})
                session = {"vae_evidence": str(evidence), "vae_spatial_compression": compression}
                self.assertEqual(comfy_null.vae_evidence(session, native)["spatial_compression"], compression)
                session["vae_spatial_compression"] = 999
                with self.assertRaises(ValueError):
                    comfy_null.vae_evidence(session, native)

    def test_r1ei_worker_996_1024_996_without_vae_or_extra_resize(self):
        with tempfile.TemporaryDirectory() as tmp:
            d = Path(tmp)
            pixels = np.random.default_rng(3).integers(0, 256, (1536, 725, 3), dtype=np.uint8)
            A = Image.fromarray(pixels)
            n.save_new(A, d/"synthetic.png")
            record = {}
            with patch.object(worker, "deterministic_torch", side_effect=AssertionError("no VAE")):
                worker.generate_r1ei_resample_only({"a": str(d/"synthetic.png"), "out": str(d)}, record)
            expected = A.crop((-136, 193, 860, 1189)).resize((1024, 1024), Image.Resampling.LANCZOS).resize((996, 996), Image.Resampling.LANCZOS)
            decoded = n.rgb(d/"native.png")
            np.testing.assert_array_equal(np.asarray(decoded), np.asarray(expected))
            with patch.object(Image.Image, "resize", side_effect=AssertionError("already resized in worker")):
                O, support, _ = n.reproject(A, decoded, "r1ei_resample_only")
            reference = A.copy(); reference.paste(expected, (-136, 193))
            np.testing.assert_array_equal(np.asarray(O), np.asarray(reference))
            self.assertEqual(support.sum(), 725 * 996)
            self.assertIs(record["normative"], False)
            self.assertNotIn("torch", sys.modules)

    def test_diagnostic_kind_is_rejected_by_unchanged_auditor(self):
        sys.path.insert(0, str(ROOT/"tools"))
        from occupancy_audit import read_null_stats
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp)/"diagnostic.json"
            n.write_new(path, {"schema_version": 1, "kind": "O_null1_diagnostic", "normative": False})
            with self.assertRaisesRegex(ValueError, "schema_or_kind"):
                read_null_stats(path, "0"*64, 1)


class Lifecycle(unittest.TestCase):
    def run_batch(self, directory, run):
        args = SimpleNamespace(out=directory, port=8197, deadline_s=10)
        with ExitStack() as stack:
            for name, value in (("local_git", {"dirty": False}), ("verify", {"a": "synthetic"}), ("verify_sources", {"ok": True}), ("worker", {})):
                stack.enter_context(patch.object(orchestrate, name, return_value=value))
            stack.enter_context(patch.object(comfy_null, "refuse_existing_server"))
            stack.enter_context(patch.object(orchestrate, "one_route", side_effect=run))
            rc = orchestrate.generate(args, {"core": directory, "w3": directory})
        return rc, n.read_json(next(directory.glob("*/batch.json")))

    def test_batch_runs_all_nine_in_order_after_inconclusive(self):
        for inconclusive in ((), ("klein",), ("klein", "qie", "r1ei")):
            seen = []
            def run(route, *args):
                seen.append(route)
                return {"normative": route in n.NORMATIVE_ROUTES, "verdict": INCONCLUSIVE if route in inconclusive else "ok"}
            with self.subTest(inconclusive=inconclusive), tempfile.TemporaryDirectory() as tmp:
                rc, batch = self.run_batch(Path(tmp), run)
                self.assertEqual(seen, list(ORDER))
                self.assertEqual(rc, 3 if inconclusive else 0)
                self.assertEqual(batch["verdict"], "INCONCLUSIVE" if inconclusive else "ok")
                self.assertEqual(batch["inconclusive_routes"], list(inconclusive))
                self.assertEqual([r["route"] for r in batch["routes"]], list(ORDER))

    def test_operational_error_still_stops_after_prior_inconclusive(self):
        for failure in (RuntimeError("deadline"), {"normative": False, "verdict": "FAIL:invalid"}):
            seen = []
            def run(route, *args):
                seen.append(route)
                if len(seen) == 1:
                    return {"normative": True, "verdict": INCONCLUSIVE}
                if isinstance(failure, Exception):
                    raise failure
                return failure
            with self.subTest(failure=failure), tempfile.TemporaryDirectory() as tmp:
                rc, batch = self.run_batch(Path(tmp), run)
                self.assertEqual(seen, list(ORDER[:2]))
                self.assertEqual(rc, 1)
                self.assertEqual(batch["verdict"], "FAIL:batch_stopped")
                self.assertEqual(batch["routes"][0]["verdict"], INCONCLUSIVE)

    def test_route_above_ceiling_returns_inconclusive_but_controls_have_no_ceiling(self):
        with tempfile.TemporaryDirectory() as tmp:
            d = Path(tmp); zones = d/"zones"; zones.mkdir()
            n.save_new(Image.new("RGB", (725, 1536)), d/"synthetic.png")
            hashes = {}
            for name in n.ZONES:
                n.save_mask(np.full((1536, 725), name == "skin"), zones/(name+".png"))
                hashes[name] = n.sha256(zones/(name+".png"))
            prov = {"a": str(d/"synthetic.png"), "manifest_sha256": "test", "environments": {k: {} for k in ("comfy", "r1ei", "r3")}}
            def fake_comfy(route, directory, *args):
                g = n.geometry(route)
                n.save_new(Image.new("RGB", tuple(g.get("native", g["internal"])), (30, 30, 30)), directory/"native.png")
            def fake_worker(job, python, directory, deadline):
                fake_comfy(job["kind"], directory)
                return {"normative": False}
            for route in ("klein", *[r for r in ORDER if r not in n.NORMATIVE_ROUTES]):
                with self.subTest(route=route), ExitStack() as stack:
                    stack.enter_context(patch.object(orchestrate, "unchanged"))
                    stack.enter_context(patch.object(comfy_null, "generate", side_effect=fake_comfy))
                    stack.enter_context(patch.object(orchestrate, "worker", side_effect=fake_worker))
                    if route != "klein":
                        stack.enter_context(patch.object(orchestrate, "validate_ceiling", side_effect=AssertionError("diagnostic must not apply ceiling")))
                    rec = orchestrate.one_route(route, d/route, {"w3": d}, prov, zones, {"masks_sha256": hashes}, route, 8197, 10)
                stats = n.read_json(d/route/"null_stats.json")
                sidecar = n.read_json(d/route/"sidecar.json")
                self.assertEqual(rec["verdict"], INCONCLUSIVE if route == "klein" else "ok")
                self.assertEqual(stats["tol_p995_support"], 30)
                self.assertIs(sidecar["normative"], route == "klein")
                self.assertEqual(stats["kind"], "O_null1" if route == "klein" else "O_null1_diagnostic")
                if route != "klein":
                    self.assertEqual(sidecar["null_validation"], "diagnostic_only:no_ceiling")


if __name__ == "__main__":
    unittest.main()
