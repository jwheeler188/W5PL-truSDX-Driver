# W5PL Driver for DL2MAN (tr)uSDX — beta 2026-11-10

Audio and CAT over the (tr)uSDX's single USB cable for WSJT-X and other digital-mode programs. Based on trusdx-audio
by SQ3SWF and PE1NNZ.

> **New: run the radio from anywhere in the house.** Plug the radio into a Raspberry Pi and use it from a laptop over
> the network: WSJT-X, VARA (xara) and Winlink (Pat) work as with a local radio. Plus a fix for receive audio that
> doesn't come back after a transmission, a transmit gain option, and safer band changes. Everything from beta
> 2026-11-08-3 is included. Updating is recommended.

## New
- **Network radio** (manual section 11.1): `linux/trusdx-netbridge.py` on a Pi shares the radio's USB link on the
  network; the driver connects with `--serial-url socket://PI-ADDRESS:4532`. The bridge applies the key/un-key timing
  next to the radio and **un-keys the radio itself** if the laptop disconnects, its transmit audio stops for 1.5 s, or
  the bridge stops. `linux/install-netbridge.sh` installs it as a boot service.
- **Receive audio broken after a transmission** (thanks G4BWQ, issue 2): if no receive audio is back 3 s after un-key,
  the driver now switches the radio's audio streaming off and on (`;UA0;` `;UA2;` `;RX;`). New option
  **`--reset-after-tx`** does this after every transmission. Idea from jasiek's trusdx-mac-audio-bridge.
- **`--tx-gain X`** scales the transmit audio. With `-v`, each transmission logs its audio level, e.g.
  `TX audio peak 95% of full scale, 0 clipped`: raise the gain only until the peak is just under 100%.
- **Band changes during a transmission** no longer lock the radio: the driver holds them until the radio is back in
  receive, then sends them.
- **Windows:** when a program raises DTR/RTS on COM8 the driver now says so ("KEYED by RTS/DTR"). Set DTR and RTS to
  **Low** in WSJT-X, or start the driver with `--no-rtsdtr` if every program uses CAT PTT.
- **macOS/Linux:** the CAT port (`/tmp/trusdx`) stays the same across reconnects, so rigctld and WSJT-X keep working
  after a USB replug or radio reboot.
- Manual: radio settings now stress **CQ Interval 0** (the radio keys up by itself otherwise, also in USB), **USB not
  CW**, and VOX off after a Digirig setup. VARA / xara / Pat through rigctld.
- Linux: PipeWire receive audio fix (tested on a Raspberry Pi 4, Ubuntu 24.04). Option `--rts-low`.
- **Tests:** 15 tests run the driver against a simulated radio, on Linux, macOS and Windows for every change.

## Tested on the air (firmware 2.00x)
- **Network radio, Pi 4 + MacBook on Wi-Fi, 40 m FT8:** 41 PSK Reporter spots in 2 minutes; 2026-11-10: 70 more
  transmissions with clean key/un-key and 300+ PSK Reporter spots, no driver warnings. Once a 1.5 s Wi-Fi stall
  stopped the laptop's audio, and the bridge un-keyed the radio by itself as designed.
- **VARA over the network:** xara 0.1.3 + Pat, a full Winlink session through W0MAC (message sent, replies received).
- **Windows x64 over the network** (driver run from Python): 22 clean FT8 transmissions; a weak-Wi-Fi PC (15%
  packet loss) works after the fixes in this release.
- **Streaming reset:** 14 of 14 transmissions with `--reset-after-tx` reset cleanly, receive audio and decoding resumed.
- **TX gain** (TX Drive 7): gain 1.5 = +1.5 dB median at 38 PSK Reporter receivers; gain 2 clipped and was 2 dB worse.

The Windows installers in this release are newly built and have not been tested on the air yet. Reports welcome.

## Downloads

| File | For |
|---|---|
| `Setup_W5PL_truSDX_Driver_beta_x64.exe` | Windows 10/11 on Intel/AMD. CAT on **COM8**. |
| `Setup_W5PL_truSDX_Driver_beta_arm64.exe` | Windows 10/11 on ARM (Snapdragon / Copilot+). CAT on **127.0.0.1:4542**. |
| `W5PL-truSDX-Driver-beta-2026-11-10-macos-linux.zip` | macOS (`macOS/install.sh`), Linux (`linux/install.sh`) and the network bridge for a Pi. |
| `SHA256SUMS.txt` | Checksums of the files above. |

**Updating:** Windows: run the new setup over the old one. macOS/Linux: replace the folder and run `install.sh` again.
Read the **[manual](MANUAL.md)**, and do your first transmit test at **low power**.

## Known limitations
- Firmware 2.00x: using the radio's buttons or knobs while WSJT-X is connected can crash the radio; the driver
  recovers. Set filter, volume and TX Drive before starting WSJT-X. After a crash, check the radio's settings.
- Receive audio is 8-bit at 7812 samples/s. The radio's **volume sets the receive level**: use 10–12.
- Network radio: the bridge has no password; use it on your home network only. Weak Wi-Fi needs `--net-buffer 600`.
- Windows ARM64: CAT over the network only (no COM port, no RTS/DTR PTT).
- The installers aren't code-signed: Windows SmartScreen shows a warning (More info → Run anyway).

Full list with measurements: [CHANGES.md](CHANGES.md).
