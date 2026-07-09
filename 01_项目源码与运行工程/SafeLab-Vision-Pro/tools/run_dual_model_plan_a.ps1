param(
    [switch]$SkipPpeWait
)

$ErrorActionPreference = "Stop"

$RepoRoot = Resolve-Path (Join-Path $PSScriptRoot "..")
$Python = Join-Path $RepoRoot ".venv-yolo\Scripts\python.exe"
$Reports = Join-Path $RepoRoot "reports\yolo_probe_current"
$RunRoot = "D:\ELFrk3588\yolo_training_runs"

$PpeName = "safelab_ppe_from_7class_yolov8n_640_20e"
$PpeDataset = "D:\ELFrk3588\SafeLab-Vision-Pro\datasets\safelab_ppe"
$PpeRun = Join-Path $RunRoot $PpeName
$PpeModel = Join-Path $PpeRun "weights\best.pt"

$FireName = "safelab_fire_smoke_yolov8s_640_continue_30e"
$FireDataset = "D:\ELFrk3588\SafeLab-Vision-Pro\datasets\safelab_fire_smoke"
$FireSeedModel = "D:\ELFrk3588\yolo_training_runs\safelab_fire_smoke_yolov8s_640_15e\weights\best.pt"
$FireRun = Join-Path $RunRoot $FireName
$FireModel = Join-Path $FireRun "weights\best.pt"

function Write-Step {
    param([string]$Message)
    $timestamp = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
    Write-Host "[$timestamp] $Message"
}

function Invoke-Checked {
    param(
        [string]$FilePath,
        [string[]]$Arguments,
        [string]$WorkingDirectory = $RepoRoot,
        [string]$StdoutPath,
        [string]$StderrPath
    )

    Write-Step ("RUN: {0} {1}" -f $FilePath, ($Arguments -join " "))
    if ($StdoutPath -and $StderrPath) {
        $process = Start-Process -FilePath $FilePath -ArgumentList $Arguments -WorkingDirectory $WorkingDirectory -NoNewWindow -Wait -PassThru -RedirectStandardOutput $StdoutPath -RedirectStandardError $StderrPath
        if ($process.ExitCode -ne 0) {
            throw "Command failed with exit code $($process.ExitCode). See $StdoutPath and $StderrPath"
        }
    } else {
        & $FilePath @Arguments
        if ($LASTEXITCODE -ne 0) {
            throw "Command failed with exit code $LASTEXITCODE"
        }
    }
}

function Get-CompletedEpochCount {
    param([string]$ResultsCsv)
    if (-not (Test-Path -LiteralPath $ResultsCsv)) {
        return 0
    }
    $lines = Get-Content -LiteralPath $ResultsCsv | Where-Object { $_.Trim() -ne "" }
    return [Math]::Max(0, $lines.Count - 1)
}

function Test-YoloRunComplete {
    param(
        [string]$ResultsCsv,
        [int]$ExpectedEpochs
    )
    return (Get-CompletedEpochCount $ResultsCsv) -ge $ExpectedEpochs
}

function Wait-YoloRun {
    param(
        [string]$RunName,
        [string]$ResultsCsv,
        [int]$ExpectedEpochs
    )

    while (-not (Test-YoloRunComplete $ResultsCsv $ExpectedEpochs)) {
        $count = Get-CompletedEpochCount $ResultsCsv
        Write-Step "$RunName still running or incomplete: $count/$ExpectedEpochs epochs recorded."
        Start-Sleep -Seconds 300
    }
    Write-Step "$RunName has $ExpectedEpochs epochs recorded."
}

function Copy-RunSummaries {
    param(
        [string]$RunName,
        [string]$RunDir
    )
    foreach ($fileName in @("args.yaml", "results.csv")) {
        $source = Join-Path $RunDir $fileName
        if (Test-Path -LiteralPath $source) {
            Copy-Item -LiteralPath $source -Destination (Join-Path $Reports "$RunName`_$fileName") -Force
        }
    }
}

function Run-ProbeAndReports {
    param(
        [string]$Name,
        [string]$Dataset,
        [string]$Model,
        [string]$Grid,
        [int]$PerClass
    )

    $probeDir = Join-Path $Reports "$Name`_probe_p$PerClass"
    Invoke-Checked $Python @(
        "tools\run_yolo_probe.py",
        "--dataset", $Dataset,
        "--model", $Model,
        "--output-dir", $probeDir,
        "--per-class", "$PerClass",
        "--conf", "0.15",
        "--conf", "0.25"
    )

    $metrics = Join-Path $probeDir "summary\conf250\iou_metrics.csv"
    Invoke-Checked $Python @(
        "tools\yolo_acceptance_report.py",
        "--metrics", $metrics,
        "--output-md", (Join-Path $Reports "$Name`_acceptance_report.md"),
        "--output-json", (Join-Path $Reports "$Name`_acceptance_report.json"),
        "--source-plan", "C:\Users\Lenovo\Desktop\新建 DOCX 文档 (2).docx"
    )

    Invoke-Checked $Python @(
        "tools\scan_yolo_thresholds.py",
        "--images", (Join-Path $probeDir "images"),
        "--truth-labels", (Join-Path $probeDir "labels"),
        "--prediction-labels", (Join-Path $probeDir "predictions\conf150\labels"),
        "--grid", $Grid,
        "--output-json", (Join-Path $Reports "$Name`_threshold_scan_conf150.json"),
        "--data-yaml", (Join-Path $Dataset "data.yaml")
    )
}

function Add-PlanOutputs {
    param([string[]]$Prefixes)

    Invoke-Checked "git" @("config", "core.longpaths", "true")
    Invoke-Checked "git" @("add", "tools\run_dual_model_plan_a.ps1")
    foreach ($prefix in $Prefixes) {
        Get-ChildItem -LiteralPath $Reports -Force |
            Where-Object { $_.Name -like "$prefix*" } |
            ForEach-Object {
                $relativePath = "reports\yolo_probe_current\$($_.Name)"
                Invoke-Checked "git" @("add", "-f", $relativePath)
            }
    }
}

function Invoke-GitCheckpoint {
    param(
        [string]$Message,
        [string[]]$Prefixes
    )

    Add-PlanOutputs $Prefixes
    $status = & git status --short
    if ($status) {
        Invoke-Checked "git" @("commit", "-m", $Message)
    } else {
        Write-Step "No git changes to commit."
    }
}

New-Item -ItemType Directory -Force -Path $Reports | Out-Null
Set-Location $RepoRoot

if (-not $SkipPpeWait) {
    Wait-YoloRun $PpeName (Join-Path $PpeRun "results.csv") 20
}
Copy-RunSummaries $PpeName $PpeRun

$ppeGrid = "0:0.15,0.20,0.25,0.30,0.35,0.40,0.45,0.50;1:0.15,0.20,0.25,0.30,0.35,0.40,0.45,0.50;2:0.15,0.20,0.25,0.30,0.35,0.40,0.45,0.50;3:0.15,0.20,0.25,0.30,0.35,0.40,0.45,0.50;4:0.15,0.20,0.25,0.30,0.35,0.40,0.45,0.50"
Run-ProbeAndReports $PpeName $PpeDataset $PpeModel $ppeGrid 80
Invoke-GitCheckpoint "Add PPE YOLOv8n plan A validation reports" @($PpeName, "dual_model_plan_a_runner")

if (-not (Test-YoloRunComplete (Join-Path $FireRun "results.csv") 15)) {
    Invoke-Checked $Python @(
        "tools\train_yolo_candidate.py",
        "--data", (Join-Path $FireDataset "data.yaml"),
        "--model", $FireSeedModel,
        "--name", $FireName,
        "--epochs", "15",
        "--imgsz", "640",
        "--batch", "8",
        "--workers", "0",
        "--optimizer", "AdamW",
        "--lr0", "0.001",
        "--lrf", "0.1"
    ) $RepoRoot (Join-Path $Reports "$FireName`_train_stdout.log") (Join-Path $Reports "$FireName`_train_stderr.log")
}
Wait-YoloRun $FireName (Join-Path $FireRun "results.csv") 15
Copy-RunSummaries $FireName $FireRun

$fireGrid = "0:0.10,0.15,0.20,0.25,0.30,0.35,0.40,0.45,0.50;1:0.10,0.15,0.20,0.25,0.30,0.35,0.40,0.45,0.50"
Run-ProbeAndReports $FireName $FireDataset $FireModel $fireGrid 80

Invoke-Checked $Python @("-m", "unittest", "discover", "-s", "tests", "-p", "test_yolo*.py", "-v") $RepoRoot (Join-Path $Reports "test_yolo_unittest_stdout.log") (Join-Path $Reports "test_yolo_unittest_stderr.log")
Invoke-Checked $Python @("-m", "unittest", "discover", "-s", "tests", "-p", "test_rule_dsl_engine.py", "-v") $RepoRoot (Join-Path $Reports "test_rule_dsl_engine_stdout.log") (Join-Path $Reports "test_rule_dsl_engine_stderr.log")

Invoke-GitCheckpoint "Add dual model plan A training and validation reports" @($PpeName, $FireName, "dual_model_plan_a_runner", "test_yolo", "test_rule_dsl_engine")
Write-Step "Plan A training and offline validation pipeline finished."
