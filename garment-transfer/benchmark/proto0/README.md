# Prototype 0 — ADDITION / OCCUPANCY STRESS TEST — imagens e anotações congeladas

Este diretório recebe, **localmente** (não redistribuído salvo licença CC0/CC-BY/autoproduzido com termo), os arquivos referenciados por `benchmark/proto0_cases.jsonl`:

| Arquivo | Conteúdo | Quando é produzido |
|---|---|---|
| `<case>_A.png` | pessoa-alvo **sem** peça da categoria (ex.: sem camiseta; adulto, não explícito) | antes de qualquer geração |
| `<case>_B.png` | peça de referência **vestida em outra pessoa** | idem |
| `<case>_FO.png` | FRONT_OCCLUDERS: máscara binária (grade de A) do que deve ficar **à frente** da roupa nova (mãos, antebraço cruzado, cabelo, móvel) | anotação humana **antes** da geração |
| `<case>_BC.png` | BODY_COVERABLE: superfície observada de A que a roupa poderia cobrir (capacidade) | idem |
| `<case>_BMIN.png` | BAND_MIN: certamente tecido | idem |
| `<case>_BMAXB.png` | BAND_MAX_BODY: pele/roupa antiga que a peça PODE cobrir (condicional a atributos de B) | idem |
| `<case>_FS.png` | FREE_SPACE: fundo/objetos atrás que o volume PODE ocupar | idem |
| `<case>_UNC.png` | UNCERTAIN_OCCUPANCY: zona decidida pelo motor (axila, inter-membro, folga) | idem |
| `<case>_KGI.png` | KEPT_GARMENT_INTERFACE (quando há peça mantida; z-order via spec.layering) | idem |
| `<case>_PR.png` | (opcional) C1 estrito: rosto, fundo distante, objetos | idem |
| `<case>_EL_<elemento>.png` | máscara 2D **por elemento** do `z_order` (hand_R, forearm_L, upper_arm_L, torso_front_skin, furniture…); `front_occluders_mask` = união das `front_certain` (o validador checa) | idem |
| `<case>_GT.png` | só em pares autoproduzidos (`self_captured_pair`): a mesma pessoa COM a peça — GT real de ocupação e z-order | captura com tripé, termo assinado |

Relações do `z_order` (anotadas por elemento, antes de gerar): `front_certain` (fica à frente; eliminatório), `behind_must_cover` (a peça DEVE cobrir — torso frontal para top), `behind_may_cover` (depende de atributo de B — braço superior vs manga), `split_by_garment_edge` (parte à frente/parte coberta; fronteira = bainha sob a mão), `uncertain` (cabelo vs gola, cós vs bainha). Cabelo frontal: anotar só o **núcleo** (α ≥ 0,98) como `front_certain`; a franja é C5.

Casos pareados (controles de atribuição): `proto0_hard_01_pair_b` (mesma A, B em pose semelhante → isola eixo C), `proto0_easy_01_pair_b` (mesma A fácil, B estampada do EXTREME → isola fidelidade), `proto0_hard_03`/`proto0_hard_04` (mesma A com braços cruzados; B manga curta → `split_by_garment_edge`; B manga longa → `behind_must_cover`: a fronteira deve seguir a manga de B, não o corpo de A), `proto0_gt_pair_01` (par autoproduzido com GT real), `proto0_ctrl_noop_01` (A já veste a peça), `proto0_ctrl_negative_synth_01` (O fabricado com a mão apagada/movida — o auditor TEM de falhar).

Pré-requisito antes de gerar qualquer imagem (`layer_estimator_eval`): medir o estimador automático de camadas contra esta anotação — IoU por elemento (SAM 3 por **pontos** DWPose; o nó nativo `SAM3_Detect` não aceita exemplar de imagem e texto não distingue esquerda/direita), acerto da relação front/behind (profundidade mediana do render MHR; MoGe para móveis, com FOV compartilhado), e fração do torso nu que o parser de vestuário rotula como fundo (o conjunto ATR não tem classe de pele do tronco → `BODY_COVERABLE` vem da silhueta da pessoa menos elementos, não do parser). Elemento com IoU < 0,85 → `uncertain`.

Regras:
1. Nenhuma máscara deste diretório pode ser derivada de uma saída de qualquer motor. Data e autor ficam em `frozen_annotation`.
2. As máscaras de tecido novo **na saída** (`G`) usadas por `tools/occupancy_audit.py` vêm de um segmentador independente do motor (SAM 3 por **texto** "t-shirt" para a peça, `individual_masks` e `max_detections ≥ 4`, união das instâncias; SAM 3 por **pontos** DWPose para os elementos do corpo em O′) ou de anotação humana da saída; nunca da máscara que o motor usou. A métrica "a peça nasceu" exige também `band_min_change_magnitude` (ΔE em BAND_MIN acima do p95 do controle no-op) para evitar falso nascimento por pele levemente alterada. **Calibração obrigatória:** anotar G manualmente em todas as saídas do Prototype 0 e medir IoU/precisão/recall do SAM 3 por zona (BAND_MIN, UNCERTAIN, franja); zona com IoU abaixo do limiar → veredito INCONCLUSIVO.
5. A auditoria roda em **dois alvos**: `O_engine` (saída bruta do motor reprojetada; mede o motor) e `O_composed` (entrega). Em `O_engine`, **identidade de pixel do oclusor é só diagnóstica** (o round-trip do VAE altera quase todos os pixels); o eixo D usa métricas **estruturais**: tecido sobre o oclusor por elemento, IoU da máscara do oclusor re-segmentada, deslocamento de keypoints da mão, membro duplicado, tecido presente na coroa do oclusor. Em `O_composed`: identidade de pixel (C1, núcleo dos oclusores), `composition_seam` (O_composed vs O_engine na coroa) e `hair_halo`.
3. Casos sintéticos/controlados (render 3D ou pares autoproduzidos com/sem a peça) devem preencher `ground_truth_type` e `ground_truth`.
4. Somente adultos e conteúdo não explícito; `consent_adult_non_explicit: true` é obrigatório no schema.
