# CHECKPOINT — estado do projeto para continuidade (2026-10-08, após red-team)

## Onde estamos
Fases 0–4 entregues **e revisadas adversarialmente** (`docs/06_RED_TEAM_REVISION.md`). **Nenhum protótipo executado; nenhum modelo instalado; nenhuma medição padronizada no hardware-alvo** (existe evidência histórica não padronizada, `03` §1b). A decisão estrutural D-008 foi **rebaixada a hipótese H0**; o primeiro experimento real é o **Prototype 0 — ADDITION / OCCUPANCY STRESS TEST**.

## Estado por componente

| Componente | Estado | Medido | Estimado | Não resolvido |
|---|---|---|---|---|
| Contrato (`00`) | **revisado**: três campos (autoridade de reconstrução / autorização de ocupação / z-order por elemento); C1–C5 vira vocabulário de auditoria; auditoria dupla O′/O; regra da banda com franja C3 | — | tolerâncias O1/O2/O4/O5/O11 | O3 reformulada; O12 política de oclusor |
| SOTA (`01`, `research_raw/`) | **revisado**: níveis de evidência corrigidos em 7 clusters (`research_raw/07`); afirmação sobre benchmarks reformulada | — | — | itens NV listados em `01` §12 e `07` |
| Famílias (`02`) | **revisado**: casca = hipótese H0; motores = candidatos sem "principal" | — | pose difícil `?` para todos | — |
| Viabilidade (`03`) | **revisado**: evidência histórica (QIE-2511 Q5 ~10–15 min @0,5 MP; sweep de denoise); estimador = triagem com bandas; OmniGen2/BAGEL marginais; IDM-VTON citação corrigida | **histórico não padronizado** | tudo o mais | medição com `measure_run.py` |
| Seleção (`04`) | **revisado**: H0; canal por rota (F1 noise_mask+DifferentialDiffusion verificado; F2 política de oclusor; F3 sem canal); H7′, H11–H13; Prototype 0 antes de A | — | — | H4 (QIE tempo); trilha de licença O10 (FASHN não permissiva via parser) |
| Plano de protótipos (`05`) | **revisado**: Prototype 0 primeiro; A/D/F com auditoria dupla | — | — | casos `dev` ainda não coletados |
| Red-team (`06`) | **escrito** (fontes + lentes 1–2 + verificação direta); lentes 3–6 e refutações **pendentes de incorporação** | — | — | ver §11 de `06` |
| Benchmark | schema v3 (consentimento obrigatório; `proto0`; `frozen_annotation` com FREE_SPACE/UNCERTAIN/z-order/estados); 6 casos proto0 esqueleto validados | — | — | imagens e máscaras reais ainda não produzidas |
| Ferramentas | `inventory_windows.ps1` (multi-caminho), `measure_run.py`, `pixel_preservation_check.py`, `memory_budget.py` (triagem), `occupancy_audit.py` v2 (alvos duplos; 5 testes sintéticos ok) | smoke tests CPU | — | execução no Windows/alvo |
| Workflows ComfyUI / custom nodes | **não existem** (por decisão) | — | — | só após Prototype 0 |

## O que foi medido
Nada na RTX 5070 nesta sessão. Histórico não padronizado: QIE-2511 Q5 @~544×960 ≈ 10–15 min/imagem; sweep de denoise 0.18–1.00 (`03` §1b).

## O que permanece estimado
VRAM/RAM/tempo de todas as rotas; VRAM de FASHN (não declarada); valores do mapa de autoridade (0.7/0.5/0.3) e r_C3.

## O que não foi resolvido
- H0/H11: se força graduada no latente desacopla criar-roupa de reconstruir-A (destilados têm 4 degraus).
- z-order `uncertain` indecidível a priori (cabelo vs gola; cós vs bainha).
- Confiabilidade do segmentador G sobre tecido alucinado (calibração obrigatória).
- Licenças: FASHN parser NC; SAM/DINOv3 proprietárias revogáveis; SegFormer-B2-clothes herança NVIDIA; intenção de uso (O10).
- Nenhum benchmark externo com GT real de adição sobre pele em pose difícil.

## Como retomar
1. Ler `docs/06_RED_TEAM_REVISION.md` §6–§10 e `docs/04_selecao_provisoria.md` §7.
2. Incorporar lentes 3–6 + refutações (se ainda pendentes) em `06` e docs 00–05.
3. Rodar `tools/inventory_windows.ps1` no alvo; medir klein 4B, FASHN 1.5 e QIE-2511 Q5 (mesma A/B do sweep) com `measure_run.py` em frio.
4. Produzir as imagens e máscaras congeladas dos 6 casos `proto0` (+ controle negativo sintético + par com GT) e validar.
5. Executar o Prototype 0 (Gate G0) e aplicar os critérios pré-registrados; registrar em `DECISION_LOG.md`.
