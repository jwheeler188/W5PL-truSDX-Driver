ARM64 drivers for Setup_W5PL_truSDX_Driver_beta_arm64.exe  (Windows on ARM: Snapdragon / Copilot+ PCs)
=========================================================================================================

Windows on ARM can run the x64 driver program, but device drivers must be native ARM64.
The drivers bundled with the original installer are x86/x64 only, so download the current
versions yourself from the official sites and put them here, then run ..\build.bat again:

  arm64-drivers\CH341SER.EXE
      WCH CH340/CH341 USB-serial driver for Windows, version 3.9 or newer (includes ARM64).
      Official site: https://www.wch-ic.com  (search: CH341SER.EXE)

  arm64-drivers\vbcable\
      The current VB-CABLE driver pack: the downloaded VBCABLE_Driver_Pack*.zip, or its extracted folder
      Releases since October 2024 support ARM64.
      Official site: https://vb-audio.com/Cable/
      VB-CABLE is donationware - see vb-audio.com for its license.

No virtual COM-port driver is needed on ARM64: the ARM64 edition runs the driver with
--cat-tcp 4542, and WSJT-X connects to it over the network:
      WSJT-X > Settings > Radio > Serial Port:  127.0.0.1:4542     PTT Method: CAT

If these files are missing, build.bat still builds the x64 installer and skips the ARM64 one.
