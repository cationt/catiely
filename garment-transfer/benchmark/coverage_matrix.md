# Matriz de cobertura do benchmark

Eixos (ver `manifest.schema.json` → `coverage`): **pose × perspectiva × categoria × construção × material × oclusão × modalidade de referência × operação**.
Não se testa o produto cartesiano completo; a matriz torna as **lacunas visíveis**. Toda célula não coberta é reportada como "não avaliado".

## Níveis (obrigatórios) e mínimos operacionais

| Nível | Definição | Dev (mín.) | Teste final (mín.) |
|---|---|---|---|
| EASY | frontal, em pé, peça simples, referência em orientação semelhante | 6 | 10 |
| MEDIUM | 3/4, sentado, braços parcialmente sobre a roupa, referência em outra pose | 6 | 10 |
| HARD | reclinado, agachado, pernas cruzadas/afastadas, assimetria, membros próximos da câmera, câmera baixa/alta, foreshortening, oclusões importantes | 6 | 10 |
| EXTREME | poses muito diferentes de B, perspectiva extrema, construção difícil, múltiplos membros cruzados, ocupação simultânea de pele+fundo, detalhes pequenos essenciais | 6 | 10 |

Esses números (24 dev / ≥ 40 final) são **mínimos para organizar a investigação**, não garantia estatística. Ampliar/revisar antes da Fase 7 conforme cobertura, variabilidade e custo (pendência O9 em `docs/00_formulacao_contrato.md`).

## Splits e anti-vazamento

- `dev` (ajuste de thresholds/arquitetura), `regression` (congelado após Fase 5; roda a cada mudança), `final_test` (congelado antes da Fase 7; **nunca** usado para ajustar nada).
- Vazamento controlado por `person_group_id`, `garment_group_id` e `source_group_id`: nenhum id aparece em mais de um split.
- Thresholds de QA são calibrados em `dev`, verificados em `regression`, reportados em `final_test`.

## Cobertura mínima por eixo (a atingir em `final_test`)

| Eixo | Valores que **devem** aparecer ≥ 3 vezes cada |
|---|---|
| Categoria | top, cropped_top, long_sleeve_top, jacket, skirt_mini, skirt_midi, skirt_maxi, shorts, pants, dress_tight, dress_loose, set_two_piece |
| Construção | straps_thin, asymmetric, slit, open_front, buttons/zipper, pleats, none_special |
| Material | solid matte, print_large, print_small/logo_text, satin_shiny, sheer_non_explicit, knit, denim |
| Oclusão | none, hands_on_garment, arms_crossing, hair_over_garment, object_in_front, self_occlusion_legs |
| Modalidade de referência | worn_other_person (**maioria**, caso central), catalog_ghost, flat_lay; hanger/mannequin ≥ 1 |
| Delta de pose A↔B | similar, moderate, very_different |
| Operação | replace, add_over_skin, add_over_background, add_over_layer, replace_and_expose_skin |
| Perspectiva | eye_level, low_angle, high_angle, foreshortened_limb |

## Controles obrigatórios

| Controle | Objetivo | Resultado esperado |
|---|---|---|
| `same_garment_noop` | B mostra a mesma peça que A já veste (outra foto) | O ≈ A na peça; QA não deve acusar `garment_remnants` nem `no_transfer` indevidamente (calibra falso positivo) |
| `wrong_category_should_fail` | Spec pede categoria que B não contém | `FAIL: invalid_spec`/`wrong_category` antes de gerar |
| `B_identity_leak_probe` | B com doador de aparência muito distinta de A (tom de pele, cabelo, fundo marcante) | nenhum traço do doador em O (`B_leakage`) |
| Mesmo garment, doadores distintos | Duas B com a mesma peça em pessoas diferentes | O deve convergir na peça; divergência mede dependência do doador |
| Pares reais (quando houver) | GT da mesma pessoa com a peça, registrando residuais de pose/luz | comparação estrutural, não pixel-a-pixel |

## Fontes e política legal

- **Redistribuição no repo** só para CC0/CC-BY (com atribuição) ou autoproduzidas com consentimento. Demais fontes: **apenas manifesto** (URL + sha256 + prep).
- Datasets acadêmicos (VITON-HD, DressCode, DeepFashion) têm licenças de pesquisa que **proíbem redistribuição**; são usados localmente apenas para desenvolvimento quando a licença permitir, e **nunca** no `final_test` redistribuível. Detalhes e verificação de licenças: `docs/01_estado_da_arte.md` §Datasets.
- Somente adultos, conteúdo não explícito, `consent_adult_non_explicit: true` obrigatório.

## Como preencher

1. Escolha a célula alvo pela lacuna da matriz (`python benchmark/coverage_report.py manifest.jsonl` lista células vazias).
2. Registre A, B, spec e `expected` (com estados observado/inferido/desconhecido **antes** de gerar qualquer saída).
3. Valide contra o schema: `python benchmark/validate_manifest.py manifest.jsonl`.
