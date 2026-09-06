param([string]$RunName = ('tempest_repro_' + (Get-Date -Format 'yyyyMMdd_HHmmss')))
$ErrorActionPreference = 'Stop'
if ($RunName -notmatch '^tempest_repro_[A-Za-z0-9_]+$') { throw 'RunName must use the tempest_repro_ prefix and letters/digits/underscores.' }
$taskRoot = Split-Path (Split-Path $PSScriptRoot -Parent) -Parent
$taskOut = Join-Path (Join-Path $taskRoot 'lab') $RunName
if (Test-Path -LiteralPath $taskOut) { throw 'Reproduction output already exists; preserve it and choose another RunName.' }
New-Item -ItemType Directory -Path $taskOut | Out-Null
Get-ChildItem -LiteralPath $PSScriptRoot -Filter '*.py' | Copy-Item -Destination $taskOut
Copy-Item -LiteralPath (Join-Path $PSScriptRoot 'public') -Destination (Join-Path $taskOut 'public') -Recurse
$taskPython = 'C:\Users\finla\AppData\Local\ChessTK\venv312\Scripts\python.exe'
function Invoke-Research([string]$Script, [string[]]$ResearchArgs = @()) {
    & $taskPython -B (Join-Path $taskOut $Script) @ResearchArgs
    if ($LASTEXITCODE -ne 0) { throw "Research step failed: $Script" }
}
Invoke-Research 'prepare.py'
Invoke-Research 'reference.py' @('--mode','corpus')
Invoke-Research 'run_probes.py'
Invoke-Research 'probe.py' @('--variant','baseline','--deep','--cpu','8','--output',(Join-Path $taskOut 'baseline-deep-probes.jsonl'))
Invoke-Research 'reference.py' @('--mode','games')
Invoke-Research 'public_deep.py'
Invoke-Research 'prepare_critical.py'
Invoke-Research 'probe.py' @('--variant','baseline','--cpu','8','--cases',(Join-Path $taskOut 'opponent-critical.json'),'--output',(Join-Path $taskOut 'opponent-critical-probes.jsonl'))
Invoke-Research 'reference.py' @('--mode','choices')
Invoke-Research 'eval_experiment.py'
Invoke-Research 'label_audit.py'
Invoke-Research 'accumulator.py'
Invoke-Research 'rule_probe.py'
Invoke-Research 'history_audit.py'
Invoke-Research 'freeze_confirmation.py'
Invoke-Research 'summarize.py'
Invoke-Research 'confirm_opponent_advantages.py'
Invoke-Research 'stage_match.py'
Invoke-Research 'match/clock_match.py' @('--candidate',(Join-Path $taskOut 'prototypes/pesto_only'),'--baseline',(Join-Path $taskRoot 'odin_v6'),'--cpu','4','--nodes','20000','--openings',(Join-Path $taskRoot 'lab/odin/fast/generation-openings/screen.fen'),'--think-ms','100','--indices','0,1,2,3,4,5','--output',(Join-Path $taskOut 'match/games.jsonl'))
Invoke-Research 'audit_match.py'
Invoke-Research 'finalize.py'
Write-Output "Reproduced research in $taskOut. Original artifacts were preserved."
