$ErrorActionPreference = "Stop"
$workspaceRoot = $PSScriptRoot
$buildStamp = Get-Date -Format "yyyyMMdd-HHmmss"
$appName = "chikuchiku_denden"
$tempRoot = Join-Path $env:TEMP ($appName + "-pyinstaller-" + $buildStamp)
$workPath = Join-Path $tempRoot "build"
$tempDistPath = Join-Path $tempRoot "dist"
$finalDistDir = Join-Path $workspaceRoot "dist"
$finalBundleDir = Join-Path $finalDistDir $appName
$fallbackBundleDir = Join-Path $finalDistDir ($appName + "-" + $buildStamp)
$releaseRootDir = Join-Path $workspaceRoot "release"
$releaseBundleDir = Join-Path $releaseRootDir $appName
$fallbackReleaseBundleDir = Join-Path $releaseRootDir ($appName + "-" + $buildStamp)
$distributionReadme = Join-Path $workspaceRoot "RELEASE_README.txt"

# PyInstaller cannot overwrite the output .exe while it is running.
$runningExe = Get-Process -Name $appName -ErrorAction SilentlyContinue
if ($runningExe) {
  Write-Host "Stopping running $appName.exe before rebuild..."
  $runningExe | Stop-Process -Force
  Start-Sleep -Seconds 2
}

python -m PyInstaller `
  --noconfirm `
  --clean `
  --workpath $workPath `
  --distpath $tempDistPath `
  --onedir `
  --name $appName `
  --collect-all streamlit `
  --collect-all altair `
  --collect-all pyarrow `
  --collect-all watchdog `
  --add-data "app.py;." `
  --add-data "__init__.py;." `
  --add-data "calculators.py;." `
  --add-data "io_utils.py;." `
  --add-data "models.py;." `
  --add-data "resource_paths.py;." `
  --add-data "ui_components.py;." `
  --add-data "engine;engine" `
  --add-data "defaults;defaults" `
  --add-data "assets;assets" `
  run_exe.py

$builtBundleDir = Join-Path $tempDistPath $appName
if (-not (Test-Path -LiteralPath $builtBundleDir)) {
  throw "Build finished without producing $builtBundleDir"
}

$finalized = $false
if (Test-Path -LiteralPath $finalBundleDir) {
  for ($attempt = 1; $attempt -le 5 -and -not $finalized; $attempt++) {
    try {
      Remove-Item -LiteralPath $finalBundleDir -Recurse -Force
      Copy-Item -LiteralPath $builtBundleDir -Destination $finalBundleDir -Recurse
      $finalized = $true
    }
    catch {
      if ($attempt -lt 5) {
        Start-Sleep -Seconds 1
      }
    }
  }
}
else {
  Copy-Item -LiteralPath $builtBundleDir -Destination $finalBundleDir -Recurse
  $finalized = $true
}

if (-not $finalized) {
  Copy-Item -LiteralPath $builtBundleDir -Destination $fallbackBundleDir -Recurse
  $packagedBundleDir = $fallbackBundleDir
  Write-Warning "Could not replace $finalBundleDir because Windows still denies access. Saved the new build to $fallbackBundleDir"
}
else {
  $packagedBundleDir = $finalBundleDir
  Write-Host "Build available at $finalBundleDir"
}

$releaseSourceDir = if ($packagedBundleDir) { $packagedBundleDir } else { $builtBundleDir }
$releasePrepared = $false

New-Item -ItemType Directory -Path $releaseRootDir -Force | Out-Null

if (Test-Path -LiteralPath $releaseBundleDir) {
  for ($attempt = 1; $attempt -le 5 -and -not $releasePrepared; $attempt++) {
    try {
      Remove-Item -LiteralPath $releaseBundleDir -Recurse -Force
      Copy-Item -LiteralPath $releaseSourceDir -Destination $releaseBundleDir -Recurse
      $releasePrepared = $true
    }
    catch {
      if ($attempt -lt 5) {
        Start-Sleep -Seconds 1
      }
    }
  }
}
else {
  Copy-Item -LiteralPath $releaseSourceDir -Destination $releaseBundleDir -Recurse
  $releasePrepared = $true
}

if (-not $releasePrepared) {
  Copy-Item -LiteralPath $releaseSourceDir -Destination $fallbackReleaseBundleDir -Recurse
  $releaseBundleDir = $fallbackReleaseBundleDir
  Write-Warning "Could not replace the release folder. Saved the distribution-ready bundle to $fallbackReleaseBundleDir"
}

if (Test-Path -LiteralPath $distributionReadme) {
  Copy-Item -LiteralPath $distributionReadme -Destination (Join-Path $releaseBundleDir "README.txt") -Force
}

Write-Host "Distribution-ready folder: $releaseBundleDir"
