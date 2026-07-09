param(
    [string]$HostIp = $(if ($env:SAFELAB_BOARD_HOST) { $env:SAFELAB_BOARD_HOST } else { "192.168.0.232" }),
    [string]$Username = $(if ($env:SAFELAB_BOARD_USER) { $env:SAFELAB_BOARD_USER } else { "root" }),
    [string]$Password = $(if ($env:SAFELAB_BOARD_PASSWORD) { $env:SAFELAB_BOARD_PASSWORD } else { "root" }),
    [string]$RemoteRoot = "/root",
    [string]$ProjectName = "SafeLab-Vision-Pro",
    [switch]$SkipBoardOps
)

$ErrorActionPreference = "Stop"

$ProjectDir = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$WorkspaceDir = (Resolve-Path (Join-Path $ProjectDir "..")).Path
$ArchivePath = Join-Path $WorkspaceDir "$ProjectName.tar.gz"
$RemoteTar = "$RemoteRoot/$ProjectName.tar.gz"
$RemoteProject = "$RemoteRoot/$ProjectName"

function Write-Step {
    param([string]$Message)
    Write-Host ""
    Write-Host "== $Message =="
}

Write-Step "Checking local tools"
if (-not (Get-Command tar -ErrorAction SilentlyContinue)) {
    throw "tar command not found"
}
if (-not (Get-Command python -ErrorAction SilentlyContinue)) {
    throw "python command not found"
}

Write-Step "Checking board network"
if (-not (Test-Connection -ComputerName $HostIp -Count 2 -Quiet)) {
    throw "Board $HostIp is not reachable"
}

Write-Step "Packing project"
& tar `
    --exclude="$ProjectName/data/events/*.jsonl" `
    --exclude="$ProjectName/data/events/archive" `
    --exclude="$ProjectName/.pip-cache" `
    --exclude="$ProjectName/.tmp" `
    --exclude="$ProjectName/.venv-yolo" `
    --exclude="$ProjectName/.yolo-config" `
    --exclude="$ProjectName/datasets" `
    --exclude="$ProjectName/datasets/safelab/images/*" `
    --exclude="$ProjectName/datasets/safelab/labels/*" `
    --exclude="$ProjectName/logs" `
    --exclude="$ProjectName/models/checkpoints/*" `
    --exclude="$ProjectName/models/onnx/*" `
    --exclude="$ProjectName/models/rknn/*" `
    --exclude="$ProjectName/models/calibration/images/*" `
    --exclude="$ProjectName/rknn_transfer_package" `
    --exclude="$ProjectName/rknn_transfer_package.zip" `
    --exclude="$ProjectName/runs" `
    --exclude="$ProjectName/**/__pycache__" `
    --exclude="$ProjectName/reports/demo_export" `
    --exclude="$ProjectName/*.pt" `
    -czf $ArchivePath `
    -C $WorkspaceDir `
    $ProjectName
if ($LASTEXITCODE -ne 0) {
    throw "tar failed with exit code $LASTEXITCODE"
}
$archive = Get-Item $ArchivePath
Write-Host "Archive: $($archive.FullName) ($($archive.Length) bytes)"

Write-Step "Uploading and deploying to board"
$skipOpsLiteral = if ($SkipBoardOps) { "true" } else { "false" }
$pythonCode = @"
from pathlib import Path
import paramiko

host = r"$HostIp"
username = r"$Username"
password = r"$Password"
archive_path = Path(r"$ArchivePath")
remote_tar = r"$RemoteTar"
remote_project = r"$RemoteProject"
skip_ops = "$skipOpsLiteral" == "true"

client = paramiko.SSHClient()
client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
client.connect(
    hostname=host,
    username=username,
    password=password,
    timeout=10,
    banner_timeout=10,
    auth_timeout=10,
    look_for_keys=False,
    allow_agent=False,
)

sftp = client.open_sftp()
sftp.put(str(archive_path), remote_tar)
sftp.close()

cmd = (
    "cd /root"
    " && rm -rf /root/.safelab_preserve"
    " && mkdir -p /root/.safelab_preserve"
    f" && if [ -d {remote_project}/models/rknn ]; then mkdir -p /root/.safelab_preserve/models && cp -a {remote_project}/models/rknn /root/.safelab_preserve/models/; fi"
    f" && if [ -f {remote_project}/models/labels.txt ]; then mkdir -p /root/.safelab_preserve/models && cp -a {remote_project}/models/labels.txt /root/.safelab_preserve/models/; fi"
    f" && if [ -d {remote_project}/test_images ]; then cp -a {remote_project}/test_images /root/.safelab_preserve/; fi"
    f" && rm -rf {remote_project}"
    f" && tar -xzf {remote_tar}"
    f" && if [ -d /root/.safelab_preserve/models/rknn ]; then mkdir -p {remote_project}/models && cp -a /root/.safelab_preserve/models/rknn {remote_project}/models/; fi"
    f" && if [ -f /root/.safelab_preserve/models/labels.txt ]; then mkdir -p {remote_project}/models && cp -a /root/.safelab_preserve/models/labels.txt {remote_project}/models/; fi"
    f" && if [ -d /root/.safelab_preserve/test_images ]; then cp -a /root/.safelab_preserve/test_images {remote_project}/; fi"
    f" && cd {remote_project}"
)
if skip_ops:
    cmd += " && sh tools/board_smoke_test.sh"
else:
    cmd += " && sh tools/board_ops.sh"

stdin, stdout, stderr = client.exec_command(cmd, timeout=120)
out = stdout.read().decode("utf-8", errors="replace")
err = stderr.read().decode("utf-8", errors="replace")
code = stdout.channel.recv_exit_status()
print(out)
if err:
    print("--- STDERR ---")
    print(err)
client.close()
raise SystemExit(code)
"@

$pythonCode | python -
if ($LASTEXITCODE -ne 0) {
    throw "Board deployment check failed with exit code $LASTEXITCODE"
}

Write-Step "Done"
Write-Host "Synced to ${Username}@${HostIp}:$RemoteProject"
