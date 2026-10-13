$ErrorActionPreference = 'Stop'
$root = Split-Path $PSScriptRoot -Parent
Set-Location $root
if (!(Test-Path .venv/Scripts/python.exe)) { py -3 -m venv .venv; if ($LASTEXITCODE) { throw 'Virtual environment creation failed' } }
& .venv/Scripts/python.exe -m pip install -e .
if ($LASTEXITCODE) { throw 'Dependency installation failed' }
& .venv/Scripts/python.exe -m jobs4jsr.cli setup
exit $LASTEXITCODE
