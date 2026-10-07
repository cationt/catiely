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

# Python/Torch do ComfyUI Desktop (caminho padrão; ajuste se instalado em outro lugar)
$comfyPy = Join-Path $env:USERPROFILE "Documents\ComfyUI\.venv\Scripts\python.exe"
if (Test-Path $comfyPy) {
  $probe = @'
import json, sys
d = {"python": sys.version.split()[0]}
try:
    import torch; d["torch"]=torch.__version__; d["cuda"]=torch.version.cuda; d["cudnn"]=torch.backends.cudnn.version()
    d["cuda_available"]=torch.cuda.is_available()
    if torch.cuda.is_available():
        p=torch.cuda.get_device_properties(0); d["gpu"]=p.name; d["sm"]=f"{p.major}.{p.minor}"; d["vram_total_mb"]=round(p.total_memory/2**20)
        d["arch_list"]=torch.cuda.get_arch_list()
except Exception as e: d["torch_error"]=str(e)
for m in ["xformers","sageattention","triton","flash_attn","nunchaku","gguf"]:
    try:
        mod=__import__(m); d[m]=getattr(mod,"__version__","?")
    except Exception as e: d[m]=None
print(json.dumps(d))
'@
  $tmp = New-TemporaryFile
  Set-Content -Path $tmp -Value $probe -Encoding UTF8
  try { $out.comfy_python = (& $comfyPy -I $tmp.FullName) | ConvertFrom-Json } catch { $out.comfy_python_error = "$_" }
  Remove-Item $tmp -Force
} else { $out.comfy_python = "não encontrado em $comfyPy (ajuste o caminho)" }

$file = "inventory_$((Get-Date).ToString('yyyyMMdd_HHmmss')).json"
$out | ConvertTo-Json -Depth 6 | Set-Content -Path $file -Encoding UTF8
Write-Host "Inventário gravado em $file"
