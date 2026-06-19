#requires -Version 5.1
# Daily code audit wrapper (PowerShell port of run-audit.sh) for local Windows use.
# A skill is model-invoked context and cannot schedule or scope itself; this is the
# scheduler's hands. No jq/flock dependency (uses ConvertFrom-Json + a lockfile).
$ErrorActionPreference = 'Stop'

function Get-Default($v, $d) { if ([string]::IsNullOrEmpty($v)) { $d } else { $v } }

$RepoDir = Get-Default $env:REPO_DIR (git rev-parse --show-toplevel)
$Spec    = Get-Default $env:SPEC ''
$OutDir  = Get-Default $env:OUT_DIR (Join-Path $RepoDir 'audits')
$StateFile = Get-Default $env:STATE_FILE (Join-Path $RepoDir '.claude/state/code-auditor-last-sha')
$LockFile  = Get-Default $env:LOCK_FILE (Join-Path $env:TEMP 'code-auditor.lock')
$Model     = Get-Default $env:MODEL 'sonnet'
$MaxTurns  = Get-Default $env:MAX_TURNS '25'
$MaxBudget = Get-Default $env:MAX_BUDGET_USD '2'
$AllowedTools = Get-Default $env:ALLOWED_TOOLS 'Read,Grep,Glob,Bash(git diff:*),Bash(git log:*),Bash(git show:*),Bash(git rev-parse:*),Bash(git diff-tree:*)'

Set-Location $RepoDir
New-Item -ItemType Directory -Force -Path $OutDir, (Split-Path $StateFile) | Out-Null

# --- single-instance lock ---
try { $lock = [System.IO.File]::Open($LockFile,'OpenOrCreate','ReadWrite','None') }
catch { Write-Error 'another audit holds the lock; exiting'; exit 0 }

try {
  $HeadSha = (git rev-parse HEAD).Trim()
  $LastSha = $null
  if (Test-Path $StateFile) {
    $candidate = (Get-Content $StateFile -Raw).Trim()
    git cat-file -e "$candidate^{commit}" 2>$null
    if ($LASTEXITCODE -eq 0) { $LastSha = $candidate }
  }
  if (-not $LastSha) {
    $LastSha = (git rev-list -1 --before='24 hours ago' HEAD 2>$null)
    if ($LastSha) { $LastSha = $LastSha.Trim() }
  }
  $Range = if ($LastSha) { "$LastSha..$HeadSha" } else { $HeadSha }

  $changed = git diff --name-only $Range
  if ($LastSha -eq $HeadSha -or [string]::IsNullOrWhiteSpace(($changed -join ''))) {
    Write-Host 'no changes since last audit'
    Set-Content -NoNewline -Encoding ascii $StateFile $HeadSha
    exit 0
  }

  $specShown = if ($Spec) { $Spec } else { '<none>' }
  $Prompt = @"
Use the code-auditor skill. RANGE=$Range. SPEC=$specShown.
Audit only the changes in RANGE. Output only the JSON report per the skill's schema.
"@

  $date = Get-Date -Format 'yyyy-MM-dd'
  $ReportJson = Join-Path $OutDir "$date.json"
  $RunLog     = Join-Path $OutDir "$date.log"

  $raw = claude -p $Prompt --model $Model --allowedTools $AllowedTools `
    --permission-mode dontAsk --max-turns $MaxTurns --max-budget-usd $MaxBudget `
    --output-format json 2> $RunLog
  if ($LASTEXITCODE -ne 0) { Write-Error "claude run failed (exit $LASTEXITCODE); see $RunLog"; exit $LASTEXITCODE }

  # Extract .result, then validate it is JSON (ConvertFrom-Json throws if not).
  $result = ($raw | ConvertFrom-Json).result
  Set-Content -Encoding utf8 $ReportJson $result
  try { $report = $result | ConvertFrom-Json }
  catch { Write-Error "auditor returned non-JSON; state NOT advanced; see $ReportJson"; exit 1 }

  Set-Content -NoNewline -Encoding ascii $StateFile $HeadSha
  Write-Host "audit written: $ReportJson"
  $report.findings | Group-Object severity | ForEach-Object { "$($_.Name): $($_.Count)" }
}
finally { $lock.Close() }
