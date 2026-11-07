#!/usr/bin/env python3
"""(tr)uSDX direct un-key timing test - talks straight to the radio, no driver, no WSJT-X.

!! SET THE RADIO'S POWER TO 0 W (or use a dummy load), CLOSE WSJT-X AND STOP THE DRIVER FIRST !!
!! Keep a hand on the power switch: if it reports STILL NOT BACK, switch the radio off.        !!

Each cycle: make sure the radio streams RX audio -> TX0; + US -> SECONDS of a 1500 Hz tone at RATE
samples/s (evenly paced) -> un-key (200 ms quiet, ;RX;, 100 ms, ;UA2;) -> time until RX audio is back.

Usage:  python3 unkey_test.py PORT [--cycles 5] [--seconds 13] [--rate 8000] [--amp 127]
  macOS PORT e.g. /dev/cu.usbserial-1110   Windows PORT e.g. COM5 (the CH340 port, not COM8/9)
Results on firmware 2.00x: 13 s at 8000 or 9600 S/s -> 6/6 back in ~0.3 s; 8 s at 11520 -> stuck keyed.
"""
import serial, threading, time, sys, math, argparse, statistics

ap = argparse.ArgumentParser()
ap.add_argument("port")
ap.add_argument("--cycles", type=int, default=5)
ap.add_argument("--seconds", type=float, default=13.0)
ap.add_argument("--rate", type=int, default=8000)
ap.add_argument("--amp", type=int, default=127, help="tone amplitude 0..127 (0 = silence)")
a = ap.parse_args()

ser = serial.Serial(a.port, 115200, timeout=0.05, write_timeout=2)
rx, lock, running = [], threading.Lock(), [True]

def reader():
    while running[0]:
        d = ser.read(4096)
        if d:
            with lock: rx.append((time.time(), d))
threading.Thread(target=reader, daemon=True).start()

def streaming_since(t):
    with lock: d = b"".join(x for ts, x in rx if ts >= t)
    return b"US" in d or sum(1 for b in d if 0x60 <= b <= 0xA0) > 200

def wait_stream(t0, timeout):
    while time.time() - t0 < timeout:
        if streaming_since(t0): return time.time() - t0
        time.sleep(0.01)
    return None

def w(b): ser.write(b); ser.flush()

def ensure_rx():
    if wait_stream(time.time(), 0.5) is not None: return True
    for _ in range(3):
        t = time.time(); w(b";RX;"); time.sleep(0.1); w(b";UA2;")
        if wait_stream(t, 1.5) is not None: return True
    return False

n = a.rate // 50   # 20 ms pieces
blk = bytes(max(0, min(255, int(128 + a.amp * math.sin(2 * math.pi * 1500 * i / a.rate)))) for i in range(n)).replace(b";", b":")

print(f"initial RX streaming: {ensure_rx()}", flush=True)
res = []
for i in range(a.cycles):
    if not ensure_rx(): print("no RX streaming before TX - abort"); break
    w(b"TX0;"); time.sleep(0.05); w(b"US")
    end, nxt = time.time() + a.seconds, time.time()
    while time.time() < end:
        w(blk); nxt += 0.02; time.sleep(max(0, nxt - time.time()))
    t0 = time.time(); time.sleep(0.2); w(b";RX;"); time.sleep(0.1); w(b";UA2;")
    dt = wait_stream(t0, 5.0)
    if dt is None:
        t1 = time.time(); w(b";RX;"); time.sleep(0.1); w(b";UA2;")
        dt2 = wait_stream(t1, 3.0)
        print(f"#{i+1}: NOT back in 5 s; recovery -> {'back after %.2fs' % dt2 if dt2 else 'STILL NOT BACK - POWER THE RADIO OFF'}", flush=True)
        res.append(None)
        if dt2 is None: break
    else:
        res.append(dt); print(f"#{i+1}: RX streaming back {dt:.3f} s after un-key", flush=True)
    time.sleep(1.0)
ok = [x for x in res if x is not None]
print(f"\n{a.seconds:.0f} s TX at {a.rate} S/s: {len(ok)}/{len(res)} ok" + (f", median {statistics.median(ok):.3f} s, max {max(ok):.3f} s" if ok else ""))
running[0] = False
