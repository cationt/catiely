# setup_r3.ps1 - prepara a medicao de viabilidade da rota R3 (FASHN VTON 1.5, modos segfree e masked) na maquina-alvo.
# NAO executa o benchmark. Faz: venv dedicado (W3Root\r3\.venv), torch CUDA (mesma versao do ComfyUI Desktop quando detectavel),
# deps pinadas, clone pinado do fashn-vton-1.5 (autocrlf=false; provenance por blob OID + sha256 LF), instalacao --no-deps dos pacotes
# upstream, download deterministico dos pesos (hf_hub_download com revision), sha256, verificacao do CUDAExecutionProvider do ONNX Runtime,
# dry-run e smoke test (1 passo) do runner. Arquivo em ASCII puro + BOM UTF-8 (Windows PowerShell 5.1).
# Uso (PowerShell, pasta do repo catiely):
#   powershell -ExecutionPolicy Bypass -File garment-transfer\tools\r3_fashn\setup_r3.ps1 -A <A.png> -B <B.png> -Category tops -GarmentPhotoType model [-W3Root C:\...\w3-measure]
param(
  [string]$W3Root = "C:\Users\henri\OneDrive\Documentos\w3-measure",
  [string]$A = "",
  [string]$B = "",
  [string]$Category = "tops",                   # baseline: subtarefa nativa, nao transferencia integral do biquini two-piece
  [string]$GarmentPhotoType = "model",          # B vestida em outra pessoa
  [string]$PythonExe = "",                      # opcional: interpretador para criar o venv (padrao: py -3.12 -> python do ComfyUI -> python)
  [string]$TorchIndex = "",                     # opcional: ex. https://download.pytorch.org/whl/cu130 (padrao: deduzido do torch do ComfyUI)
  [switch]$SkipDownload,
  [switch]$SkipSmoke
)
$ErrorActionPreference = "Stop"
$RepoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..\..\..")).Path          # catiely/
$GT = Join-Path $RepoRoot "garment-transfer"
$R3 = Join-Path $W3Root "r3"
$Venv = Join-Path $R3 ".venv"
$WeightsDir = Join-Path $W3Root "models\fashn-vton-1.5"
$CloneDir = Join-Path $R3 "fashn-vton-1.5"
$Tools = Join-Path $GT "tools\r3_fashn"
$Manifest = Get-Content (Join-Path $Tools "r3_manifest.json") -Raw | ConvertFrom-Json
$Log = Join-Path $R3 ("setup_" + (Get-Date -Format "yyyyMMddTHHmmss") + ".log")
New-Item -ItemType Directory -Force -Path $R3, $WeightsDir | Out-Null
Start-Transcript -Path $Log -Force | Out-Null
function Step($m) { Write-Host ("`n=== " + $m + " ===") -ForegroundColor Cyan }
function Fail($m) { Write-Host ("FALHA: " + $m) -ForegroundColor Red; Stop-Transcript | Out-Null; exit 1 }
if ($Category -ne "tops" -or $GarmentPhotoType -ne "model") { Fail "baseline R3 exige tops/model: B e um biquini two-piece; dois passes sao outra arquitetura" }
if (-not $A -or -not $B) { Fail "informe -A e -B: mesmas entradas do Klein/R1-EI" }
$expected = Get-Content (Join-Path $Tools "expected_inputs.json") -Raw | ConvertFrom-Json
if ((Get-FileHash -LiteralPath $A -Algorithm SHA256).Hash.ToLowerInvariant() -ne $expected.inputs_sha256.person -or
    (Get-FileHash -LiteralPath $B -Algorithm SHA256).Hash.ToLowerInvariant() -ne $expected.inputs_sha256.garment) { Fail "SHA256 de A/B diverge do Klein/R1-EI (expected_inputs.json)" }

Step "0. Espaco em disco e inventario minimo"
$drive = (Get-Item $W3Root).PSDrive.Name
$free = (Get-PSDrive $drive).Free / 1GB
Write-Host ("Disco {0}: {1:N1} GB livres (necessario ~ 2.6 GB pesos + ~ 5 GB venv/torch)" -f $drive, $free)
if (-not $SkipDownload -and $free -lt 10) { Fail "menos de 10 GB livres em $drive - libere espaco (checagem simples de seguranca, nao e restricao do projeto)" }
$os = Get-CimInstance Win32_OperatingSystem
Write-Host ("RAM fisica: {0:N1} GB | Commit limit (RAM+pagefile): {1:N1} GB" -f ($os.TotalVisibleMemorySize/1MB), ($os.TotalVirtualMemorySize/1MB))
try { nvidia-smi --query-gpu=name,memory.total,driver_version --format=csv } catch { Write-Host "nvidia-smi nao encontrado no PATH (ok)" -ForegroundColor Yellow }

Step "1. Detectar Python do ComfyUI Desktop (para casar torch/CUDA)"
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
} else { Write-Host "ComfyUI Desktop nao detectado (ok; torch vem do indice cu130)" -ForegroundColor Yellow }
if (-not $TorchIndex) {
  if ($comfyCuda) { $TorchIndex = "https://download.pytorch.org/whl/cu" + ($comfyCuda -replace '\.', '') } else { $TorchIndex = "https://download.pytorch.org/whl/cu130" }
}
Write-Host "Indice torch: $TorchIndex"
$cudaMajor = if ($comfyCuda) { ($comfyCuda -split '\.')[0] } else { "13" }

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
& $py -c "import sys; print('venv python', sys.version.split()[0]); assert sys.version_info[:2] >= (3,11), 'onnxruntime-gpu 1.30 exige Python >= 3.11'"
if ($LASTEXITCODE -ne 0) { Fail "python do venv incompativel" }

Step "3. torch + torchvision CUDA (indice PyTorch; wheels Windows do PyPI sao CPU-only)"
$torchSpec = if ($comfyTorch -and $comfyTorch -notmatch 'dev|rc|\+') { "torch==$comfyTorch" } else { "torch" }
Write-Host "pip install $torchSpec torchvision --index-url $TorchIndex"
& $py -m pip install $torchSpec torchvision --index-url $TorchIndex
if ($LASTEXITCODE -ne 0) {
  Write-Host "versao exata indisponivel no indice; tentando a estavel mais recente" -ForegroundColor Yellow
  & $py -m pip install torch torchvision --index-url $TorchIndex
  if ($LASTEXITCODE -ne 0) { Fail "torch CUDA nao instalado" }
}
& $py -c "import torch; ok=torch.cuda.is_available(); print('torch', torch.__version__, 'cuda', torch.version.cuda, 'cudnn', torch.backends.cudnn.version(), 'available', ok, 'arch', torch.cuda.get_arch_list()); assert ok, 'CUDA indisponivel'; p=torch.cuda.get_device_properties(0); print('GPU', p.name, round(p.total_memory/2**30,1), 'GB', 'sm', p.major, p.minor); assert any('sm_120' in a or 'sm_12' in a for a in torch.cuda.get_arch_list()), 'build sem sm_120 (Blackwell)'"
if ($LASTEXITCODE -ne 0) { Fail "torch sem CUDA/sm_120 - use -TorchIndex https://download.pytorch.org/whl/cu130 (ou cu128)" }
$torchCuda = (& $py -c "import torch; print(torch.version.cuda.split('.')[0])").Trim()

Step "4. Dependencias pinadas (requirements-r3.txt) + pacotes upstream com --no-deps"
$reqFile = Join-Path $Tools "requirements-r3.txt"
if ($torchCuda -eq "12") {
  Write-Host "torch e CUDA 12.x: onnxruntime-gpu 1.30.0 (build CUDA 13.0) NAO casa; usando o fallback 1.26.0 (build CUDA 12.8) do manifesto" -ForegroundColor Yellow
  $reqTmp = Join-Path $R3 "requirements-r3.cuda12.txt"
  (Get-Content $reqFile) -replace '^onnxruntime-gpu==1\.30\.0', 'onnxruntime-gpu==1.26.0' | Set-Content -Encoding ascii $reqTmp
  $reqFile = $reqTmp
}
& $py -m pip install -r $reqFile
if ($LASTEXITCODE -ne 0) { Fail "requirements" }
& $py -m pip install --no-deps fashn-human-parser==0.1.1
if ($LASTEXITCODE -ne 0) { Fail "fashn-human-parser" }

Step "5. Clone do fashn-vton-1.5 no commit pinado $($Manifest.code_repos.vton.commit) (sem conversao de EOL) + instalacao --no-deps + provenance"
$pin = $Manifest.code_repos.vton.commit
if (Get-Command git -ErrorAction SilentlyContinue) {
  if (-not (Test-Path (Join-Path $CloneDir ".git"))) { git -c core.autocrlf=false clone --quiet https://github.com/fashn-AI/fashn-vton-1.5 $CloneDir }
  git -C $CloneDir config core.autocrlf false
  git -C $CloneDir fetch --quiet origin
  git -C $CloneDir checkout --quiet $pin
  git -C $CloneDir checkout --quiet -- .
  $head = (git -C $CloneDir rev-parse HEAD).Trim()
  if ($head -ne $pin) { Fail "commit do clone ($head) != pin" }
} else {
  Write-Host "git nao encontrado: baixando o zip do commit pinado" -ForegroundColor Yellow
  $zip = Join-Path $R3 "fashn-vton-1.5-$pin.zip"
  Invoke-WebRequest -Uri "https://github.com/fashn-AI/fashn-vton-1.5/archive/$pin.zip" -OutFile $zip
  if (Test-Path $CloneDir) { Remove-Item -Recurse -Force $CloneDir }
  Expand-Archive -Path $zip -DestinationPath $R3 -Force
  Rename-Item -Path (Join-Path $R3 "fashn-vton-1.5-$pin") -NewName "fashn-vton-1.5"
  $head = "$pin (zip; sem .git)"
}
& $py (Join-Path $Tools "verify_provenance.py") --clone-dir $CloneDir --repo vton --json-out (Join-Path $R3 "provenance_vton.json")
if ($LASTEXITCODE -ne 0) { Fail "provenance do clone divergente (ver provenance_vton.json)" }
& $py -m pip install --no-deps $CloneDir
if ($LASTEXITCODE -ne 0) { Fail "pip install fashn-vton (clone)" }
& $py -c "import torch; import onnxruntime as ort; ort.preload_dlls(); from onnxruntime.capi import build_and_package_info as b; import fashn_vton, fashn_human_parser, transformers, cv2, einops, matplotlib, numpy; print('fashn_vton', fashn_vton.__version__, 'parser', fashn_human_parser.__version__, 'ort', ort.__version__, 'ort_cuda_build', getattr(b,'cuda_version',None), 'providers', ort.get_available_providers(), 'transformers', transformers.__version__, 'cv2', cv2.__version__, 'numpy', numpy.__version__)"
if ($LASTEXITCODE -ne 0) { Fail "imports (torch -> onnxruntime -> fashn_vton)" }
& $py -m pip freeze | Out-File -Encoding utf8 (Join-Path $R3 "pip_freeze.txt")
Write-Host "clone ok: $head"

Step "6. Download deterministico dos pesos (hf_hub_download com revision pinada; parser humano tambem LOCAL - nada fica para o benchmark)"
if (-not $SkipDownload) {
  & $py (Join-Path $Tools "fetch_weights.py") --weights-dir $WeightsDir
  if ($LASTEXITCODE -ne 0) { Fail "download/verificacao dos pesos" }
}

Step "7. Verificacao de integridade (tamanhos + sha256 de todos os pesos)"
& $py (Join-Path $Tools "fetch_weights.py") --weights-dir $WeightsDir --verify-only --verify-sha --json-out (Join-Path $R3 "verify_weights.json")
if ($LASTEXITCODE -ne 0) { Fail "pesos divergentes (ver verify_weights.json)" }

Step "8. ONNX Runtime: CUDAExecutionProvider efetivo (sem fallback silencioso para CPU)"
$yolox = Join-Path $WeightsDir "dwpose\yolox_l.onnx"
& $py -c "import sys, torch, numpy as np, onnxruntime as ort; ort.preload_dlls(); s = ort.InferenceSession(sys.argv[1], providers=['CUDAExecutionProvider'], provider_options=[{'device_id':'0'}]); p = s.get_providers(); print('providers efetivos:', p); x = np.zeros((1,3,640,640), np.float32); import time; t=time.perf_counter(); s.run(None, {s.get_inputs()[0].name: x}); print('yolox 640 ok em %.3f s' % (time.perf_counter()-t)); assert p[0] == 'CUDAExecutionProvider', 'ORT caiu para CPU: ' + str(p)" $yolox
if ($LASTEXITCODE -ne 0) { Fail "CUDAExecutionProvider nao efetivo (ver mensagens acima; conferir torch\lib DLLs CUDA/cuDNN e build do onnxruntime-gpu)" }
$eap = $ErrorActionPreference; $ErrorActionPreference = "Continue"   # stderr de comando nativo redirecionado NAO pode virar erro terminante (PS 5.1)
& $py -c "import sys, torch, onnxruntime as ort; ort.preload_dlls(); sys.stderr = sys.stdout; ort.print_debug_info()" 2>&1 | Out-File -Encoding utf8 (Join-Path $R3 "ort_debug_info.txt")
$ErrorActionPreference = $eap

Step "9. Entradas A/B verificadas + subtarefa tops + dry-run e smoke de ambos os modos"
$inputs = Join-Path $R3 "inputs"; New-Item -ItemType Directory -Force -Path $inputs | Out-Null
Copy-Item $A (Join-Path $inputs "A.png") -Force; Copy-Item $B (Join-Path $inputs "B.png") -Force
$decisionPath = Join-Path $inputs "inputs_decision.json"
$decision = @{ category = $Category; garment_photo_type = $GarmentPhotoType; scope = $expected.scope; decided_on = (Get-Date -Format "yyyy-MM-dd"); rule = "B = biquini preto two-piece em outra pessoa. tops = subtarefa nativa de custo, nao transferencia integral; tops -> bottoms = arquitetura separada; one-pieces nao autorizado como substituto"; A = (Join-Path $inputs "A.png"); B = (Join-Path $inputs "B.png"); source_A = (Resolve-Path -LiteralPath $A).Path; source_B = (Resolve-Path -LiteralPath $B).Path; inputs_sha256 = @{ person = (Get-FileHash -LiteralPath (Join-Path $inputs "A.png") -Algorithm SHA256).Hash.ToLowerInvariant(); garment = (Get-FileHash -LiteralPath (Join-Path $inputs "B.png") -Algorithm SHA256).Hash.ToLowerInvariant() } }
$decision | ConvertTo-Json -Depth 4 | Out-File -Encoding utf8 $decisionPath
& $py (Join-Path $Tools "verify_inputs.py") --person (Join-Path $inputs "A.png") --garment (Join-Path $inputs "B.png") --decision $decisionPath
if ($LASTEXITCODE -ne 0) { Fail "A/B copiadas ou decisao divergentes" }
$common = @("--person", (Join-Path $inputs "A.png"), "--garment", (Join-Path $inputs "B.png"), "--weights-dir", $WeightsDir, "--category", $Category, "--garment-photo-type", $GarmentPhotoType, "--inputs-decision", $decisionPath)
& $py (Join-Path $Tools "run_fashn_vton.py") @common --segmentation-free --out (Join-Path $R3 "dryrun\segfree.png") --dry-run
if ($LASTEXITCODE -ne 0) { Fail "dry-run (segfree)" }
& $py (Join-Path $Tools "run_fashn_vton.py") @common --masked --out (Join-Path $R3 "dryrun\masked.png") --dry-run
if ($LASTEXITCODE -ne 0) { Fail "dry-run (masked)" }
if (-not $SkipSmoke) {
  & $py (Join-Path $Tools "run_fashn_vton.py") @common --segmentation-free --out (Join-Path $R3 "smoke\segfree_1step.png") --smoke
  if ($LASTEXITCODE -ne 0) { Fail "smoke test (1 passo) falhou - ver smoke\segfree_1step.png.json (providers, versoes, erro)" }
  Get-Content (Join-Path $R3 "smoke\segfree_1step.png.json") | ConvertFrom-Json | Select-Object verdict, dtype, onnx_providers, phases, torch_vram, geometry | ConvertTo-Json -Depth 4
  & $py (Join-Path $Tools "run_fashn_vton.py") @common --masked --out (Join-Path $R3 "smoke\masked_1step.png") --smoke
  if ($LASTEXITCODE -ne 0) { Fail "smoke test masked (1 passo) falhou - ver smoke\masked_1step.png.json" }
  Get-Content (Join-Path $R3 "smoke\masked_1step.png.json") | ConvertFrom-Json | Select-Object verdict, dtype, onnx_providers, phases, torch_vram, geometry | ConvertTo-Json -Depth 4
}

Step "10. Resumo"
Write-Host ("venv:          " + $Venv)
Write-Host ("pesos:         " + $WeightsDir + "  (verify_weights.json)")
Write-Host ("clone:         " + $CloneDir + "  (provenance_vton.json)")
Write-Host ("ORT:           ort_debug_info.txt em " + $R3)
Write-Host ("entradas:      " + $inputs + "  (inputs_decision.json)")
Write-Host ("log:           " + $Log)
if ($SkipSmoke) { Write-Host "`nPREPARACAO PARCIAL: smoke segfree/masked pendente; execute novamente sem -SkipSmoke." -ForegroundColor Yellow }
else { Write-Host "`nPRONTO PARA O BENCHMARK (nao executado). Revise o output acima e so entao rode bench_r3.ps1." -ForegroundColor Green }
Stop-Transcript | Out-Null
