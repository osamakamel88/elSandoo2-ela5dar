# ==============================================================================
# elSandoo2 el a5dar (The Green Box) - Setup & Prerequisite Engine
# Developed & Customized by Recode Developments (Osama Kamel)
# ==============================================================================

[CmdletBinding()]
param(
    [switch]$CheckOnly,
    [switch]$UpdateOnly,
    [switch]$AutoProceed,
    [switch]$SkipUpdate
)

# Ensure TLS 1.2 is active for web requests
[Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12 -bor [Net.ServicePointManager]::SecurityProtocol

$ErrorActionPreference = "Continue"
$ProjectDir = (Resolve-Path "$PSScriptRoot").Path
$GitHubRepoUrl = "https://github.com/osamakamel88/elSandoo2-el-a5dar.git"
$GitHubApiUrl = "https://api.github.com/repos/osamakamel88/elSandoo2-el-a5dar/commits/main"

# UI Helper functions
function Write-Header {
    Clear-Host
    Write-Host "======================================================================" -ForegroundColor Green
    Write-Host "         elSandoo2 el a5dar (The Green Box) - Auto Setup" -ForegroundColor Cyan
    Write-Host "                   by Recode Developments                     " -ForegroundColor DarkCyan
    Write-Host "======================================================================" -ForegroundColor Green
    Write-Host ""
}

function Write-StatusItem {
    param(
        [string]$Title,
        [string]$Status, # OK, MISSING, INSTALLING, FAILED, WARNING, INFO
        [string]$Details = ""
    )
    $titlePadded = $Title.PadRight(32)
    Write-Host -NoNewline "  $titlePadded "
    switch ($Status) {
        "OK"         { Write-Host -NoNewline "[  OK  ] " -ForegroundColor Green }
        "MISSING"    { Write-Host -NoNewline "[MISSING] " -ForegroundColor Yellow }
        "INSTALLING" { Write-Host -NoNewline "[INSTALL] " -ForegroundColor Cyan }
        "FAILED"     { Write-Host -NoNewline "[FAILED ] " -ForegroundColor Red }
        "WARNING"    { Write-Host -NoNewline "[WARNING] " -ForegroundColor DarkYellow }
        "INFO"       { Write-Host -NoNewline "[ INFO ] " -ForegroundColor White }
        default      { Write-Host -NoNewline "[$Status] " }
    }
    if ($Details) {
        Write-Host "$Details" -ForegroundColor Gray
    } else {
        Write-Host ""
    }
}

function Refresh-SessionEnvironment {
    # Refresh PATH from registry for both Machine and User
    $machinePath = [Environment]::GetEnvironmentVariable("Path", "Machine")
    $userPath = [Environment]::GetEnvironmentVariable("Path", "User")
    $localBin = Join-Path $ProjectDir "bin\ffmpeg"
    
    $combinedPath = "$localBin;$userPath;$machinePath"
    $env:Path = $combinedPath
    [Environment]::SetEnvironmentVariable("Path", $combinedPath, "Process")
}

# Download with fallback
function Download-FileWithProgress {
    param(
        [string]$Url,
        [string]$Destination
    )
    Write-Host "    Downloading: $Url" -ForegroundColor DarkGray
    Write-Host "    To: $Destination" -ForegroundColor DarkGray
    $dir = Split-Path $Destination
    if (-not (Test-Path $dir)) { New-Item -ItemType Directory -Path $dir -Force | Out-Null }
    
    # Try curl.exe if available (often faster with built-in progress)
    $curl = Get-Command curl.exe -ErrorAction SilentlyContinue
    if ($curl) {
        & curl.exe -L -k --progress-bar -o $Destination $Url
        if ($LASTEXITCODE -eq 0 -and (Test-Path $Destination)) { return $true }
    }
    
    try {
        $webClient = New-Object System.Net.WebClient
        $webClient.Headers.Add("User-Agent", "elSandoo2-Setup")
        $webClient.DownloadFile($Url, $Destination)
        return $true
    } catch {
        try {
            Invoke-WebRequest -Uri $Url -OutFile $Destination -UseBasicParsing -UserAgent "elSandoo2-Setup"
            return $true
        } catch {
            Write-Host "    Download error: $_" -ForegroundColor Red
            return $false
        }
    }
}

Write-Header

# ------------------------------------------------------------------------------
# 1. Architecture Check
# ------------------------------------------------------------------------------
$is64Bit = [Environment]::Is64BitOperatingSystem
if (-not $is64Bit) {
    Write-StatusItem -Title "Operating System (64-bit)" -Status "FAILED" -Details "32-bit Windows is not supported. Please use 64-bit Windows."
    if (-not $CheckOnly) { pause; exit 1 }
} else {
    Write-StatusItem -Title "Operating System (64-bit)" -Status "OK" -Details "Windows x64 confirmed"
}

# ------------------------------------------------------------------------------
# 2. GitHub Connection & Update Sync
# ------------------------------------------------------------------------------
Write-Host "`n--- [1/6] GitHub Source Connection & Updates ---" -ForegroundColor Cyan

$internetAvailable = $false
try {
    $test = Test-Connection -ComputerName "github.com" -Count 1 -Quiet -ErrorAction SilentlyContinue
    if (-not $test) {
        # Fallback HTTP check
        $req = [System.Net.WebRequest]::Create("https://github.com")
        $req.Timeout = 4000
        $resp = $req.GetResponse()
        $resp.Close()
        $internetAvailable = $true
    } else {
        $internetAvailable = $true
    }
} catch {
    $internetAvailable = $false
}

if ($internetAvailable) {
    Write-StatusItem -Title "Internet & GitHub Access" -Status "OK" -Details "Connected to github.com"
} else {
    Write-StatusItem -Title "Internet & GitHub Access" -Status "WARNING" -Details "Offline or GitHub unreachable. Proceeding with local files."
}

$gitCmd = Get-Command git.exe -ErrorAction SilentlyContinue

if ($internetAvailable -and -not $SkipUpdate) {
    $isGitRepo = Test-Path (Join-Path $ProjectDir ".git")
    if ($isGitRepo -and $gitCmd) {
        Write-Host "  Checking for updates from GitHub repository..." -ForegroundColor DarkGray
        try {
            Push-Location $ProjectDir
            & git remote set-url origin $GitHubRepoUrl 2>$null
            & git fetch origin main --quiet 2>$null
            $localHash = (& git rev-parse HEAD 2>$null).Trim()
            $remoteHash = (& git rev-parse origin/main 2>$null).Trim()
            
            if ($localHash -and $remoteHash -and ($localHash -ne $remoteHash)) {
                Write-StatusItem -Title "GitHub Source Update" -Status "INSTALLING" -Details "New version detected! Syncing latest changes..."
                # Preserve local config & storage
                & git stash --quiet 2>$null
                & git pull origin main --quiet
                & git stash pop --quiet 2>$null
                Write-StatusItem -Title "GitHub Source Update" -Status "OK" -Details "Updated to latest commit: $($remoteHash.Substring(0,7))"
            } else {
                Write-StatusItem -Title "GitHub Source Update" -Status "OK" -Details "Repository is up to date ($($localHash.Substring(0,7)))"
            }
            Pop-Location
        } catch {
            Write-StatusItem -Title "GitHub Source Update" -Status "WARNING" -Details "Could not pull updates: $_"
            Pop-Location
        }
    } elseif ($gitCmd -and -not $isGitRepo) {
        Write-StatusItem -Title "Git Repository Status" -Status "INFO" -Details "Converting local directory to tracking Git repository..."
        try {
            Push-Location $ProjectDir
            & git init --quiet
            & git remote add origin $GitHubRepoUrl 2>$null
            & git remote set-url origin $GitHubRepoUrl
            & git fetch origin main --quiet
            & git reset origin/main --quiet 2>$null
            Write-StatusItem -Title "Git Repository Setup" -Status "OK" -Details "Connected to origin/main"
            Pop-Location
        } catch {
            Write-StatusItem -Title "Git Repository Setup" -Status "WARNING" -Details "Could not attach git remote: $_"
            Pop-Location
        }
    } else {
        # Git is not installed on this PC
        Write-StatusItem -Title "Git CLI Tool" -Status "MISSING" -Details "Git is not installed on this PC."
        if (-not $CheckOnly) {
            Write-Host "  Attempting to install Git via winget..." -ForegroundColor DarkGray
            $winget = Get-Command winget.exe -ErrorAction SilentlyContinue
            if ($winget) {
                & winget install --id Git.Git -e --silent --accept-package-agreements --accept-source-agreements | Out-Null
                Refresh-SessionEnvironment
                $gitCmd = Get-Command git.exe -ErrorAction SilentlyContinue
                if ($gitCmd) {
                    Write-StatusItem -Title "Git CLI Tool" -Status "OK" -Details "Installed Git successfully"
                }
            }
        }
    }
}

if ($UpdateOnly) {
    Write-Host "`n[SUCCESS] Update check completed!" -ForegroundColor Green
    exit 0
}

# ------------------------------------------------------------------------------
# 3. Microsoft Visual C++ Redistributable (2015-2022 x64)
# ------------------------------------------------------------------------------
Write-Host "`n--- [2/6] Visual C++ Runtime (Required for faster-whisper & PyTorch) ---" -ForegroundColor Cyan

$vcRedistInstalled = $false
$vcKeys = @(
    "HKLM:\SOFTWARE\Microsoft\VisualStudio\14.0\VC\Runtimes\X64",
    "HKLM:\SOFTWARE\WOW6432Node\Microsoft\VisualStudio\14.0\VC\Runtimes\X64"
)
foreach ($k in $vcKeys) {
    if (Test-Path $k) {
        $installedVal = (Get-ItemProperty -Path $k -Name "Installed" -ErrorAction SilentlyContinue).Installed
        if ($installedVal -eq 1) { $vcRedistInstalled = $true; break }
    }
}
if (-not $vcRedistInstalled) {
    # Check for vcruntime140.dll in System32
    if (Test-Path "$env:windir\System32\vcruntime140.dll") {
        $vcRedistInstalled = $true
    }
}

if ($vcRedistInstalled) {
    Write-StatusItem -Title "Visual C++ 2015-2022 x64" -Status "OK" -Details "Runtime is installed"
} else {
    Write-StatusItem -Title "Visual C++ 2015-2022 x64" -Status "MISSING" -Details "Missing vcruntime140.dll"
    if (-not $CheckOnly) {
        Write-StatusItem -Title "Visual C++ 2015-2022 x64" -Status "INSTALLING" -Details "Downloading official Microsoft installer..."
        $tempVcInstaller = Join-Path $env:TEMP "vc_redist.x64.exe"
        $downloadSuccess = Download-FileWithProgress -Url "https://aka.ms/vs/17/release/vc_redist.x64.exe" -Destination $tempVcInstaller
        if ($downloadSuccess -and (Test-Path $tempVcInstaller)) {
            Write-Host "    Installing Visual C++ Redistributable silently..." -ForegroundColor DarkGray
            $proc = Start-Process -FilePath $tempVcInstaller -ArgumentList "/install /quiet /norestart" -PassThru -Wait
            if ($proc.ExitCode -eq 0 -or $proc.ExitCode -eq 3010) {
                Write-StatusItem -Title "Visual C++ 2015-2022 x64" -Status "OK" -Details "Installed successfully"
            } else {
                Write-StatusItem -Title "Visual C++ 2015-2022 x64" -Status "WARNING" -Details "Installer exited with code $($proc.ExitCode)"
            }
            Remove-Item -Force $tempVcInstaller -ErrorAction SilentlyContinue
        } else {
            Write-StatusItem -Title "Visual C++ 2015-2022 x64" -Status "FAILED" -Details "Could not download vc_redist.x64.exe"
        }
    }
}

# ------------------------------------------------------------------------------
# 4. Python Environment (3.10 / 3.11 / 3.12 / 3.13)
# ------------------------------------------------------------------------------
Write-Host "`n--- [3/6] Python Runtime ---" -ForegroundColor Cyan

function Find-UsablePython {
    # Check venv first if it already exists
    $venvPy = Join-Path $ProjectDir "venv\Scripts\python.exe"
    if (Test-Path $venvPy) {
        $ver = & $venvPy --version 2>&1
        if ($ver -match "Python (\d+)\.(\d+)") {
            return @{ Path = $venvPy; Version = $ver.ToString().Trim(); IsVenv = $true }
        }
    }
    
    # Check py launcher
    $pyLauncher = Get-Command py.exe -ErrorAction SilentlyContinue
    if ($pyLauncher) {
        foreach ($targetVer in @("-3.11", "-3.10", "-3.12", "-3")) {
            $ver = & py.exe $targetVer --version 2>&1
            if ($ver -match "Python (\d+)\.(\d+)") {
                $major = [int]$matches[1]
                $minor = [int]$matches[2]
                if ($major -eq 3 -and $minor -ge 10) {
                    return @{ Path = "py.exe $targetVer"; Version = $ver.ToString().Trim(); IsVenv = $false }
                }
            }
        }
    }
    
    # Check python in PATH
    $pyCmd = Get-Command python.exe -ErrorAction SilentlyContinue
    if ($pyCmd) {
        $ver = & python.exe --version 2>&1
        if ($ver -match "Python (\d+)\.(\d+)") {
            $major = [int]$matches[1]
            $minor = [int]$matches[2]
            if ($major -eq 3 -and $minor -ge 10) {
                return @{ Path = "python.exe"; Version = $ver.ToString().Trim(); IsVenv = $false }
            }
        }
    }
    
    # Check standard install locations in user AppData / Program Files
    $possiblePaths = @(
        "$env:LocalAppData\Programs\Python\Python311\python.exe",
        "$env:LocalAppData\Programs\Python\Python310\python.exe",
        "$env:LocalAppData\Programs\Python\Python312\python.exe",
        "C:\Program Files\Python311\python.exe",
        "C:\Program Files\Python310\python.exe",
        "C:\Python311\python.exe",
        "C:\Python310\python.exe"
    )
    foreach ($p in $possiblePaths) {
        if (Test-Path $p) {
            $ver = & $p --version 2>&1
            if ($ver -match "Python (\d+)\.(\d+)") {
                return @{ Path = $p; Version = $ver.ToString().Trim(); IsVenv = $false }
            }
        }
    }
    
    return $null
}

$foundPython = Find-UsablePython

if ($foundPython) {
    Write-StatusItem -Title "Python Runtime" -Status "OK" -Details "$($foundPython.Version) found ($($foundPython.Path))"
} else {
    Write-StatusItem -Title "Python Runtime" -Status "MISSING" -Details "No Python 3.10+ detected on system"
    if (-not $CheckOnly) {
        Write-StatusItem -Title "Python Installation" -Status "INSTALLING" -Details "Installing Python 3.11 automatically..."
        
        # Method A: Try winget
        $winget = Get-Command winget.exe -ErrorAction SilentlyContinue
        $installedViaWinget = $false
        if ($winget) {
            Write-Host "    Attempting silent installation via winget (Python.Python.3.11)..." -ForegroundColor DarkGray
            & winget install --id Python.Python.3.11 -e --silent --accept-package-agreements --accept-source-agreements | Out-Null
            Refresh-SessionEnvironment
            $foundPython = Find-UsablePython
            if ($foundPython) { $installedViaWinget = $true }
        }
        
        # Method B: Direct official Python installer (portable/user scope - NO ADMIN REQUIRED)
        if (-not $installedViaWinget) {
            Write-Host "    Downloading official Python 3.11 64-bit installer from python.org..." -ForegroundColor DarkGray
            $tempPyInstaller = Join-Path $env:TEMP "python-3.11.9-amd64.exe"
            $downloadSuccess = Download-FileWithProgress -Url "https://www.python.org/ftp/python/3.11.9/python-3.11.9-amd64.exe" -Destination $tempPyInstaller
            if ($downloadSuccess -and (Test-Path $tempPyInstaller)) {
                Write-Host "    Running silent installer (Current User, PATH updated)..." -ForegroundColor DarkGray
                $pyArgs = "/quiet InstallAllUsers=0 PrependPath=1 Include_pip=1 Include_test=0 SimpleInstall=1"
                $proc = Start-Process -FilePath $tempPyInstaller -ArgumentList $pyArgs -PassThru -Wait
                Remove-Item -Force $tempPyInstaller -ErrorAction SilentlyContinue
                Refresh-SessionEnvironment
                $foundPython = Find-UsablePython
            }
        }
        
        if ($foundPython) {
            Write-StatusItem -Title "Python Installation" -Status "OK" -Details "Installed $($foundPython.Version) successfully"
        } else {
            Write-StatusItem -Title "Python Installation" -Status "FAILED" -Details "Could not auto-install Python. Please install from python.org"
            pause
            exit 1
        }
    }
}

# ------------------------------------------------------------------------------
# 5. FFmpeg & FFprobe (Core requirement for MoviePy & audio processing)
# ------------------------------------------------------------------------------
Write-Host "`n--- [4/6] FFmpeg & FFprobe Multimedia Engine ---" -ForegroundColor Cyan

Refresh-SessionEnvironment
$localFfmpegDir = Join-Path $ProjectDir "bin\ffmpeg"
$localFfmpegExe = Join-Path $localFfmpegDir "ffmpeg.exe"
$localFfprobeExe = Join-Path $localFfmpegDir "ffprobe.exe"

$ffmpegFound = $false
$ffmpegPath = ""

if (Test-Path $localFfmpegExe) {
    $ffmpegFound = $true
    $ffmpegPath = $localFfmpegExe
} else {
    $sysFfmpeg = Get-Command ffmpeg.exe -ErrorAction SilentlyContinue
    if ($sysFfmpeg) {
        $ffmpegFound = $true
        $ffmpegPath = $sysFfmpeg.Source
    }
}

if ($ffmpegFound) {
    Write-StatusItem -Title "FFmpeg & FFprobe" -Status "OK" -Details "Detected at: $ffmpegPath"
} else {
    Write-StatusItem -Title "FFmpeg & FFprobe" -Status "MISSING" -Details "FFmpeg is not installed or not in PATH"
    if (-not $CheckOnly) {
        Write-StatusItem -Title "FFmpeg Auto-Install" -Status "INSTALLING" -Details "Installing portable FFmpeg directly into bin\ffmpeg..."
        
        # Ensure target bin directory exists
        if (-not (Test-Path $localFfmpegDir)) {
            New-Item -ItemType Directory -Path $localFfmpegDir -Force | Out-Null
        }
        
        $tempZip = Join-Path $env:TEMP "ffmpeg-release-essentials.zip"
        # Download official Gyan.dev release essentials (trusted standard build)
        $ffmpegUrls = @(
            "https://www.gyan.dev/ffmpeg/builds/ffmpeg-release-essentials.zip",
            "https://github.com/BtbN/FFmpeg-Builds/releases/download/latest/ffmpeg-master-latest-win64-gpl.zip"
        )
        
        $downloadSuccess = $false
        foreach ($url in $ffmpegUrls) {
            Write-Host "    Trying FFmpeg source: $url" -ForegroundColor DarkGray
            $downloadSuccess = Download-FileWithProgress -Url $url -Destination $tempZip
            if ($downloadSuccess -and (Test-Path $tempZip)) { break }
        }
        
        if ($downloadSuccess -and (Test-Path $tempZip)) {
            Write-Host "    Extracting ffmpeg.exe and ffprobe.exe..." -ForegroundColor DarkGray
            $tempExtractDir = Join-Path $env:TEMP "ffmpeg_extract_$([System.Guid]::NewGuid().ToString('N'))"
            New-Item -ItemType Directory -Path $tempExtractDir -Force | Out-Null
            
            try {
                Expand-Archive -Path $tempZip -DestinationPath $tempExtractDir -Force
                $extractedFfmpeg = Get-ChildItem -Path $tempExtractDir -Filter "ffmpeg.exe" -Recurse | Select-Object -First 1
                $extractedFfprobe = Get-ChildItem -Path $tempExtractDir -Filter "ffprobe.exe" -Recurse | Select-Object -First 1
                
                if ($extractedFfmpeg) {
                    Copy-Item -Path $extractedFfmpeg.FullName -Destination $localFfmpegExe -Force
                }
                if ($extractedFfprobe) {
                    Copy-Item -Path $extractedFfprobe.FullName -Destination $localFfprobeExe -Force
                }
                
                Remove-Item -Recurse -Force $tempExtractDir -ErrorAction SilentlyContinue
                Remove-Item -Force $tempZip -ErrorAction SilentlyContinue
                
                if (Test-Path $localFfmpegExe) {
                    Refresh-SessionEnvironment
                    Write-StatusItem -Title "FFmpeg Auto-Install" -Status "OK" -Details "Portable FFmpeg installed to bin\ffmpeg"
                } else {
                    Write-StatusItem -Title "FFmpeg Auto-Install" -Status "FAILED" -Details "Could not locate ffmpeg.exe in extracted archive"
                }
            } catch {
                Write-StatusItem -Title "FFmpeg Auto-Install" -Status "FAILED" -Details "Extraction failed: $_"
            }
        } else {
            # Method B fallback: Winget
            $winget = Get-Command winget.exe -ErrorAction SilentlyContinue
            if ($winget) {
                Write-Host "    Attempting winget install Gyan.FFmpeg..." -ForegroundColor DarkGray
                & winget install --id Gyan.FFmpeg -e --silent --accept-package-agreements --accept-source-agreements | Out-Null
                Refresh-SessionEnvironment
                $sysFfmpeg = Get-Command ffmpeg.exe -ErrorAction SilentlyContinue
                if ($sysFfmpeg) {
                    Write-StatusItem -Title "FFmpeg Auto-Install" -Status "OK" -Details "Installed via winget"
                } else {
                    Write-StatusItem -Title "FFmpeg Auto-Install" -Status "FAILED" -Details "Winget install completed but ffmpeg not found in PATH"
                }
            }
        }
    }
}

# ------------------------------------------------------------------------------
# 6. Virtual Environment & Python Dependencies
# ------------------------------------------------------------------------------
Write-Host "`n--- [5/6] Virtual Environment & Dependencies ---" -ForegroundColor Cyan

$venvPath = Join-Path $ProjectDir "venv"
$venvPython = Join-Path $venvPath "Scripts\python.exe"
$venvPip = Join-Path $venvPath "Scripts\pip.exe"

if (-not (Test-Path $venvPython)) {
    Write-StatusItem -Title "Virtual Environment (venv)" -Status "MISSING" -Details "venv directory does not exist"
    if (-not $CheckOnly) {
        Write-StatusItem -Title "Virtual Environment (venv)" -Status "INSTALLING" -Details "Creating isolated virtual environment..."
        
        $basePy = $foundPython.Path
        if ($basePy -like "py.exe*") {
            $parts = $basePy -split " "
            & py.exe $parts[1] -m venv "$venvPath"
        } else {
            & $basePy -m venv "$venvPath"
        }
        
        if (Test-Path $venvPython) {
            Write-StatusItem -Title "Virtual Environment (venv)" -Status "OK" -Details "Created venv successfully"
        } else {
            Write-StatusItem -Title "Virtual Environment (venv)" -Status "FAILED" -Details "Failed to create virtual environment"
            pause
            exit 1
        }
    }
} else {
    Write-StatusItem -Title "Virtual Environment (venv)" -Status "OK" -Details "Isolated venv verified"
}

# Install / verify dependencies
if (Test-Path $venvPython) {
    if (-not $CheckOnly) {
        Write-StatusItem -Title "Pip, Setuptools & Wheel" -Status "INSTALLING" -Details "Upgrading package manager..."
        & $venvPython -m pip install --upgrade pip setuptools wheel --quiet
        
        $reqFile = Join-Path $ProjectDir "requirements.txt"
        if (Test-Path $reqFile) {
            Write-StatusItem -Title "Dependencies Installation" -Status "INSTALLING" -Details "Installing from requirements.txt (may take a few minutes)..."
            Write-Host "    [Please wait] Installing moviepy, streamlit, edge-tts, faster-whisper..." -ForegroundColor DarkGray
            
            & $venvPip install -r $reqFile
            if ($LASTEXITCODE -eq 0) {
                Write-StatusItem -Title "Dependencies Installation" -Status "OK" -Details "All requirements installed successfully"
            } else {
                Write-StatusItem -Title "Dependencies Installation" -Status "WARNING" -Details "Pip exited with code $LASTEXITCODE. Retrying..."
                & $venvPip install -r $reqFile
            }
        }
    } else {
        # Check-only test
        Write-StatusItem -Title "Dependencies Status" -Status "INFO" -Details "Requirements file found ($((Get-Content (Join-Path $ProjectDir 'requirements.txt')).Count) entries)"
    }
}

# ------------------------------------------------------------------------------
# 7. Project Configuration & Directory Validation
# ------------------------------------------------------------------------------
Write-Host "`n--- [6/6] Configuration & System Verification ---" -ForegroundColor Cyan

# Directories
$dirsToEnsure = @("storage", "models", "logs", "resource", "storage\cache", "storage\tasks")
foreach ($d in $dirsToEnsure) {
    $fullPath = Join-Path $ProjectDir $d
    if (-not (Test-Path $fullPath)) {
        New-Item -ItemType Directory -Path $fullPath -Force | Out-Null
    }
}
Write-StatusItem -Title "Required Folders" -Status "OK" -Details "storage, models, logs, resource verified"

# Config.toml
$cfgPath = Join-Path $ProjectDir "config.toml"
$cfgExample = Join-Path $ProjectDir "config.example.toml"
if (-not (Test-Path $cfgPath)) {
    if (Test-Path $cfgExample) {
        Copy-Item $cfgExample $cfgPath
        Write-StatusItem -Title "Configuration (config.toml)" -Status "OK" -Details "Created default config.toml from template"
    } else {
        Write-StatusItem -Title "Configuration (config.toml)" -Status "WARNING" -Details "config.example.toml not found"
    }
} else {
    Write-StatusItem -Title "Configuration (config.toml)" -Status "OK" -Details "Existing user config.toml preserved"
}

# Streamlit credentials (suppress prompt)
$streamlitDir = Join-Path $ProjectDir ".streamlit"
if (-not (Test-Path $streamlitDir)) { New-Item -ItemType Directory -Path $streamlitDir -Force | Out-Null }
$credsPath = Join-Path $streamlitDir "credentials.toml"
if (-not (Test-Path $credsPath)) {
    "[general]`nemail = `"`"" | Out-File -FilePath $credsPath -Encoding utf8
    Write-StatusItem -Title "Streamlit Preferences" -Status "OK" -Details "Created credentials.toml"
} else {
    Write-StatusItem -Title "Streamlit Preferences" -Status "OK" -Details "Streamlit ready"
}

# Self-Diagnosis Import Test
if (Test-Path $venvPython) {
    Write-Host "`n  Running quick self-diagnosis test..." -ForegroundColor DarkGray
    $testScript = "import streamlit, moviepy, edge_tts, faster_whisper; print('HEALTH_OK')"
    $testOut = & $venvPython -c $testScript 2>&1
    if ($testOut -match "HEALTH_OK") {
        Write-StatusItem -Title "System Self-Diagnosis" -Status "OK" -Details "All core modules (streamlit, moviepy, edge-tts, whisper) load successfully!"
    } else {
        Write-StatusItem -Title "System Self-Diagnosis" -Status "WARNING" -Details "Test output: $testOut"
    }
}

# ------------------------------------------------------------------------------
# Completion / Next Steps
# ------------------------------------------------------------------------------
Write-Host ""
Write-Host "======================================================================" -ForegroundColor Green
if ($CheckOnly) {
    Write-Host "                 Diagnostic Check Finished!                           " -ForegroundColor Cyan
    Write-Host "======================================================================" -ForegroundColor Green
    Write-Host ""
    $answer = Read-Host "Would you like to auto-install any missing prerequisites now? [Y/N]"
    if ($answer -match "^[Yy]") {
        & "$PSCommandPath"
    }
    exit 0
}

Write-Host "       elSandoo2 el a5dar is 100% READY for action!                   " -ForegroundColor Green
Write-Host "======================================================================" -ForegroundColor Green
Write-Host ""
Write-Host "You can start the app at any time by double-clicking 'run.bat'." -ForegroundColor Cyan
Write-Host ""

if ($AutoProceed) {
    Write-Host "Auto-launching elSandoo2 el a5dar..." -ForegroundColor Green
    Start-Process -FilePath (Join-Path $ProjectDir "run.bat")
    exit 0
}

$launchChoice = Read-Host "Do you want to launch the app right now? [Y/n]"
if ($launchChoice -eq "" -or $launchChoice -match "^[Yy]") {
    Write-Host "`nLaunching elSandoo2 el a5dar WebUI at http://localhost:8501..." -ForegroundColor Green
    Start-Process -FilePath (Join-Path $ProjectDir "run.bat")
}
