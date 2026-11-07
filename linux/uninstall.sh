#!/usr/bin/env bash
# W5PL Driver for DL2MAN (tr)uSDX - Linux uninstaller
# Stops the driver, removes the TRUSDX virtual audio device, the /tmp/trusdx CAT link and the private Python
# environment (if one was built). Distribution packages (python3-pyaudio, python3-serial, pactl) and your serial-port
# group membership are shared with other software and are kept; the commands to remove them are printed.
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$HERE"
# Driver processes only: Python running trusdx-txrx.py (a plain "pkill -f trusdx-txrx.py" would also kill e.g. an
# editor or viewer that has the file open)
driver_pids() { pgrep -f 'trusdx-txrx[.]py' | while read -r p; do [[ "$(ps -o comm= -p "$p" 2>/dev/null)" == *[Pp]ython* ]] && echo "$p"; done; }
say() { printf '\033[36m==>\033[0m %s\n' "$*"; }

say "W5PL Driver for DL2MAN (tr)uSDX - Linux uninstall"
PIDS=$(driver_pids)
if [[ -n "$PIDS" ]]; then say "Stopping the running driver"; kill $PIDS 2>/dev/null; sleep 2; fi
if command -v pactl >/dev/null; then
  for m in $(pactl list short modules 2>/dev/null | awk '/module-null-sink/ && /sink_name=TRUSDX/ {print $1}'); do
    pactl unload-module "$m" && say "Removed virtual audio device TRUSDX"
  done
fi
[[ -L /tmp/trusdx ]] && rm -f /tmp/trusdx && say "Removed /tmp/trusdx"
rm -rf .venv ../__pycache__
say "Done. You can now delete the release folder: $(dirname "$HERE")"
echo "Kept (shared with other software). To remove them too, e.g. on Debian/Ubuntu:"
echo "   sudo apt remove python3-pyaudio python3-serial"
echo "   sudo gpasswd -d $USER dialout      # serial-port access (uucp on Arch)"
