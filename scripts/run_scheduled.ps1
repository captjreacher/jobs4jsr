$ErrorActionPreference = 'Stop'
$root = Split-Path $PSScriptRoot -Parent
$logs = Join-Path $root 'outputs/logs'
New-Item -ItemType Directory -Force $logs | Out-Null
& "$root/.venv/Scripts/python.exe" -m jobs4jsr.cli --root $root scheduled *> (Join-Path $logs ('scheduled-' + (Get-Date -Format yyyy-MM-dd-HHmmss) + '.log'))
exit $LASTEXITCODE
