param([string]$Python)
$ErrorActionPreference = 'Stop'
$skillRoot = Split-Path -Parent $PSScriptRoot
if (-not (Test-Path -LiteralPath (Join-Path $skillRoot '.git'))) { throw 'Not a Git install. Install into an empty directory; preserve this local copy and runtime.' }
$remote = & git -C $skillRoot config --get remote.origin.url
if ($LASTEXITCODE -ne 0 -or "$remote".Trim() -notin @('https://github.com/William0702/film-reference-workbench.git','https://github.com/William0702/film-reference-workbench','git@github.com:William0702/film-reference-workbench.git')) { throw 'Unexpected origin; refusing to update from another repository.' }
$branch = & git -C $skillRoot branch --show-current
if ($LASTEXITCODE -ne 0 -or "$branch".Trim() -ne 'main') { throw 'Switch to main before updating.' }
$changes = & git -C $skillRoot status --porcelain
if ($LASTEXITCODE -ne 0 -or $changes) { throw 'Local changes exist. Preserve or commit them before updating; no files were reset.' }
& git -C $skillRoot pull --ff-only origin main
if ($LASTEXITCODE -ne 0) { throw 'Update failed or history diverged. No force reset performed.' }
$setupArgs = @{}
if ($Python) { $setupArgs.Python = $Python }
& (Join-Path $PSScriptRoot 'setup.ps1') @setupArgs
Write-Host 'Code and runtime verified. Reload the skill in your Agent if needed.'
