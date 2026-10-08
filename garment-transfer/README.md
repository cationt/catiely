# Garment Transfer Local com Preservação Rigorosa

Sistema (em investigação) para: dada **A** (pessoa-alvo) e **B** (roupa de referência, inclusive vestida em outra pessoa), produzir uma fotografia convincente da **mesma pessoa de A, na mesma pose, câmera e cena**, usando a peça de **B** — tudo local, em RTX 5070 12 GB + ~16 GB RAM, ≤ 60 min por imagem, orquestrado por ComfyUI Desktop.

Estado atual (2026-10-07): **Fases 0–4 entregues em forma documental** — contrato formal, estado da arte com fontes, comparação de famílias, viabilidade **estimada** (nenhuma medição no hardware-alvo ainda) e shortlist **provisória** (casca de preservação + motores R1 FLUX.2 klein 4B / R2 Qwen-Image-Edit-2511 condicional / R3 FASHN VTON 1.5 / R4 try-off→VTON por máscara). Nenhum protótipo foi executado; nenhum workflow de produção existe. Ver `docs/CHECKPOINT.md` e `docs/DECISION_LOG.md`.

## Mapa

| Caminho | Conteúdo |
|---|---|
| `docs/00_formulacao_contrato.md` | Contrato formal: entradas, saída, autoridade de A/B, classes C1–C5, informação ausente, eliminatórias, tempo, observabilidade, QA, ambiguidades, metas. |
| `docs/01_estado_da_arte.md` | Pesquisa (data de corte registrada) com fontes e níveis de evidência. |
| `docs/02_familias_arquiteturais.md` | Mecanismos causais, 15 perguntas por candidata, matrizes de capacidade e viabilidade. |
| `docs/03_viabilidade_local.md` | Orçamento de memória/tempo, suporte Blackwell/Windows/ComfyUI, offload/precisão, elegibilidade. |
| `docs/04_selecao_provisoria.md` | Shortlist, hipóteses falsificáveis, alternativas, critérios de abandono. |
| `docs/05_plano_prototipos.md` | Protocolo dos protótipos A–H e ablações. |
| `docs/DECISION_LOG.md`, `docs/CHECKPOINT.md` | Decisões rastreáveis e estado para continuidade. |
| `benchmark/` | Schema do manifesto, matriz de cobertura, validadores. Imagens não redistribuíveis ficam só como manifesto. |
| `tools/` | `inventory_windows.ps1` (inventário do alvo), `measure_run.py` (tempo/VRAM/RAM/commit com deadline), `pixel_preservation_check.py` (auditoria C1), `memory_budget.py` (estimativas, nível ESTIMADO). |
| `research_raw/` | Relatórios brutos dos levantamentos, com URLs consultadas. |

## Níveis de evidência usados em todos os documentos

`MEDIDO NO HARDWARE-ALVO` · `REPRODUZIDO EM OUTRO HARDWARE` · `REPORTADO EM FONTE PRIMÁRIA` · `ESTIMADO (hipóteses)` · `INFERÊNCIA ARQUITETURAL` · `DESCONHECIDO`.
Para produtos proprietários: `PUBLIC FACT` vs `ARCHITECTURAL INFERENCE`.
