# Fase 4 — Seleção provisória de arquitetura, hipóteses falsificáveis e critérios de abandono

**Data:** 2026-10-07 · **revisado em 2026-10-08 pelo red-team** (`06_RED_TEAM_REVISION.md`): D-008 rebaixada a hipótese H0; shortlist sem "motor principal"; Prototype 0 antes do Protótipo A; H7 substituída; canal de ligação por rota explicitado. **Natureza desta decisão:** **provisória**. Baseia-se em evidência de fontes primárias e relatos (Fases 1–3), **sem nenhuma medição no hardware-alvo e sem nenhum protótipo executado**. Será revisada obrigatoriamente após a Fase 3 medida e os Protótipos A–H. Nada aqui é compromisso irrevogável.

---

## 1. Hipótese estrutural H0 (ex-D-008): casca de invariantes + envelope + motor substituível

**D-008 foi rebaixada a hipótese (D-014).** A estrutura em duas camadas permanece; a cláusula "partição C1–C5 congelada antes da geração" foi **rejeitada** por circularidade (a área da peça só existe depois do caimento) e por não expressar oclusão (`06` F-01, F-04).

```
A, B, S ──► [1] Análise de A e B      ──► invariantes de A; garment_spec(B) com estados
            [2] contract_frozen       ──► PROTECTED · FRONT_OCCLUDERS_CORE + z-order por elemento · envelope [BAND_MIN, BAND_MAX_BODY ∪ FREE_SPACE ∪ UNCERTAIN] por classe E1/E2/E3 · CONTACT_FRINGE · KEPT_GARMENT_INTERFACE
            [3] mapa R(p) de autoridade de reconstrução (0 → 1, graduado) → canal de ligação da rota (§3.1)
            [4] Motor (R*)            ──► O′ (candidatos, seeds)
            [5] partition_measured    ──► tecido G em O′ por segmentador INDEPENDENTE (calibrado); franja C3 = dilate(G, r_C3)
            [6] Composição            ──► M_comp = dilate(G, r_C3) ∪ C5_BAND, ∩ envelope, − (PROTECTED ∪ FRONT_OCCLUDERS_CORE); oclusores frontais por cima; mistura em CONTACT_FRINGE
            [7] Auditoria DUPLA (O′ e O) + QA/seleção/retry/rejeição
```

**H0 (redação completa em `06` §3).** Falsificação: Prototype 0 — se, para o melhor mecanismo de separação espacial, não existir configuração com `coverage_of_band_min ≥ 0.9` **e** deriva de landmarks dentro da banda ≤ tolerância **e** sem `bad_occlusion` em O′ em ≥ 4/6 dos seis casos core congelados em `benchmark/proto0/g0_case_roles.json` (`proto0_easy_01`, `proto0_medium_01`, `proto0_hard_01`, `proto0_hard_02`, `proto0_hard_03`, `proto0_hard_05`) para ao menos um motor, a casca por região é insuficiente → voltar à Fase 2 (camadas explícitas / F5 / F6).

Riscos conhecidos: costuras do VAE (ART-VITON/ASUKA); mapa no latente (dedos/cabelo via C5 em pixel); destilados de 4 passos dão ao DifferentialDiffusion só 4 degraus; z-order `uncertain` indecidível a priori.

Componentes da camada de análise/QA (nenhum é o gerador; licenças re-verificadas em `research_raw/07`):

| Função | Componente provisório | Licença (verificada) | Nota |
|---|---|---|---|
| Segmentação por conceito/exemplar (partes de A; peça em B; tecido G em O′) | **SAM 3/3.1** (nativo no core) + **BiRefNet** (bordas/C5) | SAM License (Meta, proprietária revogável; comercial não proibido) / MIT | G exige calibração vs anotação (IoU por zona) |
| Rótulos de vestuário/pele | SegFormer-B2-clothes | código MIT; pesos: tag MIT não verificada; base NVIDIA **NC** | revisão legal; alternativa SCHP (MIT, inplace_abn no Windows) |
| Pose/landmarks (invariantes; atribuição de pixels a segmentos) | **DWPose/rtmlib** | Apache-2.0 | sem breakdown em sentado/deitado |
| Profundidade / ordem antebraço↔torso / fundo adjacente (FREE_SPACE) | **MoGe-2** (nativo) | MIT (pesos NV); MoGe-3 exige FlexGEMM/Triton (Windows NV) | usar MoGe-2 |
| Superfície do torso oculta (UNCERTAIN) | **SAM 3D Body→MHR** (nativo, sem detectron2) | SAM License / MHR Apache incl. ativos | sempre `inferido`; VRAM não declarada |
| Atributos relativos da peça (manga/bainha) | DINOv2 features | Apache-2.0 | **não** gera máscara (F-08) |
| Juiz semântico (atributos; nunca física/topologia) | Qwen3-VL-8B Q4 | Apache-2.0 | perguntas atômicas; ordem aleatorizada |
| Auditoria de pixels / ocupação / z-order / identidade da peça | `tools/pixel_preservation_check.py`, `tools/occupancy_audit.py` v5, `tools/garment_fidelity_audit.py`, `tools/g0_gate.py` (+ `freeze_proto0.py`) | — | referências congeladas (FREEZE.json); dois alvos; evidência obrigatória por manifesto |

## 2. Shortlist de motores (R1–R4) e por que cada um está onde está

| Rota | Motor | Família | Licença | Status | Por que mantida | O que a derruba |
|---|---|---|---|---|---|---|
| **R1** | **FLUX.2 klein 4B** (fp8/bf16) com A + recorte(s) da peça de B como referências; variante **R1-DD** (noise_mask + DifferentialDiffusion com mapa R(p)) | F1 | **Apache-2.0** | **CANDIDATO PRIORITÁRIO / baseline barato** (não "principal": sem exemplo oficial de try-on, S-07) | único editor multi-ref permissivo que cabe com folga ("~8 GB", TE não especificado, `P`); 4 passos e guidance fixo 1.0 → barato para todos os braços do Prototype 0; multi-ref ✅ (`P`) | Prototype 0: FALHA-CRIAÇÃO ou FALHA-ACOPLAMENTO; H11 não gradua em 4 passos; Protótipo B: `wrong_category`; vazamento de B não controlável |
| **R1b** | FLUX.2 klein 9B / 9B-KV | F1 | FLUX NC | MANTIDA como comparador NC | melhor aberto em GEditBench v2 (`R`) | Fase 3: s/it com offload inviável; licença, se uso comercial |
| **R2** | **Qwen-Image-Edit-2511** Q5 GGUF (já roda no alvo: ~10–15 min a 0,5 MP, histórico) ou 2509+Nunchaku NVFP4; variante **R2-DD** | F1 | **Apache-2.0** (repo) | **CANDIDATO PRIORITÁRIO PARA ADIÇÃO — condicional a H4** | única evidência (histórica) de criar roupa nova onde VTON/warps falharam, com o acoplamento do denoise global; multi-imagem (limite oficial não documentado); correções: Lightning 2511 **só 4 passos**; sem inpaint nativo para 2511; Nunchaku só 2509; ControlNet não testado com 2511 (mapa de pose como referência é o caminho documentado) | H4: frio > 1 500 s/candidato @1 MP; Prototype 0: FALHA-ACOPLAMENTO mesmo com R2-DD |
| **R3** | **FASHN VTON 1.5** (subprocesso) com A + B vestida (`garment_photo_type=model`) | F3 | código Apache; pesos NV; **parser obrigatório NVIDIA NC** (S-01) | **CANDIDATO PRIORITÁRIO PARA ADIÇÃO — não permissivo como pipeline oficial; cego à representação** | maskless real na pessoa (default), parser recorta a peça de B, categoria por embedding; adição não bloqueada (código) mas **não documentada**; 0,97 B; canvas máx. 576×864; VRAM não declarada | Prototype 0: FALHA-OCLUSÃO (sem canal para FRONT_OCCLUDERS) ou drift corporal (hipótese nossa); trilha permissiva exige trocar o parser |
| **R4** | **Canonicalização + VTON por máscara**: TEMU-VTOFF (ou LoRA QIE-Extract-Outfit) → CatVTON / Leffa / FitDiT com máscara derivada do envelope e **política de oclusor em ablação** (ilha / incluído+paste / suave+paste) | F4+F2 | TEMU CC BY-NC; Leffa MIT código (VTON = SD1.5-inp); CatVTON/FitDiT NC | MANTIDA — **comparador NC de maior controle estrutural** | melhor controle de `B_leakage`; **AutoMasker do CatVTON já mascara pele de torso/braços** (S-16) → adição superior mecanicamente possível; FitDiT = retângulo folgado (S-17) | Prototype 0: nenhuma política de oclusor dá tecido coerente sem regenerar a mão (F-13); try-off perde alças/logos; erro acumulado |
| R5 | FLUX.1 Kontext dev + RefTon (`--use_reference`) | F1/F3 | FLUX NC; RefTon **sem LICENSE** (P) | PENDENTE (só se sobrar orçamento; roupa plana é a entrada primária, ref vestida é auxiliar) | — | — |
| R5b | **Comparadores NC do problema central** (tetos de referência, nunca rota final): **Insert Anything** (FLUX.1-Fill-dev + Redux; código MIT; Nunchaku "10 GB"; "the mask must fully cover the area to be edited") em 2 casos do braço E4; Qwen-Image-2.1 (máscara/anotação local + até 10 refs; Qwen Research License) e ACE++ Local Editing (FLUX NC) só se R1/R1-EI/R2 falharem em criação; **Layering-VTON** (LoRA de pose como 3.ª referência sobre QIE-2509; 40 passos, true-CFG 4; sem licença) como comparador de **canal estrutural treinado** em 2 casos — seu modo `add` é camada sobre roupa, não sobre pele | F1 inpaint c/ referência | NC / sem licença | Prototype 0 (subconjunto) | mostram se o problema é do mecanismo ou dos motores permissivos | licença |
| — | **TPD** (estágio 1 prevê máscara de ocupação a partir de bbox + pessoa + roupa + pose; Paint-by-Example; NC) | estimador | NC | só como **estimador comparador de BAND_MAX** em H7′ (nunca gerador) | único preditor de ocupação condicionado à peça | — |
| — | PromptDresser | — | CC BY-NC-SA + **GPT-4o** | **DESCARTADO** | depende de API externa (viola §12 do contrato) | — |
| **R1-EI** | **FLUX.2 klein-base-4B + Easy-Insert** (LoRA Apache-2.0, `huan-yin/Easy-Insert` @ `82094484…`; inserção por referência: background com buraco branco + referência sobre branco como 2 imagens de edição do `Flux2KleinPipeline`, prompt fixo; crop 1024²; **15 passos, CFG 4 = 30 passes**; backend Diffusers = demo oficial; variante local: carregamento sequencial bf16 — `tools/r1ei/`; o "8 GB" é o modo low-VRAM do DiffSynth) — motor do braço **E4**; capacidade em roupa/adição **NV** (exemplos upstream são objetos) |
| R8 | **two-pass FASHN (layout grosseiro, pose nativa) → klein 4B (refino com referência dentro de máscara derivada de O′_FASHN)** | F3→F1 | FASHN parser NC; klein Apache | **nova rota de teste do Prototype 0** | usa a força de cada família: F3 cria a peça e resolve ocupação; F1 recupera detalhe de B em 1 024 e multi-ref; máscara derivada de saída é permitida para **gerar** (a auditoria continua usando só as máscaras congeladas) | B não melhora ou A/D/E degradam vs FASHN sozinho |
| R6′ | **Layering-VTON** (LoRA `add`/`swap` sobre Qwen-Image-Edit-2509; pesos no repo; **sem LICENSE**) | F1 | NV | 2.ª onda (comparador de `add`) | único método com modo `add` explícito e pesos; sobre pele vs. sobre roupa não documentado | licença ausente; base 2509 |
| R7′ | OmniGen2 (offload documentado) · BAGEL (NF4) | F1 | Apache | 2.ª onda — **descarte revertido** (S-12) | caminhos documentados para 12 GB | RAM 16 GB; tempo; BAGEL sem multi-imagem documentada |
| R6 | Warp/UV + inpainting (F5) como **gerador** | F5 | mistas | **DESCARTADA como gerador; MANTIDA como condicionamento/auditoria** | mapeia corpo, não roupa; peças soltas e `add` sem mapa (Fase 2) | Se Protótipo F mostrar que o estimador de C2 por correspondência é o único que funciona, F5 ganha papel maior |
| R7 | Geometria 3D + simulação (F6) | F6 | SMPL NC etc. | **DESCARTADA nesta fase** | sem código pose-agnostic utilizável; licenças; Windows | DressWild/ChatGarment com pesos e licença utilizáveis + estimador de corpo Apache validado |
| — | Qwen-Image-2.1 | F1 | **Qwen Research (NC)** | só **comparação de pesquisa** | melhor preservação relatada (~0.1 px) e máscara local nativa | — (licença impede uso fora de pesquisa) |
| — | OmniTry, UniFit, JCo-MVTON, OmniVTON++ | F3/F5 | FLUX NC / CC BY-NC | PENDENTES (2.ª onda) | ≥28 GB bf16 ou pré-proc. pesado; ref. vestida NV | Se R1–R4 falharem em `add`, OmniTry é o próximo a testar |
| — | FLUX.2 dev, Step1X-Edit, HiDream-E1, IDM-VTON, Hunyuan 3.0, Emu3.5 | — | — | **DESCARTADAS** | inviáveis em 12 GB + 16 GB (Fase 3 §4) | upgrade de hardware (fora do escopo) |

**Trilhas de licença `[ABERTO O10]`.** A intenção de uso (pessoal/pesquisa vs. comercial) não foi declarada. Decisão padrão: a **trilha permissiva (R1, R2, R3 + componentes Apache/MIT)** é a candidata a sistema final; a **trilha NC (R1b, R4, R5)** é prototipada como comparador e só se torna final se o usuário declarar uso não comercial. Isso evita construir um sistema que não possa ser usado.

## 3. Arquitetura provisória (desenho conceitual, não workflow)

1. **Ingestão & spec:** `S` resolvido (pessoa-alvo, peça(s), modo, remove/keep); validação do gate de entrada (Fase 0 §1.4).
2. **Análise de A:** SAM 3 por **texto** (pessoa, roupa antiga por categoria) e por **pontos** derivados de keypoints DWPose (elementos do corpo com lateralidade — o nó nativo `SAM3_Detect` não aceita exemplar e texto não distingue esquerda/direita), BiRefNet (bordas/α), DWPose, MoGe-2 (profundidade; FOV). `BODY_COVERABLE` = (máscara da pessoa ∪ silhueta MHR) \ (face ∪ cabelo ∪ elementos `front_certain` ∪ roupa mantida) — **nunca** do parser de vestuário (ATR não tem classe de pele do torso; em adição o torso nu cai em fundo).
2b. **Estimador de camadas (novo, `06` L4):** `layer_graph.json` congelado = por elemento {máscara 2D (SAM 3 por pontos), z relativo (mediana do render `depth` do SAM 3D Body→MHR dentro da máscara; móveis/objetos por MoGe com o mesmo FOV e reescala robusta na silhueta), relação com a roupa nova (`front_certain`/`behind_must_cover`/`behind_may_cover`/`split_by_garment_edge`/`uncertain`), base, confiança}. O nó nativo devolve só imagem (shader depth/normals/silhouette) — o z por parte é **módulo próprio a construir e auditar**. Desacordo entre fontes ou confiança baixa → `uncertain` → fora dos vereditos eliminatórios (`occlusion_unresolved`). **Pré-requisito do Prototype 0:** tabela estimador vs anotação humana por elemento (IoU, acerto da relação).
3. **Análise de B:** SAM 3 por conceito/exemplar → máscara da peça; SegFormer → partes; `garment_spec.json` (atributos com estado observado/inferido/desconhecido, extraídos por regras + Qwen3-VL em perguntas atômicas); **recorte limpo da peça** (fundo neutralizado) como referência para R1/R2; imagem vestida íntegra para R3; try-off para R4.
4. **Envelope de ocupação por classe (O3 reformulada; `06` F-08/F-10):** `BAND_MIN` = ∪{partes de A que a categoria cobre com certeza} \ `FRONT_OCCLUDERS_CORE`; `BAND_MAX_BODY` = `BAND_MIN` ∪ {partes cuja cobertura depende de atributo observado em B (manga, comprimento)} ∪ {roupa antiga a remover}; `FREE_SPACE` = anel de folga sobre fundo/objetos atrás (largura por fit_intent e categoria; MoGe para fundo adjacente); `UNCERTAIN` = axila/inter-membro/folga. Partes de A por SegFormer/SAM 3 + atribuição a segmentos por DWPose; ordem antebraço↔torso por MoGe; SAM 3D Body opcional e sempre `inferido`. Correspondência DINOv2 B→A **só** para comprimentos relativos (razão por segmento), nunca para gerar máscara. Classe E1 primeiro. **Congelado** como `contract_frozen`.
5. **Motor (R*)** gera 1–N candidatos no canvas interno (1 024 lado maior), com seed registrada.
6. **Composição:** `partition_measured` = tecido G em O′ por SAM 3 independente (calibrado); `M_comp = dilate(G, r_C3) ∪ C5_BAND, ∩ envelope, − (PROTECTED ∪ FRONT_OCCLUDERS_CORE)`; oclusores frontais por cima (z-order); mistura (não cola) em `CONTACT_FRINGE`; tudo na grade de A após reprojeção inversa exata. Ablação no Prototype 0: envelope vs `dilate(G, r_C3)`, r ∈ {4, 8, 16} px.
7. **QA (dupla: O′ e O):** pixel-check PROTECTED (tol 0 em O composto, contrato `exact`); `occupancy_audit.py` v5 (oclusores em O′, nada-mudou-sem-tecido, franja C3 limitada, split por bainha, excesso por componente, saturação de borda; INCONCLUSIVO quando falta evidência obrigatória); `garment_fidelity_audit.py` (identidade da peça B: atributos cegos + cromaticidade); DWPose/landmarks; MoGe (contorno corporal); DINOv2/SigLIP mascarados (peça); checklist de atributos (Qwen3-VL, pareado/randomizado); detectores de resíduo (cor da roupa antiga em C2), de vazamento de B (similaridade com pessoa/fundo de B), de costura (gradiente em C5). Veredito + causas.
8. **Política de candidatos/retry:** definida na Fase 5 pelas ablações (1 forte vs N menores; preview→final); deadline rígido; rejeição explícita.

Tudo orquestrado pelo ComfyUI como grafo com nós nativos (SAM 3, SAM 3D Body, MoGe, klein/QIE, `SetLatentNoiseMask`/`InpaintModelConditioning`, `DifferentialDiffusion`) **e** subprocessos (FASHN, TEMU-VTOFF, QA) com carga/descarga explícita — sem nó monolítico.

### 3.0 Mecanismo de z-order por rota (novo, `06` L4) — ordem na entrada + ordem na saída

| Rota | Ordem na entrada (o motor vê o oclusor) | Evidência | Ordem na saída |
|---|---|---|---|
| R1/R2 (F1) | oclusor `front_certain` **visível** no contexto e excluído da região editável = (BAND_MIN ∪ BAND_MAX_BODY ∪ FREE_SPACE ∪ UNCERTAIN) \ FRONT_CORE via `SetLatentNoiseMask`; render depth/normals do MHR como referência extra (fraco); prompt (fraco) | mecanismo genérico `P`; eficácia **DESC** → Prototype 0 | composição |
| R3 (FASHN) | **nenhum** | P | só composição + QA (aprovável só se O′ já respeitar a ordem) |
| R4 (F2) | máscara nossa \ FRONT_CORE **com oclusor visível** (o agnostic padrão apaga o braço → política a/b/c em ablação) | P (código) | composição |

### 3.1 Canal de ligação da representação por rota (novo, `06` §6.3)

| Família | Canal | Evidência |
|---|---|---|
| F1 (klein, QIE) | **duas semânticas nativas distintas** (`06` F-42): (a) `noise_mask` suave = blend linear por passo (E2a); (b) `noise_mask` + `DifferentialDiffusion` = liberação por limiar temporal — em 4 passos discretiza em ≤ 4 instantes (E2b; R(p) definido por **passo de liberação**); (c) **scaffold em pixel** dentro do envelope + referência (E4; padrão dos métodos publicados de inserção por referência); encoders de texto **não** aceitam máscara | **P** (código ComfyUI; Easy-Insert/Insert Anything, `research_raw/07`) |
| F2 (CatVTON/Leffa/FitDiT) | máscara derivada do envelope + política de oclusor (a: ilha / b: incluído+paste / c: suave+paste) | P (código) |
| F3 (FASHN) | **nenhum** canal de máscara; **dois modos** a testar: seg-free (pessoa inteira; default) e mascarado (`--no-segmentation-free`: labels da categoria + braços/torso → cinza, exclui face/cabelo/joias) com pose DWPose nativa | P (código) |
| Condicionamento estrutural de A | **ControlNet: inexistente** para klein 4B e Edit-2511 (`comfy/controlnet.py` verificado); substitutos em F1: pixels de A fora da máscara como restrição dura + A inteira como `reference_latent`; render depth/normals do MHR de A como referência extra (fraco, `S/I`); mapa de pose como imagem de referência (card 2509, `S`) | P/S |

## 4. Hipóteses falsificáveis (H1–H10) e onde são testadas

| ID | Hipótese | Falsificação | Protótipo |
|---|---|---|---|
| H1 | A composição (invariantes colados + mistura em franja) mantém PROTECTED exato e pose/câmera sem costuras visíveis, com qualquer motor **que já respeite oclusão em O′**. | costuras/shift de cor acima do critério em ≥ 2/6 casos; ou `pose_drift` dentro de C2 | A |
| H2 | Recortar a peça de B (fundo neutralizado) elimina `B_leakage` em R1/R2. | traços de B (pele, cabelo, fundo) em O em ≥ 1/6 casos no `B_identity_leak_probe` | A/B |
| H3 | R1 (klein 4B) preserva categoria e topologia da peça em EASY. | `wrong_category`/`garment_topology_mismatch` em ≥ 1/6 EASY | B |
| H4 | R2 (QIE-2511 Q4/Q5) é executável em frio ≤ 1 500 s por candidato @1024 com 2–3 refs em 12 GB + 16 GB. | medido acima disso, OOM ou thrashing | Fase 3 medição |
| H5 | R3 (FASHN) adapta a peça à pose de A com delta `very_different` sem mover o corpo. | `body_distortion` ou silhueta de B copiada em ≥ 2/6 | C |
| H6 | R4 (try-off → máscara nossa → Leffa/CatVTON) preserva alças/fendas/assimetrias observadas em B. | perda de ≥ 2 atributos observados em ≥ 3/6 | B |
| H7′ | O envelope congelado por classe (§3 passo 4) satisfaz `BAND_MIN ⊆ GT_tecido ⊆ BAND_MAX` em pares com **ground truth real** (`self_captured_pair` / `same_person_with_garment_photo`, alinhamento registrado) **ou** com banda **anotada por humano antes da geração**; a largura (BAND_MAX − BAND_MIN)/GT é o custo de incerteza. **Nunca** usa a saída do gerador como referência (substitui H7, circular — `06` F-06). | violação em ≥ 2/6 pares com GT | Prototype 0 / F |
| **H0** | Casca de invariantes + envelope + ocupação medida (ex-D-008). | ver `06` §3 | **Prototype 0** |
| **H11a** | `noise_mask` **suave sem DD** (blend linear por passo) desacopla nascimento da roupa de reconstrução de A melhor que denoise global e que máscara binária. | nenhum ponto com criação ≥ 0,9 **e** preservação ≤ tol; controles E1′/E1″ reproduzem os extremos do sweep | Prototype 0 (E2a) |
| **H11b** | `noise_mask` + **DifferentialDiffusion** com níveis de R(p) alinhados aos limiares do cronograma desacopla melhor que E2a. | idem | Prototype 0 (E2b) |
| **H-DD4** | Em 4 passos (klein destilado; QIE Lightning) E2b ≈ E1 binária; só gradua em ≥ 20 passos (klein Base; QIE completo). | E2b ≠ E1 em 4 passos | Prototype 0 |
| **H-E4** | Scaffold de ocupação em **pixel** dentro do envelope + referência de B eleva `coverage_of_band_min` sem aumentar deriva de landmarks fora do envelope vs E2. | sem ganho pareado | Prototype 0 (E4; R1-EI, QIE zero-shot, Insert Anything) |
| **H-F2-skin** | Inpainters por máscara (R4) produzem pele em vez de tecido em UNCERTAIN e BAND_MAX\BAND_MIN sobre torso nu ("majority completion", UR-VTON). | curva cobertura × largura da máscara mostra tecido em ≥ 4/6 | Prototype 0 (R4) |
| **H12** | Layout de ocupação grosseiro (baixa resolução/poucos passos) auditado contra invariantes antes do detalhe reduz corpo-movido sem reduzir criação. | sem ganho pareado | Prototype 0 (variante) |
| **H13** | Peça extraída de O′ como camada RGBA (SAM 3 + BiRefNet) e recomposta com z-order congelado elimina `bad_occlusion` sem costuras piores que a composição por máscara. | `bad_occlusion` persiste ou costuras piores | Prototype 0 / D |
| H8 | Quantização Q4/NVFP4 não altera topologia nem legibilidade de detalhes ≥ 12 px vs fp8/bf16. | diferença pareada detectada em ≥ 2/6 | ablação precisão |
| H9 | Qualidade em preview (passos/res. reduzidos) prediz a final (ρ de Spearman ≥ 0.7 no ranking de candidatos). | ρ < 0.7 | ablação preview |
| H10 | Routing por sinal de dificuldade supera a melhor rota única no mesmo orçamento. | ganho não significativo | ablação routing |

## 5. Critérios de abandono (gerais e por rota)

Gerais (Fase 5 plano §Critérios de abandono): falha em A sem correção; categoria/topologia errada recorrente em EASY; inviabilidade medida; licença incompatível; dependência de roupa semelhante sem composição com rota de `add`.

| Rota | Abandono específico |
|---|---|
| R1 | H3 falsa; **ou** vazamento de B apesar do recorte (H2 falsa) sem remédio por prompt/ordem de referências |
| R2 | H4 falsa (não cabe no orçamento) — abandono imediato sem discussão de qualidade |
| R3 | drift corporal não contido pela casca (Protótipo A/C) **ou** licença de pesos não permissiva confirmada **e** usuário exige trilha permissiva |
| R4 | H6 falsa (try-off destrói construção) **ou** erro acumulado inferior à rota direta em todos os eixos |
| R5 | incompatibilidade RefTon×Nunchaku sem alternativa que caiba em 12 GB |
| Casca (H0, ex-D-008) | **Prototype 0 FALHA-ACOPLAMENTO** (nenhum mecanismo — incluindo E4 scaffold em pixel — com criação ≥ 0,9 e preservação ≤ tol em ≥ 4/6 dos casos core de `g0_case_roles.json` (ver `06` §7)) **ou** H1 falsa de forma irrecuperável → voltar à Fase 2: camadas explícitas (H13) / F5 / F6 como estrutura |
| R1-EI | FALHA-CRIAÇÃO em E4 (Easy-Insert não cria a peça em roupa) **ou** tempo frio (15 passos, modo 8 GB) acima do teto |
| Qualquer rota | FALHA-CRIAÇÃO no Prototype 0 (não faz a peça nascer em ≥ 3/6 dos casos core) → sai da trilha de `add`; FALHA-OCLUSÃO → só casos sem oclusor |

## 6. Alternativas consideradas e por que não são a decisão

- **"Um único editor geral com prompt"** (reduzir a prompt engineering): proibido pelo prompt mestre e inconsistente com a evidência de drift (Fase 1 §3); mantido apenas como motor dentro da casca.
- **"VTON por máscara agnóstica padrão"**: a máscara agnóstica da literatura destrói pele/ombros/mãos e bloqueia `add`; substituída pela máscara derivada do `region_contract`.
- **"Reconstruir 3D e simular"**: sem código/licença utilizáveis (Fase 1 §6); mantido como fonte de condicionamento.
- **"Nuvem para casos difíceis"**: proibido; casos sem solução local terminam em rejeição documentada.

## 7. Próximos passos (ordem revisada 2026-10-08)

1. **Fase 3 no alvo** (operador): `tools/inventory_windows.ps1` (agora detecta `%LOCALAPPDATA%\Comfy-Desktop\ComfyUI-Installs`); medição fria/quente de klein 4B e FASHN 1.5; QIE-2511 Q5 na mesma A/B do sweep histórico (promove o relato a `MEDIDO`). **Gate:** H4 decide se R2 continua.
2. **Prototype 0 — ADDITION / OCCUPANCY STRESS TEST** (`06` §7; casos em `benchmark/proto0_cases.jsonl` com papéis/core em `benchmark/proto0/g0_case_roles.json`): E0/E0′ vs E1/E1′/E1″/E2a/E2b/E3/E4 em klein 4B, klein-base-4B + Easy-Insert (R1-EI), FASHN 1.5, QIE-2511 (subconjunto), R4, R8; agregação por `tools/g0_gate.py`; cinco eixos medidos separadamente em O′ e O; critérios pré-registrados. **Decide H0, H11 e a elegibilidade de cada rota para `add`.**
3. Protótipo A (fundido com 0 na parte de preservação), B (fidelidade EASY) com ablação de precisão (H8), C–G, H conforme `05`.
4. Revisão desta seleção com tabela rota × protótipo; só então Fase 6 (integração).
