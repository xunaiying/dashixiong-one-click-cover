$ErrorActionPreference = "Stop"

$Root = Split-Path -Parent $MyInvocation.MyCommand.Path
$LogDir = Join-Path $Root "logs"
$LogPath = Join-Path $LogDir "launcher-install.log"
$MinicondaDir = Join-Path $env:USERPROFILE "Miniconda3"
$CondaExe = Join-Path $MinicondaDir "Scripts\conda.exe"
$CondaBat = Join-Path $MinicondaDir "condabin\conda.bat"
$EnvDir = Join-Path $Root "env"
$Installer = Join-Path $env:TEMP "applio-miniconda.exe"
$MinicondaUrl = "https://repo.anaconda.com/miniconda/Miniconda3-py312_25.11.1-1-Windows-x86_64.exe"

New-Item -ItemType Directory -Force -Path $LogDir | Out-Null

function Write-Step {
    param([string]$Message)
    $line = "[$(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')] $Message"
    Write-Host $line
    Add-Content -Path $LogPath -Value $line -Encoding UTF8
}

function Invoke-Logged {
    param(
        [string]$FilePath,
        [string[]]$ArgumentList,
        [string]$StepName
    )

    Write-Step $StepName
    Add-Content -Path $LogPath -Value "COMMAND: $FilePath $($ArgumentList -join ' ')" -Encoding UTF8
    $process = Start-Process -FilePath $FilePath -ArgumentList $ArgumentList -WorkingDirectory $Root -NoNewWindow -PassThru -Wait -RedirectStandardOutput "$LogPath.out" -RedirectStandardError "$LogPath.err"
    if (Test-Path "$LogPath.out") {
        Get-Content "$LogPath.out" -ErrorAction SilentlyContinue | Add-Content -Path $LogPath -Encoding UTF8
        Remove-Item "$LogPath.out" -Force -ErrorAction SilentlyContinue
    }
    if (Test-Path "$LogPath.err") {
        Get-Content "$LogPath.err" -ErrorAction SilentlyContinue | Add-Content -Path $LogPath -Encoding UTF8
        Remove-Item "$LogPath.err" -Force -ErrorAction SilentlyContinue
    }
    if ($process.ExitCode -ne 0) {
        throw "$StepName failed with exit code $($process.ExitCode). See $LogPath"
    }
}

Write-Step "Applio environment installation started."

if (-not (Test-Path $CondaExe)) {
    Write-Step "Miniconda not found. Downloading installer."
    Invoke-WebRequest -Uri $MinicondaUrl -OutFile $Installer
    Invoke-Logged -FilePath $Installer -ArgumentList @("/InstallationType=JustMe", "/RegisterPython=0", "/S", "/D=$MinicondaDir") -StepName "Installing Miniconda"
} else {
    Write-Step "Miniconda already exists at $MinicondaDir"
}

if (-not (Test-Path (Join-Path $EnvDir "python.exe"))) {
    Invoke-Logged -FilePath $CondaExe -ArgumentList @("create", "--override-channels", "--channel", "conda-forge", "--no-shortcuts", "-y", "-k", "--prefix", $EnvDir, "python=3.12") -StepName "Creating Conda env"
} else {
    Write-Step "Conda env already exists at $EnvDir"
}

$EnvPython = Join-Path $EnvDir "python.exe"
Invoke-Logged -FilePath $EnvPython -ArgumentList @("-m", "pip", "install", "uv") -StepName "Installing uv"
Invoke-Logged -FilePath $EnvPython -ArgumentList @("-m", "uv", "pip", "install", "-r", (Join-Path $Root "requirements.txt"), "--extra-index-url", "https://download.pytorch.org/whl/cu128", "--index-strategy", "unsafe-best-match") -StepName "Installing Applio dependencies"
Invoke-Logged -FilePath $EnvPython -ArgumentList @("-m", "uv", "pip", "install", "demucs") -StepName "Installing one-click cover dependencies"

Write-Step "Applio environment installation finished."
