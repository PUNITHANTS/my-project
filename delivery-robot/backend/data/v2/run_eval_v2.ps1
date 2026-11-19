# Dataset v2: build (with paraphrasing), then the C1-C5 evaluation on three test sets.
# Each step skips itself if its output exists, so the script can be restarted.
param(
    [string]$Model = "gpt-oss:20b",
    [string]$OutRoot = "data/evaluations/v2",
    [string]$PolicyModel = "artifacts/clarification_policy_v4.joblib"
)
$ErrorActionPreference = "Stop"
Set-Location "C:\Users\kamal\Downloads\my-project\delivery-robot\backend"
$py = "C:\Users\kamal\anaconda3\python.exe"

function Step($name, [scriptblock]$body) {
    Write-Output "=== $(Get-Date -Format s) START $name"
    & $body
    if ($LASTEXITCODE -ne 0) { throw "$name failed with exit code $LASTEXITCODE" }
    Write-Output "=== $(Get-Date -Format s) DONE $name"
}

if (-not (Test-Path "data/v2/manifest.json") -or -not (Select-String -Path "data/v2/manifest.json" -Pattern '"paraphrase_kept": [1-9]' -Quiet)) {
    $env:PYTHONUNBUFFERED = "1"
    Step "build dataset v2" { & $py data/v2/build_v2.py }
}

$env:AI_EXPERIMENT_MODE = "True"
$env:LLM_API_BASE = "http://localhost:11434/v1/chat/completions"
$env:LLM_API_KEY = "ollama"
$env:GROQ_MODEL = $Model
$env:AI_SAMPLE_AGREEMENT_K = "0"
# The campus delivery points the dataset uses (generate_v2.LOCATIONS); the
# location fallback in canonicalize_draft reads this list.
$env:AI_DELIVERY_LOCATIONS = "Sprague Library,Student Center,University Hall,Blanton Hall,Recreation Center,Dickson Hall,Calcia Hall,Freeman Hall,Richardson Hall,Partridge Hall,Life Hall,College Hall"
$env:PYTHONUNBUFFERED = "1"
$menuA = "data/menu_snapshot_v1.json"
$menuB = "data/v2/menu_snapshot_b.json"

foreach ($split in "train", "validation") {
    if (-not (Test-Path "$OutRoot/$split/summary.json")) {
        Remove-Item "$OutRoot/$split" -Recurse -Force -ErrorAction SilentlyContinue
        Step "C2 on $split" { & $py manage.py run_conversation_experiments --input "data/v2/splits/$split.jsonl" --output-dir "$OutRoot/$split" --menu-snapshot $menuA --policies C2 --trace }
    }
}

if (-not (Test-Path $PolicyModel)) {
    Step "train C5" { & $py manage.py train_clarification_policy --train "$OutRoot/train/c2_features.jsonl" --validation "$OutRoot/validation/c2_features.jsonl" --output $PolicyModel }
}

$env:AI_POLICY_MODEL_PATH = $PolicyModel
$tests = @(
    @{ name = "test_a"; input = "data/v2/splits/test_a.jsonl"; menu = $menuA },
    @{ name = "test_b"; input = "data/v2/splits/test_b.jsonl"; menu = $menuB },
    @{ name = "pizza";  input = "data/external/pizza_human.jsonl"; menu = $menuB }
)
foreach ($t in $tests) {
    $out = "$OutRoot/$($t.name)"
    if (-not (Test-Path "$out/summary.json")) {
        Remove-Item $out -Recurse -Force -ErrorAction SilentlyContinue
        Step "C1-C5 on $($t.name)" { & $py manage.py run_conversation_experiments --input $t.input --output-dir $out --menu-snapshot $t.menu --trace }
    }
    if (-not (Test-Path "$out/policy_replay.json")) {
        Step "offline policy comparison on $($t.name)" { & $py manage.py evaluate_clarification_policies --input "$out/c2_features.jsonl" --output "$out/policy_replay.json" }
    }
}
Write-Output "=== ALL DONE"
