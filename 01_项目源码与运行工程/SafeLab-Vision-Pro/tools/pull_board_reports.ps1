param(
    [string]$HostIp = "192.168.0.232",
    [string]$Username = "root",
    [string]$Password = "root",
    [string]$RemoteRoot = "/root",
    [string]$ProjectName = "SafeLab-Vision-Pro",
    [string]$LocalReportsDir = "",
    [switch]$IncludeEvents
)

$ErrorActionPreference = "Stop"

$ProjectDir = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
if ([string]::IsNullOrWhiteSpace($LocalReportsDir)) {
    $LocalReportsDir = Join-Path $ProjectDir "reports"
}

if (-not ($RemoteRoot -eq "/root" -or $RemoteRoot.StartsWith("/root/"))) {
    throw "RemoteRoot must stay under /root. Current value: $RemoteRoot"
}

$RemoteProject = "$RemoteRoot/$ProjectName"
$RemoteReports = "$RemoteProject/reports"
$LocalReportsDir = (New-Item -ItemType Directory -Force -Path $LocalReportsDir).FullName

function Write-Step {
    param([string]$Message)
    Write-Host ""
    Write-Host "== $Message =="
}

Write-Step "Checking local tools"
if (-not (Get-Command python -ErrorAction SilentlyContinue)) {
    throw "python command not found"
}

Write-Step "Checking board network"
if (-not (Test-Connection -ComputerName $HostIp -Count 2 -Quiet)) {
    throw "Board $HostIp is not reachable"
}

Write-Step "Pulling board reports"
$includeEventsLiteral = if ($IncludeEvents) { "true" } else { "false" }
$pythonCode = @"
from pathlib import Path
import json
import stat
import time
import paramiko

host = r"$HostIp"
username = r"$Username"
password = r"$Password"
remote_project = r"$RemoteProject"
remote_reports = r"$RemoteReports"
local_reports = Path(r"$LocalReportsDir")
include_events = "$includeEventsLiteral" == "true"

downloaded = []
missing = []

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

def exists(path):
    try:
        sftp.stat(path)
        return True
    except FileNotFoundError:
        return False
    except OSError:
        return False

def pull_tree(remote_dir, local_dir):
    if not exists(remote_dir):
        missing.append(remote_dir)
        return
    local_dir.mkdir(parents=True, exist_ok=True)
    for item in sftp.listdir_attr(remote_dir):
        remote_path = remote_dir.rstrip("/") + "/" + item.filename
        local_path = local_dir / item.filename
        if stat.S_ISDIR(item.st_mode):
            pull_tree(remote_path, local_path)
        elif stat.S_ISREG(item.st_mode):
            local_path.parent.mkdir(parents=True, exist_ok=True)
            sftp.get(remote_path, str(local_path))
            downloaded.append({
                "remote": remote_path,
                "local": str(local_path),
                "size_bytes": local_path.stat().st_size,
            })

pull_tree(remote_reports, local_reports)
if include_events:
    pull_tree(remote_project.rstrip("/") + "/data/events", local_reports / "board_pull" / "data_events")

sftp.close()
client.close()

summary = {
    "host": host,
    "remote_project": remote_project,
    "remote_reports": remote_reports,
    "local_reports": str(local_reports),
    "include_events": include_events,
    "downloaded_count": len(downloaded),
    "missing": missing,
    "pulled_at_epoch": int(time.time()),
    "files": downloaded,
}
summary_json = local_reports / "pull_board_reports_summary.json"
summary_txt = local_reports / "pull_board_reports_summary.txt"
summary_json.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
summary_txt.write_text(
    "\n".join([
        "SafeLab-Vision Pro Board Report Pull Summary",
        f"host: {host}",
        f"remote_project: {remote_project}",
        f"local_reports: {local_reports}",
        f"include_events: {include_events}",
        f"downloaded_count: {len(downloaded)}",
        "missing: " + (", ".join(missing) if missing else "none"),
        "",
        "Key files:",
        *[
            f"- {Path(item['local']).name} ({item['size_bytes']} bytes)"
            for item in downloaded
            if Path(item["local"]).name in {
                "board_camera_preview.jpg",
                "board_camera_preview.html",
                "board_camera_preview.txt",
                "board_audio_probe.txt",
                "board_mic_probe.wav",
                "board_camera_check.txt",
                "board_ov13855_diagnose.txt",
                "board_rknn_runtime_check.txt",
                "board_rknn_common_test_output.txt",
                "board_health_check.txt",
                "board_acceptance_summary.txt",
                "board_competition_mode.txt",
                "runtime_status.json",
                "runtime_status.txt",
            }
        ],
    ]),
    encoding="utf-8",
)
print(json.dumps({
    "downloaded_count": len(downloaded),
    "summary_json": str(summary_json),
    "summary_txt": str(summary_txt),
}, ensure_ascii=False, indent=2))
raise SystemExit(0 if not missing else 1)
"@

$pythonCode | python -
if ($LASTEXITCODE -ne 0) {
    throw "Board report pull failed with exit code $LASTEXITCODE"
}

Write-Step "Done"
Write-Host "Pulled board reports from ${Username}@${HostIp}:$RemoteReports"
Write-Host "Local reports: $LocalReportsDir"
