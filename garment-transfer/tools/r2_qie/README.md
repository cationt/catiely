# R2 — Qwen-Image-Edit-2511 Q5: PREPARADA, NÃO MEDIDA

Preparação D-055. Nenhum setup real, smoke GPU, sampling ou benchmark foi
executado neste patch. D-056 fica reservado ao resultado e ao veredito H4.
Não avançar para distribuição nula, Proto0 ou G0 nesta etapa.

## Configurações congeladas

| Identidade | Canvas | Repetições futuras | Papel |
|---|---|---|---|
| `qie2511_q5_2ref_1mp_40steps` | escala oficial ~1 MP; A pinada resulta em 688×1504 | cold ×3 + warm ×3 | primária, decide H4 |
| `qie2511_q5_2ref_0p5mp_40steps` | 544×960, Lanczos/center | cold ×3 | padronizar a evidência histórica de `03` §1b; não substitui a primária |
| `qie2511_q5_2ref_1mp_20steps` | ~1 MP | cold ×3, somente posteriormente e sob condição | registrada, desabilitada no executor |

40 steps, CFG 4, Euler, Simple, shift 3.1, denoise 1.0,
`index_timestep_zero`, CFGNorm strength 1/pre_cfg false, seed 42,
batch 1, uma imagem, Lightning desativado. A é imagem 1; B, imagem 2.
Prompt fixo está no manifesto e nos workflows; mede custo, sem otimização
de qualidade. Q3, LoRA, ControlNet, LanPaint e DifferentialDiffusion não entram.

Os dois JSONs API têm SHA256 no `manifest.json`. O cliente aceita apenas
substituição de nomes A/B e prefixo da saída. O smoke tem uma derivação
explicitamente identificada de **1 step**, mantendo os demais parâmetros;
não é benchmark. A configuração de 20 steps não pode ser selecionada.

O `TextEncodeQwenImageEditPlus` oficial recebe A/B **também no negativo vazio**.
Ambos os encodes ficam no fecho das imagens. Internamente, cada referência
é redimensionada para ~384² no vision encoder e ~1024² no VAE, nos dois
ramos. A configuração 544×960 muda o canvas/latente de saída; não reduz à
metade a área interna de cada referência. Nenhum código do fornecedor mudou.

## Provenance e divergência das fontes

`manifest.json` registra nomes, tamanhos e SHA256 integrais de Q5_K_M,
TE FP8 scaled, VAE BF16 e A/B; os hashes das entradas são os mesmos de
Klein/R1-EI. As identidades dos pesos conferem com size/SHA256 LFS nas revisões
HF registradas. Isso não reconstrói o histórico original de download.

Core **v0.38.2 @ daeb5e53681e2b10a3f0727d9ec5bc90784bee10**;
Desktop **1.1.6.0**; GGUF Registry **1.1.10**, sem `.git`: pin reproduzível
dos 17 arquivos de `.tracking`, sem inventar commit. Fontes críticas do core,
binário Desktop, pacotes, blueprint e template instalado também são verificados.
O setup não instala nem baixa nada. Divergência interrompe; não há fallback.

Origem: [template oficial Comfy-Org pinado](https://github.com/Comfy-Org/workflow_templates/blob/8be1f8c4b5af2d550d70922a23b79cee599e1f3e/templates/image_qwen_image_edit_2511.json),
workflow `ad18abd3-bdee-4f80-8fae-d15d4f845b9d`, subgraph
`cdb2cf24-c432-439b-b5c8-5f69838580c9`. Pacotes locais:
`comfyui_workflow_templates=0.11.74`, `comfyui_workflow_templates_json=0.1.100`.
Template SHA256 `b23103935f437e1fe3184247fa5bafb891a28113d0c63de7449b7cdfb0419111`.

No ramo executável sem Lightning, KSampler169 recebe **40** de
PrimitiveInt166/switch167/link355 e **CFG 4** de
PrimitiveFloat154/switch164/link356; o CFG 3 salvo no widget é inativo.
A nota textual MarkdownNote157 menciona **Comfy 20 steps**; diverge do ramo
executável. O blueprint local também executa 40/4. A decisão do arquiteto
adota **40 como baseline**, preservando a divergência no manifesto.
A assinatura de [Diffusers QwenImageEditPlusPipeline](https://github.com/huggingface/diffusers/blob/main/src/diffusers/pipelines/qwenimage/pipeline_qwenimage_edit_plus.py)
consultada em 2026-10-08 tem defaults **50 steps / true CFG 4**; é referência
adicional, não o motor desta medição.

## Cold, warm e cache auditável

Cold inicia um processo novo do core instalado, headless, e espera que esteja
de pé e ocioso, com model manager vazio e DynamicVRAM ativo. A porta loopback
precisa pertencer ao PID recém-iniciado, com create_time e comando conferidos.
Servidor ComfyUI antigo ou porta ocupada interrompem; nunca são reaproveitados
ou encerrados pelo harness. Startup tem tempo/log próprios, fora do wall.
Page cache não é limpo: `cold_pagecache_unflushed=true`.

Warm usa o **mesmo processo do terceiro cold**, preservando os modelos no
model manager. Isso não promete residência integral na VRAM de 12 GB.
Não chama `/free`, não usa `--cache-none`, não muda seed nem parâmetros.
Cada run envia cópias byte-idênticas via `/upload/image`, com nomes exclusivos,
confere SHA256 contra originais/pins e apaga somente seus aliases na pasta
input isolada ao terminar, inclusive em falhas.

A política é calculada do grafo congelado:

- `must_reexecute`: fecho a jusante de A/B, incluindo os próprios LoadImage;
- `allowed_cached`: complemento desse fecho;
- cold: `execution_cached` vazio;
- warm: todo `execution_cached` deve estar em `allowed_cached`.

O gate de classes fora do fecho aceita explicitamente `UNETLoader`,
`UnetLoaderGGUF`, `UnetLoaderGGUFAdvanced`, `CLIPLoader`, `DualCLIPLoader`,
`TripleCLIPLoader`, `CLIPLoaderGGUF`, `DualCLIPLoaderGGUF`,
`TripleCLIPLoaderGGUF`, `VAELoader`, `ModelSamplingAuraFlow` e `CFGNorm`.
Qualquer outra classe exige decisão humana; a lista não é ampliada por inferência.
As variantes aceitas não são fallbacks: o workflow usa somente
UnetLoaderGGUF + CLIPLoader nativo + VAELoader + AuraFlow + CFGNorm fora do fecho.
CLIPLoaderGGUF não aceita este TE FP8 scaled.

O dry-run imprime node id + class_type de ambos os conjuntos. Os sidecars
registram os conjuntos, loader ids, `execution_cached`, `cached_nodes` e
verdict. Não dependem dos IDs 145/152: esses foram exemplos do template
usados pela Astra na reprodução CPU do cache dos patches, anterior à decisão.
Sampler, TE, VAE encode, decode ou save cacheados invalidam o run:
**`FAIL:cached_result`, exit 23**. Outras falhas retornam erro; nada prossegue.
Os conjuntos dos três warm são comparados no relatório: divergência fica
explícita para revisão, sem invalidar automaticamente runs por esse motivo.

O smoke futuro prova: (1) cold; (2) mesma submissão, mesmos nomes e mesmos
bytes, com sampler obrigatoriamente em cache; (3) aliases byte-idênticos
renomeados, com cache permitido somente fora do fecho. A segunda fase é um
controle positivo rotulado, que reutiliza deliberadamente a saída nativa
anterior; não pode ser habilitada no benchmark. Qualquer falha para o setup.

Os warm antigos da Klein precedem esta regra e não foram auditados quanto
a `execution_cached`; não foram remedidos nesta preparação.

## Evidência, tempos e falhas

Cada run tem diretório UUID, plan, sidecar, output.png, client.log e server.log
próprios. O servidor mantém também process.log contínuo e startup.log. As
saídas nativas de ComfyUI são preservadas na pasta isolada do servidor para
auditoria; há exatamente uma imagem reportada por prompt, e uma cópia final
por run. No controle positivo do smoke a reutilização é declarada.

O cliente exige `/history` com `status.messages`, prompt_id e grafo iguais
ao submetido, uma saída com prefixo exclusivo, arquivo novo e metadados PNG
do workflow. Registra SHA do template, grafo efetivo, inputs/cópias, saída,
runtime/provenance, system_stats, PID, server_id, eventos websocket e logs.
Campos internos `is_changed` adicionados pelo core são separados dos inputs
efetivos na comparação. Nenhuma saída antiga passa como geração nova.

- `wall_s` do sidecar: submissão HTTP até saída final pronta; startup e upload
  ficam fora. É o tempo usado na avaliação de H4.
- `server_execution_s`: timestamps de início/fim em status.messages.
- `sampling_s`: intervalo monotônico de recepção websocket entre `executing`
  do KSampler e do VAEDecode; inclui carga/offload do sampler e latência dos
  eventos. Não é tempo isolado de kernel GPU.
- `per_step_s = sampling_s / steps`; no controle deliberadamente cacheado
  do smoke esses tempos são nulos, não medições de sampling.
- Logs DEBUG incluem carregamento completo/parcial, DynamicVRAM e
  `Prompt executed in ...`; o parser aceita segundos e HH:MM:SS (>600 s).

`measure_run.py` permanece intacto, com budget 3600 s e intervalo 0,5 s.
Seu wall externo inclui a pequena inicialização/validação do cliente,
além da submissão; ambos os tempos ficam disponíveis. VRAM/commit são do
sistema; `tree_private` mede o cliente, **não todo o motor externo**.
O supervisor valida exit, JSON do monitor (mesmo se o monitor sair 0),
deadline, sidecar, binding de PID/run e output. Qualquer erro/OOM/deadline
interrompe a sequência e encerra somente o servidor que criou. Se o watchdog
matar o cliente, preserva log e sidecar de falha incompleta. Não há retries.

Offline: variáveis HF/Transformers offline, API nodes desativados, somente
GGUF habilitado entre custom nodes e frontend local. O bootstrap instala
guarda de rede Python para bloquear conexões/DNS externos, mantendo loopback;
tentativa inesperada falha. Não é uma regra de firewall do SO. Nenhum download
ou instalação faz parte dos scripts. Flags efetivas ficam no sidecar;
DynamicVRAM deve estar ativo, sem `--fast` ou alterações de precisão/offload.

## H4 permanece não decidida

Primária 40 steps: mediana cold ≤1500 s, 6/6 exit 0, sem OOM/thrashing:
H4 verdadeira, sem precisar medir 20. Se ultrapassar 1500 s e a projeção
linear de sampling para 20 sugerir ≤1500 s, a projeção **não decide H4**:
devolver para executar posteriormente `qie2511_q5_2ref_1mp_20steps`, cold ×3.
Usar `wall_s - sampling_s + 20 * per_step_s` apenas como triagem explícita.
1500–3000 s é marginal, retorna ao arquiteto; >3000 s/OOM/deadline/thrashing
é falha conforme handoff, preservando a avaliação da condição de 20 antes
de qualquer decisão por projeção. Nunca executar 20 automaticamente nem
usar a secundária para substituir a primária. Thrashing exige revisão dos
dados/logs: não inventamos um threshold novo nem emitimos H4 automaticamente.
O orçamento de produção continua **3600 s por imagem final**, somando estágios.

## Operação posterior no Windows PowerShell 5.1

Fechar ComfyUI Desktop/servidores existentes primeiro. Na raiz do checkout
atualizado, o operador deve executar **depois**, não nesta preparação:

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\garment-transfer\tools\r2_qie\setup_r2.ps1
```

Esse comando valida pins locais e executa o smoke GPU de 1 step em três fases;
não instala dependências e não inicia o benchmark. Ao terminar, imprime o
`report.json` exclusivo em `C:\Users\henri\OneDrive\Documentos\w3-measure\r2\setup_<uuid>\`.
Revisar esse relatório e as saídas antes de autorizar medição. Futuramente:

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\garment-transfer\tools\r2_qie\bench_r2.ps1 -SetupReport "CAMINHO_EXATO_DO_SETUP\report.json"
```

A secundária exige chamada explícita com
`-Configuration qie2511_q5_2ref_0p5mp_40steps`. Não é executada pela primária.
Para inspeção CPU sem setup, ambos os scripts aceitam `-DryRun`.
Scripts ASCII, argumentos em arrays e paths literais suportam PS 5.1 e OneDrive.

Testes CPU: `python -B -m unittest discover -s garment-transfer/tests -p test_r2_qie.py -v`
usando o Python do ComfyUI, que já fornece aiohttp/Pillow/psutil. O servidor
dos testes é fake, com imagens sintéticas 8×8; não importa torch/ComfyUI.

## Nota: PIDs do launcher do venv

O `python.exe` do venv do ComfyUI Desktop e um launcher (uv trampoline) que inicia o interpretador real como processo filho. Por isso o PID do `bootstrap.json`, o dono do socket em 127.0.0.1:8191 e o `client_pid` do sidecar sao descendentes do PID lancado, nunca o proprio. As verificacoes de propriedade aceitam o PID lancado e os seus descendentes (`owned_pids`), o `measure_run` ja mede a arvore inteira, e o relatorio de startup inclui o ultimo erro de readiness quando o prazo de 180 s expira.
