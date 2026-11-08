# Bug report: trusdx-audio (`trusdx-txrx.py`): radio stuck in TX, slow CAT, Hamlib errors

**To:** the trusdx-audio authors (SQ3SWF / PE1NNZ)
**From:** a (tr)uSDX user, with a tested patch attached (`tools/beta-fixes.patch`)
**Date:** 2026-11-07

Thank you for trusdx-audio. It makes the (tr)uSDX a one-cable digital-mode radio. While setting it up on macOS
with WSJT-X I hit several problems. The worst is that **the radio stays keyed after a transmission**. I traced
each one with driver logs, raw serial captures, and a small script that talks to the radio directly, without the
driver or WSJT-X (`tools/unkey_test.py`). Most of the bugs are in platform-independent code, so they should affect
Windows and Linux too. This matches reports that the Windows driver is slow and doesn't always key/un-key reliably.

A working patch is in this package: `tools/beta-fixes.patch` (unified diff against the original
`trusdx-txrx.py`, which applies cleanly). The patched driver is `trusdx-txrx.py`. Feel free to take any or all of it. (The `DRIVER_NAME` / banner / window-title lines only brand this beta build; drop them.)

## Test environment
| | |
|---|---|
| Radio | (tr)uSDX, firmware **2.00x**, Semi-QSK OFF, VOX OFF, power 0 W for TX tests |
| Host | macOS 13 (MacBook, Intel Homebrew/PortAudio), Python 3.11, pyserial 3.5, pyaudio 0.2.14 |
| Software | WSJT-X **v3.3.0-beta5**, Hamlib **4.7.2**; rig `Kenwood TS-480` and `DL2MAN (tr)uSDX` (same behaviour) |
| Audio / CAT | BlackHole 2ch; CAT via the driver's pty, PTT = CAT |
| Original source | the copy shipped with Setup_truSDX_Driver.exe / README dated 2025-03-22 (github.com/threeme3/trusdx-audio currently returns 404) |

---

## Bug 1 (critical): TX audio at 11520 S/s overflows the radio, which then stays keyed
`audio_tx_rate = 11520` uses **100% of the 115200 baud link** (8N1 = 11520 bytes/s). On longer transmissions
the radio's input falls behind and drops bytes, including the `;RX;`, so the transmitter stays on.

Direct test (no driver, no WSJT-X), tone at 0 W, un-key = 200 ms quiet + `;RX;` + `;UA2;`:

| TX length | TX rate | Result |
|---|---|---|
| 2 s | 2400 / 4800 / 7812 / 11520 S/s, silence or full-scale tone | **28/28** back in RX in ~0.3 s |
| 8 s | **11520** S/s | cycle 1 needed a second `RX;`; cycle 2 **stuck keyed** |
| 13 s (FT8 length) | 9600 S/s | 3/3 back in ~0.3 s |
| 13 s (FT8 length) | **8000** S/s | 3/3 back in ~0.3 s |

**Fix:** send TX audio at 8000 S/s (option `--tx-rate`), in evenly paced 20 ms pieces instead of 512-sample
bursts. This matches your CAT page, which says lower rates are OK if the samples are evenly spaced. Through the
driver: 3/3 FT8-length TX un-keyed, with RX audio back 0.216 / 0.220 / 0.221 s after `RX;`.

> **Correction (2026-11-08, after on-air tests):** 8000 S/s in 20 ms pieces un-keys reliably but **sounds garbled on
> air**: each piece still crosses the link at full speed, so the radio plays it too fast and then pauses. Better fix,
> tested on air: open the port with **2 stop bits** (`serial.Serial(..., stopbits=serial.STOPBITS_TWO)`) and send at
> **10473 S/s** (= 115200 / 11). The link itself then spaces every sample evenly, and the radio gets ~9% spare time
> per byte. Clean audio on a second receiver, 190+ PSK Reporter spots in 5 minutes, QSOs completed, un-key in 0.1 s.
> At 11520 S/s with 1 stop bit, the same radio got stuck or rebooted after transmissions.

## Bug 2 (critical): `RX;` sent straight behind the TX audio is ignored
`handle_cat()` in TX does `tx_cat_delay()` (flush + 10 ms), then `;`, then `RX;`. The radio often ignores it,
replying `?;`, and keeps transmitting. **Fix:** stop the audio, flush, **200 ms quiet**, `;RX;`, 100 ms, `;UA2;`
(see bug 3). Measured 18/18 and 9/9 from WSJT-X Tune, plus 3/3 full FT8 slots.

## Bug 3 (high): the radio stops CAT streaming after TX
After un-keying, the radio sends no RX audio, misses the first try of CAT commands, and on the next `TX0;` keys
up **without** TX audio mode, answering every audio byte with `E;` (and then ignoring `RX;`). **Fix:** send `;UA2;`
(or `UA1;`) after every un-key. Also added: a watchdog that resends UA if no RX audio for 1.5 s, a streaming
check before `TX0;`, and a fallback second `;RX;;UA2;` 1.5 s later only if RX audio didn't return.

## Bug 4 (high): Hamlib's plain `TX;` keys the radio without CAT audio
Both Hamlib profiles send `TX;`. The driver forwards it unchanged, so the radio keys up but parses the streamed
audio as commands:
```
I: b'TX;'
O: b'E;'  O: b'E;'  O: b'E;'  ... (hundreds)   -> Hamlib: "IO error ... while getting current VFO frequency"
```
**Fix:** always key with **`TX0;`**, then **`US`** 50 ms later. Your CAT page says audio follows `US`.
Audio sent straight after `TX0;` sometimes produced `E;` too.

## Bug 5 (high): CAT polls during TX break the TX audio stream
Hamlib keeps polling (`IF;` `FA;` `MD;`) during TX. The driver interrupts the stream with `;` + command but
never resumes it with `US`, which your CAT page requires ("Audio resumes after the CAT information, signaled by
a `;US`"). After the first poll, the audio is parsed as commands (`E;` flood), the poll gets `?;`, Hamlib reports
"Command rejected by the rig", and the radio ends up ignoring `RX;`.
**Fix:** during TX (and for 1 s after un-key), answer status queries from the last cached reply, with the `IF`
TX/RX flag set. Other commands are sent as `;` + cmd + `US`.

## Bug 6 (high): non-blocking serial writes silently drop bytes
Both ports are opened with `write_timeout = 0` (non-blocking). With the link full of TX audio, `write()` writes
only what fits and the return value is ignored, so pieces of the audio, `;`, `US` and even `RX;` are **lost**.
**Fix:** `write_timeout = 2` (blocking) on both `ser` and `ser2`.

## Bug 7 (high): CAT replies lost after a whole `US<audio>;` segment, making CAT slow
In `handle_rx_audio()`, when not streaming and a chunk starts with `US`, the code sets `status[1] = True` and
returns, **ignoring that the chunk may already end with `;`**. The next CAT reply is then appended to the audio
buffer. Hamlib times out (~0.5 s) and resends, so almost every command was sent twice:
```
I: b'FW;'              (no reply)
I: b'FW;'   (+0.52 s)  retry
O: b'FW4000;'
```
Raw capture showing the cause (`st` = streaming flag): `st=1 bb=b'FW400' raw=b'0;US…'`. The reply was eaten as
audio. **Fix:** close the stream when the `US…` chunk ends in `;` (and keep its audio). After the fix: replies
first time, in ~5–10 ms.

## Bug 8 (medium): RX audio forwarded to the CAT port after TX
After TX the radio resumes RX audio **without a `US` header**. When not streaming, it's forwarded to the CAT
app: `O: b'\x80\x81\x83\x80…E;'`, and Hamlib reports "Protocol error". **Fix:** a chunk that doesn't start like a
CAT reply (A–Z or `?`) is treated as stream data.

## Bug 9 (medium): stray replies reach Hamlib
`?;` (from the extra `;`), `E;` after TX, and the radio's echo of `UA2;` reached Hamlib and knocked its replies out
of step. **Fix:** filter them for a short time after the driver's own commands.

## Bug 10 (medium): RTS/DTR PTT (Windows) and VOX
`handle_rts_dtr()` and `handle_vox()` use `;TX0;` (no `US`) and `tx_cat_delay` + `;RX;`, the same failing
sequence as bugs 2–4. **Fix:** CAT, RTS/DTR and VOX now share `start_tx()` / `stop_tx()`.

## Bug 11 (high): RX audio input jumps to 100% (unsigned 8-bit playback)
The RX output stream is opened as `paUInt8`, where silence is 128. Whenever the stream has nothing to play (during
TX, a short buffer underrun, a radio reconnect, or while a disconnected radio is being retried), the macOS audio
layer fills the gap with zero bytes, which in unsigned 8-bit is **full-scale negative DC**. WSJT-X's input meter
shows 100% (for seconds at a time during a reconnect) and underruns become loud clicks. Measured on BlackHole:
a constant -32766 (16-bit) during every forced reconnect. **Fix:** open the stream as `paInt8` and flip the sign
bit of each byte (`bytes.translate` with a 256-byte table); a zero-filled gap is then real silence. After the fix:
0 clipped samples in 4 reconnects and at idle.

## Bug 12 (medium): playback thread survives a reconnect
After a reconnect (radio unplugged and replugged), `play_receive_audio()`'s underrun wait loop never checked for
shutdown, so the old thread kept running next to the new one and both wrote to the audio device. **Fix:** a run
number (generation) per `run()`; threads exit when it changes. The RX buffer is cleared and the old streams closed.

## Bug 13 (low): RX audio gap about every 30 s
While the CAT app polls, the radio's audio stream is interrupted briefly by each reply, so it delivers ~0.15% fewer
samples than the nominal 7812 S/s the output stream plays (without polls it is exactly 7812). `play_receive_audio()`
drains the buffer, underruns, and waits for 10 chunks: a ~50 ms gap about every 30 s. **Fix:** elastic buffer
(repeat one sample when the buffer is low, drop one when it is high). Result: 0 underruns in 90 s with WSJT-X polling.

## Smaller items
- **Driver exits/restarts while keyed:** now sends `RX;` first.
- **`main()` restarts `run()` forever, so Ctrl+C only restarts it**, and two copies can end up on the same radio, which garbles CAT. The macOS launcher stops an existing copy.
- **macOS:** the pty is `/dev/ttysNNN`, which changes every run. The commented-out `/tmp/trusdx` symlink is now enabled on macOS.
- **Error messages swallow the exception** (`except Exception as e:` without printing `e`), and the macOS audio error suggests Linux `pactl`.
- **Docs:** the macOS install would benefit from noting Rosetta/Intel Homebrew vs. arm64 PortAudio (pyaudio must match its architecture).

## Addition (optional): CAT over TCP, `--cat-tcp PORT`
Windows on ARM can run the x64 driver program but can't load x64 drivers, and VSPE's 64-bit/ARM64 build is paid. Hamlib
accepts `127.0.0.1:PORT` as a rig's serial port (checked with Hamlib 4.7.2, TS-480 and DL2MAN profiles), so the patch adds
an option to serve CAT on a local TCP socket instead of a virtual COM pair. That removes the need for com0com/VSPE on
any platform.

## Not a bug, but worth knowing
With Semi-QSK off and VOX off, the radio itself behaves consistently. Every un-key failure above traces back to
bugs 1–6 (rate, missing `US`, dropped bytes, timing), not to the radio.

---

### Reproduce (at 0 W!)
```bash
# radio connected, driver stopped, WSJT-X closed
python3 tools/unkey_test.py /dev/cu.usbserial-XXXX --seconds 8 --rate 11520 --cycles 3   # gets stuck (bug 1)
python3 tools/unkey_test.py /dev/cu.usbserial-XXXX --seconds 13 --rate 8000 --cycles 3   # clean
```
On Windows, use the CH340 COM port instead (not COM8/COM9).

73, and thanks again for the driver.
