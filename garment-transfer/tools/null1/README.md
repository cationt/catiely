# O_null1 — distribuição nula e controles diagnósticos (D-057/D-058)

**Controles D-058 PREPARADOS, NÃO MEDIDOS.** Nenhum `Generate` ou GPU foi executado neste patch. A Klein normativa já foi medida pelo operador no lote `20261010T162735Z_1b40ed495243` e permanece `INCONCLUSIVE:null_distribution_not_credible`: suporte21, skin18, background22, hair_face19, occluders23. Os35 arquivos desse lote são preservados; hashes do batch/sidecar/estatísticas estão registrados no manifesto. D-057 permanece histórico; teto12, métrica, VAE e reprojeção normativa permanecem inalterados. Parada no commit para revisão do Claude. O_null2, Proto0/G0, E1/E2 e tuning permanecem fora desta etapa.

## Contrato congelado

A é exatamente a referência dos benchmarks Klein/R1-EI/R3/R2, 725×1536, SHA256 `f200d51028714bc1043d8f0cee632b3089c23bbd53216a64f8a912bd6fae151b`. Não se usa B, prompt de edição, UNET, CLIP, LoRA, sampler ou ruído. `denoise=0` significa encode/decode direto, sem executar sampler.

| Rota | Piso e escala | Reconstruction support em A |
|---|---|---|
| Klein 4B | ComfyUI próprio; VAE Flux2 bf16. Política real de `klein4b_fp8_2ref_1mp`: `ImageScaleToTotalPixels`, nearest-exact, 1×1024² pixels, resolution_steps=1 → **704×1490**; VAE center-crop → **704×1488**. | Inversa da caixa `[0,1,704,1489]` na imagem escalada. Centros dos pixels de A dentro da caixa: linhas 1…1534, largura inteira. |
| QIE-2511 Q5 | ComfyUI próprio; VAE Qwen bf16. Primária `qie2511_q5_2ref_1mp_40steps`, `FluxKontextImageScale`, Lanczos/center → **688×1504**. | Crop efetivo `[11,0,714,1536]` de A; bordas reamostradas incluídas. A secundária 544×960 exige outra nula. |
| R1-EI | `AutoencoderKLFlux2` bf16, posterior `.mode()`, encode/decode do crop com padding preto fora de A, Lanczos **1024²**. | `[-136,193,860,1189] ∩ canvas`; reprojeção da caixa **inteira**, sem insertion mask. |
| FASHN | Sem VAE: PIL fit864, sem upsampling →407×864; OpenCV `ResizePad(576,864)` → unpad407×864 → reprojeção. | Canvas inteiro. Piso comum aos modos segfree/masked; sem masking, DWPose ou VTON. |

`support.png` é binário 0/255 na grade original. Pixels copiados de A são excluídos; a implementação verifica que continuam iguais fora do suporte. A inversa inteira de QIE/R1-EI e FASHN usa Pillow Lanczos; a caixa fracionária Klein usa transformação afim Pillow bicubic com coordenadas de bordas e seleção pelos centros dos pixels. Não há alinhamento estimado por conteúdo. Geometria, kernel inverso, pesos, dtype, código e versões fazem parte de `route_config`; qualquer divergência futura de escala/VAE/resolução/reprojeção exige refazer a nula antes de utilizá-la.

`manifest.json` fixa o SHA do workflow Klein efetivamente usado (`41552539…`), os nós `92:111`/`92:110` como evidência de origem e os workflows mínimos `klein_api.json`/`qie_api.json`. O VAE Klein local teve seu SHA capturado (`d64f3a68…`); não foi inventada revisão remota para esse arquivo. Os demais pins preservam R1-EI, R2 e R3. Checks de fontes das rotas usam SHA256 normalizado LF; o diagnóstico DD verifica os bytes exatos das suas fontes pinadas. Pesos, A e imagens usam bytes exatos.

## Zonas e estatísticas

Um único parser pinado do R3 é executado sobre A original, em processo isolado: `fashn-human-parser==0.1.1`, código `f2771f2…`, pesos `1f80c34d…`. CUDA/float32, eval, seed42, algoritmos determinísticos, TF32 e cuDNN benchmark desligados; operação não determinística não suportada interrompe a execução. Não há fallback automático. Esta preparação só testa a taxonomia com labels sintéticos; **não executa o parser em A**.

- `skin`: arms ∪ legs ∪ torso ∪ feet.
- `background`: background.
- `hair_face`: face ∪ hair.
- `occluders`: hands.
- `clothing`, somente informativa: união `BODY_COVERAGE_TO_LABELS['full']` do parser (top/dress/skirt/pants/belt/scarf). Outros acessórios ficam fora dessas zonas e sua contagem é registrada.

Para cada zona, a amostra é estritamente `support ∩ zona`. Métrica: `max_RGB(abs(int32(O_null1)-int32(A)))`, partindo dos pixels RGB de 8 bits, igual ao auditor. Percentis NumPy `linear`; tolerância `max(1, ceil(p99.5))`, preservando a conversão do auditor. Zona com suporte vazio: estatísticas/tolerância `null`, contagem zero; o auditor usa o escalar de suporte. `clothing` não recebe tolerância normativa. Não se deriva margem, limiar de identidade ou ΔE do no-op nesta etapa.

Cada `null_stats.json` contém `tol_p995_support`, `tol_p995_by_zone`, p50/p95/p99/p995/max, histogramas completos 0…255, `support_fraction`, contagens totais e dentro do suporte, SHA256 de A/O_null1/support/zonas e a tupla `route_config`. O teto existente **12** vale para o escalar e para cada zona normativa. Excedê-lo preserva os dados e marca a nula `INCONCLUSIVE`, mas **continua o lote** (D-058); nunca se eleva o teto para fazer passar. Ao concluir todos os runs, `batch.json.verdict=INCONCLUSIVE` se qualquer rota for inconclusiva, com lista `inconclusive_routes` e exit3; todas válidas dão `ok`/exit0. Erro operacional, OOM, deadline ou verdict inválido ainda interrompem imediatamente com `FAIL:batch_stopped`/exit1.

O auditor v6 usa `--null-stats` normativamente, inclusive quando `--a-ref` é fornecida. No perfil g0, o JSON precisa pertencer ao FREEZE (`freeze_proto0.py --null-stats arquivo`, opção repetível). `--a-ref` só faz cross-check, com `--a-ref-support support.png` ou declaração `--a-ref-full-canvas`; escalar derivado maior que `tol_p995_support + 1` produz `null_stats_inconsistent_with_a_ref`/`INCONCLUSIVO` (exit3). `--a-ref` sozinha e `--tol-engine` explícito só são aceitos em minimal. PROTECTED usa hair_face, pele descoberta skin, fundo background e FRONT_OCCLUDERS occluders; zona ausente usa o escalar. A referência das métricas é A; a-ref não a substitui. O consumidor do gate rejeita relatórios anteriores sem nula normativa congelada. Nenhum gate real é executado aqui.

## Controles D-058 — não normativos, sem teto

Ordem fixa após o parser: `klein`, `klein_resample_only`, `klein_vae_native`, `qie`, `qie_resample_only`, `qie_vae_native`, `r1ei`, `r1ei_resample_only`, `fashn`.

| Controle | Caminho |
|---|---|
| `klein_resample_only` | LoadImage → mesma ImageScaleToTotalPixels nearest-exact → ImageCrop704×1488, offset(0,1) → SaveImage; sem VAE; inverso idêntico ao normativo. |
| `klein_vae_native` | LoadImage → ImageCrop720×1536 → mesmo VAE encode/decode → SaveImage; paste direto no recorte, sem reescala. |
| `qie_resample_only` | LoadImage → somente FluxKontextImageScale → SaveImage; sem VAE; mesmo inverso QIE. |
| `qie_vae_native` | LoadImage → ImageCrop720×1536 → mesmo VAE Qwen encode/decode → SaveImage; paste direto, sem reescala. |
| `r1ei_resample_only` | Mesmo crop com padding preto; PIL Lanczos996→1024→996 no worker; paste da caixa inteira, sem VAE e sem segundo resize no supervisor. |

Recortes nativos usam `[2,0,722,1536]`: offset central inteiro `(725−720)//2`, como o crop do VAE pinado. Suporte=720×1536, sem as duas colunas da esquerda e três da direita. Klein usa dimensões múltiplas de16; QIE, de8. FASHN continua sua nula normativa de reamostragem existente.

Sidecars, tupla e estatísticas dos controles registram `normative: false`; não se chama a validação do teto. `ok` significa execução completa, não aprovação da nula. Os JSONs diagnósticos usam `kind=O_null1_diagnostic`, rejeitado pelo auditor existente, e `status=DIAGNOSTIC_NOT_FOR_CALIBRATION`; suas estatísticas não substituem τ_null normativa. Workflows sem VAELoader não resolvem VAE nem exigem `vae_evidence`; workflows com VAE continuam exigindo a evidência. Fontes ImageCrop e quatro novos workflows têm SHA256 no manifesto. Auditor, FREEZE, cronograma DD e regras D-059 não são alterados por este handoff.

## Execução pelo operador, somente depois da revisão

Na raiz deste checkout, Windows PowerShell 5.1:

```powershell
Set-Location 'C:\Users\henri\OneDrive\Documentos\W3_REBUILD\catiely'
powershell -NoProfile -ExecutionPolicy Bypass -File .\garment-transfer\tools\null1\setup_null1.ps1 -W3Root 'C:\Users\henri\OneDrive\Documentos\w3-measure'
powershell -NoProfile -ExecutionPolicy Bypass -File .\garment-transfer\tools\null1\run_null1.ps1 -Mode Plan
```

`setup_null1.ps1` somente verifica arquivos/versões já instalados; não instala, baixa ou faz smoke. A rede externa é bloqueada antes dos imports de modelos (variáveis offline e Python audit hook para sockets/DNS; HTTP local sem proxy/redirecionamento). Não é uma regra de firewall para código nativo arbitrário. `Plan` é o default e não abre servidor, imagem real, parser ou pesos.

Para **gerar as quatro nulas e cinco controles**, fechar outros ComfyUI e executar, após aprovação do commit:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\garment-transfer\tools\null1\run_null1.ps1 -Mode Generate -W3Root 'C:\Users\henri\OneDrive\Documentos\w3-measure'
```

A árvore precisa estar commitada/limpa. O parser precede os nove runs na ordem acima. Cada ComfyUI usa processo novo, diretórios privados, loopback8197 e log DEBUG; verifica dono do endpoint, VAE efetivamente resolvido quando presente e `status.messages` com `execution_cached=[]`. O fallback interno de OOM para VAE tiled é desabilitado por wrapper em memória que relança a exceção; fontes upstream permanecem intactas. Falha operacional/deadline/verdict inválido encerra o lote sem retry/rota seguinte; INCONCLUSIVE estatístico não interrompe. O watchdog administrativo de3600s não é limiar de qualidade nem benchmark.

Saída: `garment-transfer/runs/proto0/null/<UTC_UUID>/`, contendo `batch.json`, `provenance.json`, `dd_schedule.json`, `zones/` e um diretório por rota. Cada rota publica `native.png`, `O_null1.png`, `support.png`, cinco máscaras, `null_stats.json`, `sidecar.json` e log próprio (mais workflow/history no ComfyUI). Nada sobrescreve lotes anteriores. Os artefatos são locais e ignorados pelo Git; a publicação/uso dos limiares vem depois da revisão dos resultados.

Para imprimir apenas o diagnóstico DD, em CPU, sem gerar nula:

```powershell
& "$env:LOCALAPPDATA\Comfy-Desktop\ComfyUI-Installs\ComfyUI\ComfyUI\.venv\Scripts\python.exe" -B .\garment-transfer\tools\null1\dd_schedule.py --route all
```

São4,50 e40 instantes, sem incluir o terminal zero como passo. A fórmula pinada usa `sigma_to=max(model_sampling.sigma_min, step_sigmas[-1])`, não um zero assumido. Klein4 recebe704×1490 antes do cropVAE. Klein-base50 é diagnóstico do DD **ComfyUI** a1024²; o runner Diffusers R1-EI medido não implementa DD. Nenhum nível arbitrário de R(p) é escolhido. Ver `REVIEW.md` para verificações e limites desta preparação.
