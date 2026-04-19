$Action = New-ScheduledTaskAction -Execute 'wscript.exe' -Argument '"d:\Projects\Antigravity\AI_mem_system\run_cortex_silently.vbs"'
$Trigger = New-ScheduledTaskTrigger -AtLogOn
$Settings = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -ExecutionTimeLimit 0
$Principal = New-ScheduledTaskPrincipal -UserId "$env:USERNAME" -LogonType Interactive -RunLevel Highest

Register-ScheduledTask -TaskName "CortexMemoryEngine" -Action $Action -Trigger $Trigger -Settings $Settings -Principal $Principal -Force

echo "Done! Cortex Memory Engine is now registered to start automatically at logon."
