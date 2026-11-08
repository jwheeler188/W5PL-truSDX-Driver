# W5PL Driver for DL2MAN (tr)uSDX — beta 2026-11-08-3

Audio and CAT over the (tr)uSDX's single USB cable for WSJT-X and other digital-mode programs. Based on trusdx-audio
by SQ3SWF and PE1NNZ.

> **Transmit audio fix, replaces beta 2026-11-08-2.** The previous beta's transmit audio was **garbled on air**: it keyed
> and un-keyed fine, but nobody could decode it. Thanks to G4BWQ for reporting it. The radio plays each transmit sample
> the moment it arrives, and the beta sent the audio in short bursts. This version sends every sample evenly spaced
> (10473 samples/s, 2 stop bits per byte). **If you installed beta 2026-11-08-2, update.**

## Tested on the air
macOS, firmware 2.00x, 20 m FT8:
- Clean transmit audio checked on a second receiver and with a microphone (clean FT8 tones, no clicks).
- **190+ PSK Reporter spots in 5 minutes** after the fix (best +19 dB, coast to coast plus Canada, Colombia, Cayman Islands).
- QSOs completed with WSJT-X Auto Seq; the radio un-keyed every time, no driver warnings.

Windows on ARM64, 20 m FT8: **108 PSK Reporter spots in 6 minutes**, median −14 dB (Mac: −13 dB), best +16 dB.

Windows x64 and Linux have **not** been tested with the new transmit pacing yet. Reports welcome.

## Also new
- Manual: WSJT-X **Force Control Lines** blank (macOS/Linux Hamlib error), **Pwr slider** advice for FT8, **Auto Seq
  "CQ: First"** so WSJT-X answers callers, **hearing receive audio** on the computer's speakers, macOS Microphone
  permission, and the radio's **CQ Interval** (menu 4.1), which can make it key up by itself after a crash reset.
- Linux (untested): ModemManager udev rule, ALSA loopback mode for systems without PulseAudio/PipeWire, and
  `--rx-audio` / `--tx-audio` options to choose audio devices by name.
- Option `--stop-bits 1|2` (default 2) for comparison with the factory pacing.
- Clearer boot-loop breaker message.

## Downloads

| File | For |
|---|---|
| `Setup_W5PL_truSDX_Driver_beta_x64.exe` | Windows 10/11 on Intel/AMD. CAT on **COM8**. |
| `Setup_W5PL_truSDX_Driver_beta_arm64.exe` | Windows 10/11 on ARM (Snapdragon / Copilot+). CAT on **127.0.0.1:4542**. |
| `W5PL-truSDX-Driver-beta-2026-11-08-3-macos-linux.zip` | macOS (`macOS/install.sh`) and Linux (`linux/install.sh`, untested). |
| `SHA256SUMS.txt` | Checksums of the files above. |

**Updating:** Windows: run the new setup over the old one. macOS/Linux: replace the folder and run `install.sh` again.
Read the **[manual](MANUAL.md)**, and do your first transmit test at **low power**.

## Known limitations
- Firmware 2.00x: using the radio's buttons or knobs while WSJT-X is connected can crash the radio; the driver
  recovers. Set filter, volume and TX Drive before starting WSJT-X. After a crash, check the radio's settings.
- Receive audio is 8-bit at 7812 samples/s. The radio's **volume sets the receive level**: use 10–12.
- Windows ARM64: CAT over the network only (no COM port, no RTS/DTR PTT).
- The installers aren't code-signed: Windows SmartScreen shows a warning (More info → Run anyway).

Full list with measurements: [CHANGES.md](CHANGES.md).
