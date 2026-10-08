# 06 — Revisão arquitetural adversarial (red-team) das Fases 0–4 e do plano da Fase 5

**Data:** 2026-10-08. **Natureza:** as Fases 0–4 e o plano A–H foram tratados como **primeira hipótese arquitetural** e submetidos a (i) re-verificação de todas as alegações decisivas em fontes primárias (7 clusters, `research_raw/07_red_team_fontes.md`), (ii) seis lentes adversariais independentes sobre D-008, representação espacial, adição × pose, oclusão/z-order, circularidade de avaliação e mecanismos da literatura, (iii) refutação adversarial dos achados de severidade alta, (iv) verificação direta no código do ComfyUI do mecanismo que a arquitetura revisada passa a depender. Nada foi preservado por já estar escrito. Nenhum modelo foi instalado; nenhum protótipo foi executado; nenhum peso grande foi baixado.

**Pergunta que guiou a revisão:** *como permitir que uma roupa totalmente nova seja criada sobre pele e/ou fundo, inclusive em pose extremamente complexa, com volume e oclusão corretos, SEM conceder ao gerador liberdade para reconstruir a anatomia, pose e câmera de A?*

**Resposta em uma frase (desenvolvida em §6):** o problema não é *quanta* liberdade o gerador recebe, mas que hoje ela é um **escalar** (denoise global — o sweep histórico mostra que nenhum valor serve) ou um **rótulo único por pixel** (a classe C2 da Fase 0 — que exige saber antes a área de uma peça que só existe depois do caimento). A arquitetura revisada separa três coisas que estavam fundidas: **invariantes de A** (congeláveis, entregues ao gerador como autoridade de reconstrução zero), **envelope de ocupação** [BAND_MIN, BAND_MAX] por classe (entregue como força **graduada**, não binária) e **ocupação realizada**, medida depois em O′ por segmentador independente; com **z-order por elemento** como entrada do motor, não só da composição. Isso é uma **hipótese (H0/H11)**, não uma decisão: o Prototype 0 existe para derrubá-la.

---

## 1. Falhas encontradas

Severidade: **A** = invalida a decisão/métrica como escrita; **M** = distorce evidência ou enfraquece o método; **B** = imprecisão. Status: ✔ confirmada por re-verificação ou por mais de uma lente; ⟳ pendente de refutação (lentes 3–6 em execução no fechamento desta versão; ver §11).

### 1.1 Arquitetura e contrato

| ID | Sev. | Onde | Falha | Status |
|---|---|---|---|---|
| F-01 | A | `00` §4.2/§4.4; `04` §1; D-002/D-008 | **Circularidade da "partição congelada"**: C2 é definida pelos pixels "onde a nova peça cobre…" — a peça só existe em O; a extensão exata depende de drape/volume/fit/pose. O contrato admite isso (§4.4 "banda de incerteza… se ocupadas por tecido"), o que exige medir em O, mas D-002 proíbe recalcular a partir de O e D-008 compõe "O = C1 ⊕ O′ em C2∪C3∪C4" como se C2 fosse conhecido antes. Reintroduz o conflito das permission zones um nível acima. | ✔ (L1, L2) |
| F-02 | A | `04` §1 camada [3]; `05` Protótipo A | **Máscara de composição indefinida**: com BAND_MAX, tudo que o gerador alterou dentro da banda sem ser tecido (pele/fundo regenerados) passa para O (lado "região grande"); com a máscara de tecido medida, perde-se C3 (sombra de contato) e nasce a costura dura que H1 teme. | ✔ (L1) |
| F-03 | A | `04` §5/§7; `05` Protótipo A | **D-008 só podia ser derrubada por costuras (H1)**; o modo de falha central — roupa não nasce dentro do envelope ou corpo é reconstruído dentro dele (o acoplamento do sweep de denoise) — não era critério de abandono nem era medido no protótipo que "decidia D-008". Protótipo F (adição) vinha depois. | ✔ (L1) |
| F-04 | A | `00` §4.2 "cada região cai em exatamente uma classe"; D5/D6 | **Partição por pixel é inconsistente com oclusão**: o mesmo pixel é C1 (mão visível) e C2 (tecido que deve nascer **atrás** dela). "Atrás" é relação entre camadas, não rótulo. Mãos/cabelo/objetos à frente exigem **z-order por elemento**. | ✔ (L2) |
| F-05 | A | `04` §1/§3 passo 6; `05` Protótipo D | **Composição determinística não resolve oclusão**: colar a mão de A sobre O′ só funciona se o motor construiu o tecido coerentemente ao redor dela. Nada no desenho informava aos motores F1 que a mão deve ficar à frente; a auditoria media identidade do oclusor em **O composto**, onde é trivialmente 1.0. | ✔ (L1, L2) |
| F-06 | A | `04` §4 H7; `05` Protótipo F | **H7 circular**: avaliava o estimador de C2 contra "o tecido final" da própria saída. Se o gerador cria pouca roupa, "excesso" sobe por culpa do gerador; se cria demais sobre o corpo, "cobertura" sobe por culpa do gerador. Não falsificável de forma atribuível. | ✔ (L1, L5⟳) |
| F-07 | A | `03` §1b conclusão (a); `04` §2 | **"Separar espacialmente as liberdades" sem mecanismo nomeado**: nenhuma rota R1–R4 tinha controle espacial contínuo; máscara binária = BAND_MAX reproduz "região grande", = BAND_MIN reproduz "não nasce" (análogo espacial do denoise 0.5). | ✔ (L1, L2) |
| F-08 | M | `04` §3 passo 4; O3 | **Estimador de extensão errado para pose complexa**: projetar a extensão de B via correspondência B→A quando B está em pé e A sentada/torcida usa o elo mais fraco (correspondência semântica sob grande delta). A ocupação deve vir da **geometria de A** (partes observadas) × **atributos da peça** (garment_spec), não da silhueta de B. | ✔ (L2) |
| F-09 | M | `00` §4.4 vs C3 | "Alterações na banda sem tecido são deriva" **contradiz C3**: sombra de contato/compressão da pele junto a gola/bainha são alterações legítimas sem tecido. A regra penalizaria o que torna a peça integrada. | ✔ (L1, L2) |
| F-10 | M | `04` §3 passo 4 | **Severidade do ovo-e-galinha depende da categoria**: para tops sobre torso nu, BAND_MAX ≈ superfície observável ⊕ folga e a incerteza é a **linha de término** (bainha/manga/decote) dentro do corpo; para saias/vestidos sobre fundo a banda é genuinamente grande. O plano tratava tudo igual. | ✔ (L1) |
| F-11 | M | `00` §10.1 D5/D6 | **z-order roupa↔elemento não é derivável só de A**: cabelo vs gola/capuz, mão no quadril vs aba, cós vs bainha dependem da peça (B) e de `layering` (S); frequentemente indecidível antes da geração. D5/D6 eram tratados como invariantes auditáveis. | ✔ (L2) |
| F-12 | M | `04` §2 R3 | **FASHN é estruturalmente cega à representação**: API = pessoa, roupa, categoria; parser/DWPose internos; sem canal de máscara/pose externo. Em casos com oclusor frontal, só pode passar se O′ já respeitar z-order sem ajuda. | ✔ (L2, cluster FASHN) |
| F-13 | M | `04` §2 R4; `02` F2 | **"Máscara nossa" para inpainting muda a distribuição de treino**: excluir o antebraço da máscara deixa uma "ilha" que modelos treinados com agnostic (que apaga braços) não entendem; incluí-lo regenera a mão. Nenhuma das duas políticas estava escolhida nem testada. | ✔ (L2) |
| F-14 | M | `02` §0; D-002 "requisito" | **Casca declarada "consequência lógica do contrato"**: o contrato exige auditabilidade e invariantes, não partição pixel-a-pixel pré-computada; rotular D-002 como "requisito" a imunizava contra evidência. | ✔ (L1) |
| F-15 | M | `tools/occupancy_audit.py` v1 | Não implementava a regra central do contrato (pixels na banda **sem** tecido devem ficar iguais a A; pele coverable não coberta intacta); misturava BODY_COVERABLE com envelope; sem FREE_SPACE; sem alvo O′ vs O; sem saturação de borda. | ✔ corrigido (v2) |
| F-16 | M | `benchmark/manifest.schema.json` v1 | `consent_adult_non_explicit` **não era obrigatório**; z-order era texto livre; sem FREE_SPACE/UNCERTAIN/franja; sem split `proto0`; sem flag de adição. | ✔ corrigido (v3) |
| F-17 | M | `tools/memory_budget.py` v1 | `layers` recebido e **não usado**; sem faixa de incerteza; apresentado como capaz de descartar candidatas; rotulava "excede VRAM residente" como quase-inviabilidade — **contradito pela observação histórica** (QIE-2511 Q5 rodou com offload). | ✔ corrigido (triagem com bandas; `NEEDS_OFFLOAD` ≠ inviável) |
| F-18 | M | `tools/inventory_windows.ps1` v1 | Um único caminho fixo (`Documents\ComfyUI`); a instalação real é `%LOCALAPPDATA%\Comfy-Desktop\ComfyUI-Installs\…\.venv`. | ✔ corrigido (detecção multi-caminho + override) |
| F-19 | B | `01` §1 item 3 | "**Não existe** benchmark público de poses difíceis" — imprecisa. Preciso: não existe benchmark público **com rótulos/splits** para reclinado/agachado, foreshortening severo, grande delta A↔B, **adição sobre pele/fundo com GT real** e múltiplos membros cruzados; existem benchmarks de mãos (VTBench-HOC), braços cruzados (OF-VTON; Fit4Men "moderate"), in-the-wild sem rótulo (OpenVTON-Bench, OmniTry wild, Tstars), P2P (StreetTryOn — que **removeu** não-frontais) e adição mask-free de acessórios sem GT (OmniTry-Bench). | ✔ (cluster benchmarks) |

### 1.2 Fontes (níveis de evidência corrigidos; detalhe em `research_raw/07`)

| ID | Sev. | Alegação anterior | Verdict | Correção aplicada |
|---|---|---|---|---|
| S-01 | A | FASHN VTON 1.5 = "stack Apache/permissiva" | **NUANCED** | Código Apache (P); pesos Apache só por snippet (S); **parser obrigatório `fashn-human-parser` herda NVIDIA Source Code License for SegFormer — não comercial** (P). Trilha permissiva de R3 depende de trocar o parser. |
| S-02 | M | FASHN: "~8 GB VRAM"; "limitações declaradas: drift corporal, resíduos" | **UNVERIFIABLE / CONTRADICTED** | Nenhuma VRAM oficial (único dado: 3 GiB em M4 Max sem parser); README sem seção de limitações; docstring afirma "preserves body features"; drift corporal passa a **hipótese nossa**; resíduos só em fontes secundárias. |
| S-03 | M | FASHN "maskless" | **NUANCED** | Pessoa inteira sem máscara por padrão (P), **mas** parser roda sempre e **recorta a peça de B** por labels da categoria (fora → cinza 127); categoria = embedding global; 7 canais pessoa+pose, 4 roupa+pose; **sem canal de máscara**; adição não bloqueada nem documentada; canvas máx. 576×864 (aspecto preservado); 0,97 B params. |
| S-04 | A | Qwen-Image-Edit-2511 com "LoRA 4/8 passos"; "pipeline de máscara nativa" | **CONTRADICTED (8 passos) / NUANCED (máscara)** | Lightning 2511 **só 4 passos** (P); `QwenImageEditInpaintPipeline` existe só para Edit single-image; **sem variante inpaint para EditPlus 2509/2511** (P). |
| S-05 | M | Nunchaku para QIE-2511 | **CONTRADICTED** | Só 2509 oficial; issue #731 fechada "inactive"; builds de terceiros. |
| S-06 | M | ControlNet pose/depth para QIE-2511 | **UNVERIFIABLE** | Loaders existem no core (`load_controlnet_qwen_fun/instantx`) e modelos Fun/InstantX para Qwen-Image/2512/2.1; **nenhuma fonte afirma compatibilidade com Edit-2511**; alternativa documentada: mapa de pose/depth **como imagem de referência**. |
| S-07 | M | FLUX.2 klein: "exemplo oficial de try-on" | **CONTRADICTED** | zero ocorrências; asset mostra troca de material de vestido (nossa leitura). Também: "~8 GB" não diz se inclui TE; **guidance fixo 1.0 e 4 passos** nos destilados; KV cache = nó experimental; Nunchaku PR #926 não mergeada. |
| S-08 | M | SAM 3 / SAM 3D Body / DINOv3 "sem cláusula NC" (lido como permissivo) | **NUANCED** | Licenças Meta custom: uso comercial não proibido, mas **proprietárias, não transferíveis, revogáveis (§6), alteráveis (§8)**, trade-control/ITAR; SAM 3D Body tem texto diferente (patente); VRAM não declarada; repo oficial exige detectron2 — **o nó nativo do ComfyUI não** (PR #14370 "dependency-free"). MHR: Apache também nos ativos (P, verificado no zip). |
| S-09 | M | SegFormer-B2-clothes "MIT" | **SECONDARY/NUANCED** | Código de treino MIT (P); pesos: tag MIT não verificada na fonte; **base NVIDIA SegFormer non-commercial** (P) e ATR não verificado → revisão legal. |
| S-10 | M | DensePose: pesos detectron2 CC BY-SA 3.0 | **NUANCED** | Vale para IUV (frase literal, P); `DENSEPOSE_CSE.md` **sem licença declarada**. |
| S-11 | M | IDM-VTON ">18 GB (issue #43)" | **CONTRADICTED (citação)** | #43 é um usuário com 4060 8 GB; limite documentado = nó ComfyUI "**at least 16GB**"; #197 (usuário): 12–16 GB insuficiente. Descarte mantido, citação corrigida. |
| S-12 | A | OmniGen2 e BAGEL "inviáveis" | **CONTRADICTED** | OmniGen2: offload documentado (~8,5 GB; sequential <3 GB; mas 1024² >10 min em 3060 — issue); BAGEL: NF4 para 12–32 GB (P). Reclassificados **MARGINAL/medir** (RAM 16 GB e multi-imagem não documentada no BAGEL continuam riscos). |
| S-13 | M | FLUX.2 dev "inviável" | **SUSTENTADO (P)** com nuance | piso oficial ~18 GB **com encoder remoto** (exige rede → proibido); 12 GB só em relatos secundários com 70–96 GB RAM. |
| S-14 | M | Layering-VTON "pesos não encontrados" | **CONTRADICTED** | pesos commitados (`weights/pytorch_lora_weights.safetensors`), LoRA sobre **Qwen-Image-Edit-2509**, modos `swap`/`add`; **sem LICENSE**; sobre pele vs. sobre roupa não documentado. |
| S-15 | M | OmniTry "blend com máscara borrada" | **CONTRADICTED** | inferência mask-free pura (`mask = zeros`), sem blur/blend; blend só na construção de dados; `object_map`: roupas = "replacing", acessórios = "trying on" → treinado para **adicionar acessórios**, não roupa sobre pele. |
| S-16 | M | CatVTON AutoMasker | **NUANCED (útil)** | `MASK_DENSE_PARTS['upper']=['torso','big arms','forearms']` entra **sempre** → pele do torso/braços é mascarada mesmo sem camiseta → **mecanicamente permite adição superior**, não validado; MaskFree = pix2pix sem máscara; branch default `edited` (2025-12). |
| S-17 | M | FitDiT "máscara dilatada-relaxada" | **NUANCED** | código desenha **retângulo** com pads/offsets de usuário; termo só no paper. |
| S-18 | B | Leffa "SDXL" | **CONTRADICTED (VTON)** | VTON = SD1.5-inpainting; SDXL só no pose transfer; "repaint" = blend gaussiano pós-geração. |
| S-19 | B | TryOffDiff "não comercial" | **NUANCED** | SSPL v1 (copyleft forte para serviços); "não comercial" é leitura do autor. |
| S-20 | B | LanPaint | novo | GPLv3; declara desempenho degradado em destilados (klein 4 passos). |
| S-21 | B | Issues citadas | corrigidas | #12334 é FLUX fp8 (não Qwen); #14433 é klein 9B GGUF em T4/13 GB (não Qwen); #16415 é relato de usuário sobre política auto-fast-disk. |
| S-22 | A | Mecanismo de denoise espacial no ComfyUI | **CONFIRMED_PRIMARY (verificação direta)** | `KSamplerX0Inpaint` aplica `denoise_mask` para qualquer modelo; Flux2/QwenImage não sobrescrevem `scale_latent_inpaint`; `DifferentialDiffusion` converte máscara suave em liberação por pixel ao longo do cronograma. |

---

## 2. Decisões mantidas

| Decisão | Status | Razão |
|---|---|---|
| Separar **motor de síntese** de **casca de auditoria/composição** (estrutura em duas camadas) | **MANTIDA** | nenhum gerador aberto preserva A por mecanismo (confirmado); a separação torna o motor substituível e a auditoria independente. O que muda é **o que** a casca congela e **como** fala com o motor (§6). |
| Referência de auditoria nunca vem do gerador; C1 estrito nunca é ampliado a partir de O | **MANTIDA** (princípio) | é o requisito anti-deriva legítimo; passa a ter experimento reversor (D-002 revisada). |
| Rejeição explícita quando nenhum candidato passa (D-003) | MANTIDA | — |
| Convenção 1 024 px lado maior; saída no canvas de A (D-004) | MANTIDA | — |
| Descartes **sustentados por fonte primária**: FLUX.2 dev (encoder remoto obrigatório abaixo de 24 GB), Step1X-Edit (18 GB mínimo), IDM-VTON (≥16 GB), OmniTry (28 GB), Hunyuan 3.0, Emu3.5, WSL2 | MANTIDOS | com citações corrigidas (S-11, S-13) |
| Componentes de percepção permissivos/nativos (SAM 3, SAM 3D Body→MHR, MoGe, BiRefNet, DWPose, DINOv2) | MANTIDOS **com nota de licença** | SAM/DINOv3 = licenças Meta proprietárias revogáveis (não "permissivas"); MHR Apache incl. ativos; MoGe-3 depende de FlexGEMM/Triton (Windows NV) → usar MoGe-2. |
| Trilha de licença O10 (uso comercial?) continua aberta | MANTIDA | agora com impacto maior: R3 (FASHN) **não** é permissiva como pipeline oficial (S-01). |

## 3. Decisões rebaixadas a hipótese

| Antes | Agora | Redação |
|---|---|---|
| **D-008** "casca de preservação + partição C1–C5 congelada + motor substituível + composição determinística + QA" (decisão estrutural) | **H0 — hipótese estrutural a testar no Prototype 0** | *O `region_contract` congelado antes da geração contém apenas: (a) PROTECTED (C1 estrito) e invariantes estruturais de A (landmarks, contorno de pele visível fora do envelope, rosto, cabelo, mãos); (b) FRONT_OCCLUDERS_CORE com z-order por elemento; (c) envelope de ocupação [BAND_MIN, BAND_MAX_BODY ∪ FREE_SPACE ∪ UNCERTAIN] por classe (E1/E2/E3) com origem e estado observado/inferido. A partição realizada (tecido, franja C3, C4, C5) é **medida em O′** por estimadores independentes do gerador, restrita ao envelope, e usada na composição. A auditoria julga invariantes e envelope, nunca a "área prevista". **Falsificação:** no Prototype 0, se para o melhor mecanismo de separação espacial não houver configuração com `coverage_of_band_min ≥ 0.9` **e** deriva de landmarks dentro da banda ≤ tolerância **e** sem `bad_occlusion` em O′ em ≥ 4/6 casos para ao menos um motor, H0 é falsa e a casca por região volta à Fase 2 (camadas explícitas / F5 / F6 como estrutura).* |
| **D-002** "partição congelada e nunca recalculada a partir de O — requisito" | **princípio com experimento reversor** | *Invariantes e envelope são congelados e nunca ampliados a partir de O; a ocupação realizada é medida em O por estimadores independentes do gerador — nunca pela máscara/atenção do próprio gerador. Reverte: Prototype 0 (se o envelope pré-computado impedir a peça de nascer ou exigir regenerar o corpo em ≥ 4/6 casos).* |
| "Composição determinística resolve oclusão" (implícito em `04` §3 passo 6 e `05` D) | **hipótese H13 (camadas)** + requisito de z-order como **entrada** do motor | ver §6.3 |
| "`02` §0: a casca é consequência lógica do contrato" | **hipótese H0** | reescrito |
| **D-009** shortlist com "R1 principal" | **candidatos prioritários sem motor principal** | ver §8 |
| **D-012** (descartes) | parcialmente **revertida** | OmniGen2 e BAGEL → MARGINAL/medir |

## 4. Decisões descartadas

| Decisão | Por quê |
|---|---|
| Cláusula "partição C1–C5 congelada antes da geração" como contrato | circular para C2/C3/C4/C5 (F-01); substituída por invariantes + envelope + ocupação medida |
| C1–C5 como **partição primária por pixel** | inconsistente com oclusão (F-04); C1–C5 passam a **vocabulário de auditoria** derivado de três campos (§6.1) |
| H7 como escrita | circular (F-06); substituída por H7′ com GT real ou banda humana congelada |
| Estimar BAND_MAX projetando a silhueta/extensão de B via correspondência B→A | elo mais fraco em pose complexa (F-08); correspondência DINOv2 rebaixada a leitura de **comprimentos relativos** (manga/bainha em unidades de segmento DWPose) |
| "Protótipo A decide D-008" com casos de substituição | não mede o modo de falha central (F-03); **Prototype 0 (adição × pose) decide H0** e vem antes de A |
| Rótulo "motor principal" para R1 antes de qualquer experimento | sem evidência (S-07: nem exemplo de try-on existe); termos passam a "candidato prioritário"/"baseline" |
| Qwen-Image-Layered como fonte de z-order | ordem das camadas decidida pelo modelo (S), conteúdo atrás alucinado, ~10 min/1024² e fp8 ~20 GB → fora da casca (L2-15) |
| Paste-back medido só em O composto como prova de oclusão | trivialmente 1.0 (F-05) → auditoria dupla O′/O |

---

## 5. Evidência histórica incorporada

Registrada em `03` §1b como `MEDIDO/OBSERVADO NO HARDWARE-ALVO — HISTÓRICO NÃO PADRONIZADO`: QIE-2511 Q5, ~544×960, ~10–15 min/imagem na RTX 5070; sweep de denoise global 0.18–0.50 (A preservada, roupa não nasce) · 0.70–0.80 (roupa nasce, geometria/drape errados, A razoavelmente preservada) · 1.00 (roupa mais forte, pose/corpo/câmera derivam). Interpretação adotada (hipótese fundamentada): **o denoise global acopla a liberdade de construir a roupa e a de reconstruir A; nenhum escalar satisfaz ambas.** Consequências: (i) o Prototype 0 reproduz esse sweep na mesma A/B como **baseline pareado** (braço E0) e o promove a `MEDIDO` com `measure_run.py`; (ii) toda rota de regeneração global tem de ser testada com separação **espacial** e **graduada** da liberdade; (iii) QIE-2511 a 1 MP com QA fica perto/acima de 1 500 s por candidato → H4 continua decisiva, e o estimador de memória foi corrigido para não confundir "precisa de offload" com "inviável" (F-17).

---

## 6. Arquitetura revisada

### 6.1 Representação espacial: três campos, não uma classe

Avaliamos as entidades propostas (BODY_COVERABLE, FREE_SPACE_FOR_GARMENT, FRONT_OCCLUDERS, BACK_CONTENT, GARMENT_CONTACT_REGION, UNCERTAIN_OCCUPANCY, NEWLY_EXPOSED). Conclusão: são úteis, mas misturam **três perguntas diferentes** que precisam de campos separados; algumas são deriváveis antes da geração como observadas, outras só como inferidas, e uma (z-order roupa↔elemento) é parcialmente indecidível.

| Campo | Pergunta | Valores | Derivável antes da geração? |
|---|---|---|---|
| **(1) Autoridade de reconstrução** `R(p) ∈ [0,1]` | o que o motor pode reescrever | 0 em PROTECTED e no núcleo de FRONT_OCCLUDERS; 1 em BAND_MIN; graduado em BAND_MAX\BAND_MIN, UNCERTAIN e CONTACT_FRINGE (valores iniciais a calibrar: 0.7 / 0.5 / 0.3) | sim, por construção a partir das máscaras |
| **(2) Autorização de ocupação** | onde o tecido **deve** / **pode** / **não pode** existir | BAND_MIN (deve) · BAND_MAX_BODY (pode: pele/roupa antiga, condicional a atributos de B) · FREE_SPACE (pode: fundo/objetos atrás) · UNCERTAIN (motor decide) · proibido = o resto | BAND_MIN/BAND_MAX_BODY/BODY_COVERABLE: **observados** (partes de A) × regra da categoria; FREE_SPACE, folga e condicionais de manga/bainha: **inferidos** (fit_intent, garment_spec de B); UNCERTAIN: por construção |
| **(3) Ordem de profundidade por elemento** | o que fica à frente/atrás da roupa nova | por elemento (`hand_L`, `forearm_R`, `hair_front`, `held_object`, `kept_garment_top`…): `front_certain` / `behind_certain` / `uncertain`, com `basis` ∈ {observed_in_A, category_rule, spec_layering, default} | **front_certain**: observável em A (elemento oclui o corpo coberto e é mais próximo — parsing + MoGe); **behind_certain**: regra da categoria (pele do torso frontal); **uncertain**: cabelo vs gola, alça vs ombro, cós vs bainha (`layering`), mão no quadril vs aba — resolvido por S ou por padrão (D5/D6 viram **resolução padrão de `uncertain`**, registrada como inferência, não invariante) |

C1–C5 continuam como **vocabulário de auditoria** (C1 ≡ PROTECTED/invariantes; C2 ≡ tecido medido dentro da autorização; C3 ≡ CONTACT_FRINGE; C4 ≡ NEWLY_EXPOSED; C5 ≡ banda de mistura), não como partição primária.

Máscaras nomeadas do `region_contract` (cada uma com origem, versão dos estimadores, estado `observado/inferido(conf)/desconhecido`, escala): `PROTECTED`, `FRONT_OCCLUDERS_CORE`, `BAND_MIN`, `BAND_MAX_BODY`, `FREE_SPACE`, `UNCERTAIN_OCCUPANCY`, `CONTACT_FRINGE` (derivada: dilatação da fronteira do envelope sobre pele/fundo, largura por escala — pendência O5), `KEPT_GARMENT_INTERFACE` (faixa junto a peças mantidas; z-order via `layering`), `NEWLY_EXPOSED`, `C5_BAND`. O artefato é dividido em `contract_frozen.*` (pré-geração) e `partition_measured.*` (pós-geração: tecido medido em O′, com estimador e confiança). O schema do benchmark já carrega esses campos (`frozen_annotation`, v3) e o auditor os consome (`tools/occupancy_audit.py` v2).

**Classes de envelope (F-10):** E1 *superfície observável* (tops, calças justas: BAND_MAX_BODY = partes observadas de A que a categoria cobre ⊕ folga por fit; a incerteza é a linha de término dentro do corpo) · E2 *superfície ⊕ fora da silhueta* (peças soltas: ⊕ folga grande por categoria/gravidade/MoGe) · E3 *fundo* (saias amplas, sentado: banda larga, anotação humana obrigatória no dev). **O Prototype 0 roda E1 primeiro** (o caso prioritário camiseta/manga longa sobre torso nu é E1).

**Exemplo canônico (camiseta nova com antebraço cruzado):** torso frontal → BAND_MIN (`behind_certain`); braço superior → BAND_MAX_BODY condicional a `sleeve_length` observado em B (`uncertain` se não observado); antebraço e mão cruzados → FRONT_OCCLUDERS_CORE (`front_certain`, basis observed_in_A: ocluem pele do torso e são mais próximos em MoGe); fundo lateral junto ao tronco → FREE_SPACE; axila/inter-membro → UNCERTAIN; pescoço junto ao decote e pele junto à bainha → CONTACT_FRINGE; cós da calça mantida → KEPT_GARMENT_INTERFACE (tuck=unknown → `uncertain`, inferido).

### 6.2 Fluxo revisado

```
A, B, S ─► [1] Análise de A (SAM 3 por texto/exemplar, SegFormer, DWPose, MoGe-2; SAM 3D Body→MHR opcional e sempre "inferido")
          [2] Análise de B (SAM 3/SegFormer → recorte da peça; garment_spec com estados; comprimentos relativos via DINOv2 só como atributos)
          [3] contract_frozen: PROTECTED, FRONT_OCCLUDERS_CORE + z-order por elemento, envelope por classe (E1/E2/E3), CONTACT_FRINGE, KEPT_GARMENT_INTERFACE, estados
          [4] Mapa R(p) de autoridade de reconstrução → canal de ligação por rota (6.3)
          [5] Motor gera O′ (candidatos; seeds)
          [6] partition_measured: tecido G em O′ por SAM 3 independente (+ confiança; calibrado vs anotação)
          [7] Composição: M_comp = dilate(G, r_C3) ∪ C5_BAND, ∩ envelope, − (PROTECTED ∪ FRONT_OCCLUDERS_CORE); oclusores frontais por cima; mistura (não cola) em CONTACT_FRINGE
          [8] Auditoria DUPLA (O′ e O): invariantes, oclusores em O′, ocupação vs envelope, nada-mudou-sem-tecido, coerência de borda tecido↔oclusor, saturação de borda do envelope
          [9] QA/seleção/retry/rejeição no orçamento
```

### 6.3 Canal de ligação por rota (o que faltava)

| Família | Como a representação entra no motor | Evidência | Hipótese |
|---|---|---|---|
| **F1** (klein, QIE) | `R(p)` como **mapa de denoise espacial** no latente: `SetLatentNoiseMask`/`InpaintModelConditioning(noise_mask)` + `DifferentialDiffusion` (liberação por pixel ao longo do cronograma). Verificado: o sampler aplica `denoise_mask` a qualquer modelo; Flux2 e QwenImage herdam; os encoders de texto **não** aceitam máscara — a máscara entra pelo latente. | **P** (S-22) | **H11:** força graduada desacopla nascimento da roupa de reconstrução de A melhor que denoise global e que máscara binária. Riscos: mapa no latente (dedos/fios precisam de C5 em pixel); round-trip do VAE; klein destilado tem 4 passos e guidance fixo 1.0 → o cronograma do DifferentialDiffusion tem 4 degraus (pode não graduar); QIE 2511 Lightning só 4 passos. |
| **F2** (Leffa/CatVTON/FitDiT, após try-off) | máscara derivada do envelope + **política de oclusor** em ablação: (a) oclusor excluído (ilha — fora da distribuição de treino, F-13), (b) incluído + paste-back, (c) incluído com máscara suave + paste-back do núcleo. Nota útil: o AutoMasker do CatVTON já mascara pele de torso/braços (S-16). | P (código) | **H13-F2:** alguma política dá tecido coerente ao redor do oclusor sem regenerar a mão. |
| **F3** (FASHN) | **nenhum canal** (categoria + pessoa + roupa; parser interno). Só auditoria pós-hoc em O′. | P (S-03) | aprovável em casos com oclusor **só** se O′ já respeitar z-order. |
| Condicionamento estrutural de A (pose/depth) | para QIE: mapa de pose/depth **como imagem de referência** (documentado em card 2509, S) ou ControlNet Fun/InstantX (**não testado com 2511**, S-06); para klein: nenhum ControlNet verificado. | S/NV | variante (f) do Prototype 0 |
| Camadas explícitas (alternativa se H0 falhar) | peça extraída de O′ como camada RGBA (SAM 3 + BiRefNet) recomposta com z-order congelado; geração em duas passagens (layout grosseiro → detalhe) | I | **H12** (layout→detalhe), **H13** (camada RGBA) |

### 6.4 O que muda nos documentos existentes (aplicado nesta revisão)

`00` §4.2/§4.4/§8/§9.3/§10 (três campos; máscaras nomeadas; franja C3 na regra da banda; D5/D6 como padrão de `uncertain`; artefatos frozen/measured; auditoria dupla) · `02` §0 (hipótese, não consequência) e §5 · `03` §1b/§4/§5 (histórico; estimador de triagem; OmniGen2/BAGEL marginais) · `04` §1–§7 (H0; shortlist sem "principal"; canal por rota; estimador por classe; H7′, H11–H13; abandono via Prototype 0; ordem) · `05` (Prototype 0 antes de A; A/D/F com auditoria dupla) · `01` §1/§11 (afirmação sobre benchmarks reformulada; licenças Meta; FASHN) · `DECISION_LOG` (D-014…D-02x) · `CHECKPOINT`.

---

## 7. Prototype 0 — ADDITION / OCCUPANCY STRESS TEST

**Objetivo:** antes de assumir válida qualquer casca, medir a capacidade **bruta** dos motores de criar uma peça inteira onde A não veste nada da categoria (pele + fundo + espaço entre membros), em pose complexa, com oclusão correta — e só então medir o que a casca acrescenta. **Motor primeiro, casca depois.**

**Casos** (`benchmark/proto0_cases.jsonl`, split `proto0`; adultos, não explícito; anotações congeladas antes de gerar; B sempre vestida em outra pessoa, em pé):

| Nível | Caso | Eixos |
|---|---|---|
| EASY | A sem camiseta, em pé, frontal → camiseta simples (B pose semelhante) | E1, sem oclusor |
| MEDIUM | A sem camiseta, sentada, torso rotacionado ~30° → camiseta (B em pé) | E1, FREE_SPACE lateral, móvel à frente da bainha |
| HARD-1 | A sem camiseta, braço cruzando o torso, mão sobre o peito → camiseta | FRONT_OCCLUDERS (antebraço+mão), UNCERTAIN (axila) |
| HARD-2 | A com braços em foreshortening, câmera baixa → peça de **manga longa** | manga segue o braço sem redesenhar o braço |
| EXTREME | A sem camiseta, reclinada, torso torcido, membro à frente, foreshortening, grande delta A↔B → camiseta **estampada**; tecido ocupa pele + fundo | todos os eixos; estampa para fidelidade |
| Controles | `same_garment_noop` (A já veste a peça) · controle negativo sintético (O = A com a mão apagada/movida → o auditor **tem** de falhar) · mesma A/B do sweep histórico (baseline pareado E0) · ≥ 1 par autoproduzido A-sem/A-com a peça (GT real para H7′) · caso "camiseta + calça mantida, tuck unknown" | sensibilidade do auditor; GT não circular; interface com peça mantida |

**Variável única por experimento (mesmo motor, 3 seeds fixas):** mecanismo de controle espacial.
E0 denoise global 0.7 / 0.8 / 1.0 (reproduz o relato histórico) · E1 `noise_mask` binária = envelope (0 em PROTECTED ∪ FRONT_OCCLUDERS_CORE) · E1′ controle negativo: máscara = BAND_MIN (deve "não nascer") · E1″ controle negativo: banda = corpo inteiro (deve reproduzir denoise 1.0) · E2 mapa graduado via DifferentialDiffusion (PROTECTED/FO_core = 0; BAND_MIN = 1.0; BAND_MAX\BAND_MIN = 0.7; UNCERTAIN = 0.5; CONTACT_FRINGE = 0.3) · E3 = E2 + condicionamento estrutural de A quando a rota aceitar · para F2: ablação de política de oclusor (a/b/c) · para F3: só E0-equivalente (sem controle) + auditoria.

**Motores (candidatos, sem "principal"):** FLUX.2 klein 4B fp8 (barato: 4 passos; permite todos os braços; Apache) · FASHN VTON 1.5 (maskless, `add` natural; parser NC) · Qwen-Image-Edit-2511 Q5 (já roda no alvo; só nos braços E0/E2 e em subconjunto, por custo; medir em frio com `measure_run.py`) · R4 try-off→CatVTON/Leffa com máscara derivada (comparador NC; AutoMasker cobre pele) · Kontext+RefTon só se sobrar orçamento. **Nenhuma rota é descartada por drift no teste bruto se a geometria da roupa for excepcional** — o objetivo é decompor capacidades.

**Cinco eixos medidos separadamente, nunca agregados** (`tools/occupancy_audit.py` v2, em **O′ e O**):

| Eixo | Métricas operacionais (referência congelada) |
|---|---|
| **A. Criar a peça** | `coverage_of_band_min` (≥ 0.9); `excess_on_body/background/forbidden`; `fabric_boundary_on_band_max_fraction` (saturação → envelope apertado vs. tecido cortado) |
| **B. Fidelidade a B** | checklist de atributos de `garment_spec` (categoria, manga, decote, estampa) por juiz atômico sim/não com ordem aleatorizada + inspeção; DINOv2 mascarado só como apoio |
| **C. Adaptação à pose** | inspeção estruturada "a peça segue torção/foreshortening ou copia a silhueta de B"; comparação pareada entre B em pose semelhante vs. muito diferente para a mesma A |
| **D. Oclusão / z-order** | `front_occluder_pixel_identity` e `garment_over_front_occluders` **em O′**; `occluder_border_coherence_proxy`; contagem de dedos/landmarks da mão; inspeção de interseção impossível sob a mão |
| **E. Preservação de A** | `unchanged_in_band_without_garment`, `uncovered_coverable_identity`, `unexplained_change_in_uncertain`; deriva de landmarks DWPose (ombros/cotovelos/punhos dentro da banda); IoU do contorno de pele visível fora do tecido; `protected_pixel_identity` (1.0 em O) |

Mais: calibração obrigatória do segmentador G (anotar G manualmente em todas as saídas; IoU/precisão/recall do SAM 3 por zona; zona com IoU baixo → INCONCLUSIVO); tempo e pico de VRAM/commit por candidato (`measure_run.py`, frio e quente); ablação da máscara de composição (envelope vs. `dilate(G, r_C3)`, r ∈ {4, 8, 16} px @1024) com métrica de costura.

**Critérios pré-registrados por rota (PASS/FAIL no gate):**

- **PASSA** no Prototype 0 se, em ≥ 4/6 casos (EASY–HARD) para ao menos um mecanismo E*: `coverage_of_band_min ≥ 0.9` **e** `front_occluder_pixel_identity(O′) ≥ 0.95` com `garment_over_front_occluders(O′) ≤ 0.02` **e** `unchanged_in_band_without_garment(O′) ≥ 0.98` **e** deriva de landmarks dentro da banda ≤ tolerância (calibrada no controle negativo) **e** sem `wrong_category`.
- **FALHA-CRIAÇÃO** se nenhum mecanismo faz a peça nascer (`coverage < 0.9`) em ≥ 3/6 → a rota não resolve adição (o problema do sweep) e sai da trilha de `add`.
- **FALHA-OCLUSÃO** se a peça nasce mas `front_occluder_pixel_identity(O′) < 0.95` ou borda incoerente em ≥ 2/6 → rota cega a oclusão; só aprovável em casos sem oclusor, e só se H13 (camadas) a resgatar.
- **FALHA-ACOPLAMENTO (decide H0)** se, para o melhor mecanismo, **não existir ponto** que satisfaça criação **e** preservação simultaneamente em ≥ 4/6 — com E1′/E1″ reproduzindo os extremos do sweep — então o controle por região é insuficiente e a arquitetura migra para camadas explícitas / F5 / F6 (volta à Fase 2).
- Orçamento: nenhuma rota entra na seleção sem tempo frio medido; QIE-2511 só continua se ≤ 1 500 s por candidato @1 MP com QA (H4).

**Ordem:** Prototype 0 **antes** do Protótipo A; A é fundido com 0 na parte de preservação; D e F passam a auditoria dupla.

---

## 8. Efeito sobre R1–R5

| Rota | Antes | Agora |
|---|---|---|
| R1 FLUX.2 klein 4B | "motor principal da trilha permissiva" | **candidato prioritário / baseline barato** (Apache; 4 passos; multi-ref ✅ confirmado). Correções: sem exemplo oficial de try-on; "~8 GB" não especifica TE; guidance fixo 1.0 e 4 passos → H11 pode não graduar; KV cache experimental; Nunchaku não oficial. Entra no Prototype 0 com todos os braços E0–E3 + variante **R1-DD** (noise_mask + DifferentialDiffusion). |
| R1b klein 9B | comparador NC | mantido; só se R1 falhar por capacidade. |
| R2 Qwen-Image-Edit-2511 | condicional à Fase 3 | **candidato prioritário para adição** (única evidência histórica de criar roupa onde VTON/warps falharam — com o acoplamento documentado). Correções: Lightning só 4 passos; sem inpaint nativo para 2511; Nunchaku só 2509; ControlNet não testado com 2511; ~10–15 min a 0,5 MP → H4 decisiva. Entra no Prototype 0 nos braços E0 (reproduz o sweep) e E2/E3 (**R2-DD**), em subconjunto. |
| R3 FASHN VTON 1.5 | "rota especializada permissiva; maskless → add natural" | **candidato prioritário para adição** (maskless real por padrão; parser recorta a peça de B; adição não bloqueada) **mas não permissiva** (parser NVIDIA NC) e **cega à representação** (sem canal); VRAM não verificada; canvas máx. 576×864; drift corporal = hipótese nossa. Entra no Prototype 0 só com auditoria em O′. Para trilha permissiva: testar substituição do parser (SegFormer-B2-clothes — herança NVIDIA também em aberto — ou SCHP MIT). |
| R4 try-off → VTON por máscara | "trilha NC de maior controle estrutural" | mantido como comparador NC; nota útil: CatVTON AutoMasker já mascara pele de torso/braços; FitDiT = retângulo folgado; política de oclusor em ablação (a/b/c); erro acumulado do try-off continua risco. |
| R5 Kontext + RefTon | comparador | mantido; RefTon sem LICENSE (confirmado); só se sobrar orçamento. |
| Novos comparadores | — | **Layering-VTON** (LoRA `add`/`swap` sobre QIE-2509, pesos existem, sem licença) e **OmniGen2 / BAGEL** (descartes revertidos → marginais; BAGEL sem multi-imagem documentada) ficam na 2.ª onda. |

## 9. Riscos ainda sem solução

1. **H11 pode não graduar em destilados**: klein (4 passos, guidance fixo) e QIE Lightning (4 passos) dão ao DifferentialDiffusion só 4 degraus; a alternativa (Base 50 passos / QIE 2511 completo) custa tempo que o orçamento talvez não tenha.
2. **Mapa no latente, não em pixel**: dedos, fios de cabelo e bordas finas precisam da banda C5 e do paste-back; o round-trip do VAE cria costuras de baixa frequência (ART-VITON/ASUKA). Medido no Prototype 0, não resolvido.
3. **z-order `uncertain` é intrinsecamente indecidível antes da geração** (cabelo vs gola, cós vs bainha); só pode ser inferido e inspecionado.
4. **Segmentador independente G** sobre tecido alucinado tem confiabilidade desconhecida; a calibração é obrigatória e pode tornar zonas inteiras INCONCLUSIVAS.
5. **Licenças**: a trilha "permissiva" perdeu R3 como pipeline oficial; SAM/DINOv3 são proprietárias revogáveis; SegFormer-B2-clothes com herança NVIDIA em aberto. A decisão O10 (uso comercial?) continua com o usuário.
6. **Nenhum benchmark externo** rotula adição sobre pele com GT real da mesma pessoa em pose difícil; o único GT possível é autoproduzido.
7. **Tempo**: QIE-2511 a 1 MP provavelmente excede 1 500 s/candidato; klein 4B é barato mas sem evidência de capacidade; FASHN é barato mas sem canal. Pode não existir rota que seja ao mesmo tempo capaz, controlável e dentro do orçamento — resultado que seria reportado como tal.

## 10. Próximo gate exato

**Gate G0 — Prototype 0, braço E0 + E2 em klein 4B e FASHN 1.5, 6 casos, 3 seeds, no hardware-alvo.**
Entrada: inventário (`tools/inventory_windows.ps1`), 6 casos anotados e validados (`benchmark/validate_manifest.py benchmark/proto0_cases.jsonl`), controle negativo sintético aprovado pelo auditor. Saída: tabela rota × mecanismo × eixo (A–E) em O′ e O, tempos frios/quentes, curva criação-vs-preservação por mecanismo. Decisão: aplicar os critérios pré-registrados de §7 por rota; H0 sobrevive, é modificada (camadas) ou cai.

## 11. Pendências desta revisão

- Lentes 3 (adição × pose por motor), 4 (oclusão/z-order), 5 (circularidade/avaliação) e 6 (mecanismos da literatura) e as refutações adversariais estavam em execução no fechamento desta versão; os achados sobreviventes serão incorporados a este documento e aos docs 00–05 na próxima atualização (ver `CHECKPOINT.md`).
