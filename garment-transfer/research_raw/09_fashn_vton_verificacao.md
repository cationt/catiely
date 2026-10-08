# 09 — Verificação em fonte primária: FASHN VTON v1.5 (rota R3) — 2026-10-08

Objetivo: pinar tudo o que participa da execução da R3 (código, pesos, dependências) e esclarecer a semântica dos dois modos antes da medição de viabilidade no hardware-alvo. Feito a partir do container (GitHub, Hugging Face API e PyPI acessíveis; `pytorch.org` e `onnxruntime.ai` bloqueados — docs do ONNX Runtime lidos do branch `gh-pages` no GitHub; metadados dos wheels lidos diretamente do zip no PyPI por range request). Complementa `research_raw/07` (cluster FASHN, leitura integral do código).

## 1. Código

| Item | Valor | Fonte |
|---|---|---|
| Repo | `fashn-AI/fashn-vton-1.5`, branch `main`, **HEAD = `7c0f10af3f91ad4048fe9729c470a13ef905d25a`** (2026-02-01 23:30 +01:00, "fix: update dependencies in pyproject.toml to use onnxruntime-gpu…") | `git clone` + `git log`; `git ls-remote` (sem tags) — coincide com o SHA observado pelo operador |
| Pacote | `fashn-vton 1.5.0` (`pyproject.toml`); **não existe no PyPI** (`/pypi/fashn-vton/json` → 404) | PyPI |
| Licença | Apache-2.0 (`LICENSE`; `pyproject` `license = Apache-2.0`) | arquivos |
| Paper | nenhum (badge "arXiv Coming Soon"; citação "Paper coming soon") | README |
| Dependências declaradas | torch≥2.0, torchvision≥0.15, safetensors≥0.3, huggingface_hub≥0.20, pillow≥9, numpy≥1.21, opencv-python≥4.5, tqdm≥4.65, einops≥0.6, **onnxruntime-gpu≥1.14**, matplotlib≥3.5 (usado em `dwpose/utils.py`), **fashn-human-parser≥0.1.1** | `pyproject.toml` |
| Windows | zero instruções (README usa `source .venv/bin/activate`); código portável (`os.path.join`) | README/código |
| Blob OIDs + sha256 LF dos 25 arquivos relevantes | em `tools/r3_fashn/r3_manifest.json` → `code_repos.vton.files` | `git ls-tree -r HEAD` + `sha256sum`; nenhum arquivo com CRLF no repositório |

| Item | Valor | Fonte |
|---|---|---|
| Parser (código) | `fashn-AI/fashn-human-parser`, `main` HEAD = `f2771f2fb8655349e87e2869bbde7ace0bd06f2c` (2026-01-10); PyPI `fashn-human-parser==0.1.1` wheel `3d84a195…` (7 764 B) — `parser.py`, `labels.py`, `__init__.py` do wheel **byte-idênticos** aos blobs do commit (sha256 conferidos) | clone + wheel baixado |
| Parser (licença) | **"FASHN Human Parser License"**: "The underlying model … is a fine-tuned version of SegFormer and inherits the NVIDIA Source Code License for SegFormer"; README: "This model inherits the NVIDIA Source Code License for SegFormer"; `pyproject` `license = See LICENSE`; model card HF `license: other`, `license_name: nvidia-segformer` | `LICENSE`, README, model card |
| Parser (deps) | torch≥2.2, transformers≥4.30, opencv-python≥4.8, numpy≥1.20, pillow≥9 | `pyproject.toml` |

## 2. Pesos (Hugging Face API, `?blobs=true`)

| Repo HF | Revisão (sha) | Arquivo | Bytes | sha256 |
|---|---|---|---|---|
| `fashn-ai/fashn-vton-1.5` (apache-2.0; não gated; lastModified 2026-02-01) | `7720683168567eb5a2a4c67f15116c6e29c83ded` | `model.safetensors` | 1 943 668 048 | `d6cd38286885bc29fa487ea9383f80ffeb95862e7747c630d42c5d3c05bdd35a` |
| `fashn-ai/DWPose` (apache-2.0; redistribuição; "NOT an original work by FASHN AI") | `548b5df25b84d9f4aac0611dfa1c2a7a12f15571` | `yolox_l.onnx` | 216 746 733 | `7860ae79de6c89a3c1eb72ae9a2756c0ccfbe04b7791bb5880afabd97855a411` |
| idem | idem | `dw-ll_ucoco_384.onnx` | 134 399 116 | `724f4ff2439ed61afb86fb8a1951ec39c6220682803b4a8bd4f598cd913b1843` |
| `fashn-ai/fashn-human-parser` (other / nvidia-segformer; não gated) | `1f80c34dbab321c5730dda5c3fea279fd3e97498` | `model.safetensors` | 256 146 352 | `e43c8c8a9b04f28798f0a4630cf18caa2cdb27a0d454fae43a5716e6f7078244` |
| idem | idem | `config.json` (SegformerForSemanticSegmentation, `_name_or_path nvidia/mit-b4`, depths [3,8,27,3], 18 classes) | 1 654 | `87bd5b66419dbfa7c02cfbeb94e292454863b1606c5df29526b19a6c1de70d9f` |
| idem | idem | `preprocessor_config.json` (384×576, ImageNet mean/std) | 340 | `54007eb4cedae02565c4f035750aeebe3ddc53d36ab575e8534615623e6b6225` |

Total a baixar: **2 550 962 243 B ≈ 2,55 GB (2,38 GiB)**. O sha do `model.safetensors` observado pelo operador (`d6cd3828…`) **confere** com a API; a revisão exata é `77206831…`.

Onde o upstream os obtém: `scripts/download_weights.py` → `hf_hub_download("fashn-ai/fashn-vton-1.5", "model.safetensors")`, `hf_hub_download("fashn-ai/DWPose", …)` **sem revisão** e `FashnHumanParser(device="cpu")` para "auto-cache" do parser no cache HF (`from_pretrained("fashn-ai/fashn-human-parser")` — download **implícito** em runtime se não estiver em cache). Na R3 todos os arquivos são baixados por `tools/r3_fashn/fetch_weights.py` com `revision=` pinada para um diretório local e o parser é carregado **do diretório** (`FashnHumanParser(model_id=<dir>)`, parâmetro público da classe).

## 3. Semântica dos modos (código lido, `pipeline.py` @ 7c0f10af)

- `TryOnPipeline.__init__` **sempre** carrega os três modelos: `TryOnModel` (bf16 se `cuda` e `is_bf16_supported()`, senão fp32), `DWposeDetector` (duas `onnxruntime.InferenceSession` com `providers=["CUDAExecutionProvider"]` quando device cuda — `wholebody.py`) e `FashnHumanParser` (fp32).
- `__call__`: pré-resize das **duas** imagens (`AspectPreserveResize((864,864), fit, LANCZOS, allow_upsampling=False)`) → DWPose em A e em B (B só se `garment_photo_type == "model"`; flat-lay usa pose dummy) → `draw_pose` (grayscale) → **`hp_model.predict` em A e em B, sempre** → `create_clothing_agnostic_image(…, disable_masking=segmentation_free)` → `create_garment_image(…, disable_masking = garment_photo_type == "flat-lay")` → `ResizePad((576,864))` → tensores → `_sample` (Euler, rectified flow com shift μ=1,5, `num_timesteps` passos, CFG real via `forward_for_cfg` = batch duplicado cond+nulo, `skip_cfg_last_n_steps=1`) → `unpad`.
- **`segmentation_free=True` ("segfree")**: parser **executado** em A e B; `create_clothing_agnostic_image` devolve A **inteira** (`if disable_masking: return img_np`); a peça de B continua **recortada pelo parser** (labels da categoria; resto → cinza 127) quando `garment_photo_type="model"`. **Não é "parser-free".**
- **`segmentation_free=False` ("masked")**: mesmo parser; máscara da pessoa = labels da categoria (+ arms/torso para upper/full; + legs para lower/full) com buffer, bounded, contour-following e hybrid, dilatação assimétrica (33/33/16/16 px a 864 de altura), excluindo identidade (face, hair, jewelry, bag, glasses, hat) e mãos/pés conforme cobertura → cinza 127.
- Diferença de custo entre os modos: só a criação da máscara em CPU (milissegundos); custo de GPU idêntico por construção — a medição dos dois modos registra a viabilidade das duas configurações que o G0 usará, não uma comparação de desempenho.
- Defaults oficiais (confirmados em `__call__` e em `examples/basic_inference.py`): `num_samples=1`, `num_timesteps=30`, `guidance_scale=1.5`, `skip_cfg_last_n_steps=1`, `seed=42`, `segmentation_free=True`, `garment_photo_type="model"`.
- Resolução: `TryOnModel(input_shape=(864, 576))` (H×W), patch 12 → 72×48 = 3 456 tokens; saída `unpad` = tamanho de A pré-redimensionada (≤ 864 no lado maior) → **não comparável em MP** com klein4b/R1-EI (~1 MP).
- Arquitetura (model card + código): MMDiT 972 M parâmetros, hidden 1280, 10 heads, 8 double + 16 single + 4 patch-mixer; `x_embedder` 7 canais (ruído 3 + imagem 3 + pose 1), `garment_embedder` 4; categoria por `nn.Embedding` (tops=1, bottoms=2, one-pieces=3; 0 = nulo). Sem canal de máscara.

## 4. ONNX Runtime × CUDA 13 × Blackwell (risco principal da R3)

| Fato | Evidência |
|---|---|
| `onnxruntime-gpu==1.30.0` (PyPI, 2026-09-10, `requires_python>=3.11`), wheel `cp312-win_amd64` 160 478 594 B sha256 `882da66f936e1f560b155118c5953dc45268cd92893abb8d31a940f4d1effb36` é **build CUDA 13.0** | `onnxruntime/capi/build_and_package_info.py` dentro do wheel: `cuda_version = '13.0'` (lido do zip no PyPI) |
| 1.29.0 também CUDA 13.0; **1.26.0 e 1.24.4 são CUDA 12.8** (fallback se o torch do alvo for cu128) | idem (1.26.0 wheel sha256 `5f49c446…`) |
| Docs: CUDA 13.0 + cuDNN 9.x para ORT 1.27–1.30 (PyPI); "ONNX Runtime built with CUDA 13.0 require CUDA 13.0 or newer"; pipeline de release 1.30.0 usa `cudnn_folder 9.14.0.64_cuda13` | `gh-pages/docs/execution-providers/CUDA-ExecutionProvider.md`; `tools/ci_build/github/azure-pipelines/stages/py-gpu-packaging-stage.yml` @ v1.30.0 |
| Carregamento de DLLs: `onnxruntime.preload_dlls(cuda=True, cudnn=True, msvc=True, directory=None)` (≥ 1.21); ordem no Windows: **`torch\lib` primeiro**, depois pacotes `nvidia-*` do site-packages, depois o PATH — "provided both are built against the same major version of CUDA and cuDNN" | mesma página |
| O torch do alvo é `2.12.1+cu130` → mesma major (13) → DLLs do torch servem ao ORT sem pacotes `nvidia-*` extras | inferência; **verificação empírica obrigatória** (setup passo 8: sessão CUDA + inferência yolox) |
| sm_120: notas 1.30.0 "Fixed Windows CUDA 12.9 SM120 compilation"; plugin EP CUDA 0.1.0 "CUDA 12.8/13, SM90, and SM120"; a lista `CMAKE_CUDA_ARCHITECTURES` do wheel oficial **não está declarada** nos docs lidos (parâmetro do pipeline) | releases do GitHub |
| A página `docs/install/index.md` do gh-pages ainda diz "default CUDA version … is 12.x since 1.19.0" — **desatualizada** em relação ao wheel (13.0) e à página do EP (13.0 desde 1.27) | gh-pages |
| Fallback silencioso: `InferenceSession(providers=["CUDAExecutionProvider"])` cai para CPU com aviso se o EP não carregar → o runner lê `session.get_providers()` e reprova (exit 5) | comportamento do ORT; `run_fashn_vton.py` |

## 5. Dependências pinadas (PyPI, 2026-10-08)

transformers 5.15.0 (Segformer presente em v5.15.0 e v5.19.0: `models/segformer/modeling_segformer.py` HTTP 200) · safetensors 0.8.0 · huggingface_hub 1.27.0 · numpy 2.5.2 · Pillow 12.3.0 · opencv-python 4.14.0.94 (2026-07-29; 5.0.0.93 existe mas é major novo) · einops 0.8.2 · tqdm 4.70.1 · matplotlib 3.11.2 · psutil · nvidia-ml-py. torch/torchvision do índice `cu130` (mesma versão do ComfyUI). `fashn-human-parser==0.1.1` e o clone `fashn-vton-1.5` instalados com `--no-deps` (o `torch>=2.2` do parser resolveria, no PyPI Windows, para um wheel CPU-only).

## 6. O que continua NÃO VERIFICADO

- VRAM/RAM reais no alvo (nenhuma declaração oficial; único dado: PR #6 do repo, Apple M4 Max FP16, 3,044 GiB de pico sem parser — `07`).
- Arquiteturas CUDA compiladas no wheel oficial do ORT (sm_120 inferido; teste empírico no setup).
- Comportamento sem detecção de pose em A (keypoints −1; sem exceção no pipeline aberto) e capacidade de **adição** sobre pele — só o G0 decide.
- Qualidade/fidelidade: fora do escopo desta fase.
