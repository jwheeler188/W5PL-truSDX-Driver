#!/usr/bin/env bash
# W5PL Driver for DL2MAN (tr)uSDX - Linux installer (beta 2026-11-08, UNTESTED on Linux - please report results)
# Installs Python 3 + pyaudio + pyserial and pactl from your distribution, gives you access to the radio's serial
# port, and offers to remove brltty (which grabs CH340 USB-serial radios on Ubuntu/Debian). Safe to run again.
# Supports apt (Debian/Ubuntu/Mint/Raspberry Pi OS), dnf (Fedora), pacman (Arch/Manjaro), zypper (openSUSE).
set -e
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$HERE"
say() { printf '\033[36m==>\033[0m %s\n' "$*"; }
warn() { printf '\033[33mNOTE:\033[0m %s\n' "$*"; }
die() { printf '\033[31mERROR:\033[0m %s\n' "$*"; exit 1; }
ask() { local a; read -r -p "$1 [y/N] " a; [[ "$a" == [yY]* ]]; }
WANT_ALSA=0; [[ "${1:-}" == "--alsa" ]] && WANT_ALSA=1   # ./install.sh --alsa: also set up the ALSA loopback

say "W5PL Driver for DL2MAN (tr)uSDX - Linux install"
[[ -f ../trusdx-txrx.py ]] || die "trusdx-txrx.py not found next to the linux folder. Keep the release folder together."
SUDO=""; [[ $EUID -ne 0 ]] && SUDO="sudo"

if command -v apt-get >/dev/null; then
  PM=apt; GROUP=dialout
  say "Installing packages (apt)"
  $SUDO apt-get update -qq
  $SUDO apt-get install -y python3 python3-pyaudio python3-serial pulseaudio-utils
elif command -v dnf >/dev/null; then
  PM=dnf; GROUP=dialout
  say "Installing packages (dnf)"
  $SUDO dnf install -y python3 python3-pyaudio python3-pyserial pulseaudio-utils
elif command -v pacman >/dev/null; then
  PM=pacman; GROUP=uucp
  say "Installing packages (pacman)"
  $SUDO pacman -S --needed --noconfirm python python-pyaudio python-pyserial libpulse
elif command -v zypper >/dev/null; then
  PM=zypper; GROUP=dialout
  say "Installing packages (zypper)"
  $SUDO zypper --non-interactive install python3 python3-PyAudio python3-pyserial pulseaudio-utils
else
  die "No supported package manager found. Install Python 3, pyaudio, pyserial and pactl yourself, then run ../trusdx-txrx.py"
fi

# Python modules: the distribution packages, or a private environment (.venv) if they are missing
if python3 -c "import pyaudio, serial" 2>/dev/null; then
  say "Python modules OK: $(python3 -c 'import pyaudio, serial; print("pyaudio", pyaudio.__version__, "/ pyserial", serial.__version__)')"
  rm -rf .venv
else
  warn "pyaudio/pyserial packages not usable - building a private Python environment instead"
  case $PM in
    apt) $SUDO apt-get install -y python3-venv python3-dev portaudio19-dev gcc ;;
    dnf) $SUDO dnf install -y python3-devel portaudio-devel gcc ;;
    pacman) $SUDO pacman -S --needed --noconfirm portaudio gcc ;;
    zypper) $SUDO zypper --non-interactive install python3-devel portaudio-devel gcc ;;
  esac
  rm -rf .venv; python3 -m venv .venv
  .venv/bin/python -m pip install -q --upgrade pip
  .venv/bin/python -m pip install -q pyaudio pyserial
  .venv/bin/python -c "import pyaudio, serial" || die "pyaudio/pyserial could not be installed (see messages above)"
fi

# Serial port access
if id -nG "$USER" | tr ' ' '\n' | grep -qx "$GROUP"; then
  say "You are in the '$GROUP' group (serial port access)"
else
  say "Adding you to the '$GROUP' group for access to the radio's serial port"
  $SUDO usermod -aG "$GROUP" "$USER"
  warn "Log out and back in (or reboot) once, so the new group takes effect."
fi

# brltty (Braille display daemon) claims CH340 USB-serial devices on Ubuntu/Debian, so the radio's port disappears
if command -v brltty >/dev/null || systemctl list-unit-files 2>/dev/null | grep -q '^brltty'; then
  warn "brltty is installed. On many systems it grabs the (tr)uSDX's CH340 USB port, so the radio is 'not found'."
  if ask "Remove brltty? (Say no if you use a Braille display)"; then
    case $PM in
      apt) $SUDO apt-get remove -y brltty ;; dnf) $SUDO dnf remove -y brltty ;;
      pacman) $SUDO pacman -R --noconfirm brltty ;; zypper) $SUDO zypper --non-interactive remove brltty ;;
    esac
  fi
fi
# ModemManager probes new serial ports and can grab the radio for a few seconds after it is plugged in. Tell it to
# ignore the (tr)uSDX's CH340 (USB 1a86:7523) only; ModemManager keeps working for real modems.
UDEV_RULE=/etc/udev/rules.d/77-trusdx-modemmanager-ignore.rules
if command -v udevadm >/dev/null && [[ ! -f $UDEV_RULE ]]; then
  say "Telling ModemManager to leave the (tr)uSDX's USB port alone (udev rule for CH340 1a86:7523)"
  echo 'SUBSYSTEM=="tty", ATTRS{idVendor}=="1a86", ATTRS{idProduct}=="7523", ENV{ID_MM_DEVICE_IGNORE}="1", ENV{ID_MM_PORT_IGNORE}="1"' | $SUDO tee $UDEV_RULE >/dev/null
  $SUDO udevadm control --reload-rules && $SUDO udevadm trigger --subsystem-match=tty || true
fi

# Audio: PulseAudio/PipeWire (the TRUSDX device is created by trusdx.sh at every start), or the ALSA loopback for
# systems without them (or with ./install.sh --alsa). ALSA "plug" devices convert the sample rate for every program.
if command -v pactl >/dev/null && pactl info >/dev/null 2>&1 && [[ $WANT_ALSA == 0 ]]; then
  say "PulseAudio/PipeWire found: trusdx.sh creates the TRUSDX audio device at each start (WSJT-X: TRUSDX / Monitor of TRUSDX)"
else
  say "Setting up the ALSA loopback (snd-aloop) for audio"
  $SUDO modprobe snd-aloop id=Loopback || die "could not load the snd-aloop kernel module"
  echo "snd-aloop" | $SUDO tee /etc/modules-load.d/trusdx-snd-aloop.conf >/dev/null
  echo "options snd-aloop id=Loopback" | $SUDO tee /etc/modprobe.d/trusdx-snd-aloop.conf >/dev/null
  ASRC="$HOME/.asoundrc"; touch "$ASRC"
  sed -i '/^# >>> W5PL truSDX driver >>>/,/^# <<< W5PL truSDX driver <<</d' "$ASRC"
  cat >> "$ASRC" <<'ALSA'
# >>> W5PL truSDX driver >>> (added by linux/install.sh; removed by linux/uninstall.sh)
# Loopback pairs: playback hw:Loopback,0,N is heard on capture hw:Loopback,1,N. "plug" converts the sample rate.
pcm.trusdx_rx     { type plug; slave.pcm "hw:Loopback,1,0"; hint { show on; description "truSDX receive audio (WSJT-X input)" } }
pcm.trusdx_tx     { type plug; slave.pcm "hw:Loopback,0,1"; hint { show on; description "truSDX transmit audio (WSJT-X output)" } }
pcm.trusdx_drv_rx { type plug; slave.pcm "hw:Loopback,0,0"; hint { show on; description "truSDX driver side, receive (not for apps)" } }
pcm.trusdx_drv_tx { type plug; slave.pcm "hw:Loopback,1,1"; hint { show on; description "truSDX driver side, transmit (not for apps)" } }
# <<< W5PL truSDX driver <<<
ALSA
  say "ALSA loopback ready. In WSJT-X: Input trusdx_rx, Output trusdx_tx (trusdx.sh uses ALSA automatically)"
fi

command -v pactl >/dev/null || warn "pactl not found: create the TRUSDX audio device by hand (see the manual)."
chmod +x trusdx.sh uninstall.sh
say "Done. Start the driver with:  $HERE/trusdx.sh"
