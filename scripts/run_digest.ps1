$ErrorActionPreference = 'Stop'
$root = Split-Path $PSScriptRoot -Parent
$logs = Join-Path $root 'outputs/logs'
New-Item -ItemType Directory -Force $logs | Out-Null
& "$root/.venv/Scripts/python.exe" -m jobs4jsr.cli --root $root email *> (Join-Path $logs ('digest-' + (Get-Date -Format yyyy-MM-dd-HHmmss) + '.log'))
exit $LASTEXITCODE
