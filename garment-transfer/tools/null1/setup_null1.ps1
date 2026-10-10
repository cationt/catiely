param(
    [string]$W3Root = (Join-Path $env:USERPROFILE 'OneDrive\Documentos\w3-measure'),
    [string]$Core = (Join-Path $env:LOCALAPPDATA 'Comfy-Desktop\ComfyUI-Installs\ComfyUI\ComfyUI'),
    [string]$Shared = (Join-Path $env:LOCALAPPDATA 'Comfy-Desktop\ComfyUI-Shared')
)
# Offline preflight of existing R1/R2/R3 environments; installs nothing, no smoke/GPU.
$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest
& (Join-Path $PSScriptRoot 'run_null1.ps1') -Mode Verify -W3Root $W3Root -Core $Core -Shared $Shared
