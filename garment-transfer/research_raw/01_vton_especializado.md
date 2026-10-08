# Levantamento bruto — VTON / garment transfer especializado com pesos abertos (agente de pesquisa, 2026-10-07)

Nota de acesso: proxy bloqueou arxiv.org, huggingface.co, openreview.net, fashn.ai, alphaxiv e *.github.io; READMEs/LICENSE/issues do github.com foram lidos diretamente. Fatos de arXiv/HF vêm de excertos de busca. Tags: [P] fonte primária · [R] reproduzido · [I] inferido · [U] desconhecido · NÃO VERIFICADO.

Licenças de base verificadas: FLUX.1 [dev] Non-Commercial License v1.1.1 cobre FLUX.1 Fill [dev] e Kontext [dev]; derivados incl. LoRAs herdam a restrição não comercial; saídas podem ser usadas comercialmente (BFL LICENSE-FLUX1-dev) [P]. Qwen-Image / Qwen-Image-Edit: Apache-2.0 [P]. SD1.5/SD2 inpainting: CreativeML OpenRAIL-M (não rechecado). SD3 Medium: Stability Community License, gated [R].

## A. Candidatos Tier-1 (pesos baixáveis, executáveis localmente)

### CatVTON (Zheng-Chong) — ICLR 2025
- arXiv 2407.15886 [P]. Código github.com/Zheng-Chong/CatVTON; pesos HF zhengchong/CatVTON [P/R]. Licença CC BY-NC-SA 4.0 (código, checkpoints, demo) [P]. Última notícia 2025-02-24 → dormente [I].
- Base: SD1.5-inpainting UNet, 899.06M total / 49.57M treináveis; 1024×768; "<8 GB VRAM" bf16 (GPU não especificada) [P]. Concatenação espacial pessoa+roupa; sem texto/ReferenceNet.
- Entradas: pessoa, roupa (flat/in-shop), máscara agnóstica (AutoMasker = SCHP + DensePose) [P]. Referência vestida: não endereçada [P: README silente]. Categorias upper/lower/dresses [P]. Inpainting por máscara: saia longa sobre pernas nuas só se a máscara cobrir as pernas [I].
- Variantes: CatVTON-MaskFree (2024-10-17), CatVTON-FLUX LoRA (37.4M, FLUX.1-Fill-dev, "not a stable version") [P].
- ComfyUI: ComfyUI-CatVTON.zip oficial + workflow; pzc163/Comfyui-CatVTON (Windows; detectron2/DensePose) [P: issue #8]; chflame163/ComfyUI_CatVTON_Wrapper ("≥6 GB VRAM") [P].
- Treino: VITON-HD + DressCode (estúdio, frontal).

### CatV2TON — arXiv 2501.11325 (NÃO VERIFICADO), pesos HF 256/512, CC BY-NC-SA 4.0; DiT de vídeo; ≤512 → interesse transferível; sem ComfyUI; VRAM [U].

### IDM-VTON (yisol) — ECCV 2024
- arXiv 2403.05139 [P]. Pesos HF yisol/IDM-VTON, IDM-VTON-DC [R]. CC BY-NC-SA 4.0 [P]. Dormente [I].
- Base: SDXL-inpainting + GarmentNet + IP-Adapter-plus SDXL [P/I]. 768×1024 [P].
- Entradas: pessoa, roupa, máscara agnóstica, DensePose, parsing (ATR/LIP ONNX), OpenPose, legenda [P]. Referência vestida: não. Categorias: VITON-HD upper; DressCode via DC [P].
- VRAM: mantenedor: ">18 GB VRAM required for single image inference" (issue #43, mai/2024); 4060 8 GB falha até em 360×480 [P]. ComfyUI: TemryL/ComfyUI-IDM-VTON (GPL-3.0; ≥16 GB) [P].

### OOTDiffusion (levihsu) — AAAI 2025
- arXiv 2403.01779; LICENSE CC BY-NC-SA 4.0 [P]. Checkpoints HF levihsu/OOTDiffusion [P/R]. Dormente.
- SD1.5-based "outfitting UNet + fusion"; 768×1024 [I]. Entradas: modelo + roupa; máscara via humanparsing ONNX + OpenPose [P]. Half-body (VITON-HD) e full-body (DressCode) [P]. Vestida: não. "Only tested on Linux" [P]. ComfyUI: AuroBit/ComfyUI-OOTDiffusion [R].

### StableVITON — CVPR 2024: arXiv 2312.01725; CC BY-NC-SA 4.0; Paint-by-Example UNet 13 canais + VAE finetuned; entradas: agnostic, máscara, DensePose, cloth, cloth mask; VITON-HD only; "with/without repainting" (paste-back fora da máscara) [P]. ART-VITON (2025-09) reutiliza checkpoints.

### Leffa (franciszzj, Meta) — CVPR 2025
- arXiv 2412.08486 [P]. Código MIT [P]; pesos HF franciszzj/Leffa. Última notícia 2025-02-26.
- Base (app.py): stable-diffusion-inpainting (SD1.5) para try-on (VITON-HD; DressCode "experimental"), SDXL-inpainting para pose transfer; 768×1024; fp16; 30 passos; ref_acceleration; toggle repaint [P]. "~6 s on A100" [P].
- Entradas: pessoa, roupa; AutoMasker (DensePose R50 + SCHP), parsing ATR/LIP, OpenPose [P]. upper/lower/dresses. Vestida: não. Mecanismo: regularização attention-flow sobre baseline de inpainting [P].
- VRAM: issue #27 "V100 32G OOM" no decode do VAE (sem resposta) [P]. Windows: issue #40 (AutocastCUDA, aberto) [P]. ComfyUI: StartHua/Comfyui_leffa; Bionic-AI-Solutions/ComfyUI-Leffa (~34 GB) [R].

### FitDiT (Tencent) 
- arXiv 2411.10499 [P]. Pesos 2024-12-20 (HF BoyuanJiang/FitDiT) [P/R]. CC BY-NC-SA 4.0; comercial via Tencent Cloud [P]. Última atualização 2025-01-16.
- Base: SD3-Medium DiT (gradio_sd3.py) [P/I]; padrão 1152×1536 [P]. Paper (excerto): ~19.5 GB fp16 @1024×768/25 passos, 4.57 s; "<6 GB com sequential CPU offload" [R]. Issue #23 (fev/2025): 8 GB insuficiente mesmo com aggressive offload — sem resposta [P]. Modos bf16/fp16/--offload/--aggressive_offload [P].
- Entradas: pessoa + roupa; máscara auto (Step 1) com sliders/brush [P]. Categorias upper/lower/dress [I]. Vestida: não.
- Falhas: VTBench: VTON-HandFit reduz erro de consistência de mão 38.7% vs FitDiT (2º) → mãos sob oclusão são fraqueza [R]. CVDD (Complex Virtual Dressing Dataset) 2024-11-25 [P].
- ComfyUI: BoyuanJiang/FitDiT-ComfyUI oficial (with_offload/with_aggressive_offload) [P]. Windows: nada.

### OmniTry (Kunbyte + ZJU) — NeurIPS 2025
- arXiv 2508.13632 [R]. Código Apache-2.0 [P]; pesos HF Kunbyte/OmniTry = LoRA sobre FLUX.1-Fill-dev → FLUX NC no derivado [P+I]. 2025-08-20.
- Mask-free; pessoa + objeto (+ prompt); qualquer wearable; checkpoint clothes [P]. "At least 28 GB VRAM under bf16" [P]; issue #4 discute DFloat11 (~70% menos memória, não verificado) [P]. ComfyUI: pedido na issue #3, nenhum oficial. Vestida: não endereçada.

### FASHN VTON v1.5 (FASHN AI) — jan/2026
- Sem paper ("coming soon") [P]. Código github.com/fashn-AI/fashn-vton-1.5 — Apache-2.0 [P]; pesos HF fashn-ai/fashn-vton-1.5, Apache-2.0 segundo blog 2026-01-27 (card não lido) [R]. ~2026-02-01.
- Arquitetura: difusão diretamente em pixel RGB (sem VAE), maskless; ~972M–1.0B params [R]; saída 576×864 [R]; ~8 GB VRAM, ~5 s em H100 [R]; bf16 Ampere+ [P]. Roda DWPose ONNX + parser humano próprio (licença própria) [P].
- Entradas: pessoa, roupa, categoria (tops/bottoms/one-pieces). "Supports both model photos and flat-lay product shots as garment inputs" → referência vestida suportada [P]. Maskless → pode mudar silhueta/volume [R].
- Limitações (card, excerto): resolução menor que modelos latentes 1K; preservação de forma corporal imperfeita (tripletas sintéticas); traços da roupa original em long→short ou bulky→slim [R]. Treino: 18M pares mascarados + 4M tripletas sintéticas, proprietário [R]. ComfyUI: nenhum. Windows: instruções Unix.

### RefTon / RefVTON (Qihoo 360) — CVPR 2026
- arXiv 2511.00956 [P/R]. Código github.com/360CVGroup/RefTon (licença não declarada) [P]; LoRA HF qihoo360/RefVTON sobre FLUX.1-Kontext-dev → FLUX NC [P]. Inferência 2025-10-11; treino + datasets VRF 2026-03-28 → ativo [P].
- Entradas: roupa (obrigatória) + agnostic (padrão) ou pessoa completa (--use_person) + opcional pessoa de referência vestindo a peça (--use_reference) → suporte explícito pessoa-a-pessoa [P]. 512×384 padrão; 1024×768 com cond_scale 2.0 [P]. VRAM: exemplos 8 GPUs bf16; sem mínimo declarado [P].

### UniFit (zwplus) — AAAI 2026: arXiv 2511.15831; CC BY-NC-SA 4.0 [P]; HF zwpro/UniFit; base FLUX.1-Fill-dev + Qwen2-VL-2B (MGSA) → FLUX NC [P]. 2025-11-20. Seis tarefas: try-on, reconstrução de roupa (try-off), model-free try-on, model-to-model try-on, multi-view (frente/costas), multi-cloth [P]. Entradas: prompt, modelo, roupa(s), DWPose; máscaras não mencionadas [P]. VRAM [U].

### JCo-MVTON (DAMO): arXiv 2508.17614; Apache-2.0 [P]; HF Damo-vision/JCo-MVTON (upper/lower/dress .pt) [P]. MM-DiT sobre FLUX.1-dev → derivado NC [P+I]. Mask-free: pessoa + roupa + texto [P]. Vestida: não endereçada. Resolução/VRAM [U].

### FastFit (LavieAI / Zheng-Chong) — ago/2025: "FastFit Non-Commercial License" [P]. HF zhengchong/FastFit-MR-1024, -SR-1024 [P]. SD1.5-inpainting; multi-referência (tops, bottoms, dresses, shoes, bags) com cache KV; AutoMasker; nó ComfyUI oficial + workflow (2025-08-05) [P]. DressCode-MR gated.

### DeCo-VTON (Levinna) — ECCV 2026: arXiv 2511.18775; código CC BY-NC-SA 4.0, pesos CC BY-NC 4.0 [P]; HF levinna/DeCo-VTON 512×384 e 1024×768 (2025-12-22) [P]. UNet SD1.5-inpainting único, 859.5M [P]. Entradas: pessoa, roupa, máscara agnóstica (DensePose p/ DressCode) [P]. bf16.

### Mobile-VTON (tmllab) — CVPR 2026: arXiv 2603.00947; CC BY-NC-SA 4.0 [P]; HF FlashStight/Mobile-VTON; on-device; VITON-HD + DressCode [P/I].

### OrthoTryOn (NJU-PCALab) — ECCV 2026: arXiv 2606.27880; Apache-2.0 [P]; LoRA HF Jerome-Young/OrthoTryOn sobre LongCat-Image-Edit (Meituan; licença base NÃO VERIFICADA) [P]. VTON + VTOFF + pose transfer com subespaços ortogonais [P]. Entradas: pessoa, roupa, referência sem roupa, esqueleto MMPose, instrução; máscara agnóstica opcional [P]. Treino VITON-HD (+DeepFashion).

### Try-off
- TryOffDiff (BMVC 2025; arXiv 2411.18350; MGT 2504.13078): github.com/rizavelioglu/tryoffdiff — SSPL [P]; HF rizavelioglu/tryoffdiff; SD1.4 + SigLIP; upper/lower/dress (MGT) [P]. Ativo até 2026-06. MGT motiva try-off → try-on para P2P [R].
- TryOffAnyone (2412.08573): sem licença; HF ixarchakos/tryOffAnyone; só upper [P].
- TEMU-VTOFF (ICLR 2026; 2505.21062): CC BY-NC 4.0 [P]; SD3-Medium dual-DiT; HF davidelobba/TEMU-VTOFF; entradas pessoa + categoria + legenda Qwen2.5-VL + bbox; upper/lower/full [P].
- cat-tryoff-flux (xiaozaa, 2024-12-06): FLUX.1-Fill full fine-tune; 40 GB+ VRAM [P].
- Voost (NXN Labs; 2508.04825): CC BY-NC-SA 4.0 [P]; DiT único try-on/try-off; sem pesos baixáveis (só Space) [P/R].
- Lista awesome-virtual-try-off (2026, maioria sem código): AlignVTOFF, BridgeDiff, Dress-ED, OmniDiT, Dual-UNet VTOFF, MMTryOff, RAGDiffusion++ [P].

### Adaptadores FLUX/Qwen de terceiros
- catvton-flux (nftblackmagic): código MIT; pesos NC; full fine-tune + LoRA; usuário fornece pessoa, máscara, roupa; "40 GB+ VRAM"; VITON-HD; ComfyUI lujiazho/ComfyUI-CatvtonFluxWrapper (fp8 Fill) [P].
- LoRAs FLUX.1 Kontext dev (NC): nomadoor/crossimage-tryon-fluxkontext (53 pares, "research only"); ovi054/virtual-tryon-kontext-lora (2025-10-06); will-gao/Flux-Kontext-TryOn (nunchaku) [R]. Qualidade anedótica, instável.
- Qwen-Image-Edit (Apache-2.0, 20B MMDiT): Edit-2509 multi-imagem (2025-09-22), Edit-2511 (2025-12-23) [P]. LoRAs comunitárias: FoxBaze/Try_On_Qwen_Edit_Lora_Alpha; Civitai "Clothes Try On – Qwen Edit" (set/2025; autor: fraco em padrões complexos, sapatos/chapéus); RunningHubAI/rh-qwen-image-edit-2511-lora; prithivMLmods/QIE-2511-Extract-Outfit (≈try-off) [R]. Só posts de criadores; sem benchmark. Única rota comercialmente permissiva além de FASHN 1.5 [I].

## B. Não executáveis localmente ou sem pesos (2026-10-07)
| Modelo | Status |
|---|---|
| BooW-VTON (2408.06047, MIT) | "coming soon"; sem pesos [P] |
| Any2AnyTryon (ICCV 2025) | LoRA FLUX.1-dev HF loooooong/Any2anyTryon; mask-free por tags; LAION-Garment; licença não declarada; try-off/model-gen TODO; FLUX NC [P] |
| OmniVTON / ++ | Training-free em SD2/SD1.5-inp (++ FLUX Fill), CC BY-NC 4.0; pré-processamento pesado (agnostic, TAPPS, OpenPose 25 kpts, DensePose UV, clip-interrogator, pseudo-pessoa via IMAGDressing); multi-humano [P]. Vestida: "extract garment with a segmentation model" [P→I] |
| MV-VTON (AAAI 2025) | pesos Baidu/GDrive; Paint-by-Example; frente+costas + cloth pré-warpado; CC BY-NC-SA [P] |
| IMAGDressing-v1 | Apache código, pesos NC; roupa→nova pessoa; try-on "experimental" [P] |
| DreamFit (ByteDance) | Apache-2.0; SD1.5 & FLUX.1-dev; gera pessoas; try-on precisa "keep image" não open-source [P] |
| VTON-HandFit (CVPR 2025) | CC BY-NC-SA; HaMeR + ViTPose + DensePose; melhor em mãos (VTBench) [P/R] |
| PromptDresser (ICCV 2025) | CC BY-NC-SA; SDXL-inp; GPT-4o prompts → máscara prompt-aware (tuck/fit) [P] |
| ITA-MDT (CVPR 2025) | CC BY-NC-SA; masked DiT; DINOv2; HF jiwoohong93/ita-mdt_weights [P] |
| SPM-Diff (ICLR 2025, HiDream) | licença não declarada; cloth warpado + pontos semânticos; HF HiDream-ai/SPM-Diff [P] |
| FitVTON (2606.12012) | FLUX Kontext dual LoRA, mask-free, controle de tamanho (16 protótipos corporais); HF ZenoNing/FitVTON [P] |
| PG-VTON (CVPR 2026) | training-free FLUX.1-Fill-dev; MIT; máscara pessoa + máscara roupa [P] |
| Layering VTON (ECCV 2026, 2607.22924) | swap/add + DWPose, 512×896; pesos não encontrados [P] |
| Oxygen-TryOn (JD, 2607.21694, jul/2026) | Apache-2.0 código; mask-free, multi-ref, JoyAI-Image-Edit (Qwen3-VL-8B + Wan2.1 VAE + MMDiT); aceita referências vestidas (M2M); pesos não liberados [P] |
| Tstars-Tryon 1.0 (Alibaba, 2604.19748, abr/2026) | Taobao; até 6 refs, 8 categorias, poses extremas; não open-source; só o bench [R] |
| DiT-VTON, ITVTON, FashionComposer | sem código/pesos [R] |
| MFP-VTON (2502.01626), CORAL (2602.17636) | código NÃO VERIFICADO |
| Kolors Virtual Try-On, OutfitAnyone | demos; sem pesos [P/R] |
| Vídeo: MagicTryOn (Wan2.1-14B), ViViD, 3DV-TON | ideias transferíveis: guia 3D/UV, cache de tokens de roupa [R] |

## C. Surveys e benchmarks 2025–2026
- OpenVTON-Bench (2601.22725): ~100K, ~1.5K res; admite "complex multi-layer occlusions or acrobatic poses still under-represented" [R].
- VTBench (2505.19571): textura, tamanho, fundo, mãos; VTON-HandFit melhor em mãos, FitDiT 2º [R].
- VTONQA (2601.02945): 8,132 saídas, 11 modelos, 24,396 MOS; sem rótulos de pose [R]. VTEdit-Bench (2603.11734). FIT (2604.08526): 1.13M tripletas com medidas. Garments2Look (CVPR 2026). Tstars-VTON Bench. OmniTry-Bench. CVDD.
- StreetTryOn (WACV'25): DeepFashion2-derivado; tarefas Shop2Model, Model2Model, Street2Street, Shop2Street, Model2Street; NC [P]. Único benchmark com protocolos P2P explícitos.
- Nenhum benchmark estratifica por dificuldade de pose (sentado/deitado/pernas cruzadas/foreshortening) — DESCONHECIDO para todos os modelos.

## D. Pessoa-a-pessoa — quem suporta e como
1. Direto, com pesos: FASHN VTON 1.5 [P]; RefTon (--use_reference) [P]; UniFit (model-to-model) [P]. Direto mas fechado: Oxygen-TryOn, Tstars-Tryon, MFP-VTON/CORAL.
2. Try-off → try-on: TryOffDiff/MGT, TEMU-VTOFF, cat-tryoff-flux → catvton-flux, OrthoTryOn, Any2AnyTryon (pendente), Voost (sem pesos), Qwen QIE-2511-Extract-Outfit. CORAL (excerto): máscaras de roupa de referências vestidas falham com cabelo/fundo; recortar saia esconde comprimento da bainha [R].
3. Training-free por segmentação: OmniVTON(++) [P→I]. Qwen-Image-Edit-2511 multi-imagem funciona anedoticamente [R].
Dependência de pose referência↔alvo: nenhuma fonte primária quantifica → DESCONHECIDO.

## E. Preservação pixel-exata de regiões não-roupa
- Nenhum modelo alega pixel-exato. Inpainters por máscara podem ser exatos fora da máscara por composição (Leffa repaint, StableVITON repainting) [P]; sem isso, round-trip do VAE altera todos os pixels [I]. Dentro da máscara, mãos/braços/pele são regenerados → artefatos de mãos [R].
- Maskless/pixel-space (FASHN 1.5, OmniTry, JCo-MVTON, Any2AnyTryon, UniFit, RefTon full-person) regeneram o quadro inteiro; FASHN nota drift de forma corporal e traços da roupa antiga [R]. Trade-off: máscara justa preserva corpo mas bloqueia mudança de silhueta (saia longa sobre pernas nuas exige mascarar pernas) [I].
- Adicionar roupa onde havia pele/fundo: só maskless ou inpainters com máscara ampliada; Layering-VTON "add" sem pesos [P].

## F. Shortlist prática (síntese do agente, [I])
- Comercialmente seguro: FASHN VTON 1.5 (Apache-2.0, ~8 GB, maskless, referências vestidas, 576×864) e Qwen-Image-Edit-2511 (+LoRAs).
- Melhor qualidade, só NC: FitDiT (SD3, 1152×1536, offload <6 GB alegado), Leffa (MIT código; SD1.5-inp; 768×1024), CatVTON (<8 GB, ComfyUI oficial).
- P2P pesquisa: RefTon (FLUX Kontext), UniFit (FLUX Fill), TryOffDiff/TEMU-VTOFF + inpainter.
- Observar: pesos Oxygen-TryOn, Voost, MFP-VTON/CORAL, OpenVTON-Bench.

## Fontes (2026-10-07)
GitHub (lidos): Zheng-Chong/CatVTON (+issues/8) · Zheng-Chong/CatV2TON · Zheng-Chong/Awesome-Try-On-Models · Zheng-Chong/FastFit · yisol/IDM-VTON (+issues/43) · levihsu/OOTDiffusion (+LICENSE) · rlawjdghek/StableVITON · rlawjdghek/PromptDresser · franciszzj/Leffa (+app.py, issues 1/27/40) · BoyuanJiang/FitDiT (+issues/23) · BoyuanJiang/FitDiT-ComfyUI · little-misfit/BooW-VTON · logn-2024/Any2anyTryon · Jerome-Young/OmniVTON · Jerome-Young/OmniVTON-PlusPlus · hywang2002/MV-VTON · muzishen/IMAGDressing · bytedance/DreamFit · VTON-HandFit/VTON-HandFit · rizavelioglu/tryoffdiff · rizavelioglu/awesome-virtual-try-off · ixarchakos/try-off-anyone · nxnai/Voost · Kunbyte-AI/OmniTry · nftblackmagic/catvton-flux · lujiazho/ComfyUI-CatvtonFluxWrapper · chflame163/ComfyUI_CatVTON_Wrapper · TemryL/ComfyUI-IDM-VTON · fashn-AI/fashn-vton-1.5 (+issues) · 360CVGroup/RefTon · damo-cv/JCo-MVTON · Levinna/DeCo-VTON · OxygenVision/Oxygen-TryOn · NJU-PCALab/OrthoTryOn · tmllab/2026_CVPR_Mobile-VTON · ChuenFung/Layering-Virtual-Try-On · PKU-ICST-MIPL/PG-VTON_CVPR2026 · HumanAIGC/OutfitAnyone · Kwai-Kolors/Kolors · tryonlabs/opentryon · black-forest-labs/flux/blob/main/model_licenses/LICENSE-FLUX1-dev · QwenLM/Qwen-Image · qkrwnstj306/ART-VITON · HiDream-ai/SPM-Diff · ZenoNing/FitVTON · jiwoohong93/ita-mdt_code · davidelobba/TEMU-VTOFF · zwplus/UniFit · cuiaiyu/street-tryon-benchmark · github.com/topics/virtual-try-on · github.com/topics/virtual-try-off.
Via excertos (domínios bloqueados): arXiv 2601.22725, 2603.11734, 2601.02945, 2505.19571, 2604.08526, 2603.14153, 2604.19748, 2607.21694, 2502.01626, 2602.17636, 2511.00956, 2508.17614, 2508.04825, 2508.13632, 2510.04797, 2501.16757, 2412.14168, 2411.10499, 2408.06047, 2311.16094, 2311.04811, 2412.14465, 2607.22924, 2504.13078, 2411.18350, 2412.08573 · HF: fashn-ai/fashn-vton-1.5, nomadoor/crossimage-tryon-fluxkontext, ovi054, will-gao/Flux-Kontext-TryOn, FoxBaze/Try_On_Qwen_Edit_Lora_Alpha, prithivMLmods/QIE-2511-Extract-Outfit, RunningHubAI/rh-qwen-image-edit-2511-lora, Qwen/Qwen-Image-Edit-2511, spaces Kwai-Kolors/Kolors-Virtual-Try-On, NXN-Labs/Voost, LuckyLiGY/MagicTryOn · fashn.ai/blog (vton-1-5-open-source-release; comparing-the-top-4) · fashn.ai/research/vton-1-5 · StartHua/Comfyui_leffa · AuroBit/ComfyUI-OOTDiffusion · pzc163/Comfyui-CatVTON · vivocameraresearch/magic-tryon · alibaba-yuanjing-aigclab/ViViD · 2y7c3/3DV-TON · civitai 1940532, 2287824 · discuss.huggingface.co/t/105297 · link.springer.com/article/10.1186/s13640-026-00691-w · pith.science/paper/2607.21694.
