# bench_r1ei.ps1 - medicao de viabilidade R1-EI com tools/measure_run.py (cold n=3, warm n=3), mesmo protocolo do klein4b_fp8_2ref_1mp.
# SO EXECUTAR depois de setup_r1ei.ps1 ter terminado com "PRONTO PARA O BENCHMARK" e o output ter sido revisado.
# Uso: powershell -ExecutionPolicy Bypass -File garment-transfer\tools\r1ei\bench_r1ei.ps1 [-W3Root ...] [-Mode normal|fp8|offload] [-N 3]
param(
  [string]$W3Root = "C:\Users\henri\OneDrive\Documentos\w3-measure",
  [string]$Mode = "normal",
  [int]$N = 3,
  [int]$BudgetS = 3600,
  [string]$RamMap = "",             # opcional: caminho do RAMMap.exe (Sysinternals) para esvaziar a standby list entre runs frios
  [switch]$WarmOnly,
  [switch]$ColdOnly
)
$ErrorActionPreference = "Stop"
$RepoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..\..\..")).Path
$GT = Join-Path $RepoRoot "garment-transfer"
$R1 = Join-Path $W3Root "r1ei"; $py = Join-Path $R1 ".venv\Scripts\python.exe"
$BaseDir = Join-Path $W3Root "models\FLUX.2-klein-base-4B"; $LoraDir = Join-Path $W3Root "models\Easy-Insert-diffusers"; $CloneDir = Join-Path $R1 "Easy-Insert"
$inputs = Join-Path $R1 "inputs"; $runs = Join-Path $W3Root "runs"; $outs = Join-Path $R1 "outputs"
New-Item -ItemType Directory -Force -Path $runs, $outs | Out-Null
foreach ($f in @("A.png", "B.png", "A_insert_mask.png", "B_ref_mask.png")) { if (-not (Test-Path (Join-Path $inputs $f))) { throw "entrada ausente: $f (rode setup_r1ei.ps1 com -A/-B)" } }
$label = "r1ei_kleinbase4b_easyinsert_bf16_1024_$Mode"
$note = "R1-EI Diffusers Flux2KleinPipeline + LoRA LiXiY/Easy-Insert; 15 passos CFG 4 (30 passes); crop 1024^2; mode=$Mode; processo proprio (tree_private = motor); mesmas A/B do klein4b_fp8_2ref_1mp; mascaras grosseiras de viabilidade"

function Run-One($state, $i) {
  $out = Join-Path $outs ("{0}_{1}_r{2}.png" -f $label, $state, $i)
  $cmd = @((Join-Path $GT "tools\r1ei\run_easy_insert.py"), "--a", (Join-Path $inputs "A.png"), "--b", (Join-Path $inputs "B.png"), "--insert-mask", (Join-Path $inputs "A_insert_mask.png"), "--ref-mask", (Join-Path $inputs "B_ref_mask.png"), "--out", $out, "--model-dir", $BaseDir, "--lora-dir", $LoraDir, "--easy-insert-dir", $CloneDir, "--mode", $Mode, "--seed", "1")
  Write-Host ("`n### {0} run {1}/{2}" -f $state, $i, $N) -ForegroundColor Cyan
  & $py (Join-Path $GT "tools\measure_run.py") --label ("{0}_{1}" -f $label, $state) --state $state --budget-s $BudgetS --interval-s 0.5 --out $runs --note $note -- $py @cmd
  Write-Host ("exit measure_run: " + $LASTEXITCODE)
  if (Test-Path ($out + ".json")) { Get-Content ($out + ".json") | ConvertFrom-Json | Select-Object verdict, phases, vram_peak_overall_mb, vram_reserved_peak_denoise_mb | Format-List }
}
function Flush-Cache {
  if ($RamMap -and (Test-Path $RamMap)) { & $RamMap -Et; Start-Sleep -Seconds 3; Write-Host "standby list esvaziada (RAMMap -Et)" }
  else { Write-Host "AVISO: sem RAMMap - page cache do SO NAO esvaziado; registre o run frio como cold_pagecache_unflushed" -ForegroundColor Yellow }
}
if (-not $WarmOnly) { for ($i = 1; $i -le $N; $i++) { Flush-Cache; Run-One "cold" $i } }
if (-not $ColdOnly) { for ($i = 1; $i -le $N; $i++) { Run-One "warm" $i } }
Write-Host "`nJSONs do measure_run em $runs ; saidas e sidecars em $outs" -ForegroundColor Green
