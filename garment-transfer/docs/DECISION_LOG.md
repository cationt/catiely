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
