$ErrorActionPreference = "Stop"

$rootDir = (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path
$deployScript = Join-Path $rootDir "k8s\scripts\deploy-dev.sh"

if (-not (Test-Path $deployScript)) {
  throw "Could not find deploy script at $deployScript"
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
$quotedArgs = @($args | ForEach-Object {
  "'" + ($_ -replace "'", "'\"'\"'") + "'"
}) -join " "
$bindAddress = $env:YOTOWEBMGR_BIND_ADDRESS
$bindPrefix = if ($bindAddress) {
  "BIND_ADDRESS='$bindAddress' "
} else {
  ""
}
$wslCommand = if ($quotedArgs) {
  "cd '$wslRootDir' && ${bindPrefix}./k8s/scripts/deploy-dev.sh $quotedArgs"
} else {
  "cd '$wslRootDir' && ${bindPrefix}./k8s/scripts/deploy-dev.sh"
}

Write-Host "Using WSL distro: $distro"
Write-Host "Running destructive MicroK8s redeploy from: $wslRootDir"
if ($bindAddress) {
  Write-Host "Using bind address: $bindAddress"
}

& wsl.exe -d $distro -- bash -lc $wslCommand
if ($LASTEXITCODE -ne 0) {
  throw "WSL deploy command failed with exit code $LASTEXITCODE"
}
