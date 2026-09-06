# Windows inner loop. Contest runtime is Linux Python 3.12; this laptop is not that.
param(
    [Parameter(Position = 0)]
    [ValidateSet("smoke", "perft", "play", "zip", "search", "gauntlet", "overnight", "help")]
    [string]$Command = "help"
)

$ErrorActionPreference = "Stop"
$Root = $PSScriptRoot
Set-Location $Root
$Py = Join-Path $Root ".venv\Scripts\python.exe"
if (-not (Test-Path $Py)) {
    throw "No .venv. Create one: py -3.14 -m venv .venv ; .\.venv\Scripts\python -m pip install chess==1.11.2"
}

switch ($Command) {
    "smoke" { & $Py -m lab.smoke }
    "perft" { & $Py -m lab.perft --quick }
    "search" { & $Py -m lab.test_b; & $Py -m lab.test_c }
    "play" {
        & $Py -m harness.play --white . --black baselines/random --base-ms 5000 --increment-ms 100 --ply-cap 40
    }
    "zip" {
        New-Item -ItemType Directory -Force -Path (Join-Path $Root "dist") | Out-Null
        & $Py -m harness.package --out (Join-Path $Root "dist\candidate.zip")
    }
    "gauntlet" {
        New-Item -ItemType Directory -Force -Path (Join-Path $Root "lab\logs") | Out-Null
        & $Py -m lab.gauntlet --quick
    }
    "overnight" {
        New-Item -ItemType Directory -Force -Path (Join-Path $Root "lab\logs") | Out-Null
        & $Py -m lab.gauntlet --hours 8 --opponent baselines/greedy --log lab/logs/gauntlet.jsonl
    }
    default {
        Write-Host "dev.ps1 smoke | perft | search | play | zip | gauntlet | overnight"
    }
}
