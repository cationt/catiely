param(
    [ValidateSet('Plan', 'Verify', 'Generate')][string]$Mode = 'Plan',
    [string]$W3Root = (Join-Path $env:USERPROFILE 'OneDrive\Documentos\w3-measure'),
    [string]$Core = (Join-Path $env:LOCALAPPDATA 'Comfy-Desktop\ComfyUI-Installs\ComfyUI\ComfyUI'),
    [string]$Shared = (Join-Path $env:LOCALAPPDATA 'Comfy-Desktop\ComfyUI-Shared'),
    [string]$Out = '',
    [int]$Port = 8197,
    [int]$DeadlineSeconds = 3600
)
$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest
$python = Join-Path $Core '.venv\Scripts\python.exe'
if (-not (Test-Path -LiteralPath $python -PathType Leaf)) { throw "Missing pinned ComfyUI Python: $python" }
$env:PYTHONUTF8 = '1'
$arguments = @('-B', (Join-Path $PSScriptRoot 'orchestrate.py'), '--mode', $Mode,
    '--w3-root', $W3Root, '--core', $Core, '--shared', $Shared,
    '--port', "$Port", '--deadline-s', "$DeadlineSeconds")
if ($Out) { $arguments += @('--out', $Out) }
& $python @arguments
if ($LASTEXITCODE -ne 0) { throw "O_null1 stopped (exit $LASTEXITCODE); inspect sidecars/logs; no retry." }
