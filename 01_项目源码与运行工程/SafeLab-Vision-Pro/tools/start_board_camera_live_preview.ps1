param(
    [string]$HostIp = $(if ($env:SAFELAB_BOARD_HOST) { $env:SAFELAB_BOARD_HOST } else { "192.168.0.232" }),
    [string]$Username = $(if ($env:SAFELAB_BOARD_USER) { $env:SAFELAB_BOARD_USER } else { "root" }),
    [string]$Password = $(if ($env:SAFELAB_BOARD_PASSWORD) { $env:SAFELAB_BOARD_PASSWORD } else { "root" }),
    [string]$Device = "/dev/video-camera0",
    [int]$Port = 8090,
    [int]$Fps = 10,
    [int]$PreviewWidth = 960
)

$ErrorActionPreference = "Stop"

$ProjectDir = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$ScriptPath = Join-Path $PSScriptRoot "start_board_camera_live_preview.py"

if (-not (Get-Command python -ErrorAction SilentlyContinue)) {
    throw "python command not found"
}

python $ScriptPath `
    --host $HostIp `
    --username $Username `
    --password $Password `
    --device $Device `
    --port $Port `
    --fps $Fps `
    --preview-width $PreviewWidth
