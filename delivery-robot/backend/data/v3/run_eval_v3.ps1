# Dataset v3 evaluation (plan steps 7-11). Each step skips itself if its output
# exists, so the script can be restarted after an interruption.
#
#   powershell -ExecutionPolicy Bypass -File data/v3/run_eval_v3.ps1
#
# Tuning (C5 training and threshold) uses only train and validation. Test-200
# and External-P are only evaluated, with the frozen setup.
param(
    [string]$Model = "gpt-oss:20b",
    [string]$SecondModel = "gemma3:12b",
    [string]$OutRoot = "data/evaluations/v3",
    [string]$PolicyModel = "artifacts/clarification_policy_v5.joblib"
)
$ErrorActionPreference = "Stop"
Set-Location "C:\Users\kamal\Downloads\my-project\delivery-robot\backend"
$py = "C:\Users\kamal\anaconda3\python.exe"
$menu = "data/v3/menu_snapshot_v3.json"
$externalP = "data/external/pizza_external_p.jsonl"

function Step($name, [scriptblock]$body) {
    Write-Output "=== $(Get-Date -Format s) START $name"
    & $body
    if ($LASTEXITCODE -ne 0) { throw "$name failed with exit code $LASTEXITCODE" }
    Write-Output "=== $(Get-Date -Format s) DONE $name"
}

$env:AI_EXPERIMENT_MODE = "True"
$env:LLM_API_BASE = "http://127.0.0.1:11434/v1/chat/completions"
$env:LLM_API_KEY = "ollama"
$env:AI_SAMPLE_AGREEMENT_K = "0"
$env:AI_DELIVERY_LOCATIONS = "Sprague Library,Student Center,University Hall,Blanton Hall,Recreation Center,Dickson Hall,Calcia Hall,Freeman Hall,Richardson Hall,Partridge Hall,Life Hall,College Hall"
$env:PYTHONUNBUFFERED = "1"
$env:GROQ_MODEL = $Model

# Step 7a: C2 on train and validation gives C5 its features and labels.
foreach ($split in "train", "validation") {
    if (-not (Test-Path "$OutRoot/$split/summary.json")) {
        Remove-Item "$OutRoot/$split" -Recurse -Force -ErrorAction SilentlyContinue
        Step "C2 on $split" { & $py manage.py run_conversation_experiments --input "data/v3/splits/$split.jsonl" --output-dir "$OutRoot/$split" --menu-snapshot $menu --policies C2 --trace }
    }
}

# Step 7b: train C5 on train, threshold on validation. The training command
# refuses a threshold that would ask on most correct drafts; then C5 is left out.
$policies = "C1,C2,C3,C4,C5"
if (-not (Test-Path $PolicyModel)) {
    Write-Output "=== $(Get-Date -Format s) START train C5"
    & $py manage.py train_clarification_policy --train "$OutRoot/train/c2_features.jsonl" --validation "$OutRoot/validation/c2_features.jsonl" --output $PolicyModel
    if ($LASTEXITCODE -ne 0) {
        Write-Output "C5 training refused (see message above); C5 is left out of the evaluation."
        "C5 training refused: the signals do not separate wrong drafts on validation." | Out-File -Encoding utf8 "$OutRoot/C5_NOT_TRAINED.txt"
    }
    Write-Output "=== $(Get-Date -Format s) DONE train C5"
}
if (-not (Test-Path $PolicyModel)) { $policies = "C1,C2,C3,C4" }
$env:AI_POLICY_MODEL_PATH = $PolicyModel

# Steps 8-9: frozen setup on Test-200 and External-P.
$runs = @(
    @{ name = "test"; input = "data/v3/splits/test.jsonl"; policies = $policies; model = $Model },
    @{ name = "external_p"; input = $externalP; policies = $policies; model = $Model },
    # Step 10: second model, C1 and C5 (C3 if C5 was not trained), same pipeline.
    @{ name = "test_$($SecondModel -replace '[:.]', '_')"; input = "data/v3/splits/test.jsonl"; policies = $(if ($policies -match "C5") { "C1,C5" } else { "C1,C3" }); model = $SecondModel },
    @{ name = "external_p_$($SecondModel -replace '[:.]', '_')"; input = $externalP; policies = $(if ($policies -match "C5") { "C1,C5" } else { "C1,C3" }); model = $SecondModel }
)
foreach ($r in $runs) {
    $out = "$OutRoot/$($r.name)"
    $env:GROQ_MODEL = $r.model
    if (-not (Test-Path "$out/summary.json")) {
        Remove-Item $out -Recurse -Force -ErrorAction SilentlyContinue
        Step "$($r.policies) on $($r.name) with $($r.model)" { & $py manage.py run_conversation_experiments --input $r.input --output-dir $out --menu-snapshot $menu --policies $r.policies --trace }
    }
    if (-not (Test-Path "$out/policy_replay.json")) {
        # Replay every policy's rule on one run's turns (C2's when it ran, as in v2).
        $feat = if ($r.policies -match "C2") { "c2" } else { (($r.policies -split ',')[0]).ToLower() }
        Step "offline policy comparison on $($r.name)" { & $py manage.py evaluate_clarification_policies --input "$out/$($feat)_features.jsonl" --output "$out/policy_replay.json" }
    }
    # Step 11: confidence intervals and paired McNemar tests.
    Step "stats on $($r.name)" { & $py data/v3/stats_v3.py $out --metric completed_exact; & $py data/v3/stats_v3.py $out --metric exact }
}
$env:GROQ_MODEL = $Model
Write-Output "=== ALL DONE"
