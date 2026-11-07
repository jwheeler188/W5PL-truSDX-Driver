#!/usr/bin/env bash
# W5PL Driver for DL2MAN (tr)uSDX - start the driver (Linux, PulseAudio or PipeWire). Run install.sh once first.
#   ./trusdx.sh                  normal (CAT port /tmp/trusdx)
#   ./trusdx.sh --cat-tcp 4542   CAT over the network: WSJT-X Serial Port 127.0.0.1:4542
#   ./trusdx.sh -v               verbose log of every CAT command
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

MOVER=""
if command -v pactl >/dev/null && pactl info >/dev/null 2>&1; then
  if ! pactl list short sinks | awk '{print $2}' | grep -qx TRUSDX; then
    pactl load-module module-null-sink sink_name=TRUSDX sink_properties=device.description=TRUSDX >/dev/null \
      && echo "Created virtual audio device TRUSDX"
  fi
  # PulseAudio (and pipewire-pulse) honour these for the driver's default audio device ...
  export PULSE_SINK=TRUSDX PULSE_SOURCE=TRUSDX.monitor
  # ... and on systems where ALSA talks to PipeWire directly, move the driver's streams to TRUSDX every few seconds
  # (also after a radio reconnect, which opens new streams). Same as doing it by hand in pavucontrol.
  ( while sleep 3; do
      pid=$(driver_pids | head -1); [[ -z "$pid" ]] && continue
      pactl list sink-inputs 2>/dev/null | awk -v p="$pid" '/^Sink Input #/{id=substr($3,2)} /application.process.id = /{gsub(/"/,"",$3); if($3==p) print id}' |
        while read -r id; do pactl move-sink-input "$id" TRUSDX 2>/dev/null; done
      pactl list source-outputs 2>/dev/null | awk -v p="$pid" '/^Source Output #/{id=substr($3,2)} /application.process.id = /{gsub(/"/,"",$3); if($3==p) print id}' |
        while read -r id; do pactl move-source-output "$id" TRUSDX.monitor 2>/dev/null; done
    done ) &
  MOVER=$!
  trap '[[ -n "$MOVER" ]] && kill $MOVER 2>/dev/null' EXIT
else
  echo "NOTE: pactl/PulseAudio/PipeWire not available - the driver uses the default audio device."
  echo "      Route it yourself (e.g. snd-aloop), see the manual."
fi

$PY ../trusdx-txrx.py "$@"
