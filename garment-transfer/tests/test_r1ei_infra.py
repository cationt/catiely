#!/usr/bin/env python3
"""Testes regressivos (CPU, sem torch, sem modelos) dos bugs de infraestrutura reproduzidos no Windows em 2026-10-08 durante o setup da R1-EI:
(1) PowerShell 5.1 + UTF-8 sem BOM → ParserError; (2) core.autocrlf CRLF quebrou o sha256 de provenance; (3) `hf download --include a b c`
ignorou padrões no huggingface_hub 1.27; (5) pynvml deprecado. Também confere o `summarize_runs.py` contra os 6 runs reais registrados.
Rodar: python tests/test_r1ei_infra.py"""
import fnmatch, glob, hashlib, json, os, shutil, statistics as st, subprocess, sys, tempfile, types, warnings

HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(HERE); REPO = os.path.dirname(ROOT)
R1 = os.path.join(ROOT, "tools", "r1ei")
sys.path.insert(0, HERE); sys.path.insert(0, R1); sys.path.insert(0, os.path.join(ROOT, "tools"))
from _fixtures import Checker  # noqa: E402
import verify_provenance as vp  # noqa: E402
import hf_fetch as hf  # noqa: E402
import summarize_runs as sr  # noqa: E402

BOM = b"\xef\xbb\xbf"
UTILS_LF_SHA = "d84f0cbc0a85de804ad1bf65955d6ad0fd213a4b70f9ddc620f898fd54dd300f"
UTILS_CRLF_SHA = "7aa544c68eab96e8466bb4889bea5e6293386e039c53dd40d3df55662aa0e1f7"   # sha observado no alvo com autocrlf=true
UTILS_BLOB_OID = "70b31434ad5f88d7d2b54fe74bf0496a11fc50a2"


def git_blob_oid(b):
    return hashlib.sha1(b"blob %d\0" % len(b) + b).hexdigest()


def run(cmd, **kw):
    return subprocess.run(cmd, capture_output=True, text=True, **kw)


def main():
    c = Checker()
    man = json.load(open(os.path.join(R1, "r1ei_manifest.json"), encoding="utf-8"))
    vendor = open(os.path.join(R1, "vendor", "easy_insert_utils.py"), "rb").read()

    # ---------- (1) PowerShell 5.1: todos os .ps1 com BOM UTF-8 e ASCII puro; chaves/parênteses balanceados; sem `hf download --include`
    ps1 = sorted(glob.glob(os.path.join(ROOT, "**", "*.ps1"), recursive=True))
    c.ok("ps1_encontrados", len(ps1) >= 3 and any(p.endswith("setup_r1ei.ps1") for p in ps1) and any(p.endswith("bench_r1ei.ps1") for p in ps1), [os.path.basename(p) for p in ps1])
    for p in ps1:
        b = open(p, "rb").read(); body = b[len(BOM):] if b.startswith(BOM) else b
        txt = body.decode("ascii", errors="replace")
        # contagem de chaves/parênteses fora de comentários (linhas iniciadas por # e comentários de fim de linha " # ")
        code = "\n".join(("" if l.lstrip().startswith("#") else l.split("  #")[0].split(" # ")[0]) for l in txt.splitlines())
        c.ok(f"ps1_bom_e_ascii:{os.path.basename(p)}", b.startswith(BOM) and all(x < 0x80 for x in body), (b[:3], sum(x >= 0x80 for x in body)))
        c.ok(f"ps1_balanceado:{os.path.basename(p)}", code.count("{") == code.count("}") and code.count("(") == code.count(")"), (code.count("{"), code.count("}"), code.count("("), code.count(")")))
        c.ok(f"ps1_sem_crlf_misto:{os.path.basename(p)}", b"\r\r\n" not in body, "")
    setup = open(os.path.join(R1, "setup_r1ei.ps1"), "rb").read().decode("ascii", errors="replace")
    c.ok("setup_usa_hf_fetch_e_nao_hf_download_include", "hf_fetch.py" in setup and "verify_provenance.py" in setup and "hf download" not in setup and "--include" not in setup, "")
    c.ok("setup_clone_sem_autocrlf", "core.autocrlf=false" in setup and "core.autocrlf false" in setup, "")
    c.ok("setup_checagem_de_disco_simples_so_com_download", "-not $SkipDownload -and $free -lt 20" in setup and "24" not in setup.split("Step \"1.")[0].split("$free")[-1][:60], "")
    bench = open(os.path.join(R1, "bench_r1ei.ps1"), "rb").read().decode("ascii", errors="replace")
    c.ok("bench_label_coincide_com_registro", 'r1ei_kleinbase4b_easyinsert_bf16_1024_$Mode' in bench, "")

    # ---------- .gitattributes na raiz do repositório
    ga = open(os.path.join(REPO, ".gitattributes"), encoding="utf-8").read().splitlines() if os.path.exists(os.path.join(REPO, ".gitattributes")) else []
    need = {"*.ps1 text eol=crlf", "*.py text eol=lf", "*.json text eol=lf", "*.safetensors binary", "*.png binary"}
    c.ok("gitattributes_regras_eol", need <= set(l.strip() for l in ga), sorted(need - set(l.strip() for l in ga)))

    # ---------- (2) provenance robusta a EOL
    crlf = vendor.replace(b"\n", b"\r\n")
    c.ok("vendor_blob_oid_igual_ao_pin", git_blob_oid(vendor) == man["easy_insert"]["files_git_blob_oid"]["utils.py"] == UTILS_BLOB_OID, git_blob_oid(vendor))
    c.ok("manifest_blob_oids_5_arquivos", set(man["easy_insert"]["files_git_blob_oid"]) == set(vp.FILES) and all(len(v) == 40 for v in man["easy_insert"]["files_git_blob_oid"].values()), "")
    c.ok("manifest_eol_note_registra_sha_crlf", UTILS_CRLF_SHA[:8] in man["easy_insert"].get("eol_note", ""), "")
    with tempfile.TemporaryDirectory() as d:
        pc = os.path.join(d, "utils_crlf.py"); open(pc, "wb").write(crlf)
        raw, lf, changed = vp.sha256_normalized(pc)
        c.ok("sha256_normalized_reproduz_bug_crlf", raw == UTILS_CRLF_SHA and lf == UTILS_LF_SHA and changed is True, (raw[:16], lf[:16], changed))
        raw2, lf2, changed2 = vp.sha256_normalized(os.path.join(R1, "vendor", "easy_insert_utils.py"))
        c.ok("sha256_normalized_lf_inalterado", raw2 == lf2 == UTILS_LF_SHA and changed2 is False, "")
        pm = os.path.join(d, "utils_mod.py"); open(pm, "wb").write(crlf.replace(b"def paste_back", b"def paste_back_x", 1))
        c.ok("sha256_normalized_rejeita_conteudo_alterado", vp.sha256_normalized(pm)[1] != UTILS_LF_SHA, "")

        # repositório git real: blobs LF no commit, working tree CRLF (simula autocrlf=true)
        g = os.path.join(d, "clone"); os.makedirs(g)
        files = {"utils.py": vendor, "inference_diffusers.py": b"import utils\nprint('x')\n", "README.md": b"# r\n", "LICENSE": b"Apache\n", "requirements.txt": b"diffusers\n"}
        for f, b in files.items():
            open(os.path.join(g, f), "wb").write(b)
        env = dict(os.environ, GIT_AUTHOR_NAME="t", GIT_AUTHOR_EMAIL="t@t", GIT_COMMITTER_NAME="t", GIT_COMMITTER_EMAIL="t@t")
        for cmd in (["git", "init", "-q"], ["git", "config", "core.autocrlf", "false"], ["git", "add", "-A"], ["git", "commit", "-q", "-m", "pin"]):
            r = run(cmd, cwd=g, env=env); assert r.returncode == 0, r.stderr
        head = run(["git", "rev-parse", "HEAD"], cwd=g).stdout.strip()
        fake = json.loads(json.dumps(man)); fake["easy_insert"]["commit"] = head
        fake["easy_insert"]["files_sha256"] = {f: hashlib.sha256(b).hexdigest() for f, b in files.items()}
        fake["easy_insert"]["files_git_blob_oid"] = {f: git_blob_oid(b) for f, b in files.items()}
        for f, b in files.items():
            open(os.path.join(g, f), "wb").write(b.replace(b"\n", b"\r\n"))      # working tree CRLF
        rep = vp.verify_clone(g, fake)
        c.ok("verify_clone_aceita_working_tree_crlf", rep["ok"] and "git_blob_oid" in rep["method"] and rep.get("head_ok") and rep["files"]["utils.py"]["eol_converted_in_working_tree"] and rep["files"]["utils.py"]["blob_oid_ok"] and rep["files"]["utils.py"]["sha256_raw"] == UTILS_CRLF_SHA,
             {k: v for k, v in rep["files"]["utils.py"].items() if k != "sha256_lf"})
        open(os.path.join(g, "utils.py"), "wb").write(crlf.replace(b"def paste_back", b"def paste_back_x", 1))
        rep2 = vp.verify_clone(g, fake)
        c.ok("verify_clone_rejeita_conteudo_alterado_mesmo_com_blob_ok", (not rep2["ok"]) and rep2["files"]["utils.py"]["blob_oid_ok"] and not rep2["files"]["utils.py"]["sha256_lf_ok"], rep2["files"]["utils.py"]["status"])
        open(os.path.join(g, "utils.py"), "wb").write(crlf)
        bad = json.loads(json.dumps(fake)); bad["easy_insert"]["commit"] = "0" * 40
        rep3 = vp.verify_clone(g, bad)
        c.ok("verify_clone_rejeita_commit_pinado_ausente", (not rep3["ok"]) and "git_ls_tree_failed" in rep3["method"], rep3["method"])
        # Fixture sem .git: nao apagar objetos read-only do Git no Windows.
        no_git = os.path.join(d, "clone_without_git")
        shutil.copytree(g, no_git, ignore=shutil.ignore_patterns(".git"))
        g = no_git
        rep4 = vp.verify_clone(g, fake)
        c.ok("verify_clone_sem_git_usa_sha_lf", rep4["ok"] and rep4["method"] == ["no_git", "sha256_lf_normalized"], rep4["method"])
        os.remove(os.path.join(g, "LICENSE"))
        c.ok("verify_clone_arquivo_ausente", not vp.verify_clone(g, fake)["ok"], "")
        # CLI
        mp = os.path.join(d, "fake_manifest.json"); json.dump(fake, open(mp, "w"))
        open(os.path.join(g, "LICENSE"), "wb").write(files["LICENSE"])
        r = run([sys.executable, os.path.join(R1, "verify_provenance.py"), "--clone-dir", g, "--manifest", mp, "--json-out", os.path.join(d, "prov.json")])
        c.ok("verify_provenance_cli_exit0_e_json", r.returncode == 0 and json.load(open(os.path.join(d, "prov.json")))["ok"], r.stdout[-120:])

        # runner --dry-run aceita clone com utils.py CRLF (registra a conversão) e rejeita conteúdo alterado
        import numpy as np
        from PIL import Image
        A = np.full((800, 600, 3), 190, np.uint8); Ap = os.path.join(d, "A.png"); Image.fromarray(A).save(Ap)
        B = np.full((600, 450, 3), 240, np.uint8); B[100:500, 75:375] = (30, 60, 200); Bp = os.path.join(d, "B.png"); Image.fromarray(B).save(Bp)
        am = np.zeros((800, 600), np.uint8); am[150:650, 150:450] = 255; Am = os.path.join(d, "Am.png"); Image.fromarray(am).save(Am)
        bm = np.zeros((600, 450), np.uint8); bm[100:500, 75:375] = 255; Bm = os.path.join(d, "Bm.png"); Image.fromarray(bm).save(Bm)
        mdl = os.path.join(d, "model"); lora = os.path.join(d, "lora"); os.makedirs(lora)
        for rel in list(man["base_model"]["files_needed_by_runner"]) + man["base_model"]["small_files_needed"]:
            pp = os.path.join(mdl, *rel.split("/")); os.makedirs(os.path.dirname(pp), exist_ok=True); open(pp, "wb").write(b"x")
        open(os.path.join(lora, man["lora"]["file"]), "wb").write(b"not-a-lora")
        cl = os.path.join(d, "ei_crlf"); os.makedirs(cl); open(os.path.join(cl, "utils.py"), "wb").write(crlf)
        base_cmd = [sys.executable, os.path.join(R1, "run_easy_insert.py"), "--a", Ap, "--b", Bp, "--insert-mask", Am, "--ref-mask", Bm, "--model-dir", mdl, "--lora-dir", lora, "--dry-run", "--easy-insert-dir", cl]
        r = run(base_cmd + ["--out", os.path.join(d, "o_crlf.png")])
        j = json.load(open(os.path.join(d, "o_crlf.png.json"))) if os.path.exists(os.path.join(d, "o_crlf.png.json")) else {}
        c.ok("runner_aceita_clone_crlf_e_registra_eol", r.returncode == 3 and "difere do pin" not in (r.stderr + r.stdout) and j.get("utils_source", {}).get("from") == "clone" and j["utils_source"]["working_tree_eol_converted"] is True, (r.returncode, j.get("utils_source")))
        open(os.path.join(cl, "utils.py"), "wb").write(crlf.replace(b"1.2", b"1.5", 1))
        r = run(base_cmd + ["--out", os.path.join(d, "o_bad.png")])
        c.ok("runner_rejeita_clone_crlf_alterado", r.returncode != 0 and "difere do pin" in (r.stderr + r.stdout), (r.stderr + r.stdout).strip()[-100:])

        # ---------- (3) seleção de download do Hugging Face
        pats = hf.allow_patterns_for("base")
        needed = list(man["base_model"]["files_needed_by_runner"]) + man["base_model"]["small_files_needed"]
        not_needed = ["flux-2-klein-base-4b.safetensors", "editing.jpg", "others.jpg", "realism.jpg", "README.md", "LICENSE.md"]
        c.ok("allow_patterns_base_e_lista_com_todos_os_necessarios", isinstance(pats, list) and len(pats) >= 5 and all(any(fnmatch.fnmatch(f, p) for p in pats) for f in needed), [f for f in needed if not any(fnmatch.fnmatch(f, p) for p in pats)])
        c.ok("allow_patterns_base_exclui_single_file_e_jpg", not any(any(fnmatch.fnmatch(f, p) for p in pats) for f in not_needed), [f for f in not_needed if any(fnmatch.fnmatch(f, p) for p in pats)])
        lp = hf.allow_patterns_for("lora")
        c.ok("allow_patterns_lora_pega_o_safetensors", isinstance(lp, list) and any(fnmatch.fnmatch(man["lora"]["file"], p) for p in lp) and not any(fnmatch.fnmatch("x.jpg", p) for p in lp), lp)
        calls = []
        fake_hub = types.ModuleType("huggingface_hub")
        def snapshot_download(**kw):
            calls.append(kw); return kw["local_dir"]
        fake_hub.snapshot_download = snapshot_download
        saved = sys.modules.get("huggingface_hub"); sys.modules["huggingface_hub"] = fake_hub
        try:
            hf.fetch("base", os.path.join(d, "dl_base"), man); hf.fetch("lora", os.path.join(d, "dl_lora"), man)
        finally:
            if saved is not None: sys.modules["huggingface_hub"] = saved
            else: del sys.modules["huggingface_hub"]
        c.ok("fetch_passa_lista_allow_patterns_e_revisao_pinada", len(calls) == 2 and calls[0]["repo_id"] == man["base_model"]["repo"] and calls[0]["revision"] == man["base_model"]["revision"] and calls[0]["allow_patterns"] == hf.BASE_PATTERNS and isinstance(calls[0]["allow_patterns"], list)
             and calls[1]["repo_id"] == man["lora"]["repo"] and calls[1]["revision"] == man["lora"]["revision"] and calls[1]["allow_patterns"] == hf.LORA_PATTERNS and calls[1]["local_dir"].endswith("dl_lora"), [{k: v for k, v in x.items() if k != "local_dir"} for x in calls])
        c.ok("hf_fetch_nao_usa_cli_hf_download", "hf download" not in open(os.path.join(R1, "hf_fetch.py"), encoding="utf-8").read().split('"""', 2)[2], "")
        # verify_download com manifesto pequeno falso
        fm = json.loads(json.dumps(man)); content = {"transformer/diffusion_pytorch_model.safetensors": b"T" * 100, "vae/diffusion_pytorch_model.safetensors": b"V" * 10}
        fm["base_model"]["files_needed_by_runner"] = {k: {"size_bytes": len(v), "sha256": hashlib.sha256(v).hexdigest()} for k, v in content.items()}
        fm["base_model"]["small_files_needed"] = ["model_index.json", "vae/config.json"]
        lb = b"L" * 33; fm["lora"].update({"size_bytes": len(lb), "sha256": hashlib.sha256(lb).hexdigest()})
        dest = os.path.join(d, "dest")
        for rel, b in list(content.items()) + [("model_index.json", b"{}"), ("vae/config.json", b"{}")]:
            pp = os.path.join(dest, *rel.split("/")); os.makedirs(os.path.dirname(pp), exist_ok=True); open(pp, "wb").write(b)
        ok0 = hf.verify_download(dest, fm, "base", check_sha=True)
        c.ok("verify_download_ok_tamanho_e_sha", ok0["ok"] and ok0["files"]["model_index.json"]["status"] == "presente" and ok0["total_bytes"] == 114, {k: v["status"] for k, v in ok0["files"].items()})
        open(os.path.join(dest, "vae", "diffusion_pytorch_model.safetensors"), "wb").write(b"W" * 10)
        r1 = hf.verify_download(dest, fm, "base", check_sha=True); r1s = hf.verify_download(dest, fm, "base", check_sha=False)
        c.ok("verify_download_sha_divergente_so_com_verify_sha", (not r1["ok"]) and r1["files"]["vae/diffusion_pytorch_model.safetensors"]["status"] == "sha256_divergente" and r1s["ok"], "")
        open(os.path.join(dest, "vae", "diffusion_pytorch_model.safetensors"), "wb").write(b"V" * 9)
        r2 = hf.verify_download(dest, fm, "base", check_sha=False)
        c.ok("verify_download_tamanho_divergente", (not r2["ok"]) and r2["files"]["vae/diffusion_pytorch_model.safetensors"]["status"] == "tamanho_divergente", "")
        os.remove(os.path.join(dest, "model_index.json"))
        r3 = hf.verify_download(dest, fm, "base", check_sha=False)
        c.ok("verify_download_ausente", (not r3["ok"]) and r3["files"]["model_index.json"]["status"] == "ausente", "")
        ld = os.path.join(d, "ldest"); os.makedirs(ld)
        c.ok("verify_download_lora_ausente_detectado", not hf.verify_download(ld, fm, "lora", True)["ok"], "")      # o 'Fetching 0 files' do bug
        open(os.path.join(ld, fm["lora"]["file"]), "wb").write(lb)
        c.ok("verify_download_lora_ok", hf.verify_download(ld, fm, "lora", True)["ok"], "")
        fmp = os.path.join(d, "fm.json"); json.dump(fm, open(fmp, "w"))
        r = run([sys.executable, os.path.join(R1, "hf_fetch.py"), "--what", "lora", "--dest", ld, "--manifest", fmp, "--verify-only", "--verify-sha", "--json-out", os.path.join(d, "vl.json")])
        r_bad = run([sys.executable, os.path.join(R1, "hf_fetch.py"), "--what", "base", "--dest", dest, "--manifest", fmp, "--verify-only"])
        c.ok("hf_fetch_cli_verify_only_exit_0_e_1", r.returncode == 0 and json.load(open(os.path.join(d, "vl.json")))["ok"] and r_bad.returncode == 1, (r.returncode, r_bad.returncode))

        # ---------- summarize_runs reproduz as medianas dos 6 runs reais (registro versionado)
        rec = json.load(open(os.path.join(ROOT, "benchmark", "measurements", "r1ei_kleinbase4b_easyinsert_bf16_1024_normal.json"), encoding="utf-8"))
        runs_dir = os.path.join(d, "runs"); os.makedirs(runs_dir)
        label = rec["config_label"]
        for state in ("cold", "warm"):
            for rr, fn in zip(rec["runs"][state]["all_runs"], rec["runs"][state]["files"]):
                j = {"label": f"{label}_{state}", "wall_s": rr["wall_s"], "exit_code": rr["exit_code"], "deadline_hit": rr["deadline_hit"], "verdict": rr["verdict"],
                     "commit_measurement": {"source": "GetPerformanceInfo"}, "peak": {k: rr[k] for k in sr.KEYS if k != "wall_s"}}
                if state == "cold":
                    j["state"] = state      # os warm ficam sem `state` → derivado do label
                json.dump(j, open(os.path.join(runs_dir, fn), "w"))
        json.dump({"label": "klein4b_fp8_2ref_1mp_cold", "state": "cold", "wall_s": 1.0, "exit_code": 0, "deadline_hit": False, "peak": {"vram_used_mb": 1}}, open(os.path.join(runs_dir, "zz_outro.json"), "w"))
        open(os.path.join(runs_dir, "lixo.json"), "w").write("{not json")
        loaded = sr.load_runs(runs_dir, label); summ = sr.summarize(loaded)
        for state in ("cold", "warm"):
            exp = rec["runs"][state]["median"]
            c.ok(f"summarize_runs_medianas_{state}_iguais_ao_registro", summ[state]["n"] == 3 and all(abs(summ[state]["median"][k] - exp[k]) < 1e-9 for k in exp) and summ[state]["all_exit_zero"] and not summ[state]["any_deadline"]
                 and summ[state]["wall_s_min_max"] == rec["runs"][state]["wall_s_min_max"], {k: (summ[state]["median"].get(k), exp[k]) for k in exp if abs(summ[state]["median"].get(k, -1) - exp[k]) >= 1e-9})
        # as 14 medianas também batem com a mediana calculada diretamente dos all_runs do registro (checagem interna do registro)
        internal_ok = all(abs(st.median([r[k] for r in rec["runs"][s_]["all_runs"]]) - rec["runs"][s_]["median"][k]) < 1e-9 for s_ in ("cold", "warm") for k in rec["runs"][s_]["median"])
        c.ok("registro_r1ei_medianas_consistentes_com_all_runs", internal_ok and rec["runs"]["cold"]["n"] == rec["runs"]["warm"]["n"] == 3 and rec["eligibility"]["cold_median_s"] == rec["runs"]["cold"]["median"]["wall_s"], "")
        cmp_ = rec["comparison_with_klein4b_fp8_2ref_1mp"]["cold_median"]
        klein = json.load(open(os.path.join(ROOT, "benchmark", "measurements", "klein4b_fp8_2ref_1mp.json"), encoding="utf-8"))["runs"]["cold"]["median"]
        c.ok("registro_r1ei_comparacao_com_klein_consistente", cmp_["klein4b"]["wall_s"] == klein["wall_s"] and abs(cmp_["wall_ratio"] - cmp_["r1ei"]["wall_s"] / klein["wall_s"]) < 5e-4 and abs(cmp_["delta_vram_mb"] - (cmp_["r1ei"]["vram_used_mb"] - klein["vram_used_mb"])) < 0.1
             and abs(cmp_["delta_sys_ram_mb"] - (cmp_["r1ei"]["sys_ram_used_mb"] - klein["sys_ram_used_mb"])) < 0.1, cmp_)
        r = run([sys.executable, os.path.join(R1, "summarize_runs.py"), "--runs-dir", runs_dir, "--label-prefix", label, "--candidate", "R1-EI teste", "--out", os.path.join(d, "rec_out.json")])
        out = json.load(open(os.path.join(d, "rec_out.json"))) if r.returncode == 0 else {}
        c.ok("summarize_runs_cli_gera_registro", r.returncode == 0 and out.get("runs", {}).get("cold", {}).get("median", {}).get("wall_s") == rec["runs"]["cold"]["median"]["wall_s"] and out["generated_from"]["n_files"] == 6, r.stderr[-200:])
        r = run([sys.executable, os.path.join(R1, "summarize_runs.py"), "--runs-dir", runs_dir, "--label-prefix", "nao_existe", "--candidate", "x", "--out", os.path.join(d, "none.json")])
        c.ok("summarize_runs_sem_runs_exit2", r.returncode == 2, r.returncode)

    # ---------- (5) pynvml deprecado → nvidia-ml-py; import do measure_run sem aviso; semântica preservada
    with warnings.catch_warnings(record=True) as w:
        warnings.simplefilter("always")
        import importlib; mr = importlib.import_module("measure_run")
    c.ok("measure_run_import_sem_aviso_pynvml", not any("pynvml" in str(x.message) for x in w), [str(x.message)[:60] for x in w])
    c.ok("measure_run_nvml_package_name", hasattr(mr, "nvml_package_name") and (mr.nvml_package_name() is None or isinstance(mr.nvml_package_name(), str)), mr.nvml_package_name())
    src = open(os.path.join(ROOT, "tools", "measure_run.py"), encoding="utf-8").read()
    c.ok("measure_run_grava_nvml_package_e_mantem_nvml_calls", '"nvml_package"' in src and "nvmlDeviceGetMemoryInfo" in src and "nvmlDeviceGetComputeRunningProcesses" in src, "")
    return c.done("test_r1ei_infra")


if __name__ == "__main__":
    sys.exit(main())
