# setup_r1ei.ps1 - prepara a medicao de viabilidade da rota R1-EI (FLUX.2-klein-base-4B + Easy-Insert) na maquina-alvo.
# NAO executa o benchmark. Faz: venv dedicado, torch CUDA (mesma versao do ComfyUI Desktop quando detectavel), deps pinadas,
# clone do Easy-Insert no commit pinado (autocrlf=false; provenance por blob OID/sha256 LF), download via snapshot_download (allow_patterns),
# verificacao de sha256/tamanhos, dry-run do runner. Arquivo salvo em UTF-8 COM BOM e so ASCII (Windows PowerShell 5.1).
# Uso (PowerShell, pasta do repo catiely):
#   powershell -ExecutionPolicy Bypass -File garment-transfer\tools\r1ei\setup_r1ei.ps1 -A <A.png> -B <B.png> [-W3Root C:\...\w3-measure]
param(
  [string]$W3Root = "C:\Users\henri\OneDrive\Documentos\w3-measure",
  [string]$A = "",
  [string]$B = "",
  [string]$InsertBbox = "0.25,0.18,0.75,0.72",   # bbox normalizada xyxy da regiao de insercao em A (torso) - so p/ viabilidade
  [string]$RefBbox = "0.20,0.15,0.80,0.75",      # bbox normalizada xyxy da peca em B - so p/ viabilidade
  [string]$PythonExe = "",                        # opcional: interpretador para criar o venv (padrao: py -3.12 -> python do ComfyUI -> python)
  [string]$TorchIndex = "",                       # opcional: ex. https://download.pytorch.org/whl/cu128 (padrao: deduzido do torch do ComfyUI)
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

Step "0. Espaco em disco e inventario minimo"
$drive = (Get-Item $W3Root).PSDrive.Name
$free = (Get-PSDrive $drive).Free / 1GB
Write-Host ("Disco {0}: {1:N1} GB livres (necessario ~ 15 GB modelos + ~ 6 GB venv/torch + 0.1 GB clone)" -f $drive, $free)
if (-not $SkipDownload -and $free -lt 20) { Fail "menos de 20 GB livres em $drive para baixar ~16 GB de pesos - libere espaco (checagem simples de seguranca, nao e restricao do projeto)" }
$os = Get-CimInstance Win32_OperatingSystem
Write-Host ("RAM fisica: {0:N1} GB | Commit limit (RAM+pagefile): {1:N1} GB" -f ($os.TotalVisibleMemorySize/1MB), ($os.TotalVirtualMemorySize/1MB))
try { nvidia-smi --query-gpu=name,memory.total,driver_version --format=csv } catch { Write-Host "nvidia-smi nao encontrado no PATH (ok)" -ForegroundColor Yellow }

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
} else { Write-Host "ComfyUI Desktop nao detectado (ok; torch vem do indice cu128)" -ForegroundColor Yellow }
if (-not $TorchIndex) {
  if ($comfyCuda) { $TorchIndex = "https://download.pytorch.org/whl/cu" + ($comfyCuda -replace '\.', '') } else { $TorchIndex = "https://download.pytorch.org/whl/cu128" }
}
Write-Host "Indice torch: $TorchIndex"

Step "2. Criar venv dedicado em $Venv"
if (-not (Test-Path (Join-Path $Venv "Scripts\python.exe"))) {
  $created = $false
  if ($PythonExe) { Write-Host "Criando venv com $PythonExe"; & $PythonExe -m venv $Venv; $created = ($LASTEXITCODE -eq 0) }
  elseif (Get-Command py -ErrorAction SilentlyContinue) { Write-Host "Criando venv com py -3.12"; & py -3.12 -m venv $Venv; $created = ($LASTEXITCODE -eq 0) }
  if (-not $created -and $comfyPy) { Write-Host "Criando venv com o python do ComfyUI: $comfyPy"; & $comfyPy -m venv $Venv; $created = ($LASTEXITCODE -eq 0) }
  if (-not $created -and (Get-Command python -ErrorAction SilentlyContinue)) { Write-Host "Criando venv com python"; & python -m venv $Venv; $created = ($LASTEXITCODE -eq 0) }
  if (-not $created) { Fail "venv nao criado (instale Python 3.12 ou passe -PythonExe)" }
}
$py = Join-Path $Venv "Scripts\python.exe"
& $py -m pip install --upgrade pip wheel | Out-Null
& $py -c "import sys; print('venv python', sys.version.split()[0]); assert sys.version_info[:2] >= (3,10)"

Step "3. torch + torchvision CUDA (indice PyTorch; wheels Windows do PyPI sao CPU-only)"
$torchSpec = if ($comfyTorch -and $comfyTorch -notmatch 'dev|rc|\+') { "torch==$comfyTorch" } else { "torch" }
Write-Host "pip install $torchSpec torchvision --index-url $TorchIndex"
& $py -m pip install $torchSpec torchvision --index-url $TorchIndex
if ($LASTEXITCODE -ne 0) {
  Write-Host "versao exata indisponivel no indice; tentando a estavel mais recente" -ForegroundColor Yellow
  & $py -m pip install torch torchvision --index-url $TorchIndex
  if ($LASTEXITCODE -ne 0) { Fail "torch CUDA nao instalado" }
}
& $py -c "import torch; ok=torch.cuda.is_available(); print('torch', torch.__version__, 'cuda', torch.version.cuda, 'available', ok, 'arch', torch.cuda.get_arch_list()); assert ok, 'CUDA indisponivel'; p=torch.cuda.get_device_properties(0); print('GPU', p.name, round(p.total_memory/2**30,1), 'GB', 'sm', p.major, p.minor); assert any('sm_120' in a or 'sm_12' in a for a in torch.cuda.get_arch_list()), 'build sem sm_120 (Blackwell)'"
if ($LASTEXITCODE -ne 0) { Fail "torch sem CUDA/sm_120 - use -TorchIndex https://download.pytorch.org/whl/cu128 (ou cu130)" }

Step "4. Dependencias pinadas (requirements-r1ei.txt)"
& $py -m pip install -r (Join-Path $GT "tools\r1ei\requirements-r1ei.txt")
if ($LASTEXITCODE -ne 0) { Fail "requirements" }
& $py -c "import diffusers, transformers, peft, accelerate, safetensors, huggingface_hub; from diffusers import Flux2KleinPipeline; from transformers import Qwen3ForCausalLM; print('diffusers', diffusers.__version__, 'transformers', transformers.__version__, 'peft', peft.__version__, 'accelerate', accelerate.__version__, 'hf_hub', huggingface_hub.__version__); print('Flux2KleinPipeline + Qwen3ForCausalLM importaveis')"
if ($LASTEXITCODE -ne 0) { Fail "imports" }
& $py -m pip freeze | Out-File -Encoding utf8 (Join-Path $R1 "pip_freeze.txt")

Step "5. Clone do Easy-Insert no commit pinado $($Manifest.easy_insert.commit) (sem conversao de EOL; provenance por blob OID + sha256 LF)"
$pin = $Manifest.easy_insert.commit
if (Get-Command git -ErrorAction SilentlyContinue) {
  if (-not (Test-Path (Join-Path $CloneDir ".git"))) { git -c core.autocrlf=false clone --quiet https://github.com/huan-yin/Easy-Insert $CloneDir }
  git -C $CloneDir config core.autocrlf false
  git -C $CloneDir fetch --quiet origin
  git -C $CloneDir checkout --quiet $pin
  git -C $CloneDir checkout --quiet -- .    # re-materializa o working tree com autocrlf=false (LF)
  $head = (git -C $CloneDir rev-parse HEAD).Trim()
  if ($head -ne $pin) { Fail "commit do clone ($head) != pin" }
} else {
  Write-Host "git nao encontrado: baixando o zip do commit pinado" -ForegroundColor Yellow
  $zip = Join-Path $R1 "Easy-Insert-$pin.zip"
  Invoke-WebRequest -Uri "https://github.com/huan-yin/Easy-Insert/archive/$pin.zip" -OutFile $zip
  if (Test-Path $CloneDir) { Remove-Item -Recurse -Force $CloneDir }
  Expand-Archive -Path $zip -DestinationPath $R1 -Force
  Rename-Item -Path (Join-Path $R1 "Easy-Insert-$pin") -NewName "Easy-Insert"
  $head = "$pin (zip; sem .git)"
}
& $py (Join-Path $GT "tools\r1ei\verify_provenance.py") --clone-dir $CloneDir --json-out (Join-Path $R1 "provenance_easy_insert.json")
if ($LASTEXITCODE -ne 0) { Fail "provenance do clone divergente (ver provenance_easy_insert.json)" }
Write-Host "clone ok: $head"

Step "6. Download dos pesos (huggingface_hub.snapshot_download com allow_patterns e revisoes pinadas; NAO baixa o single-file de 7,75 GB nem os jpg)"
if (-not $SkipDownload) {
  & $py (Join-Path $GT "tools\r1ei\hf_fetch.py") --what base --dest $BaseDir
  if ($LASTEXITCODE -ne 0) { Fail "download/verificacao da base" }
  & $py (Join-Path $GT "tools\r1ei\hf_fetch.py") --what lora --dest $LoraDir
  if ($LASTEXITCODE -ne 0) { Fail "download/verificacao do LoRA" }
}

Step "7. Verificacao de integridade (sha256 do LoRA; tamanhos + sha256 da base)"
$shaFlag = @(); if (-not $SkipBaseHash) { $shaFlag = @("--verify-sha") }
& $py (Join-Path $GT "tools\r1ei\hf_fetch.py") --what lora --dest $LoraDir --verify-only --verify-sha --json-out (Join-Path $R1 "verify_lora.json")
if ($LASTEXITCODE -ne 0) { Fail "LoRA divergente (ver verify_lora.json)" }
& $py (Join-Path $GT "tools\r1ei\hf_fetch.py") --what base --dest $BaseDir --verify-only @shaFlag --json-out (Join-Path $R1 "verify_base.json")
if ($LASTEXITCODE -ne 0) { Fail "base divergente (ver verify_base.json)" }
$loraFile = Join-Path $LoraDir $Manifest.lora.file

Step "8. Entradas A/B e mascaras grosseiras de viabilidade + dry-run do runner (sem GPU)"
$inputs = Join-Path $R1 "inputs"; New-Item -ItemType Directory -Force -Path $inputs | Out-Null
if (-not $A -or -not $B) { Write-Host "A/B nao informados: pulei mascaras e dry-run (passe -A e -B com as MESMAS imagens do klein4b_fp8_2ref_1mp)" -ForegroundColor Yellow }
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
Write-Host "PRONTO PARA O BENCHMARK (nao executado). Proximo passo: bench_r1ei.ps1 - so depois de revisar este output." -ForegroundColor Green
Stop-Transcript | Out-Null
