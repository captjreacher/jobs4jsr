$ErrorActionPreference = 'Stop'
$root = Split-Path $PSScriptRoot -Parent
if ((Get-TimeZone).Id -ne 'New Zealand Standard Time') { throw 'Set Windows timezone to New Zealand Standard Time before installing this local 18:00 digest.' }
$action = New-ScheduledTaskAction -Execute 'powershell.exe' -Argument ('-NoProfile -NonInteractive -ExecutionPolicy Bypass -File "' + $root + '\scripts\run_digest.ps1"') -WorkingDirectory $root
$trigger = New-ScheduledTaskTrigger -Weekly -DaysOfWeek Monday,Tuesday,Wednesday,Thursday,Friday -At '18:00'
$settings = New-ScheduledTaskSettingsSet -StartWhenAvailable -MultipleInstances IgnoreNew -ExecutionTimeLimit (New-TimeSpan -Minutes 20) -RestartCount 2 -RestartInterval (New-TimeSpan -Minutes 5) -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries
$principal = New-ScheduledTaskPrincipal -UserId ([System.Security.Principal.WindowsIdentity]::GetCurrent().Name) -LogonType Interactive -RunLevel Limited
# A local boundary without UTC offset follows Windows NZ DST transitions.
$trigger.StartBoundary = (Get-Date -Hour 18 -Minute 0 -Second 0).ToString('yyyy-MM-ddTHH:mm:ss')
Register-ScheduledTask -TaskName 'Jobs4JSR Digest' -Action $action -Trigger $trigger -Settings $settings -Principal $principal -Description 'Jess new-role digest Mon-Fri 18:00 Pacific/Auckland. Discovers nothing; emails only when the discovery database gained new roles today. Local computer must be on and user signed in.' -Force | Out-Null
Get-ScheduledTask -TaskName 'Jobs4JSR Digest' | Select-Object TaskName,State,Triggers,Settings
