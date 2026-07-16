$ErrorActionPreference = "Stop"

$androidProjectDir = Join-Path $PSScriptRoot "..\android"
$sdkRoot = $env:ANDROID_SDK_ROOT
$javaHome = $env:JAVA_HOME
$studioJbr = "C:\Program Files\Android\Android Studio\jbr"

if (-not $sdkRoot) {
  $defaultSdkRoot = Join-Path $env:LOCALAPPDATA "Android\Sdk"

  if (Test-Path $defaultSdkRoot) {
    $sdkRoot = $defaultSdkRoot
  }
}

if (-not $sdkRoot) {
  throw "ANDROID_SDK_ROOT is not set and no SDK was found under $env:LOCALAPPDATA\Android\Sdk"
}

$env:ANDROID_SDK_ROOT = $sdkRoot
$env:ANDROID_HOME = $sdkRoot

if (-not $javaHome -and (Test-Path (Join-Path $studioJbr "bin\java.exe"))) {
  $javaHome = $studioJbr
}

if (-not $javaHome) {
  throw "JAVA_HOME is not set and Android Studio JBR was not found."
}

$env:JAVA_HOME = $javaHome

$gradleWrapper = Join-Path $androidProjectDir "gradlew.bat"

if (-not (Test-Path $gradleWrapper)) {
  throw "Could not find Android Gradle wrapper at $gradleWrapper. Run 'npm run android:sync' first."
}

Push-Location $androidProjectDir

try {
  & $gradleWrapper assembleDebug
}
finally {
  Pop-Location
}
