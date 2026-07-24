[CmdletBinding()]
param(
  [string]$GamePak = 'C:\Program Files (x86)\Steam\steamapps\common\Palworld\Pal\Content\Paks\Pal-Windows.pak',
  [string]$ToolsDir = '',
  [switch]$SkipIndex
)

$ErrorActionPreference = 'Stop'
$root = Split-Path $PSScriptRoot -Parent
if (-not $ToolsDir) {
  $ToolsDir = Join-Path (Split-Path $root -Parent) 'pal-command\tools'
}
$repak = Join-Path $ToolsDir 'repak.exe'
$uassetGui = Join-Path $ToolsDir 'UAssetGUI.exe'
$mapping = Join-Path $ToolsDir 'Mappings.usmap'
$python = Join-Path $root '.venv\Scripts\python.exe'
$privateRoot = Join-Path $root 'data\private'
$extractRoot = Join-Path $privateRoot 'extracted'
$tablesRoot = Join-Path $privateRoot 'tables'
$jsonl = Join-Path $privateRoot 'palworld-game-data.jsonl'

foreach ($required in @($GamePak, $repak, $uassetGui, $mapping, $python)) {
  if (-not (Test-Path $required)) {
    throw "Required file not found: $required"
  }
}

$mapDir = Join-Path $env:LOCALAPPDATA 'UAssetGUI\Mappings'
New-Item -ItemType Directory -Force -Path $mapDir | Out-Null
Copy-Item -LiteralPath $mapping -Destination (Join-Path $mapDir 'Palworld.usmap') -Force
New-Item -ItemType Directory -Force -Path $extractRoot, $tablesRoot | Out-Null

$assets = @(
  'Pal/Content/Pal/DataTable/Character/DT_PalMonsterParameter',
  'Pal/Content/L10N/en/Pal/DataTable/Text/DT_PalNameText_Common',
  'Pal/Content/L10N/en/Pal/DataTable/Text/DT_PalLongDescriptionText',
  'Pal/Content/Pal/DataTable/Item/DT_ItemDataTable',
  'Pal/Content/L10N/en/Pal/DataTable/Text/DT_ItemNameText_Common',
  'Pal/Content/L10N/en/Pal/DataTable/Text/DT_ItemDescriptionText_Common',
  'Pal/Content/Pal/DataTable/Item/DT_ItemRecipeDataTable',
  'Pal/Content/Pal/DataTable/Character/DT_PalDropItem',
  'Pal/Content/Pal/DataTable/Spawner/DT_PalWildSpawner',
  'Pal/Content/Pal/DataTable/Spawner/DT_PalSpawnerPlacement'
)

$unpackArguments = @('unpack', '-q', '-f', '-o', $extractRoot)
foreach ($asset in $assets) {
  $unpackArguments += @('-i', "$asset.uasset", '-i', "$asset.uexp")
}
$unpackArguments += $GamePak
& $repak @unpackArguments
if ($LASTEXITCODE -ne 0) {
  throw "repak failed with exit code $LASTEXITCODE."
}

foreach ($asset in $assets) {
  $assetPath = Join-Path $extractRoot (($asset -replace '/', '\') + '.uasset')
  $tableName = Split-Path $asset -Leaf
  $jsonPath = Join-Path $tablesRoot "$tableName.json"
  Remove-Item -LiteralPath $jsonPath -Force -ErrorAction SilentlyContinue
  $process = Start-Process -FilePath $uassetGui -ArgumentList @(
    'tojson', $assetPath, $jsonPath, 'VER_UE5_1', 'Palworld'
  ) -Wait -PassThru
  if ($process.ExitCode -ne 0 -or -not (Test-Path $jsonPath)) {
    throw "UAssetGUI did not convert $tableName (exit code $($process.ExitCode))."
  }
}

$manifest = 'C:\Program Files (x86)\Steam\steamapps\appmanifest_1623730.acf'
$gameBuild = 'unknown'
if (Test-Path $manifest) {
  $match = [regex]::Match((Get-Content $manifest -Raw), '"buildid"\s+"([^"]+)"')
  if ($match.Success) {
    $gameBuild = $match.Groups[1].Value
  }
}

Push-Location $root
try {
  & $python -m pal_companion.cli game-data `
    --tables-dir $tablesRoot `
    --output $jsonl `
    --game-build $gameBuild
  if ($LASTEXITCODE -ne 0) {
    throw 'Private game-data document generation failed.'
  }
  if (-not $SkipIndex) {
    & $python -m pal_companion.cli ingest $jsonl --replace-prefix 'game:'
    if ($LASTEXITCODE -ne 0) {
      throw 'Ollama indexing failed.'
    }
  }
}
finally {
  Pop-Location
}

Write-Host "Private game data ready: $jsonl"
