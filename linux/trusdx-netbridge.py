#!/usr/bin/env python3
"""W5PL Driver for DL2MAN (tr)uSDX - network bridge (runs on the computer the radio is plugged into, e.g. a Raspberry Pi).

Shares the radio's USB serial port on the network, so the driver on a laptop anywhere in the house can use it:
    laptop:  trusdx-txrx.py --serial-url socket://PI-ADDRESS:4532
The radio's audio already travels inside its serial link (8-bit samples), so forwarding the bytes forwards the audio;
WSJT-X, VARA etc. run on the laptop exactly as with a local radio.

Safety: if the laptop disappears or its transmit audio stops for --stall seconds while the radio transmits (Wi-Fi drop,
laptop asleep, driver killed), the bridge un-keys the radio itself (200 ms quiet, ;RX;, 100 ms, ;UA2;) and ignores the
rest of that transmission until the driver sends its own ;RX;.

The serial port stays open while the bridge runs (opening it can restart the radio), with the same settings as the
driver: 115200 baud, 2 stop bits (even TX byte pacing), DTR/RTS as pyserial sets them (or --rts-low).
"""
import argparse, datetime, socket, threading, time, sys
import serial, serial.tools.list_ports

p = argparse.ArgumentParser(description=__doc__.split("\n\n")[0], formatter_class=argparse.ArgumentDefaultsHelpFormatter)
p.add_argument("--port", type=int, default=4532, help="TCP port to listen on")
p.add_argument("--bind", default="0.0.0.0", help="address to listen on (0.0.0.0 = all networks)")
p.add_argument("--device", default="", help="serial device (default: the first CH340 1a86:7523, i.e. the (tr)uSDX)")
p.add_argument("--stop-bits", type=int, choices=[1, 2], default=2, help="serial stop bits (match the driver's --stop-bits)")
p.add_argument("--rts-low", action="store_true", help="hold RTS low (DL2MAN CAT spec); default: pyserial default (both high)")
p.add_argument("--stall", type=float, default=1.5, help="un-key if TX audio from the laptop stops for this many seconds")
p.add_argument("-v", "--verbose", action="store_true", help="log every client connect/TX state change")
a = p.parse_args()

def log(msg): print(f"{datetime.datetime.now(datetime.timezone.utc):%Y-%m-%d %H:%M:%S} {msg}", flush=True)

lock = threading.Lock()
st = {"ser": None, "client": None, "tx": False, "last_in": 0.0, "mute": False, "tail": b"", "hold": b"", "gap_until": 0.0}

def find_device():
    if a.device: return a.device
    for port in serial.tools.list_ports.comports():
        if port.vid == 0x1A86 and port.pid == 0x7523: return port.device
    return None

def unkey(why):
    """Measured un-key sequence for firmware 2.00x. Caller holds lock."""
    ser = st["ser"]
    st["tx"] = False; st["hold"] = b""
    if ser is None: return
    try:
        time.sleep(0.2); ser.write(b";RX;"); ser.flush()
        time.sleep(0.1); ser.write(b";UA2;"); ser.flush()
        log(f"SAFETY: un-keyed the radio ({why})")
    except Exception as e:
        log(f"SAFETY: un-key failed ({e})")

def track(data):
    """Follow the TX state from the driver's commands. TX audio never contains ';' (the driver replaces it), so
    'TX0;' / 'RX;' only match real commands."""
    buf = st["tail"] + data
    i_tx = max(buf.rfind(b"TX0;"), buf.rfind(b"TX1;"), buf.rfind(b"TX2;"), buf.rfind(b"TX;"))
    i_rx = buf.rfind(b"RX;")
    if i_tx > i_rx and not st["tx"]:
        st["tx"] = True
        if a.verbose: log("radio keyed by the driver")
    elif i_rx > i_tx and st["tx"]:
        st["tx"] = False
        if a.verbose: log("radio un-keyed by the driver")
    st["tail"] = buf[-4:]

def serial_loop():
    """Keep the radio's port open; copy radio -> client."""
    while True:
        dev = find_device()
        if not dev:
            time.sleep(2); continue
        try:
            ser = serial.Serial(None, 115200, timeout=0.05, write_timeout=2,
                                stopbits=serial.STOPBITS_TWO if a.stop_bits == 2 else serial.STOPBITS_ONE, exclusive=True)
            ser.port = dev
            if a.rts_low: ser.dtr = True; ser.rts = False
            ser.open()
        except Exception as e:
            log(f"cannot open {dev}: {e}"); time.sleep(3); continue
        log(f"radio port {dev} open (115200, {a.stop_bits} stop bits{', RTS low' if a.rts_low else ''})")
        with lock: st["ser"] = ser
        try:
            while True:
                d = ser.read(4096)
                c = st["client"]
                if d and c:
                    try: c.sendall(d)
                    except OSError: drop_client("send failed")
        except Exception as e:
            log(f"radio port lost ({e})")
        with lock:
            st["ser"] = None; st["tx"] = False
        try: ser.close()
        except Exception: pass
        drop_client("radio port lost")   # the driver reconnects and re-initialises the radio
        time.sleep(2)

def drop_client(why):
    with lock:
        c = st["client"]; st["client"] = None
        if c is None: return
        if st["tx"]: unkey(f"laptop disconnected while transmitting: {why}")
    try: c.close()
    except OSError: pass
    log(f"laptop disconnected ({why})")

def client_loop(c, addr):
    while True:
        try: d = c.recv(65536)
        except socket.timeout: continue        # quiet laptop in RX is normal (the timeout is for sends)
        except OSError: d = b""
        if not d: break
        with lock:
            if st["client"] is not c: return   # replaced by a newer connection
            st["last_in"] = time.time()
            if st["mute"]:
                # after a safety un-key: ignore the rest of that transmission until the driver's own ;RX;
                k = (st["tail"] + d).find(b"RX;")
                if k < 0:
                    st["tail"] = (st["tail"] + d)[-4:]; continue
                d = (st["tail"] + d)[k:]; st["mute"] = False; st["tail"] = b""
                log("driver un-keyed too: forwarding again")
            was_tx = st["tx"]
            track(d)
            ser = st["ser"]
        if ser is None: continue
        try: forward(ser, d, was_tx)
        except Exception as e: log(f"write to radio failed ({e})")
    if st["client"] is c: drop_client("connection closed")

def forward(ser, d, was_tx):
    """Write to the radio with the measured key/un-key timing applied HERE, next to the radio, where it is exact
    (the laptop can't see when queued audio has left this port, and waiting there would make hamlib/xara wait):
      TX0;  -> 50 ms before the next bytes (the radio switches to TX before "US" + audio)
      ;RX;  -> only after all queued TX audio has left the port + 200 ms quiet; then 100 ms before the next bytes
    The driver sends ;RX; and ;UA2; back to back over the network and relies on this."""
    d = st["hold"] + d; st["hold"] = b""
    if was_tx and b"RX;" not in d:                # (a complete ;RX; also ends in ';': never hold that one back)
        for p in (b";RX", b";R", b";"):           # an ;RX; split across packets: wait for the rest
            if d.endswith(p): st["hold"] = p; d = d[:-len(p)]; break
    gap = st["gap_until"] - time.time()
    if gap > 0: time.sleep(gap)
    k = d.find(b"RX;") if was_tx else -1
    if k >= 0:
        j = k - 1 if k > 0 and d[k - 1:k] == b";" else k
        if j: ser.write(d[:j])
        t_drain = time.time()
        ser.flush()                                # tcdrain: the TX audio cushion has really been sent
        t_drain = time.time() - t_drain
        time.sleep(0.2)
        ser.write(d[j:k + 3]); ser.flush()
        if a.verbose: log(f"un-key: audio drained in {t_drain * 1000:.0f} ms, 200 ms quiet, then {d[j:k + 3]!r}")
        st["gap_until"] = time.time() + 0.1
        rest = d[k + 3:]
        if rest: time.sleep(0.1); ser.write(rest)
        return
    t = max(d.rfind(b"TX0;"), d.rfind(b"TX1;"), d.rfind(b"TX2;"))
    if t >= 0 and not was_tx:
        ser.write(d[:t + 4]); ser.flush()
        time.sleep(0.05)
        if d[t + 4:]: ser.write(d[t + 4:])
        return
    if d: ser.write(d)

def watchdog():
    while True:
        time.sleep(0.1)
        with lock:
            if st["tx"] and st["client"] is not None and time.time() - st["last_in"] > a.stall:
                unkey(f"no transmit audio from the laptop for {a.stall:.1f} s")
                st["mute"] = True; st["tail"] = b""

def on_stop(signum, frame):
    """Service stop/restart or Ctrl+C: never leave the radio keyed."""
    with lock:
        if st["tx"]: unkey("bridge stopping while transmitting")
    log("bridge stopped"); sys.exit(0)
import signal
signal.signal(signal.SIGTERM, on_stop); signal.signal(signal.SIGINT, on_stop)

threading.Thread(target=serial_loop, daemon=True).start()
threading.Thread(target=watchdog, daemon=True).start()
srv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
srv.bind((a.bind, a.port)); srv.listen(2)
log(f"W5PL (tr)uSDX network bridge listening on {a.bind}:{a.port} (laptop: trusdx-txrx.py --serial-url socket://{socket.gethostname()}.local:{a.port})")
while True:
    c, addr = srv.accept()
    c.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
    c.setsockopt(socket.SOL_SOCKET, socket.SO_KEEPALIVE, 1)
    c.settimeout(20)  # a laptop that stops reading RX audio for 20 s is gone (Wi-Fi stalls of seconds happen)
    if st["client"] is not None: drop_client(f"new connection from {addr[0]}")
    with lock:
        st["client"] = c; st["last_in"] = time.time(); st["mute"] = False; st["tail"] = b""; st["hold"] = b""
    log(f"laptop connected from {addr[0]}")
    threading.Thread(target=client_loop, args=(c, addr), daemon=True).start()
