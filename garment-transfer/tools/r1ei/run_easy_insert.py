#!/usr/bin/env python3
r"""
run_easy_insert.py — runner da rota R1-EI (FLUX.2-klein-base-4B + Easy-Insert) para a medição de viabilidade no hardware-alvo.

Reproduz EXATAMENTE o pipeline do upstream (huan-yin/Easy-Insert @ 82094484, backend Diffusers = `inference_diffusers.py`, o mesmo
da demo oficial do autor), com uma única diferença deliberada: o carregamento dos modelos é SEQUENCIAL para caber em 12 GB de VRAM
e 16 GB de RAM (o upstream faz `pipe.to("cuda")` com tudo em bf16 ≈ 15 GB, que não cabe):

  1. text encoder Qwen3-4B (bf16) → GPU → embeddings do prompt FIXO do Easy-Insert e do prompt negativo "" → CPU → TE liberado;
  2. Flux2KleinPipeline sem text_encoder/tokenizer: transformer bf16 + LoRA (PEFT) + VAE → GPU;
  3. denoise (15 passos, CFG 4 = 2 passes do transformer por passo) com `prompt_embeds`/`negative_prompt_embeds` pré-computados,
     saída em latente; transformer vai para CPU; VAE decodifica; `paste_back` sem feather (utils.py do upstream, byte-idêntico).

Pré-processamento = `utils.py` do upstream (vendorado em tools/r1ei/vendor/, sha256 conferido antes de importar):
recorte quadrado em torno da bbox da máscara (crop_scale 1.2) → 1024² → buraco branco (background) / objeto sobre branco (referência).

Modos de memória (--mode): normal (bf16 sequencial, padrão) · fp8 (transformer com layerwise casting fp8→bf16; só se normal estourar)
· offload (enable_sequential_cpu_offload; lento; último recurso). 100 % offline: HF_HUB_OFFLINE=1 e TRANSFORMERS_OFFLINE=1 são
forçados; só caminhos locais são aceitos.

Saída: PNG final (grade de A) + sidecar JSON (<out>.json) com tempos por fase, pico de VRAM (torch), versões, GPU, sha256 das entradas,
conferência dos pins (LoRA sha256 obrigatório; arquivos-base por tamanho, ou sha com --verify-base-sha), crop_box e argumentos.
--dry-run: sem torch; confere arquivos/pins, pré-processa, grava as entradas exatas do modelo (<out>_inputs/) e o plano em JSON.
Exit: 0 ok · 2 uso/arquivos · 3 pins divergentes · 4 falha de execução (OOM etc.).
"""
import argparse, hashlib, json, os, platform, sys, time

HERE = os.path.dirname(os.path.abspath(__file__))
MANIFEST = json.load(open(os.path.join(HERE, "r1ei_manifest.json"), encoding="utf-8"))
PROMPT = MANIFEST["easy_insert"]["upstream_defaults"]["prompt"]
UTILS_SHA = MANIFEST["easy_insert"]["files_sha256"]["utils.py"]


def sha256_file(p, limit=None):
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 22), b""):
            h.update(chunk)
    return h.hexdigest()


def load_utils(easy_insert_dir):
    """Importa utils.py do clone (se dado e byte-idêntico ao pin) ou a cópia vendorada; qualquer divergência é erro."""
    candidates = []
    if easy_insert_dir:
        candidates.append(("clone", os.path.join(easy_insert_dir, "utils.py")))
    candidates.append(("vendor", os.path.join(HERE, "vendor", "easy_insert_utils.py")))
    for src, path in candidates:
        if not os.path.exists(path):
            if src == "clone":
                raise SystemExit(f"[r1ei] utils.py não encontrado no clone: {path}")
            continue
        real = sha256_file(path)
        if real != UTILS_SHA:
            raise SystemExit(f"[r1ei] utils.py ({src}) difere do pin do upstream: {real[:16]}… ≠ {UTILS_SHA[:16]}… — não execute com pré-processamento alterado")
        import importlib.util
        spec = importlib.util.spec_from_file_location("easy_insert_utils", path)
        mod = importlib.util.module_from_spec(spec); spec.loader.exec_module(mod)
        return mod, src, path
    raise SystemExit("[r1ei] nenhum utils.py disponível")


def check_pins(args, verify_base_sha):
    """LoRA: sha256 obrigatório. Base: tamanhos sempre; sha256 se pedido. Retorna (ok, relatório)."""
    rep = {"lora": {}, "base": {}, "ok": True}
    lora_path = args.lora_file or os.path.join(args.lora_dir, MANIFEST["lora"]["file"])
    rep["lora"]["path"] = lora_path
    if not os.path.exists(lora_path):
        rep["lora"]["status"] = "ausente"; rep["ok"] = False
    else:
        rep["lora"]["size_bytes"] = os.path.getsize(lora_path)
        rep["lora"]["sha256"] = sha256_file(lora_path)
        rep["lora"]["status"] = "ok" if rep["lora"]["sha256"] == MANIFEST["lora"]["sha256"] else "sha256_divergente"
        rep["ok"] &= rep["lora"]["status"] == "ok"
    for rel, info in MANIFEST["base_model"]["files_needed_by_runner"].items():
        p = os.path.join(args.model_dir, *rel.split("/"))
        e = {"path": p}
        if not os.path.exists(p):
            e["status"] = "ausente"; rep["ok"] = False
        else:
            e["size_bytes"] = os.path.getsize(p)
            if e["size_bytes"] != info["size_bytes"]:
                e["status"] = "tamanho_divergente"; rep["ok"] = False
            elif verify_base_sha:
                e["sha256"] = sha256_file(p); e["status"] = "ok" if e["sha256"] == info["sha256"] else "sha256_divergente"
                rep["ok"] &= e["status"] == "ok"
            else:
                e["status"] = "tamanho_ok(sha_nao_verificado)"
        rep["base"][rel] = e
    for rel in MANIFEST["base_model"]["small_files_needed"]:
        if not os.path.exists(os.path.join(args.model_dir, *rel.split("/"))):
            rep["base"][rel] = {"status": "ausente"}; rep["ok"] = False
    return rep["ok"], rep


def preprocess(utils, args, inputs_dir):
    from PIL import Image
    A = Image.open(args.a).convert("RGB"); B = Image.open(args.b).convert("RGB")
    ins = Image.open(args.insert_mask).convert("L"); refm = Image.open(args.ref_mask).convert("L")
    if ins.size != A.size:
        raise SystemExit(f"[r1ei] insert-mask {ins.size} ≠ A {A.size} (a máscara deve estar na grade de A)")
    if refm.size != B.size:
        raise SystemExit(f"[r1ei] ref-mask {refm.size} ≠ B {B.size} (a máscara deve estar na grade de B)")
    if ins.getbbox() is None or refm.getbbox() is None:
        raise SystemExit("[r1ei] máscara vazia (insert ou ref) — o upstream exige ambas")
    background, gt_crop, crop_box, src_mask_c = utils.process_source(A, ins, args.size, crop_scale=args.crop_scale)
    ref = utils.process_reference(B, refm, args.size, crop_scale=args.crop_scale)
    os.makedirs(inputs_dir, exist_ok=True)
    background.save(os.path.join(inputs_dir, "image1_background_masked_1024.png"))
    ref.save(os.path.join(inputs_dir, "image2_reference_on_white_1024.png"))
    gt_crop.save(os.path.join(inputs_dir, "A_crop_1024.png"))
    meta = {"A_size": A.size, "B_size": B.size, "crop_box_on_A": list(crop_box), "crop_side_px": crop_box[2] - crop_box[0],
            "insert_bbox_on_A": list(ins.getbbox()), "ref_bbox_on_B": list(refm.getbbox()), "crop_scale": args.crop_scale, "size": args.size,
            "note": "image1/image2 são EXATAMENTE as duas imagens passadas ao pipeline (ordem: background, referência)"}
    return A, background, ref, crop_box, src_mask_c, meta


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--a", required=True, help="imagem A (pessoa-alvo)"); ap.add_argument("--b", required=True, help="imagem B (peça de referência)")
    ap.add_argument("--insert-mask", required=True, help="máscara binária na grade de A: onde a peça deve nascer (branco)")
    ap.add_argument("--ref-mask", required=True, help="máscara binária na grade de B: a peça (branco)")
    ap.add_argument("--out", required=True, help="PNG de saída (grade de A); sidecar <out>.json")
    ap.add_argument("--model-dir", required=True, help="diretório local de black-forest-labs/FLUX.2-klein-base-4B (layout diffusers)")
    ap.add_argument("--lora-dir", help="diretório local de LiXiY/Easy-Insert"); ap.add_argument("--lora-file", help="caminho direto do easy-insert-diffusers.safetensors")
    ap.add_argument("--easy-insert-dir", help="clone de huan-yin/Easy-Insert (opcional; utils.py conferido por sha256)")
    ap.add_argument("--size", type=int, default=MANIFEST["easy_insert"]["upstream_defaults"]["image_size"])
    ap.add_argument("--crop-scale", type=float, default=MANIFEST["easy_insert"]["upstream_defaults"]["crop_scale"])
    ap.add_argument("--steps", type=int, default=MANIFEST["easy_insert"]["upstream_defaults"]["num_inference_steps"])
    ap.add_argument("--cfg", type=float, default=MANIFEST["easy_insert"]["upstream_defaults"]["guidance_scale"])
    ap.add_argument("--seed", type=int, default=MANIFEST["easy_insert"]["upstream_defaults"]["seed"])
    ap.add_argument("--prompt", default=PROMPT, help="prompt fixo do upstream (não alterar na medição de viabilidade)")
    ap.add_argument("--mode", choices=["normal", "fp8", "offload"], default="normal")
    ap.add_argument("--te-layers", default="9,18,27", help="camadas ocultas do Qwen3 usadas pelo Flux2KleinPipeline (padrão do diffusers)")
    ap.add_argument("--vae-tiling", action="store_true", help="VAE em tiles no decode (reduz pico de VRAM)")
    ap.add_argument("--keep-transformer-on-gpu-for-decode", action="store_true", help="não mover o transformer para CPU antes do decode")
    ap.add_argument("--verify-base-sha", action="store_true", help="sha256 dos 4 arquivos grandes da base (≈ 15 GB; fazer ao menos uma vez)")
    ap.add_argument("--dry-run", action="store_true", help="sem torch: confere pins, pré-processa, grava plano")
    ap.add_argument("--allow-online", action="store_true", help="NÃO usar na medição: permite rede (padrão: HF_HUB_OFFLINE=1)")
    args = ap.parse_args()
    if not args.lora_dir and not args.lora_file:
        ap.error("informe --lora-dir ou --lora-file")
    if not args.allow_online:
        os.environ["HF_HUB_OFFLINE"] = "1"; os.environ["TRANSFORMERS_OFFLINE"] = "1"; os.environ["HF_HUB_DISABLE_TELEMETRY"] = "1"

    t0 = time.perf_counter(); phases = {}
    os.makedirs(os.path.dirname(os.path.abspath(args.out)) or ".", exist_ok=True)
    out_json = args.out + ".json"; inputs_dir = os.path.splitext(args.out)[0] + "_inputs"
    rec = {"route": "R1-EI", "runner_version": "1", "mode": args.mode, "args": vars(args), "prompt": args.prompt, "started_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
           "host": {"platform": platform.platform(), "python": sys.version.split()[0]}, "pins": {"easy_insert_commit": MANIFEST["easy_insert"]["commit"], "lora_revision": MANIFEST["lora"]["revision"], "base_revision": MANIFEST["base_model"]["revision"]}}
    for k in ("a", "b", "insert_mask", "ref_mask"):
        p = getattr(args, k)
        if not os.path.exists(p):
            print(f"[r1ei] arquivo ausente: {k} = {p}", file=sys.stderr); sys.exit(2)
        rec.setdefault("inputs_sha256", {})[k] = sha256_file(p)

    ok, pins = check_pins(args, args.verify_base_sha); rec["pin_check"] = pins
    utils, utils_src, utils_path = load_utils(args.easy_insert_dir); rec["utils_source"] = {"from": utils_src, "path": utils_path, "sha256": UTILS_SHA}
    A, background, ref, crop_box, src_mask_c, meta = preprocess(utils, args, inputs_dir); rec["preprocess"] = meta
    phases["preprocess_s"] = round(time.perf_counter() - t0, 3)

    if not ok:
        rec["verdict"] = "FAIL:pins_divergentes_ou_arquivos_ausentes"; json.dump(rec, open(out_json, "w", encoding="utf-8"), indent=1, ensure_ascii=False)
        print(json.dumps({k: v for k, v in pins.items()}, indent=1, ensure_ascii=False)[:4000]); print(f"[r1ei] {rec['verdict']} → {out_json}"); sys.exit(3)
    if args.dry_run:
        rec["verdict"] = "DRY_RUN_OK"; rec["phases"] = phases
        rec["plan"] = {"image1": "background com buraco branco (1024²)", "image2": "referência sobre branco (1024²)", "steps": args.steps, "guidance_scale": args.cfg, "transformer_passes": args.steps * (2 if args.cfg > 1 else 1), "mode": args.mode}
        json.dump(rec, open(out_json, "w", encoding="utf-8"), indent=1, ensure_ascii=False); print(f"[r1ei] DRY_RUN_OK → {out_json} (entradas em {inputs_dir})"); return 0

    # ------------------------------------------------------------------ execução real
    import torch
    rec["versions"] = {"torch": torch.__version__, "cuda": torch.version.cuda}
    if not torch.cuda.is_available():
        rec["verdict"] = "FAIL:cuda_indisponivel"; json.dump(rec, open(out_json, "w", encoding="utf-8"), indent=1, ensure_ascii=False); print("[r1ei] CUDA indisponível", file=sys.stderr); sys.exit(4)
    dev = torch.device("cuda"); props = torch.cuda.get_device_properties(0)
    rec["gpu"] = {"name": props.name, "total_mem_mb": round(props.total_memory / 2**20, 1), "capability": f"{props.major}.{props.minor}", "arch_list": torch.cuda.get_arch_list()}
    import diffusers, transformers, peft
    rec["versions"].update({"diffusers": diffusers.__version__, "transformers": transformers.__version__, "peft": peft.__version__})
    from diffusers import Flux2KleinPipeline
    from transformers import AutoTokenizer, Qwen3ForCausalLM
    torch.cuda.reset_peak_memory_stats(); bf16 = torch.bfloat16
    layers = tuple(int(x) for x in args.te_layers.split(","))
    try:
        # 1. text encoder → embeddings → liberar
        t = time.perf_counter()
        tok = AutoTokenizer.from_pretrained(os.path.join(args.model_dir, "tokenizer"))
        try:
            te = Qwen3ForCausalLM.from_pretrained(os.path.join(args.model_dir, "text_encoder"), dtype=bf16)
        except TypeError:
            te = Qwen3ForCausalLM.from_pretrained(os.path.join(args.model_dir, "text_encoder"), torch_dtype=bf16)
        te.to(dev).eval(); phases["load_text_encoder_s"] = round(time.perf_counter() - t, 3)
        t = time.perf_counter()
        with torch.no_grad():
            emb = Flux2KleinPipeline._get_qwen3_prompt_embeds(te, tok, [args.prompt], dtype=bf16, device=dev, max_sequence_length=512, hidden_states_layers=layers).to("cpu")
            neg = Flux2KleinPipeline._get_qwen3_prompt_embeds(te, tok, [""], dtype=bf16, device=dev, max_sequence_length=512, hidden_states_layers=layers).to("cpu")
        phases["encode_prompt_s"] = round(time.perf_counter() - t, 3); rec["prompt_embeds_shape"] = list(emb.shape)
        rec["vram_peak_after_text_encoder_mb"] = round(torch.cuda.max_memory_allocated() / 2**20, 1)
        del te; import gc; gc.collect(); torch.cuda.empty_cache(); torch.cuda.reset_peak_memory_stats()
        # 2. transformer + LoRA + VAE
        t = time.perf_counter()
        pipe = Flux2KleinPipeline.from_pretrained(args.model_dir, text_encoder=None, tokenizer=None, torch_dtype=bf16)
        lora_path = args.lora_file or os.path.join(args.lora_dir, MANIFEST["lora"]["file"])
        pipe.load_lora_weights(os.path.dirname(lora_path), weight_name=os.path.basename(lora_path))
        if args.mode == "fp8":
            pipe.transformer.enable_layerwise_casting(storage_dtype=torch.float8_e4m3fn, compute_dtype=bf16)
        if args.vae_tiling and hasattr(pipe.vae, "enable_tiling"):
            pipe.vae.enable_tiling()
        if args.mode == "offload":
            pipe.enable_sequential_cpu_offload()
        else:
            pipe.to(dev)
        phases["load_transformer_lora_vae_s"] = round(time.perf_counter() - t, 3)
        # 3. denoise → latente
        t = time.perf_counter()
        gen = torch.Generator(device="cuda").manual_seed(args.seed)
        with torch.no_grad():
            latents = pipe(image=[background, ref], prompt_embeds=emb.to(dev, bf16), negative_prompt_embeds=neg.to(dev, bf16), height=args.size, width=args.size,
                           num_inference_steps=args.steps, guidance_scale=args.cfg, generator=gen, output_type="latent").images
        torch.cuda.synchronize(); phases["denoise_s"] = round(time.perf_counter() - t, 3)
        rec["vram_peak_denoise_mb"] = round(torch.cuda.max_memory_allocated() / 2**20, 1); rec["vram_reserved_peak_denoise_mb"] = round(torch.cuda.max_memory_reserved() / 2**20, 1)
        # 4. decode (transformer fora da GPU, salvo flag)
        t = time.perf_counter()
        if args.mode != "offload" and not args.keep_transformer_on_gpu_for_decode:
            pipe.transformer.to("cpu"); torch.cuda.empty_cache()
        with torch.no_grad():
            img = pipe.vae.decode(latents.to(pipe.vae.dtype), return_dict=False)[0]
            image = pipe.image_processor.postprocess(img, output_type="pil")[0]
        torch.cuda.synchronize(); phases["decode_s"] = round(time.perf_counter() - t, 3)
        result = utils.paste_back(image, A, crop_box, src_mask_c, feather=0)
        result.save(args.out); image.save(os.path.join(inputs_dir, "generated_crop_1024.png"))
        phases["total_s"] = round(time.perf_counter() - t0, 3)
        rec.update({"phases": phases, "vram_peak_overall_mb": round(max(rec.get("vram_peak_after_text_encoder_mb", 0), rec.get("vram_peak_denoise_mb", 0)), 1), "output": args.out, "verdict": "ok"})
        json.dump(rec, open(out_json, "w", encoding="utf-8"), indent=1, ensure_ascii=False)
        print(f"[r1ei] ok total={phases['total_s']} s (TE {phases['load_text_encoder_s']}+{phases['encode_prompt_s']}; DiT load {phases['load_transformer_lora_vae_s']}; denoise {phases['denoise_s']}; decode {phases['decode_s']}) VRAM pico {rec['vram_peak_overall_mb']} MB → {args.out}")
        return 0
    except Exception as e:  # OOM e outras falhas ficam registradas no sidecar, com exit 4
        import traceback
        rec.update({"phases": phases, "verdict": f"FAIL:{type(e).__name__}", "error": str(e)[:2000], "traceback": traceback.format_exc()[-4000:],
                    "vram_peak_mb_at_failure": round(torch.cuda.max_memory_allocated() / 2**20, 1) if torch.cuda.is_available() else None})
        json.dump(rec, open(out_json, "w", encoding="utf-8"), indent=1, ensure_ascii=False)
        print(f"[r1ei] {rec['verdict']}: {str(e)[:300]} → {out_json}", file=sys.stderr); return 4


if __name__ == "__main__":
    sys.exit(main())
