# setup_r1ei.ps1 — prepara a medição de viabilidade da rota R1-EI (FLUX.2-klein-base-4B + Easy-Insert) na máquina-alvo.
# NÃO executa o benchmark. Faz: venv dedicado, torch CUDA (mesma versão do ComfyUI Desktop quando detectável), deps pinadas,
# clone do Easy-Insert no commit pinado, download dos pesos (HF, revisões pinadas), verificação de sha256/tamanhos, dry-run do runner.
# Uso (PowerShell, pasta do repo catiely):
#   powershell -ExecutionPolicy Bypass -File garment-transfer\tools\r1ei\setup_r1ei.ps1 -A <A.png> -B <B.png> [-W3Root C:\...\w3-measure]
param(
  [string]$W3Root = "C:\Users\henri\OneDrive\Documentos\w3-measure",
  [string]$A = "",
  [string]$B = "",
  [string]$InsertBbox = "0.25,0.18,0.75,0.72",   # bbox normalizada xyxy da região de inserção em A (torso) — só p/ viabilidade
  [string]$RefBbox = "0.20,0.15,0.80,0.75",      # bbox normalizada xyxy da peça em B — só p/ viabilidade
  [string]$PythonExe = "",                        # opcional: interpretador para criar o venv (padrão: py -3.12 → python do ComfyUI → python)
  [string]$TorchIndex = "",                       # opcional: ex. https://download.pytorch.org/whl/cu128 (padrão: deduzido do torch do ComfyUI)
  [switch]$SkipDownload,
  [switch]$SkipBaseHash
)
$ErrorActionPreference = "Stop"
$RepoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..\..\..")).Path          # catiely/
$GT = Join-Path $RepoRoot "garment-transfer"
$R1 = Join-Path $W3Root "r1ei"
$Venv = Join-Path $R1 ".venv"
$ModelsRoot = Join-Path $W3Root "models"
$BaseDir = Join-Path $ModelsRoot "FLUX.2-klein-base-4B"
$LoraDir = Join-Path $ModelsRoot "Easy-Insert-diffusers"
$CloneDir = Join-Path $R1 "Easy-Insert"
$Manifest = Get-Content (Join-Path $GT "tools\r1ei\r1ei_manifest.json") -Raw | ConvertFrom-Json
$Log = Join-Path $R1 ("setup_" + (Get-Date -Format "yyyyMMddTHHmmss") + ".log")
New-Item -ItemType Directory -Force -Path $R1, $ModelsRoot | Out-Null
Start-Transcript -Path $Log -Force | Out-Null
function Step($m) { Write-Host ("`n=== " + $m + " ===") -ForegroundColor Cyan }
function Fail($m) { Write-Host ("FALHA: " + $m) -ForegroundColor Red; Stop-Transcript | Out-Null; exit 1 }

Step "0. Espaço em disco e inventário mínimo"
$drive = (Get-Item $W3Root).PSDrive.Name
$free = (Get-PSDrive $drive).Free / 1GB
Write-Host ("Disco {0}: {1:N1} GB livres (necessário ≈ 15 GB modelos + ≈ 6 GB venv/torch + 0.1 GB clone)" -f $drive, $free)
if ($free -lt 24) { Fail "menos de 24 GB livres em $drive — libere espaço ou use -W3Root em outro disco" }
$os = Get-CimInstance Win32_OperatingSystem
Write-Host ("RAM física: {0:N1} GB | Commit limit (RAM+pagefile): {1:N1} GB" -f ($os.TotalVisibleMemorySize/1MB), ($os.TotalVirtualMemorySize/1MB))
try { nvidia-smi --query-gpu=name,memory.total,driver_version --format=csv } catch { Write-Host "nvidia-smi não encontrado no PATH (ok)" -ForegroundColor Yellow }

Step "1. Detectar Python do ComfyUI Desktop (para casar torch/CUDA e, se preciso, criar o venv)"
$comfyPy = $null
$cands = @()
if ($env:COMFY_PYTHON) { $cands += $env:COMFY_PYTHON }
$cands += Get-ChildItem -Path "$env:LOCALAPPDATA\Comfy-Desktop\ComfyUI-Installs" -Recurse -Depth 3 -Filter python.exe -ErrorAction SilentlyContinue | Where-Object { $_.FullName -match "\\\.venv\\Scripts\\python\.exe$" } | ForEach-Object { $_.FullName }
$cands += "C:\Users\henri\AppData\Local\Comfy-Desktop\ComfyUI-Installs\ComfyUI\ComfyUI\.venv\Scripts\python.exe"
foreach ($c in $cands | Select-Object -Unique) { if ($c -and (Test-Path $c)) { $comfyPy = $c; break } }
$comfyTorch = $null; $comfyCuda = $null
if ($comfyPy) {
  Write-Host "ComfyUI python: $comfyPy"
  $probe = & $comfyPy -c "import torch,sys; print(torch.__version__); print(torch.version.cuda); print(sys.version.split()[0])" 2>$null
  if ($probe) { $comfyTorch = ($probe[0] -split '\+')[0]; $comfyCuda = $probe[1]; Write-Host "ComfyUI torch: $($probe[0]) | CUDA $comfyCuda | python $($probe[2])" }
} else { Write-Host "ComfyUI Desktop não detectado (ok; torch vem do índice cu128)" -ForegroundColor Yellow }
if (-not $TorchIndex) {
  if ($comfyCuda) { $TorchIndex = "https://download.pytorch.org/whl/cu" + ($comfyCuda -replace '\.', '') } else { $TorchIndex = "https://download.pytorch.org/whl/cu128" }
}
Write-Host "Índice torch: $TorchIndex"

Step "2. Criar venv dedicado em $Venv"
if (-not (Test-Path (Join-Path $Venv "Scripts\python.exe"))) {
  $created = $false
  if ($PythonExe) { Write-Host "Criando venv com $PythonExe"; & $PythonExe -m venv $Venv; $created = ($LASTEXITCODE -eq 0) }
  elseif (Get-Command py -ErrorAction SilentlyContinue) { Write-Host "Criando venv com py -3.12"; & py -3.12 -m venv $Venv; $created = ($LASTEXITCODE -eq 0) }
  if (-not $created -and $comfyPy) { Write-Host "Criando venv com o python do ComfyUI: $comfyPy"; & $comfyPy -m venv $Venv; $created = ($LASTEXITCODE -eq 0) }
  if (-not $created -and (Get-Command python -ErrorAction SilentlyContinue)) { Write-Host "Criando venv com python"; & python -m venv $Venv; $created = ($LASTEXITCODE -eq 0) }
  if (-not $created) { Fail "venv não criado (instale Python 3.12 ou passe -PythonExe)" }
}
$py = Join-Path $Venv "Scripts\python.exe"
& $py -m pip install --upgrade pip wheel | Out-Null
& $py -c "import sys; print('venv python', sys.version.split()[0]); assert sys.version_info[:2] >= (3,10)"

Step "3. torch + torchvision CUDA (índice PyTorch; wheels Windows do PyPI são CPU-only)"
$torchSpec = if ($comfyTorch -and $comfyTorch -notmatch 'dev|rc|\+') { "torch==$comfyTorch" } else { "torch" }
Write-Host "pip install $torchSpec torchvision --index-url $TorchIndex"
& $py -m pip install $torchSpec torchvision --index-url $TorchIndex
if ($LASTEXITCODE -ne 0) {
  Write-Host "versão exata indisponível no índice; tentando a estável mais recente" -ForegroundColor Yellow
  & $py -m pip install torch torchvision --index-url $TorchIndex
  if ($LASTEXITCODE -ne 0) { Fail "torch CUDA não instalado" }
}
& $py -c "import torch; ok=torch.cuda.is_available(); print('torch', torch.__version__, 'cuda', torch.version.cuda, 'available', ok, 'arch', torch.cuda.get_arch_list()); assert ok, 'CUDA indisponível'; p=torch.cuda.get_device_properties(0); print('GPU', p.name, round(p.total_memory/2**30,1), 'GB', 'sm', p.major, p.minor); assert any('sm_120' in a or 'sm_12' in a for a in torch.cuda.get_arch_list()), 'build sem sm_120 (Blackwell)'"
if ($LASTEXITCODE -ne 0) { Fail "torch sem CUDA/sm_120 — use -TorchIndex https://download.pytorch.org/whl/cu128 (ou cu130)" }

Step "4. Dependências pinadas (requirements-r1ei.txt)"
& $py -m pip install -r (Join-Path $GT "tools\r1ei\requirements-r1ei.txt")
if ($LASTEXITCODE -ne 0) { Fail "requirements" }
& $py -c "import diffusers, transformers, peft, accelerate, safetensors, huggingface_hub; from diffusers import Flux2KleinPipeline; from transformers import Qwen3ForCausalLM; print('diffusers', diffusers.__version__, 'transformers', transformers.__version__, 'peft', peft.__version__, 'accelerate', accelerate.__version__, 'hf_hub', huggingface_hub.__version__); print('Flux2KleinPipeline + Qwen3ForCausalLM importáveis')"
if ($LASTEXITCODE -ne 0) { Fail "imports" }
& $py -m pip freeze | Out-File -Encoding utf8 (Join-Path $R1 "pip_freeze.txt")

Step "5. Clone do Easy-Insert no commit pinado $($Manifest.easy_insert.commit)"
$pin = $Manifest.easy_insert.commit
if (Get-Command git -ErrorAction SilentlyContinue) {
  if (-not (Test-Path (Join-Path $CloneDir ".git"))) { git clone --quiet https://github.com/huan-yin/Easy-Insert $CloneDir }
  git -C $CloneDir fetch --quiet origin
  git -C $CloneDir checkout --quiet $pin
  $head = (git -C $CloneDir rev-parse HEAD).Trim()
  if ($head -ne $pin) { Fail "commit do clone ($head) ≠ pin" }
} else {
  Write-Host "git não encontrado: baixando o zip do commit pinado" -ForegroundColor Yellow
  $zip = Join-Path $R1 "Easy-Insert-$pin.zip"
  Invoke-WebRequest -Uri "https://github.com/huan-yin/Easy-Insert/archive/$pin.zip" -OutFile $zip
  if (Test-Path $CloneDir) { Remove-Item -Recurse -Force $CloneDir }
  Expand-Archive -Path $zip -DestinationPath $R1 -Force
  Rename-Item -Path (Join-Path $R1 "Easy-Insert-$pin") -NewName "Easy-Insert"
  $head = "$pin (zip; sem .git)"
}
foreach ($f in @("utils.py", "inference_diffusers.py", "README.md", "LICENSE", "requirements.txt")) {
  $sha = (Get-FileHash -Algorithm SHA256 (Join-Path $CloneDir $f)).Hash.ToLower()
  if ($sha -ne $Manifest.easy_insert.files_sha256.$f) { Fail "$f do clone difere do pin ($sha)" }
}
Write-Host "clone ok: $head ; sha256 de utils.py/inference_diffusers.py/README/LICENSE/requirements conferidos"

Step "6. Download dos pesos (Hugging Face, revisões pinadas; NÃO baixa o single-file de 7,75 GB nem os jpg)"
$hf = Join-Path $Venv "Scripts\hf.exe"
if (-not (Test-Path $hf)) { $hf = Join-Path $Venv "Scripts\huggingface-cli.exe" }
if (-not $SkipDownload) {
  & $hf download $Manifest.base_model.repo --revision $Manifest.base_model.revision --local-dir $BaseDir --include "transformer/*" "text_encoder/*" "tokenizer/*" "vae/*" "scheduler/*" "model_index.json"
  if ($LASTEXITCODE -ne 0) { Fail "download da base" }
  & $hf download $Manifest.lora.repo --revision $Manifest.lora.revision --local-dir $LoraDir --include "*.safetensors" "*.json"
  if ($LASTEXITCODE -ne 0) { Fail "download do LoRA" }
}

Step "7. Verificação de integridade (sha256 do LoRA; tamanhos + sha256 da base)"
$loraFile = Join-Path $LoraDir $Manifest.lora.file
$lsha = (Get-FileHash -Algorithm SHA256 $loraFile).Hash.ToLower()
if ($lsha -ne $Manifest.lora.sha256) { Fail "LoRA sha256 divergente: $lsha" }
Write-Host "LoRA ok: $($Manifest.lora.file) $((Get-Item $loraFile).Length) bytes"
$totalBytes = 0
foreach ($p in $Manifest.base_model.files_needed_by_runner.PSObject.Properties) {
  $f = Join-Path $BaseDir ($p.Name -replace '/', '\')
  if (-not (Test-Path $f)) { Fail "arquivo ausente: $($p.Name)" }
  $len = (Get-Item $f).Length; $totalBytes += $len
  if ($len -ne $p.Value.size_bytes) { Fail "tamanho divergente: $($p.Name) ($len ≠ $($p.Value.size_bytes))" }
  if (-not $SkipBaseHash) {
    $h = (Get-FileHash -Algorithm SHA256 $f).Hash.ToLower()
    if ($h -ne $p.Value.sha256) { Fail "sha256 divergente: $($p.Name)" }
    Write-Host ("ok  {0,14:N0} bytes  sha256 ok  {1}" -f $len, $p.Name)
  } else { Write-Host ("ok  {0,14:N0} bytes  (sha não verificado)  {1}" -f $len, $p.Name) }
}
Write-Host ("Total verificado: {0:N2} GB" -f ($totalBytes/1GB))

Step "8. Entradas A/B e máscaras grosseiras de viabilidade + dry-run do runner (sem GPU)"
$inputs = Join-Path $R1 "inputs"; New-Item -ItemType Directory -Force -Path $inputs | Out-Null
if (-not $A -or -not $B) { Write-Host "A/B não informados: pulei máscaras e dry-run (passe -A e -B com as MESMAS imagens do klein4b_fp8_2ref_1mp)" -ForegroundColor Yellow }
else {
  Copy-Item $A (Join-Path $inputs "A.png") -Force; Copy-Item $B (Join-Path $inputs "B.png") -Force
  & $py (Join-Path $GT "tools\r1ei\make_masks.py") --image (Join-Path $inputs "A.png") --bbox $InsertBbox --out (Join-Path $inputs "A_insert_mask.png")
  & $py (Join-Path $GT "tools\r1ei\make_masks.py") --image (Join-Path $inputs "B.png") --bbox $RefBbox --out (Join-Path $inputs "B_ref_mask.png")
  & $py (Join-Path $GT "tools\r1ei\run_easy_insert.py") --a (Join-Path $inputs "A.png") --b (Join-Path $inputs "B.png") --insert-mask (Join-Path $inputs "A_insert_mask.png") --ref-mask (Join-Path $inputs "B_ref_mask.png") --out (Join-Path $R1 "dryrun\out.png") --model-dir $BaseDir --lora-dir $LoraDir --easy-insert-dir $CloneDir --dry-run
  if ($LASTEXITCODE -ne 0) { Fail "dry-run do runner" }
  Get-Content (Join-Path $R1 "dryrun\out.png.json") | Select-Object -First 60
}

Step "9. Resumo"
Write-Host "venv:        $Venv"
Write-Host "torch index: $TorchIndex"
Write-Host "base:        $BaseDir  (rev $($Manifest.base_model.revision))"
Write-Host "lora:        $loraFile  (rev $($Manifest.lora.revision))"
Write-Host "clone:       $CloneDir  ($head)"
Write-Host "log:         $Log"
Write-Host "PRONTO PARA O BENCHMARK (não executado). Próximo passo: bench_r1ei.ps1 — só depois de revisar este output." -ForegroundColor Green
Stop-Transcript | Out-Null
