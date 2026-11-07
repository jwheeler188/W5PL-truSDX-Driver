#!/bin/zsh
# W5PL Driver for DL2MAN (tr)uSDX - start the driver (macOS). Run install.sh once first.
#   ./trusdx.sh                  normal (CAT port /tmp/trusdx)
#   ./trusdx.sh --cat-tcp 4542   CAT over the network: WSJT-X Serial Port 127.0.0.1:4542
#   ./trusdx.sh -v               verbose log of every CAT command (for troubleshooting)
#   ./trusdx.sh --help           all options
# WSJT-X serial port: /tmp/trusdx  |  audio in/out: BlackHole 2ch
# Stop it: close this window (Ctrl+C only restarts it), or run ./uninstall.sh to remove it
HERE="${0:A:h}"
cd "$HERE"
# Driver processes only: Python running trusdx-txrx.py (a plain "pkill -f trusdx-txrx.py" would also kill e.g. an
# editor or viewer that has the file open)
driver_pids() { pgrep -f 'trusdx-txrx[.]py' | while read -r p; do [[ "$(ps -o comm= -p "$p" 2>/dev/null)" == *[Pp]ython* ]] && echo "$p"; done; }
[[ -x .venv/bin/python && -f .arch ]] || { echo "Run ./install.sh first (in $HERE)."; exit 1; }
PIDS=$(driver_pids)
if [[ -n "$PIDS" ]]; then
  echo "Stopping a driver copy that is already running (two copies on the radio's port garble CAT)..."
  kill ${=PIDS} 2>/dev/null; sleep 2
fi
exec arch -"$(cat .arch)" ./.venv/bin/python ../trusdx-txrx.py "$@"
