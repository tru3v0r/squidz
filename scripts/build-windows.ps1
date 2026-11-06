$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest
$ProjectRoot = Split-Path -Parent $PSScriptRoot
Set-Location $ProjectRoot

function Invoke-Checked {
    param([string]$Label, [scriptblock]$Command)
    Write-Host "==> $Label"
    & $Command
    if ($LASTEXITCODE -ne 0) {
        throw "$Label failed (exit code $LASTEXITCODE). No successful build was produced."
    }
}

# Python 3.12 has prebuilt wheels for pygame 2.6.1 on Windows.
& py -3.12 --version
if ($LASTEXITCODE -ne 0) {
    throw 'Python 3.12 is required. Install it from python.org, then rerun this script.'
}

# Keep the environment outside Dropbox-synced project directories when possible.
$VenvRoot = if ($env:SQUIDZ_VENV_DIR) { $env:SQUIDZ_VENV_DIR } else { Join-Path $env:LOCALAPPDATA 'squidz\venv-py312' }
$Python = Join-Path $VenvRoot 'Scripts\python.exe'
if (Test-Path $Python) {
    & $Python -c 'import sys; sys.exit(0 if sys.version_info[:2] == (3, 12) else 1)'
    if ($LASTEXITCODE -ne 0) {
        throw "Existing virtual environment is not Python 3.12: $VenvRoot. Remove it or set SQUIDZ_VENV_DIR."
    }
} else {
    Invoke-Checked 'Create Python 3.12 environment' { py -3.12 -m venv $VenvRoot }
}

Invoke-Checked 'Install dependencies' { & $Python -m pip install --only-binary pygame -e '.[build,test]' }
Invoke-Checked 'Run tests' { & $Python -m pytest -q }

# Remove any stale executable so failure cannot be mistaken for success.
if (Test-Path 'dist\squidz') { Remove-Item 'dist\squidz' -Recurse -Force }
Invoke-Checked 'Build Windows executable' {
    & $Python -m PyInstaller --noconfirm --clean --onedir --windowed --name squidz --collect-all pygame --hidden-import comtypes.client src\squidz\main.py
}

$Exe = Join-Path $ProjectRoot 'dist\squidz\squidz.exe'
if (-not (Test-Path $Exe)) { throw "PyInstaller finished without creating $Exe" }

New-Item -ItemType Directory -Force 'dist\squidz\config' | Out-Null
Copy-Item 'config\*' 'dist\squidz\config\' -Recurse -Force -ErrorAction Stop
Copy-Item 'docs' 'dist\squidz\docs' -Recurse -Force -ErrorAction Stop
Copy-Item 'browser-extension' 'dist\squidz\browser-extension' -Recurse -Force -ErrorAction Stop
Write-Host "SUCCESS: $Exe" -ForegroundColor Green
