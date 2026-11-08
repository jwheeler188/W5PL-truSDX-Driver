# W5PL Driver for DL2MAN (tr)uSDX

**Audio and CAT over a single USB cable** for the DL2MAN (tr)uSDX, for WSJT-X, JS8Call, fldigi and other digital-mode
programs. No audio cables, no external sound card: a laptop, the radio, one USB cable and an antenna.

Based on [trusdx-audio](https://github.com/threeme3/trusdx-audio) by SQ3SWF and PE1NNZ, with the problems that made it
unreliable fixed. Above all, **the radio no longer gets stuck in transmit**.

| | |
|---|---|
| **Windows 10/11, Intel/AMD** | `Setup_W5PL_truSDX_Driver_beta_x64.exe` |
| **Windows 10/11 on ARM** (Snapdragon / Copilot+) | `Setup_W5PL_truSDX_Driver_beta_arm64.exe` |
| **macOS 12+**, Intel and Apple Silicon | `W5PL-truSDX-Driver-<version>-macos-linux.zip` → `macOS/install.sh` |
| **Linux** (PulseAudio / PipeWire) — *untested* | `W5PL-truSDX-Driver-<version>-macos-linux.zip` → `linux/install.sh` |

Download from the [Releases](../../releases) page.

> **Beta.** Tested on macOS 13 with (tr)uSDX firmware 2.00x and WSJT-X v3.3.0-beta5 (Hamlib 4.7.2): CAT, Tune and full
> FT8 transmit cycles, un-keying back to receive in about 0.2–0.3 s. The Windows installers have been built and
> installed on Windows on ARM. Linux is untested. **Do your first transmit test at 0 W** ([manual, section 6](MANUAL.md#6-first-test-0-w)).

## Quick start

1. **Radio:** firmware R2.00u or newer, menu 2.4 **Semi-QSK OFF**, **VOX OFF**, volume **10–12**. Connect it by USB.
2. **Install** for your system (details in the [manual](MANUAL.md#4-installing)):
   - **Windows:** run the setup for your PC. If the factory "truSDX Driver" is installed, let setup remove it first.
   - **macOS:** `brew install --cask blackhole-2ch`, restart, then run `macOS/install.sh`.
   - **Linux:** run `linux/install.sh`, then log out and back in once.
3. **Start the driver** and wait for `(tr)uSDX driver OK!`.
   Windows: Start menu → *W5PL Driver for DL2MAN (tr)uSDX*. macOS: `macOS/Start W5PL truSDX Driver.command`. Linux: `linux/trusdx.sh`.
4. **WSJT-X → Settings → Radio:** Rig **DL2MAN (tr)uSDX** (or **Kenwood TS-480**), 115200 baud, PTT **CAT**, Mode **USB**.

   | | Windows x64 | Windows ARM64 | macOS | Linux |
   |---|---|---|---|---|
   | Serial Port | `COM8` | `127.0.0.1:4542` | `/tmp/trusdx` | `/tmp/trusdx` |
   | Audio Input | CABLE Output | CABLE Output | BlackHole 2ch | Monitor of TRUSDX |
   | Audio Output | CABLE Input | CABLE Input | BlackHole 2ch | TRUSDX |

5. Click **Test CAT** (green), then do the [0 W test](MANUAL.md#6-first-test-0-w).

> **Firmware 2.00x:** set filter, volume and TX Drive on the radio *before* starting WSJT-X, and don't use the
> radio's controls while WSJT-X is connected: that can crash the radio. The driver recovers, but avoid it
> ([manual, section 17](MANUAL.md#17-known-limitations)).

## Documentation

- **[MANUAL.md](MANUAL.md)** — the full manual: installation, WSJT-X setup, receive level, options, troubleshooting,
  logs, uninstalling, building, how it works.
- **[CHANGES.md](CHANGES.md)** — what was fixed compared to the original driver, and how it was measured.
- **[BUG-REPORT.md](BUG-REPORT.md)** — the bug report and patch ([tools/beta-fixes.patch](tools/beta-fixes.patch))
  for the original driver's authors.

## What's fixed

- Radio **stuck in transmit** after long transmissions (transmit audio overflowed the 115200-baud link).
- **Un-key** commands ignored; audio streaming not restored after transmit.
- **Slow, retried CAT** commands and Hamlib *protocol error* / *timeout* messages.
- Receive audio input **jumping to 100%**, and short **receive-audio gaps**.
- Problems after **unplugging and reconnecting** the radio.
- **Crash recovery:** if the radio crashes (firmware 2.00x, front-panel use while streaming), the driver keeps WSJT-X
  connected and lets the radio reboot cleanly instead of keeping it in a reboot loop.
- New: **macOS** installer, **Windows on ARM** edition, **network CAT** (`--cat-tcp`), uninstallers, this manual.

## Repository layout

```
trusdx-txrx.py            the driver (one Python file, all platforms)
macOS/                    install.sh, trusdx.sh, Start W5PL truSDX Driver.command, uninstall.sh
linux/                    install.sh, trusdx.sh, uninstall.sh
windows/                  run-from-python.bat; installer-build/ (build.bat → Windows installers)
tools/                    unkey_test.py, beta-fixes.patch, make-release.sh, the original driver and README
MANUAL.md CHANGES.md BUG-REPORT.md LICENSE NOTICE.md
```

## Credits

The original **trusdx-audio** driver is by **SQ3SWF** and **PE1NNZ**. The **(tr)uSDX** radio and its CAT streaming
protocol are by **DL2MAN** and **PE1NNZ** ([dl2man.de](https://dl2man.de)). This release (fixes, packaging,
documentation) is by **W5PL**.

**License:** GPL-3.0 for W5PL's changes ([LICENSE](LICENSE)); see [NOTICE.md](NOTICE.md) for the original code and
third-party components.
