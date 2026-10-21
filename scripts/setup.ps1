param([string]$Python, [switch]$CheckOnly, [switch]$SkipSelfTest)
$ErrorActionPreference = 'Stop'
$skillRoot = Split-Path -Parent $PSScriptRoot
if ($env:OS -ne 'Windows_NT' -or -not [Environment]::Is64BitOperatingSystem) { throw 'Windows x64 is required.' }
function Test-Python312([string]$Executable, [string[]]$PrefixArgs = @()) {
    try {
        $versionResult = & $Executable @PrefixArgs -c 'import sys,struct; print(int(sys.version_info[:2]==(3,12) and struct.calcsize(''P'')==8))' 2>$null
        return ($LASTEXITCODE -eq 0 -and "$versionResult".Trim() -eq '1')
    } catch { return $false }
}
$pythonExe = $null
$pythonArgs = @()
if ($Python) {
    if (-not (Test-Python312 $Python)) { throw 'Specified Python must be CPython 3.12 x64.' }
    $pythonExe = $Python
} else {
    if (Get-Command py -ErrorAction SilentlyContinue) {
        if (Test-Python312 'py' @('-3.12')) { $pythonExe = 'py'; $pythonArgs = @('-3.12') }
    }
    if (-not $pythonExe -and (Get-Command python -ErrorAction SilentlyContinue)) {
        if (Test-Python312 'python') { $pythonExe = 'python' }
    }
    $userPython = Join-Path $env:LOCALAPPDATA 'Programs\Python\Python312\python.exe'
    if (-not $pythonExe -and (Test-Path -LiteralPath $userPython)) {
        if (Test-Python312 $userPython) { $pythonExe = $userPython }
    }
}
if (-not $pythonExe) {
    if ($CheckOnly) { throw 'Missing Python 3.12 x64. Run setup.ps1 without -CheckOnly to repair.' }
    if (-not (Get-Command winget -ErrorAction SilentlyContinue)) { throw 'Missing Python 3.12 and winget. Install Python 3.12 x64 from python.org, then rerun.' }
    $runtimeLock = Get-Content -LiteralPath (Join-Path $skillRoot 'references/runtime-lock.json') -Raw | ConvertFrom-Json
    & winget install --id $runtimeLock.python.wingetId --version $runtimeLock.python.version --exact --source winget --scope user --silent --accept-package-agreements --accept-source-agreements --disable-interactivity
    if ($LASTEXITCODE -ne 0) { throw 'Python user installation failed; inspect winget output, then rerun.' }
    $pythonExe = Join-Path $env:LOCALAPPDATA 'Programs\Python\Python312\python.exe'
    if (-not (Test-Python312 $pythonExe)) { throw 'Python installed but not usable at the expected user path.' }
}
$bootstrapArgs = @('-X', 'utf8', (Join-Path $PSScriptRoot 'bootstrap.py'))
if (-not $CheckOnly) { $bootstrapArgs += '--repair' }
if (-not $CheckOnly -and -not $SkipSelfTest) { $bootstrapArgs += '--self-test' }
& $pythonExe @pythonArgs @bootstrapArgs
if ($LASTEXITCODE -ne 0) { throw 'Runtime setup failed. See runtime/setup-report.json for component details.' }
