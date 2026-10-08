# PREREG — Prototype 0 (ADDITION / OCCUPANCY STRESS TEST) — pré-registro

> Preencher e **commitar ANTES do primeiro run**; `freeze_tag` (ex.: `proto0-frozen-v1`) aponta para o commit com as máscaras congeladas e este arquivo. O auditor grava o sha256 deste PREREG no JSON (`--prereg-sha`). Alterações depois do primeiro run exigem novo PREREG (v2) e justificativa no `DECISION_LOG`.

## 1. Hipóteses pré-registradas
- **H0** (casca de invariantes + envelope + ocupação medida) — redação em `docs/06` §3.
- **H11a** (noise_mask suave = blend linear por passo desacopla criar-roupa de reconstruir-A) · **H11b** (noise_mask + DifferentialDiffusion, níveis alinhados aos limiares do cronograma) · **H-DD4** ("em 4 passos, E2b ≈ E1 binária; só gradua em ≥ 20 passos") · **H-E4** ("scaffold de ocupação em pixel eleva `coverage_of_band_min` sem aumentar deriva fora do envelope vs E2") · **H-F2-skin** ("inpainters por máscara produzem pele em vez de tecido sobre torso nu em UNCERTAIN / BAND_MAX\BAND_MIN").
- Para cada hipótese: o que a falsifica (números abaixo).

## 2. Casos (ids e sha256 do manifesto congelado)
| case_id | nível | sha256 do manifesto (linha) | GT? | anotador | inter-anotador IoU (BMIN / FO) |
|---|---|---|---|---|---|
| … | | | | | |

## 3. Rotas, braços e seeds
| Rota | Braços | Seeds | Resolução | Observações |
|---|---|---|---|---|
| R1 klein 4B fp8 | E0′, E1, E1′, E1″, E2a, E2b | 1,2,3 | 1024 lado maior | guidance fixo 1.0, 4 passos |
| R1-EI klein-base-4B + Easy-Insert | E4 | 1,2,3 | 1024² (recorte) | 15 passos (NV); medir frio |
| R3 FASHN 1.5 | seg-free; mascarado | 1,2,3 | ≤ 576×864 | só auditoria em O′ |
| R2 QIE-2511 Q5 | E0 (sweep), E0′, E2b, E4, E3 (depth MoGe como ref.; patch Blockwise NV) | 1 (2 se couber) | 544×960 | sob H4 |
| R4 CatVTON | máscara desenhada = envelope \ FO; B plana e B vestida recortada; política a/b/c | 1,2,3 | 1024×768 | NC |
| R8 two-pass FASHN→klein | — | 1,2,3 | — | máscara derivada de O′_FASHN só para gerar |

## 4. Distribuição nula (antes de qualquer veredito)
- `O_null1` = VAE encode/decode de cada A (denoise 0, mesma resolução interna e reprojeção) por rota.
- `O_null2` = pipeline completo em `same_garment_noop`.
- Registrar |O_null − A| por zona (pele, fundo, oclusores): **τ_null = p99,5**; `min_*_identity = (1 − fração acima de τ_null na nula) − margem`; ΔE mínimo em BAND_MIN = p95 do no-op. Publicar em `runs/proto0/null/`.

## 5. Limiares (valores exatos usados, com origem)
| Métrica | Limiar | Origem |
|---|---|---|
| coverage_of_band_min | ≥ 0,90 | provisório; nunca mais apertado que (1 − IoU inter-anotador de BMIN) |
| band_min_change_magnitude (ΔE) | > p95 no-op | nula |
| garment_over_element (front_certain) | ≤ 0,02 | provisório |
| occluder_mask_iou | ≥ 0,90 | provisório; calibrar no controle `hand_removed_synthetic` |
| hand_keypoint_shift | ≤ … | calibrado no controle negativo |
| unchanged_in_band_without_garment / uncovered_coverable_identity | ≥ … | derivado da nula |
| excess_forbidden_frac | ≤ 0,02 | provisório |

## 6. Regra de agregação
- Por caso: **mediana sobre seeds** decide; reportar também a **pior seed**.
- Por rota × mecanismo: critérios PASS / FALHA-CRIAÇÃO / FALHA-OCLUSÃO / FALHA-ACOPLAMENTO de `docs/06` §7 sobre os casos EASY–HARD (≥ 4/6); EXTREME reportado à parte.
- Controles obrigatórios do auditor (`identity_output`, `known_drift_positive`, `fabric_over_occluder_synthetic`, `hand_removed_synthetic`) **devem falhar**; `same_garment_noop` e `B_leak_specificity_probe` **devem passar** — antes de qualquer caso real contar.

## 7. Avaliação humana cega
- Saídas renomeadas por hash (rota/seed ocultos), ordem aleatória, formulário fixo (perguntas sim/não/ambíguo por elemento — as mesmas do auditor), catch trials (A inalterada; falha sintética óbvia), avaliador e data registrados; concordância se houver 2.º avaliador.

## 8. Análise prevista e consequências
- Curva criação × preservação por mecanismo (eixos A e E) com E1′/E1″ como extremos.
- Tabela rota × eixo (A–E) em O′ e O.
- Consequências pré-declaradas: ver `docs/06` §7 (critérios) e §10 (gate G0).
