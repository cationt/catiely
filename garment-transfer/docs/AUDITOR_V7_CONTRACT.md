# Proposta de contrato do auditor v7 — D-059

**Estado: proposta para revisão; v7 ainda não implementado.** Fonte normativa: `03_viabilidade_local.md` §7b, D-059. Esta preparação pina o lote 2 e prepara `Derive` CPU; não executa a derivação real, GPU, G0 ou O_null2. Sequência: revisão → operador executa `Derive` → D-060 decide tolerâncias/frações e eventual ramo (b) → implementar auditor v7 e migrar fixtures → FREEZE por caso → G0. O auditor v6 permanece operacional segundo seu contrato histórico. Nenhum requisito abaixo habilita uso antecipado de schema 2 no v6.

## Referências, grades e proveniência

| Alvo | Imagens / máscaras | Referência de identidade | Contagem do canvas |
|---|---|---|---|
| `engine` | O′ interno e máscaras na grade declarada em `grid` | `A_fwd`, produzida pelo mesmo executor pinado da nula; `identity_reference = "A_forward"` | largura × altura da grade interna |
| `composed` | O e máscaras na grade de A | A original; `exact`, tol 0 e PROTECTED 1,0 | largura × altura de A |

O auditor **confere o SHA256 de `A_fwd` e não reimplementa geometria**. O′ e máscaras do engine devem ter a grade declarada: incompatibilidade → `INCONCLUSIVO:grid_mismatch`, nunca FAIL atribuído ao motor. Divergência de `A_fwd` → `INCONCLUSIVO:a_forward_mismatch`. A ligação nula↔SHA de A original↔tupla exata permanece obrigatória; `sha256.a_forward` não substitui `sha256.a`.

**Adendo D-059a:** para a A.jpg de viabilidade, a referência Klein vem de `klein_crop_api.json` no executor pinado, `--cpu`, sem VAE: LoadImage → ImageCrop720×1536(2,0) → SaveImage. A decodificação PyAV não é reimplementada. Piso contra Pillow e diferença entre decodificadores ficam informativos no mesmo schema2, com versões PyAV/Pillow; o histórico continua intacto. Predição normativa ≤8/7/7/9/10 (suporte/skin/background/hair_face/occluders); qualquer excesso sobre esses limites ou o p99,5 contra Pillow interrompe para revisão, sem aceitar a nula. A do Proto0 em PNG; JPEG restrito à A pinada de viabilidade.

`A_fwd` substitui A em `same`, comparações por zona, franja, ΔE e `protected_max_err` do engine. `--a-ref` continua somente cross-check, exige suporte explícito ou full-canvas explícito, na **mesma grade interna contra `A_fwd`**; `--null-stats` permanece normativa. O escalar do cross-check > `tol_p995_support + 1` continua `null_stats_inconsistent_with_a_ref` / INCONCLUSIVO. `--a-ref` sozinha e `--tol-engine` explícito continuam restritos a minimal.

## Geometria de máscaras e domínio

As imagens de referência vêm dos executores pinados; o módulo compartilhado `tools/null_geometry.py` fornece `forward_grid(rota, tamanho de A, parâmetros do caso)` e transformação de máscaras por **nearest**. Ele participa dos pins, de `code_identity()` e dos testes contra os artefatos preservados. Máscaras internas e originais são dois conjuntos distintos. Keypoints de A seguem a afim da grade; pontos fora são descartados e contados em `keypoints_outside_grid`, com `--person-scale-px` escalado. Suporte de validade do canvas, por nearest, intersecta todas as regiões de identidade e a franja quando a caixa excede A.

**BAND_MIN fora do domínio interno → `INCONCLUSIVO:engine_domain_excludes_band`**, a conferir no validador/auditor. Pixels descartados por crop não ganham validade por cópia de A.

Os valores em `thresholds` continuam em px da grade original de A: `contact_fringe_px` congelado no manifesto e `g_boundary_err_px` inalterado, CLI ≤ 2. Só o raio de contato interno usa `max(1, floor(v × s + 0,5))`, gravado em `grid.contact_fringe_px_internal`, **fora de `thresholds`**. `s` é a escala linear efetiva após o crop central; o gate continua exigindo limiares iguais entre casos.

## Estatísticas schema 2

O v7 rejeitará **schema 1 em todos os perfis**. O schema 2 de O_null1 usa a métrica inalterada `max_RGB(abs(uint8 O_null1 − uint8 A_fwd))`, com percentis somente em `support ∩ zona`; `tol = max(1, ceil(p99,5))`. Publica:

- `kind: O_null1`, tupla exata em `route_config`, versões de Pillow/ComfyUI;
- `grid`: rota, largura/altura, `forward_policy`, `scale_linear` e raios internos;
- SHA256 de A original, `A_fwd`, O_null1, suporte e zonas da grade interna;
- `counts.canvas` interno, `support_fraction`, `counts.by_zone.<zona>.support` e cauda `0,005 × n` ao lado da tolerância;
- p50/p95/p99/p99,5/max, `tol_p995_support`, tolerâncias por zona e `frac_above_tol` por suporte e zona.

Teto **12** para escalar e cada zona de O_null1 interna, sem mudar a métrica para obter aprovação. Cauda da zona < 100 px → sua tolerância é **informativa**, aplica-se o escalar. Mapeamento permanece PROTECTED→hair_face, pele descoberta→skin, fundo→background, FRONT_OCCLUDERS→occluders; zona ausente recorre ao escalar, clothing só reportada. Frações engine `min_* = 1 − frac_above_tol − margem` serão decididas em **D-060**; não assumir 1,0/0,98. A aplicação do teto a O_null2 também aguarda D-060; sem decisão explícita, O_null2 é informativa.

FASHN é `identity_no_reconstruction`, tol 1, `provisional_until_O_null2:true`, **não medida**, na saída unpad (407×864 para a A pinada). Diagnósticos futuros com tol 8/12 usam os mesmos O′/G e SHAs, minimal, `gate_eligible=false`, fora do índice do gate, ao lado de tol 1; franja escala com a tolerância. Isso não antecipa o G0 da FASHN.

## G, composição e costura

G é medida em O′ interno por segmentação independente/anotação humana; os dois auditores consomem **os mesmos SHA** dessa evidência. Para composed, `Gc = nearest(G_int)` levada à grade de A; `--garment-mask-composed` obrigatório se grid ≠ A. A colagem do compositor fica em Gc ∪ franja(8) na grade de A; o contrato composto continua exact/tol 0/PROTECTED 1,0. `composition_seam` compara O apenas com O′ reprojetada por política registrada (inverso usado somente nessa métrica), ou é removida. A derivação normativa da Parte 2 não usa esse inverso.

## FREEZE, gate e migração

`g0_gate` exigirá auditor **7 + schema 2 + grid**; `freeze_proto0` conferirá a grade contra `forward_grid` e preservará a ligação da nula à A e à tupla do caso. Nula desta A pinada valida contrato/teto e **não habilita G0 de outra A ou tupla**. Migrar fixtures dos auditores, FREEZE e gate para os dois conjuntos de máscaras, hashes e contagens internos, mantendo os controles do contrato composto.

Redefinir `identity_output` do engine como O′ := `A_fwd` (deve falhar por não-criação) e `same_garment_noop` como comparação na grade interna; o composto continua contra A. A calibração dos controles e as frações aguardam D-060 antes da implementação do v7. Não declarar fixtures migradas nesta preparação.

As tuplas G0 a congelar são as do PREREG §3: Klein crop central a múltiplos de 16 sem reescala até 1,1 MP, acima escala 1 MP com nula própria; QIE 544×960; R1-EI caixa da máscara congelada ×1,2 → 1024²; FASHN fit 864 / ResizePad 576×864 / unpad. O crop Klein substituirá o nó de escala no caminho de A no grafo G0 importado/pinado, preservando o VAE e declarando o caminho de B. Smoke de memória Klein n=3 cold somente se algum crop exceder 1 MP, antes de G0. A Parte 2 QIE 688×1504 é distinta da futura tupla G0: 544×960 é explícita no workflow local 0,5 MP, não entrada literal da tabela 1 MP de `FluxKontextImageScale`.

Klein/QIE seguem ramo (a); R1-EI permanece suspenso até Parte 2; ramo (b) não acionado. Se resultados exigirem nova decisão, ela será registrada em D-060, sem mudar teto/métrica, escolher erosão de suporte ou adotar frações para fazer passar.
