#!/usr/bin/env bash
# W5PL Driver for DL2MAN (tr)uSDX - install the network bridge as a service (starts at boot, restarts if it stops).
# Run on the computer the radio is plugged into (e.g. a Raspberry Pi), after ./install.sh.
#   ./install-netbridge.sh                 port 4532, 2 stop bits
#   ./install-netbridge.sh --rts-low       extra options are passed to trusdx-netbridge.py
# Laptop: trusdx-txrx.py --serial-url socket://THIS-COMPUTER.local:4532   (or ./trusdx.sh --serial-url ...)
# Remove: ./install-netbridge.sh --remove
# Do not run linux/trusdx.sh on this computer while the bridge runs: only one program can own the radio's port.
set -e
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
UNIT=/etc/systemd/system/trusdx-netbridge.service
say() { printf '\033[36m==>\033[0m %s\n' "$*"; }

if [[ "${1:-}" == "--remove" ]]; then
  sudo systemctl disable --now trusdx-netbridge 2>/dev/null || true
  sudo rm -f "$UNIT"; sudo systemctl daemon-reload
  say "Network bridge service removed"; exit 0
fi
[[ -f "$HERE/trusdx-netbridge.py" ]] || { echo "trusdx-netbridge.py not found next to this script"; exit 1; }
python3 -c "import serial" 2>/dev/null || { echo "pyserial missing: run ./install.sh first"; exit 1; }
pkill -f 'trusdx-netbridge[.]py' 2>/dev/null || true   # a copy started by hand

say "Installing the service ($UNIT) for user $USER"
sudo tee "$UNIT" >/dev/null <<UNITFILE
[Unit]
Description=W5PL (tr)uSDX network bridge (radio serial port on TCP 4532)
After=network-online.target
Wants=network-online.target

[Service]
User=$USER
SupplementaryGroups=dialout
ExecStart=/usr/bin/python3 -u $HERE/trusdx-netbridge.py -v $*
Restart=always
RestartSec=3

[Install]
WantedBy=multi-user.target
UNITFILE
sudo systemctl daemon-reload
sudo systemctl enable --now trusdx-netbridge
sleep 2
systemctl --no-pager --lines=3 status trusdx-netbridge | sed -n '1,3p;$p'
command -v ufw >/dev/null && sudo ufw status 2>/dev/null | grep -q "Status: active" && {
  say "Firewall (ufw) is on: allowing TCP 4532 from the local network"; sudo ufw allow 4532/tcp; }
say "Done. Log: journalctl -u trusdx-netbridge -f    Laptop: --serial-url socket://$(hostname).local:4532"
