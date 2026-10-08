# 08 — Verificação primária de "Easy-Insert" e do stack R1-EI (2026-10-08)

Pergunta: o componente chamado no projeto de "Easy-Insert" existe, é público, é compatível com FLUX.2-klein-base-4B e o nome estava correto? **Sim, sim, sim, sim** — com três precisões (abaixo). Tudo verificado em fonte primária a partir do contêiner (GitHub, API do Hugging Face e PyPI acessíveis; **ModelScope e pytorch.org bloqueados** pelo proxy, logo o que depende deles fica `NV`).

## 1. Repositório (clone completo)

| Item | Valor |
|---|---|
| URL | https://github.com/huan-yin/Easy-Insert |
| Commits | 2: `5d24557c…` ("upload inference", 2026-08-16 18:32 +08) → **`82094484f432b74efb6c4ccbf144c08350f02144`** ("update diffusers inference", 2026-08-16 20:20 +08), autor Li Xiangyue |
| Arquivos | `README.md`, `LICENSE` (Apache-2.0, texto lido), `requirements.txt`, `utils.py`, `inference.py` (DiffSynth), `inference_diffusers.py` (Diffusers), `low_varm_inference.py` (DiffSynth low-VRAM), `app.py` (Gradio), `examples/` (4 exemplos: background, insert_mask, ref_image, ref_mask, result; 1280² a 1801×2600) |
| sha256 | `utils.py d84f0cbc…`, `inference_diffusers.py ca8803be…`, `README.md dc728c42…`, `LICENSE c71d239d…`, `requirements.txt d630ce07…` |
| Paper | nenhum link em README/model card/Space; nenhum arXiv citado |
| Definição (README) | "a LoRA model for FLUX.2-klein-base-4B that performs reference-based object insertion: given a background image with a masked region and a reference image highlighting an object, the model inserts the object into the masked region while preserving the background, lighting, and surrounding elements" |
| Entradas | background, insert mask (branco = onde inserir), reference image, reference mask (branco = objeto) |
| Pré-processamento (`utils.py`) | `process_source`: binariza máscara; recorte **quadrado** em torno da bbox da máscara com `scale=1.2` (padding preto fora da imagem); resize 1024² (LANCZOS; máscara NEAREST); **região da máscara pintada de branco**. `process_reference`: mesmo recorte; objeto sobre **fundo branco**. `paste_back`: redimensiona a geração ao lado do crop, composita **só dentro da máscara** (feather 0) e cola em A. |
| Prompt fixo | "Replace the white mask of image1 with the content in image2. Preserving the background, lighting, and surrounding elements, maintain a seamless and natural result." |
| Hiperparâmetros | `image_size=1024`, `num_inference_steps=15`, `cfg_scale/guidance_scale=4`, `seed=1`; `edit_image=[background, ref]` (DiffSynth) / `image=[background, ref]` (Diffusers) |
| requirements.txt | `diffsynth==2.1.2`, `diffusers==0.39.0`, transformers, accelerate, peft, safetensors, sentencepiece, torchvision, Pillow, numpy, `gradio==6.24.0` |

## 2. Pesos

| Repo | Hub | Estado | Conteúdo |
|---|---|---|---|
| `LiXiY/Easy-Insert` | Hugging Face | **público**, `license: apache-2.0`, revisão `dd71e3f8422135844b625b1289c38f13789ea736` (2026-08-16) | `easy-insert-diffusers.safetensors` **96 365 440 bytes**, sha256 `6826ffccc1d1dd6642b27f0697c36509fcef5dfd7a336d39ce21f177d74866f6`; `config.json` (`{"name": "Easy-Insert"}`); README (mesma descrição + link do GitHub) |
| `HuanJue/Easy-Insert` | Hugging Face | **não existe publicamente** (`/api/models/HuanJue/Easy-Insert` vazio; raw README → "Invalid username or password") | — |
| `HuanJue/Easy-Insert` | ModelScope | referenciado pelo README (badge "Diffsynth_LoRA") e pelos scripts DiffSynth (`easy-insert.safetensors`); **não verificável daqui** (proxy 403) | `NV` |
| Space `LiXiY/Easy-Insert` | Hugging Face | público, Gradio, 2026-08-16 | `app.py` usa **`Flux2KleinPipeline.from_pretrained(...)` + `pipe.load_lora_weights("LiXiY/Easy-Insert")`** → o caminho Diffusers é o da demo oficial do autor; `requirements.txt` idêntico ao do repo |
| `black-forest-labs/FLUX.2-klein-base-4B` | Hugging Face | **público, não gated**, `apache-2.0` (LICENSE.md lido), revisão `a3b4f4849157f664bdbc776fd7453c2783562f4d` (2026-02-24) | `transformer/diffusion_pytorch_model.safetensors` 7 751 109 744 B (`e1096746…`); `text_encoder/model-0000{1,2}-of-00002.safetensors` 4 967 215 360 + 3 077 766 632 B (`8c0506e7…`, `82f2bd83…`); `vae/diffusion_pytorch_model.safetensors` 168 120 878 B (`ca70d220…`); `tokenizer/tokenizer.json` 11 422 654 B; `flux-2-klein-base-4b.safetensors` 7 751 105 712 B (single-file para ComfyUI; **não necessário**); configs |

Arquitetura (configs): transformer `Flux2Transformer2DModel` com 5 blocos duplos + 20 simples, 24 cabeças × 128, `in_channels` 128, `joint_attention_dim` 7680, **`guidance_embeds: false`** (klein-base é não destilado → CFG real); text encoder `Qwen3ForCausalLM` hidden 2560, 36 camadas (Qwen3-4B), bf16; VAE `AutoencoderKLFlux2` latente 32 canais, patch 2×2 → 16 px/token (1024² → 4096 tokens; com 2 imagens de edição, 12 288 tokens por passe); scheduler FlowMatchEuler com `shift 3.0`, `use_dynamic_shifting`.

## 3. Bibliotecas

| Pacote | Fato verificado |
|---|---|
| `diffusers==0.39.0` (PyPI, 2026-07-03) | contém `Flux2KleinPipeline(DiffusionPipeline, Flux2LoraLoaderMixin)`; `__call__(image=[...], prompt / prompt_embeds, negative_prompt_embeds, height, width, num_inference_steps=50, guidance_scale=4.0, generator, output_type, text_encoder_out_layers=(9,18,27), max_sequence_length=512)`; `do_classifier_free_guidance = guidance_scale > 1 and not is_distilled` → 2 passes do transformer por passo; imagens de edição > 1 MP são reduzidas a ~1 MP (`_resize_to_target_area`); `model_cpu_offload_seq = "text_encoder->transformer->vae"`; `enable_layerwise_casting`, `enable_model_cpu_offload`, `enable_sequential_cpu_offload`, `enable_group_offload` disponíveis; passar `text_encoder=None` em `from_pretrained` pula o carregamento do componente (pipeline_utils l. 973) |
| `diffsynth==2.1.2` (PyPI, 2026-08-14) | `Flux2ImagePipeline.from_pretrained(model_configs=[ModelConfig(...)], vram_limit=...)`; `ModelConfig` com `offload/onload/preparing/computation` (device, dtype) — base do modo "8 GB"; **download padrão = ModelScope** (`parse_download_source` → `"modelscope"`; `DIFFSYNTH_DOWNLOAD_SOURCE=HuggingFace` troca; `DIFFSYNTH_SKIP_DOWNLOAD=True` só locais); `python>=3.10.1`; sem dependência obrigatória de flash-attn/sageattention/triton para FLUX.2 (imports opcionais só em modelos de vídeo) |
| `torch` (PyPI 2.14.1) | wheels **Windows do PyPI são CPU-only** (118 MB; deps `nvidia-*`/`triton` só com `platform_system == "Linux"`) → torch CUDA para Windows vem de `https://download.pytorch.org/whl/cu128` (ou cu130); Blackwell sm_120 exige CUDA ≥ 12.8. `pytorch.org` bloqueado daqui → a disponibilidade exata do índice é `NV` deste contêiner (o ComfyUI Desktop do operador já roda torch CUDA na 5070, prova de existência) |
| Versões vigentes em 2026-08-16 (data do release) | transformers 5.15.0 (2026-08-10), accelerate 1.14.0, peft 0.20.0, safetensors 0.8.0, sentencepiece 0.2.2, huggingface_hub 1.27.0 (diffusers exige `<2.0`), numpy 2.5.2, Pillow 12.3.0 — usadas como pins em `tools/r1ei/requirements-r1ei.txt` |

## 4. Precisões ao que o projeto afirmava

1. "8 GB" refere-se ao **`low_varm_inference.py` do DiffSynth** (offload em disco, pesos `float8_e4m3fn` em CPU, computação bf16 em CUDA, `vram_limit = VRAM livre − 0,5 GB`), não ao pipeline em geral; o modo padrão do upstream (`pipe.to("cuda")`, tudo bf16) precisa de ≈ 15–16 GB e **não cabe** em 12 GB.
2. Existem **dois formatos de LoRA**: DiffSynth (`easy-insert.safetensors`, ModelScope) e Diffusers (`easy-insert-diffusers.safetensors`, Hugging Face). O caminho verificável daqui e usado pela demo oficial é o Diffusers.
3. **Nenhum paper**; "Easy-Insert" é um release de LoRA + código. A capacidade em **roupa** continua `NV` (os 4 exemplos são objetos; nada de vestuário) — a medir, não presumir.

## 5. O que fica `NV` deste contêiner (verificável só na máquina-alvo)

ModelScope `HuanJue/Easy-Insert` (existência, tamanho); índice `download.pytorch.org/whl/cu128` (acesso); compatibilidade `diffusers 0.39.0 × transformers 5.15.0` em Windows (a demo do autor usou essas faixas em Linux); VRAM/RAM/tempo reais da variante sequencial bf16.
