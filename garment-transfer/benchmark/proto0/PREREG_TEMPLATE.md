# PREREG — Prototype 0 (ADDITION / OCCUPANCY STRESS TEST) — pré-registro

> Preencher e **commitar ANTES do primeiro run** como `benchmark/proto0/PREREG.md`; `freeze_tag` (ex.: `proto0-frozen-v1`) aponta para o commit com as máscaras congeladas e este arquivo. **Congelamento verificável:** `tools/freeze_proto0.py` escreve `benchmark/proto0/FREEZE.json` com o sha256 de `PREREG.md`, de `proto0_cases.jsonl`, de `g0_case_roles.json` e de **cada arquivo referenciado** pelo manifesto (A, B, máscaras, GT), mais o commit git e o `freeze_tag`. O auditor recebe `--prereg benchmark/proto0/PREREG.md` e **calcula o sha256 ele mesmo** (nenhum hash é passado à mão) e verifica `FREEZE.json` (`--freeze benchmark/proto0/FREEZE.json`) **antes de avaliar qualquer coisa**; qualquer divergência = `FAIL:frozen_reference_mismatch` para todos os casos do run. Alterações depois do primeiro run exigem novo PREREG (v2), novo `FREEZE.json` e justificativa no `DECISION_LOG`.

## 1. Hipóteses pré-registradas
- **H0** (casca de invariantes + envelope + ocupação medida) — redação em `docs/06` §3.
- **H11a** (noise_mask suave = blend linear por passo desacopla criar-roupa de reconstruir-A) · **H11b** (noise_mask + DifferentialDiffusion, níveis alinhados aos limiares do cronograma) · **H-DD4** ("em 4 passos, E2b ≈ E1 binária; só gradua em ≥ 20 passos") · **H-E4** ("scaffold de ocupação em pixel eleva `coverage_of_band_min` sem aumentar deriva fora do envelope vs E2") · **H-F2-skin** ("inpainters por máscara produzem pele em vez de tecido sobre torso nu em UNCERTAIN / BAND_MAX\BAND_MIN").
- Para cada hipótese: o que a falsifica (números abaixo).

## 2. Casos: conjunto core do gate G0, papéis e progressão (congelados em `benchmark/proto0/g0_case_roles.json`)

### 2.1 Os SEIS casos core (regra ≥ 4/6; EASY–HARD; 3 seeds)
Exatamente estes seis `case_id` contam para o gate G0 — nenhum outro, nenhuma substituição:

1. `proto0_easy_01`
2. `proto0_medium_01`
3. `proto0_hard_01`
4. `proto0_hard_02`
5. `proto0_hard_03`
6. `proto0_hard_05`

Critério de escolha (fixado antes de qualquer run): **independência** — nenhum par de casos core compartilha a mesma imagem A (`validate_manifest.py` verifica; `provenance.shares_A_with` declara quem compartilha A). `proto0_hard_04` usa a mesma A de `proto0_hard_03`, por isso é o **par de atribuição de manga**, julgado pelo auditor e reportado ao lado de `hard_03`, mas **não** conta nos 6.

**Nenhum conjunto de casos pode ser escolhido, trocado ou excluído depois de ver resultados.** Um caso core que se revele inválido (erro de anotação descoberto após o run) é reportado como tal e conta como **não-PASS** para todas as rotas; a correção entra só num PREREG v2 com novo run completo.

### 2.2 Papel de cada caso (todos os 19; `g0_case_roles.json` é a fonte, o validador exige papel para todo caso proto0)
| case_id | nível | papel | conta no 6? | o que mede / como é reportado |
|---|---|---|---|---|
| `proto0_easy_01` | EASY | `gate_core` | **sim** | criação sobre pele, sem oclusor; controla EASY→MEDIUM |
| `proto0_medium_01` | MEDIUM | `gate_core` | **sim** | FREE_SPACE lateral, móvel à frente da bainha; controla MEDIUM→HARD |
| `proto0_hard_01` | HARD | `gate_core` | **sim** | FRONT_OCCLUDERS (antebraço + mão), UNCERTAIN (axila) |
| `proto0_hard_02` | HARD | `gate_core` | **sim** | foreshortening, câmera baixa, manga longa segue o braço |
| `proto0_hard_03` | HARD | `gate_core` | **sim** | braços cruzados, B manga curta → `split_by_garment_edge` no braço superior esquerdo |
| `proto0_hard_05` | HARD | `gate_core` | **sim** | oclusor frontal independente (A distinta de todos os outros core) |
| `proto0_easy_02` | EASY | `replication` | não | replica EASY em outra pessoa; reportado ao lado de `easy_01` (sinal de generalização) |
| `proto0_easy_01_pair_b` | EASY | `attribution_fidelity` | não | mesma A de `easy_01`, B estampada do EXTREME → isola eixo B (fidelidade) |
| `proto0_hard_01_pair_b` | HARD | `attribution_pose_delta` | não | mesma A de `hard_01`, B em pose semelhante → isola eixo C (pose) |
| `proto0_hard_04` | HARD | `attribution_sleeve_pair` | não | mesma A de `hard_03`, B manga longa → `behind_must_cover`; a fronteira deve seguir a manga de B; reportado ao lado de `hard_03` |
| `proto0_extreme_01` | EXTREME | `extreme_report_only` | não | todos os eixos; só reporte, nunca entra no 4/6 |
| `proto0_gt_pair_01` | HARD | `ground_truth` | não | par autoproduzido com GT real (ocupação / z-order para H7′); métricas O vs GT − piso |
| `proto0_gt_layer_01` | HARD | `ground_truth` | não | GT real com peça mantida (interface KGI, `add_over_layer`) |
| `proto0_ctrl_noop_01` | EASY | `auditor_control` | não | `same_garment_noop` — **deve PASSAR** (calibra falso nascimento/resíduos) |
| `proto0_ctrl_negative_synth_01` | HARD | `auditor_control` | não | `hand_removed_synthetic` — **deve FALHAR** (duplicate_limb / keypoints) |
| `proto0_ctrl_identity_output_01` | HARD | `auditor_control` | não | `identity_output` (O := A) — **deve FALHAR** por não-criação |
| `proto0_ctrl_known_drift_01` | HARD | `auditor_control` | não | `known_drift_positive` (denoise 1,0 do sweep) — **deve FALHAR** por reconstrução |
| `proto0_ctrl_fabric_over_occluder_01` | HARD | `auditor_control` | não | `fabric_over_occluder_synthetic` — **deve FALHAR** z-order |
| `proto0_ctrl_b_leak_specificity_01` | HARD | `auditor_control` | não | `B_leak_specificity_probe` — **deve PASSAR** |

### 2.3 Progressão por nível (eixo A = "a peça nasceu": `coverage_of_band_min ≥ 0,9` **e** ΔE > p95 do no-op)
Um braço só avança quando cria a peça em **≥ 2 de 3 seeds** (`min_seeds_axis_A = 2`, `of_seeds = 3`) nos casos que controlam a transição:

| Transição | Casos que controlam | Regra |
|---|---|---|
| EASY → MEDIUM | `proto0_easy_01` | eixo A em ≥ 2/3 seeds (1 caso de 1) |
| MEDIUM → HARD | `proto0_medium_01` | eixo A em ≥ 2/3 seeds (1 caso de 1) |
| HARD → EXTREME | `proto0_hard_01`, `proto0_hard_02`, `proto0_hard_03`, `proto0_hard_05` | eixo A em ≥ 2/3 seeds em **≥ 2 dos 4** casos |

Braço que não cria a peça em EASY é rotulado **replace-only** e sai sem discussão de fidelidade. Os casos de controle do auditor rodam **antes** de qualquer caso real contar (§6).

### 2.4 Congelamento por caso (preencher; os hashes vivem em `FREEZE.json`, não aqui)
| case_id | anotador(es) | anotado em | inter-anotador IoU (BMIN / FO / EL) | GT? |
|---|---|---|---|---|
| … | | | | |

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
| **franja C3** (`contact_fringe_px` ao redor de G) | \|ΔL\| ≤ 12 **e** Δchroma ≤ 6 por pixel; ≤ 5 % dos pixels da franja violando; correlação de estrutura de gradiente (A vs O′ na franja) ≥ 0,6 | provisório — recalibrar com a nula; muda só em PREREG v2 |
| **split_by_garment_edge** (por elemento) | cobertura de `split_must_cover_mask` por G ≥ 0,90; tecido sobre `split_must_stay_visible_mask` ≤ 0,02; identidade de `split_must_stay_visible_mask` ≥ limiar derivado da nula; **zona de fronteira** (elemento ∩ UNCERTAIN): cada pixel é G **ou** idêntico a A (dentro de τ_null) — nada intermediário | provisório (cobertura/tecido); nula (identidade) |
| **fidelidade à peça** (`tools/garment_fidelity_audit.py`) | adjudicação **cega** dos atributos congelados em `expected.garment_attributes` (humano, saídas por hash): **categoria eliminatória**; distância cromática em Lab entre G em O′ e `expected.b_garment_mask` em B ≤ 12 (mediana por região; provisório); DINOv2 cos-sim (G em O′ vs peça em B) **acima da baseline de peça aleatória** — só reporte, não decide | provisório / baseline medida no próprio run |
| **tol_engine** (identidade de pixel em O′) | p99,5 de \|A_ref − A\| por zona (`--a-ref`, O_null1) | nula |
| **tol_composed** (identidade de pixel em O) | **0** — contrato exato em PROTECTED (`frozen_annotation.protected_mask` = `<case>_PR.png`, resolvido do manifesto) e núcleo dos oclusores | contrato (`docs/00` §4) |

## 6. Regra de agregação
- Por caso: **mediana sobre seeds** decide; reportar também a **pior seed**.
- `tools/g0_gate.py` aplica as regras de `g0_case_roles.json` (core 4/6, progressão §2.3, papéis) sobre os JSONs do auditor — nenhuma contagem é feita à mão. **PASS de ocupação (`occupancy_audit.py`) sozinho NÃO é PASS do caso:** o caso só passa se `garment_fidelity_audit.py` também der PASS (categoria correta e cromaticidade dentro do limiar de §5) na **mesma seed**; falha de fidelidade com ocupação boa é reportada como **FALHA-FIDELIDADE** e conta como não-PASS no 4/6.
- Por rota × mecanismo: critérios PASS / FALHA-CRIAÇÃO / FALHA-OCLUSÃO / FALHA-ACOPLAMENTO de `docs/06` §7 sobre os **seis casos core** de §2.1 (≥ 4/6); EXTREME, pares de atribuição, replicação e GT reportados à parte, nunca somados ao 4/6.
- Controles obrigatórios do auditor (`identity_output`, `known_drift_positive`, `fabric_over_occluder_synthetic`, `hand_removed_synthetic`) **devem falhar**; `same_garment_noop` e `B_leak_specificity_probe` **devem passar** — antes de qualquer caso real contar. Se um controle sair errado, o run inteiro é INCONCLUSIVO para aquela rota.

## 7. Avaliação humana cega
- Saídas renomeadas por hash (rota/seed ocultos), ordem aleatória, formulário fixo (perguntas sim/não/ambíguo por elemento — as mesmas do auditor), catch trials (A inalterada; falha sintética óbvia), avaliador e data registrados; concordância se houver 2.º avaliador.

## 8. Análise prevista e consequências
- Curva criação × preservação por mecanismo (eixos A e E) com E1′/E1″ como extremos.
- Tabela rota × eixo (A–E) em O′ e O.
- Consequências pré-declaradas: ver `docs/06` §7 (critérios) e §10 (gate G0).
