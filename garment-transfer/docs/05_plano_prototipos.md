# Fase 5 (plano) — Protótipos mínimos A–H, ablações e critérios de abandono

**Status:** protocolo definido; execução **pendente**. **Revisado em 2026-10-08:** o **Prototype 0 — ADDITION / OCCUPANCY STRESS TEST** (`06` §7) precede o Protótipo A e decide H0/H11; A, D e F passam a auditoria dupla (O′ e O); H7 foi substituída por H7′ (não circular).
**Regra geral:** nenhum pipeline amplo é integrado antes de A–H confirmarem ou derrubarem as hipóteses da shortlist. Cada protótipo altera **uma** variável por experimento, com seed registrada, baseline explícito e critério de falha fixado **antes** de rodar.

As rotas sob teste (R1, R2, …) são as da shortlist em `04_selecao_provisoria.md`. Este documento define **o que** se mede e **o que decide**; não define a arquitetura.

---

## 0. Convenções experimentais

| Item | Regra |
|---|---|
| Resolução | Convenção inicial: `A` com lado maior 1 024 px; variante 1 536 só no Protótipo B (pendência O8). |
| Seeds | 3 seeds fixas por caso por rota (`{1, 2, 3}` registradas). Seeds iguais entre modelos **não** implicam ruído equivalente; comparação pareada é por caso, não por seed. |
| Orçamento por protótipo | Declarado por experimento. Protótipos não precisam caber em 3 600 s individualmente, mas o custo é registrado para a composição final. |
| Hardware | Medições em outra máquina são `REPRODUZIDO EM OUTRO HARDWARE`; só a RTX 5070 do usuário produz `MEDIDO NO HARDWARE-ALVO`. |
| Casos | Subconjunto do split `dev` (nunca `final_test`), com `expected` preenchido antes da geração. |
| Avaliação | Automática (detectores da Fase 0 §9.3 instanciados) **e** inspeção humana registrada por caso (pelo agente/operador, declarada como tal; não inventar participantes). |
| Registro | `runs/<prototipo>/<rota>/<caso>/<seed>/` com `O`, intermediários, `R`, `timeline.json`, `manifest.json`. |

---

## Prototype 0 — ADDITION / OCCUPANCY STRESS TEST (novo; vem antes de A)

Protocolo completo em `06_RED_TEAM_REVISION.md` §7; casos em `benchmark/proto0_cases.jsonl` (EASY, MEDIUM, HARD-1 braço cruzado, HARD-2 manga longa em foreshortening, EXTREME, controles: no-op, controle negativo sintético, baseline pareado do sweep histórico, par autoproduzido com GT). Variável única: mecanismo de controle espacial (E0 denoise global · E1 máscara binária = envelope · E1′/E1″ controles negativos · E2 mapa graduado via DifferentialDiffusion · E3 = E2 + condicionamento estrutural). Cinco eixos medidos separadamente (criar a peça · fidelidade · adaptação à pose · oclusão · preservação) em **O′ e O** com `tools/occupancy_audit.py` v3 e referências congeladas: em O′ o eixo D usa métricas **estruturais** (tecido sobre oclusor por elemento, IoU da máscara do oclusor, keypoints da mão, membro duplicado, tecido na coroa do oclusor) — identidade de pixel em O′ é só diagnóstica; a métrica "a peça nasceu" exige cobertura **e** ΔE em BAND_MIN acima do no-op. **Pré-requisito:** avaliação do estimador de camadas vs anotação (IoU por elemento; relação; fração do torso nu rotulada como fundo pelo parser). Casos pareados (mesma A com B semelhante/muito diferente; mesma A com B manga curta/longa → `split_by_garment_edge` vs `behind_must_cover`), par autoproduzido com GT e controle negativo sintético. Ordem: começar por EASY; braço que não cria a peça em EASY é rotulado replace-only e sai sem discussão de fidelidade. Critérios PASS / FALHA-CRIAÇÃO / FALHA-OCLUSÃO / FALHA-ACOPLAMENTO pré-registrados por rota. **Decisão:** H0 sobrevive, é modificada (camadas, H13) ou cai; cada rota ganha ou perde elegibilidade para `add`.

## Protótipo A — Preservação (fundido com o Prototype 0 na parte de preservação)

**Hipótese (H-A):** a rota mantém os invariantes de `A` (identidade, pose, câmera, fundo) e os pixels C1 dentro da tolerância do contrato, **enquanto** altera a região da peça (não é preservação trivial).

| Campo | Definição |
|---|---|
| Casos | 6 do `dev`: 2 EASY, 2 MEDIUM, 2 HARD; todos com cabelo sobre a roupa em ≥ 2 casos e mãos sobre a roupa em ≥ 2. |
| Baseline | `A` inalterada (controle de trivialidade) e um "no-op" (`same_garment_noop`). |
| Variável | Rota (R1 vs R2 …) com sua estratégia nativa de preservação; depois, ablação: com/sem composição determinística de C1 externa à rota. |
| Controles | Mesmo `contract_frozen` para todas as rotas; `O′` **e** `O` reprojetadas ao canvas original; PNG sem perda; métricas de oclusor em O′ (em O são triviais pela casca). |
| Métricas | `pixel_preservation_check` em C1 (nº alterados, erro máx., MAE/RMSE); landmarks faciais/corporais normalizados (visíveis); embedding de identidade; LPIPS/DISTS no fundo fora de C2∪C3; verificação de mudança real na peça (não trivial). |
| Critério de falha | Qualquer pixel C1 alterado em modo `exact` sem mecanismo de composição; em `near_exact`, `frac_over_tol > max_frac` (O1 calibrado aqui); `identity_drift`/`pose_drift`/`camera_drift` detectados em ≥ 2 de 6 casos; ou "preservação" obtida sem alterar a peça. |
| Decisão | Rota reprovada em A **não** segue para integração sem um mecanismo externo de preservação verificável; se nem com composição externa preservar pose/câmera, **abandonar**. |

**Ablação A1 (cabelo/bordas, pendência O2):** variar largura da banda C5 (4/8/16 px @1 024) e medir artefatos de junção (inspeção + gradiente de borda).

---

## Protótipo B — Fidelidade à peça

**Hipótese (H-B):** construção e detalhes observáveis de `B` (alças, bainha, cintura, decote, fechos, estampa, logos) sobrevivem à transferência em orientação semelhante (EASY), isolando fidelidade de adaptação de pose.

| Campo | Definição |
|---|---|
| Casos | 6 EASY com construção não trivial: alças finas, assimetria, fenda, botões, estampa grande, logo/texto pequeno (escalonado 8/12/24/48 px em `O`, pendência O4). |
| Baseline | Rota mais simples da shortlist. |
| Variável | Rota; depois: A+B vs multi-ref (B2 = detalhe) para medir ganho (pendência O7); 1 024 vs 1 536 (pendência O8). |
| Métricas | Checklist de atributos de `garment_spec.json` (observado → preservado/alterado/ausente/não avaliável); similaridade DINO/CLIP em recortes da peça **com** compensação de pose (apenas EASY); legibilidade de texto/logo (OCR local, quando aplicável); cor intrínseca com compensação de iluminação. |
| Critério de falha | `wrong_category` ou `garment_topology_mismatch` em qualquer caso; perda de ≥ 2 atributos observados por caso em ≥ 3 casos; texto/logo ilegível acima do tamanho mínimo útil. |
| Decisão | Rota que troca categoria/topologia em EASY é **abandonada** (não é corrigível por refinamento). Rota que perde só microdetalhes segue para teste de refinamento localizado (Protótipo B2). |

**B2 (refinamento):** refinamento localizado da peça com referência; medir se recupera detalhes **sem** alterar C1 e sem introduzir `B_leakage`.

---

## Protótipo C — Adaptação (pose/perspectiva)

**Hipótese (H-C):** a peça muda de configuração espacial para a pose/câmera de `A` **sem** mover o corpo, mesmo quando `B` está em pose muito diferente.

| Campo | Definição |
|---|---|
| Casos | 6: delta de pose `moderate` (3) e `very_different` (3); incluir A sentada com B em pé; A com foreshortening de membro. |
| Baseline | Mesma peça com `B` em pose `similar` (controle de ganho/perda atribuível ao delta). |
| Variável | Delta de pose de `B` (mesma peça, doadores/poses diferentes) — mede dependência da orientação de `B`. |
| Métricas | Landmarks/articulações de `A` em `O` (pose_drift); contorno corporal (body_distortion); checklist de atributos (perda induzida pelo delta); inspeção: a peça "segue" a pose ou copia a silhueta de `B`? |
| Critério de falha | `pose_drift` ou `body_distortion` em ≥ 2 casos; silhueta de `B` copiada (peça não acompanha torção/perspectiva) em ≥ 2 casos; queda ≥ 50 % nos atributos preservados vs. controle `similar`. |
| Decisão | Rota que depende de orientação semelhante é rotulada "EASY/MEDIUM apenas" e não pode ser a rota principal para HARD/EXTREME; procurar rota complementar ou abandonar o alvo HARD para ela. |

---

## Protótipo D — Oclusão e ordem espacial

**Hipótese (H-D):** roupa, braços, pernas, cabelo e objetos mantêm a ordem frente/atrás correta; membros cruzando a região da peça permanecem à frente e intactos.

| Campo | Definição |
|---|---|
| Casos | 6: braços cruzados sobre o tronco (2), mão na cintura/bolso (1), cabelo longo sobre o decote (1), objeto à frente (bolsa/caneca) (1), pernas cruzadas com saia/calça (1). |
| Baseline | Caso equivalente sem oclusão (mesma peça, mesma pessoa se possível). |
| Variável | Presença/tipo de oclusão. |
| Métricas | Inspeção estruturada de ordem por **elemento** (front_certain/behind_certain/uncertain); integridade de mãos/dedos; `front_occluder_pixel_identity` e `garment_over_front_occluders` **em O′**; `occluder_border_coherence_proxy` (junção falsa escondida pelo paste-back); tecido sobre membro (`bad_occlusion`). |
| Critério de falha | `bad_occlusion` ou `impossible_intersection` em ≥ 2 casos; mãos/dedos alterados. |
| Decisão | Falha aqui indica confusão corpo/roupa na rota; corrigível apenas se houver mecanismo de ordem explícito (composição por camadas com preservação de C1). Se nem com isso resolver, rota limitada a casos `occlusion: none`. |

---

## Protótipo E — Tecido (volume, drape, contato)

**Hipótese (H-E):** volume, drape, folds, gravidade, tensão e contato são coerentes com a pose e a gravidade de `A` (não copiados de `B`), com efeitos locais (C3) de alcance mínimo.

| Campo | Definição |
|---|---|
| Casos | 6: saia maxi sentada (1), vestido solto reclinada (1), top justo com torção (1), jaqueta aberta em movimento (1), tecido brilhante (1), tecido fino/semitransparente não explícito (1). |
| Baseline | `B` em pé (fonte das pregas originais) — verificar se pregas de `B` foram copiadas. |
| Variável | Rota; depois material (mesmo corte, materiais diferentes). |
| Métricas | Inspeção estruturada (direção das pregas vs. gravidade/tensão; contato com assento/corpo; volume plausível); extensão de C3 medida (largura da franja de sombra/contato alterada fora de C2); `lighting_drift` (estatísticas de iluminação global fora de C2∪C3). |
| Critério de falha | Pregas de `B` copiadas em pose incompatível em ≥ 2 casos; `lighting_drift`; C3 excedendo largura máxima (O5 calibrada aqui) em ≥ 2 casos. |
| Decisão | Define a política de C3 e separa rotas que "aprendem aparência" de rotas que respeitam física o bastante; falha total aqui com todas as rotas → documentar como limite do domínio, não esconder. |

---

## Protótipo F — Adição (ocupar pele e fundo)

**Hipótese (H-F):** a peça consegue ocupar pele (ex.: saia maxi sobre pernas nuas, manga longa sobre braço nu) e fundo (saia ampla) **sem** ampliar indevidamente a edição e sem mover o corpo.

| Campo | Definição |
|---|---|
| Casos | 6: `add_over_skin` (3), `add_over_background` (2), `add_over_layer` (1: jaqueta sobre top mantido). |
| Baseline | Mesma peça em `replace` (A já com peça da categoria). |
| Variável | Operação (add vs replace); estimador de envelope por classe E2/E3 (E1 já decidido no Prototype 0) — pendência O3 reformulada; referência **não circular** (GT real ou banda humana congelada; H7′). |
| Métricas | `unchanged_in_band_without_garment`, `excess_on_background`, `coverage_of_band_min` vs GT/banda humana, `fabric_boundary_on_band_max_fraction`; pixels PROTECTED; body_distortion. |
| Critério de falha | Rota só adiciona onde havia roupa (depende de roupa semelhante em `A`) em ≥ 3 casos; `background_drift`; corpo movido para "caber". |
| Decisão | Rota incapaz de `add` é rotulada "replace-only"; se for a melhor em fidelidade, avaliar composição com uma rota de `add` (routing por operação). |

---

## Protótipo G — Substituição limpa

**Hipótese (H-G):** a roupa antiga de `A` é removida sem resíduos, sem danificar camadas preservadas (`keep_from_A`) e sem inventar corpo além do mínimo coerente (C4 marcado como inferido).

| Campo | Definição |
|---|---|
| Casos | 6: manga longa → regata (expõe braços) (2), calça → shorts (expõe pernas) (1), vestido → top+saia (1), gola alta → decote (1), jaqueta sobre camiseta mantida → outra jaqueta (`add_over_layer`) (1). |
| Baseline | `same_garment_noop`. |
| Variável | Rota; com/sem etapa explícita de remoção. |
| Métricas | `garment_remnants` (cor/bordas da peça antiga fora da nova); integridade de `keep_from_A` (pixels C1 + inspeção); coerência de C4 (tom de pele, continuidade, sem anatomia "corrigida"); mapa de inferência produzido. |
| Critério de falha | Resíduos em ≥ 2 casos; peça mantida danificada; C4 com anatomia incoerente com `A`. |
| Decisão | Resíduos recorrentes → necessidade de etapa de remoção/representação agnóstica independente; se a rota não aceita isso, limitar a casos em que a nova peça cobre a antiga. |

---

## Protótipo H — Pose difícil (combinação)

**Hipótese (H-H):** os requisitos A–G continuam compatíveis **quando combinados** em casos HARD/EXTREME (reclinado + braços cruzados + saia ampla + estampa + `B` em pé, etc.).

| Campo | Definição |
|---|---|
| Casos | 6 HARD/EXTREME do `dev` cobrindo ≥ 4 eixos difíceis simultâneos cada. |
| Baseline | O mesmo caso decomposto (quando possível) nos protótipos anteriores. |
| Variável | Rota única vs. composição/routing (se a Fase 4 propuser). |
| Métricas | Todas as anteriores + tempo total e memória **dentro de 3 600 s** com QA. |
| Critério de falha | Qualquer falha crítica (§6.2 do contrato) em ≥ 4 de 6 casos; ou tempo > 3 600 s. |
| Decisão | Define o domínio suportado declarável; se nenhuma rota/composição passar em HARD, o relatório final declara HARD/EXTREME como **não validado**, sem reduzir a dificuldade do benchmark. |

---

## Ablações transversais

| Ablação | Pergunta | Rotas |
|---|---|---|
| Precisão numérica | bf16 vs fp8 vs quantização moderada vs agressiva: perda de detalhe/topologia mensurável? | Todas as rotas que admitem quantização |
| Offload | Tempo e estabilidade com offload parcial vs total; pico de RAM/commit | Todas |
| Tiled VAE | Continuidade de estampa/costuras em bordas de tile | Rotas com VAE grande |
| Preview → final | Qualidade em resolução baixa/poucos passos prediz a final? (seleção barata descarta o melhor?) | Rotas candidatas a múltiplos candidatos |
| Candidatos vs refinamento | 1 geração forte vs N menores + refinamento, mesmo orçamento | Compor com Fase 3 |
| Routing | Ganho real do routing vs rota única no mesmo orçamento | Se proposto na Fase 4 |

---

## Critérios de abandono (gerais)

Uma rota é **abandonada** (não entra na integração) se qualquer um ocorrer:

0. **FALHA-CRIAÇÃO ou FALHA-ACOPLAMENTO no Prototype 0** (critérios em `06` §7).
1. Falha em A (preservação) sem mecanismo externo verificável que a corrija.
2. `wrong_category`/`garment_topology_mismatch` recorrentes em EASY (Protótipo B).
3. Inviabilidade no hardware-alvo: não executa, ou excede 3 600 s na configuração mínima com QA, **medido** (não estimado).
4. Licença incompatível com o uso pretendido, ou pesos/código indisponíveis localmente.
5. Dependência de roupa semelhante já existir em `A` **e** incapacidade de composição com rota de `add` (Protótipo F).

Uma rota é **limitada** (entra com domínio declarado) se falhar apenas em C (pose), D (oclusão) ou E (tecido) para subclasses específicas.

## Saída desta fase

- Tabela rota × protótipo com `PASS`/`FAIL`/`LIMITADO` e evidência (links para runs).
- Decisão de retorno à Fase 4 (revisar shortlist) ou avanço à Fase 6 (integração) — com justificativa.
- Pendências O1–O5, O7, O8 resolvidas ou re-registradas.
