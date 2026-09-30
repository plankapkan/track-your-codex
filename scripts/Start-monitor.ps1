param([switch]$NoBrowser, [int]$Port = 8766)
$ErrorActionPreference = 'Stop'
$monitorRoot = Split-Path -Parent $PSScriptRoot
$monitorData = Join-Path $monitorRoot 'data'
$monitorUrl = "http://127.0.0.1:$Port/"
$monitorReady = $false
try {
    $monitorHealth = Invoke-RestMethod -Uri "${monitorUrl}api/health" -TimeoutSec 2
    if ($monitorHealth.service -ne 'codex-usage-monitor') { throw 'This port belongs to another service.' }
    $monitorReady = $true
} catch {
    if ($_.Exception.Message -eq 'This port belongs to another service.') { throw }
}
if (-not $monitorReady) {
    $monitorPython = Join-Path $env:USERPROFILE '.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe'
    if (-not (Test-Path -LiteralPath $monitorPython)) {
        $monitorPython = (Get-Command python -ErrorAction Stop).Source
    }
    New-Item -ItemType Directory -Path $monitorData -Force | Out-Null
    $monitorArgs = @('-m', 'token_tracker', '--data', ('"' + $monitorData + '"'), '--port', "$Port")
    $monitorProcess = Start-Process -FilePath $monitorPython -ArgumentList $monitorArgs -WorkingDirectory $monitorRoot -WindowStyle Hidden -PassThru -RedirectStandardOutput (Join-Path $monitorData 'monitor.log') -RedirectStandardError (Join-Path $monitorData 'monitor-error.log')
    for ($monitorAttempt = 0; $monitorAttempt -lt 50; $monitorAttempt++) {
        Start-Sleep -Milliseconds 200
        try {
            $monitorHealth = Invoke-RestMethod -Uri "${monitorUrl}api/health" -TimeoutSec 1
            if ($monitorHealth.service -eq 'codex-usage-monitor') { $monitorReady = $true; break }
        } catch {}
        if ($monitorProcess.HasExited) { break }
    }
    if (-not $monitorReady) { throw "Monitor did not start. See $monitorData\monitor-error.log" }
}
Write-Output "Codex usage monitor: $monitorUrl"
if (-not $NoBrowser) { Start-Process $monitorUrl }
