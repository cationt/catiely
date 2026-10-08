# Levantamento bruto — editores gerais de imagem com múltiplas referências, pesos abertos (agente de pesquisa, 2026-10-07)

> Material bruto em inglês. Legenda: P = fonte primária (GitHub/código/issue oficial) · R = reproduzido (snippets de HF cards, blogs, testes de terceiros) · I = inferido · U = desconhecido · NÃO VERIFICADO. Proxy bloqueou huggingface.co, arxiv.org, bfl.ai, blog/docs.comfy.org, qwen.ai. Não checados por orçamento: Hunyuan Image 3.5, UniPic3, LLaDA-Image, LongCat-Image-Edit, GLM-Image, Wan2.7-Image.

## 0. Executive summary (12 GB VRAM / ~16 GB RAM)
1. **No open model does "put garment B on person A" as masked inpainting.** Every open editor is global re-synthesis conditioned on reference latents/VLM tokens; preservation is statistical, not pixel-locked. Only Qwen-Image-2.1 (mask input, P) and FLUX.1 Fill / Qwen Edit-Inpaint pipelines (mask, P) accept an explicit mask; Fill is not multi-reference.
2. **Most realistic at 12 GB:** FLUX.2 [klein] 4B (Apache-2.0, ~8 GB VRAM claim, 4-step; P), FLUX.2 [klein] 9B fp8 (non-commercial; ran on a 4 GB laptop GPU with offload, P), Qwen-Image-2.1 (7B DiT + 8B VL encoder; 12 GB GGUF and 4070 timings reported, R/P; **research-only license**), Qwen-Image-Edit-2511 (20B; Q4 GGUF ~12 GB, but **16 GB system RAM is the bottleneck**, I).
3. **Try-on LoRAs exist for:** FLUX.1 Kontext dev, Qwen-Image-Edit (2509), FLUX.2 klein 9B (fal), Qwen-Image-2.1 (ausboss). None for klein 4B or 2511 specifically.
4. **Best independent comparison:** GEditBench v2 (Mar 2026) ranks FLUX.2 klein 9B top open editor, narrowly ahead of QIE-2511 (R). RISEBench (2026-04-23): appearance-consistency 71.0 (QIE-2511) vs 71.6 (Kontext dev) vs 86.0 (Nano Banana) (P).
5. **Z-Image-Edit unreleased** ("To be released", P). **FLUX 3 Image** (2026-10-01) API-only; open weights "in coming weeks" (R).

## 1. Candidates
### 1.1 FLUX.1 Kontext [dev]
- ~June 2025; 12B rectified-flow transformer, CLIP-L + T5-XXL (NÃO VERIFICADO this session). License "FLUX.1-dev Non-Commercial License" (P). ComfyUI core support (June 2025); node `FluxKontextMultiReferenceLatentMethod` (P). Multi-image: officially single reference; multi-ref by stitching/latent concat (community). Diffusers `FluxKontextInpaintPipeline` supports mask + reference (P). Preservation: global regeneration; RISEBench appearance 71.6, overall 5.8 (P); KRIS-Bench 49.54 (P). Nunchaku INT4/NVFP4 official (P); city96 GGUF (P). Try-on LoRAs (R): Alissonerdx/TryAnything (240 VTON images, upper-body focus); Civitai kontext-tryon7, KontextCouture, Kontext_change_clothes (dresses poor); peternara/kontext-vtoff. UniWorld-FLUX.1-Kontext-Dev (Edit-R1).
### 1.2 FLUX.1 Fill [dev] — in/outpainting; NC; mask-driven; not multi-reference; compositing stage only.
### 1.3 FLUX.2 [dev] — 2025-11-25 (P); 32B; TE Mistral-Small-3.2-24B (P); NC. ComfyUI core v0.3.72 (P). Multi-ref up to 10 (ComfyUI tutorial)/6 (BFL docs) (R, conflict). "H100-equivalent"; 4-bit + remote TE on 4090 (P). **Not viable at 12 GB/16 GB RAM** (I).
### 1.4 FLUX.2 [klein] 4B / 9B / 9B-KV / Base
- **2026-01-15** (P). klein 4B + 4B Base **Apache-2.0**; 9B, 9B-KV, 9B Base **FLUX Non-Commercial** (P, flux2 README). Distilled = 4 steps; Base = 50 (P). "9B KV faster at equal quality for image editing via KV caching" (P). Unified T2I + single/multi-reference editing (P).
- Encoders: Qwen3-4B (klein 4B), Qwen3-8B (klein 9B) — R (ComfyUI issue #12032; v0.26.0 "Allow using Qwen3-VL as flux2 klein text encoder"). VAE: FLUX.2 VAE.
- ComfyUI v0.9.2 (2026-01-15) "Flux2 Klein support"; v0.17.0 (2026-03-13) FluxKVCache node (P). Multi-ref via ReferenceLatent nodes (R). Hosted endpoints 1–4 refs (R). No official try-on example (U).
- Preservation: global regeneration, no mask input. GEditBench v2: klein 9B "open-source champion, narrow lead over QIE-2511" (R); Qwen-Image-Flash paper Elo: klein 9B 1088, 4B 1054, QIE-2511 1042, Nano Banana Pro 1218 (R).
- Memory: README "Klein 4B fits in ~8GB VRAM (RTX 3090/4070 and up)" (P); HF card ~13 GB (R, conflict). 9B distilled ~2 s on RTX 5090 / 19.6 GB; base ~35 s / 21.7 GB (R); official 9B fp8 repo says "~29GB… RTX 4090 and above" (R, conflicts). GGUF: unsloth 4B/9B/base-9B, QuantStack 9B-KV (R). **Nunchaku: not official** — PR #926 open since 2026-03-31 (P).
- Low-VRAM (P): ComfyUI issue #12920 (2026-03-13): RTX 3050 Laptop 4 GB / 15.7 GB RAM, ComfyUI 0.17.0 — klein 9B fp8 edit "works well", 9B-KV OOMs at step 0. Discussion #12699: 4070 user 21–22 s → 16–18 s for klein9b-fp8 after DynamicVRAM.
- Speed (P): vLLM-Omni PR #1866: 2×4090 TP2 + CPU offload, 3 refs: 81.1 s/img (9B) → 49.2 s/img (9B-KV), n=1.
- Try-on LoRAs (R): `fal/flux-klein-9b-virtual-tryon-lora` — 3 refs person/top/bottom, trigger "TRYON …", 28 steps, guidance 2.5, ComfyUI file; `fal/virtual-tryoff-lora` (klein base 9B, Apache-2.0, 300 pairs). Nothing klein-4B-specific.
### 1.5 Qwen-Image-Edit 2508 → 2509 → 2511
- Dates (P): Edit 2025-08-18; 2509 2025-09-22; Layered 2025-12-19; 2511 2025-12-23. "20B MMDiT" (P); TE Qwen2.5-VL (7B NÃO VERIFICADO). Apache-2.0 (P). 2511 bf16 57.7 GB (R).
- Multi-image: 2509+ via `QwenImageEditPlusPipeline` (P); VLM tokens + reference latents. ComfyUI `TextEncodeQwenImageEditPlus` 3 image sockets (P); encodes VL at ~384² area and VAE at ~1024² area (R).
- 2511 claims: "mitigate image drift, improved character consistency, integrated LoRA capabilities, stronger geometric reasoning".
- ComfyUI core: v0.3.60 (2025-09-23) qwen edit plus; v0.5.0 (2025-12-17) 2511 reference method; v0.6.0 Layered (P).
- Preservation/drift: global regeneration. Issue QwenLM/Qwen-Image #243 (2025-12-30): square outputs "lose the subject's likeness significantly", 832×1216 "almost perfect zero-shift"; no reply. lilting.ch: ~8 px shift/edit with default encode node (forced 1 MP resize) → ~1 px with native-size ReferenceLatent (R). RISEBench appearance 71.0 (2511) vs 66.4 (2509); overall 19.4 vs 9.2. SGLang: "consistency is improved rather than guaranteed" (R). Mask: `QwenImageEditInpaintPipeline` (P, original Edit); community mask nodes.
- Benchmarks (P, FireRed self-reported): QIE-2511 ImgEdit_O 4.51, GEdit_O 7.877 EN. KRIS-Bench 2509: 56.15 (P).
- Memory: Lightning 4-step LoRA + fused fp8 (2025-12-22, P). GGUF unsloth (Q8_0 ≈20.3 GB, Q5_0 ≈13.4 GB, Q4_0 ≈11.9 GB per third parties). **Nunchaku official: none for 2511** (only 2509, P); community QuantFunc INT4/FP4 (R). **16 GB RAM:** no direct report; ComfyUI #12541 (5060 Ti 16 GB, 32 GB RAM) RAM to 32 GB and pagefile thrash with Qwen edit + 4 refs (P). Expect paging at 16 GB with fp8 (~20 GB) + 8B encoder (I).
- Speed: RTX 3090, original Edit, 8-step LoRA: 36 s (R).
- Try-on LoRAs: Garments2Look-LoRA (ArtmeScienceLab, CVPR 2026; two adapters inpainting & editing on **2509**, rank 32, 20K samples; dataset+code Apache-2.0, "adapter license not yet specified"; P). kingroka "Clothes Try On – Qwen Edit" (2509; weak on complex patterns; hair may transfer; R). For 2511: RunningHubAI clothing-style-transfer LoRA; prithivMLmods QIE-2511-Extract-Outfit (try-off) (R).
### 1.6 Qwen-Image-2.0 (2026-02-10) — API-only. Not eligible.
### 1.7 Qwen-Image-2.1 (2026-09-20)
- (P, GitHub README) 7B single-stream DiT (32 layers), Qwen3-VL 8B encoder (text + condition images), 64-channel RGBA VAE (16× compression), flow matching, block-causal attention + prefix KV cache. Up to **10 reference images**; native 2K; local edits "specified by circles, painted annotations, or separate masks"; aims to preserve identity.
- **License: "Qwen RESEARCH LICENSE AGREEMENT" — "FOR NON-COMMERCIAL PURPOSES ONLY… research or evaluation"** (P, LICENSE).
- ComfyUI core v0.37.0 (2026-09-21) support; v0.38.0 tiny VAE (P). Comfy-Org bf16 + INT8-ConvRot; TE bf16 17.5 GB vs DiT 14.2 GB (R).
- Memory/speed: Unsloth "runs locally on 12GB VRAM with GGUFs", FP8 on 6 GB via offload (R). RTX 4070 12 GB (kuraneko1, P): ~17 GB official quantized weights, 1024² ~10 s, 2048² ~90 s, edit ~16–20 s at 12 steps. RTX 4060 Ti 16 GB: edit ~60 s, VRAM 13–15 GB (R).
- Preservation: lilting.ch: output resolution arg cut drift to ~0.1 px (R). No independent identity study (U).
- Try-on LoRA (R): `ausboss/Qwen-Image-2.1-Outfit-Swap-Consistency-LoRA` (self-reported face-pixel change 14.1 % → 1.7 %, drift 3.6 px → 0.1 px; qwen-research-license). 2511 LoRAs incompatible.
### 1.8 Qwen-Image-Layered — RGBA decomposition; Apache-2.0; not an editor for try-on; ~10 min/1024² on 4070 (P).
### 1.9 OmniGen2 (2025-06-16) — Apache-2.0; Qwen2.5-VL decoupled; ~17 GB native, model-CPU-offload ≈ −50 %, sequential <3 GB (P); in-context multi-image; "in-context generation sometimes produces objects that differ from the original" (P). ComfyUI official 2025-07-01. No 2026 updates.
### 1.10 BAGEL (2025-05-20) — 7B active / 14B MoT, Apache-2.0; NF4 for 12–32 GB (P). GEdit O 6.52; RISEBench 5.8 (15.8 CoT), appearance 58.7 (P). Multi-image not documented (U).
### 1.11 Step1X-Edit v1.2 (2025-11-26) — Apache-2.0; FP8+offload **18 GB**, 35–51 s H800 (P). Single-image only. RISEBench appearance 41.5.
### 1.12 HiDream-E1.1 — 17B sparse DiT + Llama-3.1-8B, MIT (P); no VRAM stated; no multi-image; RISEBench appearance 12.6.
### 1.13 Lumina-DiMOO — A800 38.9 GB (P). ### 1.14 Emu3.5 — minutes/image; ≥2 GPUs (P). ### 1.15 HunyuanImage 3.0 — 80B MoE; ≥8×80 GB; license excludes EU/UK/KR. Not feasible.
### 1.16 Z-Image — 6B S3-DiT Apache-2.0; Turbo 2025-11-26; **Z-Image-Edit and Omni-Base "To be released"** (P, 2026-10-07).
### 1.17 FireRed-Image-Edit 1.0/1.1 (2026-02-14 / 03-03) — Apache-2.0; 1–3 inputs natively; "Agent" uses Gemini API (external); 30 GB VRAM (P); ~20.4B DiT + 8.3B TE (R) → Qwen-Image-derived (I); GGUF Q4 would behave like QIE-2511 (I).
### 1.18 Others — Wan2.7-Image NV; Kandinsky 5.0 Image Lite (6B) no multi-image; Ovis-U1 single-image; UniWorld-V2 (RL fine-tunes of QIE-2509 / Kontext).
### 1.19 Proprietary (not eligible; public facts, R) — Nano Banana 2 = Gemini 3.1 Flash Image (2026-02-26; 14 refs); Nano Banana 2.1 (2026-10-06); GPT-Image-1.5 (2025-12-16), gpt-image-2 (2026-04-21), GPT-Image-2.5 (2026-09-08); Seedream 4.5 (≤14 refs), 5.0 Pro (2026-07-08); FLUX 3 Image (2026-10-01; API; ≤10 refs; bounding-box layout; "multi-turn edits without changing any other pixel"; open weights promised).

## 2. ComfyUI core low-VRAM/RAM features 2026 (P)
| Feature | What it does | Source / date |
|---|---|---|
| Adaptive model loading (comfy-aimdo) | ModelPatcher negotiates load level per inference; "No need to load models fully to RAM"; weights read from disk don't consume process RAM; avoids Windows shared-memory spill; opt-in `--fast dynamic_vram` at first; GGUF unsupported at merge. Flux2+LoRA 39.6→34.8 s (5090). | PR #11845 merged 2026-02-01 (v0.12.0) |
| DynamicVRAM default | custom PyTorch allocator reserving virtual address space, faulting tensors on demand; cached weights "never end up in your page file"; higher VRAM use expected; disabled with torch.compile, weight hooks, `--disable-smart-memory`; WSL disabled then re-enabled (v0.33.1); TE kept on GPU (v0.37.0). Recommends PyTorch 2.10 cu130. | v0.16.0 (2026-03-05); Discussion #12699 |
| RAM pressure strategies | aimdo 0.2.11 "Improved RAM Pressure release strategies – Windows speedups"; `--lowvram` no-op under dynamic vram. | v0.18.0 (2026-03-21), v0.19.0 |
| `--cache-ram` | retention priority active intermediates > current model > other models > old; default mode; active 10 % RAM (min 2 GB, max 10 GB). | PR #13603 (2026-04-28, v0.21.0); v0.23.0 |
| Threaded disk loader | multi-threaded load; offload to disk. | v0.23.0 (2026-06-01) |
| `--vram-headroom` / dynamic `--reserve-vram` | keep N GB free counting other apps. | v0.25.0 (2026-06-16) |
| `--async-offload` | default on Nvidia since v0.3.76 (2025-12-02). | releases |
| Pinned memory | default on Nvidia (v0.3.69); `--disable-pinned-memory` suggested for low-RAM boxes. | releases; PR #11845 comments |
| Block swap | no core flag; only wrapper nodes. | — |
Known reports (P): #12541 (5060 Ti 16 GB / 32 GB RAM: RAM to 32 GB, pagefile thrash); Desktop #1741 (3060 12 GB, 0.24.1: all models unloaded after every run, 155 s/prompt); #12699 comments: 5090/4090 user 2→4.4 s and disabled it; 4070 user faster. Implication for 16 GB RAM: adaptive loading avoids staging full safetensors in RAM — main reason a 20 GB fp8 file can load at all on a 16 GB box; Windows commit charge still governs (R/I).

## 3. Published comparisons
- **GEditBench v2** (arXiv 2603.28547, Mar 2026; 16 editors; GPT-4o + "PVC-Judge"): FLUX.2 klein 9B top open model, narrow lead over QIE-2511; Nano Banana Pro leads overall (R).
- **RISEBench** (2026-04-23, P) appearance / overall: Nano Banana 86.0/33.9; GPT-Image-1 80.2/30.0; BAGEL-CoT 75.6/15.8; Kontext dev 71.6/5.8; **QIE-2511 71.0/19.4**; Seedream-4.0 67.4/12.2; QIE-2509 66.4/9.2; BAGEL 58.7/5.8; Step1X-Edit 41.5/1.9. FLUX.2 not listed.
- **KRIS-Bench** (P): Step1X v1.2 60.93 > QIE-2509 56.15 > Kontext dev 49.54.
- **GEdit/ImgEdit** (P, FireRed self-reported): FireRed-1.1 7.943/4.56 vs QIE-2511 7.877/4.51.
- **Try-on specific:** Garments2Look (CVPR 2026, P): "current methods [incl. general-purpose editors] struggle with complete outfits and layering". MIEScore (2608.02059) NV. Also unread: MPIE-Bench, CPI-Bench, Edit-Compass.
- **Community:** lilting.ch pixel-shift tests (QIE-2511 ~8 px → ~1 px; Qwen-2.1 ~0.1 px); portrait-editing paper (2602.16149): FLUX.2-dev and Qwen-Edit shift toward stereotyped gender presentation.

## 4. Not checked
Hunyuan Image 3.5 (partner/API nodes in v0.38.0), UniPic3 (1–6 inputs), LLaDA-Image, LongCat-Image-Edit, GLM-Image, Wan2.7-Image; exact ComfyUI version that made `--cache-ram` default; HF cards for klein/Kontext/Fill.

## Sources
Fetched: github.com/black-forest-labs/flux2 (+model_cards/FLUX.2-dev.md) · black-forest-labs/flux · QwenLM/Qwen-Image (+README raw, issues 241/243) · QwenLM/Qwen-Image-2.1 (+LICENSE) · Tongyi-MAI/Z-Image (+issues/169) · Tencent-Hunyuan/HunyuanImage-3.0 (+LICENSE) · FireRedTeam/FireRed-Image-Edit · stepfun-ai/Step1X-Edit · VectorSpaceLab/OmniGen2 · ByteDance-Seed/Bagel · HiDream-ai/HiDream-E1, HiDream-I1 · Alpha-VLLM/Lumina-DiMOO · baaivision/Emu3.5 · PKU-YuanGroup/UniWorld-V2, ImgEdit · PhoenixZ810/RISEBench · mercurystraw/Kris_Bench · ZhangqiJiang07/GEditBench_v2 · ArtmeScienceLab/Garments2Look · nunchaku-ai/nunchaku (+pull/926), ComfyUI-nunchaku (+issues/731) · city96/ComfyUI-GGUF (+tools/convert.py) · ModelTC/Qwen-Image-Lightning · modelscope/DiffSynth-Studio · Comfy-Org/ComfyUI releases (pages 1–8; v0.21.0, v0.22.0, v0.23.0), cli_args.py, discussions/12699, pull/11845, pull/13603, issues 11476/12032/12541/12920 · Comfy-Org/desktop/issues/1741 · vllm-project/vllm-omni/pull/1866 · DavidJBarnes/wanly-console/issues/574 · deepbeepmeep/Wan2GP/issues/2408 · ltdrdata/ComfyUI-Impact-Pack/issues/1208 · Acly/krita-ai-diffusion/discussions/2275, 2081 · kuraneko1/qwen21-fast-comfyui · diffusers docs flux.md, flux2.md, qwenimage.md.
Snippet-only: HF black-forest-labs/FLUX.2-klein-4B, -9B, -9b-fp8, -9b-kv; Qwen/Qwen-Image-Edit-2511, Qwen-Image-2.1; fal/flux-klein-9b-virtual-tryon-lora, fal/virtual-tryoff-lora; ausboss/Qwen-Image-2.1-Outfit-Swap-Consistency-LoRA; ArtmeScienceLab/Garments2Look-LoRA; Alissonerdx/TryAnything; QuantFunc/Nunchaku-Qwen-Image-EDIT-2511; unsloth/*-GGUF; civitai 1940532, 2111450, 1794060, 1941506; arXiv 2603.28547, 2608.02059, 2602.13344, 2510.16888; bfl.ai blog/docs; blog.comfy.org (dynamic-vram, flux2-klein, qwen-image-edit-2511, qwen-image-21); docs.comfy.org; qwen.ai blog; lilting.ch; nextdiffusion.ai; kombitz.com; unsloth.ai docs; techcrunch (Nano Banana 2); the-decoder (Nano Banana 2.1; FLUX 3); openrouter (flux-3-image); replicate (seedream-5-pro); community.openai.com; SGLang docs; venturebeat; marktechpost; cellcog.ai; diffusiondoodles; willitrunai; localaimaster; apatero.
