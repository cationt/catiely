"""Null preparation tests: synthetic RGB/masks, mocked lifecycle, no model imports/GPU."""
import ast
import copy
import importlib.util
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import numpy as np
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/"tools/null1"))
import common as n
import comfy
import offline
import orchestrate
import provenance
import worker


class Geometry(unittest.TestCase):
    def test_support_exact_routes(self):
        expected = {"r1ei": 725*996, "qie": 703*1536, "klein": 725*1534, "fashn": 725*1536}
        for route, pixels in expected.items():
            with self.subTest(route=route):
                self.assertEqual(n.support_for_geometry((725,1536), n.geometry(route)).sum(), pixels)

    def test_projection_never_pastes_insertion_mask(self):
        A = Image.new("RGB", (725,1536), (11,22,33))
        for route in ("r1ei", "klein", "qie", "fashn"):
            geo = n.geometry(route)
            native = Image.new("RGB", tuple(geo.get("unpad", geo["internal"])), (101,102,103))
            O, support, _ = n.reproject(A, native, route)
            self.assertTrue((np.asarray(O)[~support] == (11,22,33)).all())
            self.assertTrue((np.asarray(O)[support] == (101,102,103)).all())
        # R1-EI includes x=0 and x=724 inside crop, beyond historical insertion bbox.
        self.assertTrue(n.support_for_geometry(A.size, n.geometry("r1ei"))[500,0])

    def test_wrong_shape_fail_closed(self):
        with self.assertRaises(ValueError):
            n.geometry("qie", (544,960))
        with self.assertRaises(ValueError):
            n.reproject(Image.new("RGB",(725,1536)), Image.new("RGB",(544,960)), "qie")

    def test_pixel_center_support_boundaries(self):
        s = n.support_for_geometry((5,5), {"box_on_A":[1.2,.7,4.1,3.6]})
        self.assertEqual(np.argwhere(s).tolist(), [[y,x] for y in (1,2,3) for x in (1,2,3)])

    def test_parser_zones_no_hand_in_skin(self):
        labels = np.arange(18,dtype=np.uint8).reshape(3,6)
        zones = n.zones_from_labels(labels)
        self.assertEqual(labels[zones["skin"]].tolist(), [12,14,15,16])
        self.assertEqual(labels[zones["occluders"]].tolist(), [13])
        self.assertEqual(labels[zones["hair_face"]].tolist(), [1,2])
        self.assertFalse(np.any(zones["skin"] & zones["occluders"]))
        with self.assertRaises(ValueError):
            n.zones_from_labels(np.array([[18]],dtype=np.uint8))


class Statistics(unittest.TestCase):
    def test_small_support_not_diluted(self):
        with tempfile.TemporaryDirectory() as tmp:
            d=Path(tmp); A=np.zeros((100,100,3),np.uint8); O=A.copy(); O[0,0]=[3,7,19]
            support=np.zeros((100,100),bool); support[0,0]=True
            n.save_new(Image.fromarray(A),d/"A.png"); n.save_new(Image.fromarray(O),d/"O.png")
            n.save_mask(support,d/"support.png")
            zones={}
            for name in n.ZONES:
                path=d/(name+".png"); n.save_mask(support if name=="skin" else np.zeros_like(support),path);zones[name]=path
            result=n.null_statistics(d/"A.png",d/"O.png",d/"support.png",zones,{"test":"synthetic"})
            self.assertEqual(result["tol_p995_support"],19)
            self.assertEqual(result["tol_p995_by_zone"]["skin"],19)
            self.assertIsNone(result["tol_p995_by_zone"]["occluders"])
            self.assertEqual(result["statistics"]["support"]["histogram_0_255"][19],1)
            self.assertEqual(result["support_fraction"],.0001)
            self.assertEqual(result["sha256"]["a"],n.sha256(d/"A.png"))
            O[1,1]=255;n.save_new(Image.fromarray(O),d/"wrong.png")
            with self.assertRaisesRegex(ValueError,"outside support"):
                n.null_statistics(d/"A.png",d/"wrong.png",d/"support.png",zones,{"test":1})

    def test_quantiles_and_max_are_channel_max(self):
        d=n.distribution(np.array([0,2,4,8],dtype=np.int32))
        self.assertEqual(d["p50"],3)
        self.assertAlmostEqual(d["p995"],7.94)
        self.assertEqual(n.tolerance(d),8)

    def test_all_zone_ceilings_and_clothing_diagnostic(self):
        stats={"tol_p995_support":3,"tol_p995_by_zone":{k:3 for k in n.NORMATIVE_ZONES}}
        for zone in n.NORMATIVE_ZONES:
            bad=copy.deepcopy(stats);bad["tol_p995_by_zone"][zone]=13
            self.assertEqual(orchestrate.validate_ceiling(bad),{zone:13})
        self.assertEqual(orchestrate.validate_ceiling(stats),{})


class Execution(unittest.TestCase):
    def history(self):
        return {"prompt":[0,"id",{}],"status":{"completed":True,"status_str":"success",
                    "messages":[["execution_cached",{"prompt_id":"id","nodes":[]}]]}}

    def test_history_requires_empty_cache_messages_and_correct_graph(self):
        self.assertEqual(comfy.validate_history(self.history(),"id",{}),[])
        for mutate in (lambda r:r["status"].pop("messages"),
                       lambda r:r["status"]["messages"][0][1].update(nodes=["encode"]),
                       lambda r:r["status"].update(status_str="error"),
                       lambda r:r["prompt"].__setitem__(2,{"wrong":1})):
            r=self.history();mutate(r)
            with self.assertRaises(ValueError):comfy.validate_history(r,"id",{})

    def test_only_comfy_is_changed_metadata_is_ignored(self):
        graph={"A":{"class_type":"LoadImage","inputs":{"image":"A.jpg"}}}
        executed=copy.deepcopy(graph);executed["A"]["is_changed"]="fingerprint"
        self.assertEqual(comfy.execution_graph(executed),graph)
        executed["A"]["inputs"]["image"]="other.jpg"
        self.assertNotEqual(comfy.execution_graph(executed),graph)

    def test_route_failure_preserved_no_projection(self):
        with tempfile.TemporaryDirectory() as tmp:
            d=Path(tmp)/"klein"
            fake={"manifest_sha256":"x","environments":{"comfy":{}},"a":"never opened"}
            with patch.object(orchestrate,"unchanged"), patch.object(comfy,"generate",side_effect=RuntimeError("OOM")), patch.object(orchestrate,"reproject") as project:
                with self.assertRaisesRegex(RuntimeError,"OOM"):
                    orchestrate.one_route("klein",d,{},fake,Path(tmp),{},"unique",8197,30)
                project.assert_not_called()
            self.assertEqual(n.read_json(d/"sidecar.json")["verdict"],"FAIL:route")
            self.assertFalse((d/"null_stats.json").exists())

    def test_batch_stops_after_first_route_failure(self):
        from types import SimpleNamespace
        with tempfile.TemporaryDirectory() as tmp:
            args=SimpleNamespace(out=Path(tmp),port=8197,deadline_s=10)
            paths={"core":Path(tmp),"w3":Path(tmp)}
            with patch.object(orchestrate,"local_git",return_value={"dirty":False}), patch.object(orchestrate,"verify",return_value={"a":"synthetic"}), patch.object(orchestrate,"verify_sources",return_value={"ok":True}), patch.object(comfy,"refuse_existing_server"), patch.object(orchestrate,"worker",return_value={}), patch.object(orchestrate,"one_route",side_effect=RuntimeError("deadline")) as route:
                self.assertEqual(orchestrate.generate(args,paths),1)
                self.assertEqual(route.call_count,1)
                self.assertEqual(route.call_args.args[0],"klein")
            batch=n.read_json(next(Path(tmp).glob("*/batch.json")))
            self.assertEqual(batch["verdict"],"FAIL:batch_stopped")

    def test_offline_rejects_external_socket_and_dns(self):
        for event,args in [("socket.connect",(None,("8.8.8.8",443))), ("socket.getaddrinfo",("example.com",443)),("socket.bind",(None,("0.0.0.0",8197)))]:
            with self.assertRaises(RuntimeError):offline.guard(event,args)
        offline.guard("socket.connect",(None,("127.0.0.1",8197)))

    def test_parser_deadline_has_sidecar_and_stops_before_routes(self):
        from types import SimpleNamespace
        with tempfile.TemporaryDirectory() as tmp:
            args=SimpleNamespace(out=Path(tmp),port=8197,deadline_s=10)
            paths={"core":Path(tmp),"w3":Path(tmp)}
            with patch.object(orchestrate,"local_git",return_value={"dirty":False}), patch.object(orchestrate,"verify",return_value={"a":"synthetic"}), patch.object(orchestrate,"verify_sources",return_value={"ok":True}), patch.object(comfy,"refuse_existing_server"), patch.object(orchestrate,"worker",side_effect=RuntimeError("worker deadline")), patch.object(orchestrate,"one_route") as route:
                self.assertEqual(orchestrate.generate(args,paths),1)
                route.assert_not_called()
            sidecar=n.read_json(next(Path(tmp).glob("*/zones/sidecar.json")))
            self.assertEqual(sidecar["verdict"],"FAIL:worker")
            self.assertIn("deadline",sidecar["error"])

    def test_core_identity_rejects_changed_head_or_tracked_tree(self):
        with patch.object(provenance.subprocess,"check_output",side_effect=["other\n"]):
            with self.assertRaisesRegex(ValueError,"commit changed"):
                provenance.core_identity(Path("synthetic"),"pinned")
        with patch.object(provenance.subprocess,"check_output",side_effect=["pinned\n"," M nodes.py\n"]):
            with self.assertRaisesRegex(ValueError,"tree is dirty"):
                provenance.core_identity(Path("synthetic"),"pinned")

    @unittest.skipUnless(os.name == "nt", "Windows PowerShell parser")
    def test_powershell51_scripts_parse_without_execution(self):
        for file in n.HERE.glob("*.ps1"):
            content=file.read_bytes()
            self.assertTrue(content.startswith(b"\xef\xbb\xbf"))
            content.decode("utf-8-sig").encode("ascii")
            command = "$tokens=$null; $errors=$null; [System.Management.Automation.Language.Parser]::ParseFile('" + str(file).replace("'", "''") + "',[ref]$tokens,[ref]$errors) | Out-Null; if ($errors.Count) { $errors | Out-String | Write-Error; exit 1 }; if ($PSVersionTable.PSVersion.Major -ne 5) { exit 2 }"
            result=subprocess.run([str(Path(os.environ["WINDIR"])/"System32/WindowsPowerShell/v1.0/powershell.exe"),"-NoProfile","-Command",command],capture_output=True,text=True)
            self.assertEqual(result.returncode,0,result.stderr)

    def test_plan_never_imports_torch_or_runs_workers(self):
        with patch.object(orchestrate,"verify",side_effect=AssertionError("verify")), patch.object(orchestrate,"generate",side_effect=AssertionError("GPU")):
            p=orchestrate.plan()
        self.assertEqual(p["status"],"PREPARED_NOT_MEASURED")
        self.assertEqual(set(p["routes"]),{"klein","qie","r1ei","fashn"})
        self.assertNotIn("torch",sys.modules)

    def test_frozen_graphs_only_roundtrip_no_sampler(self):
        m=provenance.frozen()
        for entry in m["workflows"].values():
            graph=n.read_json(n.HERE/entry["file"])
            self.assertEqual(len(graph),6)
            self.assertEqual(graph["encode"]["inputs"]["pixels"],["scale",0])
            self.assertEqual(graph["decode"]["inputs"]["samples"],["encode",0])
            self.assertFalse(any("Sampler" in v["class_type"] for v in graph.values()))

    def test_sources_compile_without_importing_models(self):
        for path in n.HERE.glob("*.py"):
            ast.parse(path.read_text(encoding="utf-8"),filename=str(path))

    def test_pinned_fashn_transforms_on_synthetic_image_only(self):
        source=Path(os.environ.get("NULL1_TRANSFORMS_PATH", str(ROOT.parents[1]/"fashn-vton-1.5/src/fashn_vton/preprocessing/transforms.py")))
        if not source.exists():
            self.skipTest("set NULL1_TRANSFORMS_PATH to the pinned transforms.py for optional source integration")
        self.assertEqual(n.sha256(source,lf=True),provenance.frozen()["transforms_sha256_lf"])
        with tempfile.TemporaryDirectory() as tmp:
            d=Path(tmp)
            pixels=np.random.default_rng(2).integers(0,256,(1536,725,3),dtype=np.uint8)
            n.save_new(Image.fromarray(pixels),d/"synthetic.png")
            evidence={"runtime":{"transforms":str(source)}}
            worker.generate_fashn({"a":str(d/"synthetic.png"),"out":str(d)},evidence)
            actual=np.asarray(n.rgb(d/"native.png"))
            expected=np.asarray(Image.fromarray(pixels).resize((407,864),Image.Resampling.LANCZOS))
            np.testing.assert_array_equal(actual,expected)
            self.assertEqual(evidence["device"],"cpu")
            self.assertNotIn("torch",sys.modules)


if __name__ == "__main__":
    unittest.main()
