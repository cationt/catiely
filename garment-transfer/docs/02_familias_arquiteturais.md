# Fase 2 — Famílias arquiteturais: mecanismos, 15 perguntas, matrizes

**Data:** 2026-10-07. **Base:** `01_estado_da_arte.md` e `research_raw/`. Esta fase compara **mecanismos causais**, não nomes. Nenhuma família é obrigatória; qualquer componente pode ser conclusão, nenhum é premissa.

Níveis: `P` primária · `R` reproduzido · `E` estimado · `I` inferência arquitetural · `NV` não verificado · `DESC` desconhecido.

---

## 0. Observação estrutural que atravessa todas as famílias

O contrato (Fase 0) exige três coisas que **nenhum gerador aberto entrega sozinho**: (a) preservação determinística de C1, (b) ocupação de C2 determinada pela peça e não pela roupa antiga/corpo, (c) auditoria independente da saída. Logo, toda família abaixo é avaliada como **"motor de síntese da peça"** dentro de uma *casca de preservação* externa (partição C1–C5 congelada → síntese → composição determinística em C1 → QA). A casca **não é consequência lógica do contrato**: o contrato exige auditabilidade e invariantes, não uma partição pixel-a-pixel pré-computada. É a **hipótese estrutural H0** (`06` §3) e será testada primeiro no **Prototype 0** (adição × pose complexa), não no Protótipo A (rev. 2026-10-08). A pergunta real desta fase é: **qual motor produz a melhor peça em C2∪C3∪C4 sem mover o corpo, dadas A e B (vestida)?**

---

## 1. Famílias

| ID | Família | Mecanismo essencial | Exemplos com pesos (Fase 1) |
|---|---|---|---|
| **F1** | Editor geral multi-referência (regeneração global condicionada) | DiT/flow re-sintetiza o quadro inteiro a partir de latentes de referência + tokens de VLM/texto; sem máscara | FLUX.2 klein 4B/9B, Qwen-Image-Edit-2509/2511, Qwen-Image-2.1 (NC), FLUX.1 Kontext dev (NC), OmniGen2 |
| **F2** | VTON especializado por máscara (inpainting condicionado à peça) | UNet/DiT inpainting sobre "agnostic" (A com roupa removida) dentro de máscara; peça injetada por concat/ReferenceNet/atenção | CatVTON, Leffa, FitDiT, DeCo-VTON, IDM-VTON, FastFit, Mobile-VTON |
| **F3** | VTON maskless / pixel-space | Modelo aprende localização implícita; regenera o quadro; pode mudar silhueta | FASHN VTON 1.5, OmniTry, JCo-MVTON, UniFit, RefTon (modo pessoa) |
| **F4** | Canonicalização da peça + síntese (try-off → try-on) | Extrai a peça de B para forma canônica (plana ou A-pose) e alimenta F2/F3/F1 | TEMU-VTOFF, TryOffDiff/MGT, QIE-Extract-Outfit LoRA, UniFit (try-off), OrthoTryOn |
| **F5** | Correspondência/fitting explícito + síntese | Warping guiado por DensePose/UV/fluxo/correspondência semântica, depois inpainting/refinamento | OmniVTON/++ (training-free), Pose-with-Style (UV), GP-VTON (fluxo), composições DIY com DINOv2/RoMa |
| **F6** | Geometria 3D + simulação + refinamento | Corpo 3D (SAM 3D Body→MHR) + padrão de costura (ChatGarment/GarmentCode) + drape (ContourCraft/Warp) + render + refinamento difusivo | só protótipo de pesquisa (Fase 1 §6) |
| **F7** | Composições / routing / ensembles | Casca de preservação + motor(es) de F1–F5 escolhidos por sinal de dificuldade; candidatos + refinamento | a definir; deve provar ganho vs. rota única |

---

## 2. As 15 perguntas, por família

### F1 — Editor geral multi-referência

1. **Preserva A?** Estatisticamente: condiciona em A inteira e tende a copiar; sem mecanismo verificável. Drift medido: QIE-2511 ~8 px por edição com o node padrão (reamostragem forçada a 1 MP) → ~1 px com latente de referência em tamanho nativo (`R`); saída quadrada "perde semelhança" (issue #243, `P`); RISEBench appearance 71.0 (QIE-2511) / 71.6 (Kontext) vs 86.0 (Nano Banana). **Nada é protegido por mecanismo** → casca externa obrigatória.
2. **Preserva B?** Transfere aparência e categoria; construção fina (alças, fechos, texto) depende do prompt e do modelo; LoRAs de try-on relatam fraqueza em padrões complexos e vestidos (`R`). Sem benchmark de topologia.
3. **Pose/perspectiva?** Implícito via atenção; não depende de orientação igual, mas não há garantia de que a peça "siga" a torção; **DESC** em pose difícil.
4. **Saias, camadas, assimetria, alças?** Depende do prompt; Garments2Look: editores gerais "struggle with complete outfits and layering" (`P`).
5. **Adição/substituição/ocupar pele e fundo?** Sim, por regeneração (o modelo pode ocupar qualquer região) — é a família mais flexível para `add`, ao custo de deriva fora de C2.
6. **Membros cruzando / ordem frente-atrás?** Aprendido; falhas de mãos documentadas em editores (`R`); **DESC** sistemático.
7. **Correspondência?** Implícita (atenção entre tokens de A e B); corpo e roupa **podem** se confundir (vazamento de cabelo de B relatado em LoRA Qwen, `R`).
8. **3D/prior?** Nenhum; tudo aprendido.
9. **Tecido/drape?** Aproximação visual aprendida; nenhuma evidência de física.
10. **Textura/texto/brilho/transparência?** Qwen-Image forte em texto (`R`); klein sem dado; logos pequenos **DESC**.
11. **Referência vestida/multi-ref?** Sim (até 3 sockets no ComfyUI para QIE; klein multi-ref ✅); vazamento de pessoa/fundo de B só controlado por prompt → **risco alto de `B_leakage`**.
12. **Preservação determinística sem matar volume?** Não nativa; casca externa com C2 estimado antes.
13. **Falhas corrigíveis por refinamento?** Deriva de fundo/rosto: corrigível por composição C1. Categoria/topologia errada: **não**.
14. **Teto/domínio?** Melhor qualidade geral entre abertos (GEditBench v2: klein 9B > QIE-2511, `R`); domínio demonstrado: edições gerais, não VTON em pose difícil.
15. **Viabilidade?** klein 4B: "~8 GB" (`P`) → **elegível**; klein 9B fp8: rodou em 4 GB/15.7 GB RAM com offload (`P`) → elegível-marginal (NC); QIE-2511: Q4 11.9–13.1 GB > 11.3 GB usáveis + TE → **marginal**, dependente de DynamicVRAM (Fase 3); Qwen-Image-2.1: elegível tecnicamente, **inelegível por licença** para uso não-pesquisa.

### F2 — VTON por máscara (inpainting)

1. **Preserva A?** Fora da máscara: exato **só com paste-back** (Leffa `repaint`, StableVITON "repainting"); sem isso, VAE altera todos os pixels. Dentro da máscara (mãos, braços, pele): **regenerado** → artefatos de mãos (VTBench) e corpo inventado. Pose/câmera: preservadas por construção fora da máscara; dentro, dependem de DensePose/parsing.
2. **Preserva B?** Construção razoável em EASY (VITON-HD/DressCode); detalhes: Leffa (attention-flow) e FitDiT (frequency loss) atacam distorção de textura; texto/logos fracos (GarDiff).
3. **Pose?** Treinados em frontal/estúdio; adaptação via DensePose; pose difícil **DESC** (nenhum paper mede); BooW-VTON: máscaras "introduce noticeable artifacts" em poses complexas (`R`).
4. **Saias/camadas/alças?** Categorias up/low/dress; camadas não; alças finas sofrem com máscara agnóstica que apaga pele/ombro.
5. **Adição/ocupação?** **Só dentro da máscara**: saia longa sobre pernas nuas exige mascarar pernas (destrói C1 potencial); mecanismo de máscara = regra "roupa antiga ∪ nova" (TPD) ou dilatação (FitDiT).
6. **Membros cruzando?** Se o membro está dentro da máscara, é regenerado; ordem depende de DensePose; fraco (VTBench mãos).
7. **Correspondência?** Implícita por atenção/concat; DensePose dá prior corporal, **não** topologia da peça (hipótese histórica §22 do prompt confirmada pela literatura).
8. **3D/prior?** DensePose/parsing como prior corporal 2.5D.
9. **Tecido?** Aprendido; pregas plausíveis em frontal.
10. **Textura/texto?** Médio; Leffa/FitDiT melhores.
11. **Ref. vestida?** Não nativa (exceto alegação CatVTON); requer F4 na frente. Multi-ref: FastFit (vários itens), MV-VTON (frente/costas).
12. **Determinístico sem matar volume?** Conflito direto: máscara justa preserva, máscara larga permite volume mas regenera corpo. **Trade-off não resolvido pela família.**
13. **Corrigível?** Resíduos/costuras: sim (refino local). Categoria: raramente troca (condicionamento forte). Corpo regenerado: **não** sem casca.
14. **Teto?** Alto em EASY/MEDIUM frontal; domínio = estúdio frontal.
15. **Viabilidade?** CatVTON <8 GB (`P`), Leffa ~fp16 SD1.5 (OOM VAE em 32 GB sem tiling é issue de decode, `P`), FitDiT 19.5 GB fp16 / "<6 GB" offload (`P-ex`, 8 GB insuficiente em issue) → CatVTON/Leffa/DeCo elegíveis; FitDiT marginal; IDM-VTON inviável. **Todos NC** (exceto código Leffa MIT; pesos SD1.5-inpainting OpenRAIL-M).

### F3 — VTON maskless / pixel-space

1. **Preserva A?** Regenera tudo; FASHN admite "body-shape preservation may be imperfect" e resíduos em long→short (`R`); OmniTry usa blend com máscara borrada (`P`). Casca externa obrigatória.
2. **Preserva B?** FASHN treinado em 18M pares (proprietário) → categoria/forma boas; **576×864** limita microdetalhe (`R`).
3. **Pose?** FASHN: `PoseError` quando não detecta pose (API); DWPose interno; sem dado em sentado/deitado.
4. **Saias/camadas?** one-pieces sim; camadas não (um item por chamada).
5. **Adição/ocupação?** **Sim** — maskless pode mudar silhueta e ocupar pele/fundo (`R`), é sua vantagem.
6. **Membros?** DESC.
7. **Correspondência?** Implícita.
8. **3D?** Não.
9. **Tecido?** Aprendido.
10. **Textura?** Limitada pela resolução.
11. **Ref. vestida?** **FASHN: sim** (`P`); OmniTry/JCo NV; UniFit sim (NC).
12. **Determinístico?** Não nativo.
13. **Corrigível?** Resolução baixa → refinamento localizado com referência (testar em B2); drift corporal: **não** corrigível além da casca.
14. **Teto?** Produto comercial real (FASHN v1.6 fechado é superior; 1.5 é a versão aberta).
15. **Viabilidade?** FASHN ~8 GB, ~1B params, sem VAE → **elegível e leve**; OmniTry ≥28 GB bf16 → só com fp8/GGUF do FLUX Fill (marginal, NC).

### F4 — Canonicalização (try-off) + síntese

1. **Preserva A?** Herda do motor downstream (F2/F3/F1); a etapa de try-off não toca A.
2. **Preserva B?** Depende do try-off: TEMU-VTOFF (SD3-M dual DiT) é o mais capaz (up/low/full); todos alucinam costas e perdem logos/estampas (literatura, `R`). **Erro acumulado:** try-off perde detalhe → try-on não recupera.
3. **Pose?** Remove a dependência da pose de B (vantagem central: a peça entra canônica). Pose de A fica a cargo do motor.
4. **Saias/alças/assimetria?** Try-off tende a simetrizar e "completar" — risco de `garment_topology_mismatch` já na etapa 1. Precisa auditoria intermediária (garment_spec de B vs. peça canônica).
5. **Adição?** Herda do motor.
6–9. Herda do motor.
10. **Textura/texto?** Ponto fraco documentado ("logos and printed designs").
11. **Ref. vestida?** É a razão de existir; vazamento de B controlado estruturalmente (pessoa/fundo não entram no motor). **Melhor controle de `B_leakage` entre as famílias.**
12. Herda.
13. **Corrigível?** Perda de detalhe no try-off → multi-ref (recorte de detalhe de B como 2.ª referência) ou refinamento; topologia errada → não.
14. **Teto?** Limitado pelo elo mais fraco; MGT mostra ganho em vazamento de pele (`R`, único quantitativo).
15. **Viabilidade?** TEMU-VTOFF: SD3-M (gated, Stability Community) + Qwen2.5-VL-7B para legenda → ~8–12 GB sequencial (`E`); TryOffDiff SD1.4 leve (SSPL); LoRA Qwen extract (Apache; sobre QIE-2511, marginal). Adiciona minutos ao orçamento.

### F5 — Correspondência/fitting explícito + síntese

1. **Preserva A?** Warping não toca A; a síntese posterior é inpainting (F2) → mesma análise.
2. **Preserva B?** Textura transportada por warp preserva estampa/texto **melhor que qualquer gerador** onde a correspondência é confiável; onde não é, cria distorções e buracos (UV: "ignore the underlying 3D shape", auto-oclusão).
3. **Pose?** Explícita: DensePose/UV ou fluxo mapeia superfície corporal de B para A. **Mas** mapeia **corpo**, não **roupa**: saia ampla, mangas largas, caimento não seguem o corpo (hipótese histórica §22 confirmada). ViTon-GUN/FW-VTON canonicalizam para A-pose por esse motivo (código NV).
4. **Saias/camadas?** Fraco para peças soltas; ok para justas.
5. **Adição?** Possível se o warp projeta sobre pele; extensão fora do corpo (saia) **não** tem mapa.
6. **Membros/ordem?** DensePose dá ordem corpo-corpo; roupa-vs-membro não.
7. **Correspondência?** Explícita (vantagem auditável): podemos **medir** confiança por região e cair para síntese onde é baixa.
8. **3D?** 2.5D (UV) ou 3D leve (MHR+MoGe).
9. **Tecido?** Nenhum; warp é cinemático.
10. **Textura?** Ponto forte (transporte de pixels/features), limitado pela resolução de B e pela deformação.
11. **Ref. vestida?** Sim por natureza (B é vestida; parsing isola a peça); vazamento controlado por máscara de parsing (falha em cabelo/fundo — CORAL).
12. **Determinístico?** O warp é determinístico dado o mapa; a síntese final não.
13. **Corrigível?** Buracos/distorções → inpainting local (bom); mapa errado → não.
14. **Teto?** Como rota principal: baixo em peças soltas e poses difíceis (OmniVTON exige pré-processamento pesado e é NC). Como **condicionamento auxiliar** (prior de textura/posição para F1/F2): promissor e auditável.
15. **Viabilidade?** Componentes leves (DWPose, SAM 3, BiRefNet, DINOv2, MoGe cabem folgados); DensePose via detectron2 difícil no Windows (`I`); OmniVTON pesado em pré-processamento e NC.

### F6 — Geometria 3D + simulação + refinamento

1. **Preserva A?** Corpo 3D é estimado (inferência) e pode divergir do observado → **risco de `body_distortion` ao renderizar** sobre A; só serve se a malha for usada como guia, não como substituto.
2. **Preserva B?** Padrão de costura estimado de 1 imagem: topologia errada em pose não frontal (SewFactory frontal; Dress-1-to-3 não recupera painéis). Textura: mapeamento UV do padrão NV.
3. **Pose?** Melhor família em princípio (simulação na pose de A), **se** corpo e padrão forem corretos.
4. **Saias/camadas?** Simuladores multi-peça (ContourCraft) existem; padrões de saias amplas plausíveis.
5. **Adição?** Natural (simula sobre o corpo).
6. **Membros/ordem?** Natural (3D).
7–8. Explícito.
9. **Tecido?** Única família com drape físico — mas parâmetros de material são **desconhecidos** (Fase 0 §5): simulação com material errado é tão "aproximada" quanto a aprendida.
10. **Textura?** Depende de UV e render; refinamento difusivo reintroduz deriva.
11. **Ref. vestida?** Sim (padrão + textura de B).
12. **Determinístico?** Render é determinístico; refinamento não.
13. **Corrigível?** Erros de padrão exigem edição manual (fora do caso central).
14. **Teto?** Alto em teoria; **não demonstrado** em imagem única in-the-wild.
15. **Viabilidade?** Estágios cabem em 12 GB sequencialmente (`E`); <60 min plausível (`I`); **bloqueios:** licença SMPL (ContourCraft/HOOD), ChatGarment usa GPT-4o em scripts, SewFormer exige Maya, DressWild sem código, Windows (PyTorch3D/nvdiffrast). **Não elegível como rota de produção nesta fase**; elegível como fonte de condicionamento (malha MHR/normais) em F5/F7.

### F7 — Composições / routing

Respondido pela composição dos motores; só se justifica se demonstrar ganho sobre a melhor rota única **no mesmo orçamento** (Fase 5, ablação "Routing"). Sinais de dificuldade candidatos (mensuráveis): delta de pose A↔B (DWPose), fração de C2-possível fora da roupa antiga (operação `add`), oclusões sobre a região (parsing), tamanho de detalhes em B, categoria.

---

## 3. Matriz de capacidade visual

Escala: ●●● forte com evidência · ●● plausível/parcial · ● fraco · ○ não suporta · `?` desconhecido (sem evidência). Evidência ao lado quando existe.

| Candidata | Preservação A (nativa) | Fidelidade construção B | Topologia (alças/fendas/fechos) | Pose difícil | Perspectiva | Tecido/drape | Oclusão/mãos | Ref. vestida | Multi-ref | Add (pele/fundo) | Replace limpo | Texto/logo |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| FLUX.2 klein 4B (F1) | ● (regenera) | ●● `R` | ? | ? | ? | ●● `I` | ? | ●● (via refs) | ●●● `P` | **?** (sem barreira de mecanismo, sem evidência; `I`) | ●● | ? |
| FLUX.2 klein 9B (F1, NC) | ● | ●●● `R` (GEditBench v2) | ? | ? | ? | ●● | ? | ●● | ●●● | **?** | ●● | ●● |
| Qwen-Image-Edit-2511 (F1) | ● (~1–8 px drift `R`) | ●●● `R` | ? | ? | ? | ●● | ? | ●● | ●●● (limite oficial não documentado) | **?/●** (único dado: histórico no alvo — cria roupa com denoise global ≥ 0,7, acoplado a drift; eixo espacial não testado) | ●● | ●●● `R` |
| Qwen-Image-2.1 (F1, NC) | ●● (máscara local `P`; ~0.1 px `R`) | ●●● | ? | ? | ? | ●● | ? | ●● | ●●● (10) | ●●● | ●● | ●●● |
| CatVTON (F2, NC) | ●● (fora da máscara c/ paste-back) | ●● `P` | ● | ● `R` | ● | ●● | ● `R` | ● (alegado) | ○ | ● (só na máscara) | ●●● | ● |
| Leffa (F2) | ●● | ●●● `P` (flow loss) | ●● | ? | ● | ●● | ● | ○ | ○ | ● | ●●● | ●● |
| FitDiT (F2, NC) | ●● | ●●● `P` | ●● | ? | ● | ●● | ●● (2.º VTBench) | ○ | ○ | ●● (máscara dilatada) | ●●● | ●● |
| FASHN VTON 1.5 (F3) | **?** (drift corporal = hipótese nossa; autor afirma "preserves body features") | ●●● `R` (18M pares) | ●● | ? | ? | ●● | ? (sem canal para oclusores) | ●●● `P` | ○ | **?** (adição não bloqueada no código, não documentada; dois modos: seg-free e mascarado) | ●● (resíduos só em fontes secundárias) | ● (576×864) |
| OmniTry (F3, NC pesos) | ● | ●● | ? | ? | ? | ●● | ? | ? | ○ | ●●● | ●● | ? |
| RefTon (F3/F1, NC) | ● | ●● | ? | ? | ? | ●● | ? | ●●● `P` (aux) | ●● | ●● | ●● | ? |
| TEMU-VTOFF → F2 (F4, NC) | herda | ●● (perde logos `R`) | ● (simetriza) | ●●● (remove pose de B) | — | herda | herda | ●●● | ●● | herda | herda | ● |
| QIE-Extract LoRA → F1/F2 (F4) | herda | ? | ? | ●●● | — | herda | herda | ●●● | ●● | herda | herda | ? |
| OmniVTON++ (F5, NC) | ●● | ●● | ● | ●● (Principal Pose Guidance `R`) | ● | ● | ● | ●●● `P` | ○ | ● | ●● | ●● |
| Warp UV/DINO DIY (F5) | ●●● (não toca A) | ●●● onde confiável | ● | ● (corpo≠roupa) | ●● | ○ | ●● (ordem corpo) | ●●● | ●● | ● | — | ●●● |
| Geometria+simulação (F6) | ● (corpo estimado) | ● (padrão frontal) | ● | ●●● teoria / ? prática | ●●● | ●●● teoria / ? material | ●●● | ●● | ●● | ●●● | ●●● | ● |

Leitura por eixo:
- **Preservação de A:** nenhuma candidata é forte nativamente; F5 (warp) e a casca externa são os únicos mecanismos verificáveis. → A casca é obrigatória, independente do motor.
- **Fidelidade/topologia de B:** F2 (Leffa/FitDiT) e F1 (QIE-2511/klein 9B) empatam em evidência fraca; F4 adiciona risco de simetrização; F5 transporta textura mas não constrói topologia.
- **Pose difícil:** **nenhuma evidência para nenhuma candidata**. F4 reduz a dependência da pose de B; nada reduz a dificuldade da pose de A. É o eixo que o benchmark próprio precisa medir primeiro.
- **Add (ocupar pele/fundo) — rev. 2026-10-08:** a nota máxima para F1/F3 era **inferência de mecanismo** ("regenera tudo, logo pode ocupar qualquer região"), não evidência; o único dado empírico (sweep no alvo) mostra que essa liberdade **global** não produz a peça sem reconstruir A. Inversamente, **inpainting por máscara que cobre a pele (F2) é o mecanismo mais direto de nascimento da peça** (tarefa nativa: o agnostic de treino já apaga pele/braços; o AutoMasker do CatVTON mascara torso/braços) — a barreira real de F2 é referência plana (try-off) e regeneração de mãos dentro da máscara, mitigável excluindo `FRONT_OCCLUDERS` (política a testar). Capacidade bruta de adição de **todas** as famílias é desconhecida → Prototype 0.
- **Ref. vestida:** F3 (FASHN), F4 (try-off) e F5 (parsing) têm controle estrutural; F1 depende de prompt (risco de vazamento).

**Trocas sem solução identificada:** (i) máscara justa vs. volume novo (F2); (ii) regeneração global vs. preservação (F1/F3); (iii) canonicalizar perde detalhe vs. direto vaza B (F4 vs F1/F3); (iv) warp preserva textura mas não topologia nem caimento (F5).

## 4. Matriz de viabilidade operacional

| Candidata | Versão / pesos | Entradas exigidas | Treino exigido | Mecanismo | VRAM est./reportada | RAM | Licença (código / pesos) | ComfyUI | Windows | Manutenção | Reprodutibilidade | Elegibilidade (provisória; Fase 3 decide) |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| FLUX.2 klein 4B | 2026-01-15; HF BFL | A, B(s), prompt | não | F1 | "~8 GB" `P`; fp8 ~4 GB pesos + TE 4B | ok | **Apache-2.0** | core | sim | ativa (BFL) | seeds + fp8 | **ELEGÍVEL** |
| FLUX.2 klein 9B / 9B-KV | idem | idem | não | F1 | 9B fp8 ~9 GB + TE 8B → offload; rodou em 4 GB VRAM/15.7 GB RAM `P` | apertada | FLUX NC | core | sim | ativa | idem | ELEGÍVEL-MARGINAL (NC) |
| Qwen-Image-Edit-2511 | 2025-12-23 | A, B(s), prompt | não | F1 | Q4 11.9–13.1 GB + VL-7B 4.7–9.4 GB → excede 11.3 GB usáveis; DynamicVRAM | **crítica** (relato 32 GB saturada) | **Apache-2.0** | core | sim | ativa (Qwen) | GGUF Q4 altera detalhe (NV) | MARGINAL — medir |
| Qwen-Image-2.1 | 2026-09-20 | A, B(s), máscara opcional | não | F1 | 4070 12 GB: edit 16–20 s `R` | TE 8B fp8 ~8 GB | **Qwen Research (NC)** | core | sim | ativa | — | ELEGÍVEL só para pesquisa/comparação |
| FLUX.1 Kontext dev (+LoRAs/RefTon) | 2025-06 | A, B, prompt | não | F1/F3 | Nunchaku NVFP4 ~6.8 GB `P-ex` | ok | FLUX NC | core + nunchaku | sim (wheels) | ativa | nunchaku altera detalhe (NV) | ELEGÍVEL (NC) |
| CatVTON | 2024-07; HF | A, B plana, máscara (SCHP+DensePose) | não | F2 | <8 GB `P` | ok | CC BY-NC-SA | oficial | detectron2 difícil `I` | dormente | boa | ELEGÍVEL (NC); ref. vestida só via F4 |
| Leffa | 2024-12; HF | A, B plana; AutoMasker | não | F2 | SD1.5+ref UNet ~4 GB + VAE decode | ok | MIT / SD1.5-inp | 2 wrappers | issue Windows aberta `P` | 2025-02 | boa | ELEGÍVEL; ref. vestida via F4 |
| FitDiT | 2024-12; HF | A, B plana; máscara auto | não | F2 | 19.5 GB fp16; "<6 GB" offload `P-ex`; 8 GB insuficiente `P` | ok | CC BY-NC-SA | oficial | não testado | 2025-01 | boa | MARGINAL (NC) — medir offload |
| DeCo-VTON | 2025-12; HF | A, B plana, agnostic | não | F2 | SD1.5 único | ok | CC BY-NC-SA / NC | — | ? | nova | média | ELEGÍVEL (NC) |
| FASHN VTON 1.5 | 2026-01; HF | A, B (plana **ou vestida**), categoria | não | F3 | ~8 GB `R` | ok | **Apache-2.0** (pesos NV) | nenhum (subprocesso) | instruções Unix; PyTorch puro `I` | ativa | boa | **ELEGÍVEL** |
| OmniTry | 2025-08 | A, B, prompt | não | F3 | ≥28 GB bf16 `P` → fp8/GGUF Fill | apertada | Apache / FLUX NC | não | ? | 2025-08 | média | MARGINAL (NC) |
| UniFit | 2025-11 | prompt, A, B, DWPose | não | F3/F4 | FLUX Fill + Qwen2-VL-2B | apertada | CC BY-NC-SA / FLUX NC | não | ? | nova | média | MARGINAL (NC) |
| TEMU-VTOFF | 2025-05 / 2026-03 | B, categoria, legenda VLM, bbox | não | F4 | SD3-M dual + VL-7B (seq.) `E` | ok c/ seq. | CC BY-NC 4.0; SD3 gated | não | ? | ativa | média | ELEGÍVEL (NC) como pré-etapa |
| TryOffDiff/MGT | 2024-11 / 2025-04 | B, classe | não | F4 | SD1.4 leve | ok | **SSPL** (não comercial salvo open-source total) | não | PyTorch puro | ativa | boa | ELEGÍVEL (SSPL) |
| OmniVTON++ | 2026-02 | A, B, agnostic, TAPPS, OpenPose, DensePose UV, pseudo-pessoa (IMAGDressing) | não | F5 | pesado em pré-proc. (NV) | ? | CC BY-NC | não | DensePose difícil | nova | baixa (muitos componentes) | PENDENTE (custo) |
| Warp DIY (DWPose + SAM 3 + BiRefNet + DINOv2/RoMa + MoGe/SAM 3D Body) | 2026 | A, B | não (opcional) | F5 cond. | cada componente ≤ 4 GB `P/R` | ok | Apache/MIT (+ SAM/DINOv3 custom) | core (SAM3, SAM 3D Body, MoGe) | PyTorch/ONNX | ativa | boa | ELEGÍVEL como **condicionamento/auditoria**, não como gerador |
| Geometria+simulação | 2025–26 | A, B (+edição manual) | não | F6 | seq. ≤ 12 GB `E` | ? | SMPL NC; GarmentCode MIT; MHR Apache | parcial | PyTorch3D/nvdiffrast difíceis | fragmentada | baixa | **NÃO ELEGÍVEL** como rota (pesquisa) |
| FLUX.2 dev, Step1X-Edit, HiDream-E1, IDM-VTON, Hunyuan 3.0, Emu3.5 | — | — | — | F1/F2 | > 12 GB mesmo quantizado/offload `P/R` | > 16 GB | — | — | — | — | — | **INVIÁVEL** |

## 5. Conclusões da Fase 2

1. **Separar a casca do motor — como hipótese (H0).** A exigência de preservação não é satisfeita por nenhum gerador; a casca congela **invariantes + oclusores com z-order + envelope de ocupação por classe** (não a área da peça), entrega ao motor um **mapa graduado de autoridade de reconstrução** pelo canal de cada família (F1: denoise espacial no latente + DifferentialDiffusion, verificado no código do ComfyUI; F2: máscara derivada + política de oclusor; F3: nenhum canal → só auditoria) e **mede** a ocupação em O′ com segmentador independente. Testada no **Prototype 0 antes** de escolher o motor. Componentes: SAM 3/SAM 2, BiRefNet, DWPose, SegFormer (licença dos pesos em aberto), MoGe-2, SAM 3D Body→MHR — com as licenças Meta registradas como proprietárias revogáveis (rev. 2026-10-08).
2. **Motores a prototipar (candidatos, sem "principal"; três mecanismos):** F1 (klein 4B barato/Apache; QIE-2511 com evidência histórica de criar roupa onde VTON/warps falharam, acoplado ao denoise global; klein 9B/Kontext comparadores NC), F3 (FASHN 1.5: referência vestida nativa, maskless real na pessoa, **mas** parser NC e sem canal espacial), F2+F4 (try-off → Leffa/CatVTON/FitDiT com máscara derivada; o AutoMasker do CatVTON já cobre pele de torso/braços; política de oclusor em ablação). A capacidade **bruta de adição × pose** de cada um é desconhecida e é o que o Prototype 0 mede primeiro (rev. 2026-10-08).
3. **F5 entra como condicionamento e auditoria**, não como gerador: correspondência DINOv2/RoMa e pose/corpo fornecem (a) estimativa de extensão de C2 independente do gerador (pendência O3), (b) prior de posição/textura para refinamento, (c) detectores de QA.
4. **F6 fica fora** até haver código de reconstrução de padrão pose-agnostic com licença utilizável.
5. **Trocas sem solução** (§3) são exatamente o que os Protótipos C, E, F e G medem; a seleção da Fase 4 é provisória até lá.
6. **Pose difícil é desconhecida para todos** — o benchmark próprio (HARD/EXTREME) é a única fonte de verdade possível; nenhuma declaração de suporte será feita antes dele.
