# CHECKPOINT — estado do projeto para continuidade (2026-10-07)

## Onde estamos
Fases **0–4 entregues em forma documental**; **nenhum protótipo executado; nenhuma medição no hardware-alvo**. A seleção da Fase 4 é provisória por definição. Próximo gate: medição no alvo (Fase 3 §8) e Protótipo A.

## Estado por componente

| Componente | Estado | Medido | Estimado | Não resolvido |
|---|---|---|---|---|
| Contrato formal (C1–C5, eliminatórias, tempo, QA) | **escrito** (`00`) | — | tolerâncias O1/O2/O4/O5 | pendências O1–O9 (tabela em `00` §10.2) |
| Pesquisa SOTA | **escrita** (`01`, `research_raw/`) | — | — | itens NV listados em `01` §12 |
| Comparação de famílias | **escrita** (`02`) | — | matriz de capacidade com `?` em pose difícil para todos | nenhum dado de pose difícil existe |
| Viabilidade local | **estimada** (`03`) | **nada** | orçamentos `memory_budget.py` | tudo depende de `measure_run.py` no alvo |
| Seleção provisória | **escrita** (`04`): casca + R1 klein 4B / R2 QIE-2511 (condicional) / R3 FASHN 1.5 / R4 try-off→VTON máscara; R5 Kontext+RefTon comparador | — | — | trilha de licença O10 (uso comercial?) |
| Plano de protótipos A–H | **escrito** (`05`) | — | — | casos do split `dev` ainda não coletados |
| Benchmark | **esquema + matriz + validadores** (`benchmark/`) | — | — | 0 casos reais; fontes legais definidas (Commons/autoproduzido) |
| Ferramentas | `inventory_windows.ps1`, `measure_run.py`, `pixel_preservation_check.py`, `memory_budget.py` **testados em Linux/CPU** | smoke tests ok | — | execução no Windows/alvo |
| Workflows ComfyUI | **não existem** | — | — | só após Protótipo A/B |
| Custom nodes | **nenhum** (decisão: nativos + subprocessos) | — | — | — |

## O que foi medido nesta sessão
Apenas smoke tests dos scripts (CPU, sem GPU). Nada sobre a RTX 5070.

## O que permanece estimado
Toda VRAM/RAM/tempo de rotas (`03` §4–§5); baseline de RAM do Windows+ComfyUI (4.5 GB assumido); utilizável VRAM (~11.3 GB).

## O que não foi resolvido
- Desempenho de qualquer rota em HARD/EXTREME (desconhecido para toda a literatura).
- Viabilidade de QIE-2511 em 16 GB RAM (H4).
- Licença dos pesos FASHN 1.5, RefTon, Any2AnyTryon, SegFormer-B2-clothes (cards não acessíveis).
- Se GGUF é suportado pelo DynamicVRAM atual; stack torch do Comfy-Desktop 1.1.6 numa 5070.
- Intenção de uso (comercial vs. não) → trilha de licença.

## Como retomar
1. Ler `docs/04_selecao_provisoria.md` §7 e `docs/03_viabilidade_local.md` §8.
2. Rodar `tools/inventory_windows.ps1` no alvo e anexar o JSON em `runs/`.
3. Medir R1 e R3 em frio; depois R2 (gate H4) e R4.
4. Coletar 24 casos `dev` conforme `benchmark/coverage_matrix.md`; validar com `benchmark/validate_manifest.py`.
5. Executar Protótipo A; registrar em `docs/DECISION_LOG.md`.
