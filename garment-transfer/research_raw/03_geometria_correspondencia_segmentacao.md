# Levantamento bruto — percepção, geometria, correspondência e simulação (agente de pesquisa, 2026-10-07)

Nota: relatório gerado por agente de pesquisa; fontes consultadas listadas ao final. Vários domínios (HF, arXiv, Meta AI, MPI) estavam bloqueados no egress, logo licenças de model cards do HF vêm de snippets (REPRODUZIDO). Níveis: P = fonte primária, R = reproduzido, I = inferido, U = não verificado.

## Nota transversal Windows (I)
Componentes puramente PyTorch/ONNX (BiRefNet, DWPose/rtmlib, MoGe, Depth Anything, Marigold, StableNormal, Sapiens-lite, SegFormer) rodam nativamente em Windows. O que compila extensões CUDA (GroundingDINO `_C`, pós-processamento do SAM 2, inplace_abn do SCHP, detectron2 para DensePose/SAM 3D Body, tiny-cuda-nn para VTON360) é o ponto de dor usual; o README do SAM 2 recomenda WSL. SMPLer-X foi testado em RTX 3090 + WSL2 (P).

## 1. Parsing humano / segmentação de roupa
| Componente | Repo / pesos | Licença (exata) | Última atividade | E/S | VRAM / velocidade | Windows | Evidência |
|---|---|---|---|---|---|---|---|
| SCHP | GoGoDuck912/Self-Correction-Human-Parsing | MIT | sem data recente; era Python 3.6 | RGB → LIP 20 / ATR 18 / Pascal-Part 7 | ResNet-101, <4 GB (I) | inplace_abn CUDA → difícil | P |
| CIHP-PGN | Engineering-Course/CIHP_PGN | MIT | TF1 legado | RGB → partes CIHP | — | TF1, evitar | P |
| SegFormer-B2-clothes (mattmdjaga) | HF mattmdjaga/segformer_b2_clothes | MIT (catálogo terceiro; card inacessível) | modelo 2023; wrappers ativos | RGB → ATR 18 classes | ~27M params, roda em CPU (I) | transformers puro | R |
| Fashionpedia | fashionpedia.github.io | U (página bloqueada) | 2020 | 27 categorias, 19 partes, 294 atributos; modelo oficial Attribute-Mask R-CNN | — | — | R; nenhum checkpoint Mask2Former-Fashionpedia aberto encontrado |
| Sapiens (v1) | facebookresearch/sapiens; HF facebook/sapiens-* | CC BY-NC 4.0 | superado | RGB → pose / seg partes / depth / normais; 0.3B–2B | Sapiens-lite "4x faster"; VRAM não declarada | lite é PyTorch puro | P |
| Sapiens2 | facebookresearch/sapiens2 | "Sapiens2 License" (Meta, custom): sem cláusula comercial explícita; proíbe deepfakes, vigilância, biometria, militar/ITAR; cláusula de auditoria | 2026-04-24; matting 2026-05-15 | ViTs 1024×768, 0.1B–5B; 308 keypoints, 29 partes, normais, pointmaps, matting | não declarado | Py≥3.12, PyTorch≥2.7 | P |
| SAM 2.1 | facebookresearch/sam2 | Apache 2.0 | 2024-09-30 | pontos/caixas/máscaras → máscaras, tracking | 39.5–91.2 FPS A100 | WSL recomendado | P |
| SAM 3 / 3.1 | facebookresearch/sam3; HF facebook/sam3 | "SAM License" (Meta custom, 2025-11-19): sem cláusula comercial explícita; proíbe militar, nuclear, espionagem, ITAR | SAM 3 nov/2025; SAM 3.1 2026-03-27 | texto (noun phrase) ou exemplar → todas as instâncias (PCS, ~270K conceitos), + pontos/caixas/máscaras, vídeo; 848M params; sem referring expressions | não declarado; checkpoint fp16 ComfyUI 1.75 GB → ~4–8 GB (I) | Py 3.12+, PyTorch 2.7+, CUDA 12.6+ | P |
| Grounding DINO 1.0 | IDEA-Research/GroundingDINO | Apache 2.0 | 2023-07 | texto → caixas | — | precisa CUDA_HOME | P |
| Grounding DINO 1.5/1.6, DINO-X | Grounding-DINO-1.5-API | código Apache 2.0, **modelos só via API** | — | — | nuvem | n/a | P — não local |
| Grounded-SAM-2 | IDEA-Research/Grounded-SAM-2 | Apache 2.0 + componentes | 2025-04-20 | texto → caixas → máscaras | — | Linux/Docker | P |
| BiRefNet | ZhengPeng7/BiRefNet | MIT | 2025-09-23 | RGB → alpha; variantes HR 2048², matting, dynamic | 17 FPS @1024² FP16, 3.45 GB RTX 4090 | PyTorch puro; ONNX | P |

Leitura: para máscaras de peça, a pilha local realista é SAM 3 (texto "dress", "left sleeve", ou exemplar recortado de B) + SegFormer/SCHP para rótulos semânticos + BiRefNet para bordas. Licenças permissivas inequívocas: SAM 2, BiRefNet, SCHP. SAM 3 tem licença custom da Meta sem cláusula "non-commercial", mas exige revisão jurídica.

## 2. Pose / corpo / profundidade / normais
### Pose 2D
- DWPose — IDEA-Research/DWPose, Apache 2.0, ONNX (dw-ll_ucoco_384 + yolox_l), COCO-WholeBody AP 0.665; via rtmlib (Tau-J/rtmlib, Apache 2.0, ONNXRuntime/OpenVINO/TensorRT; também RTMPose, RTMO, RTMW, RTMW3D, ViTPose) — amigável a Windows, sem mmcv. (P)
- RTMPose / RTMO / RTMW — MMPose, Apache 2.0 (R).
- ViTPose / ViTPose++ — Apache 2.0, mmcv 1.3.9 (obsoleto). (P)
- OpenPose — licença CMU: uso não comercial acadêmico apenas; comercial pago. Evitar. (P)
- Robustez em pose difícil: nenhum publica breakdown sentado/deitado; whole-body (DWPose/RTMW, Sapiens2 308 kp) lida melhor com foreshortening que COCO-17 (I).

### Corpo 3D
| Modelo | Licença | Saída | Velocidade / HW | Robustez | Evidência |
|---|---|---|---|---|---|
| SAM 3D Body (facebookresearch/sam-3d-body; HF gated facebook/sam-3d-body-dinov3 / -vith) | SAM License (Meta custom) | parâmetros MHR + malha (corpo, mãos, pés); prompts: bbox, keypoints 2D, máscaras; detector SAM3 opcional, FOV MoGe | não declarado; anedótico ~17 GB em RTX 3090; relatos em 12 GB; checkpoints bf16 + int8 em repack ComfyUI (R) | 3DPW MPJPE 54.8, EMDB 61.7; Meta alega melhor em oclusão/viewpoints difíceis e supera NLF | P (repo), R (VRAM) |
| MHR — Momentum Human Rig (facebookresearch/MHR, pip install mhr) | Apache 2.0 | 45 shape, 204 pose, 72 expressão, 7 LODs, conversão para SMPL | PyTorch diferenciável | — | P |
| Anny (naver/anny) | Apache 2.0; dados MakeHuman CC0; variante topologia "smplx" não comercial | modelo corporal bebê→idoso | v0.6 2026-08-06 | — | P |
| Multi-HMR (naver/multi-hmr) | Non-Commercial License | SMPL-X multi-pessoa em câmera; checkpoint Anny 2026-02-17 | 29–126 ms V100 | venceu Robin Challenge CVPR'24 | P |
| Multi-HMR 2 (arXiv 2606.14841) | código U | — | — | — | R |
| SMPLer-X / SMPLest-X | S-Lab License 1.0 (não comercial) | SMPL-X; 32M–662M | 17–36 FPS V100; testado RTX 3090 + WSL2 | — | P |
| HMR2.0 / 4D-Humans | MIT (código); arquivos SMPL sob registro | SMPL | — | Fit3D 74.5 MPJPE vs NLF 59.8 (R) | P |
| TokenHMR | não comercial (MPI) | SMPL/SMPL-H | PyTorch 2.1 / CUDA 11.8 | 3DPW PVE 84.3 | P |
| CameraHMR | U (sem LICENSE visível) | SMPL + câmera perspectiva completa | CUDA 11.8 | — | P/U |
| NLF (isarandi/nlf) | código MIT; pesos "noncommercial research use" | qualquer ponto de superfície; compatível SMPL/SMPL-X | TF + PyTorch | forte em poses extremas Fit3D (R) | P |
| DensePose | repo Caffe2 original CC BY-NC 4.0; código detectron2 Apache 2.0; model zoo DensePose do detectron2: "CC Attribution-ShareAlike 3.0"; anotações DensePose-COCO CC BY-NC 2.0 (R) | IUV / CSE | — | — | P — a alegação "CC-BY-NC" vale para repo 2018 e dataset, não para pesos do detectron2 |

Licenças SMPL / SMPL-X (P via vchoutas/smplx README; R via páginas de licença): "non-commercial scientific research purposes"; comercial via ps-licensing@tue.mpg.de / Meshcapade. Todo HMR que emite SMPL (HMR2.0, TokenHMR, CameraHMR, Multi-HMR, SMPLer-X, NLF, HOOD/ContourCraft) exige os arquivos MPI → não comercial salvo licença. Alternativas comercialmente limpas: MHR (Apache 2.0, via SAM 3D Body) e Anny (Apache 2.0; mas o estimador Multi-HMR Anny é NC).

### Profundidade
| Modelo | Licença | Notas | Evidência |
|---|---|---|---|
| Depth Anything V2 | Small Apache 2.0; Base/Large/Giant CC BY-NC 4.0 | 24.8M–335M; 518 px | P |
| Depth Anything 3 (ByteDance-Seed) | código Apache 2.0; DA3-SMALL/BASE/METRIC-LARGE/MONO-LARGE Apache 2.0; DA3-LARGE/GIANT/NESTED (-1.1) CC BY-NC 4.0 | 2025-11-14; depth, conf, extrínsecos, intrínsecos; streaming "<12 GB"; precisa xformers | P |
| Depth Pro (apple) | Apple custom (ASCL-like), comercial não endereçado | depth métrico + focal | P |
| MoGe-2 / MoGe-3 (microsoft/MoGe) | MIT | point map métrico, depth, normais, FOV, máscara; 60 ms ViT-L FP16 A100/3090; MoGe-3 2026-08-18 (Triton/FlexGEMM — checar Windows); nós nativos ComfyUI | P |
| Marigold | código Apache 2.0; modelos RAIL++-M | depth/normais/IID v1.1 (2025-05-15); SD2 768² | P |

### Normais
- DSINE — licença Imperial College não comercial. (P)
- StableNormal — Apache 2.0; SD-based; turbo "10× faster"; 2024-10. (P)
- Marigold-Normals (RAIL++-M), MoGe-2 -normal (MIT), Sapiens/Sapiens2 (NC/custom), RoSE (ICLR 2026) — U.

Recupera vs. infere (I): todos os monoculares inferem geometria ocluída a partir de priors; para sentado/deitado/foreshortening, o lado de trás, a ordem de profundidade entre membros e a escala absoluta são alucinados. SAM 3D Body + MoGe FOV é a única combinação corrigível por prompt (keypoints/máscara) e comercialmente mais limpa (MHR).

## 3. Correspondência densa entre duas imagens diferentes
| Método | Licença | O que dá | Custo | Evidência |
|---|---|---|---|---|
| DIFT | MIT | features SD/ADM, matching semântico de pontos; img 768, ensemble 8 → VRAM alta | 1–2 s/par | P |
| SD-DINO (Tale of Two Features) | sem LICENSE | SD + DINOv2 | PyTorch 1.13 | P |
| GeoAware-SC | sem LICENSE | SD+DINOv2 + pós-processador; 85.6 PCK@0.1 SPair-71k | extração SPair 2 h RTX 3090, 90 GB disco | P |
| DINOv2 | Apache 2.0 | features de patch | leve | R |
| DINOv3 (gated) | "DINOv3 License" (Meta custom; blog chama de "commercial license") | ViT-S→7B; SPair recall 58.7 (7B) vs 56.1 DINOv2-g | — | P/R |
| RoMa v2 (Parskatt/RoMaV2) | MIT exceto backbone DINOv3 | warp denso + overlap/precisão; kernel CUDA opcional; Linux Py 3.12 | — | P |
| MASt3R / DUSt3R | CC BY-NC-SA 4.0 (+ termos mapfree) | matches 2D-2D + 3D | CUDA 12.1 | P |
| VGGT | código OK comercial desde 2025-07-29; só checkpoint VGGT-1B-Commercial (gated) | câmeras, depth, point maps, tracks | <1 s/cena; bf16 Ampere | P |
| EfficientLoFTR | Project Registration License v1.0 (comercial após registro) | matches semi-densos | fp16 | P |
| MapAnything, Pi3 | — | geometria multi-view | — | R |

Estado da correspondência semântica 2025–26 (R): SPair-71k PCK@0.1 de GeoAware-SC 85.6 → SemAlign3D 88.9 (2025); DiTF (NeurIPS 2025) features de DiT superam SD/DINO; SimpleMatch (2026) 84.2 baseline DINOv2; MARCO (CVPR 2026) +8.9–10.3 PCK@0.01 e 10× mais rápido; Jamais Vu (2025): matchers supervisionados colapsam em keypoints não vistos (SPair-U) — relevante para roupas. Leitura prática: DINOv2/DINOv3 congelado (+ features SD/DiT) com pós-processamento geométrico; RoMa v2 é o melhor matcher denso off-the-shelf mas é geométrico, não semântico — não casa manga em A com a mesma manga em B através de pose/identidade sem prior semântico.

Linhagem de warping de roupa (R): TPS (CP-VTON) → appearance flow (ClothFlow/PF-AFN, HR-VITON) → GP-VTON (CVPR 2023): fluxos locais por parte + montagem por parsing global + truncamento dinâmico de gradiente. DeepFashion2: 13 categorias, até 39 landmarks/categoria. Nenhum modelo aberto 2025–26 de landmarks de roupa encontrado (U).

## 4. Reconstrução 3D de roupa, priors, simulação, VTON 3D-aware
| Componente | Repo | Licença | Status | Evidência |
|---|---|---|---|---|
| Garment3DGen (Meta) | nsarafianos/Garment3DGen | CC BY-NC 4.0 | precisa base mesh + imagem (InstantMesh); nvdiffrast, PyTorch3D, Py 3.8/CUDA 11.8 | P |
| GarmentCode / pygarment | maria-korosteleva/GarmentCode | MIT | v2.0.0 2024-08-30; drape via fork NVIDIA Warp; corpos de GarmentCodeData | P |
| GarmentCodeData | igl.ethz.ch (bloqueado) | U | — | U |
| Design2GarmentCode | código não encontrado | U | — | R |
| SewFormer | sail-sg/sewformer; HF liulj/sewformer | sem licença | imagem → padrão; simulação requer Maya + RSC-Net SMPL | P |
| NeuralTailor | — | U | nuvem de pontos → padrão | R |
| DressCode (3D) | IHe-KaiI/DressCode | U | texto → SewingGPT + texturas | R |
| ClothesNet, BCNet | — | U | dataset / 2020 frontal | R |
| Dress-1-to-3 (fev 2025) | página bloqueada | U | padrão → multi-view diffusion → CIPC; não recupera painéis ausentes | R |
| ChatGarment (CVPR 2025) | biansy000/ChatGarment | Apache 2.0 | imagem/texto → GarmentCode JSON → ContourCraft-CG; usa GPT-4o em alguns scripts; pesos incertos | P |
| AIpparel, GarmentDiffusion | — | U | geração multimodal de padrões | R |
| DressWild (arXiv 2602.16502, fev 2026) | — | U | feed-forward, pose-agnostic imagem → padrão + roupa 3D; código não verificado | R |
| HOOD | dolorousrtur/hood | MIT | SMPL; 2023-09-30 | P |
| ContourCraft | dolorousrtur/contourcraft | MIT | multi-peça, resolução de interseções; só SMPL (SMPL-X TODO); inferência em sequência de malha arbitrária | P |
| NVIDIA Warp | NVIDIA/warp | Apache 2.0 | wheels Windows CUDA (Turing+) | P |
| Blender cloth | — | GPL | solver CPU | I |
| 3DV-TON (MM 2025) | 2y7c3/3DV-TON | MIT | vídeo; pipeline de guia 3D texturizado NÃO liberado; GVHMR (SMPL) + DensePose + CatVTON | P |
| VTON 360 (CVPR 2025) | scnuhealthy/VTON360 | sem LICENSE | multi-view + nerfstudio/gsplat/tiny-cuda-nn | P |
| GS-VTON | yukangcao/GS-VTON | sem LICENSE | 3DGS + IDM-VTON (CC BY-NC-SA) | P |

Viabilidade de "reconstruir corpo + roupa → simular → renderizar → refinar" em 12 GB e <60 min (I): cada estágio cabe em 12 GB se sequencial (SAM 3D Body int8/bf16; ChatGarment/SewFormer com VLM 4-bit; GarmentCode + Warp/ContourCraft em segundos–minutos; rasterizar; refinamento SD/FLUX em 12 GB). <60 min plausível para uma peça; bloqueios práticos: dependência GPT-4o do ChatGarment e simulação Maya do SewFormer. Qualidade: estimadores de padrão a partir de uma imagem treinados em dados sintéticos frontais (SewFactory); sentado/deitado/pernas cruzadas → topologia de painéis errada; Dress-1-to-3 não recupera painéis ausentes; DressWild alega pose-agnostic mas não verificado. Licenças: cadeia bloqueada comercialmente em SMPL/SMPL-X e Garment3DGen (CC BY-NC). Caminho mais limpo: SAM 3D Body → MHR (Apache) ou Anny → ContourCraft com corpo não-SMPL (treinado em SMPL; qualidade não testada) ou Warp/Blender → ChatGarment (Apache)/GarmentCode (MIT). Protótipo de pesquisa, não caminho de produto, até verificar DressWild e GarmentCodeData.

## 5. VTON em vídeo — ideias transferíveis
| Método | Repo | Licença | Notas | Evidência |
|---|---|---|---|---|
| MagicTryOn | vivoCameraResearch/Magic-TryOn | README CC BY-NC-SA 4.0 (badge inconsistente) | Wan2.1-I2V-14B; 14B (2025-06), 1.3B (2025-12-26), Turbo (2026-04-19); preservação coarse-to-fine + mask-aware loss | P |
| CatV2TON | Zheng-Chong/CatV2TON | CC BY-NC-SA 4.0 | DiT único imagem+vídeo; ViViD-S filtrando frames de costas + suavização 3D de máscaras | P |
| DreamVVT | Virtu-Lab/DreamVVT | sem licença, sem pesos | DiT por estágios | P |
| 3DV-TON | acima | MIT | 3D texturizado (SMPL via GVHMR) como guia | P |
| 2026 preprints | iTryOn (2605.21431), BooM-VVT mask-free (2609.04120), keyframe detail injection (2512.20340) | — | auto-reportado | R |

Transferível para imagem única: (a) guia 3D texturizado ou malha MHR como condicionamento geometricamente consistente; (b) máscaras de roupa suavizadas em 3D em vez de parsing por imagem; (c) treino mask-free com pseudo-dados para eliminar falhas de parsing em pose difícil; (d) injeção de detalhe por referência.

## Nós ComfyUI (2026-10-07)
| Componente | Nó | Status | Evidência |
|---|---|---|---|
| SAM 3 / 3.1 | nativo no core (comfy_extras/nodes_sam3.py: SAM3_Detect, SAM3_VideoTrack, SAM3_TrackToMask, SAM3_TrackPreview; checkpoint sam3.1_multiplex_fp16); também PozzettiAndrea/ComfyUI-SAM3; ComfyUI-RMBG v3.2.0 (2026-09-30) | mantido | P |
| SAM 3D Body | nativo no core desde 2026-08-23 (PR #14370, kijai: GLB/BVH, MoGe FOV, SAM3.1 track; modelos HF Comfy-Org/sam-3d-body; reduzir batch_size) | mantido | P |
| MoGe-2 | nativo (LoadMoGeModel / MoGeInference) | mantido | R |
| DWPose / DepthAnything V2 / DSINE | Fannovel16/comfyui_controlnet_aux (Apache 2.0) | baixa rotatividade, vivo | P |
| SAM 2 | kijai/ComfyUI-segment-anything-2 (WIP, 57 issues) | semi-estagnado | P |
| Depth Anything V2 | kijai/ComfyUI-DepthAnythingV2 | estagnado | P |
| Depth Anything 3 | PozzettiAndrea, Ltamann, 1038lab | só comunidade | R |
| BiRefNet | 1038lab/ComfyUI-RMBG (GPL-3.0, v3.2.0 2026-09-30; inclui SegFormer clothes, BEN2) | mantido | P |
| SegFormer-B2-clothes | chflame163/ComfyUI_LayerStyle (MIT, ativo) | mantido | P |
| Sapiens / Sapiens2 | smthemex, lassiiter, Bogyie, starsFriday (2026-05) | wrappers pequenos | R |
| HMR2.0 | logtd/ComfyUI-4DHumans (GPL-3.0, Ubuntu) | pouco mantido | P |
| DUSt3R / MASt3R / RoMa | chaojie/ComfyUI-dust3r (2024-05); sem nó MASt3R/RoMa | estagnado / nenhum | R |

## Itens NÃO VERIFICADOS
Licença CameraHMR; licença GarmentCodeData; licença Fashionpedia; releases de código Dress-1-to-3 e DressWild; código Multi-HMR 2; licenças SewFormer/DressCode/BCNet/ClothesNet; licença do card HF mattmdjaga/segformer_b2_clothes; VRAM oficial SAM 3 / SAM 3D Body / Sapiens2; se "SAM License"/"Sapiens2 License" permitem uso comercial.

## Fontes (2026-10-07)
github.com/facebookresearch/sam3 (+LICENSE) · facebookresearch/sam2 · facebookresearch/sapiens (+LICENSE) · facebookresearch/sapiens2 (+LICENSE.md) · facebookresearch/sam-3d-body (+INSTALL.md) · facebookresearch/MHR · facebookresearch/dinov3/blob/main/LICENSE.md · facebookresearch/DensePose/blob/master/LICENSE · facebookresearch/detectron2/tree/main/projects/DensePose (+doc/DENSEPOSE_IUV.md) · facebookresearch/vggt · ByteDance-Seed/Depth-Anything-3 · DepthAnything/Depth-Anything-V2 · Parskatt/RoMaV2 · naver/multi-hmr (+LICENSE.txt) · naver/anny · naver/mast3r · isarandi/nlf · pixelite1201/CameraHMR · saidwivedi/TokenHMR · caizhongang/SMPLer-X (+LICENSE) · shubham-goel/4D-Humans · vchoutas/smplx · IDEA-Research/DWPose · Tau-J/rtmlib · ViTAE-Transformer/ViTPose · CMU-Perceptual-Computing-Lab/openpose/blob/master/LICENSE · IDEA-Research/GroundingDINO · IDEA-Research/Grounding-DINO-1.5-API · IDEA-Research/Grounded-SAM-2 · ZhengPeng7/BiRefNet · microsoft/MoGe · apple/ml-depth-pro/blob/main/LICENSE · prs-eth/Marigold · Stable-X/StableNormal · baegwangbin/DSINE (+LICENSE) · GoGoDuck912/Self-Correction-Human-Parsing · Engineering-Course/CIHP_PGN · StartHua/Comfyui_segformer_b2_clothes · Tsingularity/dift · Junyi42/GeoAware-SC · Junyi42/sd-dino · zju3dv/EfficientLoFTR (+LICENSE) · nsarafianos/Garment3DGen (+LICENSE.md) · maria-korosteleva/GarmentCode · sail-sg/sewformer · biansy000/ChatGarment · dolorousrtur/hood · dolorousrtur/contourcraft · NVIDIA/warp · 2y7c3/3DV-TON · scnuhealthy/VTON360 · yukangcao/GS-VTON · Zheng-Chong/CatV2TON · vivoCameraResearch/Magic-TryOn · Virtu-Lab/DreamVVT · Comfy-Org/ComfyUI/pull/14370 · Comfy-Org/ComfyUI/blob/master/comfy_extras/nodes_sam3.py · Fannovel16/comfyui_controlnet_aux · kijai/ComfyUI-segment-anything-2 · kijai/ComfyUI-DepthAnythingV2 · 1038lab/ComfyUI-RMBG · chflame163/ComfyUI_LayerStyle · PozzettiAndrea/ComfyUI-SAM3 · logtd/ComfyUI-4DHumans. Secundárias (snippets): ai.meta.com/blog (SAM 3, DINOv3), huggingface.co (facebook/sapiens-*, facebook/sam-3d-body-dinov3, mattmdjaga/segformer_b2_clothes, zhengchong/CatV2TON, LuckyLiGY/MagicTryOn), smpl-x.is.tue.mpg.de/modellicense.html, Meshcapade/wiki, docs.comfy.org (MoGe), comfyui-wiki.com, runcomfy.com, arXiv: 2511.16719, 2602.15989, 2511.15586, 2511.03589, 2606.14841, 2411.08128, 2407.07532, 2511.15706, 2508.10104, 2604.18267, 2609.29193, 2601.12357, 2503.22462, 2505.18584, 2506.08220, 2502.03449, 2602.16502, 2412.17811, 2412.08603, 2504.21476, 2504.17414, 2503.12165, 2410.05259, 2508.02807, 2512.20340, 2605.21431, 2609.04120, 2303.13756, 1901.07973, 2005.00419, 2004.12276, 2406.16864, 2403.00712.
