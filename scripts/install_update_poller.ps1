param([switch]$Install)
$ErrorActionPreference = 'Stop'
$root = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
if (-not $Install) { Write-Output 'Review only. After production approval, pass -Install to register the separate outbound poller task.'; exit 0 }
if (-not (Test-Path -LiteralPath "$root\.venv\Scripts\python.exe")) { throw 'Python environment missing' }
if (Get-ScheduledTask -TaskName 'Jobs4JSR Update Poller' -ErrorAction SilentlyContinue) { throw 'Poller task already exists; review it before replacing it.' }
$discovery = Get-ScheduledTask -TaskName 'Jobs4JSR Discovery'
if ($discovery.Actions.Arguments -notlike "*$root\scripts\run_scheduled.ps1*") { throw 'Use the same canonical root as the installed discovery task.' }
$logs = Join-Path $root 'outputs/logs'
New-Item -ItemType Directory -Force $logs | Out-Null
# Manage the Python process directly: stopping the task stops the actual runner,
# rather than relying on a shell wrapper to propagate termination to a child.
$action = New-ScheduledTaskAction -Execute "$root\.venv\Scripts\python.exe" -Argument ('-u -m jobs4jsr.poller --root "' + $root + '"') -WorkingDirectory $root
$trigger = New-ScheduledTaskTrigger -AtLogOn -User ([System.Security.Principal.WindowsIdentity]::GetCurrent().Name)
$settings = New-ScheduledTaskSettingsSet -MultipleInstances IgnoreNew -ExecutionTimeLimit ([TimeSpan]::Zero) -RestartCount 999 -RestartInterval (New-TimeSpan -Minutes 1) -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries
$principal = New-ScheduledTaskPrincipal -UserId ([System.Security.Principal.WindowsIdentity]::GetCurrent().Name) -LogonType Interactive -RunLevel Limited
Register-ScheduledTask -TaskName 'Jobs4JSR Update Poller' -Action $action -Trigger $trigger -Settings $settings -Principal $principal -Description 'Outbound manual-update queue poller; uses existing sourcing pipeline. Requires signed-in user.' | Out-Null
Write-Output 'Poller registered. Enable the private environment flag and start only under the release runbook. Discovery schedule unchanged.'
