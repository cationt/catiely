# Levantamento bruto — sistemas comerciais, datasets/licenças e métricas/avaliadores (agente de pesquisa, 2026-10-07)

> Material bruto em inglês, gerado por agente de pesquisa. Legenda: **[A]** página primária lida (GitHub); **[B]** texto primário via snippet de busca; **[C]** secundário; **[INF]** inferência arquitetural; **NV** = NÃO VERIFICADO. Proxy bloqueou a maioria dos hosts de vendors/papers.

## TOPIC A — Commercial / proprietary systems as functional benchmarks

| System | Inputs (worn-reference accepted?) | Preserves / regenerates | Resolution & limits | Documented failure modes | Pricing (public) | Evid. |
|---|---|---|---|---|---|---|
| **Google Doppl (Labs)** — shut down 2026-04-30 | Full-body photo + photo/screenshot of an outfit incl. *other people wearing clothes* → worn-reference **YES** | Image + short video; invents matching pants/shoes if only a shirt is uploaded; fallback "basic black tee and pants" [B] | US adults only; tops/bottoms/dresses; footwear, lingerie, swimwear, accessories excluded; weak on costumes/cultural dress; sheer unsupported [B] | Third-party: pants/socks errors, body-shape warp in mirror selfies, poor with weak lighting / atypical poses [C] | Free | B/C |
| **Google Shopping "Try it on"** | Shopper photo (full-body or selfie → Nano Banana full-body avatar); garment **only from product listing** | Result "illustrative"; [INF] garment regenerated, face kept | Not for Sponsored; lingerie/swim/accessories unsupported; shoes added 2025-10-08; merchant images ≥512², ideally ≥1024; one garment, front-facing model/mannequin or flat | Google "what to avoid": phone too close, **sit/crouch**, far-away shots, children, **baggy clothes**, hands in pockets [B] | Free | B |
| **Gemini Nano Banana / Nano Banana Pro** | Generic multi-image editing; 2.5 Flash Image ≤3 inputs; 3 Pro Image up to 14 refs (≤6 objects, ≤5 characters) [B]. No try-on mode documented | Whole image regenerated; no pixel-preservation guarantee [INF]; SynthID watermark [B]; Adobe-forum user: face/body altered, garment not transferred [C] | 3 Pro Image 2K/4K | may return text instead of image; stop early; safety refusals | per-token API | B |
| **Vertex AI Virtual Try-On (virtual-try-on-001)** | dedicated person + product API | — | — | — | — | **NV** |
| **Kling AI / Kolors Virtual Try-On** | `human_image` + `garment_image` (fal); worn-ref NV | Kolors README: try-on only as demo; **no try-on weights/code** [A]; Kolors base: Apache code, weights academic-free, commercial by registration | — | ComfyUI node "image resolution too low" error [C] | fal $0.07/gen [C] | A/C |
| **FASHN.ai v1.6 / Try-On Max** | `model_image`, `garment_image`; `category` ∈ {auto, tops, bottoms, one-pieces}; **`garment_photo_type` ∈ {auto, flat-lay, model}** ("model" = worn by a person; flat-lay covers ghost-mannequin); `mode` performance/balanced/quality (~7/10/19 s); `segmentation_free`, `num_samples`, `seed` → worn-reference **YES (documented)** | Auto-category on full-body on-model photos swaps entire outfit; Try-On Max "preserves identity, pose, styling"; supports clothing, shoes, hats, jewelry, bags [B] | v1.6 native 864×1296; 5–17 s; Try-On Max ~50 s | `PoseError` when no body pose detected in model or garment image [B] | $0.075/credit; v1.6 = 1 credit; Max = 4 | B |
| **Botika** | flat-lay → AI model | new on-model image | HD / 4K | — | ~$33/mo | B/C |
| **Vmake**, **Veesual**, **Zalando** (3D avatar), **ABOUT YOU**, **Amazon** | see notes: mostly product-to-model or AR; limited docs | — | — | — | — | C / NV |
| **Alibaba Outfit Anyone** | demo: "only allows uploading clothing images"; models preset; no code/weights/license [A]; Aidge "Virtual TryOn" API NV | — | — | — | — | A |
| **ByteDance Seedream 4.0 / Dreamina** | multi-reference editor "up to a dozen" refs; try-on from multiple clothing photos cited [B] | generic whole-image [INF] | 2K/4K | — | — | B/C |
| **Adobe Firefly** | photo → prompt-driven outfit change; generative-fill brush | region inpainting [INF] | — | blocked/failed transfers reported [C] | subscription | B/C |
| **Pixelcut** | clothing "standalone **or worn by a person**"; fit onto library or custom model → worn-reference **YES** | — | — | — | 10 credits | B |
| **Huhu.ai**, **Fotor** | model + garment URL + category; Fotor claims keep face/pose/body, <5 s | — | — | preset-driven | free tiers | B/C |

### A.2 Functional target from public commercial systems
- **Worn-reference input:** documented by FASHN (`garment_photo_type=model`), Pixelcut; core of Doppl. Generic editors accept it without garment-specific guarantees.
- **Categories:** tops/bottoms/one-pieces; whole-outfit swap; shoes (Google since 2025-10); hats/jewelry/bags (FASHN Max). Lingerie/swim excluded by Google.
- **Multi-garment/layering:** multi-reference editors (Seedream, Nano Banana Pro 14 refs); dedicated APIs single-garment-per-call.
- **Preservation claims:** FASHN Max "preserves identity, pose, styling"; nobody documents pixel-exact background/face preservation.
- **Pose change / hard poses:** **not a solved commercial capability** — Google tells users not to sit/crouch and warns about baggy clothing.
- **Resolution:** FASHN 864×1296; Max ≥1K; Nano Banana Pro 2K/4K; Google asks ≥1024 inputs.
- **Failure classes to include in benchmark:** sitting/crouching, phone too close/far, hands in pockets, baggy source clothing, costumes, sheer fabrics, lower-body items, mirror-selfie body warp, garment invention, no-pose-detected.

## TOPIC B — Datasets, benchmarks, licenses

### B.1 Established datasets
| Dataset | Content | License (exact) | Redistribution in repo? | Evid. |
|---|---|---|---|---|
| **VITON-HD** | 1024×768; 11,647 train / 2,032 test frontal woman + top | **CC BY-NC 4.0**, "Copyright (c) 2021, NeStyle Inc." | NC sharing allowed with attribution; [INF] underlying Zalando photo rights not addressed → safer to ship a manifest | A |
| **Dress Code** | 53,792 garments / 107,584 images; upper/lower/dresses; keypoints, SCHP, DensePose | Custom **YNAP licence**: research/teaching only; no commercial; no re-identification; sharing only as provided; hand-signed release; "will not be released to private companies" | Effectively **no**; manifest/IDs only | A |
| **DeepFashion** | gated | non-commercial research only; no copy/publish/distribute | **No** | B |
| **DeepFashion2** | 491,895 images; password | **No license text on GitHub** | assume NC; **no** | A |
| **DeepFashion-MultiModal** | 44,096 images; parsing, keypoints, DensePose, text | NC research only; no redistribution | **No** | A |
| **Fashionpedia** | 48,825 images (Flickr + Unsplash/Pexels); 27 cats, 19 parts, 294 attrs; JSON has per-image `license` + `original_url` | **Not stated on GitHub**; HF mirrors say CC BY 4.0 [C] — NV; per-image Flickr licenses may include NC/ND | only after per-image check | A/C |
| **StreetTryOn** (WACV'25) | 12,364 / 2,089 street images from DeepFashion2; tasks Shop2Model, **Model2Model**, **Street2Street**, Shop2Street, Model2Street | annotations only; "inherits DeepFashion2 and VITON-HD… No commercial usage" | **No** | A |
| **LAION-based fashion** | LAION-Garment (Any2AnyTryon) no license; LRVS-Fashion CC BY-NC 4.0 annotations | URLs only | A/B |

### B.2 2024–2026 benchmarks
| Benchmark | Focus / size | Availability & license | Evid. |
|---|---|---|---|
| **VTBench** (2505.19571) | hand-occlusion handling, background consistency, cross-category size; ~2,933 items; pairwise prefs | repo README+figure only; **no data/license**; "not open-source" per OpenVTON-Bench | A/B |
| **OpenVTON-Bench** (2601.22725) | ~100K pairs ≤1536², 20 categories; VLM judge 1–5 on Background/Identity/Texture/Shape/Overall; SAM3 region metrics; DINOv3; human study 76 users / 92,072 samples; admits multi-layer occlusion and acrobatic poses under-represented | Code **MIT**; data HF **CC BY-NC 4.0** | A/B |
| **VITON-Bench (VTON-VLLM, NeurIPS 2025)** | complex scenarios; human-annotated criteria | repo no LICENSE, placeholder links → NV | A |
| **OmniTry-Bench** | 12 wearable types; shop + wild; 6,975 pairs / 360 small; images "mainly from Pexels" | code Apache-2.0; bench license NV | A |
| **Garments2Look** (CVPR 2026) | ~80K pairs, 40 categories, outfit-level with accessories | HF card Apache-2.0 [B] | B |
| **TStars-VTON** (Alibaba, 2604.19748) | 1–6 layered items; ~1,780 pairs | license NV | C |
| **VTEdit-Bench** (2603.11734) | 24,220 pairs, 5 tasks | release NV | B |
| **Dress-ED** (ECCV 2026) | 146,460 quadruplets, 7 edit types on Dress Code | CC BY-NC 4.0 + Dress Code licence | A |
| **VTON-QBench / VTON-IQA** (ECCV 2026) | 62,688 images from 14 sources (incl. Nano Banana Pro, GPT-Image-1.5), 431,800 ratings | CC BY-NC-SA 4.0 | A/B |
| **TryOnReward-100K / TryOn-Bench** (2609.13259) | 99,286 preference pairs; ≥9 annotators | release NV | B |
| **Handfit-3K** (2408.12340) | 3,620 hand-occlusion images | NV | B |
| **Sitting / lying poses** | **No dedicated public benchmark found** | — | — |

### B.3 Legally safe sources for own benchmark
| Source | Key terms | Redistribute in repo? |
|---|---|---|
| **Unsplash License** | free incl. commercial; **excludes compiling photos to replicate a similar/competing service**; help center flags "machine learning and/or AI purposes" as restricted; datasets non-transferable | **No** — manifest only; ML clause is a risk even for evaluation |
| **Pexels License** | free; no standalone distribution; no compiling to compete; identifiable people not in negative/political/endorsement contexts | **No** — manifest only (OmniTry used Pexels: precedent, not clearance) |
| **Pixabay Content License** | free, modify; **no standalone distribution**; uploader must hold releases; personality rights may apply | **No** — manifest only |
| **Wikimedia Commons** | only free licenses (CC0, CC BY, CC BY-SA, PD); per-file; **personality rights separate**; consent needed for private-place photos | **Yes, per-file**, with attribution/SA; filter for consent/private settings |
| **Synthetic humans** (BEDLAM/2.0, SynBody, MS Face Synthetics) | non-commercial research only; redistribution not permitted | **No** |
| **Self-captured** | full control; written model releases | Yes — the only practical route for sitting/lying/occlusion sets |

## TOPIC C — Evaluation metrics and local tools

### C.1 Identity
- **InsightFace / ArcFace (buffalo_l)**: code MIT; pretrained models and training data "**non-commercial research purposes only**"; 2025-11-24: buffalo_l licensing via recognition-oss-pack@insightface.ai [A].
- **AdaFace**: repo MIT; weights trained on WebFace4M/12M, MS1MV2; dataset terms NV (typically NC).
- **facenet-pytorch**: MIT; weights VGGFace2/CASIA-WebFace; terms NV. AuraFace (Apache-2.0 claim) [C].
- [INF] cosine on aligned crops; in mask-based VTON the face is copied through, so identity drift is diagnostic mainly for whole-image generators.

### C.2 Pose
- **DWPose**: Apache-2.0 code; ONNX weights; trained COCO + UBody [A]. **mmpose/RTMPose**: Apache-2.0 [A]. Some TensorRT ports CC BY-NC-SA [C]. HMR/SMPL-based: restrictive licenses — flag.

### C.3 Structure / background drift
- **LPIPS**: BSD-2-Clause [A]. **DISTS**: MIT [A]. SSIM/PSNR trivial.
- Practice: OpenVTON-Bench computes SSIM/PSNR/LPIPS/cosine on SAM3 garment regions + DINOv3 full-image; OmniTry computes LPIPS/SSIM outside the object [A].

### C.4 Garment fidelity
- **CLIP** code MIT (weights license not stated). **DINOv2** Apache-2.0. **DINOv3** custom royalty-free license (no military/ITAR; ship agreement; gated) — commercial not expressly excluded, legal review [INF]. **SigLIP 2**: Apache-2.0 [A].
- VTON-specific: **M-DINO / M-CLIP-I** — mask garment in result and reference, white background, cosine (OmniTry; CtrlVTON); DINO lower and more geometry-sensitive than CLIP. **DINOv3 [CLS] cosine** + multi-scale eroded masks (OpenVTON-Bench). CORAL **GTC**/**FPC**. DAT (2608.29804): 7 interpretable garment dimensions. **"GarmentCLIP": not found → NV.**

### C.5 Local VLM judges
| Model | Sizes | License | VRAM notes | Evid. |
|---|---|---|---|---|
| **Qwen3-VL** | 2B/4B/8B/32B dense; 30B-A3B, 235B-A22B MoE; FP8 | Apache-2.0 [A] | Q4: 8B ≈6–12 GB, 32B ≈20 GB [C] | A/C |
| **InternVL3 / 3.5** | 1B–241B | code MIT; weights license not stated | — | A |
| **Gemma 3** | 4B/12B/27B | Gemma Terms + Prohibited Use | 27B bf16 ≈46 GB [C] | C |
| **MiniCPM-V/o** | V 4.6: 1.3B (4 GB); o 4.5: 9B (19 GB bf16 / 11 GB int4) | Apache-2.0 [A] | as listed | A |
| **Molmo 2** | 4B, 8B | repo Apache-2.0; weights NV | 8B bf16 ≈17 GB [C] | A/C |
Reliability: **no VTON-specific reliability numbers for open VLMs found**. VTON papers use closed judges (Gemini 3.x, GPT-5).

### C.6 Weaknesses of VLM judges
- **PICABench** (2510.17681): general-prompt VLM judging "lack[s] sensitivity to nuanced physical violations"; remedy = region-grounded yes/no on shadows, reflections, contact, material deformation [B].
- **TryOnReward** (2609.13259): generic VLMs "fail to provide the discriminative granularity" for try-on; reward hacking [B].
- **VTON-VLLM**: standard metrics miss texture preservation and body–clothing coherence [B].
- **EditJudgeBias** (2610.01670): swapping candidate order reverses up to 60.9% of pairwise MLLM decisions; fabricated majority opinions inflate ratings [B]. "VLM Judges Can Rank but Cannot Score" (2604.25235); informativeness bias (2604.17768) [C].
- Implication [INF]: pairwise/ranking with position randomization; atomic yes/no per region; never a single global score.

### C.7 Human-evaluation protocols (2025–2026)
- MuGa-VTON: 100 samples, 20 AMT raters; Q1 garment match, Q2 realism. OmniVTON: 100 volunteers × 100 groups, randomized. Voost: 50 samples; photorealism, garment detail, structure. DAT: triplets, randomized L/R, A/B/Same(+N/A), each twice. TryOnReward-100K: ≥9 annotators, 1–5, three dims. OpenVTON-Bench: 76 users, 92,072 samples. VTON-QBench: 13,838 annotators. VTBench: pairwise across 6 models. LPH-VTON: 21 participants. Layering VTON: 5-point Likert incl. inner-layer visibility.
- Pattern: forced-choice pairwise or best-of-N; 20–100 raters; 50–100 items; identity folded into "realism".

## Open items (NV)
Vertex AI virtual-try-on-001 rules; FASHN fashn-vton-1.5 weights license; Amazon apparel page; Alibaba Aidge spec; Huhu categories; exact Pexels wording; Gemini output ownership; Molmo2/InternVL3 weight licenses; Fashionpedia license; TStars/OmniTry-Bench/TryOn-Bench data licenses.

## Sources
support.google.com/labs/answer/16537062 · blog.google (doppl; shoes) · etvbharat (Doppl) · tech.yahoo.com (Doppl test) · support.google.com/googleshopping/answer/16253678 · techcrunch.com 2025-10-08 · support.google.com/merchants/answer/14096369 · ai.google.dev/gemini-api/docs (models, image-generation) · docs.cloud.google.com (vertex limitations; vto) · community.adobe.com/questions-404/... · github.com/Kwai-Kolors/Kolors · fal.ai (kolors try-on) · docs.fashn.ai (tryon-v1-6, parameters-guide, tryon-max) · fashn.ai/blog (v1-6; pricing) · botika.com · iotm2mcouncil.org (Veesual) · corporate.zalando.com · en.aboutyou.de · amazon.com VTO hub · wwd.com · github.com/HumanAIGC/OutfitAnyone · docs.aidc-ai.com · seed.bytedance.com (Seedream 4.0) · adobe.com/products/firefly · pixelcut.ai (api, guide) · huhu.ai/try-on-api · fotor.com · github.com/shadow2496/VITON-HD (+LICENSE) · github.com/aimagelab/dress-code (+LICENCE) · mmlab.ie.cuhk.edu.hk DeepFashionAgreement.pdf · github.com/switchablenorms/DeepFashion2 · github.com/yumingj/DeepFashion-MultiModal · github.com/cvdfoundation/fashionpedia · arxiv 2004.12276 · github.com/cuiaiyu/street-tryon-benchmark · github.com/logn-2024/Any2anyTryon · arxiv 2505.19571 · github.com/HUuxiaobin/VTBench · arxiv 2601.22725 · github.com/RenxingIntelligence/OpenVTON-Bench · github.com/HiDream-ai/VTON-VLLM · github.com/Kunbyte-AI/OmniTry (+omnitry_bench) · HF ArtmeScienceLab/Garments2Look · arxiv 2604.19748 · 2603.11734 · github.com/aimagelab/Dress-ED · github.com/litelightlite/VTON-IQA · arxiv 2609.13259 · 2408.12340 · unsplash.com/license (+help) · pexels.com/terms-of-service · pixabay.com/service/license-summary · commons.wikimedia.org (Licensing; Identifiable people) · bedlam.is.tue.mpg.de/license · HF caizhongang/SynBody · github.com/microsoft/FaceSynthetics · github.com/deepinsight/insightface · github.com/mk-minchul/AdaFace · github.com/timesler/facenet-pytorch · github.com/IDEA-Research/DWPose · github.com/open-mmlab/mmpose · github.com/richzhang/PerceptualSimilarity · github.com/dingkeyan93/DISTS · github.com/openai/CLIP · github.com/facebookresearch/dinov2 · github.com/facebookresearch/dinov3/blob/main/LICENSE.md · big_vision (SigLIP 2) · arxiv 2608.29804 · github.com/QwenLM/Qwen3-VL · github.com/OpenGVLab/InternVL · github.com/OpenBMB/MiniCPM-V · github.com/allenai/molmo · arxiv 2510.17681 · 2610.01670 · 2604.25235 · 2604.17768.
