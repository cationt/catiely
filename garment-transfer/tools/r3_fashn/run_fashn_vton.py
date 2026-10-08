#!/usr/bin/env python3
"""run_fashn_vton.py — runner da rota R3 (FASHN VTON 1.5) em processo próprio, 100 % offline, com sidecar de proveniência e fases.

Executa o pipeline upstream `fashn_vton.TryOnPipeline` SEM alterar o algoritmo. Únicas adaptações (documentadas):
  (a) fonte dos pesos do parser humano: `FashnHumanParser(model_id=<weights-dir>/fashn-human-parser)` (diretório local verificado)
      em vez do download implícito de 'fashn-ai/fashn-human-parser' para o cache HF;
  (b) instrumentação de tempo: wrappers em pose_model / hp_model.predict / _sample / _setup_* (medição; sem efeito nos resultados).
Modos: --segmentation-free (segfree: parser executado, masking da pessoa DESABILITADO) | --masked (parser executado, masking habilitado).
Sem --allow-online: HF_HUB_OFFLINE=1 etc. ANTES dos imports + guarda de rede (socket.connect fora de loopback → erro).
ONNX Runtime: `import torch` antes de `import onnxruntime`, `preload_dlls()`; CUDAExecutionProvider exigido — fallback para CPU é
detectado via session.get_providers() e reprovado (exit 5) salvo --allow-ort-cpu-fallback; providers efetivos vão para o sidecar.

Saída: <out>.png e sidecar <out>.png.json. Exit: 0 ok · 2 uso/entradas · 3 pins/código divergentes · 4 CUDA indisponível · 5 ORT em CPU
(sem permissão) · 6 exceção em runtime.
--dry-run: sem torch; confere pesos/código, carrega A/B, calcula a geometria (pré-resize, padding, canvas) com o transforms.py upstream
            carregado por caminho; grava o plano no sidecar.
--smoke:   carga completa + pose + parser + pré-processamento + amostragem com 1 passo (valida caminho/VRAM/providers; NÃO é benchmark).
"""
import argparse, hashlib, importlib.util, json, os, platform, socket, sys, time

HERE = os.path.dirname(os.path.abspath(__file__))
MANIFEST = json.load(open(os.path.join(HERE, "r3_manifest.json"), encoding="utf-8"))
NET_ATTEMPTS = []


def sha256_file(p):
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 22), b""):
            h.update(chunk)
    return h.hexdigest()


def sha256_lf(p):
    b = open(p, "rb").read(); lf = b.replace(b"\r\n", b"\n").replace(b"\r", b"\n")
    return hashlib.sha256(lf).hexdigest(), lf != b


def enforce_offline(weights_dir):
    """Define o ambiente offline/determinístico ANTES de importar torch/transformers/huggingface_hub e instala a guarda de rede."""
    env = {"HF_HUB_OFFLINE": "1", "TRANSFORMERS_OFFLINE": "1", "HF_DATASETS_OFFLINE": "1", "HF_HUB_DISABLE_TELEMETRY": "1", "DISABLE_TELEMETRY": "1",
           "HF_HOME": os.path.join(os.path.abspath(weights_dir), "hf_home"), "TOKENIZERS_PARALLELISM": "false"}
    for k, v in env.items():
        os.environ[k] = v
    orig_connect = socket.socket.connect; orig_connect_ex = socket.socket.connect_ex

    def _blocked(addr):
        host = addr[0] if isinstance(addr, tuple) else str(addr)
        return host not in ("127.0.0.1", "::1", "localhost")

    def connect(self, addr):
        if _blocked(addr):
            NET_ATTEMPTS.append(str(addr)); raise RuntimeError(f"[r3] tentativa de conexão de rede bloqueada em modo offline: {addr}")
        return orig_connect(self, addr)

    def connect_ex(self, addr):
        if _blocked(addr):
            NET_ATTEMPTS.append(str(addr)); raise RuntimeError(f"[r3] tentativa de conexão de rede bloqueada em modo offline: {addr}")
        return orig_connect_ex(self, addr)
    socket.socket.connect = connect; socket.socket.connect_ex = connect_ex
    return env


def package_dir(name):
    """Diretório de um pacote instalado SEM executar o seu __init__ (find_spec de top-level não importa o módulo)."""
    spec = importlib.util.find_spec(name)
    if spec is None or not spec.submodule_search_locations:
        return None
    return list(spec.submodule_search_locations)[0]


def check_code(rec):
    """sha256 (LF-normalizado) dos arquivos dos pacotes instalados fashn_vton e fashn_human_parser contra o manifesto."""
    out = {"ok": True, "packages": {}}
    for key, pkg in (("vton", "fashn_vton"), ("human_parser", "fashn_human_parser")):
        entry = MANIFEST["code_repos"][key]; prefix = entry["package_files_prefix"] + pkg + "/"
        pdir = package_dir(pkg); files = {}
        p_ok = pdir is not None
        for rel, info in entry["files"].items():
            if not rel.startswith(prefix):
                continue
            sub = rel[len(prefix):]
            p = os.path.join(pdir, *sub.split("/")) if pdir else None
            if not p or not os.path.exists(p):
                files[sub] = {"status": "ausente"}; p_ok = False; continue
            sha, eol = sha256_lf(p)
            files[sub] = {"status": "ok" if sha == info["sha256"] else "sha256_divergente", "eol_converted": eol}
            p_ok &= sha == info["sha256"]
        out["packages"][key] = {"dir": pdir, "ok": p_ok, "files": files}; out["ok"] &= p_ok
    rec["code_check"] = out
    return out["ok"]


def check_weights(args, rec):
    sys.path.insert(0, HERE)
    import fetch_weights as fw  # noqa: E402
    rep = fw.verify(args.weights_dir, MANIFEST, None, check_sha=args.verify_sha)
    rec["pin_check"] = {"method": "sha256" if args.verify_sha else "size", "ok": rep["ok"],
                        "files": {f"{c}:{rel}": e["status"] for c, comp in rep["components"].items() for rel, e in comp["files"].items()}}
    return rep["ok"]


def load_transforms_by_path():
    """Carrega fashn_vton/preprocessing/transforms.py por caminho (só cv2/numpy/PIL), sem executar fashn_vton/__init__ (que importa torch)."""
    pdir = package_dir("fashn_vton")
    path = os.path.join(pdir, "preprocessing", "transforms.py") if pdir else None
    if not path or not os.path.exists(path):
        raise SystemExit("[r3] fashn_vton não instalado (transforms.py ausente) — rode o setup")
    spec = importlib.util.spec_from_file_location("r3_transforms", path); mod = importlib.util.module_from_spec(spec); spec.loader.exec_module(mod)
    return mod


def geometry(a_img, b_img, mod):
    h, w = MANIFEST["pipeline_facts"]["model_input_hw"]; m = max(h, w)
    pre = mod.AspectPreserveResize(target_size=(m, m), mode="fit", backend="pil")
    a2 = pre(a_img, allow_upsampling=False); b2 = pre(b_img, allow_upsampling=False)
    rp = mod.ResizePad((w, h), backend="opencv")
    import numpy as np
    a3 = rp.resize_fn(np.zeros((a2.size[1], a2.size[0], 3), np.uint8)); b3 = rp.resize_fn(np.zeros((b2.size[1], b2.size[0], 3), np.uint8))
    pad_a = rp.pad_fn._calculate_needed_padding(a3.shape[1], a3.shape[0], w, h)
    return {"A_original_wh": list(a_img.size), "B_original_wh": list(b_img.size), "A_pre_resized_wh": list(a2.size), "B_pre_resized_wh": list(b2.size),
            "A_in_canvas_wh": [a3.shape[1], a3.shape[0]], "B_in_canvas_wh": [b3.shape[1], b3.shape[0]], "model_input_wh": [w, h],
            "A_padding_lrtb_in_model_canvas": {"left": pad_a[0], "top": pad_a[1], "right": pad_a[2], "bottom": pad_a[3]},
            "output_wh_expected": [a3.shape[1], a3.shape[0]], "pixels_generated": w * h,
            "note": "canvas fixo 576×864 (checkpoint); A pré-redimensionada para caber em 864 sem upsampling, depois ajustada ao canvas 576×864 com padding simétrico; saída = unpad → tamanho de A dentro do canvas"}


class Timed:
    """Wrapper de medição para objetos chamáveis (pose_model) e funções (predict, _sample): registra início/fim de cada chamada."""

    def __init__(self, inner, name, log, sync):
        self.inner = inner; self.name = name; self.log = log; self.sync = sync

    def __call__(self, *a, **k):
        self.sync(); t0 = time.perf_counter()
        r = self.inner(*a, **k)
        self.sync(); self.log.append((self.name, t0, time.perf_counter()))
        return r

    def __getattr__(self, item):
        return getattr(self.inner, item)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--person", required=True, help="A (pessoa-alvo)"); ap.add_argument("--garment", required=True, help="B (peça de referência)")
    ap.add_argument("--weights-dir", required=True, help="layout de fetch_weights.py: model.safetensors, dwpose/, fashn-human-parser/")
    ap.add_argument("--hp-dir", help="diretório local do parser (padrão <weights-dir>/fashn-human-parser)")
    ap.add_argument("--category", choices=["tops", "bottoms", "one-pieces"], required=True)
    ap.add_argument("--garment-photo-type", choices=["model", "flat-lay"], default="model")
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--segmentation-free", dest="segmentation_free", action="store_true", help="segfree: parser executado; masking da pessoa desabilitado (default upstream)")
    g.add_argument("--masked", dest="segmentation_free", action="store_false", help="masked: parser executado; masking da pessoa habilitado")
    ap.add_argument("--num-samples", type=int, default=1); ap.add_argument("--num-timesteps", type=int, default=30); ap.add_argument("--guidance-scale", type=float, default=1.5)
    ap.add_argument("--skip-cfg-last-n-steps", type=int, default=1); ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--out", required=True); ap.add_argument("--device", default="cuda")
    ap.add_argument("--inputs-decision", help="decisão do setup R3: exige tops/model e SHA256 das A/B Klein/R1-EI")
    ap.add_argument("--allow-ort-cpu-fallback", action="store_true", help="não reprovar se o ORT cair para CPU (sempre registrado)")
    ap.add_argument("--verify-sha", action="store_true", help="sha256 completo dos pesos (lento; o setup faz isso; o bench confere tamanhos)")
    ap.add_argument("--allow-code-mismatch", action="store_true"); ap.add_argument("--allow-online", action="store_true", help="NÃO usar no benchmark")
    ap.add_argument("--dry-run", action="store_true"); ap.add_argument("--smoke", action="store_true", help="carga completa + 1 passo de amostragem")
    ap.add_argument("--mode-label", help="rótulo livre para o sidecar (ex.: segfree/masked)")
    args = ap.parse_args()
    if args.num_samples != 1:
        print("[r3] aviso: protocolo de viabilidade usa num_samples=1", file=sys.stderr)
    out_json = args.out + ".json"; os.makedirs(os.path.dirname(os.path.abspath(args.out)) or ".", exist_ok=True)
    hp_dir = args.hp_dir or os.path.join(args.weights_dir, "fashn-human-parser")
    mode = "segfree" if args.segmentation_free else "masked"
    rec = {"route": "R3", "runner_version": "1", "mode": mode, "mode_label": args.mode_label or mode, "dry_run": args.dry_run, "smoke": args.smoke, "args": vars(args),
           "started_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), "host": {"platform": platform.platform(), "python": sys.version.split()[0]},
           "pins": {"vton_commit": MANIFEST["code_repos"]["vton"]["commit"], "human_parser_commit": MANIFEST["code_repos"]["human_parser"]["commit"],
                    "tryon_revision": MANIFEST["components"]["tryon"]["revision"], "dwpose_revision": MANIFEST["components"]["dwpose"]["revision"],
                    "human_parser_revision": MANIFEST["components"]["human_parser"]["revision"], "model_sha256": MANIFEST["components"]["tryon"]["files"]["model.safetensors"]["sha256"]},
           "params": {"category": args.category, "garment_photo_type": args.garment_photo_type, "segmentation_free": args.segmentation_free, "num_samples": args.num_samples,
                      "num_timesteps": args.num_timesteps, "guidance_scale": args.guidance_scale, "skip_cfg_last_n_steps": args.skip_cfg_last_n_steps, "seed": args.seed},
           "semantics": {"segfree": MANIFEST["pipeline_facts"]["segfree_semantics"], "masked": MANIFEST["pipeline_facts"]["masked_semantics"]}[mode]}
    offline_env = None
    if not args.allow_online:
        offline_env = enforce_offline(args.weights_dir)
    rec["offline"] = {"enforced": not args.allow_online, "env": offline_env, "net_guard": not args.allow_online, "hp_source": "local_dir", "hp_dir": hp_dir}

    for k in ("person", "garment"):
        if not os.path.exists(getattr(args, k)):
            print(f"[r3] arquivo ausente: {k} = {getattr(args, k)}", file=sys.stderr); sys.exit(2)
        rec.setdefault("inputs_sha256", {})[k] = sha256_file(getattr(args, k))
    from PIL import Image
    a_img = Image.open(args.person).convert("RGB"); b_img = Image.open(args.garment).convert("RGB")

    def dump(verdict, code=None):
        rec["verdict"] = verdict; rec["net_attempts_blocked"] = list(NET_ATTEMPTS); rec["finished_utc"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        json.dump(rec, open(out_json, "w", encoding="utf-8"), indent=1, ensure_ascii=False)
        print(f"[r3] {verdict} → {out_json}")
        if code is not None:
            sys.exit(code)

    if args.inputs_decision:
        sys.path.insert(0, HERE)
        from verify_inputs import verify
        try:
            if args.category != "tops" or args.garment_photo_type != "model":
                raise ValueError("baseline R3 exige tops/model; two-pass e outra arquitetura")
            rec["input_check"] = verify(args.person, args.garment, args.inputs_decision)
        except (OSError, ValueError, KeyError) as e:
            rec["input_check"] = {"ok": False, "error": str(e)}
            dump("FAIL:entradas_baseline_divergentes", 2)

    weights_ok = check_weights(args, rec); code_ok = check_code(rec)
    if not weights_ok:
        dump("FAIL:pesos_divergentes_ou_ausentes", 3)
    if not code_ok and not args.allow_code_mismatch:
        dump("FAIL:codigo_divergente_do_pin", 3)
    try:
        rec["geometry"] = geometry(a_img, b_img, load_transforms_by_path())
    except SystemExit:
        raise
    except Exception as e:
        rec["geometry"] = {"error": str(e)}
    if args.dry_run:
        rec["plan"] = {"mode": mode, "steps": args.num_timesteps, "cfg_passes_per_step": 2, "transformer_forwards": args.num_timesteps, "batch_per_forward": 2 * args.num_samples,
                       "parser_runs": 2, "dwpose_runs": 1 if args.garment_photo_type == "flat-lay" else 2}
        dump("DRY_RUN_OK", 0)

    # ---------------- execução real (torch antes de onnxruntime; preload_dlls) ----------------
    t_proc0 = time.perf_counter()
    import torch  # noqa: E402
    import onnxruntime as ort  # noqa: E402
    preload = {"called": False}
    if hasattr(ort, "preload_dlls"):
        try:
            ort.preload_dlls(); preload["called"] = True
        except Exception as e:
            preload["error"] = str(e)
    try:
        from onnxruntime.capi import build_and_package_info as bpi  # noqa: E402
        ort_build = {"package": getattr(bpi, "package_name", None), "cuda_version": getattr(bpi, "cuda_version", None), "cudnn_version": getattr(bpi, "cudnn_version", None)}
    except Exception:
        ort_build = None
    import transformers, numpy as np, cv2  # noqa: E402
    import fashn_vton, fashn_human_parser  # noqa: E402
    from fashn_vton import TryOnPipeline  # noqa: E402
    from fashn_human_parser import FashnHumanParser  # noqa: E402
    rec["versions"] = {"torch": torch.__version__, "cuda": torch.version.cuda, "cudnn": torch.backends.cudnn.version(), "onnxruntime": ort.__version__, "onnxruntime_build": ort_build,
                       "onnxruntime_available_providers": ort.get_available_providers(), "onnxruntime_device": ort.get_device(), "preload_dlls": preload,
                       "transformers": transformers.__version__, "numpy": np.__version__, "opencv": cv2.__version__, "fashn_vton": getattr(fashn_vton, "__version__", None),
                       "fashn_human_parser": getattr(fashn_human_parser, "__version__", None), "python": sys.version.split()[0]}
    want_cuda = args.device.startswith("cuda")
    if want_cuda and not torch.cuda.is_available():
        dump("FAIL:cuda_indisponivel", 4)
    if want_cuda:
        p = torch.cuda.get_device_properties(0)
        rec["gpu"] = {"name": p.name, "total_mem_mb": round(p.total_memory / 2**20, 1), "sm": f"{p.major}.{p.minor}", "bf16_supported": torch.cuda.is_bf16_supported()}
        torch.cuda.reset_peak_memory_stats()
    sync = (lambda: torch.cuda.synchronize()) if want_cuda else (lambda: None)
    log = []; phases = {}

    class R3Pipeline(TryOnPipeline):
        """Única mudança funcional: o parser vem do diretório local verificado (fonte dos pesos), não do hub. _setup_* só ganham tempo."""

        def _setup_tryon_model(self):
            t = time.perf_counter(); super()._setup_tryon_model(); sync(); phases["load_tryon_s"] = round(time.perf_counter() - t, 3)

        def _setup_pose_model(self):
            t = time.perf_counter(); super()._setup_pose_model(); phases["load_dwpose_s"] = round(time.perf_counter() - t, 3)

        def _setup_hp_model(self):
            t = time.perf_counter()
            hp_device = "cuda" if self.device.type == "cuda" else "cpu"
            self.hp_model = FashnHumanParser(model_id=hp_dir, device=hp_device)
            sync(); phases["load_human_parser_s"] = round(time.perf_counter() - t, 3)

    try:
        t0 = time.perf_counter()
        pipe = R3Pipeline(weights_dir=args.weights_dir, device=args.device if want_cuda else "cpu")
        sync(); phases["load_total_s"] = round(time.perf_counter() - t0, 3)
        assert tuple(pipe.tryon_model.input_shape) == tuple(MANIFEST["pipeline_facts"]["model_input_hw"]), pipe.tryon_model.input_shape
        rec["dtype"] = str(pipe.inference_dtype)
        # providers efetivos do ORT (DWPose): sessões criadas em wholebody.Wholebody
        wb = pipe.pose_model.pose_estimation
        prov = {"requested": ["CUDAExecutionProvider"] if want_cuda else ["CPUExecutionProvider"],
                "effective_det": wb.session_det.get_providers(), "effective_pose": wb.session_pose.get_providers()}
        prov["cuda_effective"] = prov["effective_det"][0] == "CUDAExecutionProvider" and prov["effective_pose"][0] == "CUDAExecutionProvider"
        prov["fallback_to_cpu"] = want_cuda and not prov["cuda_effective"]
        rec["onnx_providers"] = prov
        if prov["fallback_to_cpu"] and not args.allow_ort_cpu_fallback:
            dump("FAIL:ort_cuda_fallback_para_cpu", 5)
        # instrumentação (medição apenas)
        pipe.pose_model = Timed(pipe.pose_model, "pose", log, sync)
        pipe.hp_model.predict = Timed(pipe.hp_model.predict, "parse", log, sync)
        pipe._sample = Timed(pipe._sample, "sampling", log, sync)
        steps = 1 if args.smoke else args.num_timesteps
        t_call0 = time.perf_counter()
        result = pipe(person_image=a_img, garment_image=b_img, category=args.category, garment_photo_type=args.garment_photo_type, num_samples=args.num_samples,
                      num_timesteps=steps, guidance_scale=args.guidance_scale, skip_cfg_last_n_steps=args.skip_cfg_last_n_steps, seed=args.seed,
                      segmentation_free=args.segmentation_free)
        sync(); t_call1 = time.perf_counter()
        img = result.images[0]; img.save(args.out)
        t_save = time.perf_counter()
        # fases a partir do log de chamadas (ordem upstream: pose A, pose B (se model), parse A, parse B, pré-proc, sampling, pós-proc)
        poses = [x for x in log if x[0] == "pose"]; parses = [x for x in log if x[0] == "parse"]; samp = [x for x in log if x[0] == "sampling"]
        if poses: phases["pose_A_s"] = round(poses[0][2] - poses[0][1], 3)
        if len(poses) > 1: phases["pose_B_s"] = round(poses[1][2] - poses[1][1], 3)
        if parses: phases["parse_A_s"] = round(parses[0][2] - parses[0][1], 3)
        if len(parses) > 1: phases["parse_B_s"] = round(parses[1][2] - parses[1][1], 3)
        if samp:
            last_pre = max([x[2] for x in poses + parses] or [t_call0])
            phases["preprocessing_s"] = round(samp[0][1] - last_pre, 3); phases["sampling_s"] = round(samp[0][2] - samp[0][1], 3); phases["postprocess_s"] = round(t_call1 - samp[0][2], 3)
            phases["pose_draw_before_parse_s"] = round(parses[0][1] - poses[-1][2], 3) if poses and parses else None
        phases["call_total_s"] = round(t_call1 - t_call0, 3); phases["save_s"] = round(t_save - t_call1, 3)
        phases["process_total_s_since_torch_import"] = round(t_save - t_proc0, 3); phases["steps_executed"] = steps
        rec["phases"] = phases
        rec["output"] = {"path": args.out, "wh": list(img.size), "sha256": sha256_file(args.out), "n_images": len(result.images)}
        if want_cuda:
            rec["torch_vram"] = {"max_allocated_mb": round(torch.cuda.max_memory_allocated() / 2**20, 1), "max_reserved_mb": round(torch.cuda.max_memory_reserved() / 2**20, 1)}
        dump("SMOKE_OK" if args.smoke else "ok", 0)
    except SystemExit:
        raise
    except Exception as e:
        import traceback
        rec["error"] = {"type": type(e).__name__, "message": str(e), "traceback": traceback.format_exc()[-4000:]}; rec["phases"] = phases
        dump(f"FAIL:exception:{type(e).__name__}", 6)


if __name__ == "__main__":
    main()
