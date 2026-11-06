$ErrorActionPreference = 'Stop'
Set-Location (Split-Path -Parent $PSScriptRoot)
if (-not (Test-Path '.venv\Scripts\python.exe')) { py -m venv .venv }
& .\.venv\Scripts\python.exe -m pip install -e . comtypes
& .\.venv\Scripts\python.exe -m squidz
