[CmdletBinding()]
param(
  [switch]$Check,
  [switch]$Once,
  [int]$RestartDelaySeconds = 10
)

$ErrorActionPreference = 'Stop'
$projectRoot = (Resolve-Path -LiteralPath (Join-Path $PSScriptRoot '..')).Path
$executable = Join-Path $projectRoot '.venv\Scripts\pal-companion.exe'
$logDirectory = Join-Path $env:APPDATA 'com.luibots.palcompanion'
$logPath = Join-Path $logDirectory 'service.log'

if ($Check) {
  Write-Host '=== PAL COMPANION SERVICE CHECK ==='
  Write-Host ("  executable : {0}" -f $(if (Test-Path $executable) { 'found' } else { 'MISSING' }))
  try {
    $health = Invoke-RestMethod -Uri 'http://127.0.0.1:8765/health' -TimeoutSec 2
    Write-Host ("  API health : {0}" -f $health.status)
  }
  catch {
    Write-Host '  API health : offline'
  }
  return
}

if (-not (Test-Path $executable)) {
  throw "Pal Companion executable not found at $executable"
}

New-Item -ItemType Directory -Force -Path $logDirectory | Out-Null
$mutex = [Threading.Mutex]::new($false, 'Local\PalCompanionApi')
$ownsMutex = $false
try {
  try {
    $ownsMutex = $mutex.WaitOne(0, $false)
  }
  catch [Threading.AbandonedMutexException] {
    $ownsMutex = $true
  }
  if (-not $ownsMutex) {
    Write-Host 'Pal Companion API is already supervised by another process.'
    return
  }

  do {
    ("[{0}] --- companion API starting ---" -f (Get-Date -Format 'yyyy-MM-dd HH:mm:ss')) |
      Add-Content -LiteralPath $logPath -Encoding utf8
    $ErrorActionPreference = 'Continue'
    Push-Location $projectRoot
    try {
      & $executable api *>&1 | Out-File -LiteralPath $logPath -Append -Encoding utf8
      $exitCode = $LASTEXITCODE
    }
    finally {
      Pop-Location
      $ErrorActionPreference = 'Stop'
    }
    ("[{0}] --- companion API exited ({1}); {2} ---" -f (
      Get-Date -Format 'yyyy-MM-dd HH:mm:ss'
    ), $exitCode, $(if ($Once) { 'supervisor stopping' } else { 'restarting' })) |
      Add-Content -LiteralPath $logPath -Encoding utf8
    if (-not $Once) {
      Start-Sleep -Seconds ([Math]::Max(2, $RestartDelaySeconds))
    }
  } while (-not $Once)
}
finally {
  if ($ownsMutex) {
    $mutex.ReleaseMutex()
  }
  $mutex.Dispose()
}
