"""D-059 CPU tests. Synthetic derivations only; real lot tests are read-only.

Never subtract real native/reference images or write a real Part 2 result here.
"""
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
from types import SimpleNamespace
from unittest.mock import patch

import numpy as np
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"tools/null1"))
sys.path.insert(0,str(ROOT/"tools"))
import common as n
import derive as d
import null_geometry as g
import orchestrate as o
import provenance as p
import comfy_null as comfy
import launch_server


class Geometry(unittest.TestCase):
    def test_part2_grids_and_source_boxes(self):
        expected = {"klein_g0":(720,1536),"qie_g0":(688,1504),"r1ei_g0":(1024,1024),
                    "klein_1mp_fallback":(704,1488),"fashn_g0":(407,864)}
        manifest = p.frozen()
        for name,spec in manifest["part2"]["configurations"].items():
            grid = g.forward_grid(spec["base_route"],(725,1536),spec["geometry"])
            self.assertEqual((grid["width"],grid["height"]),expected[name])
            self.assertIsNone(grid["contact_fringe_px_internal"])
        self.assertEqual(g.forward_grid("klein",(725,1536))["box_on_A"],[2,0,722,1536])
        self.assertEqual(g.forward_grid("qie",(725,1536),{"policy":"kontext_table"})["box_on_A"],[11,0,714,1536])

    def test_generic_sizes_and_g0_distinct_tuple(self):
        self.assertEqual(n.geometry("klein",(641,977),{"policy":"crop16"})["internal"],[640,976])
        self.assertEqual(n.geometry("qie",(800,1200),{"policy":"544x960"})["internal"],[544,960])
        self.assertEqual(g.forward_grid("r1ei",(1000,800),{"insertion_bbox":[100,200,300,500]})["box_on_A"],[20,170,380,530])
        self.assertEqual(n.geometry("klein_vae_native",(641,977))["box_on_A"],[0,0,640,976])
        with self.assertRaisesRegex(ValueError,"explicit 1MP"):
            g.forward_grid("klein",(1600,1600))
        self.assertEqual(g.forward_grid("klein",(1600,1600),{"policy":"1mp"})["width"],1024)

    def test_smoke_only_above_one_mp(self):
        self.assertFalse(g.forward_grid("klein",(1024,1024))["memory_smoke_required"])
        self.assertTrue(g.forward_grid("klein",(725,1536))["memory_smoke_required"])

    def test_r1ei_validity_nearest_and_no_erosion_normative(self):
        grid = g.forward_grid("r1ei",(725,1536),{"crop_box":[-136,193,860,1189]})
        support = g.validity_support(grid)
        expected = np.asarray(Image.new("L",(725,1536),255).crop((-136,193,860,1189)).resize((1024,1024),Image.Resampling.NEAREST)) == 255
        np.testing.assert_array_equal(support,expected)
        self.assertFalse(support[:,0].any())
        for radius in (4,8):
            self.assertLess(d.eroded_validity(support,radius).sum(),support.sum())
            self.assertEqual(d.eroded_validity(support,radius)[0].sum(),support[0].sum()-2*radius)

    def test_rounding_fringe_and_keypoints(self):
        grid = g.forward_grid("klein",(725,1536),{"contact_fringe_px":8})
        self.assertEqual(grid["contact_fringe_px_internal"],8)
        self.assertNotIn("thresholds",grid)
        points,count = g.forward_keypoints([[1,4,.9],[2,4,.9],[721,1500,.8],[722,4,.9]],grid)
        self.assertEqual(count,2)
        np.testing.assert_array_equal(points,[[0,4,.9],[719,1500,.8]])
        q = g.forward_grid("qie",(725,1536),{"policy":"kontext_table","contact_fringe_px":8})
        self.assertEqual(q["contact_fringe_px_internal"],8)

    def test_binary_masks_and_unknown_parameters_fail(self):
        grid = g.forward_grid("klein",(32,32))
        with self.assertRaises(ValueError):g.forward_mask(np.zeros((32,32),np.uint8),grid)
        with self.assertRaises(ValueError):g.forward_mask(np.zeros((33,32),bool),grid)
        with self.assertRaises(ValueError):g.forward_grid("qie",(32,32),{"surprise":True})
        with self.assertRaises(ValueError):g.forward_grid("r1ei",(32,32))

    def test_fashn_geometry_matches_pinned_transform_on_synthetic_images(self):
        src = os.environ.get("R3_VTON_SRC")
        if not src:self.skipTest("R3_VTON_SRC is needed for pinned CPU integration")
        path = Path(src)/"fashn_vton/preprocessing/transforms.py"
        manifest = p.frozen()
        self.assertEqual(n.sha256(path,lf=True),manifest["transforms_sha256_lf"])
        spec = importlib.util.spec_from_file_location("d059_transforms",path)
        module = importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
        for size in ((725,1536),(1600,900),(200,300),(864,864)):
            pre = module.AspectPreserveResize((864,864),"fit","pil")(Image.new("RGB",size),allow_upsampling=False)
            pad = module.ResizePad((576,864),"opencv")
            output = pad.unpad(Image.fromarray(pad(np.asarray(pre),mem_padding=True)))
            grid = g.forward_grid("fashn",size)
            self.assertEqual(output.size,(grid["width"],grid["height"]))


class Statistics(unittest.TestCase):
    def data(self):
        delta = np.zeros((200,500),np.int32)
        support = np.ones(delta.shape,bool)
        zones = {k:np.zeros(delta.shape,bool) for k in n.ZONES}
        return delta,support,zones

    def test_small_tail_informative_scalar_applied_and_fractions(self):
        delta,support,zones = self.data()
        zones["occluders"][0,:100] = True;delta[0,:100] = 30
        stats = d.summarize_delta(delta,support,zones)
        self.assertEqual(stats["tol_p995_support"],1)
        self.assertEqual(stats["tol_p995_by_zone"]["occluders"],30)
        self.assertFalse(stats["zone_tolerance_normative"]["occluders"])
        self.assertEqual(stats["tol_applied_by_zone"]["occluders"],1)
        self.assertEqual(stats["counts"]["by_zone"]["occluders"],{"total":100,"support":100,"tail":.5})
        self.assertEqual(stats["frac_above_tol"]["by_zone"]["occluders"],1)
        self.assertEqual(d.ceiling_excess(stats),{})

    def test_tail_boundary_100_is_normative_and_cap_not_forced(self):
        delta,support,zones = self.data()
        zones["skin"][:40] = True;delta[:40] = 13
        stats = d.summarize_delta(delta,support,zones)
        self.assertTrue(stats["zone_tolerance_normative"]["skin"])
        self.assertEqual(stats["counts"]["by_zone"]["skin"]["tail"],100)
        self.assertEqual(d.ceiling_excess(stats),{"support":13,"skin":13})

    def test_padding_not_diluting_scalar_or_zones(self):
        delta,support,zones = self.data();support[:]=False;support[50,50]=True;delta[50,50]=24
        zones["skin"][:]=True
        stats = d.summarize_delta(delta,support,zones)
        self.assertEqual(stats["tol_p995_support"],24)
        self.assertEqual(stats["tol_p995_by_zone"]["skin"],24)
        self.assertEqual(stats["counts"]["by_zone"]["skin"]["support"],1)
        self.assertIsNone(stats["tol_p995_by_zone"]["occluders"])
        self.assertIsNone(stats["frac_above_tol"]["by_zone"]["occluders"])
        self.assertEqual(d.ceiling_excess(stats),{"support":24})

    def test_empty_support_rejected(self):
        delta,support,zones = self.data();support[:]=False
        with self.assertRaisesRegex(ValueError,"empty internal"):
            d.summarize_delta(delta,support,zones)

    def test_prediction_uses_informative_values_without_changing_them(self):
        stats={"tol_p995_support":10,"tol_p995_by_zone":{"skin":12,"occluders":15}}
        result=d.prediction_check(stats,{"support":[7,9],"skin":[7,7],"occluders":[10,13]})
        self.assertTrue(result["investigate_before_accepting"])
        self.assertEqual(result["deviations"]["support"]["distance"],1)
        self.assertEqual(stats["tol_p995_by_zone"]["occluders"],15)

    def test_schema2_hashes_and_internal_canvas(self):
        with tempfile.TemporaryDirectory() as temp:
            out=Path(temp); grid=g.forward_grid("klein",(35,35))
            n.save_new(Image.new("RGB",(35,35)),out/"A.png")
            n.save_new(Image.new("RGB",(32,32)),out/"A_forward.png")
            n.save_new(Image.new("RGB",(32,32),(1,2,7)),out/"O.png")
            n.save_mask(np.ones((32,32),bool),out/"support.png")
            zones={k:out/(k+".png") for k in n.ZONES}
            for file in zones.values():n.save_mask(np.ones((32,32),bool),file)
            stats=d.null_statistics_v2(out/"A.png",out/"A_forward.png",out/"O.png",out/"support.png",zones,grid,{"route":"synthetic"})
            self.assertEqual(stats["schema_version"],2)
            self.assertEqual(stats["counts"]["canvas"],1024)
            self.assertEqual(stats["tol_p995_support"],7)
            self.assertEqual(stats["sha256"]["a_forward"],n.sha256(out/"A_forward.png"))
            self.assertEqual(stats["sha256"]["a"],n.sha256(out/"A.png"))
            self.assertFalse(stats["gate_eligible"])


class PinsAndLifecycle(unittest.TestCase):
    def test_entire_lot_manifest_exact_and_read_only(self):
        manifest=p.frozen();pin=manifest["part2"]["source_lot"]
        self.assertEqual(pin["file_count"],183)
        for name in n.ROUTE_ORDER:
            for file in ("native.png","support.png",*[z+".png" for z in n.ZONES]):
                self.assertIn(name+"/"+file,pin["files"])
        self.assertIn("r1ei/A_crop_1024.png",pin["files"])
        self.assertEqual(d.verify_lot(ROOT/pin["path"],pin)["file_count"],183)

    def test_tampering_missing_extra_files_and_inplace_output_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            source=Path(temp)/"source";source.mkdir();(source/"pin.bin").write_bytes(b"original")
            pin={"file_count":1,"files":{"pin.bin":n.sha256(source/"pin.bin")}}
            d.verify_lot(source,pin)
            for output in (source,source/"derived",source.parent):
                with self.assertRaises(ValueError):d.safe_output(source,output)
            self.assertEqual(d.safe_output(source,source.parent/"derived"),source.parent/"derived")
            (source/"pin.bin").write_bytes(b"changed")
            with self.assertRaisesRegex(ValueError,"SHA256"):d.verify_lot(source,pin)
            (source/"extra").write_bytes(b"x")
            with self.assertRaisesRegex(ValueError,"file set"):d.verify_lot(source,pin)

    def test_prepared_workflow_changes_only_A_crop_and_pins_code(self):
        manifest=p.frozen()
        original=n.read_json(n.HERE/"klein_benchmark_source_api.json")
        crop=n.read_json(n.HERE/"klein_g0_crop_api.json")
        self.assertEqual(set(original),set(crop))
        self.assertEqual([k for k in original if original[k]!=crop[k]],["92:111"])
        self.assertEqual(crop["92:111"]["inputs"],{"image":["76",0],"width":720,"height":1536,"x":2,"y":0})
        self.assertEqual(crop["92:110"],original["92:110"])
        self.assertEqual(crop["92:85"],original["92:85"])
        self.assertIn("../null_geometry.py",o.code_identity())
        self.assertEqual(manifest["shared_code"]["null_geometry"]["sha256"],n.sha256(ROOT/"tools/null_geometry.py",lf=True))

    def test_derive_dispatch_never_reaches_generation_or_verify(self):
        with patch.object(d,"derive",return_value=0) as derive,patch.object(o,"generate") as gen,patch.object(o,"verify") as verify,patch.object(o,"install"):
            self.assertEqual(o.main(["--mode","Derive"]),0)
            derive.assert_called_once();gen.assert_not_called();verify.assert_not_called()

    def test_cpu_source_has_no_model_network_subprocess_or_reproject_calls(self):
        for module in (d,g):
            tree=ast.parse(Path(module.__file__).read_text(encoding="utf-8"))
            imported=set()
            for node in ast.walk(tree):
                if isinstance(node,ast.Import):imported.update(x.name.split('.')[0] for x in node.names)
                if isinstance(node,ast.ImportFrom):imported.add((node.module or '').split('.')[0])
                if isinstance(node,ast.Call) and isinstance(node.func,ast.Name):self.assertNotEqual(node.func.id,"reproject")
            self.assertFalse(imported & {"av","torch","diffusers","transformers","worker","requests","subprocess"})

    def test_synthetic_one_part2_fashn_is_definition_not_measurement(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);src=root/"source";(src/"fashn").mkdir(parents=True);(src/"zones").mkdir()
            n.save_new(Image.new("RGB",(725,1536),(1,2,3)),root/"A.png")
            n.save_new(Image.new("RGB",(407,864),(1,2,3)),src/"fashn/native.png")
            n.write_new(src/"fashn/null_stats.json",{"route_config":{"synthetic":True}})
            for zone in n.ZONES:n.save_mask(np.ones((1536,725),bool),src/"zones"/(zone+".png"))
            rec=d.one_part2("fashn_g0",root/"derived",src,root/"A.png",p.frozen(),{}, {})
            stats=n.read_json(root/"derived/null_stats.json")
            self.assertEqual(rec["verdict"],"ok")
            self.assertEqual(stats["operator"],"identity_no_reconstruction")
            self.assertFalse(stats["measured"])
            self.assertTrue(stats["provisional_until_O_null2"])
            self.assertEqual(stats["tol_p995_support"],1)

    def test_synthetic_batch_continues_inconclusive_and_stops_operational_error(self):
        for operational_error in (False,True):
            with tempfile.TemporaryDirectory() as temp:
                root=Path(temp);a=root/"A.png";n.save_new(Image.new("RGB",(32,32)),a)
                manifest=copy.deepcopy(p.frozen());manifest["a"]={"root":"shared","path":"A.png","sha256":n.sha256(a)}
                manifest["part2"]["source_lot"]["path"]=str(root/"source")
                calls=[]
                def one(name,*args):
                    calls.append(name)
                    if operational_error and len(calls)==2:raise RuntimeError("synthetic operational error")
                    return {"verdict":"INCONCLUSIVE:null_distribution_not_credible" if len(calls)==1 else "ok"}
                with patch.object(p,"frozen",return_value=manifest),patch.object(p,"verify_cpu_crop",return_value={}),patch.object(o,"local_git",return_value={"dirty":False}),patch.object(d,"verify_lot",return_value={"sha256_verified":True}),patch.object(d,"cpu_runtime",return_value={}),patch.object(d,"one_part2",side_effect=one),patch.object(n,"reproject",side_effect=AssertionError("reprojection forbidden")):
                    rc=d.derive(SimpleNamespace(out=root/"out",port=8197,deadline_s=20),{"shared":root})
                batch=n.read_json(next((root/"out").glob("*/batch.json")))
                self.assertEqual(rc,1 if operational_error else 3)
                self.assertEqual(calls,list(d.PART2[:2] if operational_error else d.PART2))
                self.assertEqual(batch["inconclusive_routes"],[d.PART2[0]])

    def test_preserved_forward_artifacts_bit_exact_no_stats(self):
        """Read-only regression: validates existing executor forward, never derives null deltas."""
        manifest=p.frozen();lot=ROOT/manifest["part2"]["source_lot"]["path"]
        shared=Path(os.environ.get("LOCALAPPDATA",""))/"Comfy-Desktop/ComfyUI-Shared"
        a_path=shared/manifest["a"]["path"]
        if not a_path.exists():self.skipTest("pinned A local fixture unavailable")
        self.assertEqual(n.sha256(a_path),manifest["a"]["sha256"])
        a=n.rgb(a_path)
        for name in ("klein_resample_only","qie_resample_only"):
            params={"policy":"1mp"} if name.startswith("klein") else {"policy":"kontext_table"}
            grid=g.forward_grid(name.split('_')[0],a.size,params)
            # D-059a: executor decode, NOT a Pillow replica of ComfyUI's RGB forward.
            native=n.rgb(lot/name/"native.png")
            self.assertEqual(native.size,(grid["width"],grid["height"]))
            saved=list((lot/name/"server/output").glob("*.png"))
            self.assertEqual(len(saved),1)
            self.assertEqual(n.sha256(lot/name/"native.png"),n.sha256(saved[0]))
        crop=a.crop((-136,193,860,1189)).resize((1024,1024),Image.Resampling.LANCZOS)
        np.testing.assert_array_equal(np.asarray(crop),np.asarray(n.rgb(lot/"r1ei/A_crop_1024.png")))
        # Source validity/crops reproduce original support masks, without calling inverse.
        for route in n.ROUTE_ORDER:
            np.testing.assert_array_equal(n.support_for_geometry(a.size,n.geometry(route)),n.mask(lot/route/"support.png",a.size))


class D059a(unittest.TestCase):
    def test_cpu_graph_exact_and_no_model_or_scale(self):
        manifest=p.frozen();entry=manifest["cpu_workflows"]["klein_crop"]
        graph=n.read_json(n.HERE/entry["file"])
        comfy.validate_cpu_graph(graph)
        self.assertEqual(entry["output_grid"],[720,1536])
        self.assertEqual(comfy.workflow_vae("klein_crop",{}),(None,None))
        graph["vae"]={"class_type":"VAELoader","inputs":{}}
        with self.assertRaises(ValueError):comfy.validate_cpu_graph(graph)
        self.assertNotIn("klein_crop",n.ROUTE_ORDER)

    def test_cpu_bootstrap_refuses_cuda_and_models(self):
        session={"action":"derive_reference","cpu_only":True,"flags":["--cpu"],"vae":None,"vae_evidence":None}
        manager=SimpleNamespace(get_torch_device=lambda:SimpleNamespace(type="cpu"),current_loaded_models=[])
        torch=SimpleNamespace(cuda=SimpleNamespace(is_initialized=lambda:False))
        rec=launch_server.cpu_startup_evidence(session,manager,torch)
        self.assertEqual(rec["device"],"cpu");self.assertFalse(rec["cuda_initialized"])
        self.assertEqual(rec["packages"]["av"],"18.1.0")
        for change in ({"flags":[]},{"vae":"vae.safetensors"},{"action":"generate"}):
            with self.assertRaises(ValueError):launch_server.validate_cpu_session({**session,**change})
        manager.current_loaded_models=["invalid"]
        with self.assertRaises(ValueError):launch_server.cpu_startup_evidence(session,manager,torch)
        manager.current_loaded_models=[];torch.cuda.is_initialized=lambda:True
        with self.assertRaises(ValueError):launch_server.cpu_startup_evidence(session,manager,torch)

    def test_crop_failure_preserves_sidecar_and_never_falls_back(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);n.save_new(Image.new("RGB",(32,32)),root/"A.png")
            with patch.object(p,"unchanged"),patch.object(comfy,"generate",side_effect=RuntimeError("deadline")) as run:
                with self.assertRaisesRegex(RuntimeError,"deadline"):
                    d.crop_reference(root/"ref",{},root/"A.png",8197,20,{})
            self.assertEqual(run.call_args.args[0],"klein_crop")
            self.assertEqual(n.read_json(root/"ref/sidecar.json")["verdict"],"FAIL:reference")
            self.assertFalse((root/"ref/native.png").exists())

    def test_mocked_klein_reference_used_and_pillow_informative(self):
        for value,stop in ((2,False),(7,True)):
            with tempfile.TemporaryDirectory() as temp:
                root=Path(temp);src=root/"source";(src/"klein_vae_native").mkdir(parents=True);(src/"zones").mkdir()
                n.save_new(Image.new("RGB",(725,1536)),root/"A.png")
                n.save_new(Image.new("RGB",(720,1536),(3,3,3)),src/"klein_vae_native/native.png")
                n.write_new(src/"klein_vae_native/null_stats.json",{"route_config":{"synthetic":True}})
                for zone in n.ZONES:
                    v=np.ones((1536,725),bool)
                    if zone=="occluders":v[2:]=False  # small-tail zone STILL participates in D-059a stop
                    n.save_mask(v,src/"zones"/(zone+".png"))
                def executor(directory):
                    directory.mkdir();n.save_new(Image.new("RGB",(720,1536),(value,value,value)),directory/"native.png")
                    rec={"verdict":"ok","a_sha256":n.sha256(root/"A.png"),"native_sha256":n.sha256(directory/"native.png")}
                    n.write_new(directory/"sidecar.json",rec)
                    return directory/"native.png",rec
                runtime=p.frozen()["part2"]["runtime"]
                rec=d.one_part2("klein_g0",root/"derived",src,root/"A.png",p.frozen(),{},runtime,executor)
                stats=n.read_json(root/"derived/null_stats.json")
                self.assertEqual(rec["stop_batch"],stop)
                self.assertEqual(stats["statistics"]["support"]["p995"],abs(3-value))
                self.assertEqual(stats["informative"]["pillow_reference"]["statistics"]["support"]["p995"],3)
                self.assertEqual(stats["informative"]["executor_minus_pillow"]["statistics"]["support"]["max"],value)
                self.assertEqual(stats["route_config"]["PyAV"],"18.1.0")
                if stop:self.assertIn("occluders",stats["prediction_check"]["exceeded"])

    def test_d059a_stop_prevents_next_route(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);n.save_new(Image.new("RGB",(32,32)),root/"A.png")
            manifest=copy.deepcopy(p.frozen());manifest["a"]={"root":"shared","path":"A.png","sha256":n.sha256(root/"A.png")}
            manifest["part2"]["source_lot"]["path"]=str(root/"source")
            with patch.object(p,"frozen",return_value=manifest),patch.object(p,"verify_cpu_crop",return_value={}),patch.object(o,"local_git",return_value={"dirty":False}),patch.object(d,"verify_lot",return_value={}),patch.object(d,"cpu_runtime",return_value={}),patch.object(d,"one_part2",return_value={"verdict":"INCONCLUSIVE:klein_above_pillow_or_prediction","stop_batch":True}) as run:
                self.assertEqual(d.derive(SimpleNamespace(out=root/"out",port=8197,deadline_s=20),{"shared":root}),3)
                run.assert_called_once()
            batch=n.read_json(next((root/"out").glob("*/batch.json")))
            self.assertEqual(batch["stopped_for_review"]["route"],"klein_g0")


if __name__ == "__main__":unittest.main(verbosity=2)
