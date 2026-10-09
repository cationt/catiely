"""CPU-only R2 tests. No ComfyUI, torch, GPU, installed weights or setup execution."""
import asyncio
import copy
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch, Mock
from types import SimpleNamespace

R2 = Path(__file__).resolve().parents[1] / "tools/r2_qie"
sys.path.insert(0, str(R2))
import common
import client
import launch_server
import orchestrate


def history(graph, cached=(), prompt_id="prompt-1"):
    return {"prompt": [0, prompt_id, copy.deepcopy(graph), {}, ["save"]],
            "outputs": {}, "status": {"completed": True, "status_str": "success", "messages": [
                ["execution_start", {"prompt_id": prompt_id, "timestamp": 1000}],
                ["execution_cached", {"prompt_id": prompt_id, "timestamp": 1100, "nodes": list(cached)}],
                ["execution_success", {"prompt_id": prompt_id, "timestamp": 5000}]]}}


class Contracts(unittest.TestCase):
    def setUp(self):
        self.manifest, self.graph, self.policy, _ = common.frozen()

    def test_both_workflow_hashes_and_parameters(self):
        for config in (common.PRIMARY, common.SECONDARY):
            _, graph, _, checksum = common.frozen(config)
            self.assertEqual(len(checksum), 64)
            sampler = graph["sampler"]["inputs"]
            self.assertEqual({k: sampler[k] for k in ("steps", "cfg", "seed", "sampler_name", "scheduler", "denoise")},
                             dict(steps=40, cfg=4, seed=42, sampler_name="euler", scheduler="simple", denoise=1))
            self.assertEqual(graph["shift"]["inputs"]["shift"], 3.1)
            self.assertEqual(graph["negative"]["inputs"]["image2"], ["B", 0])
            self.assertEqual(graph["pos_ref"]["inputs"]["reference_latents_method"], "index_timestep_zero")
            self.assertFalse(any("Lora" in n["class_type"] for n in graph.values()))

    def test_graph_derived_sets(self):
        allowed = {n["node_id"] for n in self.policy["allowed_cached"]}
        self.assertEqual(allowed, {"unet", "clip", "vae", "shift", "norm"})
        self.assertEqual({n["node_id"] for n in self.policy["must_reexecute"]}, set(self.graph) - allowed)

    def test_ids_can_change(self):
        remap = {i: "different_" + i for i in self.graph}
        graph = {remap[i]: copy.deepcopy(node) for i, node in self.graph.items()}
        for node in graph.values():
            for key, value in node["inputs"].items():
                if common.link(value):
                    node["inputs"][key] = [remap[value[0]], value[1]]
        policy = common.cache_policy(graph, [remap["A"], remap["B"]])
        self.assertEqual(len(policy["must_reexecute"]), 11)

    def test_text_without_images_requires_human(self):
        graph = copy.deepcopy(self.graph)
        del graph["negative"]["inputs"]["image1"]
        del graph["negative"]["inputs"]["image2"]
        with self.assertRaisesRegex(common.InvalidRun, "human decision required"):
            common.cache_policy(graph, ["A", "B"])

    def test_unknown_disconnected_class_requires_human(self):
        self.graph["new"] = {"class_type": "SomethingElse", "inputs": {}}
        with self.assertRaisesRegex(common.InvalidRun, "human decision required"):
            common.cache_policy(self.graph, ["A", "B"])

    def test_cycle_rejected(self):
        self.graph["A"]["inputs"]["cycle"] = ["save", 0]
        with self.assertRaisesRegex(common.InvalidRun, "cyclic"):
            common.cache_policy(self.graph, ["A", "B"])

    def test_dangling_link_rejected(self):
        self.graph["sampler"]["inputs"]["model"] = ["missing", 0]
        with self.assertRaisesRegex(common.InvalidRun, "dangling"):
            common.cache_policy(self.graph, ["A", "B"])

    def test_roots_are_exactly_two_loadimages(self):
        for roots in (["A", "A"], ["A", "vae"], ["A"]):
            with self.subTest(roots=roots), self.assertRaises(common.InvalidRun):
                common.cache_policy(self.graph, roots)

    def test_warm_model_patches_allowed(self):
        result = common.validate_history(history(self.graph, ["unet", "clip", "vae", "shift", "norm"]), "prompt-1", self.graph, "warm")
        self.assertEqual(result["cache_validation_verdict"], "ok")
        self.assertEqual(result["server_execution_s"], 4)

    def test_every_image_descendant_forbidden(self):
        for node in self.policy["must_reexecute"]:
            with self.subTest(node=node), self.assertRaises(common.CachedResult):
                common.validate_history(history(self.graph, [node["node_id"]]), "prompt-1", self.graph, "warm")

    def test_cold_even_loader_cache_forbidden(self):
        with self.assertRaises(common.CachedResult) as caught:
            common.validate_history(history(self.graph, ["unet"]), "prompt-1", self.graph, "cold")
        self.assertEqual(caught.exception.evidence["cached_nodes"], ["unet"])
        self.assertEqual(common.EXIT_CACHED_RESULT, 23)

    def test_history_is_required_and_bound(self):
        for mutation in (lambda r: r["status"].pop("messages"),
                         lambda r: r["status"]["messages"].pop(1),
                         lambda r: r["status"]["messages"][1][1].update(prompt_id="other"),
                         lambda r: r["status"].update(completed=False),
                         lambda r: r["status"]["messages"][1][1].update(nodes=["absent"]),
                         lambda r: r["status"]["messages"][1][1].update(nodes=["unet", "unet"])):
            record = history(self.graph)
            mutation(record)
            with self.assertRaises(common.InvalidRun):
                common.validate_history(record, "prompt-1", self.graph, "cold")

    def test_smoke_positive_control_requires_cached_sampler(self):
        with self.assertRaisesRegex(common.InvalidRun, "sampler was not cached"):
            common.validate_history(history(self.graph, ["unet"]), "prompt-1", self.graph, "warm", control=True)
        result = common.validate_history(history(self.graph, list(self.graph)), "prompt-1", self.graph, "warm", control=True)
        self.assertEqual(result["cache_validation_verdict"], "expected_cached_result_smoke_control")

    def test_warm_divergence_is_explicit_not_failure(self):
        report = common.warm_consistency([{"state": "warm", "cached_nodes": x} for x in (["unet"], ["unet", "norm"], ["unet"])])
        self.assertTrue(report["warm_cache_divergence"])

    def test_same_warm_sets_ignore_order(self):
        self.assertFalse(common.warm_consistency([{"state": "warm", "cached_nodes": x} for x in (["a", "b"], ["b", "a"], ["a", "b"])])["warm_cache_divergence"])

    def test_conditional20_disabled(self):
        with self.assertRaisesRegex(common.InvalidRun, "deferred"):
            common.frozen("qie2511_q5_2ref_1mp_20steps")

    def test_hash_mismatch_rejected(self):
        with patch.object(common, "sha256", return_value="wrong"), self.assertRaisesRegex(common.InvalidRun, "freeze"):
            common.frozen()

    def test_smoke_changes_only_steps(self):
        _, smoke, _, _ = common.frozen(smoke=True)
        smoke["sampler"]["inputs"]["steps"] = 40
        self.assertEqual(smoke, self.graph)

    def test_render_changes_only_io_and_never_seed(self):
        graph = common.render(self.graph, "A_unique.jpg", "B_unique.png", "unique")
        for name in ("sampler", "shift", "norm", "positive", "negative"):
            self.assertEqual(graph[name], self.graph[name])

    def test_runtime_fingerprint_is_not_parameter_change(self):
        graph = copy.deepcopy(self.graph)
        graph["A"]["is_changed"] = ["digest"]
        self.assertEqual(common.execution_graph(graph), self.graph)
        graph["sampler"]["inputs"]["seed"] = 4
        self.assertNotEqual(common.execution_graph(graph), self.graph)

    def test_network_guard_blocks_external(self):
        for event, args in (("socket.connect", (None, ("8.8.8.8", 443))),
                            ("socket.getaddrinfo", ("huggingface.co", 443)),
                            ("socket.bind", (None, ("0.0.0.0", 8191)))):
            with self.assertRaises(RuntimeError):
                launch_server.network_guard(event, args)
        launch_server.network_guard("socket.connect", (None, ("127.0.0.1", 8191)))

    def test_endpoint_owner_and_pid_reuse_rejected(self):
        session = {"pid": 10, "process_created": 1, "port": 8191, "launch_path": "unique-session.json"}
        process = SimpleNamespace(create_time=lambda: 1, cmdline=lambda: [str(R2 / "launch_server.py"), "unique-session.json"])
        connection = SimpleNamespace(status="LISTEN", laddr=SimpleNamespace(ip="127.0.0.1", port=8191), pid=10)
        psutil = SimpleNamespace(Process=lambda pid: process, net_connections=lambda kind: [connection], CONN_LISTEN="LISTEN")
        with patch.dict(sys.modules, {"psutil": psutil}):
            client.assert_owner(session)
            connection.pid = 11
            with self.assertRaisesRegex(common.InvalidRun, "endpoint"):
                client.assert_owner(session)
            connection.pid = 10
            process.create_time = lambda: 2
            with self.assertRaisesRegex(common.InvalidRun, "reused"):
                client.assert_owner(session)

    def test_old_comfy_process_rejected_before_port_bind(self):
        process = SimpleNamespace(info={"pid": os.getpid()+1, "name": "python.exe", "cmdline": ["python", "main.py"]}, cwd=lambda: "C:/ComfyUI")
        psutil = SimpleNamespace(process_iter=lambda args: [process], Error=RuntimeError)
        with patch.dict(sys.modules, {"psutil": psutil}), self.assertRaisesRegex(common.InvalidRun, "old ComfyUI"):
            orchestrate.refuse_existing_server(8191)

    def test_input_cleanup_cannot_escape(self):
        with tempfile.TemporaryDirectory() as temp:
            with self.assertRaisesRegex(common.InvalidRun, "unsafe cleanup"):
                client.cleanup_aliases({"input_dir": temp}, "../outside")

    def test_measure_fail_fast_contract(self):
        good = {"label": "run", "state": "warm", "exit_code": 0, "deadline_hit": False, "verdict": "ok", "child_pid": 123}
        sidecar = {"run_id": "run", "state": "warm", "verdict": "ok", "cache_validation_verdict": "ok", "client_pid": 123}
        common.validate_measure(good, sidecar, "run", "warm")
        for field, value in (("exit_code", 23), ("deadline_hit", True), ("verdict", "FAIL:exit_23"), ("label", "old"), ("child_pid", 999)):
            with self.subTest(field=field), self.assertRaises(common.InvalidRun):
                common.validate_measure({**good, field: value}, sidecar, "run", "warm")
        for field, value in (("verdict", "FAIL:cached_result"), ("run_id", "old"), ("cache_validation_verdict", None)):
            with self.subTest(field=field), self.assertRaises(common.InvalidRun):
                common.validate_measure(good, {**sidecar, field: value}, "run", "warm")

    def test_write_never_overwrites(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "result.json"
            common.write_new(path, {"first": True})
            with self.assertRaises(FileExistsError):
                common.write_new(path, {})

    def test_short_and_long_server_logs(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            for index, (line, expected) in enumerate((("Prompt executed in 39.25 seconds", 39.25), ("Prompt executed in 00:25:01", 1501))):
                source = root / "process.log"
                source.write_text("loaded partially\n" + line, encoding="utf-8")
                evidence = client.log_evidence({"process_log": str(source)}, 0, root / f"run{index}.log")
                self.assertEqual(evidence["prompt_executed_s"], expected)
                self.assertIn("loaded partially", evidence["relevant_lines"])

    def test_cached_result_has_dedicated_exit_and_sidecar(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / "process.log").write_text("Prompt executed in 0.00 seconds", encoding="utf-8")
            session = {"startup_s": 1, "process_log": str(root / "process.log")}
            common.write_new(root / "session.json", session)
            common.write_new(root / "plan.json", {"run_id": "unique", "configuration": common.PRIMARY, "state": "warm", "smoke": False, "run_dir": str(root), "session_path": str(root / "session.json"), "log_offset": 0})
            error = common.CachedResult("FAIL:cached_result")
            error.evidence = {**self.policy, "cached_nodes": ["sampler"], "execution_cached": [{"node_id": "sampler", "class_type": "KSampler"}], "cache_validation_verdict": "FAIL:cached_result"}
            with patch.object(client, "execute", side_effect=error):
                self.assertEqual(client.run(root / "plan.json"), 23)
            self.assertEqual(common.read_json(root / "sidecar.json")["verdict"], "FAIL:cached_result")

    @unittest.skipUnless(os.name == "nt", "Windows PowerShell parser")
    def test_powershell51_parser_and_ascii(self):
        for file in (R2 / "setup_r2.ps1", R2 / "bench_r2.ps1"):
            file.read_bytes().decode("ascii")
            command = "$tokens=$null; $errors=$null; [System.Management.Automation.Language.Parser]::ParseFile('" + str(file).replace("'", "''") + "',[ref]$tokens,[ref]$errors) | Out-Null; if ($errors.Count) { $errors | Out-String | Write-Error; exit 1 }; if ($PSVersionTable.PSVersion.Major -ne 5) { exit 2 }"
            process = subprocess.run([str(Path(os.environ["WINDIR"]) / "System32/WindowsPowerShell/v1.0/powershell.exe"), "-NoProfile", "-Command", command], capture_output=True, text=True)
            self.assertEqual(process.returncode, 0, process.stderr)

    @unittest.skipUnless(os.name == "nt", "operator lifecycle is Windows-only")
    def test_benchmark_stops_first_failure_and_cleans_server(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            provenance = {"fake_cpu_test": True}
            common.write_new(root / "setup.json", {"action": "setup", "verdict": "ok", "provenance_digest": common.digest_json(provenance)})
            with patch.object(orchestrate, "verify", return_value=provenance), \
                 patch.object(orchestrate, "dry_run"), patch.object(orchestrate, "Server") as server, \
                 patch.object(orchestrate, "one_run", side_effect=common.InvalidRun("measure deadline")) as run, \
                 patch.object(sys, "argv", ["orchestrate.py", "bench", "--work-root", str(root), "--setup-report", str(root / "setup.json")]):
                with self.assertRaisesRegex(common.InvalidRun, "measure deadline"):
                    orchestrate.main()
                self.assertEqual(run.call_count, 1)
                server.return_value.stop.assert_called_once()
            report = common.read_json(next(root.glob("bench_*/report.json")))
            self.assertTrue(report["verdict"].startswith("FAIL:"))

    @unittest.skipUnless(os.name == "nt", "operator lifecycle is Windows-only")
    def test_three_fresh_colds_then_three_warms_on_third_server(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            provenance = {"fake_cpu_test": True}
            common.write_new(root / "setup.json", {"action": "setup", "verdict": "ok", "provenance_digest": common.digest_json(provenance)})
            servers = [Mock() for _ in range(3)]
            calls = []
            def fake_run(root, server, config, state, index):
                calls.append((server, state, index))
                return {"path": f"fake_{state}_{index}.json", "sidecar": {"state": state, "cached_nodes": ["unet"] if state == "warm" else []}}
            with patch.object(orchestrate, "verify", return_value=provenance), patch.object(orchestrate, "dry_run"), \
                 patch.object(orchestrate, "Server", side_effect=servers), patch.object(orchestrate, "one_run", side_effect=fake_run), \
                 patch.object(sys, "argv", ["orchestrate.py", "bench", "--work-root", str(root), "--setup-report", str(root / "setup.json")]):
                self.assertEqual(orchestrate.main(), 0)
            self.assertEqual([c[0] for c in calls[:3]], servers)
            self.assertTrue(all(c[0] is servers[2] and c[1] == "warm" for c in calls[3:]))
            self.assertEqual(len(calls), 6)
            for server in servers:
                server.start.assert_called_once()
                server.stop.assert_called_once()

    def test_dry_run_has_no_hardware_side_effects(self):
        with patch.object(orchestrate, "verify", side_effect=AssertionError("must not verify/install")), \
             patch.object(orchestrate.Server, "start", side_effect=AssertionError("must not start")), \
             patch.object(sys, "argv", ["orchestrate.py", "dry-run"]):
            self.assertEqual(orchestrate.main(), 0)


class FakeServerTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        from aiohttp import web
        from PIL import Image
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        (self.root / "input").mkdir()
        (self.root / "output").mkdir()
        self.inputs = {}
        for role in ("A", "B"):
            path = self.root / (role + ".png")
            Image.new("RGB", (8, 8), (60, 70, 80)).save(path)
            self.inputs[role] = {"path": str(path), "sha256": common.sha256(path)}
        self.manifest, self.template, self.policy, self.checksum = common.frozen()
        for role in ("A", "B"):
            self.manifest["inputs"][role]["sha256"] = self.inputs[role]["sha256"]
        self.ws = None
        self.record = None
        self.cached = []
        self.mutation = None
        self.tasks = []
        self.web = web
        app = web.Application()
        app.router.add_get("/system_stats", self.stats)
        app.router.add_get("/queue", self.queue)
        app.router.add_get("/ws", self.websocket)
        app.router.add_post("/prompt", self.prompt)
        app.router.add_post("/upload/image", self.upload)
        app.router.add_get("/history/{prompt_id}", self.get_history)
        self.runner = web.AppRunner(app)
        await self.runner.setup()
        site = web.TCPSite(self.runner, "127.0.0.1", 0)
        await site.start()
        port = site._server.sockets[0].getsockname()[1]
        self.session = {"port": port, "input_dir": str(self.root / "input"), "output_dir": str(self.root / "output"),
                        "provenance": {"inputs": self.inputs, "manifest_sha256": common.sha256(R2 / "manifest.json")}}
        self.owner_patch = patch.object(client, "assert_owner")
        self.owner_patch.start()
        self.freeze_patch = patch.object(client, "frozen", return_value=(self.manifest, self.template, self.policy, self.checksum))
        self.freeze_patch.start()

    async def asyncTearDown(self):
        for task in self.tasks:
            await task
        await self.runner.cleanup()
        self.freeze_patch.stop()
        self.owner_patch.stop()
        self.temp.cleanup()

    async def stats(self, request):
        return self.web.json_response({"system": {"comfyui_version": "0.38.2"}})

    async def queue(self, request):
        return self.web.json_response({"queue_running": [], "queue_pending": []})

    async def websocket(self, request):
        self.ws = self.web.WebSocketResponse()
        await self.ws.prepare(request)
        async for _ in self.ws:
            pass
        return self.ws

    async def upload(self, request):
        data = await request.post()
        image = data["image"]
        target = self.root / "input" / image.filename
        target.write_bytes(image.file.read())
        return self.web.json_response({"name": image.filename, "type": "input", "subfolder": ""})

    async def prompt(self, request):
        graph = (await request.json())["prompt"]
        self.tasks.append(asyncio.create_task(self.complete(graph)))
        return self.web.json_response({"prompt_id": "prompt-1", "node_errors": {}})

    async def complete(self, graph):
        from PIL import Image
        from PIL.PngImagePlugin import PngInfo
        await self.ws.send_json({"type": "executing", "data": {"prompt_id": "prompt-1", "node": "sampler"}})
        await asyncio.sleep(0.03)
        await self.ws.send_json({"type": "executing", "data": {"prompt_id": "prompt-1", "node": "decode"}})
        name = graph["save"]["inputs"]["filename_prefix"] + "_00001_.png"
        metadata = PngInfo()
        mutated = copy.deepcopy(graph)
        mutated["A"]["is_changed"] = ["same-bytes"]
        metadata.add_text("prompt", json.dumps(mutated))
        if "save" not in self.cached:
            Image.new("RGB", (8, 8)).save(self.root / "output" / name, pnginfo=metadata)
        self.record = history(mutated, self.cached)
        self.record["outputs"] = {"save": {"images": [{"filename": name, "subfolder": "", "type": "output"}]}}
        if self.mutation:
            self.mutation(self.record)

    async def get_history(self, request):
        return self.web.json_response({"prompt-1": self.record} if self.record else {})

    async def plan(self, state="warm"):
        aliases = await client.upload_inputs(self.session, "unique_run")
        directory = self.root / "run"
        directory.mkdir()
        return {"configuration": common.PRIMARY, "smoke": False, "state": state, "aliases": aliases,
                "output_prefix": "unique_output", "workflow": common.render(self.template, aliases["A"]["name"], aliases["B"]["name"], "unique_output"),
                "run_dir": str(directory), "preexisting_outputs": [], "prepared_at_ns": 0, "expected_dimensions": [8, 8]}

    async def test_full_fake_http_ws_flow_and_cleanup(self):
        self.cached = ["unet", "clip", "vae", "shift", "norm"]
        plan = await self.plan()
        evidence = {}
        await client.execute(plan, self.session, evidence)
        self.assertGreater(evidence["sampling_s"], 0)
        self.assertAlmostEqual(evidence["per_step_s"], evidence["sampling_s"] / 40)
        self.assertEqual(evidence["cached_nodes"], sorted(self.cached))
        self.assertTrue(Path(evidence["output"]["path"]).is_file())
        client.cleanup_aliases(self.session, "unique_run")
        self.assertEqual(list((self.root / "input").iterdir()), [])
        self.assertTrue(Path(self.inputs["A"]["path"]).is_file())

    async def test_fake_cold_empty_cache(self):
        evidence = {}
        await client.execute(await self.plan("cold"), self.session, evidence)
        self.assertEqual(evidence["execution_cached"], [])

    async def test_fake_identical_control_then_renamed_warm(self):
        first = await self.plan("cold")
        first["smoke"] = True
        before = {}
        await client.execute(first, self.session, before)
        client.cleanup_aliases(self.session, "unique_run")
        aliases = await client.upload_inputs(self.session, "unique_run")
        second_dir = self.root / "second"
        second_dir.mkdir()
        second = {**first, "state": "warm", "control": True, "aliases": aliases,
                  "run_dir": str(second_dir), "control_source": before["output"]["server_path"], "control_sha256": before["output"]["sha256"]}
        self.cached = list(self.template)
        self.record = None
        control = {}
        await client.execute(second, self.session, control)
        self.assertIn("sampler", control["cached_nodes"])
        self.assertIsNone(control["sampling_s"])
        client.cleanup_aliases(self.session, "unique_run")
        new_aliases = await client.upload_inputs(self.session, "renamed")
        third_dir = self.root / "third"
        third_dir.mkdir()
        third = {**first, "state": "warm", "aliases": new_aliases, "run_dir": str(third_dir), "output_prefix": "renamed_output",
                 "workflow": common.render(self.template, new_aliases["A"]["name"], new_aliases["B"]["name"], "renamed_output")}
        self.cached = ["unet", "clip", "vae", "shift", "norm"]
        self.record = None
        after = {}
        await client.execute(third, self.session, after)
        self.assertEqual(after["cache_validation_verdict"], "ok")
        self.assertEqual(before["inputs"]["A"]["sha256"], after["inputs"]["A"]["sha256"])
        self.assertNotEqual(first["workflow"], third["workflow"])
        self.assertNotEqual(before["output"]["path"], after["output"]["path"])

    async def test_fake_cached_sampler_rejected(self):
        self.cached = ["sampler"]
        with self.assertRaises(common.CachedResult):
            await client.execute(await self.plan(), self.session, {})
        self.assertFalse((self.root / "run/output.png").exists())

    async def test_fake_history_without_messages_rejected(self):
        self.mutation = lambda record: record["status"].pop("messages")
        with self.assertRaisesRegex(common.InvalidRun, "status.messages"):
            await client.execute(await self.plan(), self.session, {})

    async def test_fake_old_output_name_rejected(self):
        self.mutation = lambda record: record["outputs"]["save"]["images"][0].update(filename="old_00001_.png")
        with self.assertRaisesRegex(common.InvalidRun, "prefix"):
            await client.execute(await self.plan(), self.session, {})

    async def test_fake_wrong_prompt_parameters_rejected(self):
        self.mutation = lambda record: record["prompt"][2]["sampler"]["inputs"].update(seed=100)
        with self.assertRaisesRegex(common.InvalidRun, "workflow/prompt"):
            await client.execute(await self.plan(), self.session, {})

    async def test_changed_alias_rejected_before_submit(self):
        plan = await self.plan()
        Path(plan["aliases"]["A"]["path"]).write_bytes(b"wrong")
        with self.assertRaisesRegex(common.InvalidRun, "input copy changed"):
            await client.execute(plan, self.session, {})
        self.assertIsNone(self.record)

    async def test_control_forbidden_in_formal_run(self):
        plan = await self.plan()
        plan["control"] = True
        with self.assertRaisesRegex(common.InvalidRun, "control forbidden"):
            await client.execute(plan, self.session, {})


if __name__ == "__main__":
    unittest.main()
