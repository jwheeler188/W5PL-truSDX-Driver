@echo off
rem W5PL Driver for DL2MAN (tr)uSDX - run it directly from Python on Windows (no build needed).
rem Needs: Python 3 from python.org (tick "Add python.exe to PATH"), plus the virtual COM8/COM9 pair (VSPE)
rem and VB-Audio CABLE - both are installed by Setup_W5PL_truSDX_Driver_beta_x64.exe (or the factory Setup_truSDX_Driver.exe).
rem Close the installed driver window first: only one program may use the radio's COM port.
rem Windows on ARM / no VSPE: run   run-from-python.bat --cat-tcp 4542   and set WSJT-X Serial Port to 127.0.0.1:4542
rem (needs x64 Python - PyAudio has no ARM64 package - plus ARM64 VB-CABLE and CH340 v3.9+ drivers)
cd /d "%~dp0"
python -m pip install --quiet pyaudio pyserial || (echo Python or pip not found - install Python 3 from python.org & pause & exit /b 1)
python ..\trusdx-txrx.py %*
pause
