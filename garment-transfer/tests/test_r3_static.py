#!/usr/bin/env python3
"""Testes estáticos/CPU da preparação R3 (FASHN VTON 1.5): manifesto e hashes, downloader/verificador com pesos esparsos, provenance
robusta a CRLF, runner em --dry-run (sem torch; geometria pelo transforms.py upstream carregado por caminho), guarda offline, scripts
PowerShell (BOM/ASCII/balanceamento), bench. Precisa dos clones pinados? NÃO: usa fixtures sintéticas e, para o dry-run, um pacote
`fashn_vton` mínimo recriado com o transforms.py cujo sha256 bate com o pin (conteúdo embutido no teste via vendor? não — o teste
baixa nada: ele exige a presença opcional do clone em $R3_VTON_SRC; sem ele, os testes de geometria são marcados como SKIP).
Rodar: python tests/test_r3_static.py"""
import glob, hashlib, json, os, shutil, socket, subprocess, sys, tempfile, types

HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(HERE); REPO = os.path.dirname(ROOT)
R3 = os.path.join(ROOT, "tools", "r3_fashn")
sys.path.insert(0, HERE); sys.path.insert(0, R3)
from _fixtures import Checker  # noqa: E402
import fetch_weights as fw  # noqa: E402
import verify_provenance as vp  # noqa: E402

BOM = b"\xef\xbb\xbf"


def run(cmd, **kw):
    return subprocess.run(cmd, capture_output=True, text=True, **kw)


def git_blob_oid(b):
    return hashlib.sha1(b"blob %d\0" % len(b) + b).hexdigest()


def sparse(path, size):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "wb") as f:
        f.truncate(size)


def main():
    c = Checker()
    man = json.load(open(os.path.join(R3, "r3_manifest.json"), encoding="utf-8"))

    # ---------- manifesto: pins completos e coerentes
    vton = man["code_repos"]["vton"]; hp = man["code_repos"]["human_parser"]; comps = man["components"]
    c.ok("manifest_commits_40hex", all(len(x["commit"]) == 40 and all(ch in "0123456789abcdef" for ch in x["commit"]) for x in (vton, hp)), (vton["commit"], hp["commit"]))
    c.ok("manifest_vton_commit_e_o_observado", vton["commit"] == "7c0f10af3f91ad4048fe9729c470a13ef905d25a", vton["commit"])
    c.ok("manifest_model_sha_e_o_observado", comps["tryon"]["files"]["model.safetensors"]["sha256"] == "d6cd38286885bc29fa487ea9383f80ffeb95862e7747c630d42c5d3c05bdd35a" and comps["tryon"]["files"]["model.safetensors"]["size_bytes"] == 1943668048, "")
    c.ok("manifest_code_files_com_blob_e_sha", all(len(i["blob_oid"]) == 40 and len(i["sha256"]) == 64 and i["size_bytes"] > 0 for r in (vton, hp) for i in r["files"].values()) and len(vton["files"]) >= 20, (len(vton["files"]), len(hp["files"])))
    c.ok("manifest_pipeline_files_pinados", all(f"src/fashn_vton/{m}" in vton["files"] for m in ("pipeline.py", "tryon_mmdit.py", "preprocessing/agnostic.py", "preprocessing/transforms.py", "dwpose/wholebody.py", "utils/sampling.py")), "")
    c.ok("manifest_componentes_6_arquivos_com_revisao", set(comps) == {"tryon", "dwpose", "human_parser"} and all(len(cp["revision"]) == 40 for cp in comps.values()) and sum(len(cp["files"]) for cp in comps.values()) == 6 and all(len(i["sha256"]) == 64 and i["size_bytes"] > 0 for cp in comps.values() for i in cp["files"].values()), "")
    total = sum(i["size_bytes"] for cp in comps.values() for i in cp["files"].values())
    c.ok("manifest_total_bytes_coerente", man["download_total_bytes"] == total, (man["download_total_bytes"], total))
    c.ok("manifest_defaults_oficiais", man["upstream_defaults"]["num_timesteps"] == 30 and man["upstream_defaults"]["guidance_scale"] == 1.5 and man["upstream_defaults"]["seed"] == 42 and man["upstream_defaults"]["num_samples"] == 1 and man["upstream_defaults"]["segmentation_free"] is True, "")
    c.ok("manifest_parser_licenca_nvidia_registrada", "NVIDIA" in hp["license"] and "NVIDIA" in comps["human_parser"]["license"], "")
    c.ok("manifest_segfree_nao_e_parser_free", "parser" in man["pipeline_facts"]["segfree_semantics"].lower() and "executado" in man["pipeline_facts"]["segfree_semantics"] and "parser-free" in man["pipeline_facts"]["segfree_semantics"], "")
    c.ok("manifest_ort_cuda13_pin", man["environment"]["onnxruntime"]["pin"] == "onnxruntime-gpu==1.30.0" and man["environment"]["onnxruntime"]["wheel_win_cp312"]["cuda_version"] == "13.0" and "1.26.0" in man["environment"]["onnxruntime"]["fallback_cuda12"]["pin"], "")
    c.ok("manifest_model_input_hw", man["pipeline_facts"]["model_input_hw"] == [864, 576], "")
    reqs = [l.split("#")[0].strip() for l in open(os.path.join(R3, "requirements-r3.txt"), encoding="utf-8") if l.strip() and not l.startswith("#")]
    c.ok("requirements_pinadas_sem_torch_e_sem_upstream", all("==" in l or l.startswith(("psutil", "nvidia-ml-py")) for l in reqs) and not any(l.startswith(("torch", "fashn")) for l in reqs) and any(l.startswith("onnxruntime-gpu==1.30.0") for l in reqs), reqs)

    with tempfile.TemporaryDirectory() as d:
        # ---------- fetch_weights: verificação com pesos esparsos (tamanhos) + sha em arquivos pequenos falsos
        wd = os.path.join(d, "weights")
        for cp in comps.values():
            sub = cp.get("local_subdir", "")
            for rel, info in cp["files"].items():
                sparse(os.path.join(wd, sub, *rel.split("/")) if sub else os.path.join(wd, *rel.split("/")), info["size_bytes"])
        rep = fw.verify(wd, man, None, check_sha=False)
        c.ok("fetch_weights_verify_tamanhos_ok", rep["ok"] and rep["total_bytes"] == total and set(rep["components"]) == {"tryon", "dwpose", "human_parser"}, {k: v["ok"] for k, v in rep["components"].items()})
        os.remove(os.path.join(wd, "dwpose", "yolox_l.onnx"))
        r1 = fw.verify(wd, man, None, False)
        c.ok("fetch_weights_verify_ausente", (not r1["ok"]) and r1["components"]["dwpose"]["files"]["yolox_l.onnx"]["status"] == "ausente" and r1["components"]["tryon"]["ok"], "")
        sparse(os.path.join(wd, "dwpose", "yolox_l.onnx"), 10)
        r2 = fw.verify(wd, man, "dwpose", False)
        c.ok("fetch_weights_verify_tamanho_divergente_e_only", (not r2["ok"]) and r2["components"]["dwpose"]["files"]["yolox_l.onnx"]["status"] == "tamanho_divergente" and set(r2["components"]) == {"dwpose"}, "")
        sparse(os.path.join(wd, "dwpose", "yolox_l.onnx"), comps["dwpose"]["files"]["yolox_l.onnx"]["size_bytes"])
        fm = json.loads(json.dumps(man)); small = b"{}"; fm["components"]["human_parser"]["files"]["config.json"] = {"size_bytes": 2, "sha256": hashlib.sha256(small).hexdigest()}
        open(os.path.join(wd, "fashn-human-parser", "config.json"), "wb").write(small)
        r3 = fw.verify(wd, fm, "human_parser", check_sha=True)
        c.ok("fetch_weights_verify_sha_ok_e_divergente", r3["components"]["human_parser"]["files"]["config.json"]["status"] == "ok" and r3["components"]["human_parser"]["files"]["model.safetensors"]["status"] == "sha256_divergente" and not r3["ok"], {k: v["status"] for k, v in r3["components"]["human_parser"]["files"].items()})
        # fetch usa hf_hub_download com revision pinada por arquivo (fake huggingface_hub)
        calls = []; fake_hub = types.ModuleType("huggingface_hub")
        def hf_hub_download(**kw):
            calls.append(kw); return os.path.join(kw["local_dir"], kw["filename"])
        fake_hub.hf_hub_download = hf_hub_download; saved = sys.modules.get("huggingface_hub"); sys.modules["huggingface_hub"] = fake_hub
        try:
            fw.fetch(os.path.join(d, "dl"), man)
        finally:
            if saved is not None: sys.modules["huggingface_hub"] = saved
            else: del sys.modules["huggingface_hub"]
        c.ok("fetch_weights_hf_hub_download_revision_pinada_por_arquivo", len(calls) == 6 and all(len(k["revision"]) == 40 for k in calls) and {k["repo_id"] for k in calls} == {cp["repo"] for cp in comps.values()}
             and any(k["filename"] == "model.safetensors" and k["revision"] == comps["tryon"]["revision"] and k["local_dir"].endswith("dl") for k in calls)
             and any(k["filename"] == "yolox_l.onnx" and k["local_dir"].endswith("dwpose") for k in calls) and any(k["local_dir"].endswith("fashn-human-parser") for k in calls), [(k["repo_id"], k["filename"]) for k in calls])
        src = open(os.path.join(R3, "fetch_weights.py"), encoding="utf-8").read().split('"""', 2)[2]
        c.ok("fetch_weights_sem_hf_download_cli", "hf download" not in src and "--include" not in src, "")
        # CLI --verify-only exit 0/1
        mp = os.path.join(d, "fm.json"); json.dump(fm, open(mp, "w"))
        r = run([sys.executable, os.path.join(R3, "fetch_weights.py"), "--weights-dir", wd, "--manifest", mp, "--verify-only", "--only", "tryon", "--json-out", os.path.join(d, "v.json")])
        rb = run([sys.executable, os.path.join(R3, "fetch_weights.py"), "--weights-dir", wd, "--manifest", mp, "--verify-only", "--only", "human_parser", "--verify-sha"])
        c.ok("fetch_weights_cli_exit_0_e_1", r.returncode == 0 and json.load(open(os.path.join(d, "v.json")))["ok"] and rb.returncode == 1, (r.returncode, rb.returncode, r.stderr[-200:]))

        # ---------- verify_provenance: repositório git real com working tree CRLF; manifesto falso com os pins calculados
        g = os.path.join(d, "clone"); files = {"LICENSE": b"Apache\n", "README.md": b"# r\n", "pyproject.toml": b"[project]\nname='x'\n", "src/fashn_vton/__init__.py": b"__version__ = '1.5.0'\n", "src/fashn_vton/pipeline.py": b"import torch\n\nclass TryOnPipeline:\n    pass\n"}
        for f, b in files.items():
            p = os.path.join(g, *f.split("/")); os.makedirs(os.path.dirname(p), exist_ok=True); open(p, "wb").write(b)
        env = dict(os.environ, GIT_AUTHOR_NAME="t", GIT_AUTHOR_EMAIL="t@t", GIT_COMMITTER_NAME="t", GIT_COMMITTER_EMAIL="t@t")
        for cmd in (["git", "init", "-q"], ["git", "config", "core.autocrlf", "false"], ["git", "add", "-A"], ["git", "commit", "-q", "-m", "pin"]):
            assert run(cmd, cwd=g, env=env).returncode == 0
        head = run(["git", "rev-parse", "HEAD"], cwd=g).stdout.strip()
        entry = {"github": "x", "commit": head, "files": {f: {"blob_oid": git_blob_oid(b), "sha256": hashlib.sha256(b).hexdigest(), "size_bytes": len(b)} for f, b in files.items()}}
        for f, b in files.items():
            open(os.path.join(g, *f.split("/")), "wb").write(b.replace(b"\n", b"\r\n"))
        rep = vp.verify_clone(g, entry)
        c.ok("verify_provenance_aceita_crlf_subdiretorios", rep["ok"] and rep["head_ok"] and all(v["blob_oid_ok"] and v["sha256_lf_ok"] and v["eol_converted_in_working_tree"] for v in rep["files"].values()), {k: v.get("status") for k, v in rep["files"].items()})
        open(os.path.join(g, "src", "fashn_vton", "pipeline.py"), "wb").write(b"import torch\r\n\r\nclass TryOnPipeline:\r\n    x = 1\r\n")
        rep2 = vp.verify_clone(g, entry)
        c.ok("verify_provenance_rejeita_conteudo_alterado", (not rep2["ok"]) and rep2["files"]["src/fashn_vton/pipeline.py"]["status"] == "sha256_divergente" and rep2["files"]["src/fashn_vton/pipeline.py"]["blob_oid_ok"], "")
        bad = dict(entry, commit="0" * 40)
        c.ok("verify_provenance_rejeita_commit_ausente", not vp.verify_clone(g, bad)["ok"], "")
        fman = {"code_repos": {"vton": entry}}; fmp = os.path.join(d, "fman.json"); json.dump(fman, open(fmp, "w"))
        open(os.path.join(g, "src", "fashn_vton", "pipeline.py"), "wb").write(files["src/fashn_vton/pipeline.py"].replace(b"\n", b"\r\n"))
        r = run([sys.executable, os.path.join(R3, "verify_provenance.py"), "--clone-dir", g, "--repo", "vton", "--manifest", fmp, "--json-out", os.path.join(d, "prov.json")])
        c.ok("verify_provenance_cli_exit0", r.returncode == 0 and json.load(open(os.path.join(d, "prov.json")))["ok"], r.stdout[-150:])

        # ---------- runner --dry-run: pacote fashn_vton mínimo (transforms.py idêntico ao pin, se o clone estiver disponível; senão SKIP)
        import numpy as np
        from PIL import Image
        A = np.full((1216, 832, 3), 180, np.uint8); Ap = os.path.join(d, "A.png"); Image.fromarray(A).save(Ap)
        B = np.full((1000, 750, 3), 235, np.uint8); B[150:800, 120:620] = (30, 60, 200); Bp = os.path.join(d, "B.png"); Image.fromarray(B).save(Bp)
        src_env = os.environ.get("R3_VTON_SRC") or next((p for p in [os.path.join(REPO, "..", "fashn-vton-1.5", "src"), "/tmp/claude-0/-home-user-catiely/1b441bb0-3bc6-5ccf-940a-58a0bf04b886/scratchpad/r3src/fashn-vton-1.5/src"] if os.path.isdir(p)), None)
        hp_src = os.environ.get("R3_HP_SRC") or (os.path.join(os.path.dirname(os.path.dirname(src_env)), "..", "fashn-human-parser", "src") if src_env else None)
        base = [sys.executable, os.path.join(R3, "run_fashn_vton.py"), "--person", Ap, "--garment", Bp, "--weights-dir", wd, "--category", "tops"]
        # (a) sem pacote fashn_vton instalado: dry-run reprova por código divergente/ausente (exit 3) sem tocar em torch
        envno = dict(os.environ); envno["PYTHONPATH"] = os.path.join(d, "empty"); os.makedirs(os.path.join(d, "empty"), exist_ok=True)
        sparse(os.path.join(wd, "fashn-human-parser", "config.json"), comps["human_parser"]["files"]["config.json"]["size_bytes"])
        r = run(base + ["--segmentation-free", "--out", os.path.join(d, "o0.png"), "--dry-run"], env=envno)
        j0 = json.load(open(os.path.join(d, "o0.png.json"))) if os.path.exists(os.path.join(d, "o0.png.json")) else {}
        c.ok("runner_dry_run_sem_pacote_exit3_codigo", r.returncode == 3 and j0.get("verdict") == "FAIL:codigo_divergente_do_pin" and j0.get("code_check", {}).get("ok") is False and j0.get("pin_check", {}).get("ok") is True, (r.returncode, j0.get("verdict"), r.stderr[-200:]))
        # (b) pesos ausentes → exit 3 por pesos (antes do código)
        os.remove(os.path.join(wd, "model.safetensors"))
        r = run(base + ["--masked", "--out", os.path.join(d, "o1.png"), "--dry-run"], env=envno)
        j1 = json.load(open(os.path.join(d, "o1.png.json")))
        c.ok("runner_dry_run_pesos_ausentes_exit3", r.returncode == 3 and j1["verdict"].startswith("FAIL:pesos") and j1["pin_check"]["files"]["tryon:model.safetensors"] == "ausente", (r.returncode, j1["verdict"]))
        sparse(os.path.join(wd, "model.safetensors"), comps["tryon"]["files"]["model.safetensors"]["size_bytes"])
        # (c) modo obrigatório e exclusivo
        r = run(base + ["--out", os.path.join(d, "o2.png"), "--dry-run"], env=envno)
        c.ok("runner_exige_modo", r.returncode == 2 and "segmentation-free" in (r.stderr + r.stdout), r.returncode)
        r = run(base + ["--segmentation-free", "--masked", "--out", os.path.join(d, "o2.png"), "--dry-run"], env=envno)
        c.ok("runner_modos_exclusivos", r.returncode == 2, r.returncode)
        # (d) com o clone pinado no PYTHONPATH: dry-run OK, código conferido, geometria pelo transforms.py upstream
        if src_env and os.path.isdir(src_env) and hp_src and os.path.isdir(hp_src):
            envok = dict(os.environ); envok["PYTHONPATH"] = os.pathsep.join([src_env, hp_src])
            r = run(base + ["--segmentation-free", "--out", os.path.join(d, "o3.png"), "--dry-run"], env=envok)
            j3 = json.load(open(os.path.join(d, "o3.png.json"))) if os.path.exists(os.path.join(d, "o3.png.json")) else {}
            g3 = j3.get("geometry", {})
            c.ok("runner_dry_run_ok_com_clone_pinado", r.returncode == 0 and j3.get("verdict") == "DRY_RUN_OK" and j3["code_check"]["ok"] and j3["pin_check"]["ok"] and j3["mode"] == "segfree", (r.returncode, j3.get("verdict"), j3.get("code_check", {}).get("ok"), r.stderr[-300:]))
            c.ok("runner_geometria_upstream_fit_864_canvas_576x864", g3.get("A_pre_resized_wh") == [591, 864] and g3.get("A_in_canvas_wh") == [576, 842] and g3.get("output_wh_expected") == [576, 842] and g3.get("model_input_wh") == [576, 864] and g3.get("A_padding_lrtb_in_model_canvas") == {"left": 0, "top": 11, "right": 0, "bottom": 11} and g3.get("B_pre_resized_wh") == [648, 864], g3)
            c.ok("runner_sidecar_offline_e_plano", j3["offline"]["enforced"] and j3["offline"]["env"]["HF_HUB_OFFLINE"] == "1" and j3["offline"]["env"]["TRANSFORMERS_OFFLINE"] == "1" and j3["offline"]["env"]["HF_HOME"].startswith(wd) and j3["offline"]["net_guard"] and j3["plan"]["parser_runs"] == 2 and j3["plan"]["dwpose_runs"] == 2 and j3["plan"]["cfg_passes_per_step"] == 2 and j3["params"]["num_timesteps"] == 30 and j3["params"]["guidance_scale"] == 1.5 and j3["params"]["seed"] == 42, "")
            r = run(base + ["--masked", "--garment-photo-type", "flat-lay", "--out", os.path.join(d, "o4.png"), "--dry-run"], env=envok)
            j4 = json.load(open(os.path.join(d, "o4.png.json")))
            c.ok("runner_dry_run_masked_flatlay_plano", r.returncode == 0 and j4["mode"] == "masked" and j4["plan"]["dwpose_runs"] == 1 and j4["params"]["segmentation_free"] is False and "habilitado" in j4["semantics"].lower(), (j4["mode"], j4["plan"]))
            # código adulterado no pacote → exit 3
            alt = os.path.join(d, "altsrc"); shutil.copytree(src_env, alt)
            pp = os.path.join(alt, "fashn_vton", "pipeline.py"); open(pp, "a", encoding="utf-8").write("\n# alterado\n")
            envalt = dict(os.environ); envalt["PYTHONPATH"] = os.pathsep.join([alt, hp_src])
            r = run(base + ["--segmentation-free", "--out", os.path.join(d, "o5.png"), "--dry-run"], env=envalt)
            j5 = json.load(open(os.path.join(d, "o5.png.json")))
            c.ok("runner_codigo_adulterado_exit3", r.returncode == 3 and j5["verdict"] == "FAIL:codigo_divergente_do_pin" and j5["code_check"]["packages"]["vton"]["files"]["pipeline.py"]["status"] == "sha256_divergente", (r.returncode, j5["verdict"]))
            # CRLF no pacote instalado (autocrlf) → aceito, eol registrado
            crlf = os.path.join(d, "crlfsrc"); shutil.copytree(src_env, crlf)
            for root, _, fs in os.walk(crlf):
                for f in fs:
                    if f.endswith(".py"):
                        p = os.path.join(root, f); b = open(p, "rb").read(); open(p, "wb").write(b.replace(b"\n", b"\r\n"))
            envcrlf = dict(os.environ); envcrlf["PYTHONPATH"] = os.pathsep.join([crlf, hp_src])
            r = run(base + ["--segmentation-free", "--out", os.path.join(d, "o6.png"), "--dry-run"], env=envcrlf)
            j6 = json.load(open(os.path.join(d, "o6.png.json")))
            c.ok("runner_codigo_crlf_aceito_eol_registrado", r.returncode == 0 and j6["code_check"]["ok"] and j6["code_check"]["packages"]["vton"]["files"]["pipeline.py"]["eol_converted"] is True, (r.returncode, j6.get("verdict")))
        else:
            print("SKIP  runner_dry_run_com_clone (clone pinado nao disponivel: defina R3_VTON_SRC e R3_HP_SRC)")

        # ---------- guarda offline do runner (função pura; sem torch)
        import importlib.util
        spec = importlib.util.spec_from_file_location("r3runner", os.path.join(R3, "run_fashn_vton.py")); mod = importlib.util.module_from_spec(spec); spec.loader.exec_module(mod)
        saved_env = {k: os.environ.get(k) for k in ("HF_HUB_OFFLINE", "TRANSFORMERS_OFFLINE", "HF_HOME")}
        orig_connect = socket.socket.connect; orig_connect_ex = socket.socket.connect_ex
        try:
            env = mod.enforce_offline(wd)
            blocked = False
            try:
                s_ = socket.socket(); s_.settimeout(0.2); s_.connect(("93.184.216.34", 80))
            except RuntimeError as e:
                blocked = "bloqueada" in str(e)
            except Exception:
                blocked = False
            finally:
                s_.close()
            loop_ok = True
            try:
                s2 = socket.socket(); s2.settimeout(0.2); s2.connect_ex(("127.0.0.1", 9))   # loopback permitido (pode recusar; não pode levantar a guarda)
            except RuntimeError:
                loop_ok = False
            finally:
                s2.close()
            c.ok("runner_guarda_de_rede_bloqueia_externo_permite_loopback", blocked and loop_ok and mod.NET_ATTEMPTS and env["HF_HUB_OFFLINE"] == "1" and os.environ["HF_HUB_OFFLINE"] == "1" and env["HF_HOME"].startswith(os.path.abspath(wd)), (blocked, loop_ok, mod.NET_ATTEMPTS[:1]))
        finally:
            socket.socket.connect = orig_connect; socket.socket.connect_ex = orig_connect_ex
            for k, v in saved_env.items():
                if v is None: os.environ.pop(k, None)
                else: os.environ[k] = v

    # ---------- PowerShell: BOM + ASCII + balanceamento (fora de comentários) + conteúdo essencial
    for name in ("setup_r3.ps1", "bench_r3.ps1"):
        b = open(os.path.join(R3, name), "rb").read(); body = b[3:] if b.startswith(BOM) else b; txt = body.decode("ascii", errors="replace")
        code = "\n".join(("" if l.lstrip().startswith("#") else l.split("  #")[0].split(" # ")[0]) for l in txt.splitlines())
        c.ok(f"ps1_bom_ascii_balanceado:{name}", b.startswith(BOM) and all(x < 0x80 for x in body) and code.count("{") == code.count("}") and code.count("(") == code.count(")"), (b[:3], sum(x >= 0x80 for x in body)))
    setup = open(os.path.join(R3, "setup_r3.ps1"), "rb").read().decode("ascii", errors="replace")
    c.ok("setup_r3_fluxo_essencial", all(k in setup for k in ("fetch_weights.py", "verify_provenance.py", "--no-deps fashn-human-parser==0.1.1", "pip install --no-deps $CloneDir", "core.autocrlf=false", "preload_dlls()", "CUDAExecutionProvider", "--dry-run", "--smoke", "inputs_decision.json", "requirements-r3.txt")) and "hf download" not in setup and "measure_run.py" not in setup, "")
    c.ok("setup_r3_baseline_tops_model_e_hashes", '$Category -ne "tops"' in setup and '$GarmentPhotoType -ne "model"' in setup and "Get-FileHash" in setup and "expected_inputs.json" in setup and "--inputs-decision" in setup, "")
    c.ok("setup_r3_fallback_ort_cuda12", "onnxruntime-gpu==1.26.0" in setup and '$torchCuda -eq "12"' in setup, "")
    bench = open(os.path.join(R3, "bench_r3.ps1"), "rb").read().decode("ascii", errors="replace")
    c.ok("bench_r3_protocolo", all(k in bench for k in ('"segfree", "masked"', "--num-timesteps", '"30"', "--guidance-scale", '"1.5"', "--seed", '"42"', "--num-samples", '"1"', "--budget-s $BudgetS", "--interval-s 0.5", "r3_fashn15_bf16_576x864", "cold_pagecache_unflushed", "inputs_decision.json")) and "[int]$BudgetS = 3600" in bench and "[int]$N = 3" in bench, "")
    c.ok("bench_r3_modos_flags_corretas", '"--segmentation-free" } else { "--masked" }' in bench and "--allow-online" not in bench and "--allow-ort-cpu-fallback" not in bench, "")
    # .gitattributes cobre .ps1/.py/.json
    ga = open(os.path.join(REPO, ".gitattributes"), encoding="utf-8").read()
    c.ok("gitattributes_presente", "*.ps1 text eol=crlf" in ga and "*.py text eol=lf" in ga, "")
    return c.done("test_r3_static")


if __name__ == "__main__":
    sys.exit(main())
