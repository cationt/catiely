# bench_r3.ps1 - medicao de viabilidade R3 (FASHN VTON 1.5) com tools/measure_run.py: 2 modos x (cold xN + warm xN), mesmo protocolo
# do klein4b_fp8_2ref_1mp e da R1-EI. SO EXECUTAR depois de setup_r3.ps1 ter terminado com "PRONTO PARA O BENCHMARK" e o output revisado.
# Uso: powershell -ExecutionPolicy Bypass -File garment-transfer\tools\r3_fashn\bench_r3.ps1 [-W3Root ...] [-Category tops] [-GarmentPhotoType model] [-N 3] [-Modes segfree,masked] [-RamMap C:\...\RAMMap.exe]
param(
  [string]$W3Root = "C:\Users\henri\OneDrive\Documentos\w3-measure",
  [string]$Category = "",                 # se vazio, le inputs\inputs_decision.json (gravado pelo setup)
  [string]$GarmentPhotoType = "",         # idem
  [string[]]$Modes = @("segfree", "masked"),
  [int]$N = 3,
  [int]$BudgetS = 3600,
  [string]$RamMap = "",                   # opcional: RAMMap.exe (Sysinternals) para esvaziar a standby list antes de cada run frio
  [switch]$WarmOnly,
  [switch]$ColdOnly
)
$ErrorActionPreference = "Stop"
$RepoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..\..\..")).Path
$GT = Join-Path $RepoRoot "garment-transfer"
$R3 = Join-Path $W3Root "r3"; $py = Join-Path $R3 ".venv\Scripts\python.exe"
$WeightsDir = Join-Path $W3Root "models\fashn-vton-1.5"
$inputs = Join-Path $R3 "inputs"; $runs = Join-Path $W3Root "runs"; $outs = Join-Path $R3 "outputs"
New-Item -ItemType Directory -Force -Path $runs, $outs | Out-Null
foreach ($f in @("A.png", "B.png")) { if (-not (Test-Path (Join-Path $inputs $f))) { throw "entrada ausente: $f (rode setup_r3.ps1 com -A/-B/-Category)" } }
if (-not $Category -or -not $GarmentPhotoType) {
  $dec = Join-Path $inputs "inputs_decision.json"
  if (-not (Test-Path $dec)) { throw "inputs_decision.json ausente: passe -Category e -GarmentPhotoType ou rode setup_r3.ps1 com -Category" }
  $d = Get-Content $dec -Raw | ConvertFrom-Json
  if (-not $Category) { $Category = $d.category }
  if (-not $GarmentPhotoType) { $GarmentPhotoType = $d.garment_photo_type }
}
if ($Category -notin @("tops", "bottoms", "one-pieces")) { throw "categoria invalida: $Category" }
foreach ($m in $Modes) { if ($m -notin @("segfree", "masked")) { throw "modo invalido: $m (segfree|masked)" } }
$labelBase = "r3_fashn15_bf16_576x864"
$noteBase = "R3 FASHN VTON 1.5 (fashn_vton @ 7c0f10af; model.safetensors d6cd3828...); num_samples 1; 30 passos; CFG 1.5; seed 42; category=$Category; garment_photo_type=$GarmentPhotoType; processo proprio (tree_private/tree_rss = motor); offline (HF_HUB_OFFLINE=1 + guarda de rede; parser local); DWPose em CUDAExecutionProvider exigido; mesmas A/B do klein4b_fp8_2ref_1mp; cold = process-cold (page cache do SO NAO esvaziado salvo RAMMap); warm = processo novo com cache do SO aquecido (NAO residente)"

function Run-One($mode, $state, $i) {
  $label = "{0}_{1}" -f $labelBase, $mode
  $out = Join-Path $outs ("{0}_{1}_r{2}.png" -f $label, $state, $i)
  $modeFlag = if ($mode -eq "segfree") { "--segmentation-free" } else { "--masked" }
  $cmd = @((Join-Path $GT "tools\r3_fashn\run_fashn_vton.py"), "--person", (Join-Path $inputs "A.png"), "--garment", (Join-Path $inputs "B.png"), "--weights-dir", $WeightsDir, "--category", $Category, "--garment-photo-type", $GarmentPhotoType, $modeFlag, "--num-samples", "1", "--num-timesteps", "30", "--guidance-scale", "1.5", "--seed", "42", "--out", $out, "--mode-label", $mode)
  $note = $noteBase + "; mode=" + $mode + " (" + $(if ($mode -eq "segfree") { "parser executado, masking da pessoa desabilitado" } else { "parser executado, masking da pessoa habilitado" }) + ")"
  if ($state -eq "cold" -and -not ($RamMap -and (Test-Path $RamMap))) { $note += "; cold_pagecache_unflushed" }
  Write-Host ("`n### {0} {1} run {2}/{3}" -f $mode, $state, $i, $N) -ForegroundColor Cyan
  & $py (Join-Path $GT "tools\measure_run.py") --label ("{0}_{1}" -f $label, $state) --state $state --budget-s $BudgetS --interval-s 0.5 --out $runs --note $note -- $py @cmd
  Write-Host ("exit measure_run: " + $LASTEXITCODE)
  if (Test-Path ($out + ".json")) { Get-Content ($out + ".json") | ConvertFrom-Json | Select-Object verdict, dtype, phases, torch_vram, onnx_providers | ConvertTo-Json -Depth 4 }
}
function Flush-Cache {
  if ($RamMap -and (Test-Path $RamMap)) { & $RamMap -Et; Start-Sleep -Seconds 3; Write-Host "standby list esvaziada (RAMMap -Et)" }
  else { Write-Host "AVISO: sem RAMMap - page cache do SO NAO esvaziado; run frio registrado como cold_pagecache_unflushed" -ForegroundColor Yellow }
}
foreach ($mode in $Modes) {
  if (-not $WarmOnly) { for ($i = 1; $i -le $N; $i++) { Flush-Cache; Run-One $mode "cold" $i } }
  if (-not $ColdOnly) { for ($i = 1; $i -le $N; $i++) { Run-One $mode "warm" $i } }
}
Write-Host "`nJSONs do measure_run em $runs ; saidas e sidecars em $outs" -ForegroundColor Green
Write-Host ("Registro: python garment-transfer\tools\r1ei\summarize_runs.py --runs-dir " + $runs + " --label-prefix " + $labelBase + "_segfree --sidecars-dir " + $outs + " --candidate R3 --out r3_segfree.json (idem _masked)")
