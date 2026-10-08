# Fase 3 — Viabilidade local: RTX 5070 12 GB · ~16 GB RAM · Windows 11 · ComfyUI Desktop

**Data:** 2026-10-07 (revisado 2026-10-08). **Status global: PENDENTE DE MEDIÇÃO PADRONIZADA NO HARDWARE-ALVO.** Esta sessão rodou em contêiner Linux sem GPU. Existe, porém, **evidência experimental histórica da própria RTX 5070 do usuário** (§1b), registrada com o nível `MEDIDO/OBSERVADO NO HARDWARE-ALVO — HISTÓRICO NÃO PADRONIZADO`: ela não substitui a medição com `tools/measure_run.py` (sem inventário, sem versão do ComfyUI, sem pico de memória), mas é a única medida real disponível e orienta a prioridade dos experimentos. O restante é: fatos de código/documentação (`P`), relatos de usuários em hardware parecido (`R`), estimativas com hipóteses explícitas (`E`) e inferências (`I`). O procedimento de medição reproduzível está em §8 e nos scripts de `tools/`.

---

## 1. Hardware e pilha de software (fatos)

| Item | Valor | Ev. |
|---|---|---|
| GPU | RTX 5070, GB205 (Blackwell, **sm_120**), 6 144 CUDA cores, 12 GB GDDR7 192-bit, ~672 GB/s, PCIe 5.0 x16, 250 W | `R` (reviews; nvidia.com bloqueado) |
| VRAM utilizável no ComfyUI/Windows | 12 GB − `EXTRA_RESERVED_VRAM` 600 MB ("Windows is higher because of the shared vram issue") − contexto CUDA/driver/display (~0.3–0.8 GB, varia) ≈ **~10.5–11.3 GB** | `P` (model_management.py) + `E` |
| FP8 / NVFP4 | `supports_fp8_compute()` → True (major ≥ 9; Windows exige torch ≥ 2.4); `supports_nvfp4_compute()` → True (major ≥ 10) | `P` |
| PCIe host→device | teórico ~63 GB/s; medido 3DMark em rig 5070: 44.9 GB/s; cudaMemcpy pinned em série 50: **NV** | `R`/`I` |
| RAM | ~16 GB físicos; Windows 11 + ComfyUI Desktop + frontend ≈ 4–6 GB antes de qualquer modelo (a medir com `inventory_windows.ps1`) | `E` |
| Pinned memory (ComfyUI) | `MAX_PINNED_MEMORY = ram * 0.40` no Windows → **~6.4 GB** | `P` |
| PyTorch | Blackwell desde 2.7.0 (2025-04); estável atual 2.14.1 (2026-09-30); CUDA 13.0 padrão desde 2.12; ComfyUI README exige cu130 em séries 20+ | `P` |
| ComfyUI core | v0.39.0 (2026-10-05); **DynamicVRAM (comfy-aimdo) padrão** em NVIDIA com torch ≥ 2.8 | `P` |
| ComfyUI Desktop | app legado arquivado (2026-06-26); **Comfy-Desktop v1.1.6 (2026-10-03)**: Python 3.13.12 + uv; documenta stacks cu126/cu128 com torch 2.11.0; **qual stack instala numa 5070: NV** | `P` |
| Atenção/kernels Windows | SageAttention 2.2.0 wheels Windows (sm89/sm120, CUDA ≥ 12.8); triton-windows 3.6; SageAttention 3 (FP4) Windows: NV; xformers sm_120 Windows: NV; FlashAttention 2.8.4 wheels comunitárias | `P`/`NV` |


## 1b. Evidência histórica no hardware-alvo (`MEDIDO/OBSERVADO — HISTÓRICO NÃO PADRONIZADO`)

Relato do operador sobre execuções anteriores na **RTX 5070 12 GB** (data, versão do ComfyUI, flags, RAM/commit e pico de VRAM **não registrados**; por isso não é uma medição padronizada):

| Item | Observação |
|---|---|
| Modelo | Qwen-Image-Edit-2511, GGUF **Q5** |
| Resolução | ~544×960 |
| Tempo | **~10–15 min por imagem** |
| Técnica | Edição por **denoise global** (img2img sobre A inteira) com a roupa de B como referência |

Sweep de denoise observado (mesma A/B):

| Denoise | A (pose/corpo/câmera) | Roupa de B | Observação |
|---|---|---|---|
| 0.18 · 0.22 · 0.26 · 0.30 · 0.50 | preservadas | **praticamente não aparece** | — |
| 0.70 | razoavelmente preservada | começa a aparecer | geometria/drape **incorretos** |
| 0.80 | idem | idem | mesmo problema estrutural |
| 1.00 | reconstrução de pose/corpo/câmera **aumenta** | mais forte | — |

**Classificação do experimento (rev. 2026-10-08, `06` L3):** o sweep variou apenas o **eixo temporal** (denoise global, img2img/SDEdit sobre A inteira); **não** testou o modo nativo do editor (denoise 1.0 com A como `reference_latent`) nem o **eixo espacial** (máscara de latente / força por pixel). Portanto mede a inadequação do img2img global, **não** a capacidade de QIE-2511. Abaixo de ~0,5 nenhum editor cria um objeto grande ausente de A (propriedade do SDEdit). Passos/CFG/LoRA/flags não foram registrados — repetir com registro.

**Interpretação (registrada como hipótese fundamentada, não como fato geral):** o denoise global acopla duas liberdades que o contrato exige separadas — a liberdade para *construir a roupa* (que precisa ser alta onde a peça nasce, inclusive sobre pele e fundo) e a liberdade para *reconstruir A* (que precisa ser ~zero). Um único escalar não pode satisfazer ambas: abaixo de ~0.7 a roupa não nasce; em ~0.7–0.8 nasce com geometria errada; em 1.0 A deriva. Consequências para a Fase 4/5: (a) qualquer rota baseada em regeneração global tem de ser testada com mecanismos que **separem espacialmente** essas liberdades — por motor: R1/R2 → máscara de latente (dura) + DifferentialDiffusion (gradiente) + A como referência (**ControlNet para klein 4B e Edit-2511: inexistente, verificado em `comfy/controlnet.py`**; o ControlNet Fun/InstantX existe só para Qwen-Image base/2512/2.1 e perderia a referência B); R3 → pose nativa DWPose + modo mascarado (`--no-segmentation-free`); R4 → DensePose + máscara nossa menos oclusores. "Geração em camadas" (Qwen-Image-Layered) **não é mecanismo de adição** (é decomposição imagem→RGBA; prompt não controla camadas; VRAM não declarada) e sai da lista. Denoise global < 1,0 fica **proibido como rota** (só baseline E0); (b) o custo de ~10–15 min/imagem em Q5 a ~0.5 MP sugere que, a 1 MP e com QA, QIE-2511 fica perto ou acima do teto de 1 500 s por candidato — **H4 continua decisiva**; (c) esta observação é a evidência mais direta de que "preservar A" e "criar roupa" não podem ser deixadas ao mesmo controle, o que motiva o Prototype 0 (ver `docs/06_RED_TEAM_REVISION.md`).

O que falta para promover a `MEDIDO NO HARDWARE-ALVO`: repetir com `measure_run.py` (frio/quente), `inventory_windows.ps1`, versão do ComfyUI/flags, pico de VRAM/commit, e as mesmas A/B usadas no Prototype 0.


### 1d. Medição padronizada mínima no hardware-alvo — FLUX.2 klein 4B (`MEDIDO NO HARDWARE-ALVO`, 2026-10-08)

Configuração `klein4b_fp8_2ref_1mp`: FLUX.2 klein 4B **destilado, fp8**; **A + B (2 referências)**; **~1 MP**; **4 passos**; ComfyUI **externo** (processo separado); `tools/measure_run.py` com commit charge **real** (`psapi.GetPerformanceInfo`); deadline 3 600 s. Registro legível por máquina em `benchmark/measurements/klein4b_fp8_2ref_1mp.json`; JSONs brutos na máquina-alvo (`…\w3-measure\runs\`). O run `20261008T071430Z_klein4b_official_ab_cold.json` **não** pertence a esta configuração e não entrou nas repetições.

| Estado | n | wall_s (cada run) | **mediana wall_s** | VRAM pico (mediana) | RAM sistema (mediana) | swap (mediana) | commit charge (mediana) | exit / deadline / OOM |
|---|---|---|---|---|---|---|---|---|
| **cold** | 3 | 34,820 · 31,849 · 31,818 | **31,849 s** | 11 660,5 MB | 10 671,8 MB | 935,1 MB | 29 258,5 MB | 0 / não / não |
| **warm** | 3 | 9,072 · 17,147 · 31,257 | **17,147 s** | 11 624,4 MB | 10 884,4 MB | 860,7 MB | 29 964,7 MB | 0 / não / não |

Leitura:
- **Tempo:** a mediana frio (31,8 s) está ≈ 2 % do teto de elegibilidade (§8 item 6: frio ≤ 1 500 s/candidato). A rota R1 é **elegível por tempo**, com folga para dezenas de seeds/máscaras no Prototype 0.
- **Variabilidade quente:** 9,1 → 31,3 s (3,4×). Registrada como variabilidade de cache/residência do ComfyUI externo (modelos parcialmente evictados entre runs; DynamicVRAM/fast-disk); **nenhum run foi descartado**. Consequência: comparações futuras reportam mediana **e** todos os runs; n ≥ 10 antes de percentis (§8 item 7).
- **VRAM:** pico ≈ 11,6 GB de 12 GB em ambos os estados — a rota roda, mas **no limite** (`NEAR_LIMIT`): sem folga para QA residente no mesmo processo; estimadores (SAM 3, DWPose, MHR) terão de rodar em sequência, com o motor descarregado.
- **Commit charge:** ≈ 29–30 GB do sistema inteiro (RAM física 16 GB) — a execução **depende do pagefile**; `tree_private_mb` do processo medido não representa o motor (ComfyUI externo).
- **O que esta medição não diz:** nada sobre **qualidade** (criação da peça, oclusão, preservação de A) — isso é o Prototype 0 (G0). A etapa de **viabilidade** de R1 fica **fechada** com este registro; nenhuma otimização adicional de R1 antes de G0 (D-048).

### 1e. R1-EI (klein-base-4B + Easy-Insert): identidade verificada e medição padronizada no hardware-alvo (2026-10-08; `P` para identidade, `MEDIDO NO HARDWARE-ALVO` para tempo/memória)

Identidade confirmada em fonte primária (`research_raw/08`): `huan-yin/Easy-Insert` @ `82094484…` (Apache-2.0; sem paper) é um **LoRA** para `FLUX.2-klein-base-4B` (não gated, Apache-2.0) que faz inserção por referência — background com buraco branco + referência sobre branco como **duas imagens de edição** do `Flux2KleinPipeline` + prompt fixo; crop quadrado 1,2× → 1024²; **15 passos, CFG 4** (klein-base não é destilado → 2 passes/passo); paste-back sem feather. O nome usado pelo projeto estava correto; precisões: o "8 GB" é o modo low-VRAM do **DiffSynth** (offload em disco + pesos fp8 em CPU), o LoRA do Hugging Face (`LiXiY/Easy-Insert`, 96 MB) é em formato **diffusers** e é o da demo oficial do autor, o LoRA DiffSynth está só no ModelScope (`NV` daqui).

Variante operacional escolhida para 12 GB / 16 GB: **Diffusers 0.39.0, carregamento sequencial bf16** (TE Qwen3-4B → embeddings → liberado; transformer bf16 + LoRA + VAE residentes; transformer sai da GPU antes do decode) — estimativa `E`: VRAM pico ≈ 9–10,5 GB, RAM ≈ 8–9 GB, numéricos iguais ao upstream. Rejeitadas: `pipe.to("cuda")` do upstream (≈ 15–16 GB VRAM), `enable_model_cpu_offload` (≈ 16–17 GB de RAM). Fallbacks registrados: `--mode fp8` (layerwise casting do transformer) e `--mode offload`. Protocolo comparativo com `klein4b_fp8_2ref_1mp` e as diferenças inevitáveis (processo próprio; 30 passes vs 4; bf16 vs fp8; 2 máscaras adicionais; crop 1024² vs A inteira; cold sem flush do page cache salvo RAMMap) estão em `tools/r1ei/README.md` §3. Preparação completa (manifesto de pins, runner com sidecar de proveniência, máscaras de viabilidade, `setup_r1ei.ps1`, `bench_r1ei.ps1`, testes CPU) em `tools/r1ei/`. A estimativa `E` acima (VRAM 9–10,5 GB) ficou **abaixo** do medido (12,1–12,2 GB): o estimador subestimou as ativações/reservas do allocator, confirmando a regra de §4 ("NEAR_LIMIT significa medir").

**Medição padronizada (`MEDIDO NO HARDWARE-ALVO`, 2026-10-08)** — configuração `r1ei_kleinbase4b_easyinsert_bf16_1024_normal`: klein-base-4B **bf16** + LoRA Easy-Insert; crop **1024²** (crop_scale 1,2) em torno da máscara, colado de volta em A; **15 passos, CFG 4 = 30 passes**; seed 1; modo `normal` (sequencial bf16); **mesmas A e B** do `klein4b_fp8_2ref_1mp` + 2 máscaras grosseiras (bbox); processo **próprio** (ComfyUI Desktop fechado) → `tree_rss`/`tree_private` **são** o motor; torch 2.12.1+cu130; `measure_run.py` com commit real; deadline 3 600 s. **cold** = processo novo, pesos do disco, page cache do SO **não** esvaziado (`cold_pagecache_unflushed`); **warm** = processo novo com cache do sistema presumivelmente aquecido — **não** é pipeline residente. Registro legível por máquina: `benchmark/measurements/r1ei_kleinbase4b_easyinsert_bf16_1024_normal.json`; JSONs brutos e sidecars na máquina-alvo (`…\w3-measure\runs\`, `…\w3-measure\r1ei\outputs\`); regenerável com `tools/r1ei/summarize_runs.py`.

| Estado | n | wall_s (cada run) | **mediana wall_s** | VRAM pico (mediana) | RSS árvore (mediana) | private árvore (mediana) | RAM sistema (mediana) | swap (mediana) | commit charge (mediana) | exit / deadline / OOM |
|---|---|---|---|---|---|---|---|---|---|---|
| **cold** | 3 | 222,488 · 287,689 · 272,462 | **272,462 s** | 12 136,7 MB | 9 293,2 MB | 23 728,2 MB | 15 200,3 MB | 984,4 MB | 32 697,2 MB | 0 / não / não |
| **warm** | 3 | 283,905 · 284,508 · 282,808 | **283,905 s** | 12 177,9 MB | 9 199,4 MB | 23 728,9 MB | 14 896,3 MB | 1 026,2 MB | 35 054,9 MB | 0 / não / não |

Leitura:
- **Tempo:** mediana frio **272,5 s** ≈ 18 % do teto de elegibilidade (§8 item 6: frio ≤ 1 500 s). R1-EI é **elegível por tempo**; **8,55×** mais lenta que klein 4B fp8 no frio (31,8 s) — compatível com 30 passes vs 4 (7,5×) mais carga por processo. Não há justificativa, por tempo, para `--mode fp8`/`offload`.
- **VRAM crítica:** picos de 12 129–12 187 MB em **6/6** runs, com 12 227 MiB físicos → folga mínima **≈ 40 MiB**. Sem OOM, mas sem margem alguma para QA residente; eviction WDDM silenciosa é possível e não foi medida. É o primeiro candidato em que a VRAM, não o tempo, é a restrição operacional. Fallback `fp8` fica registrado para entradas maiores ou para liberar VRAM a estimadores.
- **warm ≈ cold (1,04×):** esperado para processo novo por run — os ≈ 16 GB de pesos não cabem no page cache ao lado de um processo com RSS ≈ 9 GB em 16 GB de RAM. A razão warm/cold **não** mede residência de modelo (diferente do klein4b, cujo "warm" tinha o ComfyUI externo residente). Dispersão do frio −18 %/+6 %; do quente ±0,4 %; **nenhum run descartado**.
- **RAM/commit:** `sys_ram_used` 14,4–15,2 GB de 16 GB (saturada); `tree_private` 20,8–24,3 GB > RSS 8,6–9,8 GB (reservas virtuais CUDA/WDDM commitadas); commit do sistema 31,6–35,1 GB → **depende do pagefile** (≈ 26 GB no alvo). ΔRAM vs klein4b ≈ +4,5 GB (o klein4b tinha ComfyUI + browser no baseline; comparação indicativa).
- **O que esta medição não diz:** nada sobre **capacidade em roupa/adição** (NV) nem sobre qualidade/oclusão/preservação de A — isso é G0/E4. A **viabilidade de R1-EI fica fechada** com este registro (D-051).

### 1c. Custo do mecanismo × motor (rev. 2026-10-08, nível `E`/`P`)

| Mecanismo de separação espacial | Fator de custo | Aplicável a | Evidência |
|---|---|---|---|
| máscara de latente / `InpaintModelConditioning(noise_mask)` | ×1,0 | R1, R2, R4 | `P` (core, modelo-agnóstico) |
| `DifferentialDiffusion` (gradiente por pixel) | ×1,0 | R1, R2 | `P` (core; experimental; destilados têm só 4 degraus) |
| LanPaint (`NumSteps`) | ×NumSteps (README: 5 = 5× mais lento); GPL-3.0; **máscara binária obrigatória** (incompatível com R(p) graduado); "degraded performance on distillation models" | só R1 (klein) como ablação secundária, NumSteps 2; **não** em R2 (×5 sobre 10–15 min excede 3 600 s) | `P` |
| Scaffold em pixel + Easy-Insert (klein-base-4B, **15 passos × 2 passes (CFG 4)** = 30 passes; modo "8 GB" = DiffSynth low-VRAM) | ×(30/4) passes vs klein destilado; **medido: 8,55× no frio** (272,5 s vs 31,8 s) | R1-EI (E4) | `P` (código lido: `inference_diffusers.py`) / **`MEDIDO`** (tempo e VRAM, §1e) |
| Insert Anything (Fill+Redux Nunchaku "10 GB") | NC; comparador em 2 casos | — | `P` |
| two-pass (R3 grosseiro → R1 refino) | custo(R3) + custo(R1) | R8 | `E` |
| ControlNet pose/depth | ×1,3–1,5 onde existir | **inexistente** para klein 4B e Edit-2511 | `P` (controlnet.py) |
| Estimador de camadas (SAM 3 + DWPose + SAM 3D Body + MoGe) | custo fixo por solicitação; VRAM do SAM 3D Body **não declarada** | todas | `E` |

Com R2 a 600–900 s por amostra a 0,5 MP (histórico), qualquer fator > 1 estoura 1 500 s/candidato; com klein 4B (segundos por amostra) cabem dezenas de seeds e máscaras. Para R2 no Prototype 0: só máscara + DifferentialDiffusion em 544×960, 1–2 seeds, sob H4.

## 2. Como o ComfyUI 2026 gerencia memória (muda as regras de viabilidade)

| Mecanismo | O que faz | Consequência para 12 GB + 16 GB | Ev. |
|---|---|---|---|
| **DynamicVRAM / comfy-aimdo** | Alocador que reserva espaço de endereços virtual na GPU e **traz pesos sob demanda**; carregamento por **mmap do safetensors** (sem cópia em RAM: "No need to load models fully to RAM"; "working with read-only RAM by design"); TE colocado na GPU (v0.37.0) | Um fp8 de 20 GB **pode** carregar numa máquina de 16 GB sem estourar commit; porém pesos que não cabem são **re-lidos a cada passo** (do page cache ou do disco) → tempo por passo dominado por I/O | `P` |
| **`--fast-disk` auto** (v0.37.0) | Detecta disco rápido e força leitura do arquivo a cada passo em vez de RAM não-pinned | Issue #16415: 50–90 s/it vs 36 s/it; SSD a 100 %. **Testar com e sem** (`--disable-fast-disk`) | `P` |
| **Pinned ≤ 40 % RAM** | Buffer host pinned limitado a ~6.4 GB; eviction se swap > 5 % ou disponível < 512 MB | Offload "rápido" só cobre ~6 GB; o resto vem de páginas não-pinned/disco | `P` |
| **`--cache-ram` padrão** | Cache de resultados com headroom 10 % RAM (mín. 2 GB, máx. 10 GB) | Em 16 GB o cache compete com pesos; avaliar `--cache-none` | `P` |
| **Legado (`--disable-dynamic-vram`)** | Partial loading por estimativa; `MIN_WEIGHT_MEMORY_RATIO = 0.0` em NVIDIA; TE em CPU com `--lowvram` | Único dado em 16 GB RAM (RTX 3060 12 GB, FLUX.1-dev fp8): **10–20 min de swapping antes do sampler** (#12334). Flag será removida | `P` |
| Incompatibilidades | DynamicVRAM × torch.compile/full-graph (SageAttention post4 → `--disable-dynamic-vram`); DynamicVRAM impede `fp8_e4m3fn_fast` (#16551: 1.07 vs 1.72 it/s); GGUF não suportado pelo aimdo no merge (#11845; status atual NV); triton-windows × offload ("Pointer argument cannot be accessed") | Não assumir que offload + quantização + atenção eficiente coexistem; **medir cada combinação** | `P` |
| Regressões abertas | #14618 (3060 12 GB: re-leitura por mudança de prompt, 49–103 s), #14276 (5070 Ti: recarga após troca de dtype, 120–190 s), #15255 (Desktop/Windows: OOM em host-buffer; workaround `--disable-pinned-memory`), Desktop #1741 (3060 12 GB: descarrega tudo a cada run, 155 s/prompt) | Tempo por solicitação pode ser dominado por recarga; o orçamento de 3 600 s deve incluir isso em **frio** | `P` |
| Subprocessos / venvs separados | Sem API oficial no core; Comfy-Org **pyisolate** (JSON-RPC; Linux-first, Windows NV), comunidade **comfy-env** (TCP no Windows; ~2 GB RAM por worker ocioso) | Rotas fora do grafo (FASHN, TEMU-VTOFF, DWPose) rodam como subprocesso com **carga/descarga explícita**; RAM de processos ociosos deve ser zero (encerrar) | `P`/`R` |

## 3. Quantização e precisão disponíveis em Blackwell/Windows

| Formato | Suporte | Modelos relevantes | Notas | Ev. |
|---|---|---|---|---|
| fp8 e4m3fn (scaled) | core; `fp8_matrix_mult` via `--fast` (regressão c/ DynamicVRAM) | klein 4B/9B (oficial), QIE-2511 (Comfy-Org), Kontext, FLUX Fill | menor perda esperada; maior tamanho | `P` |
| **NVFP4 / INT4 SVDQuant (Nunchaku)** v1.2.1 | wheels Windows cu12.8/torch 2.10; FP4 para Blackwell | FLUX.1 dev/Kontext/Fill, Qwen-Image, **QIE-2509** (+Lightning), Z-Image-Turbo; **2511 e FLUX.2: não oficiais** (PR #926 aberto) | "Transformer VRAM to as little as 3 GiB" com offload assíncrono; churn de compatibilidade com ComfyUI | `P` |
| GGUF (ComfyUI-GGUF) | arquiteturas: flux, sd1, sdxl, sd3, hidream, wan, lumina2, **qwen_image**; TEs t5, llama (Mistral), qwen2vl (+mmproj), qwen3, qwen3vl, gemma3; FLUX.2 por pass-through (`I`) | QIE-2511 Q4_0 11.9 / Q4_K_M 13.1 / Q5_0 13.4 / Q8_0 20.3 GB; klein 4B/9B (unsloth) | dequant on-the-fly (troca VRAM por compute); "DiTs seem less affected by quantization" (README); **sem estudo Q4 vs Q8 em edição** | `P`/`R` |
| bf16 | padrão | modelos ≤ 4B | — | `P` |
| Atenção | SDPA padrão; SageAttention 2.2 via KJNodes "Patch Sage Attention" (não usar `--use-sage-attention` em Qwen: saída preta) | QIE 40 passos 14m30→9m30 em 5090 | ganho ~30–35 % (`R`) | `R` |
| Tiled VAE | core (VAEDecodeTiled) | Leffa (OOM no decode em V100 32 GB sem tiling), FitDiT 1152×1536, QIE | pode introduzir descontinuidade de estampa em bordas de tile → ablação | `P`/`I` |

**Política de precisão (contrato §10):** maior fidelidade viável primeiro (bf16 → fp8 → NVFP4/Q5–Q6 → Q4), com comparação **visual pareada** na Fase 5 antes de aceitar quantização agressiva. Q3 fica fora por padrão.

## 4. Orçamento de memória estimado por candidata (nível **ESTIMADO**)

Gerado por `tools/memory_budget.py --config tools/budget_configs.json --markdown` (**modelo de triagem grosseira**; faixa de ativações [0.5×, 4×]; "CLEARLY_FITS" exige banda alta ≤ 70 % do disponível porque o estimador subestima — FitDiT: ~13 GB na banda alta vs 19.5 GB reportados). **NEAR_LIMIT significa medir, nunca descartar.** Hipóteses: bytes/param por formato (fp8 1.0; NVFP4 0.56; Q4_K_M 0.58; Q5_K_M 0.69), 1024² → 4 096 tokens latentes (×4 para 3 referências), CFG batch 2, SDPA, VRAM utilizável 11.2 GB, baseline RAM (SO+ComfyUI) 4.5 GB. **"RAM pico load" vale para o caminho legado com cópia/conversão; com DynamicVRAM/mmap, pesos são páginas file-backed e não entram no commit — a coluna fica pessimista nesse caso.** A estimativa de ativações é de ordem de grandeza e **enviesada para baixo**: FitDiT reporta ~19.5 GB fp16 em 1024×768 (paper) contra ~10 GB central / ~13 GB banda alta aqui — prova de que o estimador **não pode descartar candidatas perto do limite**; só a medição decide.

| Candidata (precisão) | Pesos modelo GB | TE GB | VRAM seq. GB [baixo–central–alto] | VRAM tudo residente GB [baixo–alto] | Triagem VRAM seq. | RAM load legado GB | Triagem RAM (legado) |
|---|---|---|---|---|---|---|---|
| FLUX.2 klein 4B bf16 + Qwen3-4B fp8 | 7.5 | 3.7 | 7.9–8.4–11.2 | 12.0–15.2 | NEAR_LIMIT | 11.7 | NEAR_LIMIT |
| FLUX.2 klein 4B fp8 + Qwen3-4B fp8 | 3.7 | 3.7 | 4.2–4.7–7.5 | 8.2–11.5 | FITS_RESIDENT | 7.8 | CLEARLY_FITS |
| FLUX.2 klein 4B fp8 + 3 refs (tokens x4) | 3.7 | 3.7 | 5.6–7.5–18.7 | 9.6–22.8 | NEAR_LIMIT | 7.8 | CLEARLY_FITS |
| FLUX.2 klein Base 4B bf16 + Easy-Insert LoRA, TE liberado após encode (15 passos × 2 passes CFG 4; 2 imagens de edição; E4; modo normal de tools/r1ei) | 7.5 | 0.0 | 8.9–10.3–18.7 | 9.2–19.0 | NEAR_LIMIT | 7.8 | CLEARLY_FITS |
| FLUX.2 klein Base 4B fp8 (layerwise casting) + Easy-Insert LoRA, TE liberado (E4; modo fp8 de tools/r1ei) | 3.7 | 0.0 | 5.1–6.5–15.0 | 5.4–15.3 | NEAR_LIMIT | 3.9 | CLEARLY_FITS |
| FLUX.2 klein 9B fp8 + Qwen3-8B fp8 | 8.4 | 7.5 | 9.2–10.0–14.9 | 17.0–22.6 | NEAR_LIMIT | 16.6 | CLEARLY_EXCEEDS |
| FLUX.2 klein 9B Q4_K_M + Qwen3-8B Q4_K_M | 4.9 | 4.3 | 5.7–6.5–11.4 | 10.3–16.0 | NEAR_LIMIT | 9.6 | CLEARLY_FITS |
| Qwen-Image-Edit-2511 fp8 + Qwen2.5-VL-7B fp8 | 18.6 | 6.5 | 19.7–20.7–26.9 | 26.5–33.7 | NEEDS_OFFLOAD | 26.4 | CLEARLY_EXCEEDS |
| Qwen-Image-Edit-2511 Q4_K_M + VL-7B Q4_K_M | 10.8 | 3.8 | 11.8–12.9–19.1 | 15.9–23.1 | NEEDS_OFFLOAD | 15.3 | CLEARLY_EXCEEDS |
| Qwen-Image-Edit-2511 Q4_K_M + 3 refs (tokens x4) | 10.8 | 3.8 | 14.9–19.1–43.8 | 19.0–47.9 | NEEDS_OFFLOAD | 15.3 | CLEARLY_EXCEEDS |
| Qwen-Image-Edit-2509 Nunchaku NVFP4 + VL-7B Q4 | 10.4 | 3.8 | 11.5–12.5–18.7 | 15.6–22.8 | NEEDS_OFFLOAD | 14.9 | NEAR_LIMIT |
| Qwen-Image-2.1 fp8 (7B) + Qwen3-VL-8B fp8 [research-only] | 6.5 | 7.5 | 7.5–7.7–11.4 | 14.9–19.2 | NEAR_LIMIT | 14.7 | NEAR_LIMIT |
| FLUX.1 Kontext dev fp8 + T5-XXL fp8 (RefTon/LoRAs) | 11.2 | 4.4 | 12.2–13.2–19.4 | 16.9–24.1 | NEEDS_OFFLOAD | 16.3 | CLEARLY_EXCEEDS |
| FLUX.1 Kontext dev Nunchaku NVFP4 + T5 fp8 | 6.3 | 4.4 | 7.3–8.3–14.5 | 12.0–19.2 | NEAR_LIMIT | 11.2 | CLEARLY_FITS |
| FLUX.1 Fill dev fp8 + LoRA (OmniTry/UniFit/CatVTON-FLUX) + T5 fp8 | 11.2 | 4.4 | 13.2–15.3–27.7 | 17.9–32.4 | NEEDS_OFFLOAD | 16.3 | CLEARLY_EXCEEDS |
| FLUX.2 dev 32B Q4_K_M + Mistral-24B Q4_K_M | 17.3 | 13.0 | 19.1–20.8–31.5 | 32.3–44.8 | NEEDS_OFFLOAD | 31.8 | CLEARLY_EXCEEDS |
| CatVTON SD1.5-inp fp16 (+SCHP+DensePose) | 1.7 | 0.0 | 1.8–1.9–2.5 | 2.1–2.8 | FITS_RESIDENT | 1.8 | CLEARLY_FITS |
| Leffa SD1.5-inp + ref UNet fp16 | 3.4 | 0.0 | 3.5–3.6–4.2 | 3.8–4.5 | FITS_RESIDENT | 3.5 | CLEARLY_FITS |
| FitDiT SD3-M dual DiT fp16 (paper ~19.5 GB sem offload) | 7.5 | 1.9 | 7.8–8.2–10.6 | 10.0–12.8 | NEAR_LIMIT | 9.8 | CLEARLY_FITS |
| FASHN VTON 1.5 pixel-space bf16 (~1B) + DWPose + parser | 1.9 | 0.0 | 2.6–3.4–8.0 | 2.9–8.3 | NEAR_LIMIT | 2.0 | CLEARLY_FITS |
| TEMU-VTOFF SD3-M dual DiT fp16 + Qwen2.5-VL-7B Q4 (legenda) | 7.5 | 3.8 | 7.6–7.8–8.9 | 11.7–13.0 | NEAR_LIMIT | 11.8 | NEAR_LIMIT |
| QA: Qwen3-VL-8B Q4_K_M (juiz local) | 4.3 | 0.0 | 4.7–5.1–7.6 | 5.0–7.9 | FITS_RESIDENT | 4.5 | CLEARLY_FITS |
| Insert Anything: FLUX.1 Fill dev Nunchaku INT4/NVFP4 + Redux + T5 fp8 (comparador NC, '10 GB') | 6.3 | 4.4 | 7.4–8.6–15.5 | 12.1–20.2 | NEAR_LIMIT | 11.2 | CLEARLY_FITS |

Leitura (rótulos de VRAM: `FITS_RESIDENT` = cabe residente com margem; `NEAR_LIMIT` = medir; `NEEDS_OFFLOAD` = roda **só** com offload/streaming via DynamicVRAM, portanto **mais lento, não inviável**):
- **Residentes com folga:** klein 4B fp8 (1 ref), CatVTON, Leffa, juiz Qwen3-VL-8B Q4, componentes de percepção.
- **Perto do limite (medir):** klein 4B com 3 referências (tokens ×4 — a atenção cresce), klein 9B Q4 + TE Q4, Kontext NVFP4, Qwen-Image-2.1 fp8, FitDiT, FASHN 1.5 (pixel-space em 576×864: a banda alta reflete incerteza sobre ativações em espaço de pixel), TEMU-VTOFF.
- **Só com offload/streaming:** QIE-2511 Q4/Q5 (+TE), QIE-2509 NVFP4, Kontext/Fill fp8, klein 9B fp8. **A evidência histórica (§1b) confirma que QIE-2511 Q5 roda assim na RTX 5070**: ~10–15 min/imagem a ~0.5 MP, o que a coloca perto/acima do teto de 1 500 s por candidato a 1 MP com QA. O veredito para essas rotas é de **tempo**, não de memória.
- **Inviáveis (por evidência `P`, re-verificada em `research_raw/07`):** FLUX.2 dev (piso oficial ~18 GB só com encoder remoto; 12 GB apenas em relatos com 70–96 GB RAM), Step1X-Edit (18 GB mínimo), IDM-VTON (≥16 GB no nó ComfyUI), Hunyuan 3.0, Emu3.5. HiDream-E1: **inferência** (sem requisito declarado). OmniGen2 e BAGEL: **não** inviáveis (offload/NF4 documentados) → marginais.

Lição registrada (D-016): "excede VRAM residente" foi lido na primeira versão deste documento como quase-inviabilidade; a observação histórica mostra que é uma questão de tempo por passo. O estimador agora separa os dois conceitos.

Calibração com medições (2026-10-08): klein 4B fp8 A+B — estimado 4,2–7,5 GB (seq.) / 8,2–11,5 GB (residente), **medido 11,6 GB** (ComfyUI residente; §1d); klein-base-4B bf16 + Easy-Insert — estimado 8,9–18,7 GB (seq.), **medido 12,1–12,2 GB** (§1e). Em ambos o valor medido ficou na metade superior ou acima da banda: o estimador continua **enviesado para baixo** e só serve para triagem.

## 5. Elegibilidade provisória por candidata (consolida §2–§4; **tudo PENDENTE de medição**)

| Candidata | Elegibilidade | Justificativa | O que a medição deve confirmar |
|---|---|---|---|
| FLUX.2 klein 4B (Apache) | **ELEGÍVEL** | "~8 GB" (`P`); fp8 4 GB + TE 4 GB; 4 passos | tempo frio (load) e quente por imagem com 2–3 refs @1024; qualidade vs 9B |
| FLUX.2 klein 9B / 9B-KV (NC) | ELEGÍVEL-MARGINAL | fp8 9 GB + TE 8 GB > VRAM → offload; rodou em 4 GB/15.7 GB RAM (`P`) | s/it com offload no Windows; 9B-KV OOM relatado em edição |
| Qwen-Image-Edit-2511 (Apache) | **MARGINAL** | Q4 ≥ 11.9 GB + TE; 16 GB RAM sem relato; 32 GB RAM saturou com 4 refs @2K | s/it em Q4_K_M + TE Q4 com DynamicVRAM; pico de commit; se > ~20 min/imagem (frio) a rota não cabe em 3 candidatos + QA |
| Qwen-Image-Edit-2509 + Nunchaku NVFP4 (Apache) | MARGINAL | 12.7 GB arquivo (`R`) → offload por camada obrigatório; Lightning 4/8 passos | idem; comparar qualidade NVFP4 vs Q5 GGUF |
| Qwen-Image-2.1 (NC pesquisa) | ELEGÍVEL (só comparação) | 4070 12 GB: edit 16–20 s (`R`) | — (inelegível por licença fora de pesquisa) |
| FLUX.1 Kontext dev + RefTon / LoRAs (NC) | ELEGÍVEL | Nunchaku NVFP4 ~6.8 GB (`P-ex`) | RefTon LoRA sobre Nunchaku: compatibilidade NV |
| CatVTON (NC) | ELEGÍVEL | <8 GB (`P`) | DensePose/SCHP no Windows (detectron2) |
| Leffa (MIT/OpenRAIL) | ELEGÍVEL | SD1.5 + ref UNet | issue Windows #40 (autocast); decode em tiles |
| FitDiT (NC) | MARGINAL | 19.5 GB fp16; offload "<6 GB" (`P-ex`) mas 8 GB falhou (issue) | medir `--aggressive_offload` em 12 GB |
| FASHN VTON 1.5 (Apache) | **ELEGÍVEL** | ~8 GB (`R`), ~1B, sem VAE | subprocesso Windows; licença dos pesos (card NV) |
| TEMU-VTOFF (NC) / TryOffDiff (SSPL) | ELEGÍVEL (pré-etapa) | SD3-M dual DiT sequencial ~8 GB (`E`) | tempo adicional; SD3-M gated |
| OmniTry / UniFit (FLUX Fill NC) | MARGINAL | ≥28 GB bf16 → fp8/GGUF 12 GB + offload | VRAM real com LoRA em fp8 |
| OmniVTON++ (NC) | PENDENTE | pré-processamento pesado (DensePose, TAPPS, pseudo-pessoa) | custo total; Windows |
| Percepção (SAM 3, SAM 2, BiRefNet, DWPose, SegFormer, MoGe, DINOv2) | ELEGÍVEL | ≤ 4 GB cada (`P`/`R`); nativos no core (SAM 3, SAM 3D Body, MoGe) | SAM 3D Body: ~17 GB fp32 anedótico → usar bf16/int8 |
| QA: Qwen3-VL-8B Q4 (Apache) | ELEGÍVEL | ~6–12 GB (`C`) → carregar **após** descarregar o gerador | tempo de julgamento por imagem |
| FLUX.2 dev (piso oficial ~18 GB **com encoder remoto** → rede, proibido), Step1X-Edit (18 GB mínimo, P), IDM-VTON (nó ComfyUI "**at least 16GB**", P — a citação anterior ">18 GB em #43" estava errada), HiDream-E1 (sem requisito declarado; ≥24 GB só relato), Hunyuan 3.0, Emu3.5, WSL2 | **INVIÁVEL** | `research_raw/07` cluster descartados; WSL2: VM 8 GB padrão, sem DynamicVRAM | — |
| OmniGen2 (offload documentado ~8,5 GB / sequential <3 GB; 1024² >10 min em 3060 relatado), BAGEL (NF4 recomendado para 12–32 GB; sem multi-imagem documentada) | **MARGINAL — descarte anterior revertido** (rev. 2026-10-08) | fonte primária contradiz "inviável"; RAM 16 GB e tempo seguem riscos | medir em frio; 2.ª onda |

## 6. Windows: pagefile, commit, fallback

- **Commit charge** governa: alocações falham quando commit > RAM + pagefile (erro 1455) mesmo com RAM livre. Páginas mmap read-only são file-backed (não contam) — isso é o que torna o DynamicVRAM viável em 16 GB (`I`); buffers pinned contam (cap 6.4 GB).
- **Pagefile:** não recomendar tamanho arbitrário. Procedimento: medir o commit charge **real** durante a execução (§8) — `measure_run.py` grava em cada amostra `sys.commit.total_mb` (= `Committed Bytes`, CommitTotal × PageSize) e `sys.commit.limit_mb` (= `Commit Limit`) via `psapi.GetPerformanceInfo`, com `source: "GetPerformanceInfo"`, e o pico em `peak.commit_total_mb` — e dimensionar pagefile = pico de commit observado + 25 %, em SSD com espaço livre. Fora do Windows, ou se a chamada falhar, o script grava apenas um **proxy** (`ram_used + swap_used`, `source: "proxy_ram_used_plus_swap"`, campo `sys.commit.commit_proxy_mb` em cada amostra (não existe proxy no topo nem em `peak`; `peak.commit_source` fica `proxy_ram_used_plus_swap`), `commit_measurement.is_real_commit_counter = false`): isso **não** é commit e não serve para dimensionar pagefile; relatos comunitários para FLUX apontam picos de 30–48 GB em máquinas de 16 GB no **caminho legado**. Thrashing de horas não é viabilidade.
- **WSL2:** VM com 8 GB padrão (min(50 %, 8 GB) no Win11); DynamicVRAM "WSL não planejado" → **descartado**.
- **CUDA Sysmem Fallback Policy:** "Prefer No Sysmem Fallback" troca lentidão silenciosa por OOM explícito; comfy-aimdo "behaves a lot better on Windows systems with System Memory fallback". Testar ambos; registrar.
- **HAGS:** efeito pequeno relatado; testar.

## 7. Tempo: divisões de orçamento (não estimativas de desempenho)

Com 3 600 s totais e QA/exportação reservados (~300 s: SAM 3 + DWPose + DINOv2 + juiz VLM + pixel-check, `E`), restam ~3 300 s para carregamento + candidatos + refinamento. Exemplos de divisão (apenas aritmética):

| Divisão | Load frio | Candidatos | Refinamento | Sobra |
|---|---|---|---|---|
| 1 forte | 600 | 1 × 1 500 | 600 | 600 |
| 3 previews + 1 refino | 600 | 3 × 480 | 1 500 | −240 → **não cabe** |
| 2 candidatos + refino | 600 | 2 × 900 | 600 | 600 |

O que decide qual divisão é possível é o tempo medido por passo com os pesos reais no DynamicVRAM; nenhuma rota entra na seleção final sem `measure_run.py` em estado **frio**.

## 7b. Distribuição nula por rota (pré-requisito de qualquer veredito sobre `O′`; `06` F-33)

Para cada rota e resolução interna: (a) `O_null1` = `A` após encode/decode do VAE da rota (denoise 0) e reprojeção ao canvas; (b) `O_null2` = pipeline completo em `same_garment_noop`. Medir |O_null − A| por zona (pele, fundo, oclusores) e publicar em `runs/proto0/null/`. τ_null = p99,5; limiares de identidade = (1 − fração acima de τ_null na nula) − margem; ΔE mínimo em BAND_MIN = p95 do no-op. O auditor compara `O′` com `VAE(A)` via `--a-ref` (isola a edição do piso do VAE) e `O` composto com `A`. Também imprimir, por motor/sampler/passos, os limiares do DifferentialDiffusion `(ts − ts_to)/(ts_from − ts_to)` para mapear R(p) → passo de liberação (em 4 passos há só 4 instantes).

## 8. Procedimento de medição reproduzível no alvo (a executar pelo operador)

1. **Inventário:** `powershell -ExecutionPolicy Bypass -File tools/inventory_windows.ps1` → `inventory_*.json` (RAM real, pagefile, discos, driver, torch/CUDA do ComfyUI Desktop, processos residentes). Anexar a todo relatório.
2. **Baseline:** com ComfyUI Desktop aberto e ocioso, registrar VRAM/RAM/commit real (`baseline.sys.commit.total_mb`/`limit_mb`, fonte `GetPerformanceInfo`; o script faz o baseline antes de executar).
3. **Por candidata**, estado **frio** (pesos em disco, nenhum modelo residente; reiniciar o ComfyUI entre medições):
   `python tools/measure_run.py --label <rota>_<precisao>_cold --state cold --budget-s 3600 --out runs -- <comando que executa 1 imagem A+B a 1024 e grava PNG>`
   Repetir em **quente** (`--state warm`). Registrar `--note` com flags do ComfyUI (`--disable-fast-disk`, `--cache-none`, `--disable-pinned-memory`, `--reserve-vram`).
4. **Métricas a extrair do JSON:** `wall_s`, `peak.vram_used_mb`, `peak.commit_total_mb` (commit charge real do sistema = `Committed Bytes` via `GetPerformanceInfo`; só vale se `commit_measurement.is_real_commit_counter = true` — com `source = proxy_ram_used_plus_swap` o número é RAM usada + swap usada, **não** commit), `peak.tree_private_mb` (private bytes da árvore de processos = commit do processo **no Windows**; em Linux é USS — conferir `peak.tree_private_source`), `peak.sys_ram_used_mb`, `peak.swap_used_mb`, taxa de page faults; e dos logs do ComfyUI (`--verbose DEBUG`): "loaded completely/partially", "prepared for dynamic VRAM loading … MB Staged", "Prompt executed in X seconds".
5. **Combinações a testar explicitamente:** DynamicVRAM on/off; `--fast-disk` on/off; pinned on/off; SageAttention on/off; fp8 vs NVFP4 vs Q4/Q5; tiled VAE on/off; 1 vs 3 referências; 1024 vs 1536.
6. **Critério de elegibilidade final:** rota cabe se **frio** ≤ 1 500 s para 1 candidato @1024 com QA (deixa espaço para 2 candidatos ou refino) e sem OOM; "marginal" se 1 500–3 000 s; inviável acima ou com OOM/thrashing (swap_used crescente + page-fault rate alta por > 5 min).
7. **Repetições:** n ≥ 3 por configuração para mediana; n ≥ 10 antes de reportar percentis.

## 9. O que esta fase **não** sabe (honestamente)

- Tempo medido só para **R1 klein 4B** (§1d) e **R1-EI** (§1e); nenhuma medição ainda de R3, R2, R4 em 12 GB + 16 GB RAM. Para R1-EI não se sabe se a folga de ≈ 40 MiB de VRAM sobrevive a máscaras maiores/outras A (eviction WDDM não medida).
- Qual stack torch/CUDA o Comfy-Desktop 1.1.6 instala numa 5070 (cu128 vs cu130) e se SageAttention/Nunchaku wheels casam com ele.
- Perda de qualidade de Q4/NVFP4 em **topologia e microdetalhe** de roupa (nenhum estudo).
- Se GGUF já é suportado pelo aimdo (era "unsupported at merge").
- Custo real de subprocessos Windows (FASHN, TEMU-VTOFF) e se `pyisolate` funciona no Windows.
