# CHECKPOINT — estado do projeto para continuidade (2026-10-08, após red-team completo + patch review do harness)

## Onde estamos
Fases 0–4 entregues **e revisadas adversarialmente** (`docs/06_RED_TEAM_REVISION.md` §1–§11). Uma **auditoria externa do harness** (commit `48041a5`) encontrou 14 blockers metodológicos antes do primeiro run; todos foram corrigidos e cobertos por testes (`06` §12, D-036…D-046); uma **segunda rodada adversarial** (8 lentes) derrubou mais 20 pontos, também corrigidos e testados (`06` §12.1, D-047). **Nenhum protótipo executado; nenhum modelo instalado; nenhuma imagem gerada; nenhuma medição padronizada no hardware-alvo** (existe evidência histórica não padronizada, `03` §1b). A decisão estrutural D-008 continua **rebaixada a hipótese H0**; o primeiro experimento real é o **Prototype 0 — ADDITION / OCCUPANCY STRESS TEST** (Gate G0), que agora tem seis casos core congelados e um harness que **impede PASS com evidência obrigatória ausente**.

## Estado por componente

| Componente | Estado | Medido | Estimado | Não resolvido |
|---|---|---|---|---|
| Contrato (`00`) | revisado: três campos; C1–C5 vocabulário de auditoria; auditoria dupla O′/O; regra da banda com franja C3 **limitada** (não isenta); definição operacional de "tecido da peça" = (i)+(ii) em `occupancy_audit` + (iii) em `garment_fidelity_audit` | — | tolerâncias O1/O2/O4/O5/O11 | O3 reformulada; O12 política de oclusor |
| SOTA (`01`, `research_raw/`) | revisado: níveis de evidência corrigidos em 7 clusters (`research_raw/07`) | — | — | itens NV listados em `01` §12 e `07` |
| Famílias (`02`) | revisado: casca = hipótese H0; motores = candidatos sem "principal" | — | pose difícil `?` para todos | — |
| Viabilidade (`03`) | revisado: evidência histórica; estimador = triagem com bandas; `measure_run.py` mede commit **real** no Windows (`GetPerformanceInfo`, **confirmado no alvo**) | **R1 klein 4B medido** (§1d: 31,8 s frio; 11,6 GB VRAM) | demais rotas | R1-EI, R3, R2, R4 ainda não medidos |
| Seleção (`04`) | revisado: H0; canal por rota; H7′, H11–H13; Prototype 0 antes de A; QA dupla com três auditores | — | — | H4 (QIE tempo); trilha de licença O10 |
| Plano de protótipos (`05`) | revisado: Prototype 0 primeiro; seis casos core nomeados | — | — | casos `dev` ainda não coletados |
| Red-team (`06`) | completo (§1–§11) + **§12 patch review** (B-01…B-14) | — | — | refutação adversarial independente dos achados de lente ainda parcial (D-035) |
| Benchmark | schema **v6** (`shares_A_with`; `split_must_cover/stay_visible` obrigatórias em split; `b_garment_mask`; `protected_mask`; `consent_record_id` exigido para self-captured); validador **v3** (`--roles`, reuso de máscaras só do arquivo do dono e B-dependentes só com a mesma B, placeholders ampliados, consentimento sem bypass, papéis G0 com `of == 6` e ≥ 3 seeds, `--check-files` abre os PNGs); **19 casos proto0** corrigidos (hard_03/04 com A própria e z-order de manga longa; gt_* com máscaras próprias) — 0 erros com `--allow-placeholders`, 543 placeholders → **NÃO CONGELADO**; `g0_case_roles.json` (6 core: easy_01, medium_01, hard_01, hard_02, hard_03, hard_05); `PREREG_TEMPLATE.md` §2 com casos/papéis/progressão | — | — | imagens, máscaras por elemento, GT e `FREEZE.json` ainda não produzidos; 2 anotadores; tag `proto0-frozen-v1` |
| Ferramentas | `occupancy_audit.py` **v5** (evidência obrigatória por manifesto; NOT_APPLICABLE vs MISSING_REQUIRED_EVIDENCE; `tol_engine` da nula / `tol_composed = 0`; franja C3 limitada; split julgável; proveniência: `--prereg` arquivo, `--freeze` com árvore limpa/commit/tag, sha de A/B/máscaras/O′/G; franja congelada; adjudicação ligada à saída; máscaras estritamente binárias); `garment_fidelity_audit.py` (identidade da peça B; obrigatório); `freeze_proto0.py`/`freeze_check.py`; `g0_gate.py` (regras pré-registradas; reuso de runs, ≥ 3 seeds, O composto vinculante, integridade dos JSONs); `measure_run.py` (commit real/proxy declarado); `inventory_windows.ps1`; `pixel_preservation_check.py`; `memory_budget.py` | smoke tests CPU | — | execução no Windows/alvo; script dos limiares do DD por cronograma |
| Testes | `tests/run_all.py`: occupancy 65, fidelity 13, gate 17, validator 25, measure_run 18 checks — todos verdes | CPU | — | — |
| R1-EI (`tools/r1ei/`) | **preparado, não executado**: identidade do Easy-Insert verificada (`research_raw/08`, D-049); runner Diffusers sequencial bf16 com sidecar de proveniência; pins (`r1ei_manifest.json`, `requirements-r1ei.txt`); `setup_r1ei.ps1` / `bench_r1ei.ps1`; `tests/test_r1ei_static.py` (14) | — | VRAM ≈ 9–10,5 GB, RAM ≈ 8–9 GB (E) | execução no alvo; LoRA ModelScope NV; capacidade em roupa NV |
| Workflows ComfyUI / custom nodes | **não existem** (por decisão) | — | — | só após Prototype 0 |

## O que foi medido
- **R1 — FLUX.2 klein 4B fp8, A+B, ~1 MP, 4 passos (`klein4b_fp8_2ref_1mp`), MEDIDO NO HARDWARE-ALVO (2026-10-08):** cold mediana **31,8 s** (n=3), warm **17,1 s** (n=3; 9,1–31,3 s), VRAM pico ≈ **11,6 GB**, commit ≈ 29–30 GB, 6/6 exit 0 sem OOM — elegível por tempo; viabilidade de R1 **fechada** (`03` §1d; D-048; `benchmark/measurements/klein4b_fp8_2ref_1mp.json`).
- Histórico não padronizado: QIE-2511 Q5 @~544×960 ≈ 10–15 min/imagem; sweep de denoise 0.18–1.00 (`03` §1b).

## O que permanece estimado
VRAM/RAM/tempo de todas as rotas; VRAM de FASHN (não declarada); valores do mapa de autoridade (0.7/0.5/0.3) e r_C3; limiares de franja (|ΔL*| ≤ 12, Δchroma ≤ 6), de cromaticidade (12 / 0,40) e de split — **provisórios até a calibração na nula e no `same_garment_noop`**.

## O que não foi resolvido
- H0/H11a/H11b/H-E4: se blend linear, liberação temporal (4 degraus em destilados) ou scaffold em pixel desacoplam criar-roupa de reconstruir-A.
- Capacidade do Easy-Insert em roupa/adição — NV. Compatibilidade do patch Blockwise com Edit-2511; templates KleinBase4B — NV.
- z-order `uncertain` indecidível a priori (cabelo vs gola; cós vs bainha).
- Confiabilidade do segmentador G sobre tecido alucinado (calibração obrigatória; sub-segmentação de G aparece como violação de franja).
- Identidade de peças acromáticas (branco vs preto) não é separável por cromaticidade; depende da adjudicação cega de atributos.
- Licenças: FASHN parser NC; SAM/DINOv3 proprietárias revogáveis; SegFormer-B2-clothes herança NVIDIA; intenção de uso (O10).
- Nenhum benchmark externo com GT real de adição sobre pele em pose difícil.

## Próximo passo imediato (exige a máquina-alvo)
**R1-EI — viabilidade** (`tools/r1ei/README.md`): rodar `setup_r1ei.ps1 -A <A> -B <B>` (venv, torch CUDA, deps pinadas, clone pinado, ≈ 16 GB de pesos do HF com sha256, dry-run) → revisar o output → só então `bench_r1ei.ps1` (cold×3/warm×3 com `measure_run.py`) → registrar em `03` §1e / `benchmark/measurements/`. Nada de G0, E1/E2, nula, FASHN ou QIE antes disso.

## Como retomar
1. Ler `docs/06_RED_TEAM_REVISION.md` §6–§10 e **§12**, `docs/04_selecao_provisoria.md` §7 e `benchmark/proto0/PREREG_TEMPLATE.md`.
2. Rodar `tools/inventory_windows.ps1` no alvo; medir klein 4B, klein-base-4B + Easy-Insert, FASHN 1.5 e QIE-2511 Q5 (mesma A/B do sweep) com `measure_run.py` em frio (confirmar `commit_measurement.source == GetPerformanceInfo`); medir a **distribuição nula** por rota (`03` §7b) → `--a-ref`/`--null-stats`; imprimir os limiares do DD por cronograma.
3. Produzir imagens, máscaras por elemento (2 anotadores), `_BG`, `_PR`, split masks e GT dos 19 casos `proto0`; preencher atributos (sem placeholders) e `consent_record_id`; `validate_manifest.py --check-files` (0 placeholders); preencher `PREREG.md`; `tools/freeze_proto0.py --tag proto0-frozen-v1` → `FREEZE.json`; commit + tag.
4. Validar o auditor: `tests/run_all.py` verde; controles reais (`identity_output`, `known_drift_positive`, `fabric_over_occluder_synthetic`, `hand_removed_synthetic` devem FALHAR; `same_garment_noop`, `B_leak_specificity_probe` devem PASSAR); sweep histórica anotada; calibrar limiares provisórios na nula.
5. Executar o Prototype 0 (Gate G0) por nível (EASY primeiro; progressão por `g0_case_roles.json`); para cada caso × seed rodar `occupancy_audit.py` **e** `garment_fidelity_audit.py` (perfil g0, `--manifest --case-id --prereg --freeze --roles`); agregar com `tools/g0_gate.py`; registrar em `DECISION_LOG.md`.
