# Revisão da preparação O_null1 — D-057

Este registro D-057 é histórico. A revisão do handoff posterior está em **D-058**, ao final deste arquivo; ela substitui somente a interrupção após INCONCLUSIVE e adiciona controles sem valor normativo.

Base preservada: `12a44d4b41a64eae93e745ab264e7f5aa0e3e42a`, branch `claude/eloquent-cray-17bgqp`. Revisão focada da implementação existente, sem reiniciar a pesquisa de arquitetura. Estado: **PREPARADA, NÃO MEDIDA**. Nenhum modelo foi carregado, nenhum servidor ComfyUI foi iniciado e nenhuma O_null1 real foi gerada nesta preparação.

## Revisão adversarial e correções

| Risco verificado | Resultado/correção |
|---|---|
| Diluição do percentil por pixels copiados | O gerador e o cross-check exigem suporte explícito e não vazio. Estatísticas usam somente suporte ou suporte∩zona. Teste sintético com suporte de um pixel preserva erro19 mesmo em canvas100×100. |
| Reutilização da insertion mask de R1-EI | Projeção cobre toda a caixa996², recortada pelo canvas. Testes incluem as duas extremidades horizontais da caixa visível. |
| Geometria silenciosamente diferente da medida | Escala Klein extraída do workflow medido e fixada; crop interno VAE e crop QIE registrados. Resolução de saída divergente interrompe antes das estatísticas. |
| Tolerância por zona ignorada ou teto contornável | Auditor aplica as quatro tolerâncias às métricas correspondentes; valida teto12 no escalar e em cada zona. CLI não pode elevar o teto; FREEZE e consumidor do gate também rejeitam a violação. Testes de gate usam somente fixtures sintéticas. |
| `--a-ref` substituindo a fonte normativa ou diluindo o cross-check | `--null-stats` prevalece; suporte/full-canvas explícito obrigatório; diferença maior que+1 retorna INCONCLUSIVO. g0 exige JSON normativo congelado. |
| Incompatibilidade com transforms FASHN | `ResizePad` OpenCV recebe array NumPy; `unpad` recebe PIL como no código pinado. Integração CPU sobre imagem aleatória sintética coincide exatamente com o resize esperado. |
| Import incorreto do pré-processador Flux2 | Corrigido para `diffusers.pipelines.flux2.image_processor.Flux2ImageProcessor`; fonte efetivamente importada incluída nos SHA256 verificados. |
| Rejeição indevida de history/PNG legítimos | ComfyUI adiciona `is_changed` ao grafo executado. Somente esse metadado é removido da comparação; classes, inputs e arestas continuam obrigatoriamente idênticos. |
| OOM produzindo fallback silencioso | Exceções do VAE são relançadas antes do fallback tiled; logs de OOM/fallback invalidam a rota. Falha/deadline encerra o lote. O comportamento de execução GPU permanece para validação futura. |
| Falha do parser sem sidecar | Supervisor grava sidecar também em erro/deadline, preserva evidência e não inicia nenhuma rota. Regressão com worker simulado. |
| Provenance declarada sem verificar o ambiente real | Verifica commit e árvore tracked limpa do ComfyUI, fontes/ativos, A e versões dos três ambientes. HEAD divergente ou fonte modificada é erro. |
| Encoding PowerShell incompatível com testes existentes | Scripts novos usam UTF-8 com BOM, corpo ASCII e CRLF. Teste antigo do R2 passou a aceitar o BOM existente; nenhum script ou parâmetro do R2 foi alterado. Parser real do PowerShell5.1 coberto. |

## Validação CPU

Suíte completa concluída em2026-10-10: **13 scripts, todos exit0, sem SKIP**. Contagens reportadas: null1 20/20; schedule11/11; occupancy_null20/20; occupancy65/65; gate25/25; fidelity13/13; measure_run18; r1ei_infra68/68; r1ei_static15/15; r2_qie41/41; r3_review5/5; r3_static43/43; validate_manifest25/25. Total369 casos/checks reportados. Nenhum teste GPU.

Comando da suíte completa, a partir da raiz deste checkout:

```powershell
$env:PYTHONUTF8 = '1'
$env:R3_VTON_SRC = 'C:\Users\henri\OneDrive\Documentos\W3_REBUILD\fashn-vton-1.5\src'
$env:R3_HP_SRC = 'C:\Users\henri\OneDrive\Documentos\W3_REBUILD\fashn-human-parser\src'
& "$env:LOCALAPPDATA\Comfy-Desktop\ComfyUI-Installs\ComfyUI\ComfyUI\.venv\Scripts\python.exe" -B .\garment-transfer\tests\run_all.py
```

Também verificados: `orchestrate.py --mode Verify` (somente hashes/metadados locais, sem instalação/download/import de modelos), `run_null1.ps1 -Mode Plan` no PowerShell5.1 e `git diff --check`. O Verify validou33 fontes/ativos mais A, os três ambientes e os sete arquivos de fonte do diagnóstico DD. O Plan imprimiu os quatro suportes previstos e94 instantes DD, sem imagem real ou pesos.

| Rota | Pixels no suporte previsto | Canvas |
|---|---:|---:|
| Klein | 1 112 150 | 1 113 600 |
| QIE | 1 079 808 | 1 113 600 |
| R1-EI | 722 100 | 1 113 600 |
| FASHN | 1 113 600 | 1 113 600 |

## Limites e ponto de parada

Testes sintéticos, mocks e leitura estática não provam execução CUDA, determinismo dos kernels no alvo, aceitação dos workflows pelo servidor real ou que a nula ficará abaixo do teto12. Esses resultados só existirão após revisão deste commit e execução explícita pelo operador. A geração futura é sequencial e interrompe no primeiro erro ou nula rejeitada, preservando o lote parcial para revisão.

Nenhum valor real de τ_null foi publicado. Não houve sampling, benchmark, O_null2, Proto0/G0, E1/E2, tuning ou otimização. Comandos futuros em [README.md](README.md); não executá-los em modo Generate antes da revisão do Claude. Qualquer alteração da tupla de escala/VAE/resolução/reprojeção exige uma nova nula.

## D-058 — controles preparados, sem execução real (2026-10-10)

Base deste patch: `7ce11ec0b9f7d179f8988719cd87fb84a7438679`, incluindo a correção de shadowing por `comfy_null`. A evidência medida pelo operador é preservada no lote `20261010T162735Z_1b40ed495243`: Klein `INCONCLUSIVE:null_distribution_not_credible`, suporte21, skin18, background22, hair_face19, occluders23. Nenhuma GPU, servidor ComfyUI real ou `Generate` foi executado neste patch.

Revisão adversarial focada:

- Comparação CPU contra a implementação do HEAD base: as quatro geometrias normativas, suportes e reprojeções são idênticos, inclusive byte a byte em pixels sintéticos aleatórios. Pins e parâmetros normativos anteriores permanecem; funções `distribution`, `tolerance`, `validate_ceiling`, `generate_r1ei` e `generate_fashn` têm AST inalterada.
- Os quatro workflows novos têm SHA256; a fonte `ImageCrop` também foi pinada. Resample-only não resolve VAE nem exige seu sidecar; native continua exigindo VAE/evidência e compressão correta. O crop central720×1536 segue o offset inteiro do código pinado: `[2,0,722,1536]`; paste sem resize.
- Regressões verificam inversos idênticos de Klein/QIE resample-only, R1-EI996→1024→996 no worker e ausência de resize adicional no supervisor. VAE e sampler não são executados em testes.
- Testes de lifecycle simulam os nove runs na ordem exata, uma ou várias rotas INCONCLUSIVE, retorno final3 e batch INCONCLUSIVE; erro operacional posterior ainda interrompe/exit1 e preserva a inconclusão anterior. Todos os cinco controles aceitam estatística30 sem chamar o teto, registrando `normative:false` e sem servir de calibração.
- O JSON diagnóstico é recusado pelo auditor já existente por `kind=O_null1_diagnostic`; nenhum código do auditor, FREEZE, gate ou DD foi alterado. D-059 não estava registrada neste checkout e nenhuma regra foi inferida ou modificada.
- Corrigida somente a expectativa de caminho absoluto de um teste de isolamento já presente no HEAD, para execução no Windows; isolamento do launcher preservado. Metadados dos controles são gravados também nos sidecars de falha.
- Os35 arquivos do lote medido foram conferidos por SHA256 antes e depois do patch, sem alteração. O manifesto registra os hashes originais de batch, sidecar e null_stats; não reescreve a evidência antiga.

Validação: **14 scripts CPU, 381 casos/checks, todos exit0, sem SKIP**. Inclui `test_null1`22/22, `test_null1_diagnostics`10/10 e todos os scripts anteriores. `orchestrate.py --mode Verify` e `run_null1.ps1 -Mode Plan` no PowerShell5.1 passaram; `git diff --check` passou. A suíte completa usa o mesmo comando e clones pinados descritos acima.

Controles reais seguem **PREPARADOS, NÃO MEDIDOS**. Testes CPU não comprovam sua execução GPU futura nem alteram a rejeição normativa da Klein. Parada no commit para revisão do Claude.
