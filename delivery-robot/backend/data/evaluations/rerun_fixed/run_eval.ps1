# Full C1-C5 rerun with the local model. Each step skips itself if its output exists,
# so the script can be restarted after an interruption (the response cache makes
# already-answered turns free).
param(
    [string]$Model = "gpt-oss:20b",
    [string]$OutRoot = "data/evaluations/rerun_fixed"
)
$ErrorActionPreference = "Stop"
Set-Location "C:\Users\kamal\Downloads\my-project\delivery-robot\backend"
$py = "C:\Users\kamal\anaconda3\python.exe"

$env:AI_EXPERIMENT_MODE = "True"
$env:LLM_API_BASE = "http://localhost:11434/v1/chat/completions"
$env:LLM_API_KEY = "ollama"
$env:GROQ_MODEL = $Model
$env:AI_SAMPLE_AGREEMENT_K = "0"
$env:PYTHONUNBUFFERED = "1"
$snapshot = "data/menu_snapshot_v1.json"
$policyModel = "artifacts/clarification_policy_v2.joblib"

function Step($name, [scriptblock]$body) {
    Write-Output "=== $(Get-Date -Format s) START $name"
    & $body
    if ($LASTEXITCODE -ne 0) { throw "$name failed with exit code $LASTEXITCODE" }
    Write-Output "=== $(Get-Date -Format s) DONE $name"
}

foreach ($split in "train", "validation") {
    if (-not (Test-Path "$OutRoot/$split/summary.json")) {
        Remove-Item "$OutRoot/$split" -Recurse -Force -ErrorAction SilentlyContinue
        Step "C2 on $split" { & $py manage.py run_conversation_experiments --input "data/splits/$split.jsonl" --output-dir "$OutRoot/$split" --menu-snapshot $snapshot --policies C2 --trace }
    }
}

if (-not (Test-Path $policyModel)) {
    Step "train C5" { & $py manage.py train_clarification_policy --train "$OutRoot/train/c2_features.jsonl" --validation "$OutRoot/validation/c2_features.jsonl" --output $policyModel }
}

$env:AI_POLICY_MODEL_PATH = $policyModel
if (-not (Test-Path "$OutRoot/test/summary.json")) {
    Remove-Item "$OutRoot/test" -Recurse -Force -ErrorAction SilentlyContinue
    Step "C1-C5 on test" { & $py manage.py run_conversation_experiments --input "data/splits/test.jsonl" --output-dir "$OutRoot/test" --menu-snapshot $snapshot --trace }
}

Step "offline policy comparison on test" { & $py manage.py evaluate_clarification_policies --input "$OutRoot/test/c2_features.jsonl" --output "$OutRoot/test/policy_replay.json" }
Write-Output "=== ALL DONE"
