# Fase 1 — Estado da arte (data de corte: 2026-10-07)

**Método.** Seis levantamentos paralelos (VTON especializado; editores gerais multi-referência; transferência a partir de referência vestida e try-off; percepção/geometria/correspondência/simulação; viabilidade RTX 5070/Windows/ComfyUI; sistemas comerciais, datasets e métricas), com verificação em fontes primárias quando acessíveis. Relatórios brutos com todas as URLs em `research_raw/`. Quatro fatos decisivos para a shortlist foram re-verificados diretamente nos repositórios oficiais (FLUX.2 README, FASHN VTON 1.5 README, Qwen-Image-2.1 LICENSE, RefTon README, ComfyUI `model_management.py`, CatVTON README).

**Limitação de acesso registrada.** O ambiente de pesquisa bloqueou arxiv.org, huggingface.co, openreview.net, bfl.ai, blog/docs.comfy.org, nvidia.com, pytorch.org, learn.microsoft.com e páginas de projeto. Repositórios GitHub (README, LICENSE, código, issues, releases) foram lidos diretamente. Consequência: alegações cuja única fonte seria um model card do HF ou um PDF do arXiv estão marcadas `REPORTADO (excerto)` quando vieram de trechos indexados, e `NÃO VERIFICADO` quando nem isso foi possível. Nenhuma alegação abaixo foi inventada; onde não há fonte, está dito.

**Níveis de evidência.** `P` = fonte primária lida (repo/LICENSE/código/issue oficial) · `P-ex` = texto oficial via excerto · `R` = reproduzido por terceiros (blog, usuário, agregador) · `E` = estimado · `I` = inferência arquitetural · `NV` = não verificado.

---

## 1. Síntese executiva

1. **Nenhum modelo aberto resolve "vestir A com a peça de B" como edição localizada com preservação verificável.** Editores gerais regeneram o quadro inteiro (preservação estatística); VTON especializados por máscara preservam fora da máscara só se houver *paste-back* explícito e regeneram mãos/pele dentro dela; modelos maskless (FASHN 1.5, OmniTry) regeneram tudo e admitem deriva de forma corporal. A preservação C1–C5 exigida pelo contrato **terá de ser imposta por fora** de qualquer gerador (hipótese central da Fase 4).
2. **Referência vestida (caso central) tem suporte explícito em poucos modelos com pesos:** FASHN VTON 1.5 (`P`: "model photos" como entrada; Apache-2.0), RefTon/RefVTON (`P`: `--use_reference` = "target cloth worn by different person"; LoRA sobre FLUX.1 Kontext dev, licença não declarada → herda FLUX NC), UniFit (`P`: tarefa model-to-model; FLUX Fill NC), CatVTON (abstract alega "in-shop or worn"; README silente). A rota dominante na literatura 2025–26 para referência vestida é **canonicalizar primeiro** (try-off → peça plana; ou unwrapping para A-pose) e então aplicar um try-on por máscara; só um trabalho (MGT, arXiv 2504.13078) quantifica o ganho (menos vazamento de tom de pele) e seu backbone downstream não foi verificado.
3. **Não existe benchmark público de poses difíceis** (sentado, deitado, pernas cruzadas, foreshortening, braços sobre a roupa). OpenVTON-Bench (2026) admite sub-representação de "multi-layer occlusions or acrobatic poses"; StreetTryOn é o único com protocolos pessoa-a-pessoa; VTBench tem dimensão de oclusão por mãos. Logo, **o desempenho de todos os modelos em HARD/EXTREME é DESCONHECIDO** e terá de ser medido pelo nosso benchmark.
4. **Hardware:** nenhuma medição publicada de qualquer candidato em 12 GB VRAM + 16 GB RAM. O único dado em 16 GB RAM (RTX 3060 12 GB, FLUX.1-dev fp8, caminho legado) mostra 10–20 min de swapping antes do sampler (`P`, ComfyUI #12334). O ComfyUI 2026 mudou o modelo de memória (DynamicVRAM/comfy-aimdo: mmap sem cópia em RAM; TE na GPU; pinned ≤ 40 % da RAM no Windows), o que torna estimativas pré-2026 pouco transferíveis. **Viabilidade = PENDENTE até medir no alvo.**
5. **Licenças separam duas trilhas.** Permissiva (Apache/MIT): FLUX.2 klein 4B (+Base), Qwen-Image-Edit-2509/2511, FASHN VTON 1.5, OmniTry/JCo-MVTON/OrthoTryOn (código; pesos herdam FLUX NC ou LongCat NV), Leffa (código MIT; pesos SD1.5-inpainting OpenRAIL), SAM 2, BiRefNet, DWPose/rtmlib, MoGe, MHR, DINOv2, SigLIP 2, LPIPS, DISTS. Não comercial: tudo derivado de FLUX.1 (Kontext, Fill, RefTon, OmniTry pesos, UniFit), FLUX.2 klein 9B, Qwen-Image-2.1 (Qwen Research License), CatVTON, IDM-VTON, FitDiT, TEMU-VTOFF, OmniVTON, DensePose original, SMPL/SMPL-X e todo HMR que os usa, Sapiens v1, InsightFace (pesos), VITON-HD/DressCode.

---

## 2. VTON especializado (pesos abertos)

| Modelo | Base / params | Res. | Entradas | Categorias | Ref. vestida | Preservação | VRAM | ComfyUI | Licença | Status | Ev. |
|---|---|---|---|---|---|---|---|---|---|---|---|
| **CatVTON** (ICLR'25) | SD1.5-inp, 899M/49.6M treináveis; concat espacial | 1024×768 | pessoa, roupa, máscara agnóstica (SCHP+DensePose) | up/low/dress | abstract alega; README silente | máscara; MaskFree variante | "<8 GB" bf16 | oficial + wrappers | CC BY-NC-SA 4.0 | dormente (2025-02) | P |
| **Leffa** (CVPR'25, Meta) | SD1.5-inp + UNet ref.; attention-flow loss | 768×1024 | pessoa, roupa; AutoMasker | up/low/dress (DC exp.) | não | máscara; toggle `repaint` | não declarada; OOM no VAE em V100 32G (issue) | 2 wrappers | **MIT** (código) | 2025-02 | P |
| **FitDiT** (Tencent) | DiT SD3-M, dual; frequency loss; máscara dilatada-relaxada | 1152×1536 | pessoa, roupa; máscara auto c/ sliders | up/low/dress | não | máscara | ~19.5 GB fp16 @1024×768; "<6 GB" c/ offload sequencial (excerto); 8 GB insuficiente (issue #23) | oficial | CC BY-NC-SA | 2025-01 | P/P-ex |
| **IDM-VTON** (ECCV'24) | SDXL-inp + GarmentNet + IP-Adapter | 768×1024 | pessoa, roupa, agnostic, DensePose, parsing, OpenPose, legenda | up; DC | não | máscara | ">18 GB" (mantenedor) | wrapper ≥16 GB | CC BY-NC-SA | dormente | P |
| **OOTDiffusion** | SD1.5 outfitting UNet | 768×1024 | modelo, roupa; parsing+OpenPose | half/full | não | máscara | NV | wrapper | CC BY-NC-SA | dormente; "Linux only" | P |
| **StableVITON** | Paint-by-Example 13ch | 512/1024 | agnostic, máscara, DensePose, cloth | up | não | máscara; "repainting" | NV | — | CC BY-NC-SA | dormente | P |
| **DeCo-VTON** (ECCV'26) | SD1.5-inp único, 859M | 1024×768 | pessoa, roupa, agnostic | VITON-HD, DC | não | máscara | bf16 | — | CC BY-NC-SA / pesos CC BY-NC | 2025-12 | P |
| **FastFit** | SD1.5-inp; multi-ref c/ cache KV | 1024 | pessoa, várias peças; AutoMasker | tops, bottoms, dresses, shoes, bags | não | máscara | NV | oficial | FastFit NC | 2025-08 | P |
| **FASHN VTON 1.5** (2026-01) | difusão em **pixel**, sem VAE, maskless, ~1B | 576×864 | pessoa, roupa, categoria; DWPose + parser próprio | tops/bottoms/one-pieces | **sim** ("model photos") | regenera tudo; card admite drift de forma corporal e resíduos em long→short | ~8 GB (excerto) | nenhum | **Apache-2.0** (código; pesos NV) | ativo | P/P-ex |
| **OmniTry** (NeurIPS'25) | LoRA sobre FLUX.1-Fill-dev; mask-free | 1024 | pessoa, objeto, prompt | 12 wearables | NV | regenera; blend c/ máscara borrada | "≥28 GB bf16" | pedido | Apache (código) / FLUX NC (pesos) | 2025-08 | P |
| **JCo-MVTON** | MM-DiT sobre FLUX.1-dev; mask-free | NV | pessoa, roupa, texto | up/low/dress | NV | regenera | NV | — | Apache / FLUX NC | 2025-08 | P |
| **RefTon/RefVTON** (CVPR'26) | LoRA FLUX.1-Kontext-dev | 512×384; 1024×768 | roupa + agnostic **ou** pessoa (`--use_person`) + ref. vestida opcional (`--use_reference`) | VITON-HD/DC | **sim (auxiliar)** | regenera | NV (8 GPUs nos exemplos) | — | não declarada → FLUX NC | ativo (2026-03) | P |
| **UniFit** (AAAI'26) | FLUX.1-Fill + Qwen2-VL-2B | NV | prompt, modelo, roupa(s), DWPose | 6 tarefas incl. model-to-model, try-off, multi-view | **sim** | regenera | NV | — | CC BY-NC-SA / FLUX NC | 2025-11 | P |
| **OrthoTryOn** (ECCV'26) | LoRA LongCat-Image-Edit; VTON+VTOFF+pose | NV | pessoa, roupa, ref. sem roupa, esqueleto, instrução | VITON-HD | parcial (VTOFF) | regenera | NV | — | Apache / base NV | 2026 | P |
| **Mobile-VTON** (CVPR'26) | on-device | NV | pessoa, roupa, agnostic, DensePose | VITON-HD, DC | não | máscara | baixo | — | CC BY-NC-SA | 2026 | P |
| Sem pesos ou fechados | BooW-VTON (MIT, sem pesos), Oxygen-TryOn (JD; M2M; pesos pendentes), Tstars-Tryon (Alibaba; fechado), Voost (sem pesos), MFP-VTON/CORAL (NV), Wear-Any-Way, OutfitAnyone, Kolors VTO, FashionComposer, DiT-VTON, ITVTON | | | | | | | | | | P/R |

**Lacunas desta família:** nenhum publica desempenho em pose difícil; todos treinados em VITON-HD/DressCode (estúdio, frontal, fundo neutro) exceto FASHN (dados proprietários) e OmniTry (wild); preservação fora da máscara depende de paste-back; dentro da máscara, mãos e braços são regenerados (VTBench: mãos são a dimensão mais fraca; VTON-HandFit melhor, FitDiT 2.º).

## 3. Editores gerais multi-referência (pesos abertos)

| Modelo | Params / arq. | Multi-ref | Máscara | Preservação (bench) | VRAM / quantizações | ComfyUI | Licença | Ev. |
|---|---|---|---|---|---|---|---|---|
| **FLUX.2 klein 4B / 4B Base** (2026-01-15) | 4B flow DiT; TE Qwen3-4B; VAE FLUX.2; 4 passos (Base 50) | **sim** (README: Multi-ref Editing ✅) | não | sem bench independente; Elo (paper Qwen-Image-Flash, juiz GPT) 1054 vs 9B 1088 vs QIE-2511 1042 | "fits in ~8GB VRAM (RTX 3090/4070 and up)" (P); fp8 oficial; GGUF comunidade; **Nunchaku não oficial** (PR aberto) | core v0.9.2 | **Apache-2.0** | P |
| **FLUX.2 klein 9B / 9B-KV / 9B Base** | 9B; TE Qwen3-8B; KV cache p/ edição | sim | não | GEditBench v2 (03/2026): melhor aberto, à frente de QIE-2511 (R) | 9B fp8 rodou em 3050 4 GB / 15.7 GB RAM com offload (ComfyUI #12920, P); 9B Q8 + TE Q8 OOM em 13 GB RAM (#14433) | core; KV node v0.17.0 | FLUX NC | P/R |
| **Qwen-Image-Edit-2511** (2025-12-23) | 20B MMDiT; TE Qwen2.5-VL-7B | sim (2509+; 3 sockets no node) | pipeline inpaint (Edit original); nodes comunidade | RISEBench appearance 71.0 / overall 19.4; drift ~8 px → ~1 px com ReferenceLatent nativo (R); issue #243: saída quadrada perde semelhança | fp8 ~20 GB; GGUF Q4_0 11.9 / Q4_K_M 13.1 GB; **Nunchaku só 2509**; relato 32 GB RAM saturada c/ 4 refs @2K (#12541) | core v0.5.0 | **Apache-2.0** | P/R |
| **Qwen-Image-2.1** (2026-09-20) | 7B DiT + Qwen3-VL-8B; VAE 64ch; até 10 refs; máscara/anotação local | sim | **sim** | drift ~0.1 px c/ resolução de saída (R); sem estudo de identidade | 4070 12 GB: edit 16–20 s @1024 (R); TE bf16 17.5 GB → fp8/GGUF | core v0.37.0 | **Qwen Research License — não comercial** (P) | P/R |
| **FLUX.1 Kontext dev** | 12B; T5-XXL + CLIP-L | 1 ref oficial; multi por concat | pipeline inpaint (diffusers) | RISEBench appearance 71.6 / overall 5.8 | Nunchaku INT4/NVFP4 ~6.8 GB; fp8 12 GB | core | FLUX NC | P |
| **FLUX.1 Fill dev** | 12B inpaint/outpaint | não | **sim** | — | idem | core | FLUX NC | P |
| OmniGen2 | Qwen2.5-VL + DiT | sim (in-context) | não | "objects that differ from the original" (P) | 17 GB; offload −50 %; sequencial <3 GB | oficial | Apache-2.0 | P |
| BAGEL | 14B MoT | não documentado | não | RISEBench appearance 58.7 | NF4 p/ 12–32 GB | comunidade | Apache-2.0 | P |
| Step1X-Edit v1.2 | MLLM + 12B DiT | não | não | KRIS 60.9 | **fp8+offload 18 GB** | comunidade | Apache-2.0 | P |
| HiDream-E1.1 | 17B + Llama-8B | não | não | RISEBench appearance 12.6 | ≥24 GB (tutorial) | — | MIT | P/R |
| FLUX.2 dev | 32B; TE Mistral-24B | sim | não | — | Q4 ≈ 19 GB + TE 14–18 GB | core | FLUX NC | P/R |
| FireRed-Image-Edit 1.1 | ~20B (derivado Qwen-Image) | 1–3; "Agent" usa Gemini (externo) | não | GEdit 7.94 (auto) | 30 GB | nativo | Apache-2.0 | P |
| Z-Image-Edit | — | — | — | — | **"To be released"** (2026-10-07) | — | — | P |
| Proprietários (não elegíveis) | Nano Banana 2/2.1 (14 refs), GPT-Image-2/2.5, Seedream 5.0, FLUX 3 Image (API; pesos "em breve") | | | RISEBench Nano Banana appearance 86.0 | | | | R |

**LoRAs de try-on sobre editores gerais (todas anedóticas, sem benchmark; `R`):** Kontext (TryAnything, kontext-tryon7, KontextCouture; "dresses poor"); klein 9B (`fal/flux-klein-9b-virtual-tryon-lora`, 3 refs pessoa/top/bottom; `fal/virtual-tryoff-lora` sobre klein Base 9B, Apache); QIE-2509 (Garments2Look-LoRA, CVPR'26, Apache código, adaptador sem licença declarada; kingroka "Clothes Try On": fraco em padrões, cabelo pode vazar); QIE-2511 (só extração/estilo); Qwen-Image-2.1 (ausboss Outfit-Swap; auto-reportado). Nada específico para klein 4B.

## 4. Referência vestida: try-off e pessoa-a-pessoa

| Abordagem | Métodos com pesos | Como evita vazamento de B | Evidência de ganho | Licença | Ev. |
|---|---|---|---|---|---|
| **Try-off → try-on** | TryOffDiff/MGT (SD1.4+SigLIP; up/low/dress; SSPL), TEMU-VTOFF (SD3-M dual DiT; up/low/full; CC BY-NC), TryOffAnyone (up; sem licença), cat-tryoff-flux (40 GB+), QIE-2511-Extract-Outfit (LoRA comunidade) | canonicaliza a peça antes; remove pessoa/fundo | MGT: menos transferência de tom de pele (único quantitativo); backbone downstream NV | SSPL / NC / Apache (Qwen) | P/R |
| **Direto, mask-free** | FASHN 1.5, RefTon (ref auxiliar), UniFit, CatVTON (alegado) | perdas de localização/atenção (MFP-VTON Focus Attention, BooW localization loss — sem pesos) ou recorte por parsing | nenhum head-to-head | Apache / NC | P |
| **Training-free por segmentação** | OmniVTON/++ (SD2/SD1.5/FLUX Fill; parsing + DensePose UV + pseudo-pessoa) | recorta a peça de B por parsing | sem comparação controlada | CC BY-NC | P |
| **Canonicalização geométrica** | ViTon-GUN (A-pose unwrapping), FW-VTON (flatten→warp→integrate), Street TryOn (DensePose warp + correção) | representação canônica da peça | argumentam que warping pose→pose direto falha | código NV / NC | B |

**Modos de falha documentados relevantes ao contrato:** paste-back duro → "abrupt transitions" e shift de cor de baixa frequência pelo round-trip do VAE (ART-VITON; ASUKA); tatuagens/cicatrizes/acessórios perdidos (MuGa-VTON); texto/logos (GarDiff: "fidelity gap", CLIP sem baixo nível); regra de "completude por maioria" em desoclusão (UR-VTON: quando a maior parte do buraco deveria ser pele, ela é restaurada; quando deveria ser tecido, pele falha); máscaras de referências vestidas falham com cabelo/fundo e recortar saia esconde comprimento (CORAL, excerto).

## 5. Correspondência, warping e pose

- **Correspondência semântica 2025–26 (`R`):** SPair-71k PCK@0.1 85.6 (GeoAware-SC) → 88.9 (SemAlign3D); features de DiT superam SD/DINO (DiTF); MARCO (CVPR'26) 10× mais rápido; Jamais Vu: matchers supervisionados colapsam em keypoints não vistos — **roupas não têm keypoints em treino**, logo correspondência A↔B de partes de roupa é terreno de DINOv2/DINOv3 congelado + pós-processamento geométrico, com incerteza alta. RoMa v2 (MIT exceto backbone DINOv3) é o melhor matcher denso off-the-shelf, mas **geométrico**, não semântico.
- **Warping de roupa (`R`):** TPS → appearance flow → GP-VTON (fluxos locais por parte). Nenhum modelo aberto 2025–26 de landmarks de roupa (DeepFashion2 estagnado) — `NV`.
- **UV/DensePose:** Pose with Style (MIT; completa UV com simetria); fraqueza documentada: ignora forma 3D, auto-oclusão deixa buracos. Licença DensePose: repo 2018 e dataset CC BY-NC; **pesos do detectron2 são CC BY-SA 3.0** (`P`) — ponto frequentemente confundido.
- **3D-aware:** 3DV-TON (MIT; código do guia 3D texturizado não liberado), GS-VTON, VTON 360 (multi-view). Nenhum é imagem-única com pesos completos.

## 6. Geometria 3D, priors de vestuário e simulação

Cadeia "reconstruir corpo + roupa → simular → renderizar → refinar": cada estágio existe (SAM 3D Body → MHR Apache-2.0; ChatGarment Apache → GarmentCode MIT → ContourCraft MIT/Warp Apache; refinamento difusivo), **mas**: estimadores de padrão a partir de 1 imagem são treinados em sintéticos frontais (SewFactory) e falham em sentado/deitado; Dress-1-to-3 não recupera painéis ausentes; DressWild (fev/2026) alega pose-agnostic mas código `NV`; ContourCraft só SMPL (não comercial) e SMPL-X em TODO; ChatGarment usa GPT-4o em scripts; SewFormer exige Maya. **Veredito desta fase:** protótipo de pesquisa, não rota de produto; mantido apenas como fonte de *condicionamento geométrico* (malha/normais/profundidade) e não como gerador. Ver `02_familias_arquiteturais.md` §F6.

## 7. Percepção (segmentação, pose, corpo, profundidade) — componentes para contrato e QA

| Função | Opções permissivas | Opções com restrição | Nota | Ev. |
|---|---|---|---|---|
| Segmentação por conceito/exemplar | **SAM 3/3.1** (nativo no ComfyUI core; "SAM License" Meta custom sem cláusula NC — revisão jurídica), SAM 2.1 (Apache) | Grounding DINO 1.5+ (API only) | SAM 3 aceita texto ("dress", "left sleeve") e exemplar (recorte de B) | P |
| Parsing semântico | SegFormer-B2-clothes (MIT, catálogo; card NV), SCHP (MIT; inplace_abn difícil no Windows) | Sapiens v1 (CC BY-NC); Sapiens2 (licença custom) | 18 classes ATR | P/R |
| Bordas/matting | **BiRefNet** (MIT; 17 FPS @1024² fp16 em 4090) | — | nó mantido (ComfyUI-RMBG) | P |
| Pose 2D | **DWPose/rtmlib** (Apache; ONNX; whole-body) | OpenPose (NC CMU) | sem breakdown sentado/deitado publicado | P |
| Corpo 3D | **SAM 3D Body → MHR** (MHR Apache; SAM License), Anny (Apache; estimador NC) | Multi-HMR, SMPLer-X, TokenHMR, NLF pesos, HMR2 (todos exigem SMPL/SMPL-X **não comercial**) | SAM 3D Body nativo no core desde 2026-08-23; ~17 GB fp32 anedótico, repacks bf16/int8 | P/R |
| Profundidade/normais | **MoGe-2/3** (MIT; nativo no core), Depth Anything 3 Small/Base (Apache), StableNormal (Apache) | DA3 Large/Giant (CC BY-NC), DSINE (NC), Depth Pro (Apple custom) | todos **inferem** o oculto | P |
| Correspondência densa | DINOv2 (Apache), RoMa v2 (MIT + DINOv3 custom), EfficientLoFTR (registro) | MASt3R (CC BY-NC-SA), GeoAware-SC/SD-DINO (sem licença) | semântico ≠ geométrico | P |

## 8. Vídeo (ideias transferíveis, não entrada)

MagicTryOn (Wan2.1; CC BY-NC-SA), CatV2TON (CC BY-NC-SA), 3DV-TON (MIT). Transferível: guia 3D texturizado/malha como condicionamento consistente; máscaras suavizadas em 3D em vez de parsing por imagem; treino mask-free com pseudo-dados para poses difíceis; injeção de detalhe por referência. Nenhum exige vídeo na entrada básica.

## 9. Sistemas comerciais (benchmark funcional; nenhuma imagem do usuário será enviada)

| Sistema | PUBLIC FACT | ARCHITECTURAL INFERENCE |
|---|---|---|
| **FASHN.ai v1.6 / Try-On Max** | `garment_photo_type ∈ {auto, flat-lay, model}` ("model" = vestida em pessoa); categorias tops/bottoms/one-pieces; 864×1296 nativo; `PoseError` quando não detecta pose; Try-On Max "preserves identity, pose, styling" | pipeline com DWPose + parser (coerente com o repo 1.5 aberto) |
| **Google Doppl** (encerrado 2026-04-30) | aceitava screenshots de outras pessoas vestindo; excluía lingerie/swim/acessórios; inventava calça/sapatos se só top; terceiros: distorção corporal em selfies de espelho, falhas em poses atípicas | — |
| **Google Shopping Try-On** | peça só do catálogo do lojista; orienta: não sentar/agachar, não roupa larga, não mãos no bolso; ≥1024 px | regenera a região da peça; rosto mantido |
| **Nano Banana Pro / 2 / 2.1** | até 14 referências; sem modo try-on; SynthID; RISEBench appearance 86.0 | regeneração global |
| **Pixelcut** | roupa "standalone or worn by a person" | — |
| Kolors VTO, OutfitAnyone, Seedream, Firefly, Botika, Vmake, Veesual | só demos/API; sem pesos; detalhes em `research_raw/04_comerciais_datasets_metricas.md` | — |

**Alvo funcional derivado:** referência vestida é capacidade documentada (FASHN, Pixelcut, Doppl); **pose difícil não é capacidade comercial resolvida** (Google instrui a não sentar/agachar); ninguém documenta preservação pixel-exata; resolução nativa comercial 864×1296 a 2K.

## 10. Datasets e benchmarks (licenças exatas)

| Dataset/benchmark | Licença | Redistribuição | Uso neste projeto |
|---|---|---|---|
| VITON-HD | CC BY-NC 4.0 (NeStyle) | NC permitido; direitos de foto subjacentes não endereçados | só desenvolvimento local; nunca no `final_test` redistribuível |
| DressCode | YNAP custom: pesquisa; sem empresas privadas; assinatura à mão | **não** | não (acesso restrito) |
| DeepFashion / DF2 / DF-MultiModal | NC; sem redistribuição | **não** | não |
| StreetTryOn (WACV'25) | herda DF2/VITON-HD; NC | **não** | referência de protocolo P2P apenas |
| OpenVTON-Bench (2026) | código MIT; dados CC BY-NC 4.0 | NC | referência de métricas/regiões |
| OmniTry-Bench | código Apache; dados NV (Pexels) | NV | — |
| Garments2Look (CVPR'26) | Apache-2.0 (card, R) | provável | candidato a dev (verificar card) |
| VTON-QBench/IQA | CC BY-NC-SA | NC | calibração de IQA |
| **Benchmark próprio** | Wikimedia Commons CC0/CC BY/CC BY-SA por arquivo (**único redistribuível**; direitos de personalidade à parte); Unsplash/Pexels/Pixabay **só manifesto** (cláusulas anti-compilação/ML); autoproduzido com termo de consentimento | ver `benchmark/coverage_matrix.md` | **principal** |

## 11. Métricas e avaliadores locais

| Grupo | Ferramentas (licença) | Limitação registrada |
|---|---|---|
| Identidade | InsightFace/ArcFace (pesos **NC**), AdaFace (MIT; dados NV), facenet-pytorch (MIT; dados NV) | em VTON por máscara o rosto é copiado → diagnóstico só para regeneração global |
| Pose | DWPose/RTMPose (Apache) | proxy 2D; sem visibilidade confiável em oclusão pesada |
| Estrutura/fundo | LPIPS (BSD-2), DISTS (MIT), SSIM/PSNR | medir fora de C2∪C3 |
| Fidelidade da peça | DINOv2 (Apache), DINOv3 (custom), SigLIP 2 (Apache); M-DINO/M-CLIP-I com máscara e fundo branco (OmniTry); DINOv3 CLS + máscaras erodidas (OpenVTON-Bench) | DINO mais sensível a geometria; não separa deformação necessária de mudança de design |
| VLM juiz local | Qwen3-VL 8B (Apache; Q4 ≈ 6–12 GB), MiniCPM-V (Apache), InternVL3 (pesos NV) | PICABench: VLMs genéricos "lack sensitivity to nuanced physical violations"; EditJudgeBias: trocar a ordem inverte até 60.9 % das decisões pareadas; TryOnReward: VLMs genéricos sem granularidade para try-on; "can rank but cannot score" |
| Humano | protocolos 2025–26: pareado/forçado, 20–100 avaliadores, 50–100 itens; identidade raramente perguntada à parte | nosso protocolo perguntará preservação, fidelidade e realismo **separadamente** |

## 12. Lacunas e itens NÃO VERIFICADOS (a resolver na Fase 3/5)

- Pesos: licença de pesos FASHN 1.5 (card), Any2AnyTryon, TryOffAnyone, RefTon, SegFormer-B2-clothes (card), Molmo2/InternVL3.
- Capacidades: suporte a referência vestida de OmniTry/JCo-MVTON; base e VRAM de Voost; código MFP-VTON/CORAL/FW-VTON/ViTon-GUN/DressWild.
- Hardware: qualquer tempo medido de QIE-2509/2511, klein 4B/9B, OmniGen2, FitDiT, TEMU-VTOFF em **12 GB + 16 GB RAM**; stack torch que o Comfy-Desktop 1.1.6 instala numa 5070; cudaMemcpy H2D em série 50; qualidade Q4_K_M vs Q5/Q6/Q8 nos DiTs de edição; wheels Windows de SageAttention 3/xformers para sm_120.
- Avaliação: confiabilidade de VLMs abertos em atributos de vestuário (nenhum número publicado).
