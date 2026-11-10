# W5PL Driver for DL2MAN (tr)uSDX - builds Setup_W5PL_truSDX_Driver_beta_x64.exe (+ _arm64.exe) from the patched driver, installing anything missing.
# Run via build.bat (double-click). Needs Windows 10 (1809+) or 11 with winget ("App Installer"), and internet.
# Installs if missing: Python 3.11 x64 (per-user), NSIS, then pip packages nuitka/pyaudio/pyserial.
# Nuitka downloads its own C compiler (MinGW64) on first build.
# The build runs in a LOCAL folder (%LOCALAPPDATA%\truSDX-build): compilers fail on network shares such as the
# Parallels \\Mac\... folder. The finished installers are copied back next to this script.
$ErrorActionPreference = "Stop"
$KIT = $PSScriptRoot                          # windows\installer-build (may be a \\Mac\... share)
$DRIVER = Join-Path $KIT "..\..\trusdx-txrx.py"

function Step($m) { Write-Host "==> $m" -ForegroundColor Cyan }
function Fail($m) { Write-Host "ERROR: $m" -ForegroundColor Red; exit 1 }
function Refresh-Path {
    $env:Path = [Environment]::GetEnvironmentVariable("Path", "Machine") + ";" + [Environment]::GetEnvironmentVariable("Path", "User")
}

# 1. Python: must be an x64 (win-amd64) interpreter. PyAudio has ready-made wheels only for x64/x86 Windows; an ARM64
#    Python tries to compile it and fails ("Microsoft Visual C++ 14.0 or greater is required"). On Windows-on-ARM the
#    x64 Python runs emulated. Only these exact install folders are checked (no py launcher / PATH guessing).
$PY_CANDIDATES = @(
    "$env:LOCALAPPDATA\Programs\Python\Python311\python.exe",
    "$env:LOCALAPPDATA\Programs\Python\Python312\python.exe",
    "$env:ProgramFiles\Python311\python.exe",
    "$env:ProgramFiles\Python312\python.exe"
)
function Find-X64Python {
    foreach ($p in $PY_CANDIDATES) {
        if (-not (Test-Path -LiteralPath $p)) { continue }
        $plat = ""
        try { $plat = (& $p -c "import sysconfig; print(sysconfig.get_platform())" 2>$null | Out-String).Trim() } catch { }
        if ($plat -eq "win-amd64") { Write-Host "    $p -> $plat (using it)"; return $p }
        Write-Host "    $p -> $plat (skipped: not x64)"
    }
    return $null
}
Step "Looking for an x64 Python 3.11/3.12"
$PY = Find-X64Python
if (-not $PY) {
    if (-not (Get-Command winget -ErrorAction SilentlyContinue)) {
        Fail "winget not found. Install 'App Installer' from the Microsoft Store, or install Python 3.11 x64 from python.org (per-user, default folder), then run build.bat again."
    }
    Step "Installing Python 3.11 x64 (winget, silent, per-user; on ARM Windows it runs emulated, next to any ARM64 Python)"
    winget install --id Python.Python.3.11 -e --architecture x64 --scope user --silent --accept-package-agreements --accept-source-agreements
    Refresh-Path
    $PY = Find-X64Python
    if (-not $PY) { Fail "x64 Python 3.11 was not found after installing. Expected: $($PY_CANDIDATES[0])" }
}
Step ("Python: " + (& $PY -c "import sys, sysconfig; print(sys.executable, sys.version.split()[0], sysconfig.get_platform())"))

# 2. NSIS
function Find-Makensis {
    foreach ($p in @("${env:ProgramFiles(x86)}\NSIS\makensis.exe", "$env:ProgramFiles\NSIS\makensis.exe")) { if (Test-Path -LiteralPath $p) { return $p } }
    return $null
}
$MAKENSIS = Find-Makensis
if (-not $MAKENSIS) {
    if (-not (Get-Command winget -ErrorAction SilentlyContinue)) { Fail "winget not found - install NSIS from nsis.sourceforge.io, then run build.bat again." }
    Step "Installing NSIS (winget, silent - Windows may ask for admin permission once)"
    winget install --id NSIS.NSIS -e --silent --accept-package-agreements --accept-source-agreements
    $MAKENSIS = Find-Makensis
    if (-not $MAKENSIS) { Fail "NSIS was installed but makensis.exe wasn't found. Run build.bat again." }
}
Step "NSIS: $MAKENSIS"

# 3. Python packages (x64 wheels - no compiler needed)
Step "Installing/updating nuitka, pyaudio, pyserial"
& $PY -m pip install --quiet --upgrade pip
& $PY -m pip install --quiet --upgrade nuitka pyaudio pyserial
if ($LASTEXITCODE -ne 0) { Fail "pip install failed - see the pip messages above for the reason." }

# 4. Copy the kit to a local build folder (network shares break the C compiler)
$WORK = Join-Path $env:LOCALAPPDATA "truSDX-build"
Step "Copying the build kit to $WORK"
if (Test-Path -LiteralPath $WORK) { Remove-Item -LiteralPath $WORK -Recurse -Force }
New-Item -ItemType Directory -Path $WORK | Out-Null
foreach ($item in @("trusdx.nsi", "trusdx.bmp", "CH341SER.EXE", "SetupVSPE_32", "Setup_vbcable", "arm64-drivers")) {
    $src = Join-Path $KIT $item
    if (Test-Path -LiteralPath $src) { Copy-Item -LiteralPath $src -Destination $WORK -Recurse -Force }
}
if (-not (Test-Path -LiteralPath $DRIVER)) { Fail "driver script not found: $DRIVER" }
Copy-Item -LiteralPath $DRIVER -Destination (Join-Path $WORK "W5PL truSDX Driver.py") -Force
Set-Location -LiteralPath $WORK

# 5. Build the driver executable (x64; runs natively on Intel/AMD and emulated on Windows ARM)
Step "Building W5PL truSDX Driver.exe with Nuitka (first run downloads a C compiler - this can take several minutes)"
& $PY -m nuitka --standalone --assume-yes-for-downloads --include-module=serial.urlhandler.protocol_socket "W5PL truSDX Driver.py"
if ($LASTEXITCODE -ne 0 -or -not (Test-Path "W5PL truSDX Driver.dist\W5PL truSDX Driver.exe")) { Fail "Nuitka build failed (see messages above)." }

# 6. Build the installers
$built = @()
Step "Building Setup_W5PL_truSDX_Driver_beta_x64.exe (Intel/AMD Windows: VSPE COM8/COM9, bundled VB-CABLE + CH340)"
& $MAKENSIS trusdx.nsi
if ($LASTEXITCODE -ne 0 -or -not (Test-Path "Setup_W5PL_truSDX_Driver_beta_x64.exe")) { Fail "NSIS x64 build failed (see messages above)." }
$built += "Setup_W5PL_truSDX_Driver_beta_x64.exe"

# ARM64 edition: needs the current ARM64-capable drivers, downloaded by you from the official sites into arm64-drivers\
#   arm64-drivers\CH341SER.EXE   WCH CH340/CH341 Windows driver v3.9 or newer (wch-ic.com)
#   arm64-drivers\VBCABLE_Driver_Pack*.zip, or its extracted folder (vb-audio.com/Cable), current version
$ch = "arm64-drivers\CH341SER.EXE"
foreach ($z in @(Get-ChildItem "arm64-drivers" -Filter "VBCABLE*.zip" -ErrorAction SilentlyContinue)) {
    $dest = Join-Path "arm64-drivers" $z.BaseName
    if (-not (Test-Path -LiteralPath $dest)) { Step "Extracting $($z.Name)"; Expand-Archive -LiteralPath $z.FullName -DestinationPath $dest -Force }
}
$vbSetup = $null; $vbDir = $null
$dirs = @(Get-Item "arm64-drivers\vbcable" -ErrorAction SilentlyContinue) + @(Get-ChildItem "arm64-drivers" -Directory -Filter "VBCABLE_Driver_Pack*" -ErrorAction SilentlyContinue | Sort-Object Name -Descending)
foreach ($dir in $dirs) {
    if (-not $dir) { continue }
    $s = Get-ChildItem -LiteralPath $dir.FullName -Filter "VBCABLE_Setup*.exe" -ErrorAction SilentlyContinue |
         Sort-Object @{e={ if ($_.Name -match "arm64") {0} elseif ($_.Name -match "x64") {1} else {2} }} | Select-Object -First 1
    if ($s) { $vbSetup = $s; $vbDir = "arm64-drivers\" + $dir.Name; break }
}
if ($vbDir -and -not (Get-ChildItem -LiteralPath $vbDir -Filter "*arm*.sys" -ErrorAction SilentlyContinue)) {
    Write-Host "WARNING: $vbDir has no ARM64 driver (*arm*.sys) - download the current VB-CABLE pack from vb-audio.com" -ForegroundColor Yellow
}
if ((Test-Path -LiteralPath $ch) -and $vbSetup) {
    Step "Building Setup_W5PL_truSDX_Driver_beta_arm64.exe (Windows ARM64: CAT over TCP 127.0.0.1:4542, VB-CABLE: $vbDir\$($vbSetup.Name))"
    & $MAKENSIS /DARM64 "/DVBCABLE_SETUP=$($vbSetup.Name)" "/DVBCABLE_DIR=$vbDir" trusdx.nsi
    if ($LASTEXITCODE -ne 0 -or -not (Test-Path "Setup_W5PL_truSDX_Driver_beta_arm64.exe")) { Fail "NSIS ARM64 build failed (see messages above)." }
    $built += "Setup_W5PL_truSDX_Driver_beta_arm64.exe"
} else {
    Write-Host "NOTE: ARM64 installer skipped - put CH341SER.EXE (v3.9+) and the VB-CABLE pack (zip or folder) into" -ForegroundColor Yellow
    Write-Host "      $KIT\arm64-drivers\  (see arm64-drivers\README.txt), then run build.bat again." -ForegroundColor Yellow
}

# 7. Copy the installers back next to this script
Write-Host ""
foreach ($b in $built) {
    Copy-Item -LiteralPath (Join-Path $WORK $b) -Destination $KIT -Force
    Write-Host "Built: $KIT\$b" -ForegroundColor Green
}
