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
if systemctl is-active --quiet ModemManager 2>/dev/null; then
  warn "ModemManager is running. It can probe new serial ports for a few seconds after the radio is plugged in."
  warn "If the radio is sometimes not found right after plugging in, wait 10 s, or: sudo systemctl disable --now ModemManager"
fi

command -v pactl >/dev/null || warn "pactl not found: create the TRUSDX audio device by hand (see the manual)."
chmod +x trusdx.sh uninstall.sh
say "Done. Start the driver with:  $HERE/trusdx.sh"
