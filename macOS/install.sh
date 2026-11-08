#!/bin/zsh
# W5PL Driver for DL2MAN (tr)uSDX - macOS installer (beta 2026-11-08)
# Installs PortAudio (Homebrew), checks BlackHole 2ch, and builds a private Python environment
# with pyaudio + pyserial in this folder (.venv). Changes nothing else on the Mac. Safe to run again.
# Remove everything again with: ./uninstall.sh
set -e
HERE="${0:A:h}"
cd "$HERE"

say() { print -P "%F{cyan}==>%f $*"; }
die() { print -P "%F{red}ERROR:%f $*"; exit 1; }

say "W5PL Driver for DL2MAN (tr)uSDX - macOS install"
[[ -f ../trusdx-txrx.py ]] || die "trusdx-txrx.py not found next to the macOS folder. Keep the release folder together."
command -v brew >/dev/null || die "Homebrew not found. Install it from https://brew.sh and run this again."

if ! brew list --versions portaudio >/dev/null 2>&1; then
  say "Installing PortAudio (Homebrew)"
  brew install portaudio
fi
PA_LIB="$(brew --prefix portaudio)/lib/libportaudio.dylib"
[[ -e "$PA_LIB" ]] || die "PortAudio library not found at $PA_LIB"

# Match Python's architecture to PortAudio's (Intel Homebrew on Apple Silicon = x86_64 via Rosetta)
if file "$PA_LIB" | grep -q arm64; then ARCH=arm64; else ARCH=x86_64; fi
say "PortAudio is $ARCH - building the Python environment for $ARCH"

PY="$(command -v python3)" || die "python3 not found. Install Python 3 from python.org or: brew install python"
arch -$ARCH "$PY" -c "import sys" 2>/dev/null || die "$PY cannot run as $ARCH. Install the universal2 Python from python.org."

rm -rf .venv
arch -$ARCH "$PY" -m venv .venv
export CFLAGS="-I$(brew --prefix portaudio)/include" LDFLAGS="-L$(brew --prefix portaudio)/lib"
arch -$ARCH .venv/bin/python -m pip install -q --upgrade pip
arch -$ARCH .venv/bin/python -m pip install -q pyaudio pyserial
arch -$ARCH .venv/bin/python -c "import pyaudio, serial; print('pyaudio', pyaudio.__version__, '/ pyserial', serial.__version__)"
print "$ARCH" > .arch
chmod +x trusdx.sh uninstall.sh "Start W5PL truSDX Driver.command" 2>/dev/null || true

if system_profiler SPAudioDataType 2>/dev/null | grep -q "BlackHole 2ch"; then
  say "BlackHole 2ch found"
else
  print -P "%F{yellow}NOTE:%f BlackHole 2ch audio driver not found. Install it, then RESTART the Mac:"
  print   "      brew install --cask blackhole-2ch"
fi

say "Done. Start the driver: double-click 'Start W5PL truSDX Driver.command' in this folder, or run:"
print "      $HERE/trusdx.sh"
