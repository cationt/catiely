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
| F-20 | A | `02` §3 matriz "Add ●●●" para F1/F3; `02` F1 q.5 | **"Add" era inferência de mecanismo, não evidência** ("regenera tudo, logo pode ocupar qualquer região"); o único dado empírico (sweep no alvo) mostra que a liberdade global não produz a peça sem reconstruir A. Nenhum README (flux2, Qwen-Image) menciona máscara/inpaint/try-on. | ✔ (L3) |
| F-21 | A | `03` §1b | **O sweep mediu só o eixo temporal** (img2img/SDEdit global); não testou o modo nativo (denoise 1.0 + A como `reference_latent`) nem o eixo espacial (máscara de latente / força por pixel). Mede a inadequação do img2img, não a capacidade de QIE-2511. Passos/CFG/flags não registrados. | ✔ (L3) |
| F-22 | A | `tools/occupancy_audit.py` v2 (eixo D em O′) | **Identidade de pixel do oclusor em O′ reprovaria toda rota que regenera o quadro** (round-trip do VAE altera quase todos os pixels em > 2/255): media "o motor é um inpainter com paste-back", não "respeitou a oclusão". | ✔ (L4) → corrigido (v3: métricas estruturais em O′) |
| F-23 | A | `04` §1 tabela; §3 passo 2 | **MoGe/SAM 3D Body não dão z-order por parte nativamente**: o nó devolve só imagem (shader depth/normals/silhouette); z por elemento exige módulo próprio (`layer_graph`) com máscaras por elemento (SAM 3 por **pontos** DWPose — `SAM3_Detect` não aceita exemplar; texto não distingue esquerda/direita) e alinhamento de escala/FOV entre MHR e MoGe. | ✔ (L4) |
| F-24 | M | `04` §1 (SegFormer para rótulos); `03` §1b (ControlNet) | **ATR não tem classe de pele do torso** → em adição o torso nu cai em fundo; `BODY_COVERABLE` deve vir da silhueta da pessoa menos elementos. **ControlNet para klein 4B e Edit-2511: inexistente** (verificado em `comfy/controlnet.py`). | ✔ (L3, L4) |
| F-25 | M | `02` F2 q.5/q.12; `04` R4 | VTON por máscara estava enquadrado como quase incapaz de adição, mas **inpainting sobre pele mascarada é o mecanismo mais direto de nascimento** (tarefa nativa); a barreira real é referência plana e regeneração de mãos. CatVTON aceita máscara desenhada; `--repaint` nunca é lido no app. | ✔ (L3) |
| F-26 | M | `04` §2 R3; `02` F3 | FASHN tem **dois modos** (seg-free default; mascarado `--no-segmentation-free` = VTON com máscara que cobre pele, com pose DWPose nativa) tratados como um; nenhum tem evidência de adição/oclusão. | ✔ (L3) |
| F-27 | M | `tools/occupancy_audit.py` v2 (`coverage_of_band_min`) | "A peça nasceu" dependia só de G: falso positivo do SAM 3 sobre pele alterada aprovaria nascimento. Falta magnitude de mudança (ΔE em BAND_MIN) e ligação com B. | ✔ (L3) → corrigido (v3) |
| F-28 | M | `03` §7; `04` §2 R2 | Mecanismos de separação espacial têm **custo multiplicativo** não precificado (LanPaint ×NumSteps, two-pass soma dois motores) — inviáveis para R2 (10–15 min/amostra) e quase gratuitos para R1. | ✔ (L3) |
| F-29 | M | `benchmark/proto0_cases.jsonl` v1 | Sem casos **pareados** (mesma A com B semelhante vs muito diferente; mesma A com B manga curta vs longa), sem GT, sem `split_by_garment_edge`: falhas seriam atribuídas indistintamente a criação, pose, fidelidade ou oclusão. | ✔ (L3, L4) → corrigido (12 casos) |
| F-30 | M | `00` D5; `04` §3 passo 6 | Cabelo sobre tecido novo: **alpha simples produz halo** da cor antiga; exige estimar também a cor de primeiro plano F (des-composição). | ✔ (L4) |
| F-31 | M | `04` §3 | Em produção o `layer_graph` virá de estimadores cuja falha em pose complexa é conhecida e não medida; erro congelado = contrato errado imposto com rigor. Precisa de avaliação estimador-vs-anotação e de `occlusion_unresolved`. | ✔ (L4) |
| F-32 | A | `00` §4.4; `occupancy_audit.py` v2 | **"Tecido da peça" decidido só por G**: saída idêntica a A com G afirmando tecido em BAND_MIN recebia PASS (teste metamórfico reproduzido). Faltava exigir mudança real vs A e ligação com B. | ✔ (L5) → corrigido (v4: `changed_fraction_in_G`, ΔE em BAND_MIN; `G_source` registrado) |
| F-33 | A | `occupancy_audit.py` (tol=2; limiares 0,95/0,98/1,0 em O′) | **Sem distribuição nula**: qualquer motor latente (VAE) altera pixels não editados acima de 2/255 → FAIL uniforme independentemente de reconstruir o corpo; o limiar era arbitrário. | ✔ (L5) → corrigido (v4: `--a-ref` = VAE round-trip de A; protocolo de nula no PREREG) |
| F-34 | A | `proto0_cases.jsonl` v1 | Manifesto inconsistente com auditor/README: `free_space_mask` nulo em casos `add_over_background` (todo tecido sobre fundo cairia em região proibida); `max_mask` legado duplicando `max_body_mask`; `uncertain_occupancy_mask` nulo apesar de z-order `uncertain`; controle no-op reutilizando máscaras de outra A; atributos "TBD". | ✔ (L5) → corrigido (19 casos; validador v2 detecta cada um) |
| F-35 | A | `manifest.schema.json`; `validate_manifest.py` | **Congelamento não provado**: hashes placeholder aceitos, arquivos inexistentes aceitos, sem `freeze_commit`/tag, anotador em texto livre; modo `add` sem exigir envelope congelado. | ✔ (L5) → corrigido (validador v2: placeholders só com `--allow-placeholders`, `--check-files`; schema v5: `freeze_commit/tag`, `annotator_id`, `inter_annotator_iou`, if/then para `add`; auditor confere sha256 via `--manifest`) |
| F-36 | M | `04` §1/§3; `proto0_cases` | **Mesmo VLM define a referência e julga** (garment_spec e checklist); códigos eliminatórios (categoria/topologia) sem detector além do VLM; atributos esperados não congelados. | ✔ (L5) → referência humana antes da geração; VLM só pré-triagem; adjudicação humana cega para eliminatórias |
| F-37 | M | `05` §0 | **Inspeção humana não cega** (um avaliador que conhece rota/seed). | ✔ (L5) → protocolo cego mínimo (hash, ordem aleatória, formulário fixo, catch trials) |
| F-38 | M | `05`; `coverage_matrix` | **Limiares calibrados nos mesmos casos em que as hipóteses são julgadas**; agregação sobre seeds indefinida; "critério fixado antes" sem mecanismo. | ✔ (L5) → `PREREG_TEMPLATE.md` (commit antes do run; hash gravado pelo auditor); calibração em controles/nula; mediana sobre seeds + pior seed; `regression` com ids novos |
| F-39 | M | `validate_manifest.py` v1; `proto0_cases` | Anti-vazamento só por ids declarados; 1 pessoa e 1 peça em 4/6 casos; exposição ao pré-treino não registrada. | ✔ (L5) → duplicatas por sha/phash; `likely_in_pretraining`; ≥ 2 pessoas/peças por nível |
| F-40 | M | `occupancy_audit.py` v2 | Auditor reprovava o **motor** por propriedade da **anotação** (envelope apertado) e não checava consistência das máscaras (BMIN ∩ FO). | ✔ (L5) → v4: flag `annotation_review_required`; pré-checagem → `INCONCLUSIVO:annotation_inconsistent` com precedência |
| F-41 | M | schema (GT) | Pares com GT subespecificados: sem G* na GT, sem alinhamento/residual quantificado, sem piso de ruído A↔GT. | ✔ (L5) → schema v5: `ground_truth_garment_mask`, `gt_alignment`, `gt_noise_floor`; `ground_truth_type: synthetic_inverse` |
| F-42 | A | `06` §6.3 (versão anterior); `07` | **"Força graduada" reduzida ao DifferentialDiffusion**: o sampler já aplica `noise_mask` float como **blend linear por passo** (semântica Blended-Latent sem resampling) — mecanismo diferente da **liberação por limiar temporal** do DD; em 4 passos o DD **discretiza** R(p) em ≤ 4 instantes (valores abaixo do último limiar ≡ 0). | ✔ (L6, código verificado) → E2a/E2b separados; R(p) definido por **instante de liberação**; braço DD também em modelos não destilados |
| F-43 | A | `06` §6.3; `04` §2 | Os mecanismos **com evidência publicada** de "inserir referência numa região" em DiTs (Easy-Insert, Insert Anything, OmniTry estágio 1, CatVTON-FLUX) operam por **máscara/buraco em pixel + regeneração dentro + paste-back**, não por blend de latente; o Prototype 0 não tinha esse braço. | ✔ (L6) → braço **E4 scaffold em pixel**; rota **R1-EI** (klein-base-4B + Easy-Insert, Apache); comparador NC Insert Anything |
| F-44 | M | `06` §6.3; `04` §2 | Layering-VTON é evidência de "pose como 3.ª referência" **quando treinado** (LoRA), não zero-shot; modo `add` = camada sobre roupa, não sobre pele; 40 passos, true-CFG 4, 20B bf16. | ✔ (L6, código) → reclassificado como comparador de canal estrutural treinado |
| F-45 | M | `06` §6.3 | Quatro "separadores" citados (BooW localization loss, MFP Focus Attention, GO-MLVTON, UR-VTON) são mecanismos de **treino ou sem código**: não testáveis. UR-VTON "majority completion" é **diagnóstico** que prevê FALHA-CRIAÇÃO para F2 em torso nu. | ✔ (L6) → classes A–D de mecanismos; H-F2-skin pré-registrada |
| F-46 | M | `04` R5/comparadores | LanPaint exige máscara **binária** e multiplica o custo (×NumSteps) → incompatível com R(p) graduado e com R2; PromptDresser depende de GPT-4o (viola "sem nuvem"). | ✔ (L6) → LanPaint só em klein como ablação secundária; PromptDresser descartado; TPD só como **estimador** de envelope |
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
| S-23 | M | Easy-Insert (huan-yin) | **CONFIRMED_PRIMARY (página)** | LoRA para FLUX.2-klein-base-4B; Apache-2.0 (sidebar; texto não lido); 4 entradas (background, insert mask, reference, reference mask); recorte 1024²; "runs on 8 GB GPUs" (alegação do autor, modo lento); "Reference Clothing Replacement" só na tagline; dados de treino e datas NV. |
| S-24 | M | DiffSynth "Template-KleinBase4B-ControlNet/-Inpaint" | **NV** | README cita só a coleção "KleinBase4B-Templates" (2026-04-28) e "KleinBase4B-i2L-v2"; itens não verificados. Qwen-Image-Blockwise-ControlNet Canny/Depth/**Inpaint** (ago/2025) são para Qwen-Image **base**; compatibilidade com Edit-2511 NV. |
| S-25 | M | ComfyUI `QwenImageDiffsynthControlnet` | **CONFIRMED_PRIMARY** | nó existe (model_patch, image, strength, mask opcional); patch Fun = 129 canais "control | keep mask | masked-image"; genérico = double-block patch; **sem menção a Qwen-Image-Edit**. |
| S-26 | M | Insert Anything | **CONFIRMED_PRIMARY (README)** | código MIT; FLUX.1-Fill-dev + Redux (NC); "nunchaku demo to support 10GB VRAM" (2025-05-07); "The mask must fully cover the area to be edited"; roupa/VITON-HD **não** no README (só no paper, snippet). |
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
| **(3) Ordem de profundidade por elemento** | o que fica à frente/atrás da roupa nova | por elemento (`hand_L`, `forearm_R`, `upper_arm_L`, `hair_front`, `held_object`, `furniture`, `kept_garment_top`…), **com máscara 2D própria**: `front_certain` / `behind_must_cover` / `behind_may_cover` / `split_by_garment_edge` / `uncertain`, com `basis` ∈ {observed_in_A, category_rule, spec_layering, default} (contrato `00` §4.5) | **front_certain**: observável em A (elemento oclui o corpo coberto e é mais próximo — SAM 3 por pontos DWPose + mediana do render depth do MHR; móveis por MoGe com FOV compartilhado); **behind_must_cover**: regra da categoria (pele do torso frontal); **behind_may_cover**: depende de atributo observado em B (manga); **split_by_garment_edge**: fronteira = bainha sob a mão, cai em UNCERTAIN; **uncertain**: cabelo vs gola, alça vs ombro, cós vs bainha (`layering`), mão no quadril vs aba — resolvido por S ou por padrão (D5/D6 viram **resolução padrão**, registrada como inferência). O estimador automático é um **módulo próprio** (o nó nativo devolve só imagem) e precisa de avaliação vs anotação antes de alimentar o contrato |

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

### 6.3 Canais de ligação por **classe de mecanismo** (revisado após L6)

| Classe | Mecanismo | O que faz | Evidência | Custo | Braço do Prototype 0 |
|---|---|---|---|---|---|
| **A. Sampler/latente** | `noise_mask` **suave** (sem DD) | blend linear por pixel **em todos os passos**: `x = x·m + latente(A)·(1−m)` antes e depois do modelo — "denoise parcial espacial" (`KSamplerX0Inpaint`, qualquer modelo) | **P** (código) | ×1,0 | **E2a** |
| | `noise_mask` + **DifferentialDiffusion** | o valor do mapa vira o **instante** a partir do qual o pixel é liberado (`binary_mask = m ≥ threshold(t)`); em 4 passos discretiza em ≤ 4 instantes; valores abaixo do último limiar ≡ 0 | **P** (código) | ×1,0 | **E2b** — níveis de R(p) definidos por **passo de liberação**, derivados do cronograma de sigmas do motor; rodar também em klein **Base** (50 passos) para separar "não gradua" de "não tem passos" |
| | LanPaint | sampler com "raciocínio" por passo; **máscara binária obrigatória**; ×NumSteps; GPLv3; degradação declarada em destilados | **P** | ×2–10 | só klein, NumSteps 2, ablação secundária; **fora de R2** |
| **B. Prior de ocupação em pixel** | **scaffold/buraco no envelope** + referência de B + paste-back por G medida | a ocupação deixa de ser inferida pelo denoise e vira **entrada**: BAND_MIN sólido, BAND_MAX\BAND_MIN graduado/neutro, oclusores `front_certain` **visíveis**; regeneração total dentro; composição pela ocupação **medida** | **P** para o padrão (Easy-Insert, Insert Anything, OmniTry estágio 1, CatVTON-FLUX usam máscara em pixel) | ×1,0–1,5 | **E4** — klein-base-4B + Easy-Insert (R1-EI); QIE-2511 zero-shot com buraco (NV); comparador NC Insert Anything |
| **C. Canal treinado disponível** | Easy-Insert (LoRA Apache, klein-base-4B) · Insert Anything (Fill+Redux, NC) · Layering-VTON (pose como 3.ª ref., LoRA sobre QIE-2509, sem licença) · DiffSynth Blockwise-Depth/Inpaint (Qwen-Image base; patch `QwenImageDiffsynthControlnet` no core; compatibilidade com Edit-2511 **NV**) | estrutura/ocupação entram por pesos treinados | P / NV | var. | E4 (Easy-Insert, Insert Anything); **E3** (QIE: depth MoGe-2 como 3.ª referência zero-shot — S; patch Blockwise — NV, smoke test antes do gate); Layering-VTON como comparador de canal treinado em 2 casos |
| **D. Perdas de treino sem pesos** | BooW-VTON localization loss · MFP-VTON Focus Attention · GO-MLVTON · UR-VTON | separam em **treino**; não acionáveis em inferência | S | — | só se o projeto treinar uma LoRA própria sobre klein-base-4B (fora desta fase) |
| **F2 (VTON por máscara)** | máscara derivada do envelope \ FO com **oclusor visível** + política (a) ilha / (b) incluído+paste / (c) suave+paste | tarefa nativa de inpainting; AutoMasker do CatVTON já cobre pele; risco **H-F2-skin** (UR-VTON "majority completion": contexto de pele → completa pele) | P (código) / S | ×1,0 | R4: curva `coverage_of_band_min` × largura da máscara |
| **F3 (FASHN)** | nenhum canal; dois modos (seg-free / mascarado) | — | P | ×1,0 | só auditoria em O′ |
| **Condicionamento estrutural de A** | **ControlNet inexistente** para klein 4B e Edit-2511 (`comfy/controlnet.py`); substitutos: pixels de A fora da máscara como restrição dura; A como `reference_latent`; depth **MoGe-2** (observado) como referência extra em QIE (S); SAM 3D Body só para BODY_COVERABLE/QA (inferido → risco de impor corpo diferente) | P/S | — | E3 só em QIE |
| **Ordem na entrada + saída** | oclusor `front_certain` visível e excluído da região editável; composição = ordem na saída; detector `duplicate_limb` | — | L4 | — | todos os braços com canal |
| **Camadas explícitas (H13)** | peça extraída de O′ como RGBA (SAM 3 + BiRefNet) recomposta com z-order; Qwen-Image-Layered-Control-V2 (DiffSynth) como extrator de oclusor **NV**, 2.ª onda | I | — | só se H0 falhar |

**Taxonomia que substitui "força graduada" (F-42):** (i) blend de latente (E2a), (ii) liberação temporal (E2b), (iii) scaffold em pixel (E4), (iv) canal treinado (C). A hipótese H11 divide-se em **H11a** (blend) e **H11b** (liberação temporal); **H-DD4** prevê que em 4 passos E2b ≈ E1 binária.

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
| HARD-3 / HARD-4 (par) | mesma A, braços cruzados, mão agarrando o braço superior oposto; B **manga curta** → `split_by_garment_edge` no braço superior (bainha sob a mão); B **manga longa** → `behind_must_cover` | a fronteira deve seguir a manga de **B**, não o corpo de A |
| Pares de atribuição | `proto0_hard_01_pair_b` (mesma A, B em pose semelhante → isola eixo C); `proto0_easy_01_pair_b` (mesma A fácil, B estampada do EXTREME → isola fidelidade) | separar criação, pose e fidelidade |
| Controles | `same_garment_noop` (A já veste a peça; calibra falso nascimento via ΔE e falsos resíduos) · `proto0_ctrl_negative_synth_01` (O fabricado com a mão apagada/movida → o auditor **tem** de falhar) · mesma A/B do sweep histórico (baseline pareado E0) · `proto0_gt_pair_01` autoproduzido (mesma pessoa, tripé, sem/com a peça → GT real de ocupação e z-order para H7′) · caso "camiseta + calça mantida, tuck unknown" | sensibilidade do auditor; GT não circular; interface com peça mantida |

**Pré-requisito (antes de gerar qualquer imagem):** avaliação do estimador de camadas vs anotação humana por caso — IoU por elemento (SAM 3 por pontos DWPose), acerto da relação front/behind (MHR depth mediano), fração do torso nu que o parser rotula como fundo; elementos com IoU < 0,85 → `uncertain`. Tempo/VRAM de cada estimador com `measure_run.py` (entram nos 3 600 s; VRAM do SAM 3D Body não declarada).

**Variável única por experimento (mesmo motor, 3 seeds fixas):** mecanismo de controle espacial — com **oclusores `front_certain` visíveis no contexto** em todos os braços com canal.
E0 denoise global 0.7 / 0.8 / 1.0 (reproduz o relato histórico; **baseline do acoplamento, proibido como rota**) · E0′ modo nativo do editor (denoise 1.0, A como `reference_latent` + recorte de B, sem máscara) · E1 `noise_mask` binária = envelope (0 em PROTECTED ∪ FRONT_OCCLUDERS_CORE) · E1′ controle negativo: máscara = BAND_MIN (deve "não nascer") · E1″ controle negativo: banda = corpo inteiro (deve reproduzir denoise 1.0) · **E2a** `noise_mask` suave sem DD (blend linear) · **E2b** `noise_mask` + DifferentialDiffusion com níveis de R(p) definidos por **instante de liberação** (script imprime os limiares `(ts−ts_to)/(ts_from−ts_to)` por motor/cronograma antes do gate; rodar também em klein Base 50 passos) · **E3** (só QIE) depth MoGe-2 como 3.ª referência; patch Blockwise-Depth/Inpaint (NV, smoke test) · **E4** scaffold de ocupação em **pixel** dentro do envelope (BAND_MIN sólido; BAND_MAX\BAND_MIN neutro; oclusores visíveis) + recorte de B como referência — klein-base-4B + Easy-Insert (R1-EI); QIE-2511 zero-shot com buraco (NV) · para F2: ablação de política de oclusor (a/b/c) e curva cobertura × largura da máscara (H-F2-skin) · para F3: dois modos + auditoria.

**Motores (candidatos, sem "principal"), em ordem de custo/informação:** (1) FLUX.2 klein 4B fp8 — E0′, E1, E1′/E1″, E2a, E2b (4 passos; Apache) → (2) **klein-base-4B + Easy-Insert (R1-EI)** — E4 (15 passos NV; Apache; medir frio) → (3) FASHN VTON 1.5 em **dois modos** (seg-free e mascarado; parser NC; sem canal) → (4) Qwen-Image-Edit-2511 Q5 em subconjunto (easy_01, hard_01; 544×960; 1–2 seeds; sob H4) — E0 (reproduz o sweep), E0′, E4, E3; E2 em QIE só se E2 em klein mostrar sinal → (5) R4 CatVTON com máscara desenhada = envelope \ FO, com B plana (try-off) **e** B vestida recortada (testa "in-shop or worn"); política a/b/c → (6) **R8 two-pass FASHN → klein 4B** → comparadores em 2 casos cada: **Insert Anything** (Fill+Redux Nunchaku ~10 GB, NC; teto do mecanismo máscara+referência), **Layering-VTON** (canal treinado de pose; sem licença), Qwen-Image-2.1 / ACE++ só se R1/R2 falharem em criação. **Fora:** LanPaint em QIE; PromptDresser (GPT-4o); Qwen-Image-Layered como motor. Custo por mecanismo em `03` §1c. **Nenhuma rota é descartada por drift no teste bruto se a geometria da roupa for excepcional** — o objetivo é decompor capacidades.

**Cinco eixos medidos separadamente, nunca agregados** (`tools/occupancy_audit.py` v2, em **O′ e O**):

| Eixo | Métricas operacionais (referência congelada) |
|---|---|
| **A. Criar a peça** | `coverage_of_band_min` (≥ 0.9) **e** `band_min_change_magnitude` (ΔE em BAND_MIN > p95 do no-op); `excess_on_body/background/forbidden`; `fabric_boundary_on_band_max_fraction` (saturação → envelope apertado vs. tecido cortado); ligação com B (DINOv2 mascarado vs peça aleatória) alimenta B |
| **B. Fidelidade a B** | checklist de atributos de `garment_spec` (categoria, manga, decote, estampa) por juiz atômico sim/não com ordem aleatorizada + inspeção; DINOv2 mascarado só como apoio |
| **C. Adaptação à pose** | inspeção estruturada "a peça segue torção/foreshortening ou copia a silhueta de B"; comparação pareada entre B em pose semelhante vs. muito diferente para a mesma A |
| **D. Oclusão / z-order** | **em O′, estruturais:** `garment_over_element` por elemento `front_certain` (≤ 2 %), `occluder_mask_iou` (≥ 0,9; SAM 3 por pontos em O′), `hand_keypoint_shift` (DWPose; limiar calibrado no controle negativo), `duplicate_limb`, `coverage_of_band_min_near_occluders` (tecido existe junto ao oclusor); elementos `behind_must_cover` cobertos; inspeção de interseção impossível sob a mão. **Em O:** identidade de pixel do núcleo dos oclusores (1,0), `composition_seam` (O vs O′ na coroa), `hair_halo`. Identidade de pixel em O′ é só diagnóstica (VAE). |
| **E. Preservação de A** | `unchanged_in_band_without_garment`, `uncovered_coverable_identity`, `unexplained_change_in_uncertain`; deriva de landmarks DWPose (ombros/cotovelos/punhos dentro da banda); IoU do contorno de pele visível fora do tecido; `protected_pixel_identity` (1.0 em O) |

Mais: calibração obrigatória do segmentador G (anotar G manualmente em todas as saídas; IoU/precisão/recall do SAM 3 por zona; zona com IoU baixo → INCONCLUSIVO); tempo e pico de VRAM/commit por candidato (`measure_run.py`, frio e quente); ablação da máscara de composição (envelope vs. `dilate(G, r_C3)`, r ∈ {4, 8, 16} px @1024) com métrica de costura.

**Metodologia anti-autoengano (L5), obrigatória antes de qualquer veredito:**
1. **Congelamento verificável:** máscaras anotadas (2 anotadores ou 2 passes cegos; `inter_annotator_iou` por máscara), sha256 reais, `freeze_commit`/`freeze_tag` (`proto0-frozen-v1`) **anteriores** ao primeiro run; `validate_manifest.py --check-files` sem placeholders; o auditor confere os hashes (`--manifest --case-id`) e grava o sha do `PREREG.md`.
2. **Distribuição nula por rota:** `O_null1` = VAE encode/decode de A (denoise 0, mesma resolução/reprojeção) e `O_null2` = pipeline em `same_garment_noop`; τ_null = p99,5 por zona; limiares de identidade e ΔE derivados daí (auditor `--a-ref`), nunca fixados a priori.
3. **Controles do auditor devem produzir o veredito esperado antes de qualquer caso real contar:** `identity_output` (O := A) → FAIL; `known_drift_positive` (denoise 1,0 do sweep) → FAIL por reconstrução; `fabric_over_occluder_synthetic` e `hand_removed_synthetic` → FAIL z-order/duplicate; `same_garment_noop` e `B_leak_specificity_probe` → PASS. Validar o auditor na **sweep histórica** (0,18…1,00) com anotação congelada daquela A: cobertura crescente e identidade decrescente a partir de ~0,7 — se não reproduzir a observação humana, o auditor não está pronto.
4. **G calibrado:** anotar G manualmente em todas as saídas (cego às máscaras e às métricas); IoU/precisão/recall do SAM 3 por zona; `G_source` registrado; zona abaixo do limiar → INCONCLUSIVO.
5. **Referências e julgamento com famílias distintas:** atributos esperados fixados por humano antes da geração (sem "TBD"); VLM só pré-triagem; códigos eliminatórios (categoria, topologia, interseção, oclusão) adjudicados por **humano cego** (saídas por hash, ordem aleatória, formulário fixo, catch trials).
6. **Pré-registro** (`benchmark/proto0/PREREG_TEMPLATE.md`): hipóteses, casos, limiares com origem, regra de agregação (mediana sobre seeds + pior seed), consequências — commitado antes do run.
7. **Tolerâncias nunca mais apertadas que a discordância inter-anotador.**

**Critérios pré-registrados por rota (PASS/FAIL no gate):**

- **Ordem de execução:** começar por `proto0_easy_01`; um braço só avança para MEDIUM/HARD/EXTREME se criar a peça (eixo A) em ≥ 2/3 seeds; braço que não cria a peça em EASY é rotulado **replace-only** e sai sem discussão de fidelidade.
- **PASSA** no Prototype 0 se, em ≥ 4/6 casos (EASY–HARD) para ao menos um mecanismo E*: `coverage_of_band_min ≥ 0.9` com ΔE acima do no-op **e** por elemento `front_certain`: `garment_over_element(O′) ≤ 0.02`, `occluder_mask_iou(O′) ≥ 0.9`, zero `duplicate_limb` **e** `unchanged_in_band_without_garment(O′) ≥ 0.98` **e** deriva de landmarks/keypoints de mão dentro da banda ≤ tolerância (calibrada no controle negativo) **e** sem `wrong_category`.
- **FALHA-CRIAÇÃO** se nenhum mecanismo faz a peça nascer (`coverage < 0.9`) em ≥ 3/6 → a rota não resolve adição (o problema do sweep) e sai da trilha de `add`.
- **FALHA-OCLUSÃO** se a peça nasce mas `garment_over_element(O′) > 0.02` em elementos `front_certain`, `occluder_mask_iou < 0.9`, `duplicate_limb` ou `coverage_of_band_min_near_occluders < 0.9` em ≥ 2/6 → rota cega a oclusão: adição × oclusão declarada **não suportada** para a rota (domínio limitado), não "corrigível por composição".
- **FALHA-ACOPLAMENTO (decide H0)** se, para o melhor mecanismo (incluindo **E4 scaffold em pixel**), **não existir ponto** que satisfaça criação **e** preservação simultaneamente em ≥ 4/6 — com E1′/E1″ reproduzindo os extremos do sweep — então o controle por região é insuficiente e a arquitetura migra para camadas explícitas / F5 / F6 (volta à Fase 2).
- **H-F2-skin** confirmada (R4 produz pele em vez de tecido em UNCERTAIN/BAND_MAX\BAND_MIN em ≥ 3/6) → F2 fica **replace-only** sem precisar dos 6 casos.
- **H-DD4** (E2b ≈ E1 em 4 passos e só gradua em klein Base/QIE completo) → o mapa graduado só é viável onde o orçamento permitir ≥ 20 passos.
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
| **R1-EI** (novo) | — | **klein-base-4B + Easy-Insert** (LoRA Apache; inserção por referência em região mascarada; "8 GB" em modo lento, NV): motor do braço **E4**; capacidade em roupa/adição NV ("Reference Clothing Replacement" só na tagline). |
| **R8** (novo) | — | two-pass FASHN → klein 4B (rota de teste). |
| Comparadores | — | **Insert Anything** (Fill+Redux, NC, Nunchaku ~10 GB) = teto do mecanismo máscara+referência em 2 casos; **Layering-VTON** reclassificado como comparador de canal estrutural **treinado** (pose como 3.ª ref.), sem licença, 2 casos; **OmniGen2 / BAGEL** marginais, 2.ª onda; **TPD** só como estimador de envelope (H7′); **PromptDresser descartado** (GPT-4o). |

## 9. Riscos ainda sem solução

1. **H11 pode não graduar em destilados**: klein (4 passos, guidance fixo) e QIE Lightning (4 passos) dão ao DifferentialDiffusion só 4 degraus; a alternativa (Base 50 passos / QIE 2511 completo) custa tempo que o orçamento talvez não tenha.
2. **Mapa no latente, não em pixel**: dedos, fios de cabelo e bordas finas precisam da banda C5 e do paste-back; o round-trip do VAE cria costuras de baixa frequência (ART-VITON/ASUKA). Medido no Prototype 0, não resolvido.
3. **z-order `uncertain` é intrinsecamente indecidível antes da geração** (cabelo vs gola, cós vs bainha); só pode ser inferido e inspecionado.
4. **Segmentador independente G** sobre tecido alucinado tem confiabilidade desconhecida; a calibração é obrigatória e pode tornar zonas inteiras INCONCLUSIVAS.
5. **Licenças**: a trilha "permissiva" perdeu R3 como pipeline oficial; SAM/DINOv3 são proprietárias revogáveis; SegFormer-B2-clothes com herança NVIDIA em aberto. A decisão O10 (uso comercial?) continua com o usuário.
6. **Nenhum benchmark externo** rotula adição sobre pele com GT real da mesma pessoa em pose difícil; o único GT possível é autoproduzido.
7. **Estimador de camadas em produção**: o `layer_graph` virá de estimadores com falha conhecida em pose complexa; erro congelado = contrato errado imposto com rigor. Mitigação: avaliação vs anotação, `uncertain` por desacordo, `occlusion_unresolved` em R, modo assistido.
8. **Cabelo**: des-composição α+F exige estimador de cor de primeiro plano (disponibilidade local/licença não verificadas).
9. **Discretização do DD em 4 passos** (F-42): níveis 0,7/0,5/0,3 podem equivaler à máscara binária; só gradua em ≥ 20 passos, que custam tempo. E2a (blend linear) pode manter o "fantasma" de pele que impede a roupa de nascer — reproduzindo o acoplamento do sweep sob outra forma.
10. **Capacidade do único mecanismo permissivo com evidência de inserção por referência (Easy-Insert) em roupa/adição é NV**; o buraco regenera pele dentro do envelope (`uncovered_coverable_identity` baixo esperado) → a casca terá de recompor mais.
11. **Estimadores do contrato e detectores de QA da mesma família** (SAM 3 em A e em O′) podem errar correlacionadamente; no dev, G humano; em produção, famílias distintas e medição da correlação de erro.
12. **Tempo**: QIE-2511 a 1 MP provavelmente excede 1 500 s/candidato; klein 4B é barato mas sem evidência de capacidade; FASHN é barato mas sem canal. Pode não existir rota que seja ao mesmo tempo capaz, controlável e dentro do orçamento — resultado que seria reportado como tal.

## 10. Próximo gate exato

**Gate G0 — Prototype 0 em klein 4B (E0′, E1, E1′/E1″, E2a, E2b), klein-base-4B + Easy-Insert (E4) e FASHN 1.5 (seg-free e mascarado), começando por `proto0_easy_01` e avançando por nível; 3 seeds; no hardware-alvo; PREREG commitado e tag `proto0-frozen-v1` anteriores ao primeiro run.**
Entrada: inventário (`tools/inventory_windows.ps1`); 19 casos (12 reais + controles do auditor) anotados por elemento por 2 anotadores e validados com `validate_manifest.py --check-files` (sem placeholders); distribuição nula por rota; avaliação do estimador de camadas vs anotação; os quatro controles negativos do auditor **reprovados** e os dois positivos **aprovados**; auditor validado na sweep histórica; mesma A/B do sweep medida em frio (`measure_run.py`) para promover o relato a `MEDIDO`; `tests/test_occupancy_audit.py` verde. Saída: tabela rota × mecanismo × eixo (A–E) em O′ e O, tempos frios/quentes, curva criação-vs-preservação por mecanismo. Decisão: aplicar os critérios pré-registrados de §7 por rota; H0 sobrevive, é modificada (camadas) ou cai.

## 11. Pendências desta revisão

- Todas as seis lentes foram **incorporadas** (L1–L2: F-01…F-19; L3–L4: F-20…F-31; L5–L6: F-32…F-46).
- **Refutação adversarial (estado honesto):** o estágio de refutação foi interrompido por reinício do contêiner. Três achados altos foram refutados com evidência — L1-1, L1-2 e L2-2 — e em todos os três o refutador concluiu que o achado **descrevia a versão anterior do repositório e a mudança proposta já estava aplicada** (ou seja, confirmou o achado sobre o texto original e a correção). Os demais achados altos **não passaram por refutação adversarial independente**; estão marcados como "confirmados por lente, verificados em fonte primária onde indicado" e não como "sobreviventes a refutação". Nenhum achado alto depende de alegação que eu não tenha conseguido verificar em código/repositório, exceto os marcados NV (templates DiffSynth para klein; compatibilidade do patch Blockwise com Edit-2511; capacidade do Easy-Insert em roupa).
