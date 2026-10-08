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

Regras:
1. Nenhuma máscara deste diretório pode ser derivada de uma saída de qualquer motor. Data e autor ficam em `frozen_annotation`.
2. As máscaras de tecido novo **na saída** (`G`) usadas por `tools/occupancy_audit.py` vêm de um segmentador independente do motor (SAM 3 com texto/exemplar, `individual_masks` e `max_detections ≥ 4`, união das instâncias) ou de anotação humana da saída; nunca da máscara que o motor usou. **Calibração obrigatória:** anotar G manualmente em todas as saídas do Prototype 0 e medir IoU/precisão/recall do SAM 3 por zona (BAND_MIN, UNCERTAIN, franja); zona com IoU abaixo do limiar → veredito INCONCLUSIVO.
5. A auditoria roda em **dois alvos**: `O_engine` (saída bruta do motor reprojetada; mede o motor) e `O_composed` (entrega). Métricas de oclusor em `O_composed` são triviais quando a casca cola C1 de volta.
3. Casos sintéticos/controlados (render 3D ou pares autoproduzidos com/sem a peça) devem preencher `ground_truth_type` e `ground_truth`.
4. Somente adultos e conteúdo não explícito; `consent_adult_non_explicit: true` é obrigatório no schema.
