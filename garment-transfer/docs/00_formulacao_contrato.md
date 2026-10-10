# Fase 0 — Formulação do problema e contrato formal

**Projeto:** Garment Transfer Local com Preservação Rigorosa (A + B → A vestindo B)
**Status desta fase:** entregue para revisão; **revisado em 2026-10-08 pelo red-team** (`06_RED_TEAM_REVISION.md`): a partição C1–C5 deixa de ser a representação primária (ver §4.2-R e §4.4-R). Decisões padrão marcadas como `[PADRÃO]`, pendências como `[ABERTO]`.
**Data:** 2026-10-07 (rev. 2026-10-08)
**Dependências:** nenhuma (este documento não pressupõe arquitetura, modelo ou máscara específica).

---

## 0. Como ler este documento

Este é um **contrato semântico**: define o que o sistema recebe, o que deve entregar, o que não pode mudar, o que pode mudar e como isso será auditado. Ele **não** prescreve algoritmos, máscaras, "permission zones" ou módulos. Qualquer arquitetura candidata (Fases 2–4) será julgada contra este contrato, e o QA (Fase 8) o implementa.

Convenções:

- `A` — imagem da pessoa-alvo. `B` — imagem da peça de referência (pode estar vestida em outra pessoa). `S` — especificação da tarefa (seleções e modo). `O` — imagem de saída. `R` — relatório de QA.
- "Peça" = item de vestuário individual; "conjunto" = várias peças tratadas como unidade.
- `[PADRÃO]` = decisão tomada por omissão, alterável pelo operador. `[ABERTO]` = ambiguidade registrada, sem decisão.

---

## 1. Entradas

### 1.1 `A` — imagem da pessoa-alvo

| Campo | Contrato |
|---|---|
| Formato aceito | PNG, JPEG, WebP; sRGB (ICC convertido para sRGB na ingestão, registrando o perfil original). |
| Canvas | Qualquer proporção. `W_A × H_A` é **o canvas de saída**. Nenhuma etapa pode alterar dimensões, proporção ou enquadramento da saída final. |
| Conteúdo mínimo | Pelo menos uma pessoa adulta não explícita, com a região a ser vestida ao menos parcialmente visível. |
| Múltiplas pessoas | Permitido. A pessoa-alvo é resolvida por `S` (seleção simples: clique/caixa/índice) antes da geração. Pessoas não selecionadas são conteúdo preservado (classe C1, §4). |
| Pré-processamento interno | Permitido redimensionar/cropar **internamente** para processamento (convenção inicial de comparação: lado maior 1 024 px, proporção mantida). A saída deve ser **reprojetada ao canvas original de `A`**. Toda transformação interna é registrada com sua inversa (§8). |

### 1.2 `B` — imagem da peça de referência

| Campo | Contrato |
|---|---|
| Modalidades obrigatórias no caso central | **Vestida em outra pessoa** (worn reference). |
| Modalidades a pesquisar e registrar por rota | Catálogo (ghost/flat), flat lay, cabide, manequim. Suporte a cada modalidade deve ser declarado por rota; suporte a catálogo **não** implica suporte a referência vestida. |
| Múltiplas peças em `B` | Permitido. A(s) peça(s)-alvo são resolvidas por `S`. Peças não selecionadas de `B` não são transferidas. |
| Pessoa, fundo e iluminação de `B` | **Não são entradas da tarefa.** Nenhum traço de identidade, corpo, pose, fundo ou iluminação de `B` pode aparecer em `O`. Isso é um critério eliminatório (§6). |
| Referências adicionais (`B2..Bn`) | Modo separado ("multi-ref"): frente/costas, detalhe (logo, fecho), outro doador. O desempenho com **apenas A+B** permanece reportado separadamente. |

### 1.3 `S` — especificação da tarefa

`S` é obrigatório, mas deve ser derivável de uma interação simples. Campos:

| Campo | Valores | `[PADRÃO]` quando omitido |
|---|---|---|
| `target_person` | índice/caixa/ponto em `A` | Única pessoa, ou a maior/mais central se houver várias **e** a ambiguidade for baixa; senão `INCONCLUSIVO` (pedir seleção). |
| `garments` | lista de peças de `B` (índice/ponto/caixa + categoria opcional) | Todas as peças **claramente vestíveis** detectadas em `B` como um conjunto; se detectar >1 categoria conflitante, pedir seleção. |
| `mode` | `replace` / `add` / `add_over_layer` | `replace` da peça de `A` de mesma categoria; se `A` não tem peça da categoria, `add`. |
| `remove_from_A` | lista de categorias/peças de `A` a remover | A(s) peça(s) de `A` substituída(s) pelo `mode`; nada mais. |
| `keep_from_A` | lista explícita de itens preservados | Tudo que não está em `remove_from_A`: cabelo, acessórios, calçados, óculos, relógio, bolsa, objetos segurados, outras pessoas, fundo. |
| `layering` | ordem de camadas, `tuck_in`/`tuck_out`, `closed`/`open`, mangas arregaçadas, etc. | Inferir de `B` quando identificável; senão **manter como em `B`**; se não identificável em `B`, marcar `DESCONHECIDO` e usar a configuração mais comum da categoria, registrando a inferência. |
| `fit_intent` | `as_in_B` (preservar intenção relativa de ajuste) / `size_hint` | `as_in_B`. Nenhuma alegação de tamanho comercial. |
| `resolution_policy` | `native` / `internal_1024` / `internal_1536` | `internal_1024` com saída reprojetada ao canvas de `A`. |
| `references` | `B2..Bn` opcionais com papel (`back`, `detail`, `alt_view`) | nenhum |
| `time_budget_s` | ≤ 3 600 | 3 600 |

### 1.4 Validação de `S` antes da geração (gate de entrada)

Rejeitar (`FAIL: invalid_spec`) ou pedir esclarecimento (`INCONCLUSIVO: ambiguous_spec`) quando:

- A categoria da peça selecionada é incompatível com o `mode`/região (ex.: "adicionar vestido sobre calça mantendo a calça visível na cintura" sem especificar camadas).
- Dois pedidos são mutuamente incompatíveis (ex.: `keep_from_A` inclui a peça listada em `remove_from_A`).
- A peça selecionada em `B` não é vestuário (bolsa, sapato) e o sistema não declara suporte à categoria.
- A região-alvo em `A` é inteiramente invisível (ex.: pedir troca de calça em retrato de busto). Isto é `FAIL: target_region_not_visible`, não "transferir mesmo assim".

---

## 2. Saída

| Item | Contrato |
|---|---|
| `O` | Imagem no canvas exato de `A` (`W_A × H_A`), sRGB, exportada em **PNG sem perda** (obrigatório para auditoria de pixels). Versão JPEG opcional derivada do PNG. |
| `R` | Relatório de QA em JSON (§9): veredito `PASS`/`FAIL`/`INCONCLUSIVO`, causas, métricas por eixo, estados por atributo (`observado`/`inferido`/`desconhecido`), tempo e memória, proveniência de todos os intermediários. |
| Intermediários | Salvos para auditoria (§8). Nunca substituem `O`. |
| Rejeição | Se nenhum candidato for `PASS` dentro do orçamento, a saída é **rejeição explícita** (`R` com `FAIL`/`INCONCLUSIVO`, sem `O` "aprovada"). Entregar o "último candidato" só em modo explicitamente marcado `unverified_preview`, nunca como resultado padrão. |

---

## 3. Formulação por primeiros princípios

Tarefa: **edição contrafactual condicionada** — como a cena de `A` seria fotografada se aquela pessoa estivesse usando a(s) peça(s) de `B`?

Decomposição conceitual (formulação, **não** obrigação de reconstruir 3D nem de ter módulos separados):

1. **Pessoa** (de `A`): identidade, anatomia, proporções, pose, expressão, cabelo, superfície corporal.
2. **Cena** (de `A`): câmera (intrínsecos/extrínsecos implícitos), projeção, enquadramento, fundo, objetos, iluminação global.
3. **Roupa** (de `B`): construção, material, aparência intrínseca, caimento, interação com pessoa/cena.
4. **Observação**: visibilidade, oclusões, resolução, ruído, informação ausente — em `A` e em `B`.

`A` é evidência sobre (1) e (2). `B` é evidência sobre (3). A roupa **muda de configuração espacial** para se adaptar a (1) e (2); a pessoa de `A` **não** se torna a pessoa de `B`.

Dois enunciados que governam tudo o mais:

> **Preservar rigidamente `A`** = preservar as propriedades da pessoa e da cena que independem da troca de roupa. **Não** significa manter todos os pixels nem a silhueta externa da roupa antiga.

> **Preservar `B`** = preservar identidade e construção da peça, permitindo deformação, projeção, oclusão e resposta à iluminação compatíveis com `A`. **Não** significa copiar a silhueta 2D nem as sombras fotografadas em `B`.

Variáveis de projeto (do sistema): família de modelo, representação, condicionamento, controles, estratégia de preservação, precisão numérica, resolução interna, nº de candidatos, refinamento, avaliação.
Variáveis de entrada (do caso): categoria, corpo, pose, perspectiva, oclusão, modalidade de referência, camadas, material.
Mudar variáveis de projeto não é generalizar a novas variáveis de entrada; o benchmark (Fase 7) estratifica pelas de entrada.

---

## 4. Contrato de autoridade e classes de mudança

### 4.1 Autoridade

| Fonte | Atributos sob sua autoridade |
|---|---|
| **`A`** | identidade, rosto, expressão, cabelo (forma, cor, fios soltos), corpo, proporções, pose, anatomia, posição de membros, mãos, dedos, pés, câmera, perspectiva, foreshortening, enquadramento, iluminação global (direção, cor, intensidade), fundo, composição, outras pessoas, objetos, acessórios/calçados não selecionados. |
| **`B`** | categoria e subtipo da peça, construção, corte, comprimento relativo, intenção de fit, cintura/waistband, bainha/hem, alças/straps, mangas, decote, fechos, bolsos, costuras, painéis, aberturas, fendas, assimetrias, estampa, texto/logos, textura, material, brilho, transparência, cor intrínseca, detalhes distintivos observáveis. |
| **Nenhuma** (inferência) | costas não fotografadas, camadas ocultas, escala física absoluta, composição exata do material, anatomia coberta em `A`, regiões recém-expostas de `A`. |

### 4.2 Cinco classes semânticas de região/mudança

Toda região de `O` cai em exatamente uma classe. A classificação é derivada de **`A`, `B` e `S` antes da geração** e **auditada de forma independente da saída** (§4.4). Nunca é ampliada retroativamente para absorver deriva.

| Classe | Definição | Regra |
|---|---|---|
| **C1 — Preservado determinístico** | Conteúdo de `A` observado, ainda visível após a troca, e sem efeito físico necessário da nova peça: rosto, cabelo (exceto pixels mistos), mãos/pés fora da região de contato, fundo distante, outras pessoas, objetos, acessórios mantidos. | Igualdade **exata de pixels** quando exigida (`exact`), ou erro ≤ tolerância declarada (`near_exact`, para rotas que reprojetam). Auditada na mesma grade e espaço de cor, exportação sem perda. |
| **C2 — Ocupação da peça** | Pixels onde a nova peça cobre roupa antiga, pele ou fundo. | Mudança permitida **somente pela presença da peça**. Corpo subjacente (pose, articulações, volume), câmera e fundo remanescente são invariantes. A extensão de C2 é determinada pela peça (uma saia ampla pode ocupar fundo antes vazio), **não** pelo corpo nem pela silhueta da roupa antiga. |
| **C3 — Efeitos locais inevitáveis** | Sombras de contato, oclusão ambiente, reflexos, transmissão (transparência) e dispersão subsuperficial na vizinhança imediata da peça. | Mudança permitida com **alcance mínimo, justificado e auditável**. Proibido: relumir a cena, criar sombras globais, mudar o fundo além da franja de contato. Deriva global de iluminação é falha (`lighting_drift`), não C3. |
| **C4 — Recém-exposto** | Regiões antes cobertas (pela roupa antiga de `A`) e agora visíveis: pele, parte do fundo, cabelo atrás. | **Informação ausente.** A síntese é inferência e é marcada como tal em `R`. Deve ser coerente com `A` (tom de pele, iluminação, continuidade do fundo), sem corrigir anatomia nem "melhorar" `A`. |
| **C5 — Bordas e mistura** | Cabelo fino, franjas de tecido, transparência, desfoque de movimento/profundidade, pixels mistos entre C1 e C2/C4. | Tratar como mistura/incerteza com largura declarada (em px, por escala). Recorte binário inadequado é falha (`hard_edge_artifact`). C5 não é licença para alargar C2. |

### 4.2-R Revisão (2026-10-08): três campos em vez de uma classe por pixel

A tabela C1–C5 acima permanece como **vocabulário de auditoria**, mas **não** é mais a representação primária, por duas razões demonstradas no red-team (`06` F-01, F-04): (i) a extensão de C2 só existe depois do caimento — exigir "partição congelada antes da geração" é circular; (ii) um rótulo por pixel não expressa oclusão ("a mão é C1 **e** o tecido nasce atrás dela").

A representação primária passa a ter três campos independentes, derivados de `A`, `B`, `S` **antes** da geração:

| Campo | Pergunta | Valores |
|---|---|---|
| **Autoridade de reconstrução** `R(p) ∈ [0,1]` | o que o motor pode reescrever | 0 em `PROTECTED` e no núcleo de `FRONT_OCCLUDERS`; 1 em `BAND_MIN`; graduado em `BAND_MAX\BAND_MIN`, `UNCERTAIN`, `CONTACT_FRINGE` |
| **Autorização de ocupação** | onde o tecido deve / pode / não pode existir | `BAND_MIN` (deve) · `BAND_MAX_BODY` (pode: pele/roupa antiga, condicional a atributos observados em `B`) · `FREE_SPACE` (pode: fundo/objetos atrás) · `UNCERTAIN_OCCUPANCY` (decidido pelo motor) · proibido = resto |
| **Ordem de profundidade por elemento** | o que fica à frente/atrás da roupa nova | `front_certain` / `behind_certain` / `uncertain`, com `basis` ∈ {observed_in_A, category_rule, spec_layering, default}; só os dois primeiros são eliminatórios |

Máscaras nomeadas do contrato, cada uma com origem (estimadores + versões), estado `observado/inferido(conf)/desconhecido` e escala: `PROTECTED`, `FRONT_OCCLUDERS_CORE`, `BAND_MIN`, `BAND_MAX_BODY`, `FREE_SPACE`, `UNCERTAIN_OCCUPANCY`, `CONTACT_FRINGE`, `KEPT_GARMENT_INTERFACE`, `NEWLY_EXPOSED`, `C5_BAND`. Classe de envelope: **E1** superfície observável (tops/justos), **E2** superfície ⊕ fora da silhueta (peças soltas), **E3** fundo (saias amplas/sentado; anotação humana obrigatória no dev).

Correspondência C1–C5 ↔ campos: C1 ≡ `PROTECTED` + invariantes; C2 ≡ tecido **medido** em `O′` dentro da autorização; C3 ≡ `CONTACT_FRINGE`; C4 ≡ `NEWLY_EXPOSED`; C5 ≡ `C5_BAND`.

### 4.3 Silhueta corporal ≠ silhueta do vestuário

- A **silhueta do vestuário** pode e deve mudar (C2).
- A **silhueta corporal** (contorno dos membros, pelve, cintura, ombros, pescoço, mãos) é invariante. Compressão/tensão do tecido sobre o corpo são desejáveis; deformação do corpo para acomodar a peça é falha (`body_distortion`).
- `[PADRÃO]` Volume corporal não muda. Se a peça exigir deformação corporal incompatível (ex.: peça muito justa em pose em que o tecido não poderia conformar), o sistema sinaliza `fit_conflict` em `R` e **não** altera o corpo.
- Se `A` já apresenta anatomia ambígua ou defeituosa, preservá-la. **Preservar `A` e corrigir `A` são tarefas diferentes**; a segunda não está no escopo.

### 4.4 Auditoria independente (revisada 2026-10-08)

- O que se **congela** antes da geração (`contract_frozen.*`): `PROTECTED`, invariantes estruturais de `A` (landmarks, contorno de pele visível fora do envelope, rosto, cabelo, mãos), `FRONT_OCCLUDERS_CORE` com z-order por elemento, envelope de ocupação por classe (E1/E2/E3) com estados. **Nunca** é ampliado a partir de `O`.
- O que se **mede** depois (`partition_measured.*`): o tecido novo `G` em `O′` (saída bruta do motor reprojetada) por segmentador **independente do gerador** (nunca a máscara/atenção do próprio gerador), com confiança calibrada contra anotação humana no dev; a franja C3 = dilatação de `G` por `r_C3` (pendência O5); C4 e C5 derivados.
- **Regra da banda (corrigida, `06` F-09):** dentro do envelope, alterações são permitidas **se** ocupadas por tecido medido **ou** dentro da franja C3 ao redor dele (**mudança limitada**: |ΔL*| ≤ 12 e Δ(a*,b*) ≤ 6 em ≥ 95 % dos pixels da franja, estrutura de gradientes preservada, sem textura nova — limiares provisórios em `occupancy_audit.py`; a franja **não** é isenta); fora disso são deriva (`background_drift`/`unauthorized_change`). Pele coverable **não** coberta deve permanecer igual a `A`.
- **"Ocupado por tecido da peça" — definição operacional (`06` F-32):** conjunção de três evidências independentes do gerador: (i) segmentação independente `G` com `G_source` declarado (nunca a máscara/atenção do motor); (ii) **mudança real** vs `A` acima do piso nulo da rota (τ_null do VAE round-trip / no-op); (iii) **identidade de peça** (atributos congelados adjudicados às cegas; cromaticidade Lab do recorte de `G` vs máscara congelada da peça em `B`; DINOv2 só relatório, acima do valor obtido com peça aleatória). Sem (ii), uma saída idêntica a `A` com `G` afirmando tecido passaria. **Implementação (revisão pós-auditoria externa, `06` §12):** (i) e (ii) em `tools/occupancy_audit.py` (v5); (iii) em `tools/garment_fidelity_audit.py` — **separado e obrigatório no G0**; `tools/g0_gate.py` só conta um caso como PASS quando ambos passam. `occupancy_audit.py` sozinho **não** implementa a conjunção e declara isso no JSON (`garment_identity: NOT_EVALUATED_HERE`).
- **Distribuição nula obrigatória:** limiares de identidade em `O′` derivam de `VAE(A)` (denoise 0) e do pipeline em `same_garment_noop`, não de tolerâncias a priori.
- **Auditoria dupla:** toda métrica de oclusão/ocupação roda em `O′` (mede o motor) **e** em `O` (mede a entrega); em `O` composto, identidade de oclusores é trivial pela casca e não prova nada sobre o motor.
- A auditoria julga **invariantes e envelope**, nunca "a área prevista". `UNCERTAIN` é a única zona em que a existência de tecido é decidida pelo motor; ali só se audita "não inventou terceira coisa" e "não distorceu o corpo".
- Isto é a **hipótese estrutural H0** (`06` §3), não um requisito: o Prototype 0 pode derrubá-la.

### 4.5 Contrato de oclusão e visibilidade (novo, 2026-10-08 — `06` L4)

Para cada **elemento** de `A` (lista fechada no schema: `hand_L/R`, `forearm_L/R`, `upper_arm_L/R`, `hair_front/back`, `neck`, `torso_front_skin`, `held_object`, `bag_strap`, `furniture`, `kept_garment_*`), registrar antes da geração: máscara 2D, relação com a roupa nova e base da decisão.

| Relação | Significado | Auditoria |
|---|---|---|
| `front_certain` | elemento oclui o corpo coberto e é mais próximo da câmera (observado em `A`): mão, antebraço cruzado, objeto segurado, móvel à frente | **eliminatória**: tecido sobre o elemento em `O′` ≤ 2 %; máscara do elemento re-segmentada em `O′` com IoU ≥ 0,9; keypoints da mão sem deslocamento; sem membro duplicado |
| `behind_must_cover` | a peça **deve** cobrir (torso frontal para um top) | cobertura ≥ 0,9 em `O′` |
| `behind_may_cover` | cobertura depende de atributo observado em `B` (braço superior vs comprimento da manga) | reportado; fronteira auditada só com GT |
| `split_by_garment_edge` | parte à frente / parte coberta; a fronteira (bainha da manga sob a mão) cai na banda `UNCERTAIN` | eliminatória com máscaras congeladas `split_must_cover_mask`/`split_must_stay_visible_mask`: cobertura do must_cover por `G` ≥ 0,9; tecido sobre a parte visível ≤ 2 %; parte visível idêntica a `A` (limiar da nula); zona de fronteira: cada pixel é tecido **ou** idêntico a `A`; alternativa pré-registrada: adjudicação humana cega; sem nenhuma → INCONCLUSIVO |
| `uncertain` | indecidível a priori (cabelo vs gola/capuz; cós vs bainha por `layering`; mão no quadril vs aba) | **não eliminatória**; resolvida por `S` ou por padrão (D5/D6) e registrada como `inferido`; se o estimador automático não resolver com confiança → `occlusion_unresolved` (INCONCLUSIVO) |

Dois mecanismos **obrigatórios e distintos**: **ordem na entrada** (o oclusor `front_certain` permanece **visível** no contexto que o motor vê — nunca apagado/cinza — e é excluído da região editável) e **ordem na saída** (composição determinística). A composição é necessária, mas **não é o mecanismo de ordem**: uma rota só passa se `O′` já respeitar a ordem; caso contrário o resultado é recorte (`occluder_cutout`) ou membro duplicado (`duplicate_limb`).

Pixels `split`/`uncertain` são a única exceção legítima à regra "uma classe por pixel"; neles vale a regra de consistência, não uma classe fixa. Cabelo sobre tecido novo exige **des-composição** (α **e** cor de primeiro plano F estimadas de `A`; recompor `O = α·F + (1−α)·O′`) — alpha simples sobre tecido escuro produz halo da cor antiga (`hair_halo`).

## 5. Informação ausente, fit e identificabilidade

### 5.1 Estados por atributo

Cada atributo relevante (de pessoa, cena e peça) recebe em `R` um estado:

| Estado | Definição | Exigência |
|---|---|---|
| `observado` | Diretamente visível em `A` (pessoa/cena) ou `B` (peça), com resolução suficiente. | Fidelidade cobrada. |
| `inferido(conf)` | Não visível, mas com suporte (simetria, categoria, continuidade), com confiança declarada. | Coerência cobrada; fidelidade factual **não** garantida; marcado em `R`. |
| `desconhecido` | Sem suporte observacional (costas, camada oculta, escala física, composição do material). | Não cobrado como fidelidade; não aprovado automaticamente: avaliado como `não avaliável`. |

### 5.2 Política de desoclusão (C4)

1. Preservar o que já é observável.
2. Reconstruir o mínimo necessário, de forma coerente com `A`.
3. Marcar o que foi inferido (mapa de inferência em `R`).
4. Se a incerteza inviabilizar uma exigência crítica de `S` (ex.: "manter tatuagem no braço" quando o braço estava coberto), retornar `INCONCLUSIVO: insufficient_evidence` ou solicitar referência adicional. Nunca exigir imagens explícitas.

### 5.3 Fit, cor, material, topologia

- **Fit:** sem medidas físicas, `[PADRÃO]` preservar o design e a **intenção relativa de ajuste** observada em `B` (justo/solto/oversized) ao corpo de `A`. Nenhuma alegação de tamanho comercial, alfaiataria ou fit fisicamente verificável.
- **Cor intrínseca ≠ RGB de `B`.** A cor em `O` deve ser a cor intrínseca sob a iluminação de `A`. Avaliação de cor usa comparação com compensação de iluminação (ex.: cromaticidade relativa, comparação em regiões difusas), não distância RGB bruta.
- **Brilho/transparência** respondem à iluminação e às camadas de `A`.
- **Pregas de `B`** informam material e peso; não precisam manter posições.
- **Topologia** = construção, conectividade e aberturas da peça (nº de alças, se é peça única ou duas, fenda frontal/lateral, fechamento). Distinta de contorno projetado e de visibilidade. Uma alça ocluída por um braço **não** é alça ausente; duas regiões separadas na imagem podem ser tecido contínuo atrás de um membro.

### 5.4 Resolução e tamanho mínimo útil de detalhe

- Convenção inicial de comparação: `A` processada com lado maior 1 024 px (proporção mantida). **Revisar antes do benchmark** se não permitir avaliar os detalhes exigidos. Não é teto do produto.
- **Tamanho mínimo útil de detalhe** `[PADRÃO]`: um detalhe de `B` só é cobrado como "preservado" se ocupar ≥ 12 px na menor dimensão **na referência `B` reamostrada à escala em que aparecerá em `O`**, e ≥ 8 px em `O`. Abaixo disso, estado `não avaliável (sub-resolução)`. (Valores provisórios; calibrar na Fase 5 com exemplos de logos/estampas.)
- Resoluções maiores são comparadas **separadamente**, sob o mesmo limite de tempo. Upscaling não converte detalhe inexistente em detalhe "preservado".

---

## 6. Objetivo de otimização e critérios eliminatórios

### 6.1 Vetor de qualidade (4 eixos, não agregados)

1. **Preservação de `A`** (`P_A`)
2. **Fidelidade à peça `B`** (`F_B`)
3. **Coerência física e espacial** (`C_phys`)
4. **Realismo fotográfico** (`R_photo`)

Sujeito a: execução local; `t_total ≤ 3 600 s`; memória dentro do hardware (12 GB VRAM / ~16 GB RAM, com sistema e ComfyUI contabilizados); licença adequada; critérios mínimos (§6.2).

Comparação entre candidatos: **eliminatórias primeiro** (§6.2), depois **dominância de Pareto** nos quatro eixos. Nenhuma média ponderada que permita compensar corpo deformado com textura bonita.

### 6.2 Falhas críticas (eliminatórias)

| Código | Definição operacional |
|---|---|
| `identity_drift` | Identidade facial/corporal de `A` alterada além do limiar calibrado (Fase 8), ou traços de `B` presentes. |
| `pose_drift` | Articulações visíveis de `A` deslocadas além da tolerância normalizada pela escala; membros reposicionados. |
| `body_distortion` | Contorno corporal (não da roupa) alterado: cintura afinada, pelve movida, ombros, pescoço, mãos. |
| `camera_drift` | Mudança de perspectiva, foreshortening, enquadramento, distorção de lente ou horizonte. |
| `background_drift` | Alteração de fundo fora de C2 (ocupado por tecido) e C3 (franja mínima). |
| `lighting_drift` | Relume global, novas sombras globais, mudança de temperatura de cor da cena. |
| `wrong_category` | Peça de categoria/subtipo diferente de `B` (saia → shorts; vestido → top+saia). |
| `garment_topology_mismatch` | Construção essencial incompatível: nº de alças, peça única vs. duas peças, fenda, fechamento, assimetria. |
| `impossible_intersection` | Interpenetração tecido-corpo, tecido-objeto, ordem de oclusão impossível. |
| `B_leakage` | Pessoa, fundo, iluminação ou pose de `B` em `O`. |
| `garment_remnants` | Resíduos da roupa antiga de `A` (cor, gola, bainha) em regiões que deveriam ser C2/C4. |
| `budget_exceeded` | `t_total > 3 600 s` ou OOM não recuperado. |
| `unauthorized_change` | Alteração em C1 além da tolerância do contrato (`exact`/`near_exact`). |
| `bad_occlusion` / `visibility_violation` | Tecido sobre elemento `front_certain` em `O′`, ou máscara do oclusor alterada (IoU < 0,9), ou elemento `behind_must_cover` não coberto (rev. 2026-10-08). |
| `duplicate_limb` | Mais mãos/antebraços detectados em `O′` do que em `A` (membro alucinado dentro da região editável + oclusor colado). |

Qualquer falha crítica → candidato eliminado. Nenhum candidato sobrevivente → **"sem solução validada para este caso"**. Não reduzir silenciosamente a exigência, a categoria ou a dificuldade.

### 6.3 Falhas não eliminatórias (comparadas em Pareto)

`occluder_cutout` (recorte sem tecido na coroa do oclusor), `hair_halo` (cromaticidade do fundo antigo na banda C5), `composition_seam` acima do critério, `missing_strap` (quando visibilidade esperada), `wrong_hem`, `wrong_waistband`, `material_mismatch`, `detail_loss`, `print_distortion`, `unrealistic_drape`, `bad_contact_shadow`, `hard_edge_artifact`, `texture_oversmoothing`, `color_shift_beyond_lighting`. Cada uma com localização e severidade.

### 6.4 Prioridade

Qualidade é prioritária. Velocidade desempata alternativas de qualidade equivalente ou decide viabilidade no teto de 3 600 s.

---

## 7. Contrato de tempo e recursos

| Item | Regra |
|---|---|
| Relógio | Tempo de parede da solicitação completa: do recebimento de `A`, `B`, `S` até `O` exportada **com `R` concluído**, ou rejeição explícita. |
| Inclui | Carregamento de modelos a partir do disco, pré-processamento dependente de `A`/`B`, transferências CPU↔GPU↔disco, todos os candidatos, retries, rotas alternativas, refinamento, descarregamentos, QA, exportação. |
| Estado inicial do teste principal | Aplicação aberta, pesos em disco, **nenhum modelo da solicitação pré-carregado em RAM/VRAM**. Reportar separadamente: execução fria, aquecida (modelos já residentes) e com caches declarados. |
| Setup único | Instalação, downloads, compilação inicial ficam fora dos 60 min, com duração e custo documentados. Custos recorrentes (ex.: recompilação por mudança de shape) entram no orçamento. |
| Cache de referência | Se `B` reutilizada tiver cache, reportar custo da 1ª execução e amortizado, separadamente. |
| Deadline | Deadline rígido com cancelamento cooperativo de subprocessos e liberação de memória. O relógio **não** reinicia após falha/retry. |
| Paralelismo | Tempo de parede observado, com disputa de recursos real. |
| Memória | Registrar pico de VRAM alocada e reservada, RAM residente por processo e total, commit/pagefile, hard faults, I/O, espaço temporário, tempo de carregamento, estabilidade. Incluir avaliadores de QA e o frontend. |
| Estatística | Mediana, máximo e percentis **só** com amostra suficiente (n ≥ 10 por estrato, declarado). Uma execução < 60 min não prova estabilidade. Distinguir: *viável em um caso* / *viável em uma classe* / *validado no benchmark*. |

---

## 8. Observabilidade e auditabilidade

Intermediários obrigatórios (independentes de arquitetura; cada rota declara quais produz):

| Artefato | Conteúdo mínimo |
|---|---|
| `inputs/` | `A`, `B`, `S` originais + hashes. |
| `transforms.json` | Toda transformação de grade (crop, resize, pad, rotação) com inversa exata; espaço de cor; perfil ICC original. |
| `contract_frozen.*` | Máscaras nomeadas congeladas (§4.2-R) com z-order por elemento, estados e origem; **nunca derivado de `O`**. |
| `partition_measured.*` | Tecido `G` medido em `O′` por segmentador independente (+ confiança, IoU vs anotação quando houver), franja C3, C4, C5 derivados. |
| `garment_spec.json` | Atributos da peça extraídos de `B` com estado `observado`/`inferido`/`desconhecido` e confiança. |
| `candidates/` | Todo candidato gerado (inclusive descartados), seed, parâmetros, tempos, memória. |
| `qa/` | Veredito por candidato, causas, métricas por eixo, mapas de diferença em C1, mapa de inferência (C4). |
| `timeline.json` | Linha do tempo de etapas com início/fim, pico de VRAM/RAM por etapa, carregamentos/descarregamentos. |
| `manifest.json` | Modelos e hashes, versões de código, driver, Python, Torch, CUDA, SO, hardware, flags, fontes de não determinismo conhecidas. |

Reprodução: seed registrada; **igualdade de seed não implica igualdade bit a bit** entre ambientes, nem ruído equivalente entre modelos diferentes. Fontes de não determinismo (kernels de atenção, cuDNN autotune, redução paralela) são listadas por rota.

### 8.1 Piso de reconstrução e tolerâncias normativas (D-057)

`O_null1` é o piso sem edição da rota na **tupla exata** de escala/VAE/resolução/reprojeção registrada. `support.png` identifica os pixels da grade de A produzidos por esse piso; pixels simplesmente copiados de A ficam fora. Medir erro RGB de 8 bits por pixel (`max` dos canais de `abs(O_null1 − A)`) somente em `support ∩ zona`. Publicar fração de suporte, contagens por zona, p50/p95/p99/p99,5/max e SHA256 de A, O_null1, suporte e máscaras. R1-EI reprojeta a caixa inteira `[-136,193,860,1189]`, sem insertion mask; em rotas com crop, regiões descartadas ficam fora, bordas reamostradas ficam dentro; FASHN tem suporte inteiro.

Nesta parte1, zonas determinísticas vêm do parser pinado do R3 sobre A: skin=arms∪legs∪torso∪feet, background, hair_face=face∪hair, occluders=hands; clothing é só informativa. Na futura O_null2, usar máscaras humanas congeladas do Proto0. **τ_null permanece por zona**. `--null-stats` é normativa: escalar `tol_p995_support` e `tol_p995_by_zone`; PROTECTED→hair_face, pele descoberta→skin, fundo→background, FRONT_OCCLUDERS→occluders; zona ausente recorre ao escalar. O teto12 vale para escalar e cada zona: excesso rejeita a nula e dá INCONCLUSIVE (`INCONCLUSIVO` no JSON do auditor, exit3).

No perfil g0, `--null-stats` é obrigatória e seu SHA entra no FREEZE. `--a-ref` é somente cross-check, exige `--a-ref-support` ou `--a-ref-full-canvas` explícito e nunca prevalece sobre o JSON normativo; se seu escalar exceder `tol_p995_support + 1`, emitir `null_stats_inconsistent_with_a_ref` e INCONCLUSIVE. `--a-ref` sozinha e `--tol-engine` explícito ficam restritos a minimal. A referência das métricas permanece A. Preparação em `tools/null1/`, sem nula real medida nesta etapa; execução e uso dos limiares dependem das revisões previstas em `03` §7b.

---

## 9. QA definido desde a Fase 0

### 9.1 Vereditos

| Veredito | Significado | Ação automática |
|---|---|---|
| `PASS` | Todos os critérios **aplicáveis** satisfeitos, evidências e limitações registradas. | Exportar `O` + `R`. |
| `FAIL` | Falha crítica detectada (§6.2) ou orçamento excedido, com causa e localização. | Retry/rota alternativa se houver orçamento; senão rejeição. |
| `INCONCLUSIVO` | Evidência insuficiente para requisito crítico (detector sem confiança, atributo irresolúvel, `occlusion_unresolved` quando o estimador de camadas não decide a relação de um elemento, `annotation_inconsistent` quando as referências congeladas se contradizem — culpa da referência, não do motor). | **Nunca** promover a `PASS`. Em modo automático: abster-se ou tentar ação elegível no orçamento. Em modo assistido: `REVIEW`. |

### 9.2 Princípios dos detectores

- Nenhum score isolado comprova todos os requisitos. Detectores são **complementares e diagnósticos**, mapeados a causas específicas (§6.2–6.3 + `insufficient_evidence`).
- Distinguir **causa provável** de **causa demonstrada**. Registrar detector, custo e confiança; confiança do modelo ≠ probabilidade calibrada.
- **Não circular:** a estimativa produzida pelo próprio gerador (ex.: máscara que o gerador usou) não é referência de verdade para auditá-lo. Referências vêm de `A`, `B`, `S` e de estimadores independentes. **Independente do gerador não basta:** quando os estimadores do contrato e os detectores de QA são automáticos, devem ser de **famílias distintas** (ex.: SAM 3 no contrato; BiRefNet/SegFormer ou humano para `G` no dev), com a correlação de erro medida contra anotação humana (`06` L5-14). O mesmo VLM **nunca** define e julga o mesmo atributo.
- Preservação de pixels: mesma grade, mesmo espaço de cor, PNG sem perda; reportar nº de pixels alterados, erro máximo e agregado em C1. Nunca registrar/alinhar `O` a `A` para esconder deslocamento.
- Landmarks: normalizados por escala, ponderados por visibilidade/confiança. Pose 2D, embeddings de identidade e reconstrução 3D são **proxies**; não provam sozinhos preservação anatômica ou de câmera.
- Não comparar silhueta 2D de `B` com `O` como se as poses fossem iguais. Avaliar construção, proporções semânticas e correspondências confiáveis.
- Atributo oculto ou irresolúvel → `não avaliável`, não aprovação.
- VLMs locais podem checar atributos semânticos; **não** são oráculos de física/topologia. Suas respostas são evidência fraca, calibrada contra humanos na Fase 8.
- **Auditoria em dois alvos** (`O′` do motor e `O` composto), com métricas separadas em `R` (rev. 2026-10-08).
- Trivialidade proibida: preservação obtida deixando a roupa antiga intacta não passa (`garment_remnants`/`no_transfer`). Avaliar a composição completa (bordas, sombras, junções), não só o interior da peça.

### 9.3 Grupos mínimos de avaliação (a instanciar na Fase 5/8)

| Grupo | Atributos |
|---|---|
| Preservação de `A` | identidade, rosto, expressão, cabelo, landmarks, geometria articular, proporções, partes corporais visíveis, câmera/projeção, enquadramento, fundo, drift de pixels C1. |
| Fidelidade de `B` | categoria, construção, conectividade/aberturas, alças, cintura, bainha, comprimento relativo, mangas, decote, fechos, costuras, painéis, assimetria, cor intrínseca, material, estampa, textura, detalhes. |
| Coerência física | ordem de oclusão, continuidade, interseções, penetração, volume, contato, gravidade, drape, folds, tensão/compressão. |
| Realismo | coerência fotográfica, luz, sombras de contato, bordas, mistura com cabelo, resposta do material, artefatos. |
| Operação | tempo total, memória, estabilidade, reprovação, retries, taxa de aceitação, intervenção manual. |

---

## 10. Ambiguidades: resolvidas por padrão e registradas em aberto

### 10.1 Resolvidas `[PADRÃO]`

| # | Ambiguidade | Decisão padrão |
|---|---|---|
| D1 | Peça ou conjunto? | Peças claramente vestíveis selecionadas em `S`; sem `S`, conjunto detectado em `B` **se** não conflitar com `keep_from_A`. |
| D2 | Substituir ou adicionar? | `replace` da mesma categoria; `add` se `A` não tem a categoria. |
| D3 | Roupa de `A` sob a nova peça (ex.: camiseta sob jaqueta de `B`) | Mantida **só** se `mode=add_over_layer`; em `replace`, a peça de mesma categoria sai e as demais ficam. |
| D4 | Tuck/fechamento/mangas quando `B` é ambígua | Configuração mais comum da categoria; registrado como `inferido`. |
| D5 | Cabelo sobre a roupa | **Resolução padrão de z-order `uncertain`** (rev. 2026-10-08): cabelo frontal é `front_certain` quando observado à frente do corpo coberto; cabelo vs gola/capuz é `uncertain` e, sem `S`, resolve-se como "peça atrás do cabelo" **registrado como inferência**, não invariante. |
| D6 | Mãos/objetos sobre a região da peça | `FRONT_OCCLUDERS_CORE` (`front_certain`, basis observed_in_A quando ocluem o corpo coberto e são mais próximos): autoridade de reconstrução 0 e **entrada do motor** (não só da composição); mão no quadril vs aba de jaqueta é `uncertain`. |
| D7 | Múltiplas pessoas em `A` | Uma pessoa-alvo; as demais C1. |
| D8 | Fit | Intenção relativa de `B` preservada; sem tamanho comercial. |
| D9 | Cor | Intrínseca sob iluminação de `A`. |
| D10 | Saída | Canvas de `A`; PNG lossless; QA incluído. |
| D11 | Regiões recém-expostas | Síntese mínima coerente, marcada como inferida. |
| D12 | Anatomia defeituosa em `A` | Preservada; não corrigida. |

### 10.2 Registradas `[ABERTO]` (decidir até a Fase 4/5 com evidência)

| # | Questão | Por que está aberta | Experimento que decide |
|---|---|---|---|
| O1 | Tolerância numérica de C1 em rotas que reprojetam (`near_exact`) | Depende de como a rota devolve ao canvas original. | Protótipo A: medir erro máximo/agregado em C1 por rota. |
| O2 | Largura padrão da banda C5 por escala | Depende da resolução interna e do conteúdo (cabelo). | Protótipo A/D: calibrar com casos de cabelo solto. |
| O3 | Como estimar o envelope por classe (E1/E2/E3) sem usar a saída | **Reformulada (rev. 2026-10-08):** envelope = partes observadas de `A` × regra da categoria × atributos observados em `B` × folga por fit; correspondência `B→A` só para comprimentos relativos. | Prototype 0 (E1) e Protótipo F (E2/E3): referência = GT real ou banda humana congelada, nunca a saída. |
| O4 | Tamanho mínimo útil de detalhe (12/8 px) | Valores provisórios. | Protótipo B com logos/estampas de tamanhos escalonados. |
| O5 | Política para C3 (franja de contato): largura máxima | Depende da física da peça (saia volumosa vs. top justo). | Protótipo E. |
| O6 | Se `size_hint` será suportado | Sem evidência de que qualquer rota o respeite. | Decidir na Fase 4 (provavelmente **fora de escopo**). |
| O7 | Multi-ref: ganho mensurável | Modo separado; medir ganho vs. A+B. | Protótipo B (variante multi-ref). |
| O8 | Resolução interna > 1 024 dentro de 3 600 s | Depende de viabilidade (Fase 3). | Fase 3 + Protótipo B em 1 536. |
| O9 | Conjunto de teste final: tamanho acima do mínimo (40) | Depende de cobertura e custo. | Antes da Fase 7. |
| O11 | Valores iniciais do mapa de autoridade (0.7/0.5/0.3) e `r_C3` | sem calibração | Prototype 0 braço E2 + ablação de composição |
| O12 | Política de oclusor para rotas por máscara (ilha / incluído+paste / suave+paste) | fora da distribuição de treino (`06` F-13) | Prototype 0, rota R4 |

---

## 11. Critérios de sucesso do projeto (metas provisórias, a congelar antes da Fase 7)

Metas por estrato, reportadas em duas formas: (i) **qualidade entre aceitas** e (ii) **sucesso sobre todas as solicitações** (rejeições e timeouts contam como não sucesso).

| Estrato | Meta provisória de sucesso correto (ii) | Teto de aceitação indevida (PASS falso) |
|---|---|---|
| EASY | ≥ 80 % | ≤ 5 % |
| MEDIUM | ≥ 60 % | ≤ 5 % |
| HARD | ≥ 35 % | ≤ 8 % |
| EXTREME | ≥ 15 % (ou "não suportado" declarado por subclasse) | ≤ 8 % |

Regras:

- Um sistema que rejeita quase tudo **não** é robusto por acertar os poucos casos restantes: a métrica (ii) é a principal.
- Se a meta não for atingida, o requisito permanece **não atendido** no relatório final; não se ajusta a meta.
- Metas são **provisórias** e serão justificadas (ou revistas, com justificativa registrada) **antes** do teste final, nunca depois.

---

## 11-R Nota (2026-10-08)

As metas por estrato acima só serão congeladas depois do Prototype 0; o eixo **adição × pose complexa** (`addition_difficulty` no benchmark) passa a ser estrato próprio na Fase 7.

## 12. Fora de escopo (explícito)

- Treino de identidade/LoRA pessoal, malha corporal fornecida pelo usuário, máscara manual obrigatória, fotografia adicional obrigatória (todos opcionais, nunca requisito do caso central).
- Correção de anatomia de `A`.
- Garantia de tamanho/caimento físico.
- Conteúdo explícito; menores de idade.
- Qualquer dependência de nuvem/API externa para gerar, analisar ou avaliar.

---

## 13. Glossário

- **Worn reference:** `B` com a peça vestida em outra pessoa.
- **Try-off:** extração/reconstrução da peça de `B` em forma canônica (ex.: flat) como etapa intermediária.
- **Agnostic:** representação de `A` com a roupa antiga removida (termo da literatura de VTON); aqui é **uma possível implementação**, não contrato.
- **Topologia da peça:** construção/conectividade/aberturas; ≠ contorno 2D.
- **C1–C5:** classes de região/mudança (§4.2).
- **`region_contract`:** partição congelada e auditável, derivada antes da geração.
