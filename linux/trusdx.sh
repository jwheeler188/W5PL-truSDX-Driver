#!/usr/bin/env bash
# W5PL Driver for DL2MAN (tr)uSDX - start the driver (Linux, PulseAudio or PipeWire). Run install.sh once first.
#   ./trusdx.sh                  normal (CAT port /tmp/trusdx)
#   ./trusdx.sh --cat-tcp 4542   CAT over the network: WSJT-X Serial Port 127.0.0.1:4542
#   ./trusdx.sh -v               verbose log of every CAT command
#   ./trusdx.sh --alsa           use the ALSA loopback (install.sh --alsa) even if PulseAudio/PipeWire runs
# Audio: creates the virtual audio device "TRUSDX" (a null sink) if it doesn't exist, and connects the driver to it.
#   In WSJT-X: Input = "Monitor of TRUSDX" (TRUSDX.monitor), Output = "TRUSDX".
# Stop it: close this window, or press Ctrl+C twice (the first Ctrl+C restarts the driver)
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$HERE"
# Driver processes only: Python running trusdx-txrx.py (a plain "pkill -f trusdx-txrx.py" would also kill e.g. an
# editor or viewer that has the file open)
driver_pids() { pgrep -f 'trusdx-txrx[.]py' | while read -r p; do [[ "$(ps -o comm= -p "$p" 2>/dev/null)" == *[Pp]ython* ]] && echo "$p"; done; }
PY=python3; [[ -x .venv/bin/python ]] && PY=.venv/bin/python
$PY -c "import pyaudio, serial" 2>/dev/null || { echo "Run ./install.sh first (in $HERE)."; exit 1; }

PIDS=$(driver_pids)
if [[ -n "$PIDS" ]]; then
  echo "Stopping a driver copy that is already running (two copies on the radio's port garble CAT)..."
  kill $PIDS 2>/dev/null; sleep 2
fi

# Audio mode: PulseAudio/PipeWire if available (unless --alsa), otherwise the ALSA loopback set up by install.sh
ALSA=0; ARGS=()
for a in "$@"; do if [[ "$a" == "--alsa" ]]; then ALSA=1; else ARGS+=("$a"); fi; done
if [[ $ALSA == 0 ]] && ! { command -v pactl >/dev/null && pactl info >/dev/null 2>&1; }; then ALSA=1; fi
MOVER=""
if [[ $ALSA == 1 ]]; then
  grep -q "W5PL truSDX driver" "$HOME/.asoundrc" 2>/dev/null || { echo "ALSA loopback not set up: run ./install.sh --alsa first."; exit 1; }
  grep -q Loopback /proc/asound/cards 2>/dev/null || { echo "ALSA loopback card missing: sudo modprobe snd-aloop id=Loopback (or reboot)."; exit 1; }
  echo "Audio: ALSA loopback. In WSJT-X: Input trusdx_rx, Output trusdx_tx"
  ARGS+=(--rx-audio trusdx_drv_rx --tx-audio trusdx_drv_tx)
elif command -v pactl >/dev/null && pactl info >/dev/null 2>&1; then
  if ! pactl list short sinks | awk '{print $2}' | grep -qx TRUSDX; then
    pactl load-module module-null-sink sink_name=TRUSDX sink_properties=device.description=TRUSDX >/dev/null \
      && echo "Created virtual audio device TRUSDX"
  fi
  # PulseAudio (and pipewire-pulse) honour these for the driver's default audio device ...
  export PULSE_SINK=TRUSDX PULSE_SOURCE=TRUSDX.monitor
  # ... and on systems where ALSA talks to PipeWire directly, move the driver's streams to TRUSDX every few seconds
  # (also after a radio reconnect, which opens new streams). Same as doing it by hand in pavucontrol.
  # A stream belongs to the driver if it carries the driver's process id itself (PulseAudio) or its client does
  # (PipeWire's ALSA plugin puts application.process.id only on the client, e.g. Ubuntu 24.04 on a Raspberry Pi).
  streams_of() {  # $1 = pid, $2 = "Sink Input" or "Source Output"
    local clients; clients=$(pactl list clients 2>/dev/null | awk -v p="$1" '/^Client #/{c=substr($2,2)} /application.process.id = /{gsub(/"/,"",$3); if($3==p) print c}')
    pactl list "$([[ $2 == Sink* ]] && echo sink-inputs || echo source-outputs)" 2>/dev/null |
      awk -v p="$1" -v cl=" $(echo $clients) " -v h="$2" 'index($0,h" #")==1{id=substr($NF,2)} /^\tClient: /{if(index(cl," "$2" ")) print id} /application.process.id = /{gsub(/"/,"",$3); if($3==p) print id}' | sort -u
  }
  ( while sleep 3; do
      pid=$(driver_pids | head -1); [[ -z "$pid" ]] && continue
      streams_of "$pid" "Sink Input" | while read -r id; do pactl move-sink-input "$id" TRUSDX 2>/dev/null; done
      streams_of "$pid" "Source Output" | while read -r id; do pactl move-source-output "$id" TRUSDX.monitor 2>/dev/null; done
    done ) &
  MOVER=$!
  trap '[[ -n "$MOVER" ]] && kill $MOVER 2>/dev/null' EXIT
fi

$PY ../trusdx-txrx.py "${ARGS[@]}"
