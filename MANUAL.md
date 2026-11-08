# W5PL Driver for DL2MAN (tr)uSDX — User Manual

**Version:** beta 2026-11-08 · **Platforms:** macOS, Windows (Intel/AMD and ARM64), Linux (untested)
**Based on:** [trusdx-audio](https://github.com/threeme3/trusdx-audio) by SQ3SWF and PE1NNZ

---

## Contents
1. [What the driver does](#1-what-the-driver-does)
2. [Before you start](#2-before-you-start)
3. [Radio settings](#3-radio-settings)
4. [Installing](#4-installing)
   - [Windows (Intel/AMD)](#41-windows-intelamd) · [Windows on ARM](#42-windows-on-arm) · [macOS](#43-macos) · [Linux](#44-linux)
5. [Configuring WSJT-X](#5-configuring-wsjt-x)
6. [First test (0 W)](#6-first-test-0-w)
7. [Everyday operation](#7-everyday-operation)
8. [Setting the receive level](#8-setting-the-receive-level)
9. [Other digital-mode programs](#9-other-digital-mode-programs)
10. [Command-line options](#10-command-line-options)
11. [Network CAT (`--cat-tcp`)](#11-network-cat---cat-tcp)
12. [Troubleshooting](#12-troubleshooting)
13. [Logs and reporting a problem](#13-logs-and-reporting-a-problem)
14. [Updating and uninstalling](#14-updating-and-uninstalling)
15. [Building from source](#15-building-from-source)
16. [How it works](#16-how-it-works)
17. [Known limitations](#17-known-limitations)
18. [Credits and license](#18-credits-and-license)

---

## 1. What the driver does

The DL2MAN (tr)uSDX can carry both **CAT control and audio over its single USB cable**, using its *CAT streaming*
protocol. Digital-mode programs like WSJT-X don't understand that protocol: they expect a serial port for CAT and a
sound card for audio. This driver sits in between:

```
 WSJT-X ──CAT──▶ virtual serial port ─┐                       ┌──▶ (tr)uSDX
        ◀─audio─ virtual audio cable ─┼──▶  W5PL driver  ◀──USB┤    CAT + RX/TX audio
                                      ┘                       └──  (CH340 USB-serial, 115200 baud)
```

- **CAT:** WSJT-X talks to a virtual serial port (Windows `COM8`, macOS/Linux `/tmp/trusdx`) or a local network port
  (`127.0.0.1:4542`). The driver forwards the commands to the radio.
- **Receive audio:** the radio streams 8-bit audio at 7812 samples/s over USB. The driver plays it into a virtual audio
  cable, which WSJT-X records from.
- **Transmit audio:** WSJT-X plays into the virtual audio cable. The driver records it and streams it to the radio at
  8000 samples/s while it is keyed.
- **PTT:** WSJT-X keys the radio by CAT (recommended). RTS/DTR (Windows, COM8) and VOX (Linux) also work.

No audio cables or external sound card are needed: a laptop, the (tr)uSDX, a USB cable and an antenna.

### What this version fixes
Compared to the factory driver, it fixes **the radio staying stuck in transmit**, slow and retried CAT commands,
Hamlib "protocol error" / timeout messages, receive audio jumping to 100%, and short receive-audio gaps. It adds
macOS and Windows-on-ARM support and network CAT. The full list, with measurements, is in [CHANGES.md](CHANGES.md).

---

## 2. Before you start

You need:
- A **DL2MAN (tr)uSDX** with firmware **R2.00u or newer** (tested: **2.00x**). CAT streaming needs a 2.00 firmware.
- A **USB data cable** (not a charge-only cable).
- **WSJT-X** (tested: v3.3.0-beta5 with Hamlib 4.7.2; older WSJT-X 2.x also works with the TS-480 rig model).
- One of:
  - **Windows 10/11**, Intel/AMD or ARM64 (Snapdragon / Copilot+ PCs);
  - **macOS** 12 or newer, Intel or Apple Silicon (tested: macOS 13);
  - **Linux** with PulseAudio or PipeWire (Debian/Ubuntu, Fedora, Arch, openSUSE, Raspberry Pi OS). Not yet tested.
- Optional: the radio's **12 V supply** for full power. USB power alone gives very little output.

> **Safety:** do your first transmit tests at **0 W** or into a dummy load (section 6). If the radio ever stays
> keyed, **switch the radio off**, then send a log (section 13).

---

## 3. Radio settings

| Setting | Value | Why |
|---|---|---|
| Firmware | **R2.00u or newer** (tested 2.00x) | CAT audio streaming |
| Menu 2.4 **Semi-QSK** | **OFF** | Semi-QSK switches back to RX on its own during digital transmissions |
| **VOX** | **OFF** | Let WSJT-X key the radio by CAT |
| **Volume** | **10–12** | Sets the receive audio level sent to WSJT-X. See section 8 |
| Mode | **USB** | WSJT-X sets and keeps it with *Mode: USB* (section 5) |
| **Filter** | **3 kHz** (or full) | FT8 signals use 200–3000 Hz |
| **TX Drive** | your usual setting | Fine-tune power with WSJT-X's Pwr slider |

> **Set the filter, volume and TX Drive on the radio before you start WSJT-X, then leave the radio's controls alone
> while WSJT-X is connected.** On firmware 2.00x, pressing the radio's buttons or turning its knobs while CAT audio
> streams and WSJT-X polls can crash the radio (it reboots). See [section 17](#17-known-limitations). Power and filter
> width can't be set over CAT on this firmware; frequency and mode can, and WSJT-X does that safely.

The driver turns the radio's speaker off while it runs (use `--unmute` to keep it on).

---

## 4. Installing

> **Only one driver at a time.** Only one program can use the radio's USB port. Don't run the factory driver and
> this one together, and don't start two copies.

### 4.1 Windows (Intel/AMD)

1. Download **`Setup_W5PL_truSDX_Driver_beta_x64.exe`** from the release page.
2. Run it. Windows SmartScreen may warn about an unrecognised app: click **More info → Run anyway** (the installer
   isn't code-signed).
3. **If the factory "truSDX Driver" (or an earlier beta) is installed,** setup asks:
   **Yes** = remove it now (recommended), **No** = keep it, **Cancel** = stop. It must be removed *before* installing,
   because its uninstaller also removes the COM8/COM9 virtual port pair that this driver uses. Setup reinstalls the
   pair afterwards.
4. Setup installs, in order:
   - the driver program (`C:\Program Files\W5PL Driver for DL2MAN (tr)uSDX\`);
   - **VSPE**, a virtual serial port pair **COM8 ↔ COM9** (the driver uses COM9, WSJT-X uses COM8);
   - the **CH340** USB driver for the radio: connect the radio by USB and click **INSTALL** when asked;
   - **VB-Audio CABLE**, the virtual audio cable: click **Install Driver**. You may ignore the web page it opens.
5. Restart Windows if VB-CABLE asks you to.
6. Start **W5PL Driver for DL2MAN (tr)uSDX** from the Start menu. A console window opens. When it shows
   **`(tr)uSDX driver OK!`**, start WSJT-X (section 5: Serial Port **COM8**).

If **COM8 or COM9 already exists** (for example, Windows gave the radio's USB port COM8), the driver warns about a
conflict: in Device Manager → Ports → USB-SERIAL CH340 → Port Settings → Advanced, give the radio another COM number.

### 4.2 Windows on ARM

Windows on ARM runs the driver program emulated, but device drivers must be native ARM64, and the free VSPE virtual
COM port is x86/x64 only. So the ARM64 edition uses **network CAT** instead of COM8.

1. Download **`Setup_W5PL_truSDX_Driver_beta_arm64.exe`** and run it (SmartScreen: **More info → Run anyway**).
2. If an older "truSDX Driver" is installed, choose **Yes** to remove it first.
3. Setup installs the driver, the **CH340 v3.9+** USB driver (ARM64) and the current **VB-CABLE** (ARM64).
4. At the end it reminds you: in WSJT-X set **Serial Port** to **`127.0.0.1:4542`** and **PTT Method** to **CAT**.
5. Start **W5PL Driver for DL2MAN (tr)uSDX** from the Start menu. Its shortcut already includes `--cat-tcp 4542`.
   The console shows `CAT over TCP: set the WSJT-X Serial Port to 127.0.0.1:4542`.

RTS/DTR PTT isn't available on ARM (there is no COM port); use CAT PTT.

### 4.3 macOS

Works on Intel and Apple Silicon Macs. Everything except BlackHole and PortAudio stays inside the driver folder.

1. Install **Homebrew** if you don't have it: https://brew.sh
2. Install **BlackHole 2ch** (the virtual audio cable), then **restart the Mac**:
   ```bash
   brew install --cask blackhole-2ch
   ```
   It asks for your password, because it installs an audio driver.
3. Download and unzip the release (`W5PL-truSDX-Driver-…-macos-linux.zip`). Keep the folder together; you can move it
   anywhere first (for example, to your Applications or Documents folder).
4. In Terminal, run the installer once:
   ```bash
   cd path/to/W5PL-truSDX-Driver/macOS
   ./install.sh
   ```
   It installs PortAudio (Homebrew) and builds a private Python environment in `macOS/.venv`. On Apple Silicon with an
   Intel (Rosetta) Homebrew, it automatically builds an Intel environment to match.
5. Start the driver: double-click **`Start W5PL truSDX Driver.command`** in the `macOS` folder, or run
   `./trusdx.sh`. The first time, macOS may block the double-click: right-click → **Open** → **Open**.
6. When it shows **`(tr)uSDX driver OK!`**, start WSJT-X (section 5: Serial Port **`/tmp/trusdx`**).

Leave the Terminal window open while operating. To stop the driver, close the window. **Ctrl+C restarts it** rather
than stopping it. Starting it again stops a copy that's already running.

### 4.4 Linux

> **Not yet tested on Linux.** The driver code is shared with macOS (where it is tested), and the Linux scripts follow
> the factory driver's Linux instructions, but nobody has run this release on Linux yet. Please test at 0 W first and
> report what you find.

1. Download and unzip the release, then run the installer:
   ```bash
   cd path/to/W5PL-truSDX-Driver/linux
   ./install.sh
   ```
   It uses your package manager (apt, dnf, pacman or zypper) to install Python 3, pyaudio, pyserial and `pactl`, and:
   - adds you to the **`dialout`** group (**`uucp`** on Arch) for access to the radio's port. **Log out and back in
     once** afterwards;
   - offers to remove **brltty**, a Braille-display service that grabs the radio's CH340 USB port on Ubuntu and Debian
     (answer **no** if you use a Braille display);
   - warns if **ModemManager** is running, since it can probe the radio's port for a few seconds after you plug it in.
2. Start the driver:
   ```bash
   ./trusdx.sh
   ```
   It creates a virtual audio device called **`TRUSDX`** (a PulseAudio/PipeWire "null sink") and connects the driver to
   it automatically.
3. In WSJT-X use Serial Port **`/tmp/trusdx`**, audio Input **`Monitor of TRUSDX`** and Output **`TRUSDX`**.

If the driver's audio doesn't reach WSJT-X, open **pavucontrol** while the driver runs: on the *Playback* tab set the
driver (python3) to **TRUSDX**, and on the *Recording* tab set it to **Monitor of TRUSDX**.

On Linux, **VOX** PTT is also available (`./trusdx.sh --vox`), but CAT PTT is recommended.

---

## 5. Configuring WSJT-X

Start the driver first and wait for `(tr)uSDX driver OK!`, then start WSJT-X.

### File → Settings → Radio

| Setting | Windows x64 | Windows ARM64 | macOS | Linux |
|---|---|---|---|---|
| **Rig** | `DL2MAN (tr)uSDX` or `Kenwood TS-480` | same | same | same |
| **Serial Port** | **`COM8`** | **`127.0.0.1:4542`** | **`/tmp/trusdx`** (type it in) | **`/tmp/trusdx`** (type it in) |
| Baud Rate | 115200 | 115200 | 115200 | 115200 |
| Data Bits / Stop Bits / Handshake | Default | Default | Default | Default |
| Poll Interval | **2–5 s** (any works) | same | same | same |
| **PTT Method** | **CAT** (RTS/DTR also works) | **CAT** | **CAT** | **CAT** (or VOX) |
| **Mode** | **USB** | USB | USB | USB |
| Split Operation | None | None | None | None |
| Transmit Audio Source | either | either | either | either |

**Poll Interval:** any value works with this driver. On firmware 2.00x, a few seconds (2–5 s) means less CAT traffic
while you operate, which seemed to make the front-panel crash (section 17) less likely.

**Mode: USB** makes WSJT-X put the radio in USB by CAT (safe), including if it was left in another mode. *None* also
works, but then the radio must already be in USB.

**Which rig model?**
- **`DL2MAN (tr)uSDX`** is listed in newer WSJT-X versions with a recent Hamlib (tested: WSJT-X v3.3.0-beta5,
  Hamlib 4.7.2). Use it if your WSJT-X has it.
- **`Kenwood TS-480`** works on any WSJT-X version: the (tr)uSDX speaks the TS-480 CAT dialect and the driver reports
  itself as a TS-480. If TS-480 is missing, TS-440 also works.
- Both behave the same with this driver.

### File → Settings → Audio

| Setting | Windows | macOS | Linux |
|---|---|---|---|
| Input (Soundcard) | **CABLE Output** | **BlackHole 2ch** | **Monitor of TRUSDX** |
| Output (Soundcard) | **CABLE Input** | **BlackHole 2ch** | **TRUSDX** |

(The Windows names look crossed but are right: WSJT-X *records* from the cable's output and *plays* into its input.)

Click **Test CAT**. It should turn **green**. Then **Test PTT**: the radio should show transmit, and return to receive
when you click it again. Click **OK**.

### Transmit level
Set the WSJT-X **Pwr** slider (bottom right) so the radio isn't overdriven: start at about −10 dB and raise it until the
radio's output stops increasing, then back off slightly. Overdriving distorts the signal and causes splatter.

---

## 6. First test (0 W)

Do this with the radio's power set to **0 W** (menu), or into a dummy load, before connecting an antenna:

1. Start the driver, then WSJT-X. **Test CAT** must be green.
2. Click **Tune** for about 10 s, then click it again to stop. Repeat three times. The radio must show transmit, then go
   back to the **S-meter** within a fraction of a second each time.
3. On an FT8 frequency, click **CQ** and **Enable Tx** for 2–3 full slots (12.6 s each). The radio must return to the
   S-meter at the end of every slot, and the waterfall must keep running between transmissions.
4. Connect the antenna and repeat at low power.

If the radio stays keyed at any point: **switch the radio off**, then follow section 13.

> If the radio has crashed or rebooted since you last checked, look at **TX Drive** before a 0 W test: a crash can
> reset it (section 17).

---

## 7. Everyday operation

1. Connect the radio by USB and switch it on.
2. Start the driver (Start menu on Windows; `Start W5PL truSDX Driver.command` on macOS; `./trusdx.sh` on Linux).
3. Wait for `(tr)uSDX driver OK!`, then start WSJT-X.
4. Operate from WSJT-X. **Don't use the radio's buttons or knobs while WSJT-X is connected** (section 17). To change
   something on the radio, close WSJT-X first (the driver can keep running), change it, then start WSJT-X again.
5. When you're done, close WSJT-X, then close the driver window.

**Unplugging or switching off the radio** while the driver runs is fine: the driver shows `truSDX device not found`
until the radio is back, then reconnects by itself. WSJT-X may show a rig error during that time; click **Retry**, or
**Test CAT** in Settings, once the driver shows OK again.

**If the radio crashes and reboots** (usually after its controls were used while WSJT-X was connected), the driver
shows `(tr)uSDX not responding` and keeps WSJT-X connected with the last known frequency and mode. It gives the radio
quiet time to boot, then restarts streaming and shows `(tr)uSDX responding again`. If it crashes 3 times within a
minute (typically because it was left in CW), the driver pauses all traffic to it for 60 s and says so: switch the
radio back to USB (power-cycle it if it's frozen) and it carries on.

When the driver stops or restarts while transmitting (Ctrl+C, a radio reconnect), it un-keys the radio first. Closing
the window may end it too abruptly for that, so stop transmitting in WSJT-X before closing the driver.

---

## 8. Setting the receive level

The (tr)uSDX sends receive audio **after its volume control**, as 8-bit samples, and WSJT-X has no input-level slider
for a virtual audio cable. So **the radio's volume knob is the receive level control.**

- **Too low** (volume around 8–9 on a quiet band): the band noise is smaller than the smallest 8-bit step and rounds
  to digital silence. The WSJT-X input meter drops to zero or flickers, it looks like the audio keeps dropping out, and
  weak signals are lost.
- **Right:** on band noise with the antenna connected, the WSJT-X input meter shows about **30–50 dB**. With a typical
  antenna that's volume **10–12**.
- **Too high:** strong signals clip and the WSJT-X meter goes red. Turn it down a step.

Set it once on a quiet part of the band; it doesn't need changing between bands unless the noise level is very different.

---

## 9. Other digital-mode programs

Any program that uses Hamlib or a Kenwood TS-480 CAT profile and a sound card should work with the same settings:
**JS8Call**, **fldigi**, **FreeDV**, **VarAC**, **Winlink/VARA** and others. Use the same serial port, rig model, audio
devices and PTT method as for WSJT-X. Only WSJT-X has been tested so far.

Only **one** program can use the CAT port at a time.

---

## 10. Command-line options

Add options after the launcher (macOS/Linux: `./trusdx.sh -v`; Windows: edit the Start-menu shortcut's *Target*, or
run the `.exe` from a command prompt).

| Option | Meaning |
|---|---|
| `-v`, `--verbose` | Log every CAT command and reply, and receive-audio statistics every 5 s. Use it when reporting problems. |
| `--cat-tcp PORT` | CAT over a local network port `127.0.0.1:PORT` instead of a virtual serial port (section 11). `0` = off. |
| `--unmute` | Keep the radio's speaker on while the driver runs. |
| `--direct` | Use the system's default audio devices instead of BlackHole / VB-CABLE / TRUSDX. |
| `--no-rtsdtr` | (Windows) Ignore RTS/DTR on COM8 as PTT. |
| `--vox` | (Linux) Key the radio when transmit audio arrives (VOX PTT). |
| `--tx-rate N` | Transmit audio sample rate sent to the radio (default **8000**). Don't use 11520: it overflows the radio on long transmissions and leaves it stuck keyed. |
| `--forward-if` | Send WSJT-X's `IF;` polls to the radio instead of answering them from its `FA;`/`MD;` replies (the default since beta 2026-11-08; section 16). |
| `-B N`, `--block-size N` | Receive audio block size (default 512). |
| `-T N`, `--tx-block-size N` | Serial read block size (default 48). |
| `--rawlog FILE` | Debugging: record the raw data from the radio to a file. |
| `-h`, `--help` | Show all options. |

---

## 11. Network CAT (`--cat-tcp`)

Instead of a virtual serial port, the driver can accept CAT on a local network port. WSJT-X's Hamlib accepts
`host:port` as its serial port.

- **Start the driver with** `--cat-tcp 4542` (the Windows ARM64 shortcut already does).
- **In WSJT-X set** Serial Port **`127.0.0.1:4542`** and PTT Method **CAT**.
- Works on all platforms, so it's also an alternative to VSPE on Windows x64.
- The port only listens on `127.0.0.1` (this computer), so other computers can't connect to it.
- One program at a time. A reconnect (for example, clicking Test CAT again) is handled.
- RTS/DTR PTT isn't available in this mode.

---

## 12. Troubleshooting

| Symptom | Cause and fix |
|---|---|
| **Radio stays in transmit** | Switch the radio off. Check Semi-QSK and VOX are **OFF** and the firmware is 2.00u or newer. Make sure no second driver copy is running. Report it with a `-v` log (section 13). |
| `truSDX device not found` (repeating) | The radio is off, unplugged, or the cable is charge-only. **Windows:** Device Manager → Ports must show *USB-SERIAL CH340*; if not, reinstall the CH340 driver. **macOS:** `ls /dev/cu.usbserial*`. **Linux:** `ls /dev/ttyUSB*`; if it appears and then vanishes, remove brltty (section 4.4). |
| `could not be opened … is another program using it?` / port busy | Another program has the radio's port: the factory driver, a second copy of this driver, or a terminal program. Close it. |
| **Linux:** `Permission denied` on `/dev/ttyUSB0` | You aren't in the `dialout` (Arch: `uucp`) group yet. Run `install.sh`, then log out and back in. |
| WSJT-X **Test CAT** red, "Communication timed out" | Wrong serial port, or WSJT-X was started before the driver. Check the port (Windows `COM8` / ARM `127.0.0.1:4542` / Mac and Linux `/tmp/trusdx`), wait for `driver OK!`, then Test CAT again. |
| WSJT-X **"Hamlib error: Protocol error"** | An older driver or two copies are running. Close all copies and start this one again. |
| **Conflict on COM port COM8/COM9** (Windows) | The radio's USB port got COM8 or COM9. Change it in Device Manager → CH340 → Port Settings → Advanced. |
| `Audio device could not be opened` | **Windows:** reinstall VB-CABLE (run the installer again). **macOS:** install BlackHole 2ch and restart. **Linux:** run `./trusdx.sh` (it creates TRUSDX), or check `pactl info` works. |
| WSJT-X input meter **at zero, flickering, or "dropping out"** | Receive level too low: turn the radio's volume up (section 8). |
| **No decodes**, but the input meter and waterfall look normal | Usually **noise, not the driver**: the waterfall is speckled with no FT8 traces, and the noise is louder than usual at the same volume. The most common source is the **laptop's power charger** (also USB hubs, LED lights, monitors). Unplug the charger and run on battery, or move it away from the antenna and the radio's USB cable. Also check the antenna connection, the radio's filter (3 kHz or full, not narrower), and the band (20 m fades after sunset; try 40 m). |
| WSJT-X input meter **stuck at 100% / red** | Should no longer happen with this version. If it does, restart the driver and report it with a `-v` log. |
| **No waterfall** but CAT works | WSJT-X Audio → Input must be CABLE Output / BlackHole 2ch / Monitor of TRUSDX. On Linux, check routing in pavucontrol. |
| Transmit shows on the radio but **no output power** | Check the WSJT-X Pwr slider, the radio's power setting, and that WSJT-X Audio → Output is CABLE Input / BlackHole 2ch / TRUSDX. |
| `WARNING: (tr)uSDX left TX audio mode` | The radio left audio mode during a transmission; the driver pauses transmit audio so the un-key gets through. Please report it with a `-v` log. |
| macOS: "cannot be opened because it is from an unidentified developer" | Right-click the `.command` file → Open → Open. |
| Windows: SmartScreen blocks the installer | More info → Run anyway. The installer is unsigned. |
| **Radio reboots** (display restarts) when you press a button or turn a knob | Firmware 2.00x crashes when its controls are used while CAT audio streams and WSJT-X polls (section 17). The driver recovers by itself. Set filter/volume/TX Drive before starting WSJT-X and leave the controls alone while it's connected. |
| `(tr)uSDX not responding` … `responding again` | The radio crashed and rebooted; the driver kept WSJT-X connected and restarted streaming. No action needed. |
| `crashed 3 times in a minute. Pausing all CAT traffic` | The radio keeps crashing, usually because it's in **CW** mode. Switch it back to **USB** (power-cycle it if it's frozen); the driver retries after 60 s. |
| After a crash or reboot: **TX Drive, Semi QSK or other settings changed** | The crash can reset saved settings. Before transmitting, check TX Drive, Semi QSK (OFF), PA Bias, Ref freq and LPF Config (section 17). |
| Radio **frozen** (display stuck, no reboot) | Power-cycle it. Nothing over USB can wake a hung radio. |
| Windows: driver won't start, "VB-CABLE denied" / audio device errors | Windows made VB-CABLE its **default** sound device. Control Panel → Sound: set the computer's own speakers (Playback) and microphone (Recording) as default, then restart the driver. Select CABLE only inside WSJT-X. |
| CAT drops out, or noise, only when the **12 V supply** is connected | Supply noise or a ground loop. A clip-on ferrite on the USB and power cables helps, as does a cleaner supply. |
| `||PaMacCore (AUHAL)|| Error … -10863` at macOS start | Harmless message from the audio library; ignore it. |

---

## 13. Logs and reporting a problem

Start the driver with **`-v`** to log every CAT command with a timestamp, plus receive-audio statistics:

- **macOS:** `./trusdx.sh -v 2>&1 | tee ~/Desktop/trusdx-log.txt`
- **Linux:** `./trusdx.sh -v 2>&1 | tee ~/trusdx-log.txt`
- **Windows:** open a command prompt and run
  `"C:\Program Files\W5PL Driver for DL2MAN (tr)uSDX\W5PL truSDX Driver.exe" -v > %USERPROFILE%\Desktop\trusdx-log.txt 2>&1`
  (ARM64: add `--cat-tcp 4542` before `-v`).

Reproduce the problem, stop the driver, and attach the log to an issue on the GitHub page. Please include your
operating system, radio firmware version, WSJT-X version and rig model, and what you did just before the problem.

The statistics line every 5 s looks like:
```
RX stats 5.0s: from trx 7864 B/s, audio 7798 S/s, played 7812 S/s (nominal 7812), underruns 0, buffered 6 chunks, streaming=1
```
`underruns` should stay at 0, and `audio`/`played` should be close to 7812.

For un-key problems, `tools/unkey_test.py` measures the radio's un-key timing directly, without the driver or WSJT-X
(**at 0 W only**; stop the driver and WSJT-X first): `python3 tools/unkey_test.py <serial port> --cycles 5 --seconds 13`.

---

## 14. Updating and uninstalling

### Updating
- **Windows:** run the new installer over the old one. It closes a running driver first.
- **macOS / Linux:** replace the release folder with the new one and run `install.sh` again.

### Uninstalling
- **Windows:** Settings → Apps → **W5PL Driver for DL2MAN (tr)uSDX** → Uninstall. This removes the driver and the VSPE
  COM8/COM9 pair. VB-CABLE and the CH340 driver stay installed (other programs may use them). To remove VB-CABLE too,
  run its setup again and click **Remove Driver**.
- **macOS:** run `macOS/uninstall.sh`. It stops the driver and removes its Python environment and `/tmp/trusdx`, then asks
  whether to also remove BlackHole 2ch and PortAudio (default: keep). Then delete the folder.
- **Linux:** run `linux/uninstall.sh`. It stops the driver and removes the TRUSDX audio device, `/tmp/trusdx` and any
  private Python environment. It keeps the distribution packages and your group membership, and prints the commands to
  remove those. Then delete the folder.

---

## 15. Building from source

The driver is a single Python file, **`trusdx-txrx.py`**, the same on all platforms.

- **Run it directly:** Python 3 with `pyaudio` and `pyserial`. macOS/Linux: the `install.sh` scripts set this up.
  Windows: `windows\run-from-python.bat` (needs x64 Python on ARM, since PyAudio has no ARM64 package).
- **Windows installers:** on a Windows 10/11 PC, double-click **`windows\installer-build\build.bat`**. It installs what's
  missing (x64 Python 3.11 and NSIS via winget; nuitka, pyaudio, pyserial via pip), builds `W5PL truSDX Driver.exe` with
  Nuitka, then builds `Setup_W5PL_truSDX_Driver_beta_x64.exe`. For the ARM64 installer, first put the ARM64 drivers in
  `windows\installer-build\arm64-drivers\` (see the `README.txt` there). The build runs in a local folder, so it also works
  from a Parallels/VMware shared folder.
- **Patch for the original driver:** `tools/beta-fixes.patch` is a unified diff from the original `trusdx-txrx.py`.

---

## 16. How it works

For the technically curious. The radio's CAT streaming protocol (DL2MAN):

- `UA2;` turns on audio streaming with the speaker off (`UA1;` with it on). The radio then sends `US` followed by a
  continuous stream of 8-bit audio bytes. Any `;` in the stream ends a segment; CAT replies arrive between segments.
- `TX0;` followed by `US` keys the radio and starts transmit audio, which the driver streams as 8-bit samples.
- `RX;` un-keys it.

CAT commands the (tr)uSDX answers on 2.00x (from DL2MAN's documentation and tested on the radio):

| Command | Meaning |
|---|---|
| `FA;` / `FAnnnnnnnnnnn;` | read / set frequency (Hz) |
| `MD;` / `MDn;` | read / set mode: 1 LSB, 2 USB, 3 CW, 4 FM, 5 AM |
| `IF;` | status: frequency and mode |
| `TX0;` / `TX2;` / `RX;` | transmit / tune (CW mode) / receive |
| `ID;` | 020 (TS-480) |
| `UA0;` `UA1;` `UA2;` / `US…` | audio streaming off / on with speaker / on, speaker muted; audio data |
| `PS;` `AI;` `FW;` `FL;` `AG0;` | fixed compatibility answers (`FW;` always says 4000) |
| `PC` `SH` `SL` `AG` `SM` `VX` `NB` … | not supported (`?;`): **power and filter width can't be set over CAT** |

What the driver does to make that reliable:

- **Transmit audio rate:** 8000 samples/s, sent in even 20 ms pieces. The factory 11520 samples/s used 100% of the
  115200-baud link and overflowed the radio on long transmissions, which then missed the `RX;` and stayed keyed.
- **Un-key sequence:** stop the audio, 200 ms quiet, `;RX;`, 100 ms, `;UA2;` (the radio stops streaming after a
  transmission, so streaming is re-enabled). A second un-key follows after 1.5 s only if receive audio hasn't returned.
- **CAT during transmit:** polls such as `IF;` `FA;` `MD;` would interrupt the audio stream, so they're answered from the
  last known reply (with the transmit flag set) instead of being sent to the radio.
- **Hamlib's `TX;`** is rewritten to `TX0;` + `US`, so the radio keys in audio mode.
- **Parser:** separates audio from CAT replies, including segments that arrive whole and audio that resumes after
  transmit without a `US` header; drops the radio's echoes and error replies that would confuse Hamlib.
- **Receive audio:** played as signed 8-bit, so gaps are silence rather than full-scale; an elastic buffer absorbs the
  ~0.15% rate difference caused by CAT polls.
- **Reconnects:** each connection has its own generation of threads, so threads from before a reconnect stop.
- **Watchdog:** if no receive audio arrives for 1.5 s, streaming is switched on again, backing off (1, 2, 4, 8 s) and,
  after the first try, only once the radio has been quiet for 5 s, so a rebooting radio isn't hit during startup.
- **Crash recovery:** while the radio isn't streaming, WSJT-X's polls are answered from the last replies and nothing is
  sent to the radio; 3 crashes within a minute pause all traffic for 60 s (boot-loop breaker).
- **`IF;` polls** are answered by the driver from the radio's own `FA;` and `MD;` replies (the result is byte-identical),
  so the radio never sends its long `IF` reply; every observed crash happened during that reply.

---

## 17. Known limitations

- **Firmware 2.00x crashes when its front panel is used while CAT audio streams and a program polls it.** Tested
  2026-11-07: a mode tap, filter double-tap or volume-knob turn with WSJT-X connected made the radio reboot (and it
  reboots again while left in CW). The same presses with streaming but no CAT polls, or with nothing connected, were
  fine, and mode changes made over CAT (including CW, 90 s with 525 polls) were fine too. So: set the radio up first,
  change mode from WSJT-X, and don't touch the radio's controls while WSJT-X is connected. The driver recovers from a
  crash by itself. 2.00x also has no setting to turn off its CW decoder or to lock the mode.
- **After a crash, check the radio's settings before transmitting.** A crash while the radio saves a mode or filter
  change can reset settings: in testing, TX Drive changed from 0 to 8 (so a "0 W" test would no longer be 0 W) and
  the mode came back as CW, and the stored CQ/CW messages were garbled, i.e. the radio's saved settings were
  corrupted. Check **TX Drive**, **Semi QSK (OFF)**, **PA Bias**, **Ref freq**, **LPF Config** and the CQ messages
  against your notes. If anything is garbled, use the radio's **Reset settings..** menu item and re-enter your values
  (don't transmit with power until PA Bias is right). Write down your calibration values (Ref freq, PA Bias, LPF
  Config, TX Drive) now, while they're right.
- **Linux** hasn't been tested with this release yet.
- Receive audio is **8-bit at 7812 samples/s** (a limit of the radio's USB streaming): audio above about 3.9 kHz doesn't
  exist, and the dynamic range depends on the volume setting (section 8). FT8/FT4/JS8 work well within that.
- Windows ARM64: CAT over the network only (no virtual COM port, no RTS/DTR PTT).
- Network CAT: one program at a time.
- The Windows installers and the macOS `.command` launcher aren't code-signed, so the OS warns the first time.
- Only one driver (and one CAT program) can use the radio at a time.

---

## 18. Credits and license

- **trusdx-audio** — the original driver, by **SQ3SWF** and **PE1NNZ**: https://github.com/threeme3/trusdx-audio
- **(tr)uSDX** — the radio and its CAT streaming protocol, by **DL2MAN** and **PE1NNZ**: https://dl2man.de
- **W5PL** — this release: fixes, macOS / Windows ARM64 / Linux packaging, network CAT, documentation.
- Bundled third-party software (Windows installers): **VB-Audio CABLE** (vb-audio.com, donationware), **VSPE** (Eterlogic),
  **CH340/CH341 driver** (WCH). Each is under its own license.
- macOS uses **BlackHole** (Existential Audio, GPL-3.0) and **PortAudio**; all platforms use **PyAudio** and **pySerial**.

**License:** W5PL's changes are under the **GNU GPL v3.0** ([LICENSE](LICENSE)), with **no warranty**. The original
trusdx-audio code doesn't state a license and stays its authors'. Details, and the third-party components' licenses:
[NOTICE.md](NOTICE.md).
