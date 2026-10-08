# Garment Transfer Local com Preservação Rigorosa

Sistema (em investigação) para: dada **A** (pessoa-alvo) e **B** (roupa de referência, inclusive vestida em outra pessoa), produzir uma fotografia convincente da **mesma pessoa de A, na mesma pose, câmera e cena**, usando a peça de **B** — tudo local, em RTX 5070 12 GB + ~16 GB RAM, ≤ 60 min por imagem, orquestrado por ComfyUI Desktop.

Estado atual (2026-10-08): **Fases 0–4 entregues e revisadas adversarialmente** (`docs/06`) — contrato formal, estado da arte com fontes, comparação de famílias, viabilidade **estimada** (nenhuma medição no hardware-alvo ainda) e shortlist **provisória** (casca de preservação + motores R1 FLUX.2 klein 4B / R2 Qwen-Image-Edit-2511 condicional / R3 FASHN VTON 1.5 / R4 try-off→VTON por máscara). Nenhum protótipo foi executado; nenhum workflow de produção existe. Ver `docs/CHECKPOINT.md` e `docs/DECISION_LOG.md`.

## Mapa

| Caminho | Conteúdo |
|---|---|
| `docs/00_formulacao_contrato.md` | Contrato formal: entradas, saída, autoridade de A/B, classes C1–C5, informação ausente, eliminatórias, tempo, observabilidade, QA, ambiguidades, metas. |
| `docs/01_estado_da_arte.md` | Pesquisa (data de corte registrada) com fontes e níveis de evidência. |
| `docs/02_familias_arquiteturais.md` | Mecanismos causais, 15 perguntas por candidata, matrizes de capacidade e viabilidade. |
| `docs/03_viabilidade_local.md` | Orçamento de memória/tempo, suporte Blackwell/Windows/ComfyUI, offload/precisão, elegibilidade. |
| `docs/04_selecao_provisoria.md` | Shortlist, hipóteses falsificáveis, alternativas, critérios de abandono. |
| `docs/05_plano_prototipos.md` | Protocolo dos protótipos A–H e ablações. |
| `docs/06_RED_TEAM_REVISION.md` | **Revisão adversarial** (2026-10-08): 46 falhas, 26 correções de fontes, D-008 → hipótese H0, três campos espaciais, contrato de oclusão, Prototype 0 (ADDITION / OCCUPANCY STRESS TEST), taxonomia de canais, metodologia anti-autoengano, próximo gate; §12 **patch review pós-auditoria externa** (14 blockers do harness corrigidos e testados) e §12.1 segunda rodada adversarial (20 pontos). |
| `docs/DECISION_LOG.md`, `docs/CHECKPOINT.md` | Decisões rastreáveis (D-001…D-050) e estado para continuidade. |
| `benchmark/` | Schema do manifesto, matriz de cobertura, validadores. Imagens não redistribuíveis ficam só como manifesto. |
| `tools/` | `inventory_windows.ps1` (inventário do alvo; detecta Comfy-Desktop), `measure_run.py` (tempo/VRAM/RAM; commit real via `GetPerformanceInfo` no Windows, proxy declarado fora dele), `pixel_preservation_check.py` (auditoria C1), `memory_budget.py` (triagem grosseira com bandas), `occupancy_audit.py` v5 (ocupação/visibilidade/z-order não circular, alvos O′/O, evidência obrigatória por manifesto, franja C3 limitada, split por bainha), `garment_fidelity_audit.py` (identidade da peça B — obrigatório no G0), `freeze_proto0.py`/`freeze_check.py` (FREEZE.json e verificação de proveniência), `g0_gate.py` (regras pré-registradas do gate sobre os 6 casos core). |
| `tools/r1ei/` | **R1-EI** (klein-base-4B + Easy-Insert): identidade verificada, manifesto de pins (commit, revisões HF, sha256), runner Diffusers sequencial bf16 (`run_easy_insert.py`), máscaras de viabilidade, `setup_r1ei.ps1` / `bench_r1ei.ps1`, protocolo e diferenças vs klein4b (`README.md`). Medição ainda não executada. |
| `benchmark/measurements/` | registros legíveis por máquina das medições no hardware-alvo (`klein4b_fp8_2ref_1mp.json`). |
| `tests/` | `run_all.py` roda tudo (CPU): `test_occupancy_audit.py` (65), `test_garment_fidelity_audit.py` (13), `test_g0_gate.py` (17), `test_validate_manifest.py` (25), `test_measure_run.py` (18 checks), `test_r1ei_static.py` (14). |
| `benchmark/proto0/` | Casos do Prototype 0 (`proto0_cases.jsonl`, 19), papéis congelados (`g0_case_roles.json`: 6 core), anotações por elemento, `PREREG_TEMPLATE.md`, `FREEZE.json` (gerado no congelamento). |
| `research_raw/` | Relatórios brutos dos levantamentos, com URLs consultadas; `08_easy_insert_verificacao.md` = verificação primária do Easy-Insert/klein-base/stack. |

## Níveis de evidência usados em todos os documentos

`MEDIDO NO HARDWARE-ALVO` · `REPRODUZIDO EM OUTRO HARDWARE` · `REPORTADO EM FONTE PRIMÁRIA` · `ESTIMADO (hipóteses)` · `INFERÊNCIA ARQUITETURAL` · `DESCONHECIDO`.
Para produtos proprietários: `PUBLIC FACT` vs `ARCHITECTURAL INFERENCE`.
