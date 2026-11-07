# Notice

## This project
**W5PL Driver for DL2MAN (tr)uSDX** — Copyright (C) 2026 W5PL.

W5PL's changes and additions (the fixes in `trusdx-txrx.py`, the macOS, Linux and Windows packaging scripts, the
documentation and the test tools) are licensed under the **GNU General Public License v3.0** ([LICENSE](LICENSE)).

This program is distributed in the hope that it will be useful, but **WITHOUT ANY WARRANTY**; without even the implied
warranty of MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the GNU General Public License for details.

## Original work
`trusdx-txrx.py` is a modified version of **trusdx-audio** by **SQ3SWF** and **PE1NNZ**
(https://github.com/threeme3/trusdx-audio, "de SQ3SWF, PE1NNZ 2023"). The original repository does not state a license.
The original authors keep their rights to their code; the GPL-3.0 above covers W5PL's modifications. The unmodified
original is kept in `tools/trusdx-txrx.original.py`, and `tools/beta-fixes.patch` shows exactly what was changed.
If you are one of the original authors and want anything handled differently, please open an issue.

The (tr)uSDX radio and its CAT streaming protocol are by **DL2MAN** and **PE1NNZ** (https://dl2man.de).
"(tr)uSDX" and "DL2MAN" are used only to say which radio this driver is for; this project isn't affiliated with or
endorsed by them.

## Third-party components
These are separate programs, each under its own license, included unmodified only so the Windows installers can set
them up. They are **not** covered by this project's GPL-3.0 license:

| Component | Where | Author / license |
|---|---|---|
| VB-Audio Virtual Cable (VB-CABLE) | `windows/installer-build/Setup_vbcable/`, Windows installers | VB-Audio Software, https://vb-audio.com — donationware, see its license |
| Virtual Serial Ports Emulator (VSPE) 32/64-bit free edition | `windows/installer-build/SetupVSPE_32/`, Windows x64 installer | Eterlogic, see `SetupVSPE_32/License.rtf` |
| CH340/CH341 USB-serial driver | `windows/installer-build/CH341SER.EXE`, Windows installers | WCH (Nanjing Qinheng Microelectronics), https://www.wch-ic.com |

Used at run time, installed separately: Python, PyAudio (MIT), pySerial (BSD), PortAudio (MIT), BlackHole (GPL-3.0,
Existential Audio), Nuitka (Apache-2.0, build only), NSIS (zlib, build only).
