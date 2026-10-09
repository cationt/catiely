# Windows PowerShell 5.1; ASCII source. No install/download or implicit fallback.
param(
    [string]$ComfyRoot = (Join-Path $env:LOCALAPPDATA "Comfy-Desktop\ComfyUI-Installs\ComfyUI\ComfyUI"),
    [string]$SharedRoot = (Join-Path $env:LOCALAPPDATA "Comfy-Desktop\ComfyUI-Shared"),
    [string]$WorkRoot = (Join-Path $env:USERPROFILE "OneDrive\Documentos\w3-measure\r2"),
    [ValidateSet("qie2511_q5_2ref_1mp_40steps", "qie2511_q5_2ref_0p5mp_40steps")]
    [string]$Configuration = "qie2511_q5_2ref_1mp_40steps",
    [string]$SetupReport = "",
    [int]$Port = 8191,
    [switch]$DryRun
)
$ErrorActionPreference = "Stop"
Set-StrictMode -Version 2.0
$py = Join-Path $ComfyRoot ".venv\Scripts\python.exe"
if (-not (Test-Path -LiteralPath $py)) { throw "Pinned ComfyUI Python missing: $py" }
$action = "setup"
if ($DryRun) { $action = "dry-run" }
if ($action -eq "bench" -and -not $SetupReport) { throw "Pass -SetupReport pointing to the reviewed successful setup report.json" }
$arguments = @((Join-Path $PSScriptRoot "orchestrate.py"), $action, "--core", $ComfyRoot, "--shared", $SharedRoot, "--work-root", $WorkRoot, "--configuration", $Configuration, "--port", "$Port")
if ($SetupReport) { $arguments += @("--setup-report", $SetupReport) }
& $py @arguments
$r2Exit = $LASTEXITCODE
if ($r2Exit -ne 0) { throw "R2 stopped with exit $r2Exit; no retry or fallback. Inspect the unique run directory." }
