Set WshShell = CreateObject("WScript.Shell")
' 0 代表隱藏視窗運行 headless_startup.bat
WshShell.Run Chr(34) & "d:\Projects\Antigravity\AI_mem_system\headless_startup.bat" & Chr(34), 0
Set WshShell = Nothing
