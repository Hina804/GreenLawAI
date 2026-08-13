# Auto-restart new_documents pipeline until target time if python exits unexpectedly.
$ErrorActionPreference = "Continue"
$Root = "E:\GL_AI"
$Until = (Get-Date).Date.AddHours(10)
if ((Get-Date) -ge $Until) { $Until = $Until.AddDays(1) }
$LogDir = "$Root\data_processed\new_documents"
$Log = "$LogDir\watchdog.log"
$Runner = "$Root\scripts\run_pipeline_detached.ps1"
New-Item -ItemType Directory -Force -Path $LogDir | Out-Null

function Write-Log($msg) {
    $line = "$(Get-Date -Format o) $msg"
    $line | Out-File -FilePath $Log -Append -Encoding utf8
}

Write-Log "Watchdog started; will monitor until $Until"

while ((Get-Date) -lt $Until) {
    $py = Get-Process -Name python -ErrorAction SilentlyContinue
    if (-not $py) {
        Write-Log "python.exe not found — restarting detached pipeline"
        Start-Process powershell -ArgumentList @(
            "-NoProfile", "-ExecutionPolicy", "Bypass",
            "-File", $Runner
        ) -WorkingDirectory $Root -WindowStyle Hidden
        Start-Sleep -Seconds 30
    }
    Start-Sleep -Seconds 120
}

Write-Log "Watchdog finished (reached $Until)"
