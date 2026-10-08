# Fase 4 — Seleção provisória de arquitetura, hipóteses falsificáveis e critérios de abandono

**Data:** 2026-10-07. **Natureza desta decisão:** **provisória**. Baseia-se em evidência de fontes primárias e relatos (Fases 1–3), **sem nenhuma medição no hardware-alvo e sem nenhum protótipo executado**. Será revisada obrigatoriamente após a Fase 3 medida e os Protótipos A–H. Nada aqui é compromisso irrevogável.

---

## 1. Decisão estrutural: casca de preservação + motor substituível

**Decisão D-008.** A arquitetura é organizada em duas camadas com interface explícita:

```
A, B, S ──► [1] Análise & contrato     ──► region_contract (C1–C5 + banda), garment_spec(B), pose/corpo(A)
            [2] Motor de síntese (R*)   ──► candidato(s) O' no canvas interno
            [3] Composição determinística ──► O = C1 de A (exato) ⊕ O' em C2∪C3∪C4 ⊕ mistura em C5
            [4] QA & seleção            ──► PASS / FAIL / INCONCLUSIVO + R ; retry/rota/refino no orçamento
```

Justificativa (Fase 2 §0, §5): nenhum gerador aberto preserva A por mecanismo; a preservação exigida pelo contrato só é verificável se imposta e auditada **fora** do gerador, com partição congelada antes da geração. Isso também torna o motor substituível sem refazer QA/benchmark.

**Risco conhecido dessa decisão (a testar no Protótipo A):** composição determinística cria costuras ("abrupt transitions", shift de cor de baixa frequência pelo VAE — ART-VITON/ASUKA) e não resolve, por si, geometria e integração (hipótese histórica §22 do prompt). A banda C5 e a política de C3 existem para isso; se o Protótipo A mostrar costuras irrecuperáveis, a decisão volta à Fase 2.

Componentes da camada [1] e [4] (todos permissivos ou nativos do ComfyUI; **nenhum é o gerador**):

| Função | Componente provisório | Alternativa | Por quê |
|---|---|---|---|
| Segmentação da pessoa-alvo, cabelo, mãos, objetos, peça antiga em A; peça em B (texto + exemplar) | **SAM 3/3.1** (nativo no core) + **BiRefNet** (bordas/matting) | SAM 2.1 (Apache) + SegFormer-B2-clothes | SAM 3 aceita conceito/exemplar; BiRefNet dá C5 fino |
| Rótulos semânticos de vestuário | SegFormer-B2-clothes (ATR 18) | SCHP | leve, Windows |
| Pose/landmarks de A (invariantes; QA) | **DWPose/rtmlib** (Apache, ONNX, whole-body) | RTMW | sem mmcv; Windows |
| Corpo/profundidade de A (extensão de C2, ordem de oclusão, QA) | **MoGe-2** (MIT; nativo) + **SAM 3D Body→MHR** (nativo; bf16/int8) | Depth Anything 3 Small | MHR é Apache (evita SMPL NC) |
| Correspondência A↔B (prior de extensão da peça; auditoria de atributos) | DINOv2 features (Apache) | RoMa v2 (geométrico) | semântico, congelado, barato |
| Juiz semântico (atributos da peça; nunca física/topologia) | Qwen3-VL-8B Q4 (Apache) | MiniCPM-V | perguntas atômicas sim/não por região; ordem aleatorizada |
| Pixels C1 | `tools/pixel_preservation_check.py` | — | exato, mesma grade |

## 2. Shortlist de motores (R1–R4) e por que cada um está onde está

| Rota | Motor | Família | Licença | Status | Por que mantida | O que a derruba |
|---|---|---|---|---|---|---|
| **R1** | **FLUX.2 klein 4B** (fp8/bf16) com A + recorte(s) da peça de B como referências | F1 | **Apache-2.0** | **MANTIDA — principal da trilha permissiva** | único editor multi-ref permissivo que cabe com folga (~8 GB `P`); 4 passos → tempo para múltiplos candidatos e refino; multi-ref oficial | Protótipo B: `wrong_category`/topologia em EASY; Protótipo C: não adapta pose; vazamento de B não controlável por recorte |
| **R1b** | FLUX.2 klein 9B / 9B-KV | F1 | FLUX NC | MANTIDA como comparador NC | melhor aberto em GEditBench v2 (`R`) | Fase 3: s/it com offload inviável; licença, se uso comercial |
| **R2** | **Qwen-Image-Edit-2511** (Q4/Q5 GGUF ou 2509+Nunchaku NVFP4) com A + B(s) | F1 | **Apache-2.0** | MANTIDA — **condicional à Fase 3** | maior fidelidade semântica/texto entre permissivos; 3 referências nativas; RISEBench appearance 71.0 | Fase 3: frio > 1 500 s/candidato ou thrashing; Protótipo A: drift > tolerância mesmo com casca; quantização Q4 destrói detalhe (ablação) |
| **R3** | **FASHN VTON 1.5** (subprocesso) com A + B vestida | F3 | **Apache-2.0** (pesos NV) | **MANTIDA — rota especializada permissiva** | único VTON aberto com referência vestida nativa, ~8 GB, treinado em 18M pares (wild); maskless → `add` natural | 576×864 insuficiente para detalhe (B em 1 024/1 536); drift corporal não contido pela casca (Protótipo A/C); licença dos pesos ≠ Apache |
| **R4** | **Canonicalização + VTON por máscara**: TEMU-VTOFF (ou LoRA QIE-Extract-Outfit) → Leffa / CatVTON / FitDiT com máscara derivada do `region_contract` | F4+F2 | TEMU CC BY-NC; Leffa MIT código/OpenRAIL pesos; CatVTON/FitDiT NC | MANTIDA — **trilha NC de maior controle estrutural** | melhor controle de `B_leakage` (pessoa/fundo de B nunca entram no motor); evidência de ganho (MGT); máscara pode ser **a nossa** (C2 estimado), não a agnóstica padrão | Protótipo B: try-off simetriza/perde alças/logos; Protótipo F: incapaz de `add` sem destruir C1; erro acumulado > rota direta |
| R5 | FLUX.1 Kontext dev + RefTon (`--use_reference`) ou LoRAs try-on | F1/F3 | FLUX NC | **PENDENTE** (comparador) | único método com pesos treinado para referência vestida auxiliar; Nunchaku ~6.8 GB | RefTon LoRA × Nunchaku NV; qualidade de LoRAs anedótica; licença |
| R6 | Warp/UV + inpainting (F5) como **gerador** | F5 | mistas | **DESCARTADA como gerador; MANTIDA como condicionamento/auditoria** | mapeia corpo, não roupa; peças soltas e `add` sem mapa (Fase 2) | Se Protótipo F mostrar que o estimador de C2 por correspondência é o único que funciona, F5 ganha papel maior |
| R7 | Geometria 3D + simulação (F6) | F6 | SMPL NC etc. | **DESCARTADA nesta fase** | sem código pose-agnostic utilizável; licenças; Windows | DressWild/ChatGarment com pesos e licença utilizáveis + estimador de corpo Apache validado |
| — | Qwen-Image-2.1 | F1 | **Qwen Research (NC)** | só **comparação de pesquisa** | melhor preservação relatada (~0.1 px) e máscara local nativa | — (licença impede uso fora de pesquisa) |
| — | OmniTry, UniFit, JCo-MVTON, OmniVTON++ | F3/F5 | FLUX NC / CC BY-NC | PENDENTES (2.ª onda) | ≥28 GB bf16 ou pré-proc. pesado; ref. vestida NV | Se R1–R4 falharem em `add`, OmniTry é o próximo a testar |
| — | FLUX.2 dev, Step1X-Edit, HiDream-E1, IDM-VTON, Hunyuan 3.0, Emu3.5 | — | — | **DESCARTADAS** | inviáveis em 12 GB + 16 GB (Fase 3 §4) | upgrade de hardware (fora do escopo) |

**Trilhas de licença `[ABERTO O10]`.** A intenção de uso (pessoal/pesquisa vs. comercial) não foi declarada. Decisão padrão: a **trilha permissiva (R1, R2, R3 + componentes Apache/MIT)** é a candidata a sistema final; a **trilha NC (R1b, R4, R5)** é prototipada como comparador e só se torna final se o usuário declarar uso não comercial. Isso evita construir um sistema que não possa ser usado.

## 3. Arquitetura provisória (desenho conceitual, não workflow)

1. **Ingestão & spec:** `S` resolvido (pessoa-alvo, peça(s), modo, remove/keep); validação do gate de entrada (Fase 0 §1.4).
2. **Análise de A:** SAM 3 (pessoa, cabelo, mãos, objetos, roupa antiga por categoria), BiRefNet (bordas), DWPose, MoGe (profundidade/normais) → invariantes + ordem de oclusão + candidatos a C1/C5.
3. **Análise de B:** SAM 3 por conceito/exemplar → máscara da peça; SegFormer → partes; `garment_spec.json` (atributos com estado observado/inferido/desconhecido, extraídos por regras + Qwen3-VL em perguntas atômicas); **recorte limpo da peça** (fundo neutralizado) como referência para R1/R2; imagem vestida íntegra para R3; try-off para R4.
4. **Estimativa de C2 (pendência O3):** união de (a) prior por categoria sobre corpo/profundidade de A, (b) projeção da extensão relativa da peça em B (correspondência DINOv2 de landmarks corporais B→A), (c) roupa antiga a remover; com banda de incerteza. **Congelado** como `region_contract`.
5. **Motor (R*)** gera 1–N candidatos no canvas interno (1 024 lado maior), com seed registrada.
6. **Composição determinística:** C1 copiado de A pixel a pixel; C5 misturado com alpha de BiRefNet; C3 limitado a franja máxima; tudo na grade de A após reprojeção inversa exata.
7. **QA:** pixel-check C1; DWPose/landmarks; MoGe (contorno corporal); DINOv2/SigLIP mascarados (peça); checklist de atributos (Qwen3-VL, pareado/randomizado); detectores de resíduo (cor da roupa antiga em C2), de vazamento de B (similaridade com pessoa/fundo de B), de costura (gradiente em C5). Veredito + causas.
8. **Política de candidatos/retry:** definida na Fase 5 pelas ablações (1 forte vs N menores; preview→final); deadline rígido; rejeição explícita.

Tudo orquestrado pelo ComfyUI como grafo com nós nativos (SAM 3, SAM 3D Body, MoGe, klein/QIE) **e** subprocessos (FASHN, TEMU-VTOFF, QA) com carga/descarga explícita — sem nó monolítico.

## 4. Hipóteses falsificáveis (H1–H10) e onde são testadas

| ID | Hipótese | Falsificação | Protótipo |
|---|---|---|---|
| H1 | A casca de preservação (partição congelada + composição) mantém C1 exato e pose/câmera sem costuras visíveis, com qualquer motor. | costuras/shift de cor acima do critério em ≥ 2/6 casos; ou `pose_drift` dentro de C2 | A |
| H2 | Recortar a peça de B (fundo neutralizado) elimina `B_leakage` em R1/R2. | traços de B (pele, cabelo, fundo) em O em ≥ 1/6 casos no `B_identity_leak_probe` | A/B |
| H3 | R1 (klein 4B) preserva categoria e topologia da peça em EASY. | `wrong_category`/`garment_topology_mismatch` em ≥ 1/6 EASY | B |
| H4 | R2 (QIE-2511 Q4/Q5) é executável em frio ≤ 1 500 s por candidato @1024 com 2–3 refs em 12 GB + 16 GB. | medido acima disso, OOM ou thrashing | Fase 3 medição |
| H5 | R3 (FASHN) adapta a peça à pose de A com delta `very_different` sem mover o corpo. | `body_distortion` ou silhueta de B copiada em ≥ 2/6 | C |
| H6 | R4 (try-off → máscara nossa → Leffa/CatVTON) preserva alças/fendas/assimetrias observadas em B. | perda de ≥ 2 atributos observados em ≥ 3/6 | B |
| H7 | A estimativa de C2 independente do gerador (§3 passo 4) cobre a peça real em `add` sem exceder 15 % de área além do tecido final. | cobertura < 90 % ou excesso > 15 % em ≥ 2/6 | F |
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
| Casca (D-008) | H1 falsa de forma irrecuperável → voltar à Fase 2 e reconsiderar F5/F6 como estrutura |

## 6. Alternativas consideradas e por que não são a decisão

- **"Um único editor geral com prompt"** (reduzir a prompt engineering): proibido pelo prompt mestre e inconsistente com a evidência de drift (Fase 1 §3); mantido apenas como motor dentro da casca.
- **"VTON por máscara agnóstica padrão"**: a máscara agnóstica da literatura destrói pele/ombros/mãos e bloqueia `add`; substituída pela máscara derivada do `region_contract`.
- **"Reconstruir 3D e simular"**: sem código/licença utilizáveis (Fase 1 §6); mantido como fonte de condicionamento.
- **"Nuvem para casos difíceis"**: proibido; casos sem solução local terminam em rejeição documentada.

## 7. Próximos passos (ordem)

1. **Fase 3 no alvo** (operador): inventário + medição fria/quente de R1, R2, R3, R4 e dos componentes de percepção/QA (`docs/03_viabilidade_local.md` §8). **Gate:** H4 decide se R2 continua.
2. **Protótipo A** (casca) com R1 e R3 — decide D-008.
3. **Protótipo B** (fidelidade EASY) com R1, R2 (se viável), R3, R4 — decide H3, H6; ablação de precisão (H8).
4. Protótipos C–G e H conforme `docs/05_plano_prototipos.md`.
5. Revisão desta seleção com tabela rota × protótipo; só então Fase 6 (integração).
