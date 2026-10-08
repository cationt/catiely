# Registro de decisões (append-only)

Formato: `D-<n>` · data · fase · decisão · evidência/nível · alternativas · o que a reverteria.

| ID | Data | Fase | Decisão | Evidência (nível) | Alternativas consideradas | Experimento que reverte |
|---|---|---|---|---|---|---|
| D-001 | 2026-10-07 | 0 | O contrato é semântico (classes C1–C5), não prescreve máscaras/algoritmo. | Prompt mestre §4–5 (requisito) | Contrato por máscaras fixas | — (requisito) |
| D-002 | 2026-10-07 | 0 | `region_contract` é congelado antes da geração e nunca recalculado a partir de `O`. | Requisito anti-deriva (§5 do prompt) | Auditar com máscara do próprio gerador (circular) | — (requisito) |
| D-003 | 2026-10-07 | 0 | Saída padrão é rejeição explícita quando nenhum candidato passa; "último candidato" só em modo `unverified_preview`. | Requisito §11/§16 do prompt | Entregar melhor candidato sempre | — (requisito) |
| D-004 | 2026-10-07 | 0 | Convenção inicial 1 024 px lado maior; saída reprojetada ao canvas de `A`; 1 536 comparado separadamente. | Requisito §3 do prompt | Resolução nativa sempre | Protótipo B em 1 536 (O8) |
| D-005 | 2026-10-07 | 0 | Tamanho mínimo útil de detalhe provisório 12 px em `B` reamostrada / 8 px em `O`. | ESTIMADO (sem calibração) | 16/12 px | Protótipo B escalonado (O4) |
| D-006 | 2026-10-07 | 0 | Metas provisórias por estrato (EASY ≥ 80 %, MEDIUM ≥ 60 %, HARD ≥ 35 %, EXTREME ≥ 15 %) sobre **todas** as solicitações; congelar antes da Fase 7. | ESTIMADO (sem benchmark ainda) | Metas únicas globais | Revisão justificada antes da Fase 7 (não depois) |
| D-007 | 2026-10-07 | 0 | Medições deste repositório sem acesso à RTX 5070 são `ESTIMADO`/`REPRODUZIDO EM OUTRO HARDWARE`; viabilidade fica `PENDENTE` até rodar `tools/measure_run.py` + `tools/inventory_windows.ps1` no alvo. | Fato: esta sessão roda em contêiner Linux sem GPU | — | Execução no alvo |
| D-008 | 2026-10-07 | 4 | Arquitetura em duas camadas: casca de preservação (partição C1–C5 congelada + composição determinística + QA) com motor de síntese substituível. | Fase 2 §0/§5: nenhum gerador aberto preserva A por mecanismo (P/R) | gerador único com prompt; VTON por máscara agnóstica padrão; 3D+simulação | Protótipo A: costuras irrecuperáveis (H1 falsa) → voltar à Fase 2 |
| D-009 | 2026-10-07 | 4 | Shortlist: R1 FLUX.2 klein 4B (Apache) principal permissivo; R2 QIE-2511 condicional à Fase 3; R3 FASHN VTON 1.5 (ref. vestida nativa); R4 try-off→VTON por máscara (NC); R5 Kontext+RefTon comparador. | `01`/`02`/`03` (P/R/E) | ver `04` §2 | Protótipos B/C/F; medição H4 |
| D-010 | 2026-10-07 | 4 | F5 (correspondência/warp) só como condicionamento e auditoria; F6 (3D+simulação) descartada nesta fase. | Fase 2 §2 F5/F6; licenças SMPL; código pose-agnostic NV | F5/F6 como gerador | DressWild/ChatGarment com pesos+licença; Protótipo F favorecendo estimador por correspondência |
| D-011 | 2026-10-07 | 4 | Trilha permissiva é candidata a sistema final; trilha NC prototipada como comparador até o usuário declarar intenção de uso (O10). | intenção de uso não declarada | construir só NC | declaração do usuário |
| D-012 | 2026-10-07 | 4 | Rotas inviáveis descartadas sem protótipo: FLUX.2 dev, Step1X-Edit, HiDream-E1, IDM-VTON, Hunyuan 3.0, Emu3.5, WSL2. | `03` §4–§6 (P/R/E) | — | medição que contrarie (improvável) ou hardware diferente (fora do escopo) |
| D-013 | 2026-10-07 | 4 | Percepção/QA com componentes permissivos e nativos: SAM 3, BiRefNet, DWPose/rtmlib, SegFormer-B2-clothes, MoGe-2, SAM 3D Body→MHR, DINOv2, Qwen3-VL-8B. | licenças verificadas (P); nós nativos no core (P) | DensePose (NC/detectron2 no Windows), OpenPose (NC), InsightFace pesos (NC) | revisão jurídica de "SAM License"; Windows |
