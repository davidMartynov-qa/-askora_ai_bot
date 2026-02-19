$ErrorActionPreference = "Stop"

Set-Location -Path $PSScriptRoot

# Stop previous bot/admin processes for clean restart.
$py = Get-CimInstance Win32_Process -Filter "name='python.exe'"
foreach ($p in $py) {
    $cmd = [string]$p.CommandLine
    if ($cmd -like "*bot.py*" -or $cmd -like "*admin_app.py*") {
        try {
            Stop-Process -Id $p.ProcessId -Force -ErrorAction Stop
        } catch {
        }
    }
}

# Start bot and admin panel.
Start-Process -FilePath python `
    -ArgumentList "bot.py" `
    -WorkingDirectory $PSScriptRoot `
    -RedirectStandardOutput (Join-Path $PSScriptRoot "bot.out.log") `
    -RedirectStandardError (Join-Path $PSScriptRoot "bot.err.log")

Start-Process -FilePath python `
    -ArgumentList "admin_app.py" `
    -WorkingDirectory $PSScriptRoot `
    -RedirectStandardOutput (Join-Path $PSScriptRoot "admin.out.log") `
    -RedirectStandardError (Join-Path $PSScriptRoot "admin.err.log")

Start-Sleep -Seconds 1

Write-Host "Bot stack started."
Write-Host "Bot logs:   $PSScriptRoot\\bot.out.log / bot.err.log"
Write-Host "Admin logs: $PSScriptRoot\\admin.out.log / admin.err.log"
