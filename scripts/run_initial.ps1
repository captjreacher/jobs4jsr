$ErrorActionPreference = 'Stop'
$root = Split-Path $PSScriptRoot -Parent
& "$root/.venv/Scripts/python.exe" -m jobs4jsr.cli --root $root initial
exit $LASTEXITCODE
