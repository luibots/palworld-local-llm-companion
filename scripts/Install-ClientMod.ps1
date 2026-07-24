param(
  [string]$PalworldPath = 'C:\Program Files (x86)\Steam\steamapps\common\Palworld'
)

$ErrorActionPreference = 'Stop'
$source = Join-Path $PSScriptRoot '..\mods\PalCompanionUI'
$ue4ss = Join-Path $PalworldPath 'Mods\NativeMods\UE4SS'
$destination = Join-Path $ue4ss 'Mods\PalCompanionUI'
$modsFile = Join-Path $ue4ss 'Mods\mods.txt'

if (-not (Test-Path (Join-Path $PalworldPath 'Palworld.exe'))) {
  throw "Palworld was not found at: $PalworldPath"
}
if (-not (Test-Path $ue4ss)) {
  throw @"
UE4SS is not installed in Palworld's official NativeMods location.
Subscribe to and enable 'UE4SS Experimental (Palworld)' in Steam Workshop first,
launch Palworld once, close it, and run this installer again.
"@
}
if (Get-Process Palworld-Win64-Shipping -ErrorAction SilentlyContinue) {
  throw 'Close Palworld before installing the UI mod.'
}

New-Item -ItemType Directory -Force (Split-Path $destination) | Out-Null
Copy-Item -LiteralPath $source -Destination $destination -Recurse -Force

$lines = if (Test-Path $modsFile) { @(Get-Content -LiteralPath $modsFile) } else { @() }
$lines = @($lines | Where-Object { $_ -notmatch '^\s*PalCompanionUI\s*:' })
$lines += 'PalCompanionUI : 1'
[IO.File]::WriteAllLines($modsFile, $lines, [Text.UTF8Encoding]::new($false))

Write-Host "Installed Pal Companion UI to: $destination"
Write-Host 'Start the local companion API, launch Palworld, enter a world, and press F2.'
