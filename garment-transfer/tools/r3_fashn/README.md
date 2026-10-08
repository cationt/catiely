# R3 — FASHN VTON v1.5: preparação da medição de viabilidade (dois modos)

Estado: **preparada, não medida** (2026-10-08). Nada aqui mede qualidade; isso é o Prototype 0 / G0. Verificação em fonte primária em `research_raw/09_fashn_vton_verificacao.md`; pins em `r3_manifest.json`.

## 1. O que é (identidade verificada)

| Campo | Valor |
|---|---|
| Código | `fashn-AI/fashn-vton-1.5` @ **`7c0f10af3f91ad4048fe9729c470a13ef905d25a`** (HEAD de `main` em 2026-10-08; confirmado por `git ls-remote`; sem tags). Apache-2.0. Pacote `fashn-vton 1.5.0`, **não publicado no PyPI** → instalado do clone pinado. Sem paper. |
| Pesos do try-on | HF `fashn-ai/fashn-vton-1.5` @ `77206831…` → `model.safetensors` 1 943 668 048 B, sha256 `d6cd3828…` (apache-2.0). MMDiT 972 M, bf16, canvas **576×864**. |
| Pose | DWPose ONNX (HF `fashn-ai/DWPose` @ `548b5df2…`): `yolox_l.onnx` 216,7 MB `7860ae79…`, `dw-ll_ucoco_384.onnx` 134,4 MB `724f4ff2…` (Apache-2.0; redistribuição). Executado em `onnxruntime` com `CUDAExecutionProvider`. |
| Parser humano | `fashn-human-parser==0.1.1` (PyPI; byte-idêntico ao GitHub `f2771f2`) + pesos HF `fashn-ai/fashn-human-parser` @ `1f80c34d…` (SegFormer-B4 fine-tuned, 18 classes, 256,1 MB `e43c8c8a…`). **Licença separada: herda a NVIDIA Source Code License do SegFormer (não comercial)** — o pipeline oficial **não** é "100 % Apache"; status S-01 do projeto mantido. |
| Defaults oficiais | `num_samples=1`, `num_timesteps=30`, `guidance_scale=1.5`, `skip_cfg_last_n_steps=1`, `seed=42`, `segmentation_free=True`, `garment_photo_type="model"` (confirmados em `pipeline.py` e `examples/basic_inference.py`). Baseline **preservado**; nada é "otimizado" antes da medição. |

## 2. Os dois modos (nomenclatura correta)

| Modo | Flag do runner | O que acontece no pipeline oficial |
|---|---|---|
| **segfree** | `--segmentation-free` | `FashnHumanParser` **inicializado e executado** em A e em B; `create_clothing_agnostic_image(..., disable_masking=True)` devolve A inteira (sem máscara); a peça de B continua **recortada pelo parser** quando `garment_photo_type=model`. **Não** chamar de "parser-free". |
| **masked** | `--masked` | mesmo parser; máscara da pessoa (labels da categoria + arms/torso ou legs, buffer/bounded/contour/hybrid, dilatação, exclui face/hair/jewelry/bag/glasses/hat e mãos/pés conforme cobertura) → cinza 127. |

Custo: os modos diferem só na criação da máscara em **CPU** (ms); a GPU faz o mesmo trabalho. Medir ambos registra a viabilidade das duas configurações que o G0 vai usar — não é uma comparação de desempenho.

## 3. Protocolo (igual ao klein4b/R1-EI) e diferenças inevitáveis

Preservado: **mesmas A e B**; `tools/measure_run.py` (commit real via `GetPerformanceInfo`), `--budget-s 3600 --interval-s 0.5`; **cold×3 + warm×3 por modo = 12 runs**; processo novo por run; wall/VRAM/RAM/swap/commit/exit; sidecar com proveniência completa.

| Diferença | klein4b / R1-EI | R3 | Consequência |
|---|---|---|---|
| Resolução | ~1 MP (klein) / crop 1024² (R1-EI) | canvas **fixo 576×864** (checkpoint); A pré-redimensionada para caber em 864 sem upsampling; saída = tamanho de A pré-redimensionada | **não comparável em MP**; sidecar grava tamanhos originais, pré-redimensionados, canvas e saída |
| Entradas | A + B (+ 2 máscaras na R1-EI) | A + B + **categoria** + `garment_photo_type` declarados pelo operador | `inputs_decision.json` (setup); nada é inferido automaticamente |
| Componentes | 1 motor | motor + DWPose (ONNX/CUDA EP) + SegFormer | fases separadas no sidecar; providers efetivos registrados |
| Cold | processo novo; page cache não esvaziado salvo RAMMap | idem (`cold_pagecache_unflushed` no `--note`) | igual à R1-EI |
| Warm | processo novo com cache do SO aquecido (R1-EI) / ComfyUI residente (klein) | processo novo com cache do SO aquecido — **não** residente | igual à R1-EI |

Elegibilidade (`03` §8 item 6): cold ≤ 1 500 s elegível; 1 500–3 000 s marginal; > 3 000 s ou OOM/thrashing inviável. O watchdog de 3 600 s é só o limite do benchmark isolado, **não** orçamento renovável por estágio.

## 4. Decisão de categoria e tipo de foto de B

A categoria **não está documentada** formalmente nos registros anteriores (klein4b/R1-EI usaram A + B sem categoria). O operador determina-a **a partir da mesma B** e passa `-Category` ao setup: `tops` (parte de cima: camiseta, blusa, jaqueta), `bottoms` (calça, saia, short), `one-pieces` (vestido, macacão). `garment_photo_type`: **`model`** se B mostra a peça vestida em outra pessoa (caso do projeto), `flat-lay` só para foto de produto. O setup grava `W3Root\r3\inputs\inputs_decision.json` e o bench lê-o. Não inventar categoria para facilitar.

## 5. Offline e proveniência (lições da R1-EI aplicadas)

- **Nenhum download durante o benchmark**: `fetch_weights.py` baixa tudo (incluindo o parser, que o upstream baixaria implicitamente para o cache HF) com `hf_hub_download(repo, filename, revision=<commit>)` para `W3Root\models\fashn-vton-1.5\` e verifica tamanho + sha256. Sem `hf download --include` (falhou na R1-EI).
- **Runner offline por construção**: `HF_HUB_OFFLINE=1`, `TRANSFORMERS_OFFLINE=1`, `HF_DATASETS_OFFLINE=1`, telemetria desligada, `HF_HOME=<weights-dir>\hf_home` (determinístico e vazio) definidos **antes** dos imports + **guarda de rede** (`socket.connect` fora de loopback → exceção, registrada no sidecar). Parser carregado de diretório local (`FashnHumanParser(model_id=<dir>)`, parâmetro público) — única adaptação ao pipeline, de **fonte de pesos**, não de algoritmo.
- **Código**: clone com `core.autocrlf=false`; `verify_provenance.py --repo vton` confere blob OIDs do commit + sha256 CRLF→LF; o runner confere o sha256-LF dos arquivos **instalados** de `fashn_vton` e `fashn_human_parser` contra o manifesto a cada execução (`code_check`).
- **PowerShell 5.1**: `.ps1` em ASCII puro + BOM, CRLF via `.gitattributes`.
- **ONNX Runtime**: `import torch` antes de `import onnxruntime`; `preload_dlls()` (DLLs CUDA 13/cuDNN 9 de `torch\lib`); `CUDAExecutionProvider` exigido; fallback para CPU detectado por `get_providers()` e **reprovado** (exit 5) salvo `--allow-ort-cpu-fallback`; providers efetivos, build CUDA do ORT (`build_and_package_info.cuda_version`) e `print_debug_info` registrados.
- **Processo próprio**: o filho do `measure_run` é o runner → `tree_private`/`tree_rss` são o motor.

## 6. Risco CUDA / ONNX Runtime / Blackwell

- `onnxruntime-gpu==1.30.0` (PyPI) é **build CUDA 13.0** (`build_and_package_info.cuda_version='13.0'`, lido do wheel) → casa com `torch 2.12.1+cu130` do alvo (mesma major; `preload_dlls` usa `torch\lib`). Se o torch do alvo fosse cu128, o setup troca automaticamente para `onnxruntime-gpu==1.26.0` (CUDA 12.8).
- As arquiteturas CUDA compiladas no wheel oficial **não** estão declaradas nos docs lidos; sm_120 é inferido das notas de release ("Fixed Windows CUDA 12.9 SM120 compilation"). Por isso o setup **testa empiricamente** (passo 8: sessão CUDA + inferência yolox 640²) e o smoke test registra os providers. Se o CUDA EP falhar: o runner reprova; a alternativa (DWPose em CPU, `--ort-provider cpu`) é uma **mudança de configuração registrada**, nunca silenciosa.
- cuDNN: ORT 1.30 exige cuDNN 9.x; torch cu130 traz cuDNN 9 em `torch\lib`.

## 7. Arquivos

| Arquivo | Papel |
|---|---|
| `r3_manifest.json` | pins: commits + blob OIDs + sha256 LF dos arquivos de código; revisões HF, tamanhos e sha256 dos 6 arquivos de pesos; ORT (wheel, build CUDA, fallback); defaults; semântica dos modos; protocolo |
| `requirements-r3.txt` | deps pinadas (sem torch e sem os pacotes upstream, instalados à parte) |
| `fetch_weights.py` | download determinístico (`hf_hub_download` + `revision`) e verificação (`--verify-only --verify-sha`) |
| `verify_provenance.py` | provenance dos clones robusta a EOL (blob OIDs + sha256 LF) |
| `run_fashn_vton.py` | runner (processo próprio, offline, sidecar; `--dry-run`, `--smoke`) |
| `setup_r3.ps1` | venv `W3Root\r3\.venv`, torch CUDA (casa com o ComfyUI), deps, clone pinado + `--no-deps`, pesos, sha256, **teste do CUDA EP**, dry-run e smoke (1 passo) — **não roda o benchmark** |
| `bench_r3.ps1` | 2 modos × (cold×N + warm×N) com `measure_run.py` — só depois do setup revisado |
| `../r1ei/summarize_runs.py` | gera o registro `benchmark/measurements/*.json` a partir dos JSONs (um por modo: prefixos `r3_fashn15_bf16_576x864_segfree` / `_masked`) |
| `tests/test_r3_static.py` | testes CPU/estáticos (manifesto, hashes, dry-run com pesos esparsos, geometria, offline guard, BOM/ASCII, bench) |

## 8. Sidecar do runner (`<out>.png.json`)

`route/mode`, `pins` (commits, revisões, sha do modelo), `inputs_sha256` (A, B), `params` (categoria, `garment_photo_type`, `segmentation_free`, timesteps, CFG, seed, `skip_cfg_last_n_steps`, `num_samples`), `geometry` (A/B originais, pré-redimensionadas, canvas 576×864, padding, saída), `versions` (torch/CUDA/cuDNN/onnxruntime + build CUDA/transformers/numpy/opencv/fashn_vton/parser), `gpu`, `onnx_providers` (pedidos/efetivos/fallback), `phases` (load_tryon/dwpose/human_parser/total, pose_A, pose_B, parse_A, parse_B, preprocessing, sampling, postprocess, call_total, save), `torch_vram` (max allocated/reserved), `output` (caminho, tamanho, sha256), `offline` (env, guarda, tentativas bloqueadas), `code_check`, `pin_check`, `verdict`/`error`.

## 9. Memória: conhecido × desconhecido

Conhecido: pesos 1,94 GB (bf16) + 0,26 GB (parser fp32) + 0,35 GB (ONNX); única medição publicada 3,04 GiB de pico (Apple M4 Max, FP16, sem parser; PR #6). Desconhecido: VRAM e RAM reais no alvo, workspace do cuDNN nas sessões ORT, RAM do processo. Estimativa `E`: VRAM 3–6 GB, RAM 4–8 GB, tempo de segundos a poucas dezenas de segundos por run frio. **Só a medição decide.**
