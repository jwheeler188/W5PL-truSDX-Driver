#!/bin/zsh
# W5PL Driver for DL2MAN (tr)uSDX - macOS uninstaller
# Stops the driver and removes what install.sh created (the private Python environment in this folder) and the
# /tmp/trusdx CAT link. Then asks about the shared pieces (BlackHole 2ch, PortAudio): other apps may use them,
# so the default is to keep them. The release folder itself is left for you to delete.
HERE="${0:A:h}"
cd "$HERE"
# Driver processes only: Python running trusdx-txrx.py (a plain "pkill -f trusdx-txrx.py" would also kill e.g. an
# editor or viewer that has the file open)
driver_pids() { pgrep -f 'trusdx-txrx[.]py' | while read -r p; do [[ "$(ps -o comm= -p "$p" 2>/dev/null)" == *[Pp]ython* ]] && echo "$p"; done; }
say() { print -P "%F{cyan}==>%f $*"; }
ask() { local a; read -r "a?$1 [y/N] "; [[ "$a" == [yY]* ]]; }

say "W5PL Driver for DL2MAN (tr)uSDX - macOS uninstall"
PIDS=$(driver_pids)
if [[ -n "$PIDS" ]]; then
  say "Stopping the running driver"
  kill ${=PIDS} 2>/dev/null; sleep 2
fi
[[ -L /tmp/trusdx ]] && rm -f /tmp/trusdx && say "Removed /tmp/trusdx"
rm -rf .venv .arch ../__pycache__
say "Removed the driver's Python environment"

if command -v brew >/dev/null; then
  if brew list --cask blackhole-2ch >/dev/null 2>&1; then
    if ask "Also uninstall BlackHole 2ch (virtual audio; other apps may use it; needs your password)?"; then
      brew uninstall --cask blackhole-2ch && print "   BlackHole removed - restart the Mac to finish."
    fi
  fi
  if brew list --versions portaudio >/dev/null 2>&1; then
    if ask "Also uninstall PortAudio (Homebrew library; other programs may use it)?"; then
      brew uninstall portaudio || print "   PortAudio kept (another Homebrew package needs it)."
    fi
  fi
fi
say "Done. You can now delete the release folder: ${HERE:h}"
