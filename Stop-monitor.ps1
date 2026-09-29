$ErrorActionPreference = 'Stop'
$monitorData = Join-Path $PSScriptRoot 'data'
New-Item -ItemType Directory -Path $monitorData -Force | Out-Null
Set-Content -LiteralPath (Join-Path $monitorData 'stop') -Value 'stop' -Encoding ascii
Write-Output 'Stop requested. The local usage monitor will stop after finishing its current file.'
