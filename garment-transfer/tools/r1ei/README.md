# R1-EI — FLUX.2-klein-base-4B + Easy-Insert: preparação da medição de viabilidade

Estado: **preparado, não executado** (2026-10-08). Nada aqui mede qualidade; isso é o Prototype 0 / G0, que vem depois.

## 1. O que é "Easy-Insert" (identidade verificada em fonte primária)

| Campo | Valor | Fonte |
|---|---|---|
| Repositório | `huan-yin/Easy-Insert` — commit `82094484f432b74efb6c4ccbf144c08350f02144` (2026-08-16; 2 commits no total) | clone + `git log` |
| O que é | **LoRA** para `black-forest-labs/FLUX.2-klein-base-4B` que faz **inserção de objeto por referência**: background com região mascarada (buraco branco) + referência com o objeto mascarado → objeto inserido no buraco | README |
| Paper | **nenhum** (release de modelo com código de inferência; sem artigo, sem relatório) | README, model card, Space |
| Licença | Apache-2.0 (LICENSE do repo; model card do LoRA `apache-2.0`) | arquivos lidos |
| Pesos (Diffusers) | `LiXiY/Easy-Insert` @ `dd71e3f8…` → `easy-insert-diffusers.safetensors` (96 365 440 bytes, sha256 `6826ffcc…`) | HF API |
| Pesos (DiffSynth) | `HuanJue/Easy-Insert` (ModelScope) → `easy-insert.safetensors`; **o mesmo id não existe publicamente no Hugging Face** (API/raw: inválido) | HF API; README badges |
| Base | `black-forest-labs/FLUX.2-klein-base-4B` @ `a3b4f484…`, **não gated**, Apache-2.0; transformer 7,75 GB bf16 + Qwen3-4B 8,04 GB bf16 + VAE 0,17 GB | HF API + configs |
| Integração | é um **LoRA PEFT sobre o transformer**; as 4 entradas (background, insert mask, reference, reference mask) viram **duas imagens** de edição (`image=[background_mascarado, referência_sobre_branco]`) do `Flux2KleinPipeline` (multi-referência nativa do klein) + **prompt fixo**; o mecanismo é o "scaffold em pixel" do braço E4 | `inference_diffusers.py`, `utils.py` |
| Hiperparâmetros upstream | crop quadrado 1,2× a bbox da máscara → 1024²; 15 passos; CFG 4,0 (klein-**base** não é destilado → CFG real, 2 passes/passo); seed 1; paste-back sem feather | `inference_diffusers.py`, `utils.py` |
| Compatível com klein-base? | **Sim** — o nome usado no projeto estava correto. Precisão necessária: o backend "oficial" da demo do autor é **Diffusers** com o LoRA `LiXiY/Easy-Insert`; o backend DiffSynth usa o LoRA do ModelScope. | Space `LiXiY/Easy-Insert` (`app.py`) |

Correções ao que o projeto dizia antes: (a) "8 GB" refere-se ao **modo low-VRAM do DiffSynth** (offload em disco, pesos float8 em CPU, computação bf16), não ao pipeline em geral; (b) o LoRA do Hugging Face é em formato **diffusers**, o do ModelScope em formato DiffSynth — não são intercambiáveis sem conversão; (c) nenhum paper.

## 2. Variante operacional escolhida para RTX 5070 12 GB / 16 GB RAM

**Backend Diffusers (0.39.0) com carregamento sequencial bf16** (`run_easy_insert.py --mode normal`):

1. Qwen3-4B bf16 (8,0 GB) → GPU → embeddings do prompt fixo e do negativo `""` → CPU → liberado.
2. Transformer bf16 (7,75 GB) + LoRA (0,1 GB) + VAE (0,17 GB) → GPU; 15 passos × 2 passes; latentes.
3. Transformer → CPU; VAE decodifica; paste-back.

Por que esta e não as outras:

| Variante | VRAM pico (estimado) | RAM pico (estimado) | Numéricos | Veredito |
|---|---|---|---|---|
| upstream `pipe.to("cuda")` (tudo bf16 residente) | ≈ 15–16 GB | ≈ 8 GB | bf16 | **não cabe** em 12 GB |
| `enable_model_cpu_offload()` (diffusers) | ≈ 9–10 GB | **≈ 16–17 GB** (os 3 modelos em RAM) | bf16 | thrashing em 16 GB RAM — rejeitada |
| **sequencial bf16 (escolhida)** | ≈ 9–10,5 GB (TE sozinho 8 GB; DiT 7,75 + ativações 12 288 tokens; decode com DiT fora) | ≈ 8–9 GB (um componente por vez) | **bf16 = upstream** | cabe; fidelidade máxima |
| `fp8` (layerwise casting do transformer) | ≈ 6 GB | ≈ 8 GB | pesos fp8, computação bf16 | só se o normal estourar |
| DiffSynth low-VRAM (upstream "8 GB") | ≈ 5–8 GB | ≈ 4–8 GB | fp8 em CPU / bf16 compute | exige LoRA do ModelScope (NV daqui); mais lento (streaming) |

Prioridade do operador (qualidade > velocidade, sem configurações que não cabem) → bf16 sequencial. A estimativa de VRAM é `ESTIMADO`; a medição decide.

## 3. Protocolo comparativo com `klein4b_fp8_2ref_1mp` e diferenças inevitáveis

Preservado: mesmas A e B; mesmo objetivo; ~1 MP (crop 1024² = 1,05 MP); `tools/measure_run.py` com `GetPerformanceInfo`; cold n=3 e warm n=3; wall, VRAM, RAM, swap, commit, deadline 3 600 s, exit code; proveniência completa (sidecar JSON com sha256 de entradas, pins, versões, GPU).

Diferenças registradas (não escondidas):

| Diferença | klein4b | R1-EI | Consequência |
|---|---|---|---|
| Processo | ComfyUI externo (`tree_private` ≠ motor) | processo próprio (venv R1-EI) | `tree_private_mb` agora **é** o motor; VRAM/commit continuam comparáveis (sistema) |
| Passos | 4 (destilado, sem CFG) | 15 × 2 passes (CFG 4) = 30 passes | tempo esperado maior por construção |
| Precisão | fp8 | bf16 (modo normal) | fidelidade ao upstream; mais VRAM |
| Entradas | A + B | A + B + **2 máscaras** (não existiam no klein4b) | máscaras grosseiras (bbox) só para viabilidade; a forma não muda o custo |
| Região | A inteira ~1 MP | crop 1024² em torno da máscara, colado de volta | saída na grade de A, mas só o crop é gerado |
| Cold | ComfyUI reiniciado | processo novo; page cache do SO só esvaziado com RAMMap (`-RamMap`), senão rotular `cold_pagecache_unflushed` | registrado no `--note` |

## 4. Arquivos

| Arquivo | Papel |
|---|---|
| `r1ei_manifest.json` | pins: commit do Easy-Insert, revisões HF, sha256/tamanhos de todos os arquivos, defaults upstream, protocolo |
| `vendor/easy_insert_utils.py` | `utils.py` do upstream **byte-idêntico** (sha conferido em runtime) + `NOTICE.md` + licença |
| `run_easy_insert.py` | runner (Diffusers, sequencial bf16; `--mode fp8|offload`; `--dry-run`; sidecar JSON; 100 % offline) |
| `make_masks.py` | máscaras grosseiras (bbox) para a viabilidade |
| `requirements-r1ei.txt` | pins de dependências (torch vem do índice CUDA) |
| `setup_r1ei.ps1` | venv, torch CUDA (casa com o ComfyUI), deps, clone pinado, download HF pinado, sha256, dry-run — **não roda o benchmark** |
| `bench_r1ei.ps1` | cold×3 / warm×3 com `measure_run.py` — rodar **só depois** do setup revisado |
| `tests/test_r1ei_static.py` | testes CPU: sha do vendor, máscaras, dry-run, paste-back |

## 5. Critério de elegibilidade (o mesmo do `03` §8 item 6)

Frio mediano ≤ 1 500 s a 1024² sem OOM → elegível; 1 500–3 000 s marginal; acima ou OOM/thrashing → inviável. Se o modo `normal` estourar VRAM, repetir com `--mode fp8` e **registrar** a mudança de precisão; a qualidade (criação da peça, oclusão, preservação de A) só é julgada em G0 com as máscaras congeladas.
