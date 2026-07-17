$ErrorActionPreference = "Stop"

$rootDir = (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path
$openScript = Join-Path $rootDir "k8s\scripts\open-dev.sh"

if (-not (Test-Path $openScript)) {
  throw "Could not find port-forward helper at $openScript"
}

$wslExe = Get-Command wsl.exe -ErrorAction SilentlyContinue
if (-not $wslExe) {
  throw "wsl.exe is not available. Install or enable WSL first."
}

$distro = $env:YOTOWEBMGR_WSL_DISTRO
if (-not $distro) {
  $defaultDistro = (& wsl.exe -l -q | Where-Object { $_.Trim() } | Select-Object -First 1)
  if (-not $defaultDistro) {
    throw "No WSL distro is installed. Set YOTOWEBMGR_WSL_DISTRO after installing one."
  }
  $distro = $defaultDistro.Trim()
}

$drive = $rootDir.Substring(0, 1).ToLowerInvariant()
$relativePath = $rootDir.Substring(2).Replace("\", "/")
$wslRootDir = "/mnt/$drive$relativePath"
$bindAddress = $env:YOTOWEBMGR_BIND_ADDRESS
$wslCommand = if ($bindAddress) {
  "cd '$wslRootDir' && BIND_ADDRESS='$bindAddress' ./k8s/scripts/open-dev.sh"
} else {
  "cd '$wslRootDir' && ./k8s/scripts/open-dev.sh"
}

Write-Host "Using WSL distro: $distro"
Write-Host "Refreshing frontend port-forward from: $wslRootDir"
if ($bindAddress) {
  Write-Host "Using bind address: $bindAddress"
}

& wsl.exe -d $distro -- bash -lc $wslCommand
if ($LASTEXITCODE -ne 0) {
  throw "WSL port-forward command failed with exit code $LASTEXITCODE"
}
