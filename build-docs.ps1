<#
    build-docs.ps1 - Regenerate the player documentation site under docs\.

    Reads the Terra Mirabilis mod's own SQL and writes a static website into
    docs\, which GitHub Pages serves from the repo-root /docs folder. Commit the
    regenerated docs\ and push; the live site updates.

    The mod source is NOT part of this repo. The generator auto-locates it (a
    sibling civ6-terra-mira checkout, or the installed mod); pass -Source to point
    at it explicitly, or set the TM_MOD_DIR environment variable.

    Requires Python 3 (standard library only - no pip installs). If the only
    "python" on PATH is the Microsoft Store stub, this script finds a real
    install automatically; override with -Python or the TM_PYTHON env var.

    Usage:
        .\build-docs.ps1
        .\build-docs.ps1 -Source "C:\path\to\mod"   # folder containing Core\
        .\build-docs.ps1 -Serve                      # build, then serve at http://localhost:8791
#>
param(
    [string]$Python,
    [string]$Source,          # path to the Terra Mirabilis mod source (folder containing Core\)
    [switch]$Serve,
    [int]$Port = 8791
)

$ErrorActionPreference = 'Stop'
$repo = $PSScriptRoot

function Test-RealPython([string]$exe) {
    if (-not $exe) { return $false }
    # Reject the Microsoft Store execution-alias stub, which prints a prompt and exits.
    if ($exe -like "*\Microsoft\WindowsApps\*") { return $false }
    try { $v = & $exe --version 2>&1 } catch { return $false }
    return ($LASTEXITCODE -eq 0 -and "$v" -match 'Python 3')
}

function Resolve-Python {
    if ($Python) {
        if (Test-RealPython $Python) { return $Python }
        Write-Error "The -Python path is not a working Python 3: $Python"; exit 1
    }
    if ($env:TM_PYTHON -and (Test-RealPython $env:TM_PYTHON)) { return $env:TM_PYTHON }
    foreach ($cmd in @('python','python3')) {
        foreach ($g in (Get-Command $cmd -All -ErrorAction SilentlyContinue)) {
            if (Test-RealPython $g.Source) { return $g.Source }
        }
    }
    $roots = @(
        (Join-Path $env:LOCALAPPDATA 'Programs\Python'),
        'C:\Program Files\Python313','C:\Program Files\Python312','C:\Program Files\Python311',
        'C:\Python313','C:\Python312','C:\Python311'
    )
    foreach ($r in $roots) {
        if (Test-Path $r) {
            $hit = Get-ChildItem -Path $r -Recurse -Filter python.exe -ErrorAction SilentlyContinue |
                   Where-Object { $_.FullName -notmatch '\\venv\\' } |
                   Select-Object -First 1
            if ($hit -and (Test-RealPython $hit.FullName)) { return $hit.FullName }
        }
    }
    return $null
}

$py = Resolve-Python
if (-not $py) {
    Write-Error @"
No working Python 3 found. Install it from https://www.python.org/downloads/
(tick "Add python.exe to PATH"), or pass the path explicitly:
    .\build-docs.ps1 -Python "C:\Path\to\python.exe"
"@
    exit 1
}

Write-Host "Using Python: $py"
$genArgs = @((Join-Path $repo 'generator\generate.py'))
if ($Source) { $genArgs += @('--source', $Source) }
& $py @genArgs
if ($LASTEXITCODE -ne 0) { Write-Error "Generator failed (exit $LASTEXITCODE)."; exit 1 }

$docs = Join-Path $repo 'docs'
Write-Host ""
Write-Host "Docs written to: $docs"
Write-Host "Commit and push docs\ to update the GitHub Pages site."

if ($Serve) {
    Write-Host ""
    Write-Host "Serving docs\ at http://localhost:$Port/  (Ctrl+C to stop)"
    Push-Location $docs
    try { & $py -m http.server $Port --bind 127.0.0.1 } finally { Pop-Location }
}
