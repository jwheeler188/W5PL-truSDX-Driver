# W5PL Driver for DL2MAN (tr)uSDX — beta 2026-11-08

Audio and CAT over the (tr)uSDX's single USB cable for WSJT-X and other digital-mode programs. Based on trusdx-audio
by SQ3SWF and PE1NNZ.

## New in this beta: crash recovery

Testing on firmware 2.00x showed that **pressing the radio's buttons or turning its knobs while CAT audio streams and
WSJT-X is connected can crash the radio** (it reboots). This is a firmware issue: the same presses without CAT polling
were fine, and mode changes made over CAT were fine. The previous driver then kept the radio in a **reboot loop**. Now:

- While the radio isn't responding, the driver **answers WSJT-X from its last known state** and sends nothing to the
  radio, so WSJT-X stays connected and the radio can boot.
- Streaming is restarted only once the radio has **finished booting**.
- A **boot-loop breaker** pauses all traffic for 60 s if the radio crashes 3 times in a minute (for example when it's
  left in CW mode), and tells you what to do.
- `IF;` polls are answered by the driver from the radio's frequency and mode replies, cutting CAT traffic to the radio.

**How to avoid the crash:** set filter, volume and TX Drive on the radio before starting WSJT-X, set WSJT-X
**Settings → Radio → Mode: USB**, and don't use the radio's controls while WSJT-X is connected.

## Downloads

| File | For |
|---|---|
| `Setup_W5PL_truSDX_Driver_beta_x64.exe` | Windows 10/11 on Intel/AMD. CAT on **COM8**. |
| `Setup_W5PL_truSDX_Driver_beta_arm64.exe` | Windows 10/11 on ARM (Snapdragon / Copilot+). CAT on **127.0.0.1:4542**. |
| `W5PL-truSDX-Driver-beta-2026-11-08-macos-linux.zip` | macOS (`macOS/install.sh`) and Linux (`linux/install.sh`, untested). |
| `SHA256SUMS.txt` | Checksums of the files above. |

**Updating:** Windows: run the new setup over the old one. macOS/Linux: replace the folder and run `install.sh` again.
Read the **[manual](MANUAL.md)**, and do your first transmit test at **0 W**.

## Everything else (since beta 2026-11-07)
- No more stuck transmit (8000 samples/s transmit audio, reliable un-key), fast clean CAT, no receive-audio 100% jumps
  or gaps, clean reconnects, macOS installer, Windows on ARM edition, network CAT, uninstallers.

Full list with measurements: [CHANGES.md](CHANGES.md).

## Tested
- macOS 13, (tr)uSDX firmware 2.00x, WSJT-X v3.3.0-beta5 / Hamlib 4.7.2: CAT, Tune, full FT8 cycles, reconnects;
  the front-panel crash reproduced and isolated (Tests A–E); CAT mode changes in all modes; WSJT-X stays connected
  through a radio crash. After
  the changes, 80 s in CW with WSJT-X polling caused no crash. The boot-loop breaker is in place but hasn't been
  triggered in a test yet.
- Windows on ARM: installer, including removing the factory driver.
- **Not yet tested:** Windows on Intel/AMD hardware, Linux. Reports welcome.

## Known limitations
- Firmware 2.00x: front-panel use while WSJT-X is connected can crash the radio (see above). Power and filter width
  can't be set over CAT on this firmware.
- Receive audio is 8-bit at 7812 samples/s. The radio's **volume sets the receive level**: use 10–12.
- Windows ARM64: CAT over the network only (no COM port, no RTS/DTR PTT).
- The installers aren't code-signed: Windows SmartScreen shows a warning (More info → Run anyway).
