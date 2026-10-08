# inventory_windows.ps1 — Inventário reproduzível da máquina-alvo (Windows 11, RTX 5070, ~16 GB RAM).
# Executar em PowerShell (não precisa de admin). Saída: inventory_<data>.json no diretório atual.
# Objetivo: toda medição de viabilidade deve vir acompanhada deste inventário (nível de evidência MEDIDO NO HARDWARE-ALVO).

$ErrorActionPreference = "Continue"
$out = @{}
$out.timestamp_utc = (Get-Date).ToUniversalTime().ToString("o")

# SO
$os = Get-CimInstance Win32_OperatingSystem
$out.os = @{
  caption = $os.Caption; version = $os.Version; build = $os.BuildNumber
  total_visible_memory_mb = [math]::Round($os.TotalVisibleMemorySize/1024,1)
  free_physical_memory_mb = [math]::Round($os.FreePhysicalMemory/1024,1)
  total_virtual_memory_mb = [math]::Round($os.TotalVirtualMemorySize/1024,1)
  free_virtual_memory_mb  = [math]::Round($os.FreeVirtualMemory/1024,1)
}

# CPU / RAM física
$cpu = Get-CimInstance Win32_Processor | Select-Object -First 1
$out.cpu = @{ name = $cpu.Name; cores = $cpu.NumberOfCores; threads = $cpu.NumberOfLogicalProcessors; max_clock_mhz = $cpu.MaxClockSpeed }
$out.ram_modules = @(Get-CimInstance Win32_PhysicalMemory | ForEach-Object { @{ capacity_mb = [math]::Round($_.Capacity/1MB); speed_mts = $_.Speed; part = $_.PartNumber } })

# Pagefile (configuração e uso atual)
$out.pagefile_setting = @(Get-CimInstance Win32_PageFileSetting | ForEach-Object { @{ name=$_.Name; initial_mb=$_.InitialSize; maximum_mb=$_.MaximumSize } })
$out.pagefile_usage   = @(Get-CimInstance Win32_PageFileUsage   | ForEach-Object { @{ name=$_.Name; allocated_mb=$_.AllocatedBaseSize; current_usage_mb=$_.CurrentUsage; peak_usage_mb=$_.PeakUsage } })
$cs = Get-CimInstance Win32_ComputerSystem
$out.automatic_managed_pagefile = $cs.AutomaticManagedPagefile

# Memória comprometida agora (Performance Counters)
try {
  $out.committed_bytes_mb = [math]::Round((Get-Counter '\Memory\Committed Bytes').CounterSamples[0].CookedValue/1MB,1)
  $out.commit_limit_mb    = [math]::Round((Get-Counter '\Memory\Commit Limit').CounterSamples[0].CookedValue/1MB,1)
  $out.available_mb       = [math]::Round((Get-Counter '\Memory\Available MBytes').CounterSamples[0].CookedValue,1)
} catch { $out.perf_counters_error = "$_" }

# Discos (tipo, espaço livre) — espaço para pesos (dezenas de GB) e pagefile
$out.volumes = @(Get-Volume | Where-Object { $_.DriveLetter } | ForEach-Object { @{ letter="$($_.DriveLetter)"; fs=$_.FileSystem; size_gb=[math]::Round($_.Size/1GB,1); free_gb=[math]::Round($_.SizeRemaining/1GB,1) } })
$out.physical_disks = @(Get-PhysicalDisk | ForEach-Object { @{ name=$_.FriendlyName; media=$_.MediaType; bus=$_.BusType; size_gb=[math]::Round($_.Size/1GB,1) } })

# GPU (WMI + nvidia-smi)
$out.gpus_wmi = @(Get-CimInstance Win32_VideoController | ForEach-Object { @{ name=$_.Name; driver=$_.DriverVersion; adapter_ram_mb_wmi=[math]::Round($_.AdapterRAM/1MB) } })
try {
  $smi = & nvidia-smi --query-gpu=name,driver_version,memory.total,memory.used,pcie.link.gen.current,pcie.link.width.current,compute_cap --format=csv,noheader 2>$null
  $out.nvidia_smi = $smi
} catch { $out.nvidia_smi = "nvidia-smi indisponível" }

# NVIDIA: política de fallback para memória do sistema (afeta OOM vs. lentidão)
try {
  $out.nvidia_sysmem_fallback_hint = "Verificar em NVIDIA Control Panel > Manage 3D Settings > CUDA - Sysmem Fallback Policy (não exposto por WMI)"
} catch {}

# Processos que mais consomem memória agora (baseline antes da execução)
$out.top_processes_by_ws = @(Get-Process | Sort-Object WorkingSet64 -Descending | Select-Object -First 15 | ForEach-Object { @{ name=$_.ProcessName; ws_mb=[math]::Round($_.WorkingSet64/1MB); private_mb=[math]::Round($_.PrivateMemorySize64/1MB) } })

# ---------------------------------------------------------------------------
# Detecção robusta de instalações do ComfyUI (Desktop novo, Desktop legado, portable, manual).
# Não assume um único caminho. Registra TODAS as encontradas e qual foi usada para a sondagem.
# Override manual: $env:COMFY_PYTHON = "C:\caminho\para\python.exe"
# ---------------------------------------------------------------------------
$candidates = New-Object System.Collections.Generic.List[object]
function Add-Candidate($label, $pythonPath, $comfyRoot) {
  if ($pythonPath -and (Test-Path $pythonPath)) {
    $candidates.Add(@{ label = $label; python = $pythonPath; comfy_root = $comfyRoot; exists = $true })
  } else {
    $candidates.Add(@{ label = $label; python = "$pythonPath"; comfy_root = "$comfyRoot"; exists = $false })
  }
}
# 0) override explícito
if ($env:COMFY_PYTHON) { Add-Candidate "env:COMFY_PYTHON" $env:COMFY_PYTHON (Split-Path (Split-Path (Split-Path $env:COMFY_PYTHON))) }
# 1) Comfy-Desktop (app novo, 2026): %LOCALAPPDATA%\Comfy-Desktop\ComfyUI-Installs\<nome>\ComfyUI\.venv\Scripts\python.exe
$installsRoot = Join-Path $env:LOCALAPPDATA "Comfy-Desktop\ComfyUI-Installs"
if (Test-Path $installsRoot) {
  Get-ChildItem -Path $installsRoot -Directory -ErrorAction SilentlyContinue | ForEach-Object {
    $root = Join-Path $_.FullName "ComfyUI"
    Add-Candidate "Comfy-Desktop/ComfyUI-Installs/$($_.Name)" (Join-Path $root ".venv\Scripts\python.exe") $root
    # variante sem subpasta ComfyUI
    Add-Candidate "Comfy-Desktop/ComfyUI-Installs/$($_.Name) (flat)" (Join-Path $_.FullName ".venv\Scripts\python.exe") $_.FullName
  }
}
# 2) Comfy-Desktop: configuração do app aponta o basePath (ler JSON se existir)
foreach ($cfg in @((Join-Path $env:APPDATA "Comfy-Desktop\config.json"), (Join-Path $env:APPDATA "ComfyUI\config.json"), (Join-Path $env:APPDATA "ComfyUI\extra_models_config.yaml"))) {
  if (Test-Path $cfg) {
    try {
      $txt = Get-Content $cfg -Raw
      $m = [regex]::Matches($txt, '([A-Za-z]:\\[^"\r\n]*?ComfyUI[^"\r\n]*)')
      foreach ($mm in $m) {
        $bp = $mm.Groups[1].Value.TrimEnd('\')
        Add-Candidate "config:$([System.IO.Path]::GetFileName($cfg))" (Join-Path $bp ".venv\Scripts\python.exe") $bp
      }
    } catch {}
  }
}
# 3) Desktop legado (Comfy-Org/desktop, arquivado 2026-06): %USERPROFILE%\Documents\ComfyUI\.venv
Add-Candidate "desktop-legado/Documents" (Join-Path $env:USERPROFILE "Documents\ComfyUI\.venv\Scripts\python.exe") (Join-Path $env:USERPROFILE "Documents\ComfyUI")
# 4) Portable: <raiz>\python_embeded\python.exe ao lado de ComfyUI\
foreach ($drive in (Get-PSDrive -PSProvider FileSystem | Select-Object -ExpandProperty Root)) {
  foreach ($guess in @("ComfyUI_windows_portable", "ComfyUI", "AI\ComfyUI_windows_portable")) {
    $pp = Join-Path $drive (Join-Path $guess "python_embeded\python.exe")
    if (Test-Path $pp) { Add-Candidate "portable:$drive$guess" $pp (Join-Path $drive (Join-Path $guess "ComfyUI")) }
  }
}
# 5) Busca rasa em LocalAppData e no perfil por ComfyUI\.venv\Scripts\python.exe (profundidade limitada para não demorar)
foreach ($base in @($env:LOCALAPPDATA, $env:USERPROFILE)) {
  try {
    Get-ChildItem -Path $base -Directory -Depth 3 -Filter "ComfyUI" -ErrorAction SilentlyContinue | ForEach-Object {
      $pp = Join-Path $_.FullName ".venv\Scripts\python.exe"
      if ((Test-Path $pp) -and -not ($candidates | Where-Object { $_.python -eq $pp })) { Add-Candidate "busca:$($_.FullName)" $pp $_.FullName }
    }
  } catch {}
}
$out.comfy_candidates = @($candidates)
$found = $candidates | Where-Object { $_.exists } | Select-Object -First 1
if ($found) {
  $out.comfy_used = $found
  # versão do ComfyUI (comfyui_version.py ou pyproject.toml) e lista de custom nodes
  try {
    $verFile = Join-Path $found.comfy_root "comfyui_version.py"
    if (Test-Path $verFile) { $out.comfy_version = (Get-Content $verFile -Raw) -replace '\s+', ' ' }
    $pyproj = Join-Path $found.comfy_root "pyproject.toml"
    if (Test-Path $pyproj) { $out.comfy_pyproject_version = ((Select-String -Path $pyproj -Pattern '^version\s*=\s*"(.+)"').Matches | Select-Object -First 1).Groups[1].Value }
    $cn = Join-Path $found.comfy_root "custom_nodes"
    if (Test-Path $cn) { $out.custom_nodes = @(Get-ChildItem -Path $cn -Directory | Select-Object -ExpandProperty Name) }
    $models = Join-Path $found.comfy_root "models"
    if (Test-Path $models) {
      $out.models_dir_size_gb = [math]::Round(((Get-ChildItem -Path $models -Recurse -File -ErrorAction SilentlyContinue | Measure-Object Length -Sum).Sum)/1GB, 1)
    }
  } catch { $out.comfy_meta_error = "$_" }
  $probe = @'
import json, sys, platform
d = {"python": sys.version.split()[0], "executable": sys.executable, "platform": platform.platform()}
try:
    import torch; d["torch"]=torch.__version__; d["cuda"]=torch.version.cuda; d["cudnn"]=torch.backends.cudnn.version()
    d["cuda_available"]=torch.cuda.is_available()
    if torch.cuda.is_available():
        p=torch.cuda.get_device_properties(0); d["gpu"]=p.name; d["sm"]=f"{p.major}.{p.minor}"; d["vram_total_mb"]=round(p.total_memory/2**20)
        d["arch_list"]=torch.cuda.get_arch_list()
        try:
            free,total=torch.cuda.mem_get_info(); d["vram_free_mb_now"]=round(free/2**20)
        except Exception as e: d["mem_get_info_error"]=str(e)
except Exception as e: d["torch_error"]=str(e)
for m in ["xformers","sageattention","triton","flash_attn","nunchaku","gguf","comfy_aimdo","comfy_kitchen","onnxruntime","psutil","pynvml"]:
    try:
        mod=__import__(m); d[m]=getattr(mod,"__version__","present")
    except Exception as e: d[m]=None
print(json.dumps(d))
'@
  $tmp = New-TemporaryFile
  Set-Content -Path $tmp -Value $probe -Encoding UTF8
  try { $out.comfy_python = (& $found.python -I $tmp.FullName) | ConvertFrom-Json } catch { $out.comfy_python_error = "$_" }
  Remove-Item $tmp -Force
} else {
  $out.comfy_used = $null
  $out.comfy_python = "nenhuma instalação encontrada; defina `$env:COMFY_PYTHON com o caminho do python.exe do ComfyUI"
}

$file = "inventory_$((Get-Date).ToString('yyyyMMdd_HHmmss')).json"
$out | ConvertTo-Json -Depth 6 | Set-Content -Path $file -Encoding UTF8
Write-Host "Inventário gravado em $file"
