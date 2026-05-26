# 设置每日自动更新 Windows 计划任务
# 以管理员身份运行此脚本: 右键 -> 以管理员身份运行 PowerShell

$pythonPath = (Get-Command python).Source
$scriptPath = "f:\Program Files\claude code\smart-stock\backend\scripts\daily_update.py"
$workDir = "f:\Program Files\claude code\smart-stock"
$taskName = "SmartStockDailyUpdate"

# 创建计划任务 (每天 18:00 执行)
$action = New-ScheduledTaskAction -Execute $pythonPath -Argument "`"$scriptPath`"" -WorkingDirectory $workDir
$trigger = New-ScheduledTaskTrigger -Daily -At "18:00"
$principal = New-ScheduledTaskPrincipal -UserId "$env:USERNAME" -RunLevel Highest
$settings = New-ScheduledTaskSettingsSet `
    -AllowStartIfOnBatteries `
    -DontStopIfGoingOnBatteries `
    -StartWhenAvailable `
    -MultipleInstances IgnoreNew `
    -ExecutionTimeLimit (New-TimeSpan -Minutes 120)

Register-ScheduledTask -TaskName $taskName `
    -Action $action `
    -Trigger $trigger `
    -Principal $principal `
    -Settings $settings `
    -Description "每天18:00自动更新A股K线数据并扫描信号" `
    -Force

Write-Output "任务 '$taskName' 已创建成功!"
Write-Output ""
Write-Output "管理命令:"
Write-Output "  查看任务: Get-ScheduledTask -TaskName '$taskName'"
Write-Output "  手动执行: Start-ScheduledTask -TaskName '$taskName'"
Write-Output "  删除任务: Unregister-ScheduledTask -TaskName '$taskName' -Confirm:`$false"
Write-Output "  查看日志: Get-WinEvent -LogName 'Microsoft-Windows-TaskScheduler/Operational' | Where-Object Message -match '$taskName' | Select-Object -First 10"
