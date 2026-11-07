# Changes in beta 2026-11-07 (vs. original trusdx-txrx.py)

All of these were found from driver logs plus raw serial captures, and checked with a direct test that talks
to the radio without the driver (`tools/unkey_test.py`). Test setup: (tr)uSDX firmware 2.00x, macOS 13,
WSJT-X v3.3.0-beta5, Hamlib 4.7.2, at 0 W.

## Stuck transmitting (the main fix)
| # | Problem | Fix |
|---|---|---|
| 1 | TX audio was sent at **11520 samples/s, which uses 100% of the 115200-baud link**. On long transmissions the radio's input overflows and it loses bytes, including the `RX;`, so it **stays keyed**. 2 s transmissions un-keyed 28/28, but 8 s ones got stuck. | TX audio now goes at **8000 samples/s** (`--tx-rate`), in evenly paced 20 ms pieces instead of 64 ms bursts. Measured: **13 s (FT8 length) at 8000 and 9600 S/s, 6/6 un-keyed in ~0.3 s.** |
| 2 | `RX;` was sent 10 ms after the last TX audio and was often ignored. | Un-key sequence: stop the audio, **200 ms quiet, `;RX;`, 100 ms, `;UA2;`**. Measured 18/18 at 2 s, 9/9 from WSJT-X Tune, 3/3 full FT8 slots. |
| 3 | After a transmission the radio stops CAT audio streaming. Without it, it misses CAT commands and the next `TX0;` keys up without audio mode (`E;` flood, then stuck). | `;UA2;` after every un-key; a streaming watchdog (resends UA if no RX audio for 1.5 s); streaming checked before each key-up; a second un-key after 1.5 s only if RX audio didn't return. |
| 4 | Hamlib sends a plain `TX;` (TS-480 and DL2MAN profiles), which keys the radio *without* CAT audio, so the audio bytes are read as commands (`E;` flood). | Every key-up is sent as **`TX0;` + `US`** (the stream header the (tr)uSDX CAT docs specify). |
| 5 | Hamlib polls (`IF;` `FA;` `MD;`) during TX interrupted the audio stream with `;`, and the original never resumed it with `US`, which broke TX audio and the un-key. | Polls during TX (and for 1 s after un-key) are **answered from the last known reply**, with the IF TX/RX flag set correctly. The audio stream is never interrupted. |
| 6 | RTS/DTR PTT (Windows) and VOX used the old key/un-key. | CAT, RTS/DTR and VOX all use the same `start_tx()` / `stop_tx()`. |
| 7 | The driver could exit or restart while keyed. | It sends `RX;` on stop or restart if it was transmitting. |

## Slow, retried and failing CAT commands
| # | Problem | Fix |
|---|---|---|
| 8 | **Serial ports were opened non-blocking (`write_timeout=0`)**, so bytes (audio, `;`, `US`, even `RX;`) were **silently dropped** whenever the buffer was full. | Blocking writes with a 2 s timeout, on the radio port and the virtual CAT port. |
| 9 | When a short `US<audio>;` segment arrived in one read, the parser ignored its `;` and **swallowed the next CAT reply** as audio. Hamlib timed out (0.5 s) and retried almost every command, so the driver was slow. | Parser fixed. Replies now arrive first time, in ~5–10 ms. |
| 10 | After TX the radio resumes RX audio **without a `US` header**, which was forwarded to WSJT-X as "replies" ("Protocol error", garbage). | Anything that doesn't start like a CAT reply (A–Z or `?`) is treated as audio. |
| 11 | Stray radio replies (`?;` from the extra `;`, `E;` after TX, the `UA2;` echo) reached Hamlib and knocked its replies out of step. | Filtered out. |

## macOS usability
| # | Change |
|---|---|
| 12 | Fixed CAT port name **`/tmp/trusdx`**. The real `/dev/ttys…` number changes each run. |
| 13 | `macOS/install.sh` matches Python to Homebrew's PortAudio (Intel/Rosetta or Apple Silicon); `macOS/trusdx.sh` stops any copy already running (two copies garbled CAT). |
| 14 | Error messages now include the real reason (port busy, permission, missing device); macOS gets BlackHole hints instead of Linux ones. |
| 14a | **Radio reconnect:** each reconnect gets a new run number, so threads from the previous run exit (the old playback thread used to survive in a wait loop). The RX buffer is cleared and the old audio streams are closed. Before, after unplugging and replugging the radio, two playback threads fed BlackHole and the WSJT-X input showed 100%. |
| 14b | **RX audio at 100% / clicks:** RX audio was played as *unsigned* 8-bit (silence = 128). Whenever the stream ran dry (TX, an underrun, a reconnect or a disconnected radio) the gap was filled with zero bytes = full-scale negative DC, so the WSJT-X input jumped to 100% for seconds and underruns clicked. Now played as signed 8-bit (silence = 0). Measured on BlackHole: before, constant -32766 during every reconnect; after, 0 clipped samples in all tests. |
| 14c | Test hook (macOS/Linux): `kill -USR1 <driver pid>` forces a reconnect, exactly as unplugging the radio does. Each run logs the driver threads alive at start (should only be the TCP listener). Used for 20+ forced reconnects. |
| 14d | **RX audio gaps:** CAT polls interrupt the radio's audio stream, so with WSJT-X connected it delivers ~0.15% fewer samples than the 7812 S/s the audio device plays. The buffer slowly drained and a ~50 ms gap (underrun + refill) came about every 30 s. Elastic buffer: one sample is repeated when the buffer runs low and one dropped when it grows (inaudible). Measured with WSJT-X polling: 0 underruns in 90 s (was ~1 per 30 s). |
| 14e | `-v` logs RX audio statistics every 5 s: bytes from the radio, audio kept, played, underruns, buffer level. |
| 15 | New options: `--tx-rate`, `--rawlog`. Version banner at startup. |

## Windows
| # | Change |
|---|---|
| 16 | Replies to the CAT app go through `cat_write()`: if the app closed its end (VSPE COM8), a blocking write times out and the reply is dropped instead of crashing and restarting the driver. |
| 17 | `build.bat` / `build.ps1` install anything missing (Python 3.12 and NSIS via winget; nuitka, pyaudio, pyserial via pip), then build `Setup_truSDX_Driver_beta.exe`. |
| 18 | The NSIS script installs the Nuitka output recursively (`File /r`) and the uninstaller removes it recursively, since newer Nuitka versions use sub-folders. |
| 19 | **New `--cat-tcp PORT`:** CAT over a local TCP socket (`127.0.0.1:PORT`) instead of a virtual COM-port pair. Hamlib accepts `host:port` as the serial port (tested on macOS, Hamlib 4.7.2, TS-480 and DL2MAN profiles). One client at a time; reconnects (Test CAT) are handled. |
| 20 | **Two Windows installers** from one build: `_x64` (VSPE COM8/COM9 as before) and `_arm64` (Windows on ARM: CAT over TCP 4542, no VSPE, current ARM64-capable VB-CABLE and CH340 v3.9+ supplied in `arm64-drivers\`). The build uses x64 Python, since PyAudio has no ARM64 wheels; it runs emulated on ARM. |

## macOS and Linux packaging
| # | Change |
|---|---|
| 21 | macOS: `Start W5PL truSDX Driver.command` (double-click launcher) and `uninstall.sh` (stops the driver, removes its Python environment and `/tmp/trusdx`; asks before removing BlackHole/PortAudio, default keep). |
| 22 | Linux (**untested**): `install.sh` (apt/dnf/pacman/zypper packages, `dialout`/`uucp` group, offers to remove brltty, ModemManager note), `trusdx.sh` (creates the `TRUSDX` null sink and routes the driver to it automatically: `PULSE_SINK`/`PULSE_SOURCE`, plus moving its streams with `pactl` for PipeWire-ALSA systems), `uninstall.sh`. |
| 23 | Linux gets the stable **`/tmp/trusdx`** CAT port link too (was macOS only). |
| 24 | Radio detection falls back to the CH340's USB vendor ID (1A86) when the port's description doesn't say "USB Serial" (some CH340s report "USB2.0-Serial" on Linux). |
| 25 | Full user manual: [MANUAL.md](MANUAL.md). |

## Name
- Branded **W5PL Driver for DL2MAN (tr)uSDX**: installer title, Start-menu shortcut, Settings > Apps entry (publisher W5PL), install folder, `Setup_W5PL_truSDX_Driver_beta_x64.exe` / `_arm64.exe`, driver banner and console/terminal window title. Based on trusdx-audio by SQ3SWF / PE1NNZ, credited in the banner and installer. If an older "truSDX Driver" (factory or earlier beta) is installed, setup offers to remove it first and runs its uninstaller (silently, in place, waiting for it), before installing; the running driver is closed first.

## Not changed
- RX audio rate (7812 S/s), the CAT dialect (TS-480 / `ID020` emulation), and the Windows COM8/COM9 + VB-CABLE layout.
- Linux code paths are kept, but this beta hasn't been tested on Linux.
