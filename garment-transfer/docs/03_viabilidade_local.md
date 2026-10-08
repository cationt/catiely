# Fase 3 — Viabilidade local: RTX 5070 12 GB · ~16 GB RAM · Windows 11 · ComfyUI Desktop

**Data:** 2026-10-07. **Status global: PENDENTE DE MEDIÇÃO NO HARDWARE-ALVO.** Esta sessão rodou em contêiner Linux sem GPU; **nenhum número abaixo é "MEDIDO NO HARDWARE-ALVO"**. O que existe é: fatos de código/documentação (`P`), relatos de usuários em hardware parecido (`R`), estimativas com hipóteses explícitas (`E`) e inferências (`I`). O procedimento de medição reproduzível está em §8 e nos scripts de `tools/`.

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

Gerado por `tools/memory_budget.py --config tools/budget_configs.json`. Hipóteses: bytes/param por formato (fp8 1.0; NVFP4 0.56; Q4_K_M 0.58; Q5_K_M 0.69), 1024² → 4 096 tokens latentes (×4 para 3 referências), CFG batch 2, SDPA, VRAM utilizável 11.2 GB, baseline RAM (SO+ComfyUI) 4.5 GB. **"RAM pico load" vale para o caminho legado com cópia/conversão; com DynamicVRAM/mmap, pesos são páginas file-backed e não entram no commit — a coluna fica pessimista nesse caso.** A estimativa de ativações é de ordem de grandeza: FitDiT, por exemplo, reporta ~19.5 GB fp16 em 1024×768 (paper) contra 10.2 GB estimados aqui — prova de que o estimador **não substitui medição**.

| Candidata (precisão) | Pesos modelo | TE | VRAM tudo residente | VRAM sequencial | RAM pico load | RAM offload total | Cabe VRAM seq.? | Cabe RAM load? |
|---|---|---|---|---|---|---|---|---|
| FLUX.2 klein 4B bf16 + Qwen3-4B fp8 | 7.5 | 3.7 | 12.1 | 8.1 | 11.7 | 15.7 | sim | NÃO |
| FLUX.2 klein 4B fp8 + Qwen3-4B fp8 | 3.7 | 3.7 | 8.4 | 4.4 | 7.8 | 12.0 | sim | sim |
| FLUX.2 klein 4B fp8 + 3 refs (tokens x4) | 3.7 | 3.7 | 10.4 | 6.4 | 7.8 | 12.0 | sim | sim |
| FLUX.2 klein 9B fp8 + Qwen3-8B fp8 | 8.4 | 7.5 | 17.0 | 9.3 | 16.6 | 20.3 | sim | NÃO |
| FLUX.2 klein 9B Q4_K_M + Qwen3-8B Q4_K_M | 4.9 | 4.3 | 10.4 | 5.7 | 9.6 | 13.7 | sim | sim |
| Qwen-Image-Edit-2511 fp8 + Qwen2.5-VL-7B fp8 | 18.6 | 6.5 | 26.1 | 19.3 | 26.4 | 29.6 | NÃO | NÃO |
| Qwen-Image-Edit-2511 Q4_K_M + VL-7B Q4_K_M | 10.8 | 3.8 | 15.6 | 11.5 | 15.3 | 19.1 | NÃO | NÃO |
| Qwen-Image-Edit-2511 Q4_K_M + 3 refs (tokens x4) | 10.8 | 3.8 | 17.5 | 13.4 | 15.3 | 19.1 | NÃO | NÃO |
| Qwen-Image-Edit-2509 Nunchaku NVFP4 + VL-7B Q4 | 10.4 | 3.8 | 15.2 | 11.1 | 14.9 | 18.7 | sim | NÃO |
| Qwen-Image-2.1 fp8 (7B) + Qwen3-VL-8B fp8 [research-only] | 6.5 | 7.5 | 14.9 | 7.5 | 14.7 | 18.5 | sim | NÃO |
| FLUX.1 Kontext dev fp8 + T5-XXL fp8 (RefTon/LoRAs) | 11.2 | 4.4 | 16.5 | 11.8 | 16.3 | 20.1 | NÃO | NÃO |
| FLUX.1 Kontext dev Nunchaku NVFP4 + T5 fp8 | 6.3 | 4.4 | 11.6 | 6.9 | 11.2 | 15.1 | sim | sim |
| FLUX.1 Fill dev fp8 + LoRA (OmniTry/UniFit/CatVTON-FLUX) + T5 fp8 | 11.2 | 4.4 | 17.2 | 12.5 | 16.3 | 20.1 | NÃO | NÃO |
| FLUX.2 dev 32B Q4_K_M + Mistral-24B Q4_K_M | 17.3 | 13.0 | 31.9 | 18.6 | 31.8 | 34.7 | NÃO | NÃO |
| CatVTON SD1.5-inp fp16 (+SCHP+DensePose) | 1.7 | 0.0 | 2.2 | 1.9 | 1.8 | 6.2 | sim | sim |
| Leffa SD1.5-inp + ref UNet fp16 | 3.4 | 0.0 | 3.9 | 3.6 | 3.5 | 7.9 | sim | sim |
| FitDiT SD3-M dual DiT fp16 (paper ~19.5 GB sem offload) | 7.5 | 1.9 | 10.2 | 8.0 | 9.8 | 13.8 | sim | sim |
| FASHN VTON 1.5 pixel-space bf16 (~1B) + DWPose + parser | 1.9 | 0.0 | 3.2 | 2.9 | 2.0 | 6.4 | sim | sim |
| TEMU-VTOFF SD3-M dual DiT fp16 + Qwen2.5-VL-7B Q4 (legenda) | 7.5 | 3.8 | 11.8 | 7.7 | 11.8 | 15.7 | sim | NÃO |
| QA: Qwen3-VL-8B Q4_K_M (juiz local) | 4.3 | 0.0 | 5.1 | 4.8 | 4.5 | 8.8 | sim | sim |

Leitura:
- **Cabem com folga (VRAM e RAM):** klein 4B fp8, CatVTON, Leffa, FASHN 1.5, TEMU-VTOFF (sequencial), juiz Qwen3-VL-8B Q4, componentes de percepção.
- **Cabem só com offload/sequencial:** klein 9B (fp8 ou Q4 + TE Q4), Kontext/Fill fp8 (ou NVFP4 sem offload), FitDiT (offload), Qwen-Image-2.1 fp8.
- **Marginais (excedem VRAM utilizável mesmo em Q4 e dependem de DynamicVRAM re-lendo pesos a cada passo):** QIE-2511 Q4 (10.8 GB pesos + ativações + TE), QIE-2509 NVFP4 (10.4 GB; TE separado). Com 3 referências, tokens ×4 → ativações crescem; **o tempo por passo será dominado por I/O** e é o que precisa ser medido primeiro.
- **Inviáveis:** FLUX.2 dev (17 GB Q4 + TE 13 GB), Step1X-Edit (18 GB mínimo), IDM-VTON (≥16–18 GB), HiDream-E1 (≥24 GB relatado), Hunyuan 3.0, Emu3.5.

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
| FLUX.2 dev, Step1X-Edit, HiDream-E1, IDM-VTON, Hunyuan 3.0, Emu3.5, WSL2 | **INVIÁVEL** | §4; WSL2: VM 8 GB padrão, sem DynamicVRAM | — |

## 6. Windows: pagefile, commit, fallback

- **Commit charge** governa: alocações falham quando commit > RAM + pagefile (erro 1455) mesmo com RAM livre. Páginas mmap read-only são file-backed (não contam) — isso é o que torna o DynamicVRAM viável em 16 GB (`I`); buffers pinned contam (cap 6.4 GB).
- **Pagefile:** não recomendar tamanho arbitrário. Procedimento: medir `Committed Bytes`/`Commit Limit` durante a execução (§8), e dimensionar pagefile = pico de commit observado + 25 %, em SSD com espaço livre; relatos comunitários para FLUX apontam picos de 30–48 GB em máquinas de 16 GB no **caminho legado**. Thrashing de horas não é viabilidade.
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

## 8. Procedimento de medição reproduzível no alvo (a executar pelo operador)

1. **Inventário:** `powershell -ExecutionPolicy Bypass -File tools/inventory_windows.ps1` → `inventory_*.json` (RAM real, pagefile, discos, driver, torch/CUDA do ComfyUI Desktop, processos residentes). Anexar a todo relatório.
2. **Baseline:** com ComfyUI Desktop aberto e ocioso, registrar VRAM/RAM/commit (o script faz o baseline antes de executar).
3. **Por candidata**, estado **frio** (pesos em disco, nenhum modelo residente; reiniciar o ComfyUI entre medições):
   `python tools/measure_run.py --label <rota>_<precisao>_cold --state cold --budget-s 3600 --out runs -- <comando que executa 1 imagem A+B a 1024 e grava PNG>`
   Repetir em **quente** (`--state warm`). Registrar `--note` com flags do ComfyUI (`--disable-fast-disk`, `--cache-none`, `--disable-pinned-memory`, `--reserve-vram`).
4. **Métricas a extrair do JSON:** `wall_s`, `peak.vram_used_mb`, `peak.tree_private_mb` (commit do processo), `peak.sys_ram_used_mb`, `peak.swap_used_mb`, taxa de page faults; e dos logs do ComfyUI (`--verbose DEBUG`): "loaded completely/partially", "prepared for dynamic VRAM loading … MB Staged", "Prompt executed in X seconds".
5. **Combinações a testar explicitamente:** DynamicVRAM on/off; `--fast-disk` on/off; pinned on/off; SageAttention on/off; fp8 vs NVFP4 vs Q4/Q5; tiled VAE on/off; 1 vs 3 referências; 1024 vs 1536.
6. **Critério de elegibilidade final:** rota cabe se **frio** ≤ 1 500 s para 1 candidato @1024 com QA (deixa espaço para 2 candidatos ou refino) e sem OOM; "marginal" se 1 500–3 000 s; inviável acima ou com OOM/thrashing (swap_used crescente + page-fault rate alta por > 5 min).
7. **Repetições:** n ≥ 3 por configuração para mediana; n ≥ 10 antes de reportar percentis.

## 9. O que esta fase **não** sabe (honestamente)

- Nenhum tempo medido de **nenhuma** rota em 12 GB + 16 GB RAM com ComfyUI ≥ 0.37 (DynamicVRAM + fast-disk auto).
- Qual stack torch/CUDA o Comfy-Desktop 1.1.6 instala numa 5070 (cu128 vs cu130) e se SageAttention/Nunchaku wheels casam com ele.
- Perda de qualidade de Q4/NVFP4 em **topologia e microdetalhe** de roupa (nenhum estudo).
- Se GGUF já é suportado pelo aimdo (era "unsupported at merge").
- Custo real de subprocessos Windows (FASHN, TEMU-VTOFF) e se `pyisolate` funciona no Windows.
