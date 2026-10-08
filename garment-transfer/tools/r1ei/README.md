# R1-EI — FLUX.2-klein-base-4B + Easy-Insert: preparação da medição de viabilidade

Estado: **medido no hardware-alvo** (2026-10-08; §6; D-051) — elegível por tempo (cold 272,5 s), VRAM crítica (12,1–12,2 GB de 12 GB). Nada aqui mede qualidade; isso é o Prototype 0 / G0, que vem depois. Bugs de setup reproduzidos no Windows e corrigidos no repo em §7.

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
| Warm | ComfyUI externo com modelos **residentes** entre runs | processo **novo** por run, só o cache do SO presumivelmente aquecido | warm da R1-EI **não** mede residência de modelo; warm ≈ cold é esperado (16 GB de pesos não cabem no page cache ao lado de um processo de 9 GB em 16 GB de RAM) |

## 4. Arquivos

| Arquivo | Papel |
|---|---|
| `r1ei_manifest.json` | pins: commit do Easy-Insert, revisões HF, sha256/tamanhos de todos os arquivos, defaults upstream, protocolo |
| `vendor/easy_insert_utils.py` | `utils.py` do upstream **byte-idêntico** (sha conferido em runtime) + `NOTICE.md` + licença |
| `run_easy_insert.py` | runner (Diffusers, sequencial bf16; `--mode fp8|offload`; `--dry-run`; sidecar JSON; 100 % offline) |
| `make_masks.py` | máscaras grosseiras (bbox) para a viabilidade |
| `requirements-r1ei.txt` | pins de dependências (torch vem do índice CUDA; `nvidia-ml-py` em vez do `pynvml` deprecado) |
| `verify_provenance.py` | provenance do clone **robusta a EOL**: blob OIDs do commit (`git ls-tree`) + sha256 normalizado CRLF→LF dos 5 arquivos pinados; grava `provenance_easy_insert.json` |
| `hf_fetch.py` | download pinado via `huggingface_hub.snapshot_download(revision, allow_patterns)` + verificação de tamanhos/sha256 (`--verify-only --verify-sha`) |
| `summarize_runs.py` | gera o registro `benchmark/measurements/*.json` a partir dos JSONs do `measure_run.py` (+ sidecars): medianas por estado e **todos** os runs |
| `setup_r1ei.ps1` | venv, torch CUDA (casa com o ComfyUI), deps, clone pinado com `core.autocrlf=false` + `verify_provenance.py`, download via `hf_fetch.py`, sha256, dry-run — **não roda o benchmark**; ASCII puro + BOM UTF-8 (PS 5.1) |
| `bench_r1ei.ps1` | cold×3 / warm×3 com `measure_run.py` — rodar **só depois** do setup revisado |
| `tests/test_r1ei_static.py` | testes CPU: sha do vendor, máscaras, dry-run, paste-back |
| `tests/test_r1ei_infra.py` | regressão dos bugs de §7: BOM + ASCII em todos os `.ps1`, `.gitattributes`, provenance com working tree CRLF (reproduz o sha `7aa544c6…`), runner aceita clone CRLF e rejeita conteúdo alterado, seleção de arquivos do HF (`allow_patterns` como lista; single-file de 7,75 GB excluído), `verify_download`, medianas do `summarize_runs` sobre os 6 runs reais, `measure_run` sem aviso do pynvml |

## 5. Critério de elegibilidade (o mesmo do `03` §8 item 6)

Frio mediano ≤ 1 500 s a 1024² sem OOM → elegível; 1 500–3 000 s marginal; acima ou OOM/thrashing → inviável. Se o modo `normal` estourar VRAM, repetir com `--mode fp8` e **registrar** a mudança de precisão; a qualidade (criação da peça, oclusão, preservação de A) só é julgada em G0 com as máscaras congeladas.

## 6. Resultado da medição (`MEDIDO NO HARDWARE-ALVO`, 2026-10-08)

Configuração `r1ei_kleinbase4b_easyinsert_bf16_1024_normal`: RTX 5070 12 GB (12 227 MiB) · Ryzen 7 7800X3D · 16 GB RAM · pagefile ≈ 26 GB · Windows 11 · torch 2.12.1+cu130 (sm_120) · ComfyUI Desktop fechado · processo novo por run · 1024² · 15 passos · CFG 4 (30 passes) · seed 1 · `--mode normal` · mesmas A/B do klein4b. Registro completo (6 runs, 7 métricas cada, medianas, comparação): `benchmark/measurements/r1ei_kleinbase4b_easyinsert_bf16_1024_normal.json`.

| Estado | n | wall_s | mediana wall_s | VRAM pico (mediana) | RSS motor (mediana) | private motor (mediana) | RAM sistema (mediana) | swap | commit | exit / deadline / OOM |
|---|---|---|---|---|---|---|---|---|---|---|
| cold | 3 | 222,488 · 287,689 · 272,462 | **272,462 s** | 12 136,7 MB | 9 293,2 MB | 23 728,2 MB | 15 200,3 MB | 984,4 MB | 32 697,2 MB | 0 / não / não |
| warm | 3 | 283,905 · 284,508 · 282,808 | **283,905 s** | 12 177,9 MB | 9 199,4 MB | 23 728,9 MB | 14 896,3 MB | 1 026,2 MB | 35 054,9 MB | 0 / não / não |

Veredito: **elegível por tempo** (272,5 s ≈ 18 % do teto de 1 500 s; 8,55× o klein 4B fp8); **VRAM crítica** — pico máximo 12 186,7 MB com 12 227 MiB físicos (folga ≈ 40 MiB) em 6/6 runs, sem OOM; commit 31,6–35,1 GB (depende do pagefile); RAM do sistema ≈ 15/16 GB. `fp8`/`offload` **não** se justificam por tempo; `fp8` fica como fallback de VRAM. Nenhum run descartado. `warm ≈ cold` (1,04×) porque cada run é um processo novo (ver §3). O que **não** foi medido: capacidade em roupa/adição (NV → G0/E4); eviction WDDM sob 40 MiB de folga; máscaras maiores/outras A.

Para regenerar o registro a partir dos JSONs brutos (ficam na máquina-alvo, não no repo):

```
python tools\r1ei\summarize_runs.py --runs-dir <W3Root>\runs --label-prefix r1ei_kleinbase4b_easyinsert_bf16_1024_normal --sidecars-dir <W3Root>\r1ei\outputs --candidate "R1-EI" --out r1ei_record.json
```

## 7. Bugs de infraestrutura reproduzidos no Windows (antes da medição) e correções no repo

| # | Bug reproduzido | Causa | Correção (reproduzível, no repo) | Teste |
|---|---|---|---|---|
| 1 | `setup_r1ei.ps1` → `ParserError` no Windows PowerShell 5.1 | arquivo UTF-8 **sem BOM** com caracteres não ASCII: o PS 5.1 lê como ANSI | todos os `.ps1` (`setup_r1ei`, `bench_r1ei`, `inventory_windows`) em **ASCII puro + BOM UTF-8**; `.gitattributes` com `*.ps1 text eol=crlf` | `test_r1ei_infra.py`: BOM presente, zero bytes > 0x7F, chaves/parênteses balanceados, sem `hf download --include` |
| 2 | sha256 de `utils.py` do clone = `7aa544c6…` ≠ pin `d84f0cbc…` | `core.autocrlf=true` converteu LF→CRLF no working tree; os blobs do commit estavam corretos | clone com `git -c core.autocrlf=false` + `core.autocrlf false` no repo clonado; `verify_provenance.py` confere **blob OIDs do commit** (`git ls-tree`, independentes do working tree) **e** sha256 **normalizado CRLF→LF**; o runner compara o sha LF e grava `utils_source.working_tree_eol_converted` no sidecar | cópia CRLF do `utils.py` reproduz exatamente `7aa544c6…` e é aceita; conteúdo alterado é rejeitado mesmo com blob OIDs corretos |
| 3 | `hf download … --include a b c` → "Ignoring --include since filenames have been explicitly set"; base incompleta (~8,23 GB), LoRA "Fetching 0 files" | no huggingface_hub 1.27 o CLI (typer) aceita **um** valor por `--include`; os demais viram `filenames` posicionais | `hf_fetch.py` com `snapshot_download(repo_id, revision=pin, local_dir, allow_patterns=[lista])` + `--verify-only --verify-sha` (tamanhos e sha256 dos 5 arquivos grandes + presença dos 13 pequenos) | `allow_patterns` é lista com todos os arquivos necessários e **exclui** o single-file de 7,75 GB e os JPGs; `fetch` passa `revision` pinada; `verify_download` acusa ausente / tamanho / sha divergente |
| 4 | checagem de 24 GB de disco bloqueou o setup | limiar fixo | só checagem **simples** de segurança (20 GB) e apenas quando há download (`-SkipDownload` a dispensa); disco não é restrição do projeto | — |
| 5 | aviso "pynvml package is deprecated" (measure_run.py/torch) | pacote PyPI `pynvml` deprecado em favor de `nvidia-ml-py` (mesmo módulo `pynvml`) | `requirements-r1ei.txt` → `nvidia-ml-py`; `measure_run.py` importa com filtro do aviso e grava `host.nvml_package`; **semântica do monitor inalterada** | import sem aviso; `nvml_package_name()` |
