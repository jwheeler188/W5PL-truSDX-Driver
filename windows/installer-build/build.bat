@echo off
rem W5PL Driver for DL2MAN (tr)uSDX: builds Setup_W5PL_truSDX_Driver_beta_x64.exe (+ _arm64.exe) from the patched driver (double-click on Windows 10/11).
rem Installs anything missing first (x64 Python 3.11 and NSIS via winget; nuitka/pyaudio/pyserial via pip).
rem pushd also works when this folder is a network share (e.g. Parallels \\Mac\Home\...).
pushd "%~dp0"
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0build.ps1"
popd
echo.
pause
