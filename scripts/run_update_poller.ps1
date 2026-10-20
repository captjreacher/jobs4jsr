$ErrorActionPreference = 'Stop'
$root = Split-Path $PSScriptRoot -Parent
$logs = Join-Path $root 'outputs/logs'
New-Item -ItemType Directory -Force $logs | Out-Null
& "$root/.venv/Scripts/python.exe" -m jobs4jsr.poller --root $root *> (Join-Path $logs ('update-poller-' + (Get-Date -Format yyyy-MM-dd-HHmmss) + '.log'))
exit $LASTEXITCODE
