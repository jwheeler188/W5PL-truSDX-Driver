# W5PL Driver for DL2MAN (tr)uSDX — beta 2026-11-07

Audio and CAT over the (tr)uSDX's single USB cable for WSJT-X and other digital-mode programs. Based on trusdx-audio
by SQ3SWF and PE1NNZ, with the problems that left the radio **stuck in transmit** fixed.

## Downloads

| File | For |
|---|---|
| `Setup_W5PL_truSDX_Driver_beta_x64.exe` | Windows 10/11 on Intel/AMD. CAT on **COM8**. |
| `Setup_W5PL_truSDX_Driver_beta_arm64.exe` | Windows 10/11 on ARM (Snapdragon / Copilot+). CAT on **127.0.0.1:4542**. |
| `W5PL-truSDX-Driver-beta-2026-11-07-macos-linux.zip` | macOS (`macOS/install.sh`) and Linux (`linux/install.sh`, untested). |
| `SHA256SUMS.txt` | Checksums of the files above. |

**Installing over the factory driver (Windows):** setup finds the old "truSDX Driver" and offers to remove it first.
Choose **Yes**.

Read the **[manual](MANUAL.md)** for setup and WSJT-X settings, and **do your first transmit test at 0 W**.

## Highlights
- **No more stuck transmit:** transmit audio now runs at 8000 samples/s (the original 11520 used 100% of the USB-serial
  link and overflowed the radio on long transmissions), with a reliable un-key sequence that restores receive audio in
  about 0.2–0.3 s.
- **Fast, clean CAT:** replies arrive first time (no more Hamlib retries, *protocol error* or *timeout*); polls during
  transmit no longer break the audio stream.
- **Receive audio:** no more input pegged at 100% after a reconnect or during transmit, and no periodic gaps.
- **Reconnects:** unplugging and replugging the radio is handled cleanly.
- **New platforms:** macOS installer (Intel and Apple Silicon), Windows on ARM edition, Linux scripts (untested).
- **Network CAT** (`--cat-tcp 4542`) as an alternative to a virtual COM port.
- Uninstallers for every platform; the Windows setup removes the factory driver for you.

Full list with measurements: [CHANGES.md](CHANGES.md).

## Tested
- macOS 13, (tr)uSDX firmware 2.00x, WSJT-X v3.3.0-beta5 / Hamlib 4.7.2 (rig models *DL2MAN (tr)uSDX* and *Kenwood TS-480*):
  CAT, Tune, full FT8 cycles, 20+ forced reconnects, network CAT.
- Windows on ARM: installer, including removing the factory driver.
- **Not yet tested:** Windows on Intel/AMD hardware, Linux. Reports welcome.

## Known limitations
- Receive audio is 8-bit at 7812 samples/s (the radio's limit). The radio's **volume sets the receive level**: use 10–12.
- Windows ARM64: CAT over the network only (no COM port, no RTS/DTR PTT).
- The installers aren't code-signed: Windows SmartScreen shows a warning (More info → Run anyway).
