# Prototype 0 — ADDITION / OCCUPANCY STRESS TEST — imagens e anotações congeladas

Este diretório recebe, **localmente** (não redistribuído salvo licença CC0/CC-BY/autoproduzido com termo), os arquivos referenciados por `benchmark/proto0_cases.jsonl`:

| Arquivo | Conteúdo | Quando é produzido |
|---|---|---|
| `<case>_A.png` | pessoa-alvo **sem** peça da categoria (ex.: sem camiseta; adulto, não explícito) | antes de qualquer geração |
| `<case>_B.png` | peça de referência **vestida em outra pessoa** | idem |
| `<case>_FO.png` | FRONT_OCCLUDERS: máscara binária (grade de A) do que deve ficar **à frente** da roupa nova (mãos, antebraço cruzado, cabelo, móvel) | anotação humana **antes** da geração |
| `<case>_BC.png` | BODY_COVERABLE: superfície de A que a roupa pode cobrir | idem |
| `<case>_BMIN.png` | faixa mínima de ocupação (certamente tecido) | idem |
| `<case>_BMAX.png` | faixa máxima de ocupação (possivelmente tecido, incl. fundo que o volume pode ocupar) | idem |
| `<case>_PR.png` | (opcional) C1 estrito: rosto, fundo distante, objetos | idem |

Regras:
1. Nenhuma máscara deste diretório pode ser derivada de uma saída de qualquer motor. Data e autor ficam em `frozen_annotation`.
2. As máscaras de tecido novo **na saída** (`G`) usadas por `tools/occupancy_audit.py` vêm de um segmentador independente do motor (SAM 3 com texto/exemplar) ou de anotação humana da saída; nunca da máscara que o motor usou.
3. Casos sintéticos/controlados (render 3D ou pares autoproduzidos com/sem a peça) devem preencher `ground_truth_type` e `ground_truth`.
4. Somente adultos e conteúdo não explícito; `consent_adult_non_explicit: true` é obrigatório no schema.
