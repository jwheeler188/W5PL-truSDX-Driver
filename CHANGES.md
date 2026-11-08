# Changes

## beta 2026-11-08-3 (clean transmit audio)

Reported by G4BWQ (issue #1): transmit audio was a low "warble" with little power. Confirmed on a second receiver: the
beta's transmit audio sounded nothing like FT8, and PSK Reporter had no spots in 2 hours.

| # | Problem | Fix |
|---|---|---|
| 37 | **Garbled transmit audio.** The radio plays each transmit byte the moment it arrives (DL2MAN: 11520 Hz "or lower if samples are sent continuously at equal intervals rather than in blocks"). Beta 2026-11-08-2 sent 8000 S/s in 20 ms bursts; each burst crossed the link at full speed, so the radio played it ~44% too fast, then paused, 50 times a second. The factory 11520 S/s sounded better but fills the link: the radio misses bytes (roughness) and, on long transmissions, the `RX;`. Re-tested on air 2026-11-08 at 11520: stuck/rebooting radio after transmissions, and a 3.1 s and a 9 s un-key in a direct tone test. | The serial port now uses **2 stop bits**, so the link itself spaces the bytes evenly at 115200/11 = **10473 B/s**, and transmit audio is sent at **10473 S/s**. The radio gets ~9% spare time per byte. 40 ms of silence after `US` absorbs audio-input jitter. New option `--stop-bits 1\|2` (default 2). |
| 38 | The boot-loop breaker's message blamed only front-panel mode/filter changes. | It now also says to power-cycle and check the radio's settings (TX Drive, CQ Interval). |

Tested on air 2026-11-08 (macOS, firmware 2.00x, 20 m, main antenna): direct tone test 10473/2 stop bits cleaner than
11520 by ear and un-keyed in 0.1 s first time; FT8 checked on a second receiver and with the MacBook microphone (clean
8-tone FT8, no clicks); **190+ PSK Reporter spots in 5 minutes, best +19 dB, 270+ in 20 minutes later**; QSOs completed
(N4OPI, VE3WEJ, K3YQA, WB8P, …); no stuck transmit and no driver warnings. Windows on ARM64 (CAT over TCP): 108 PSK Reporter spots in 6 minutes, median −14 dB, best +16 dB. Windows x64: not yet tested at the new rate.

Manual additions: Force Control Lines blank (thanks G4BWQ), Pwr slider advice for FT8, WSJT-X Auto Seq "CQ: First",
hearing receive audio on the computer, macOS Microphone permission, radio CQ Interval (menu 4.1) keying the radio by
itself, DL2MAN's CW Decoder menu item.

## Linux improvements (untested on Linux)

Compared with miltonics/truSDX-Linux, a Linux-only fork that is tested on several distros, our Linux setup lacked
two things; both added:

| # | Change |
|---|---|
| 34 | `linux/install.sh` adds a udev rule so **ModemManager ignores the (tr)uSDX's CH340** (1a86:7523) instead of only warning. ModemManager keeps working for other devices. |
| 35 | **ALSA loopback** for systems without PulseAudio/PipeWire (or `install.sh --alsa` / `trusdx.sh --alsa`): `snd-aloop` loaded at boot, and `plug` devices `trusdx_rx` / `trusdx_tx` (apps) and `trusdx_drv_rx` / `trusdx_drv_tx` (driver) in `~/.asoundrc`. `plug` converts the sample rate, so the driver's audio code is unchanged. `uninstall.sh` removes all of it. |
| 36 | New driver options **`--rx-audio NAME` / `--tx-audio NAME`** choose the audio devices by name on any platform (used by the ALSA mode); a missing device prints a warning. Tested on macOS. |

## beta 2026-11-08-2 (safety fix, replaces beta 2026-11-08)

| # | Problem | Fix |
|---|---|---|
| 31 | **beta 2026-11-08 could leave the radio keyed.** A radio stuck in TX sends no RX audio, so the new crash recovery took it for a crashed radio, and while "not responding" or paused it **did not send `RX;`** (WSJT-X's un-key never reached the radio). | **`RX;` always goes to the radio** at once, with the full un-key sequence, whatever state the driver thinks the radio is in. |
| 32 | A key-up while the radio wasn't streaming keyed it **without TX audio mode** (`E;` flood, "left TX audio mode"). | The driver **refuses to key** a radio that isn't streaming (and during a pause), with a warning. |
| 33 | WSJT-X re-opening the rig during TX sent `KS;`, which the driver passed to the radio and broke the TX audio stream. | Queries the driver can't answer from its cache get `?;` from the driver during TX. |

Tested at 0 W: 5 Tune cycles and 2 full FT8 transmissions (12.5–14.2 s), 7/7 clean un-keys, no warnings.

## beta 2026-11-08

Found while testing on firmware 2.00x: **using the radio's front panel (mode tap, filter double-tap, volume knob) while
CAT audio streams and WSJT-X polls crashes the radio**, which reboots in ~4 s. The driver then kept it in a **boot loop**
(WSJT-X re-polling and reconnecting, plus the driver's streaming watchdog). The crash itself is a firmware bug: the same
presses with streaming but no CAT polls, or with no computer at all, were fine; mode changes made by CAT (including
90 s in CW with 525 polls) were fine too. The driver now recovers instead of looping:

| # | Problem | Fix |
|---|---|---|
| 26 | After a crash, WSJT-X kept polling and re-opening the rig, `RX;`/`UA2;` followed, and the radio crashed again while booting (loop every ~6 s, until WSJT-X gave up). | **Quiet mode:** when the radio stops streaming in RX (1.5 s without audio), the driver answers WSJT-X's polls from the last replies and sends nothing to the radio. WSJT-X stays connected. Messages: `(tr)uSDX not responding` / `responding again`. |
| 27 | The streaming watchdog re-sent `UA2;` every second, and a `UA2;` during the radio's startup crashed it again. | Watchdog **backs off** (1, 2, 4, 8 s), and after the first try only re-enables streaming once the radio has been **completely quiet for 5 s** (finished booting). The short burst a rebooting radio sends no longer counts as "back": audio must stream steadily for 1 s. |
| 28 | Radio saved in CW kept crashing on every boot. | **Boot-loop breaker:** 3 crashes within 60 s → all traffic to the radio (polls, streaming, transmit) pauses for 60 s with instructions (switch back to USB, power-cycle if frozen), then one fresh attempt. |
| 29 | A reply cut off by the radio's reset (binary garbage inside an `IF` reply) was cached and served to WSJT-X. | Only well-formed replies are cached. |
| 30 | Every crash happened while the radio sent its long `IF;` reply. | `IF;` polls are answered by the driver from the radio's own `FA;` (frequency) and `MD;` (mode) replies (byte-identical to the radio's reply), cutting CAT traffic to the radio by a third. `--forward-if` restores the old behaviour. |

**Workaround until the firmware is fixed:** set filter, volume and TX Drive on the radio *before* starting WSJT-X, set
WSJT-X **Mode: USB**, and don't use the radio's controls while WSJT-X is connected (see the manual, section 17).

## beta 2026-11-07 (vs. original trusdx-txrx.py)

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
