param([string]$Destination, [string]$Python, [switch]$CheckOnly)
$ErrorActionPreference = 'Stop'
if (-not $Destination) {
    $skillsBase = if ($env:CODEX_HOME) { Join-Path $env:CODEX_HOME 'skills' } else { Join-Path $env:USERPROFILE '.codex\skills' }
    $Destination = Join-Path $skillsBase 'film-reference-workbench'
}
$target = [IO.Path]::GetFullPath($Destination)
$sourceRoot = [IO.Path]::GetFullPath((Split-Path -Parent $PSScriptRoot))
if (-not (Get-Command git -ErrorAction SilentlyContinue)) { throw 'Git is required to install/update from GitHub. Install Git first.' }
if ($target -ne $sourceRoot) {
    if (Test-Path -LiteralPath $target) { throw 'Destination exists. Use its scripts/update.ps1, or choose an empty destination. Existing non-Git installs are not overwritten.' }
    if ($CheckOnly) { throw 'No installed checkout at destination.' }
    New-Item -ItemType Directory -Path (Split-Path -Parent $target) -Force | Out-Null
    & git clone --branch main -- 'https://github.com/William0702/film-reference-workbench.git' $target
    if ($LASTEXITCODE -ne 0) { throw 'Clone failed. For a private repo, grant this account read access and authenticate Git. No token is embedded.' }
}
$setupArgs = @{}
if ($Python) { $setupArgs.Python = $Python }
if ($CheckOnly) { $setupArgs.CheckOnly = $true }
& (Join-Path $target 'scripts/setup.ps1') @setupArgs
Write-Host ('Skill installed and verified: ' + $target)
