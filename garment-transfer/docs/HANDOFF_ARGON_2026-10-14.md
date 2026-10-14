# Handoff técnico da W3 para avaliação arquitetural independente

Preparado em 2026-10-14 pelo responsável pelas decisões arquiteturais registradas até D-059c (Claude), a pedido do operador, para o avaliador independente (Gemini 4 Argon). Estado descrito: branch `claude/eloquent-cray-17bgqp` em `bcce403` (último commit de decisão, D-059c); este documento entra em commits de docs posteriores e não altera `tools/`, `tests/` nem outros docs. Rascunho verificado contra as fontes por três revisores automatizados independentes; as correções estão incorporadas.

Este documento não defende a arquitetura. Transfere contexto: o que foi medido, o que foi decidido e por quê, o que eu interpreto, o que continua aberto. Toda afirmação carrega uma marca:

- **[F]** fato experimental medido no hardware-alvo ou fato de repositório verificável no checkout.
- **[D]** decisão registrada (DECISION_LOG, docs).
- **[I]** interpretação ou juízo meu, incluindo os motivos não escritos nos documentos.
- **[Q]** questão em aberto, risco ou lacuna admitida.
- **[NV]** não verificado; **[LIM]** limitação do meu conhecimento.

Fontes primárias no repositório: `docs/00_formulacao_contrato.md` (contrato), `01_estado_da_arte.md` + `research_raw/01–09`, `02_familias_arquiteturais.md`, `03_viabilidade_local.md` (medições e §7b nulas), `04_selecao_provisoria.md` (rotas e hipóteses), `05_plano_prototipos.md`, `06_RED_TEAM_REVISION.md`, `AUDITOR_V7_CONTRACT.md`, `DECISION_LOG.md` (D-001…D-059c), `CHECKPOINT.md`; `benchmark/` (manifesto proto0, PREREG, papéis, medições); `tools/` (auditores, harness de medição, rotas R1-EI/R2/R3, `null1/`, `null_geometry.py`); `tests/`.

---

## 1. Objetivo central e restrições

**[D]** Dadas A (foto da pessoa-alvo) e B (foto da peça de referência, caso central: vestida por outra pessoa), produzir O: a mesma pessoa de A, mesma pose, câmera e cena, vestindo a peça de B. Formulado como edição contrafactual condicionada: A é evidência sobre pessoa e cena; B é evidência sobre a peça; a peça muda de configuração espacial para caber em A; a pessoa de A nunca vira a pessoa de B (`00` §3).

**[D]** Restrições duras: execução 100 % local em RTX 5070 12 GB + 16 GB RAM + Windows 11 orquestrada por ComfyUI Desktop; ≤ 3600 s por imagem contando carga de pesos, QA e exportação; nenhuma dependência de nuvem ou API para gerar, analisar ou avaliar; adultos, conteúdo não explícito; A/B/resultados nunca saem da máquina (`00` §7, §12). Saída em PNG sem perda no canvas exato de A, com relatório R em JSON (PASS/FAIL/INCONCLUSIVO); sem candidato aprovado dentro do orçamento, a saída padrão é rejeição explícita (D-003, `00` §2).

**[D]** Contrato de autoridade: A manda em identidade, rosto, cabelo, corpo, pose, mãos, câmera, iluminação global e fundo; B manda em categoria, construção, caimento relativo, estampa e material da peça; a silhueta fotografada de B e a silhueta da roupa antiga de A não são coisas a preservar (`00` §4.1). O vetor de qualidade tem quatro eixos não agregados (preservação de A, fidelidade a B, coerência física, realismo) com falhas eliminatórias antes de qualquer Pareto (`00` §6).

**[I]** O projeto é uma investigação de viabilidade com disciplina de pré-registro, não um produto. Saídas de motor existem apenas como subproduto das medições de viabilidade (p.ex. 6 PNG do R1-EI, 12 do R3, 9 do R2; `CHECKPOINT` "as 6 saídas PNG de viabilidade não foram avaliadas"), **nenhuma foi avaliada por qualidade nem passou pelo harness**; o que existe é contrato, metodologia, ferramentas, medições de custo e pisos de reconstrução. Contexto: o volume de método acumulado precede qualquer avaliação de qualidade.

---

## 2. Evolução da arquitetura, por eras

### 2.1 Formulação (D-001…D-007, 2026-10-07)

**[D]** Contrato semântico com classes C1–C5 (preservado, ocupação da peça, efeitos locais inevitáveis, recém-exposto, incerto), `region_contract` congelado antes da geração, convenção inicial de 1024 px no lado maior com reprojeção ao canvas de A, metas por estrato (EASY ≥ 80 %, MEDIUM ≥ 60 %, HARD ≥ 35 %, EXTREME ≥ 15 %) e regra de níveis de evidência: nada medido fora do alvo conta como viabilidade (D-007).

### 2.2 Pesquisa e seleção provisória (D-008…D-013)

**[F]** Seis levantamentos paralelos com verificação em fonte primária onde o proxy permitiu (GitHub acessível; arXiv, HF web, sites de fabricantes bloqueados em 2026-10-07; `01` L5). Conclusões: nenhum gerador aberto preserva A por mecanismo; o único dado no alvo era um sweep histórico não padronizado de QIE-2511 Q5 a ~0,5 MP (10–15 min/imagem; denoise global ≤ 0,5 não cria a peça; 0,7–0,8 cria com geometria errada e A razoavelmente preservada; 1,0 cria mais forte e A deriva; `03` §1b, incorporado formalmente em D-021 durante o red team).

**[D]** D-008 propôs a arquitetura em duas camadas: casca de preservação (partição C1–C5 congelada + composição determinística + QA) com motor de síntese substituível. D-009 fixou a primeira shortlist (R1 klein 4B "principal"). D-010 relegou warp/correspondência (F5) a condicionamento e auditoria e descartou 3D + simulação (F6) nesta fase. D-012 descartou sem protótipo FLUX.2 dev, Step1X-Edit, HiDream-E1, IDM-VTON, Hunyuan 3.0, Emu3.5 e WSL2.

### 2.3 Red team (D-014…D-035, 2026-10-08)

**[F]** `06` registra 46 achados sobre a formulação (17 de severidade A), 26 sobre fontes, depois 14 blockers de auditoria externa do harness (B-01…B-14, commit `48041a5`; B-01…B-12 com teste de regressão, B-13/B-14 são correções documentais e da própria suíte) e 20 achados de uma segunda rodada adversarial (V-01…V-20, todos com teste de regressão) (`06` §1, §12, §12.1).

**[D]** Mudanças estruturais forçadas pelo red team:

- **D-008 rebaixada a hipótese H0** (D-014). Motivo: a partição C2 congelada é circular, porque a área da peça só existe depois do caimento (F-01), e um rótulo por pixel não expressa oclusão: "a mão é C1 e o tecido nasce atrás dela" (F-04).
- **Três campos espaciais** em vez de uma classe por pixel (D-016, D-025): autoridade de reconstrução graduada R(p) ∈ [0,1]; autorização de ocupação (BAND_MIN deve, BAND_MAX_BODY/FREE_SPACE podem, UNCERTAIN); z-order por elemento (front_certain, behind_must_cover, behind_may_cover, split_by_garment_edge, uncertain). C1–C5 vira vocabulário de auditoria (`00` §4.2-R, §4.5).
- **Prototype 0 (ADDITION / OCCUPANCY STRESS TEST) antes do Protótipo A** (D-017; registrado como pedido do usuário + F-03): medir primeiro se algum motor cria uma peça inteira onde A não veste nada da categoria, em pose difícil, com oclusão correta, antes de investir em preservação.
- **Shortlist sem "motor principal"** (D-020): R1 klein 4B = candidato prioritário/baseline barato; R2 QIE-2511 = prioritário para adição sob H4; R3 FASHN 1.5 = prioritário para adição, não permissivo (parser NVIDIA NC) e cego à representação; R4 try-off→VTON como comparador NC; R1-EI klein-base-4B + Easy-Insert = candidato prioritário permissivo para adição e motor do braço E4, scaffold em pixel (D-031, D-032).
- **Taxonomia de canais de ligação** (D-031): `noise_mask` suave = blend linear por passo (E2a) é mecanismo distinto de `noise_mask` + DifferentialDiffusion = liberação temporal (E2b, que em 4 passos discretiza em ≤ 4 instantes; H-DD4); scaffold em pixel (E4). ControlNet não existe para klein 4B nem Edit-2511 (verificado em `comfy/controlnet.py`, D-028).
- **Metodologia anti-autoengano** (D-033): distribuição nula por rota, definição operacional de "ocupado por tecido" (G independente + mudança real acima do piso nulo + identidade da peça), congelamento verificável por sha, PREREG por protótipo, controles do auditor que devem falhar/passar antes de qualquer caso real.
- **Reclassificação do sweep histórico** (D-029): mede o eixo temporal (img2img/SDEdit), não a capacidade de QIE-2511; denoise global < 1,0 proibido como rota, só baseline E0.

**[Q]** D-035 registra que a refutação adversarial independente dos achados do red team ficou parcial: só três achados altos (L1-1, L1-2, L2-2) passaram por refutação, e nela o refutador concluiu apenas que descreviam a versão anterior e que a correção já estava aplicada; os demais estão "confirmados por lente/fonte primária", não "sobreviventes a refutação". **[F]** O red team descartou ainda: BAND_MAX por projeção da silhueta de B via correspondência (F-08), Qwen-Image-Layered como fonte de z-order, paste-back em O como prova de oclusão (F-05) e H7 na forma original (F-06) (`06` §4).

### 2.4 Auditoria do harness (D-036…D-047)

**[D]** Antes do primeiro run, o harness foi endurecido: evidência obrigatória depende do manifesto (eixo D `NOT_APPLICABLE` só com `occlusion == ["none"]` sem `front_certain`); tolerâncias separadas `tol_engine` (da nula) e `tol_composed = 0` (contrato `exact`); identidade da peça em auditor separado e obrigatório (`garment_fidelity_audit.py`); franja C3 não isenta; `split_by_garment_edge` julgável; seis casos core congelados em `g0_case_roles.json` (D-041); congelamento de ponta a ponta com `FREEZE.json` (D-042); agregador `g0_gate.py` (D-046); teto de credibilidade da nula em 12 (V-06) e largura da franja congelada no manifesto (V-07).

### 2.5 Viabilidade medida no alvo (D-048…D-056, 2026-10-08/09)

Ver §4 abaixo. Fase 3 encerrada em D-056.

### 2.6 Distribuição nula (D-057…D-059c, 2026-10-10/14)

Ver §6 abaixo. É onde o projeto está parado.

---

## 3. Estado da arte, famílias e o que foi descartado

**[F]** Famílias comparadas em `02`: F1 editores gerais multi-referência (klein, QIE), F2 VTON por máscara (CatVTON, Leffa, FitDiT), F3 referência vestida nativa sem máscara (FASHN 1.5), F4 try-off → VTON, F5 correspondência/warp, F6 3D + simulação, F7 roteamento/composição. Leitura por eixo (`02` §3): nenhum candidato é nativamente forte em preservar A; "add" para F1/F3 foi rebaixado de ●●● para "?" porque era inferência de mecanismo, não evidência (D-030); pose difícil é "?" para todos.

**[D]** Descartes e seus motivos (`02` §5, `04` §6, D-010, D-012): editor geral único com prompt (proibido pelo enunciado e incompatível com a evidência de deriva); VTON agnóstico padrão (destrói pele/ombros/mãos e bloqueia adição); F6 (licença SMPL, ChatGarment depende de GPT-4o, SewFormer exige Maya, bloqueios Windows, parâmetros de material desconhecidos); modelos acima do orçamento (FLUX.2 dev, Step1X-Edit, IDM-VTON etc.). D-020 reverteu dois descartes (OmniGen2, BAGEL) para "MARGINAL/medir" após releitura das fontes.

**[F]** Trilhas de licença (`01` §1 item 5 e §7, `04` §2): permissiva (klein 4B/base Apache, QIE repo Apache, FASHN código Apache, BiRefNet MIT, DWPose Apache, MHR Apache, DINOv2 Apache); proprietária revogável (SAM License para SAM 3 / SAM 3D Body; DINOv3 License de estrutura idêntica); NC ou de pesquisa (parser FASHN herda licença NVIDIA, CatVTON, FitDiT, TEMU-VTOFF, FLUX.1 Fill/Redux, Qwen-Image-2.1 sob Qwen Research License só como comparador); sem LICENSE declarada (Layering-VTON, RefTon, pesos DensePose CSE). **[Q]** O10: a intenção de uso do usuário (pessoal/pesquisa vs comercial) nunca foi declarada; a trilha permissiva é candidata a sistema final por padrão (D-011). SegFormer-B2-clothes pode herdar NC da base NVIDIA (`research_raw/07` L40).

**[D]** Duas correções de fonte já registradas importam para quem for reavaliar rotas: a alegação "IDM-VTON exige > 18 GB" não está na issue citada (D-023; `research_raw/07` L128); o "~8 GB" da Easy-Insert refere-se ao modo low-VRAM do DiffSynth, não à variante sequencial bf16 medida (D-049; `research_raw/08` §4).

---

## 4. Resultados efetivamente demonstrados

Protocolo **[D]**: `tools/measure_run.py` com watchdog 3600 s, commit real do Windows via `GetPerformanceInfo`, n = 3 cold + 3 warm por configuração (secundária R2 544×960: só cold ×3); elegível por tempo se cold ≤ 1500 s por candidato ~1024 px (teto de triagem que reserva ~300 s de QA e espaço para 2 candidatos ou refino dentro dos 3600 s do contrato), marginal 1500–3000 s, inviável acima ou com OOM/thrashing, definido como swap crescente + page faults altos por > 5 min (`03` §7–§8). **[Q]** Ressalvas: "cold" significa processo ou servidor novo com page cache do SO não esvaziado (`cold_pagecache_unflushed`, RAMMap indisponível), não frio de disco; n = 3 permite medianas, mas fica abaixo do n ≥ 10 que `00` §7 e `03` §8 exigem para percentis e estabilidade. **[F]** Pilha medida: ComfyUI core 0.38.2 @ `daeb5e53` como servidor próprio a partir do venv do Comfy-Desktop 1.1.6 (Python 3.13.12), torch 2.12.1+cu130 em todas as rotas, Diffusers 0.39.0 no R1-EI (Python 3.12.10), onnxruntime-gpu 1.30.0 / CUDA 13.0 no R3. R2 e as nulas usam servidor ComfyUI próprio em loopback (porta ligada ao PID recém-iniciado; cache validado pelo fecho do grafo: `must_reexecute`/`allowed_cached`, `FAIL:cached_result`; warm = mesmo servidor do terceiro cold, só clip/vae em cache) (`03` §1g, `tools/r2_qie/README.md`). Tudo abaixo é **[F]** salvo indicação.

| Rota | Configuração medida | Cold mediana | Warm mediana | VRAM pico | Observações |
|---|---|---|---|---|---|
| R1 klein 4B fp8 (D-048) | A+B 2 refs, ~1 MP (704×1490), 4 passos, ComfyUI externo | 31,8 s | 17,1 s (9,1–31,3 s) | ≈ 11 660 MiB de 12 227 MiB (NEAR_LIMIT) | commit ≈ 29–30 GB (pagefile); warm variável por cache do ComfyUI externo; warm anterior à regra de `execution_cached` (não auditado) |
| R1-EI klein-base-4B bf16 + Easy-Insert (D-051) | crop 1024², 15 passos CFG 4, Diffusers sequencial, processo novo por run | 272,5 s | 283,9 s | 12,13–12,19 GB (folga mínima ≈ 40 MiB) | elegível por tempo (18 %); VRAM crítica; `fp8`/`offload` só fallbacks; 5 bugs de infraestrutura Windows corrigidos com testes (`tools/r1ei/README.md` §7: BOM obrigatório em `.ps1` para PS 5.1; `core.autocrlf` invalidava sha → proveniência por blob OID + sha LF; `hf download --include` ignorava padrões → `snapshot_download`; checagem de disco removida; `pynvml` → `nvidia-ml-py`; mais tarde, readiness do servidor R2 por PID do launcher, `ac63246`) |
| R3 FASHN 1.5 bf16 (D-053/D-054) | canvas 576×864, `tops/model`, 30 passos, CFG 1,5, modos `segfree` e `masked` | 39,2 s / 38,6 s | 38,6 s / 38,6 s | ≈ 8,0 GB externo (torch alocado 3,7 GB) | 12/12 exit 0; mede só o custo da subtarefa nativa `tops`, não a transferência integral do biquíni two-piece |
| R2 QIE-2511 Q5_K_M (D-056) | A+B, modo nativo denoise 1, 40 passos CFG 4, 688×1504, ComfyUI próprio em loopback | 566,5 s (13,9 s/passo) | 563,3 s (wall do sidecar; wall do `measure_run` não transcrito para os warm) | 1 MP: 11,24–11,41 GB (folga ≥ 821 MiB); 544×960: 11,65 GB (folga 575 MiB); RAM 15,47/16 GB; commit 31–32 GB | **H4 verdadeira**; 40 passos = ramo executável do template oficial (a nota textual de 20 passos diverge dele; Diffusers padrão 50); configuração de 20 passos registrada e desabilitada, só mediria se 40 falhasse 1500 s, regra não acionada (D-055); custo dominado por streaming de pesos (×1,15 para ×2 pixels); warm ≈ cold porque o UNET é reexecutado; secundária 544×960 cold 495,8 s |

**[F]** Lotes de distribuição nula (`03` §7b; ver §6 para a leitura): lote 1 (Klein normativa 21/18/22/19/23, INCONCLUSIVE), lote 2 (nove runs: quatro normativas e cinco controles, 183 arquivos pinados por SHA), Derive parte 2 em CPU (parou em `klein_g0` por desenho).

**[Q]** O que estas medições **não** dizem: nada sobre qualidade (criação da peça, oclusão, preservação). Não existe medição standalone de R4, R8 nem dos estimadores SAM 3 e MHR; DWPose e o parser só têm fases cronometradas dentro dos runs R3 (≈ 0,3–0,8 s cada, sem VRAM separada); nada para QIE com 3 referências. As séries de page faults exigidas pelo protocolo para declarar "sem thrashing" não foram transcritas (`03` §1g). Os JSONs brutos, sidecars e PNGs vivem só na máquina do operador; o repositório tem transcrições (`benchmark/measurements/*.json`).

**[I]** Duas lições de calibração: o estimador `memory_budget.py` é enviesado para baixo (klein: banda residente 8,2–11,5 GB vs 11,6 GB medido; R1-EI: estimativa narrativa 9–10,5 GB em `03` §1e e banda do estimador 8,9–18,7 GB vs 12,1–12,2 GB medido, na metade superior da banda), e no alvo "excede VRAM" vira custo por passo sob DynamicVRAM, não inviabilidade (D-022; `06` F-17; `03` §4 cita D-016 por engano).

---

## 5. A hipótese estrutural e o aparato de auditoria

**[D]** **H0** (ex-D-008): casca de invariantes congelados + envelope por classe + ocupação medida em O′ por segmentador independente, com motor substituível, é suficiente para desacoplar "criar a peça" de "reconstruir A". Falsificação pré-registrada no Prototype 0 (`04` §4, `06` §7). **[Q]** Não testada.

**[D]** Aparato (`tools/`): `occupancy_audit.py` v6 (alvos `engine` = O′ reprojetada e `composed` = entrega; evidências (i) G independente e (ii) mudança real acima do piso nulo; `--null-stats` normativa, teto 12, franja C3 limitada; vereditos PASS/FAIL/INCONCLUSIVO com exit 0/1/3); `garment_fidelity_audit.py` v1 (evidência (iii): atributos congelados por adjudicação cega, cromaticidade Lab); `g0_gate.py` (só seis casos core, ≥ 4/6, ≥ 3 seeds, exige os dois auditores, rejeita JSON fora do perfil g0 ou com FREEZE divergente); `freeze_proto0.py`/`freeze_check.py` (FREEZE.json com sha de tudo); `measure_run.py`; `pixel_preservation_check.py`.

**[F]** Benchmark Proto0: 19 casos em `benchmark/proto0_cases.jsonl` (EASY 4, MEDIUM 1, HARD 13, EXTREME 1; 17 em modo `add`), papéis em `g0_case_roles.json`, PREREG em template. **Nada está congelado**: todos os sha são placeholders, consentimento e anotador placeholders (543 placeholders segundo o validador, `06` §12 B-12), 194 arquivos referenciados e 0 presentes, `FREEZE.json` inexistente (`06` §12 B-08, D-042). **[D]** As A do Proto0 serão PNG (D-059a); a A pinada das medições e nulas é uma JPEG 725×1536 de viabilidade, que não é A de caso.

**[I]** Risco que deixo explícito: o aparato de auditoria é extenso e testado em CPU (15 scripts de teste: 8 em unittest com 138 funções `test*`, 9 delas assíncronas, e 7 em estilo script com checks numerados, p.ex. occupancy 65 e validador 25; `tools/null1/REVIEW.md` registra 407 casos/checks em 15 scripts no commit `7b8eca0`), mas nunca correu sobre uma saída real de motor. Os limiares de franja, cromaticidade, split e as frações de identidade são provisórios por declaração. A justificativa registrada para acumular método antes da primeira imagem avaliada é o sweep histórico (`03` §1b) e a circularidade achada pelo red team (`06` F-01/F-04); o custo é real: o harness pode se revelar inadequado quando encontrar saídas reais, e só o G0 mostrará.

---

## 6. Distribuição nula: o estado atual em detalhe (D-057 → D-059c)

Esta é a parte do projeto em que o avaliador encontrará a maior densidade de decisões recentes, duas correções de rumo minhas e uma ambiguidade experimental não resolvida.

### 6.1 Por que uma nula

**[D]** V-06 e F-33: sem um piso de reconstrução medido, qualquer tolerância de identidade em O′ é arbitrária, e uma `--a-ref` fabricada inflaria a tolerância. O teto de credibilidade 12 (8 bits, `max_RGB`, p99,5) nasceu como guarda anti-fabricação, não de uma distribuição (`06` §12.1 V-06). **[I]** Esse ponto importa para avaliar D-059: o teto nunca foi derivado; é uma constante de projeto cuja validade só a própria medição podia confirmar ou negar.

### 6.2 Parte 1 (D-057) e o lote 1

**[D]** O_null1 = A → forward da rota (escala/recorte) → VAE encode/decode sem edição → inverso → comparação na grade de A dentro de um suporte de reconstrução que exclui pixels copiados de A; métrica `max_RGB |O − A|` em 8 bits, p99,5 por zona (skin, background, hair_face, occluders; clothing informativa), `tol = max(1, ceil(p99,5))`, teto 12 em escalar e cada zona. Zonas do parser pinado do R3 sobre a A pinada. Geometrias por rota: Klein `ImageScaleToTotalPixels` nearest-exact 1 MP → 704×1490 → recorte VAE 704×1488, inverso afim bicúbico; QIE `FluxKontextImageScale` 688×1504, inverso Lanczos; R1-EI caixa [-136,193,860,1189] → Lanczos 1024², inverso Lanczos, caixa inteira sem máscara de inserção; FASHN fit 864 → ResizePad 576×864 → unpad → Lanczos de volta, sem VAE.

**[F]** Lote 1 (`20261010T162735Z_1b40ed495243`): Klein 21/18/22/19/23 → `INCONCLUSIVE:null_distribution_not_credible`. **[F]** Antes disso, o primeiro Generate falhou por shadowing do pacote namespace `comfy` do ComfyUI por um módulo nosso `comfy.py` (corrigido em `7ce11ec`).

### 6.3 D-058: controles para decompor o piso

**[D]** Teto, métrica, VAE e reprojeção inalterados; Klein fica INCONCLUSIVE; o lote passa a continuar após INCONCLUSIVE estatístico (exit 3) e só erro operacional interrompe (exit 1); cinco controles não normativos e sem teto: `klein_resample_only`, `klein_vae_native` (recorte central 720×1536, sem reescala), `qie_resample_only`, `qie_vae_native`, `r1ei_resample_only`. **[I]** Hipótese que motivou: o perfil (p99,5 21/18/22/19/23 registrado em `tools/null1/manifest.json → preserved_evidence`; p50 2, p95 7 e máx 68 constam só no `null_stats.json` local do lote 1, não versionado [NV]) parecia erro de borda de reamostragem, não ruído de VAE.

**[D]** No mesmo handoff pré-registrei a regra de decisão para D-059 (ramo (a): pisos de VAE a 1:1 ≤ 12 → teto mantido e identidade de O′ avaliada na grade interna da rota contra A levada pela mesma escala; ramo (b): algum piso > 12 → V-06 cai para esse VAE e decide-se mudar métrica ou rederivar teto, nunca em silêncio; FASHN: identidade definida na grade 576×864, piso de reprojeção informativo; D-059 registrou depois o desvio para 407×864, a saída real `unpad`). **[Q]** Essa regra ficou só no handoff em chat, não versionada; foi transcrita a posteriori em `03` §7b e deu origem à regra de processo "toda regra de decisão entra no commit anterior ao Generate".

### 6.4 Lote 2 e D-059

**[F]** Lote 2 (`20261010T170913Z_63cfc8e35a3c`), p99,5 em suporte/skin/background/hair_face/occluders:

| Rota | Normativa (grade de A, com inverso) | Só reamostragem | VAE a 1:1 (720×1536) |
|---|---|---|---|
| Klein | 21/18/22/19/23 INCONCLUSIVE | 21/18/22/18/24 | 8/7/7/9/10 |
| QIE | 8/7/7/11/9 | 5/5/5/5/7 | 8/7/7/10/8 |
| R1-EI | 8/6/8/9/11 | 4/2/5/3/3 | não medido (controle não previsto) |
| FASHN | 15/10/15/13/11 INCONCLUSIVE | é só reamostragem | sem VAE |

**[I]** Leitura adotada: o piso da Klein na grade de A é dominado pela mudança de grade (só-reamostragem reproduz a normativa em ±1); QIE é dominada pelo VAE; FASHN 15 é só reamostragem. Dois pisos de VAE medidos a 1:1 (Klein 8, QIE 8) ≤ 12. **[I]** O meu rascunho inicial afirmava "VAE do R1-EI ≤ 8 por subtração"; a refutação adversarial anterior ao registro derrubou isso: a subtração não é aditiva porque o inverso Lanczos atenua a cauda (razões simuladas 0,73–1,0) e occluders já marcava 11. D-059 registra "ramo (a) ao R1-EI por subtração" como alternativa rejeitada após refutação adversarial (4 lentes + crítico); o texto do rascunho não está versionado. Por isso D-059 deixa **R1-EI suspenso** e aplica o ramo (a) só a Klein e QIE.

**[D]** D-059 (commit `e1820d7`): teto 12 e métrica mantidos, agora na grade interna (ligeiramente mais estrito sem a atenuação do inverso); identidade de O′ (alvo engine) avaliada na grade interna contra `A_fwd` produzida pelo mesmo executor pinado e conferida por sha pelo auditor, que não reimplementa geometria; máscaras por nearest, keypoints por afim, `thresholds` em px da grade de A com raio interno fora deles, domínio do motor obrigatório (BAND_MIN fora da grade interna → INCONCLUSIVO), composed inalterado (grade de A, exact, tol 0); pisos da parte 1: Klein 21 e FASHN 15 ficam INCONCLUSIVE como tolerância na grade de A, QIE 8 e R1-EI 8 permanecem nulas normativas válidas sob D-057 até D-060; frações de identidade do engine deixam de ser 1,0/0,98 a priori e serão derivadas de `frac_above_tol` em D-060 (o v6 aplica PROTECTED 1,0 ao engine, o que reprovaria O′ = O_null1); parte 2 = derivação em CPU dos artefatos preservados do lote 2, sem Generate novo; **a parte 2 na A pinada valida contrato e teto mas não é a nula do G0**: o G0 exige nula por (rota × A do caso × tupla), via módulo de geometria compartilhado; tuplas G0 = PREREG §3 (Klein recorte a múltiplos de 16 sem reescala até 1,1 MP; QIE 544×960; R1-EI caixa ×1,2 → 1024²; FASHN fit 864); workflow G0 da Klein substitui o nó de escala por `ImageCrop`; FASHN com identidade por definição a 407×864 (saída `unpad`; desvio do "576×864" da regra pré-registrada registrado em D-059), tol 1, provisória até O_null2, e um diagnóstico de comparabilidade não normativo (`--tol-engine 8/12` em perfil `minimal`).

**[Q]** Pontos de D-059 que convido a questionar: (1) mover a identidade para a grade interna de forma uniforme, inclusive para QIE e R1-EI cujos pisos na grade de A eram credíveis; (2) a tolerância 1 da FASHN, que torna a reprovação do alvo engine quase certa por construção até existir O_null2; (3) o teto 12 aplicado sem atenuação do inverso; (4) a regra "cauda da zona < 100 px → tolerância da zona informativa", que neutraliza a zona (oclusores = mãos) que é a mais alta na Klein e no R1-EI e a segunda mais alta na QIE (hair_face 11) e na FASHN (background 15); (5) a escolha das tuplas G0 do PREREG (QIE a 544×960, 0,5 MP, medida como secundária na viabilidade em D-056, enquanto a primária de viabilidade e a parte 2 foram a 688×1504).

### 6.5 D-059a: a referência da Klein

**[F]** A Astra reportou que o ComfyUI pinado decodifica `A.jpg` com PyAV e que os pixels diferem do Pillow. **[D]** D-059a (commit `2f0a92f`): `A_fwd` da `klein_g0` passa a ser a saída do executor pinado (`LoadImage → ImageCrop 720×1536 (2,0) → SaveImage`, `--cpu`, sem VAE), não o recorte Pillow; o histórico 8/7/7/9/10 é tratado como confundido pelo decodificador; predição revisada: ≤ 8/7/7/9/10 por zona; exceder o valor Pillow em qualquer zona → parar e investigar. **[Q]** A premissa "o ComfyUI pinado decodifica JPEG com PyAV" **nunca foi verificada no código pinado**; aceitei o relato da Astra (D-059b registra isso).

### 6.6 Implementação da parte 2 (`7b8eca0`) e o Derive

**[F]** Commit `7b8eca0` (Astra): modo `Derive` CPU, lista PART2 separada de `ROUTE_ORDER`, schema 2 sem `reproject()`, lote 2 pinado (183 SHA), `tools/null_geometry.py`, `klein_crop_api.json`, grafo G0 da Klein importado (`klein_benchmark_source_api.json` → `klein_g0_crop_api.json`, só o nó 92:111 alterado), proposta de contrato do auditor v7 (`docs/AUDITOR_V7_CONTRACT.md`), emendas em `00`, `03` (2 linhas), `05`, `06`, PREREG, CHECKPOINT, README e nota de cabeçalho em `occupancy_audit.py` (VERSION continua "6"). **[I]** Revisei por conformidade e dei GO em chat; o GO não está registrado no repositório (o Derive subsequente, D-059b, o pressupõe). **[F]** `tools/null1/REVIEW.md` desse commit registra 407 casos/checks em 15 scripts, sem SKIP, no alvo; na minha reprodução em contêiner, `tests/run_all.py` teve 2 erros por ambiente (torch ausente; `runs/` ausente) e 9 testes pulados por ambiente.

**[F]** Derive (`20261011T022154Z_part2_72661d47cde2`, CPU): `klein_g0` contra `A_fwd` do executor `--cpu` = **9/9/8/10/13** (tol = ceil p99,5); informativo contra Pillow 8/7/7/9/10; |A_PyAV − A_Pillow| p99,5 5/5/4/5/8; `prediction_check.stop_before_accepting = true`; `ceiling_excess = {}` (occluders 13 > 12, mas informativa pela regra da cauda); o lote parou antes de `qie_g0`, `r1ei_g0`, fallback e `fashn_g0`; lote 2 íntegro 183/183. Veredito registrado: `INCONCLUSIVE:klein_above_pillow_or_prediction`.

### 6.7 D-059b: o stop e o próximo passo

**[I]** O resultado contradiz a expectativa que fundamentou D-059a: se o VAE tivesse consumido os pixels PyAV, esperava-se que o erro contra PyAV fosse ≤ o erro contra Pillow. A refutação adversarial do rascunho (D-059b, 2 lentes) apontou que isso não é teorema (o VAE suaviza; quantis não obedecem desigualdade triangular) e que o rascunho alterava três cláusulas pré-registradas sem declarar; ambos os pontos constam em D-059b.

**[D]** D-059b (commit `aa1a221`), com H1/H2 explícitas: **H1** a sessão Generate (GPU) decodificou A por caminho diferente da sessão `--cpu`, logo `A_fwd` não é o que o VAE viu; **H2** mesmo caminho, e a saída do VAE fica mais perto da decodificação Pillow (croma mais lisa). A evidência atual não separa as duas. Decisões: teto 12 e métrica inalterados; **supersede explicitamente** D-059 §4 "nenhum Generate novo" (autorizado um run pareado de diagnóstico em GPU), a definição do par `klein_g0` de D-059a (condicional ao resultado abaixo) e a semântica do stop (marca INCONCLUSIVE e continua). Ordem, com D-060 bloqueada até (d):

- (a′) teste CPU da premissa PNG: executor `--cpu` sobre PNG sintético sem perdas vs Pillow, bit a bit;
- (a) documental: `LoadImage.load_image` e regularizador do `VAEEncode` no core pinado, arquivo:linha:sha;
- (b) modo `Pair`: workflow que salva, na mesma sessão e do mesmo recorte, `A_fwd` e a saída do VAE; seção pinada `paired_workflows`; validador de grafo exato;
- (c) `A_fwd_paired` vs recorte `--cpu` (→ H2) e vs Pillow (→ H1); `native_paired` vs native do lote 2 decide determinismo (p99,5 ≤ 1 e máx ≤ 2, senão n ≥ 2);
- (d) normativo `klein_g0` = |native_paired − A_fwd_paired|, banda escolhida mecanicamente por (c) e gravada antes da avaliação (H2 → 9/9/8/10/13; H1 → 8/7/7/9/10), fora da banda ≥ 1 → INCONCLUSIVE, sem margem; occluders 13 lida explicitamente em D-060.

Regra prospectiva: `A_fwd` e `O_null1` do mesmo grafo e sessão em toda rota ComfyUI (o grafo G0 da Klein ganha um SaveImage no nó 92:111; o v7 exige `A_fwd` da mesma history); schema 2 ganha `reference_pairing` (qie_g0 e fallback = `separate_session`, válidos só como validação de contrato; r1ei `same_process`; fashn `identity`); FREEZE recusa `separate_session` para nulas de caso. Derive passa a continuar após o stop e re-deriva `klein_g0` com pré-registro de igualdade com o lote `72661d47cde2`. Corrige-se a regra de predição (hoje um valor 1 fora da banda passaria como `ok`). Lotes derivados pinados em `manifest.part2.derived_batches`. A em JPEG declarada inadequada ao G0 (validador PNG no patch v7).

### 6.8 D-059c: digest de pixels

**[F]** A Astra encontrou que o `SaveImage` pinado embute o grafo (com UUID da sessão) no PNG, logo o SHA do arquivo muda com pixels idênticos, e a re-derivação exigida por D-059b não poderia ser comparada por SHA de arquivo. **[D]** D-059c (commit `bcce403`): a invariante de reprodutibilidade passa a ser `pixel_sha256` (SHA256 do buffer RGB8 bruto, ordem C, com `width`/`height` iguais); SHA de arquivo e SHA do chunk `prompt` ficam como evidência; repetir UUID/prefixos históricos foi rejeitado por corromper a identidade de sessão; o lote `72661d47cde2` não é alterado.

### 6.9 O que está e não está implementado neste HEAD

**[F]** Em `bcce403`, o código em `tools/` e `tests/` é o de `7b8eca0`: o stop do Derive ainda interrompe o lote (`derive.py` L311–313 e teste `test_d059a_stop_prevents_next_route`), a regra de predição ainda tolera 1 nível fora da banda, não existe `pixel_sha256`, `reference_pairing`, `derived_batches`, modo `Pair`, `paired_workflows`, SaveImage no nó 92:111 do grafo G0 nem validador PNG; `manifest.part2.status` ainda é `PREPARED_NOT_DERIVED` e o README de `null1` ainda diz "NÃO DERIVADA"; `AUDITOR_V7_CONTRACT.md` ainda descreve o par D-059a e `A_fwd` conferida por SHA de arquivo. Tudo isso está previsto para o próximo commit da Astra.

**[LIM]** Não tenho acesso ao trabalho local não commitado da Astra nem aos lotes em `runs/proto0/null/` (ignorados pelo git). Não sei se a Astra já implementou (a′), `Pair`, a continuação do Derive ou `pixel_sha256`, nem se algum run adicional ocorreu. O operador afirmou, antes de D-059b, que não executou nada além do Derive de `7b8eca0`. Qualquer afirmação sobre o estado local atual deve vir da Astra ou do operador, não deste documento.

---

## 7. Hipóteses não comprovadas

**[Q]** Todas as hipóteses de `04` §4 continuam abertas, exceto H4 (verdadeira por medição de tempo, com a ressalva de que cobre 2 referências e não 3): H0 (casca suficiente), H1 (composição sem costuras), H2 (recorte de B elimina vazamento), H3 (klein preserva categoria/topologia em EASY), H5 (FASHN adapta à pose sem mover o corpo; "drift corporal" é hipótese nossa, não limitação declarada pelo autor), H6 (try-off preserva alças/fendas), H7′ (envelope contém GT), H8 (quantização Q4/NVFP4 não altera topologia), H9 (preview prediz final), H10 (roteamento supera rota única), H11a/H11b (blend linear vs liberação temporal desacoplam criar/preservar), H-DD4 (em 4 passos DD ≈ máscara binária), H-E4 (scaffold em pixel), H-F2-skin, H12, H13. A capacidade da Easy-Insert em roupa é NV (exemplos upstream são objetos). Nenhum protótipo A–H ou G0 executou.

**[Q]** Premissas técnicas ainda por verificar que afetam a leitura da nula: caminho de decodificação de imagens do `LoadImage` pinado; se o `VAEEncode` pinado usa a moda ou amostra do posterior (determinismo entre sessões); se decodificadores coincidem para PNG (teste (a′)).

---

## 8. Papéis e responsabilidades

**[D]** Operador (dono da máquina-alvo): executa setup/bench/Generate/Derive, envia resultados, não altera evidência. Astra (autor git `Codex <codex@openai.com>`; commits `4793a1f`, `702f05e`, `1e6b9ae`, `7b8eca0`, entre outros): implementa as decisões, para em ambiguidades, entrega commits para revisão com testes CPU, `git diff --check`, `.ps1` ASCII + BOM + CRLF, pins por sha, offline. Claude (eu): decide metodologia, revisa conformidade dos commits, dá GO/NO-GO e comandos exatos, registra decisões; não executa GPU.

**[I]** Padrão que se consolidou: Astra interrompe a implementação quando a decisão é ambígua (duas vezes na parte 2: referência PyAV e SHA de arquivo vs pixels; antes, na preparação da R2, 20 vs 40 passos, D-055). As colunas de evidência de D-059 ("4 lentes + crítico") e D-059b ("2 lentes") registram refutação adversarial automatizada dos rascunhos de decisão; ela alterou as claims indicadas em §6.4 e §6.7. As decisões D-059 em diante foram escritas por mim e revisadas por esse processo, não por um especialista humano.

---

## 9. Próximas etapas pendentes, na ordem pré-registrada

1. **Astra** (próximo commit): (a′) e (a); modo `Pair` + `paired_workflows` + validador de grafo; continuação do Derive após o stop com re-derivação pré-registrada; `reference_pairing` e `pixel_sha256` no schema 2; regra de predição "fora da banda → INCONCLUSIVE"; pins de `derived_batches`; atualização de README/`03`/`AUDITOR_V7_CONTRACT`/testes; parada para revisão.
2. **Claude**: revisão de conformidade com D-059b/D-059c; GO.
3. **Operador**: (a′) em CPU; Derive de continuação em CPU; um run `Pair` em GPU (segundos); envio de JSONs e digests.
4. **Claude**: leitura e **D-060**: banda normativa de `klein_g0` (H1/H2), tolerâncias de `qie_g0`/`r1ei_g0`/fallback, frações de identidade do engine a partir de `frac_above_tol`, leitura explícita de occluders 13, ramo (b) literal se `r1ei_g0` > 12 em alguma zona, aplicabilidade do teto a O_null2.
5. Auditor v7 (implementação do contrato), controles do auditor redefinidos na grade interna, migração de fixtures/FREEZE/gate.
6. Produção dos dados do Proto0 (imagens PNG, máscaras por elemento por 2 anotadores, consentimentos, GT), validação sem placeholders, nulas por caso, FREEZE com tag, PREREG preenchido.
7. G0 por nível, começando por `proto0_easy_01`, 3 seeds, no alvo.

**[Q]** Fora da sequência atual e sem data: O_null2 (`same_garment_noop`), E1/E2, tuning, R4/R8, smoke de memória da Klein (só se algum recorte G0 exceder 1 MP).

---

## 10. Problemas abertos e riscos

### 10.1 Metodológicos

- **[Q]** H1 vs H2 na referência da Klein; premissa PyAV não verificada; determinismo do VAE entre sessões desconhecido.
- **[Q]** Frações de identidade do engine (hoje 1,0/0,98 no v6) ainda sem derivação da nula; a regra "(1 − frac_above_tol) − margem" está pendente desde `03` §7b.
- **[Q]** Teto 12: constante anti-fabricação, nunca derivada; na grade interna é mais estrito; R1-EI tem risco pré-registrado de occluders > 12.
- **[Q]** FASHN: tol 1 e nenhuma rota de paste-back nativo → reprovação do engine quase certa até O_null2; a aplicabilidade do teto a O_null2 é indecidida.
- **[Q]** Zona de oclusores (mãos) é a menor e a mais alta em todas as rotas; a regra da cauda a torna informativa na A pinada. Se o mesmo ocorrer nas A do Proto0, a identidade de mãos fica sem tolerância normativa própria.
- **[Q]** Nulas por caso: 4 rotas × ≥ 6 casos core (19 no total), cada uma com execução GPU própria; o custo e a logística não foram estimados.
- **[Q]** G independente (SAM 3 / anotação humana) sobre tecido alucinado: calibração obrigatória e ainda inexistente; `g_boundary_err_px` sem calibração.
- **[Q]** Refutação adversarial dos achados do red team parcial (D-035).
- **[Q]** Limitações registradas do harness (`06` §12 "Não garante" e §12.1): deslocamento de fase de textura periódica na franja não detectado (V-12); ancoragem do FREEZE ao commit depende da tag `proto0-frozen-v1` (regra de processo, não de código; V-15); UNC ∩ BAND_MAX_BODY não proibido; peças acromáticas (branco vs preto) não separáveis por cromaticidade, só por adjudicação cega.
- **[Q]** Itens de `CHECKPOINT` "O que não foi resolvido" e `06` §9: compatibilidade do patch Blockwise com Edit-2511 e templates KleinBase4B NV (D-028); z-order `uncertain` indecidível a priori (cabelo vs gola, cós vs bainha); nenhum benchmark externo com GT real de adição sobre pele em pose difícil; risco registrado em `06` §9 item 12 de não existir rota ao mesmo tempo capaz, controlável e dentro do orçamento.

### 10.2 Técnicos e operacionais

- **[Q]** R1-EI com ≈ 40 MiB de folga de VRAM; comportamento sob eviction WDDM e com máscaras maiores não medido.
- **[Q]** R2 e R1 em NEAR_LIMIT; estimadores (SAM 3, DWPose, MHR) terão de rodar sequencialmente com o motor descarregado; custo de QA (~300 s reservados) estimado, não medido.
- **[Q]** Warm runs históricos da Klein anteriores à regra de cache; thrashing declarado ausente por estabilidade de tempo, sem séries de page faults.
- **[Q]** Workflow A+B da Klein medido (`klein4b_ab_api.json`) vive no W3Root do operador e foi importado ao repo só como fonte para o grafo G0; a execução G0 real não tem runner no repo.
- **[Q]** JPEG como A produz diferenças de 5–8 níveis entre decodificadores; só PNG é aceitável no G0, e o validador ainda não existe.

### 10.3 Licenças

- **[Q]** O10 (intenção de uso) indecidida; parser FASHN NC; SAM 3 / SAM 3D Body / DINOv3 revogáveis; SegFormer-B2-clothes possivelmente NC; datasets externos NC ou sem rótulos necessários; benchmark próprio exige consentimento e fontes CC.

### 10.4 Documentação desatualizada (compilado pela extração deste handoff)

**[F]** Trechos que contradizem o estado atual e que o avaliador vai encontrar: `03` cabeçalho e §5/§9 ainda dizem "PENDENTE de medição" e "nenhuma medição de R2" apesar de §1d–§1g; `04` cabeçalho diz "sem medição no alvo" mas cita D-056; `02`/`04` chamam a casca de "obrigatória" em trechos anteriores à rebaixa a H0; `04` §1 e `06` citam o auditor como v5 (é v6); `00` §4.4 diz v5; README raiz diz R3 "preparada, não medida" na tabela de pastas e "medida" no estado; CHECKPOINT título com data 2026-10-10 e "NÃO DERIVADA" no corpo antigo; `tools/null1/README.md` e `manifest.part2.status` "NÃO DERIVADA" após o Derive; `AUDITOR_V7_CONTRACT.md` sem D-059b/c; contagens de testes divergentes entre `06` §10, `06` §12 e CHECKPOINT; D-050/D-052/D-055/D-057/D-058 mantêm texto "não medida" por serem append-only; numeração de pendências pula O10 em `00` §10.2; glossário de `00` ainda define `region_contract` pré-revisão; `03` §4 cita D-016 onde a decisão é D-022. **[I]** Na minha leitura nenhum desses itens altera decisões; reduzem a legibilidade.

---

## 11. Onde eu mesmo veria fragilidade

**[I]** Para evitar que este documento funcione como defesa, registro onde eu questionaria a arquitetura se fosse o avaliador:

1. **Método antes de evidência.** Dezenas de decisões e um harness de ~1500 linhas de auditoria existem antes de qualquer imagem avaliada. A justificativa registrada é o sweep histórico (`03` §1b) e a circularidade achada pelo red team (`06` F-01/F-04); o custo de oportunidade é real e o G0 pode mostrar que partes do harness medem a coisa errada.
2. **A A pinada é uma JPEG de viabilidade.** Toda a calibração da nula até agora ocorreu sobre uma imagem que não é A de caso e cujo formato introduz a ambiguidade de decodificador. Decidi usá-la para validar o contrato porque era a única com medições de rota; um avaliador pode preferir reiniciar a nula diretamente nas A do Proto0 em PNG.
3. **Decisões em cascata sobre um único número.** D-059 → D-059a → D-059b → D-059c giraram em torno de `klein_g0`. Cada passo foi registrado e supersedido explicitamente, mas a cadeia é longa para um piso de reconstrução de 8 a 9 níveis em 255, abaixo do teto em todas as zonas normativas. Pergunta legítima: o rigor aqui é proporcional ao risco?
4. **Uniformidade da grade interna.** Mover a identidade para a grade interna para todas as rotas simplifica o contrato, mas exige auditor v7, dois conjuntos de máscaras, keypoints transformados e nulas por caso; alternativa menos invasiva (manter grade de A para rotas com piso credível) foi rejeitada por uniformidade.
5. **Teto 12 como constante.** Nunca derivado; a sua aplicação à grade interna e a O_null2 foi adiada para D-060.
6. **Regra da cauda.** Torna informativa a zona onde os pisos são piores.
7. **Dependência de um agente implementador e de um decisor automatizados.** A revisão adversarial que uso é útil, mas não substitui um especialista humano em processamento de imagem revisando, por exemplo, a escolha de `max_RGB` p99,5 como métrica de identidade.

---

## 12. Índice de evidências e decisões citadas

- Medições: `benchmark/measurements/klein4b_fp8_2ref_1mp.json`, `r1ei_kleinbase4b_easyinsert_bf16_1024_normal.json`, `r3_fashn15_bf16_576x864_{segfree,masked}.json`, `r2_qie2511_q5_2ref_{1mp,0p5mp}_40steps.json`; `03` §1d–§1g.
- Nulas: `03` §7b (D-057, D-058, D-059, D-059a, D-059b, D-059c); `tools/null1/manifest.json` (`preserved_evidence` do lote 1; `part2.source_lot` com 183 SHA do lote 2); lotes locais `20261010T162735Z_1b40ed495243`, `20261010T170913Z_63cfc8e35a3c`, `20261011T022154Z_part2_72661d47cde2` (fora do repositório).
- Decisões: `docs/DECISION_LOG.md` D-001…D-059c; mapa de supersessão: D-014 rebaixa D-008; D-015 rebaixa D-002; D-016/D-025 substituem C1–C5 por três campos; D-019 substitui H7; D-020 supera D-009; D-029 reclassifica a leitura do sweep em `03` §1b (F-21), mantendo a interpretação de acoplamento e o braço E0 de D-021; D-051 supera D-050; D-053/D-054 superam D-052; D-056 supera D-055; D-059b supersede D-059 §4 e partes de D-059a; D-059c supersede o "bit a bit por SHA de arquivo" de D-059b.
- Red team e harness: `06` §1–§12.1; `research_raw/07–09`.
- Proto0: `benchmark/proto0_cases.jsonl`, `benchmark/proto0/g0_case_roles.json`, `benchmark/proto0/PREREG_TEMPLATE.md`, `benchmark/coverage_matrix.md`.
- Ferramentas e contratos: `tools/occupancy_audit.py` (v6), `tools/garment_fidelity_audit.py`, `tools/g0_gate.py`, `tools/freeze_proto0.py`, `tools/freeze_check.py`, `tools/measure_run.py`, `tools/null1/*`, `tools/null_geometry.py`, `docs/AUDITOR_V7_CONTRACT.md`; READMEs e REVIEWs em `tools/r1ei/`, `tools/r2_qie/`, `tools/r3_fashn/`, `tools/null1/`.
