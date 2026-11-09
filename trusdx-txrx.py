#!/usr/bin/env python3
# de SQ3SWF, PE1NNZ 2023
# W5PL Driver for DL2MAN (tr)uSDX: modified by W5PL, 2026. W5PL's changes: GPL-3.0-or-later, see LICENSE and NOTICE.md.
# The original trusdx-audio (above) states no license; its authors keep their rights to their code.

# Linux:
# sudo apt install portaudio19-dev
# stty -F /dev/ttyUSB0 raw -echo -echoe -echoctl -echoke -hupcl 115200;
# pactl load-module module-null-sink sink_name=TRUSDX sink_properties=device.description="TRUSDX"
# pavucontrol
###

# Windows 7:
# Install python3.6 (32 bits version)
# python -m pip install --upgrade pip
# python -m pip install pyaudio   # or download and install the matching version from: https://www.lfd.uci.edu/~gohlke/pythonlibs/#pyaudio
# python -m pip install pyaudio
# Install, extract VB-Audio Virtual Audio Cable from https://download.vb-audio.com/
# Install VB-Audio by clicking right on x64 executable and select Run as Administrator, click install driver
# Download and extract com0com from https://sourceforge.net/projects/com0com/
# setup.exe /S /D=C:\Program Files\com0com
# Install x64 executable. In case of driver-signing issues: every-time reboot Windows by holding F8 (Win7) or Shift (Win8/10), select "Disable Driver Signature Enforcement" in Advanced Boot options
# Select Start > com0com > Setup Command Prompt, and enter: uninstall > enter: install PortName=COM8 PortName=COM9
# or open Command Prompt > cd C:\Program Files (x86)\com0com > setupc install PortName=COM8 PortName=COM9
# Select CABLE audio devices and COM8 in WSJT-X or any other HAM radio program

# Build: sudo apt install patchelf && python -m pip install -U nuitka
# python -m nuitka --standalone trusdx-txrx.py

# Setup_com0com_v3.0.0.0_W7_x64_signed.exe  /S /D=C:\Program Files\com0com
# cd "c:\Program Files\com0com"
# setupc.exe install PortName=COM8 PortName=COM9
# (as admin) VBCABLE_Setup_x64.exe

###
# socat -d -d pty,link=/tmp/ttyS0,echo=0,ignoreeof,b115200,raw,perm=0777 pty,link=/tmp/ttyS1,echo=0,ignoreeof,b115200,raw,perm=0777 &
# sudo modprobe snd-aloop

import pyaudio
import serial
import serial.tools.list_ports
import threading
import time
import socket
import os
import datetime
import array
import argparse
import sys
from sys import platform

DRIVER_NAME = "W5PL Driver for DL2MAN (tr)uSDX"   # based on trusdx-audio by SQ3SWF / PE1NNZ
DRIVER_VERSION = "beta-2026-11-08-3 (clean TX audio: even pacing, 10473 S/s with 2 stop bits)"
audio_tx_rate_trusdx = 4800
audio_tx_rate = 10473  # fix: was 11520 (100% of the 115200 baud link: trx misses bytes -> rough audio, stuck/crashed TX).
# The trx plays each TX byte the moment it arrives (DL2MAN: "11520 Hz, or lower if samples are sent continuously at
# equal intervals rather than in blocks"), so a lower rate sent in blocks (beta 8000 S/s in 20 ms pieces) is played too
# fast with gaps = garbled on air (heard 2026-11-08). With 2 stop bits the link itself paces the bytes evenly at
# 115200/11 = 10473 B/s and the trx gets ~9% spare time per byte. Tested on air 2026-11-08: cleaner than 11520, un-key 0.1 s.
audio_rx_rate = 7812
buf = []    # buffer for received audio
# fix: RX audio was played as unsigned 8-bit (silence = 128). Whenever the stream ran dry (TX, an underrun, a
# reconnect or a disconnected radio) the audio layer filled the gap with zero bytes = FULL-SCALE NEGATIVE DC, so
# the WSJT-X input showed 100% / clicks. Played as signed 8-bit instead (silence = 0): flip the sign bit.
U8_TO_S8 = bytes((i ^ 0x80) for i in range(256))
urs = [0]   # underrun counter
STATS = {'raw': 0, 'audio': 0, 'played': 0, 'urs': 0, 'ts': 0.0}  # -v: RX audio statistics, logged every 5 s
unkey_ts = [0.0]  # time of last un-key safety repeat
ua_ts = [0.0]     # last time the streaming watchdog re-sent UA
ua_gap = [1.0]    # watchdog interval: doubles (to 8 s) while the trx stays silent, so a rebooting trx gets quiet time
trx_down_logged = [False]  # 'trx not responding' logged for the current outage
audio_streak_ts = [0.0]    # start of the current unbroken run of RX audio (a rebooting trx sends only short bursts)
rx_any_ts = [0.0]          # last time ANY byte came from the trx (audio, CAT reply or boot burst)
ua_tries = [0]             # watchdog UA attempts in the current outage
outage = [False]           # trx stopped streaming in RX and has not streamed steadily since
outage_times = []          # start times of recent outages (boot-loop detection)
pause_until = [0.0]        # boot-loop breaker: no traffic to the trx until this time
t_unkey = [0.0]   # time the last un-key sequence finished
second_unkey_at = [0]  # when to send the 2nd RX+UA after an un-key (0 = none pending)
start_ts = [time.time()]  # driver start, the watchdog waits a few seconds after startup
RUN_GEN = [0]      # incremented on every run()/reconnect; threads from an older run exit
tx_broken = [False]  # set when the trx answers E; during TX (left audio mode): stop sending TX audio
reply_cache = {}  # last trx reply per CAT command (b'IF' -> b'IF...;'), answers hamlib polls during TX
rx_seen_ts = [0.0]  # last time RX audio stream data arrived from the trx (it sends none while transmitting)
status = [False, False, True, False, False]	# tx_state, cat_streaming_state, running, cat_active, keyed_by_rts_dtr
RAWLOG = [None, 0]  # debug: --rawlog FILE (or TRUSDX_RAWLOG=FILE) records raw trx reads

def log(msg):
    if config['verbose']: print(f"{datetime.datetime.utcnow()} {msg}")

def show_audio_devices():
    for i in range(pyaudio.PyAudio().get_device_count()):
        print(pyaudio.PyAudio().get_device_info_by_index(i))
    for i in range(pyaudio.PyAudio().get_host_api_count()):
        print(pyaudio.PyAudio().get_host_api_info_by_index(i))
        
def find_audio_device(name, occurance = 0):
    # Linux: the default device unless a name is given (--rx-audio/--tx-audio, e.g. the ALSA loopback set up by
    # linux/install.sh); macOS/Windows: BlackHole / VB-CABLE by name as before.
    if (platform == "linux" or platform == "linux2") and not name: return -1
    result = [i for i in range(pyaudio.PyAudio().get_device_count()) if name in (pyaudio.PyAudio().get_device_info_by_index(i)['name']) ]
    return result[occurance] if len(result) else -1 # return n-th matching device to name, -1 for no match

def show_serial_devices():
    for port in serial.tools.list_ports.comports():
        print(port)

def find_serial_device(name, occurance = 0):
    ports = serial.tools.list_ports.comports()
    result = [port.device for port in ports if name in port.description]
    if not result and name in ("USB Serial", "CH340"):
        # fix: some CH340s describe themselves differently (Linux: "USB2.0-Serial"); match WCH's USB vendor ID instead
        result = [port.device for port in ports if port.vid == 0x1A86]
    return result[occurance] if len(result) else "" # return n-th matching device to name, "" for no match

def cat_write(cat, data):
    """Write to the CAT app's virtual port. If the app has closed its end (Windows VSPE: COM8 closed), a blocking
    write would time out and kill the driver; a reply nobody is waiting for can safely be dropped."""
    try:
        cat.write(data)
        cat.flush()
    except serial.SerialTimeoutException:
        log(f"CAT app not reading - dropped {data!r}")

def mark_audio():
    now = time.time()
    if now - rx_seen_ts[0] > 0.3: audio_streak_ts[0] = now   # audio (re)started after a gap
    rx_seen_ts[0] = now

def handle_rx_audio(ser, cat, pastream, d):
    if status[1]:
        mark_audio()
        #log(f"stream: {d}")
        if not status[0]: buf.append(d); STATS['audio'] += len(d)   # in CAT streaming mode: fwd to audio buf
        #if not status[0]: pastream.write(d)  #  in CAT streaming mode: directly fwd to audio
        if d[-1] == ord(';'):
            status[1] = False           # go to CAT cmd mode when data ends with ';'
            #log("***CAT mode")
    else:
        if d.startswith(b'US'):
            #log("***US mode")
            status[1] = True            # go to CAT stream mode when data starts with US
            mark_audio()
            # fix: a short stream segment can arrive whole ("US<audio>;"); its ';' already ends the stream.
            # Without this the next CAT reply was swallowed as audio, so hamlib timed out and retried.
            if len(d) > 2:
                if not status[0]: buf.append(d[2:]); STATS['audio'] += len(d) - 2
                if d[-1] == ord(';'): status[1] = False
        elif not (len(d) >= 2 and (65 <= d[0] <= 90 or d[0] == ord('?'))):
            # fix: after TX->RX the trx resumes streaming audio without a "US" header. CAT replies always
            # start with A-Z or '?'; anything else is audio, so don't forward it to the CAT app (it caused
            # hamlib "Protocol error") - treat it as stream data instead.
            status[1] = True
            mark_audio()
            if not status[0]: buf.append(d); STATS['audio'] += len(d)
            if d[-1] == ord(';'): status[1] = False
        elif d == b'E;' and (status[0] or time.time() - unkey_ts[0] < 2.0):
            # trx error replies to TX audio bytes; never forward them to hamlib (it reports IO error).
            # During TX it means the trx left audio mode: stop feeding it audio so the RX; gets through.
            if status[0] and not tx_broken[0]:
                tx_broken[0] = True
                print(f"{datetime.datetime.utcnow()} WARNING: (tr)uSDX left TX audio mode - TX audio paused until RX")
        elif d.startswith(b'UA') and d[-1:] == b';' and len(d) <= 4:
            log(f"Dropped {d} (trx echo of the driver's own UA command)")   # not a reply to hamlib
        elif d == b'?;' and (time.time() - unkey_ts[0] < 2.0 or time.time() - ua_ts[0] < 0.5):
            log("Dropped '?;' caused by un-key safety repeat")
        else:
            if (len(d) > 3 and 65 <= d[0] <= 90 and 65 <= d[1] <= 90 and not status[0]
                    and all(48 <= c <= 90 or c in b' +-;' for c in d) and d.count(b';') == 1):   # well-formed only
                reply_cache[d[:2]] = d  # remember last reply per command, used to answer polls during TX
            if status[3]:               # only send something to cat port, when active
                cat_write(cat, d)
                log(f"O: {d}")  # in CAT command mode
            else:
                log("Skip CAT response, as CAT is not active.")

def receive_serial_audio(ser, cat, pastream, gen=None):
    try:
        log("receive_serial_audio")
        bbuf = b''  # rest after ';' that cannot be handled
        while alive(gen):
            if False and status[0]:  # WORKAROUND: special case for TX; this is a workaround to handle CAT responses properly during TX
                if(ser.in_waiting < 1): time.sleep(0.001)
                else:
                    d = ser.read()
                    #log(f"Q: {d}")  # in TX CAT command mode
                    #cat.write(d)
                    #cat.flush()
                    handle_rx_audio(ser, cat, pastream, d)
            # below implements: d = ser.read_until(b';', 32)  #read until CAT end or enough in buf but only up to 32 bytes to keep response
            #elif(ser.in_waiting < config['tx_block_size']): time.sleep(0.001)   #normal case for RX
            elif(ser.in_waiting == 0 and b';' not in bbuf): time.sleep(0.001)   #normal case for RX (but first drain complete CAT replies left in bbuf)
            else:
                #d = bbuf + ser.read(config['tx_block_size'])
                raw = ser.read(ser.in_waiting)
                if raw: rx_any_ts[0] = time.time()
                STATS['raw'] += len(raw)
                if config['verbose'] and time.time() - STATS['ts'] >= 5:
                    dt = time.time() - STATS['ts'] if STATS['ts'] else 0
                    if dt: log(f"RX stats {dt:.1f}s: from trx {STATS['raw']/dt:.0f} B/s, audio {STATS['audio']/dt:.0f} S/s, played {STATS['played']/dt:.0f} S/s (nominal {audio_rx_rate}), underruns {urs[0]-STATS['urs']}, buffered {len(buf)} chunks, streaming={int(status[1])}")
                    STATS.update(raw=0, audio=0, played=0, urs=urs[0], ts=time.time())
                if RAWLOG[0] and RAWLOG[1] < 20000 and (b';' in raw or b';' in bbuf or not status[1]):   # debug: record raw trx reads that may hold CAT replies
                    RAWLOG[1] += 1
                    RAWLOG[0].write(f"{datetime.datetime.utcnow().strftime('%H:%M:%S.%f')} st={int(status[1])} bb={bbuf!r} raw={raw!r}\n"); RAWLOG[0].flush()
                d = bbuf + raw
                x = d.split(b';', maxsplit=1)
                cat_delim = (len(x) == 2)
                bbuf = x[1] if cat_delim else b''
                if not cat_delim and len(x[0]) < config['tx_block_size']:
                    bbuf = x[0]
                    continue
                d = x[0] + b';' if cat_delim else x[0]
                handle_rx_audio(ser, cat, pastream, d)
    except Exception as e:
        log(e)
        if gen is None or gen == RUN_GEN[0]: status[2] = False   # a stale thread must not stop the next run
        if config['verbose'] and (gen is None or gen == RUN_GEN[0]): raise

def alive(gen):
    """True while the run() that started this thread is still the current one (see RUN_GEN)."""
    return status[2] and gen == RUN_GEN[0]

def play_receive_audio(pastream, gen=None):
    try:
        log("play_receive_audio")
        while alive(gen):
            if len(buf) < 2:
                #log(f"UNDERRUN #{urs[0]} - refilling")
                urs[0] += 1
                # fix: this wait never checked for shutdown, so after a radio reconnect the OLD playback thread
                # survived and both old and new threads wrote RX audio to BlackHole (input pegged at 100%).
                while len(buf) < 10 and alive(gen):
                    time.sleep(0.001)
                continue
            # fix: after a network stall (--serial-url on weak Wi-Fi) RX audio arrives in a burst; the elastic buffer
            # below catches up only ~2%, leaving RX audio late for a minute (FT8 DT off). Drop the backlog instead.
            if len(buf) > 80:
                del buf[:len(buf) - 20]
                log("I: RX audio backlog dropped (arrived late in a burst)")
            d = buf.pop(0)
            # fix: the trx's sample clock runs ~0.15% slower than the nominal 7812 S/s the audio device plays, so
            # the buffer slowly drained and a ~50 ms gap (underrun + refill) came every ~30 s. Elastic buffer:
            # repeat one sample when the buffer runs low, drop one when it grows (inaudible at this rate).
            n = len(buf)
            if n < 6 and len(d) > 1: d = d + d[-1:]
            elif n > 30 and len(d) > 2: d = d[:-1]
            if not status[0]: pastream.write(d.translate(U8_TO_S8))
            STATS['played'] += len(d)
    except Exception as e:
        log(e)
        if gen is None or gen == RUN_GEN[0]: status[2] = False   # a stale thread must not stop the next run
        if config['verbose'] and (gen is None or gen == RUN_GEN[0]): raise

def tx_cat_delay(ser):
    #ser.reset_output_buffer() # because trusdx TX buffers can be full, empty host buffers (but reset_output_buffer does not seem to work)
    ser.flush()  # because trusdx TX buffers can be full, wait until all buffers are empty
    #time.sleep(0.003 + config['block_size']/audio_tx_rate) # time.sleep(0.01) and wait a bit before interrupting TX stream for a CAT cmd
    #time.sleep(0.0005 + 32/audio_tx_rate_trusdx) # and wait until trusdx buffers are read
    time.sleep(0.010) # and wait a bit before interrupting TX stream for a CAT cmd

def ua_cmd():
    return b"UA2;" if not config['unmute'] else b"UA1;"

def start_tx(ser, pastream, why):
    """Key the trx for CAT-streamed TX audio. Shared by CAT, RTS/DTR and VOX PTT."""
    wait = 3.0 if config['serial_url'] else 1.0      # over the network RX audio can pause for a second on Wi-Fi
    if time.time() - rx_seen_ts[0] > wait:
        # trx not streaming: TX0 would key it without TX audio mode (E; flood, stuck). Re-enable first.
        ser.write(ua_cmd())
        ser.flush()
        ua_ts[0] = t0 = time.time()
        while time.time() - t0 < wait and rx_seen_ts[0] < t0: time.sleep(0.02)
        log(f"I: UA before TX (trx was not streaming) -> streaming {'back' if rx_seen_ts[0] >= t0 else 'NOT back'}")
        if rx_seen_ts[0] < t0:
            # SAFETY: keying a trx that isn't in CAT streaming mode puts it in TX without audio mode; it then floods
            # E; and can stay keyed (seen 2026-11-08 after a settings reset). Don't key it at all.
            print(f"{datetime.datetime.utcnow()} WARNING: not keying the (tr)uSDX: it is not streaming audio (TX refused, {why})")
            return
    ser.write(b"TX0;")   # only TX0 takes TX audio over the CAT stream (plain TX; makes the trx flood "E;")
    ser.flush()
    # give the trx a moment to switch to TX, then announce the audio stream with "US" (per the (tr)uSDX
    # CAT docs audio follows US). Audio sent straight after TX0 was parsed as commands -> E;
    if not config['serial_url']: time.sleep(0.05)   # over the network the bridge waits the 50 ms next to the radio
    ser.write(b"US")
    ser.flush()
    # fix: ~40 ms of silence first (no flush: it must stay queued), so jitter in the audio input never leaves a gap on
    # the link (the trx would hear one as a click). The link drains as fast as audio arrives, so the backlog stays.
    # Over the network the cushion is larger (--net-buffer, default 200 ms) so Wi-Fi delays never leave a gap.
    ser.write(bytes([0x80]) * (audio_tx_rate * tx_prefill_ms() // 1000))
    status[0] = True
    tx_broken[0] = False
    log(f"I: TX0; + US ({why})")
    if pastream:
        pastream.stop_stream()
        pastream.start_stream()

def tx_prefill_ms():
    """Silence queued ahead of the TX audio: 40 ms on USB, --net-buffer (200 ms) over the network."""
    return config['net_buffer'] if config['serial_url'] else 40

def stop_tx(ser, pastream, why):
    """Un-key. Measured on firmware 2.00x: stop the TX audio, 200 ms quiet, ;RX;, 100 ms, ;UA2;
    -> back in RX with streaming in ~0.1-0.3 s every time. Sending ;RX; right behind the audio stream
    was often ignored and left the trx stuck in TX. Shared by CAT, RTS/DTR and VOX PTT."""
    was_tx = status[0]
    status[0] = False                    # no more TX audio from the loop
    ser.flush()                          # wait until queued TX audio has left the port
    unkey_ts[0] = time.time()            # drop stray ?;/E; and answer polls from cache meanwhile
    # over the network the bridge on the Pi applies this timing next to the radio (it can see when the queued audio
    # has left the port); waiting here too would only make hamlib/xara wait (xara exits if PTT takes over 1 s)
    net = bool(config['serial_url'])
    if was_tx and not net: time.sleep(0.2)
    ser.write(b";RX;")
    ser.flush()
    if not net: time.sleep(0.1)
    ser.write(b";" + ua_cmd())           # trx drops RX streaming after TX: re-enable it
    ser.flush()
    unkey_ts[0] = t_unkey[0] = time.time()
    second_unkey_at[0] = time.time() + 1.5   # fallback only, fires if no RX audio came back
    log(f"I: {('timing by the bridge, ' if net else '200 ms quiet, ') if was_tx else ''};RX; + ;UA; ({why})")
    if pastream:
        pastream.stop_stream()
        pastream.start_stream()

def handle_vox(samples8, ser, pastream=None):
    if (128 - min(samples8)) == 64 and (max(samples8) - 127) == 64: # if does contain very loud signal
        if not status[0]:
            start_tx(ser, None, "VOX")   # don't restart the stream: the audio that triggered VOX is in it
    elif status[0]:  # in TX and no audio detected (silence)
        stop_tx(ser, None, "VOX")

def handle_rts_dtr(ser, cat, pastream=None):
    if not status[4] and (cat.cts or cat.dsr):
        status[4] = True    # keyed by RTS/DTR
        start_tx(ser, pastream, "RTS/DTR")
    elif status[4] and not (cat.cts or cat.dsr):  #if keyed by RTS/DTR
        status[4] = False
        stop_tx(ser, pastream, "RTS/DTR")

def silence_limit():
    """Seconds without RX audio before the trx counts as not responding. Over USB a gap means a crash/reboot; over
    the network (--serial-url) Wi-Fi stalls of 1-2 s are normal (measured: 15% loss, 0.6 s spikes), so wait longer."""
    return 4.0 if config['serial_url'] else 1.5

def trx_silent(now=None):
    """In RX the trx streams audio continuously; if none has arrived for 1.5 s it is not responding (rebooting
    after a crash, e.g. when its buttons/knobs are used while streaming, or busy). Not during TX or right after it."""
    now = now or time.time()
    if status[0] or now - unkey_ts[0] <= 2.0 or now - start_ts[0] <= 5.0: return False
    if now - rx_seen_ts[0] > silence_limit(): return True
    return outage[0] and now - audio_streak_ts[0] < 1.0   # boot bursts don't count as 'back'

def handle_cat(pastream, ser, cat):
    if(cat.inWaiting()):
        if not status[3]:
            status[3] = True
            log("CAT interface active")
        d = cat.read_until(b";")
        if True and d.startswith(b'ID'):   # this is a workaround for unrealistic fast RTT expectations in hamlib for sequence RX;ID;
            cat_write(cat, b'ID020;')
            log(f"I: {d}")
            log(f"O: ID020; (emu)")
            return
        if d.startswith(b"RX"):
            # SAFETY: an un-key always goes to the trx, whatever the driver believes. A trx stuck in TX sends no RX
            # audio, so it looks exactly like a crashed one; beta 2026-11-08 then held RX; back (stuck keyed).
            log(f"I: {d}")
            stop_tx(ser, pastream, "CAT")
            return
        if (d == b'IF;' and not status[0] and not config['forward_if'] and b'IF' in reply_cache
                and b'FA' in reply_cache and b'MD' in reply_cache):
            # fix: the trx crashed (reset in the middle of sending its IF reply) when its mode/filter was changed on
            # the front panel while CAT audio was streaming and hamlib was polling (2.00x, 2026-11-07; streaming
            # alone, or polling with the buttons left alone, was fine). Hamlib polls IF, FA and MD every second; build
            # the IF reply here from the trx's last real IF, FA (frequency) and MD (mode) replies, so the trx never
            # has to send its long IF reply. Frequency and mode stay current through hamlib's own FA/MD polls.
            r = bytearray(reply_cache[b'IF'])
            fa = reply_cache[b'FA']; md = reply_cache[b'MD']
            if len(r) == 38 and len(fa) == 14 and len(md) == 4:
                r[2:13] = fa[2:13]; r[29:30] = md[2:3]; r[28:29] = b'0'   # frequency, mode, P8: 0 = receiving
                cat_write(cat, bytes(r))
                log(f"I: {d} answered by the driver from FA/MD: {bytes(r)}")
                return
        if time.time() < pause_until[0] and not status[0]:
            # boot-loop breaker active: keep the line completely quiet; answer what we can from the last replies
            key = d[:-1]
            if len(d) == 3 and key in reply_cache:
                cat_write(cat, reply_cache[key]); log(f"I: {d} answered from cache (trx paused after repeated crashes)")
            elif d.startswith(b"TX"):
                print(f"{datetime.datetime.utcnow()} WARNING: not keying the (tr)uSDX: it is paused after repeated crashes")
            else:
                log(f"I: {d} not sent (trx paused after repeated crashes)")
            return
        if trx_silent() and len(d) == 3 and d[:-1] in reply_cache:
            # fix: when the trx crashed and is rebooting (seen when using its buttons/knobs while streaming), hamlib
            # kept polling and re-opening the rig, plus RX;/UA, and the trx crashed again during boot (boot loop until
            # WSJT-X gave up). While it is silent, answer polls from the last replies and keep the line quiet.
            if not trx_down_logged[0]:
                trx_down_logged[0] = True
                print(f"{datetime.datetime.utcnow()} WARNING: (tr)uSDX not responding (no RX audio) - answering CAT from cache until it is back")
            r = reply_cache[d[:-1]]
            if d[:-1] == b'IF' and len(r) >= 30: r = r[:28] + b'0' + r[29:]   # IF P8: 0 = receiving
            cat_write(cat, r)
            log(f"I: {d} answered from cache (trx not responding): {r}")
            return
        if not status[0] and time.time() - unkey_ts[0] < 1.0 and len(d) == 3 and d[:-1] in reply_cache:
            # fix: right after RX the trx is busy for ~1-2 s and does not answer; hamlib's PTT check (IF;)
            # then timed out ("Communication timed out while getting PTT state"). Answer from cache instead.
            r = reply_cache[d[:-1]]
            if d[:-1] == b'IF' and len(r) >= 30: r = r[:28] + b'0' + r[29:]   # IF P8: 0 = receiving
            cat_write(cat, r)
            log(f"I: {d} answered from cache while trx settles after RX: {r}")
            return
        if status[0] and not d.startswith(b"RX"):
            # fix: per the (tr)uSDX CAT docs, a ';' interrupts the TX audio stream and audio only resumes
            # after ";US". The original code never sent US, so after hamlib's first poll during TX the
            # audio bytes were parsed as commands ("E;" flood) and the trx then ignored RX; (stuck keyed).
            if d.startswith(b"TX"):
                log(f"I: {d} ignored (already transmitting)")
                return
            key = d[:-1]
            if len(d) == 3 and key in reply_cache:
                # status query while transmitting: answer from the last reply, keep the TX stream intact
                r = reply_cache[key]
                if key == b'IF' and len(r) >= 30: r = r[:28] + b'1' + r[29:]   # IF P8: 1 = transmitting
                cat_write(cat, r)
                log(f"I: {d} answered from cache during TX: {r}")
                return
            if len(d) == 3:
                # fix: hamlib re-opening the rig during TX sent KS; which broke the TX audio stream ("left TX audio
                # mode"). A query the driver can't answer gets ?; (what the trx answers to unknown queries anyway).
                cat_write(cat, b"?;")
                log(f"I: {d} answered ?; during TX (keeps the TX audio stream intact)")
                return
            tx_cat_delay(ser)
            ser.write(b";" + d + b"US")   # interrupt stream, send command, resume TX audio
            ser.flush()
            log(f"I: {d} sent during TX (stream interrupted and resumed with US)")
            return
        if d.startswith(b"RX"):
            log(f"I: {d}")
            stop_tx(ser, pastream, "CAT")
            return
        if d.startswith(b"TX"):
            # hamlib sends plain "TX;" (or TX1;); start_tx always uses TX0 (TX audio over CAT stream)
            log(f"I: {d}")
            start_tx(ser, pastream, "CAT" if d == b"TX0;" else f"CAT {d} -> TX0")
            return
        log(f"I: {d}")
        ser.write(d)                # fwd data on CAT port to trx
        ser.flush()

def transmit_audio_via_serial(pastream, ser, cat, gen=None):
    try:
        log("transmit_audio_via_serial_cat")
        while alive(gen):
            handle_cat(pastream, ser, cat)
            if(platform == "win32" and not config['no_rtsdtr'] and not config['cat_tcp']): handle_rts_dtr(ser, cat, pastream)
            # fix: streaming watchdog. The trx falls out of CAT streaming (after TX, or when a UA command is
            # ignored while it is busy). Without streaming it misses CAT commands and a TX0 does not enter TX
            # audio mode (E; flood, stuck keyed). In RX, if no RX audio arrived for 1.5 s, re-send UA.
            now = time.time()
            if second_unkey_at[0] and now >= second_unkey_at[0]:
                # fix: after TX the trx stays unresponsive and silent (no RX stream) until it gets a 2nd
                # RX + UA once it has left TX; hamlib then timed out and re-opened the rig. Do it ourselves.
                second_unkey_at[0] = 0
                if not status[0] and rx_seen_ts[0] < t_unkey[0]:   # only if RX audio did not come back
                    ser.write(b";RX;")
                    ser.flush()
                    time.sleep(0.1)
                    ser.write(b";" + ua_cmd())
                    ser.flush()
                    unkey_ts[0] = time.time()   # extends cache answers / stray-reply filter while it settles
                    log("I: ;RX; + UA (2nd un-key sequence)")
            # fix: a trx that crashed (front-panel input while streaming) reboots in ~4 s; a UA during its startup
            # crashed it again (boot loop every ~6 s, seen 2026-11-07). After the first try, only re-send UA once the
            # trx has been completely quiet for 5 s, i.e. has finished booting.
            if trx_silent(now) and not outage[0]:
                outage_times[:] = [t for t in outage_times if now - t < 60] + [now]
                if len(outage_times) >= 3 and now >= pause_until[0]:
                    # fix: 2.00x crashes when CAT commands arrive while it streams and its mode/filter is changed, and
                    # reliably in CW mode; saved in CW it crashed again on every boot. Stop all traffic so it can settle.
                    pause_until[0] = now + 60; outage_times.clear()
                    print(f"{datetime.datetime.utcnow()} WARNING: the (tr)uSDX crashed 3 times in a minute. Pausing all CAT traffic to it for 60 s.\n"
                          "    Firmware 2.00x can crash when its controls are used while CAT audio streams, and loops if left in CW.\n"
                          "    Switch the radio off and on, check it is in USB and its settings (TX Drive, CQ Interval 0); the driver retries in 60 s.")
            if now < pause_until[0]:
                ua_tries[0] = 0; ua_gap[0] = 1.0; outage[0] = True   # one fresh attempt when the pause ends
            elif trx_silent(now) and now - ua_ts[0] > ua_gap[0] and (ua_tries[0] == 0 or now - rx_any_ts[0] > 5.0):
                ua_tries[0] += 1; outage[0] = True
                ua_ts[0] = now
                ser.write(ua_cmd())
                ser.flush()
                log(f"I: UA2; (streaming watchdog: no RX audio for {now - rx_seen_ts[0]:.1f} s, next try in {min(ua_gap[0] * 2, 8.0):.0f} s)")
                ua_gap[0] = min(ua_gap[0] * 2, 8.0)   # back off: a rebooting trx needs quiet time
            elif outage[0] and not trx_silent(now):
                if trx_down_logged[0]: print(f"{datetime.datetime.utcnow()} (tr)uSDX responding again")
                ua_gap[0] = 1.0; trx_down_logged[0] = False; ua_tries[0] = 0; outage[0] = False
            if (status[0] or config['vox']) and pastream.get_read_available() > 0:    # in TX mode, and audio available
                samples = pastream.read(audio_tx_rate // 50, exception_on_overflow = False)   # fix: 20 ms pieces, evenly spaced (was 512-sample bursts)
                arr = array.array('h', samples)
                samples8 = bytearray([128 + x//256 for x in arr])  # was //512 because with //256 there is 5dB too much signal. Win7 only support 16 bits input audio -> convert to 8 bits
                samples8 = samples8.replace(b'\x3b', b'\x3a')      # filter ; of stream
                if status[0] and not tx_broken[0]: ser.write(samples8)
                if config['vox']: handle_vox(samples8, ser)
            else:
                time.sleep(0.001)
    except Exception as e:
        log(e)
        if gen is None or gen == RUN_GEN[0]: status[2] = False   # a stale thread must not stop the next run
        if config['verbose'] and (gen is None or gen == RUN_GEN[0]): raise

class TcpCat:
    """CAT over a local TCP socket instead of a virtual serial port pair (--cat-tcp PORT).
    Hamlib (WSJT-X) connects when "Serial Port" is set to 127.0.0.1:PORT; no com0com/VSPE needed, which matters on
    Windows ARM64 (no free ARM64 virtual COM driver). Same interface as the pyserial object handle_cat() uses.
    Listens on 127.0.0.1 only; one client at a time - a new connection (e.g. Test CAT) replaces the old one."""
    def __init__(self, port):
        import socket
        self.socket = socket
        self.srv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.srv.bind(("127.0.0.1", port))
        self.srv.listen(2)
        self.conn, self.buf, self.cv = None, bytearray(), threading.Condition()
        self.cts = self.dsr = False          # no RTS/DTR PTT over TCP: use PTT = CAT
        threading.Thread(target=self._accept, daemon=True).start()
    def _accept(self):
        while True:
            c, a = self.srv.accept()
            c.setsockopt(self.socket.IPPROTO_TCP, self.socket.TCP_NODELAY, 1)
            with self.cv:
                old, self.conn = self.conn, c
                self.buf.clear()
            if old:
                try: old.close()
                except OSError: pass
            print(f"{datetime.datetime.utcnow()} CAT client connected from {a[0]}:{a[1]}")
            threading.Thread(target=self._reader, args=(c,), daemon=True).start()
    def _reader(self, c):
        while True:
            try: d = c.recv(4096)
            except OSError: d = b""
            if not d: break
            with self.cv:
                if self.conn is c:
                    self.buf += d
                    self.cv.notify_all()
        with self.cv:
            if self.conn is c: self.conn = None
        log("CAT client disconnected")
    def inWaiting(self):
        with self.cv: return len(self.buf)
    @property
    def in_waiting(self): return self.inWaiting()
    def read_until(self, expected=b";", size=None):
        deadline = time.time() + 1.0
        with self.cv:
            while expected not in self.buf and time.time() < deadline: self.cv.wait(0.05)
            i = self.buf.find(expected)
            n = i + len(expected) if i >= 0 else len(self.buf)
            d = bytes(self.buf[:n]); del self.buf[:n]
            return d
    def write(self, data):
        c = self.conn
        if c:
            try: c.sendall(data)
            except OSError: pass          # client went away: reply nobody is waiting for
        return len(data)
    def flush(self): pass
    def close(self): pass                 # the listening socket lives for the whole driver run

TCP_CAT = [None]
PTY = [None]       # (cat dev, loopback dev, fds): the CAT port pair, created once per driver start

def pty_echo(fd1, fd2):
    try:
        log("pty_echo")
        while True:   # lives as long as the driver: the CAT port pair is kept across reconnects
            c1 = fd1.read(1)
            fd2.write(c1)
            #print(f'{datetime.datetime.utcnow()} {threading.current_thread().ident} > ', c1)
    except Exception as e:
        log(e)
        status[2] = False
        if config['verbose']: raise

# https://stackoverflow.com/questions/7088672/pyaudio-working-but-spits-out-error-messages-each-time
def run():
    start_ts[0] = time.time()   # watchdog grace period restarts on every (re)connect
    log(f"run #{RUN_GEN[0]+1}: driver threads alive before start: {sorted(t.name for t in threading.enumerate() if t.name != 'MainThread')}")
    RUN_GEN[0] += 1             # threads of a previous run (before a reconnect) stop when they see this change
    buf.clear()                 # no stale RX audio from before the reconnect
    in_stream = out_stream = pa = None
    try:
        status[0] = False
        status[1] = False
        status[2] = True
        status[3] = False
        status[4] = False

        if platform == "linux" or platform == "linux2":
           virtual_audio_dev_out = ""#"TRUSDX"
           virtual_audio_dev_in  = ""#"TRUSDX"
           trusdx_serial_dev     = "USB Serial"
           loopback_serial_dev   = ""
           cat_serial_dev        = ""
           alt_cat_serial_dev    = "/tmp/trusdx"
        elif platform == "win32":
           virtual_audio_dev_out = "CABLE Output"
           virtual_audio_dev_in  = "CABLE Input"
           trusdx_serial_dev     = "CH340"
           loopback_serial_dev   = "COM9"
           cat_serial_dev        = "COM8"
        elif platform == "darwin":
           virtual_audio_dev_out = "BlackHole 2ch"
           virtual_audio_dev_in  = "BlackHole 2ch"
           trusdx_serial_dev     = "USB Serial"
           loopback_serial_dev   = ""
           cat_serial_dev        = ""

        if config['direct']:
           virtual_audio_dev_out = "" # default audio device
           virtual_audio_dev_in  = "" # default audio device
        # new: choose the devices by name on any platform. --rx-audio: where the driver PLAYS receive audio (the app
        # records it); --tx-audio: where the driver RECORDS transmit audio (the app plays into it).
        if config['rx_audio']: virtual_audio_dev_in = config['rx_audio']
        if config['tx_audio']: virtual_audio_dev_out = config['tx_audio']
        for label, name in (("--rx-audio", config['rx_audio']), ("--tx-audio", config['tx_audio'])):
            if name and find_audio_device(name) < 0:
                print(f"WARNING: audio device '{name}' ({label}) not found - using the default device. Run with -v to list devices.")

        if config['verbose']:
            show_audio_devices()
            print("Audio device = ", find_audio_device(virtual_audio_dev_in), find_audio_device(virtual_audio_dev_out) )
            show_serial_devices()
            print("Serial device = ", find_serial_device(trusdx_serial_dev) )
            print("Serial loopback = ", find_serial_device(loopback_serial_dev) )
        
        tcp = config['cat_tcp'] > 0
        if platform == "win32" and not tcp:
            if find_serial_device(loopback_serial_dev):
                print(f"Conflict on COM port {loopback_serial_dev}: Go to Device Manager, select CH340 device and change in advanced settings COM port other than 8 or 9.")
                time.sleep(1)
            if find_serial_device(cat_serial_dev):
                print(f"Conflict on COM port {cat_serial_dev}: Go to Device Manager, select CH340 device and change in advanced settings COM port other than 8 or 9.")
                time.sleep(1)

        if tcp:
           if TCP_CAT[0] is None: TCP_CAT[0] = TcpCat(config['cat_tcp'])
           cat_serial_dev = f"127.0.0.1:{config['cat_tcp']}"
           print(f"CAT over TCP: set the WSJT-X Serial Port to {cat_serial_dev}")
        elif platform != "win32":  # skip for Windows as we have com0com there
           # fix: create the CAT port pair ONCE and keep it across reconnects (USB replug, radio reboot, network
           # drop). A new pair per run moved /tmp/trusdx, so rigctld/WSJT-X stayed on the old, dead port.
           if PTY[0] is None:
              _master1, slave1 = os.openpty()  # make a tty <-> tty device where one end is opened as serial device, other end by CAT app
              _master2, slave2 = os.openpty()
              master1 = os.fdopen(_master1, 'rb+', 0)
              master2 = os.fdopen(_master2, 'rb+', 0)
              threading.Thread(target=pty_echo, args=(master1,master2), daemon=True).start()
              threading.Thread(target=pty_echo, args=(master2,master1), daemon=True).start()
              PTY[0] = (os.ttyname(slave1), os.ttyname(slave2), slave1, slave2)
              if platform in ("darwin", "linux", "linux2"):  # stable CAT port name: the /dev/ttysNNN (/dev/pts/N) number differs every start
                 alt_cat_serial_dev = "/tmp/trusdx"
                 if os.path.lexists(alt_cat_serial_dev): os.remove(alt_cat_serial_dev)
                 os.symlink(PTY[0][0], alt_cat_serial_dev)
                 print(f"Stable CAT port: {alt_cat_serial_dev} -> {PTY[0][0]}  (use {alt_cat_serial_dev} in WSJT-X)")
           cat_serial_dev, loopback_serial_dev = PTY[0][0], PTY[0][1]
        try:
            # fix: write_timeout=0 means non-blocking writes that silently DROP bytes when the buffer is full
            ser2 = TCP_CAT[0] if tcp else serial.Serial(loopback_serial_dev, 115200, write_timeout = 2)
        except Exception as e:
            if platform == "win32":
                print(f"VSPE virtual com port {loopback_serial_dev} not available ({e}): reinstall or enable VSPE (COM8/COM9 pair)")
            else:
                print(f"virtual CAT port {loopback_serial_dev} could not be opened ({e})")
        
        try:
           #in_stream = pyaudio.PyAudio().open(frames_per_buffer=0, format = pyaudio.paInt16, channels = 1, rate = audio_tx_rate, input = True, input_device_index = find_audio_device(virtual_audio_dev_out) if virtual_audio_dev_out else -1)
           pa = pyaudio.PyAudio()   # one instance for both streams, so they can be closed on reconnect
           in_stream = pa.open(frames_per_buffer=config['block_size'], format = pyaudio.paInt16, channels = 1, rate = audio_tx_rate, input = True, input_device_index = find_audio_device(virtual_audio_dev_out) if virtual_audio_dev_out else -1)
           out_stream = pa.open(frames_per_buffer=0, format = pyaudio.paInt8, channels = 1, rate = audio_rx_rate, output = True, output_device_index = find_audio_device(virtual_audio_dev_in) if virtual_audio_dev_in else -1)
        except Exception as e:
            print(f"Audio device could not be opened ({e})")
            if platform == "win32": print("  VB-Audio CABLE not found: reinstall or enable it")
            elif platform == "darwin": print("  install BlackHole 2ch (brew install --cask blackhole-2ch) and restart the Mac")
            else:
                print("  run in terminal: pactl load-module module-null-sink sink_name=TRUSDX sink_properties=device.description=\"TRUSDX\" && pavucontrol  (hint: sudo modprobe snd-aloop)")
            raise
 
        try:
            # fix: was write_timeout=0 (non-blocking): during TX the link is full of audio, so pieces of the
            # audio, ';', 'US' and even 'RX;' were silently dropped -> E; floods and a trx stuck in TX.
            if config['serial_url']:
                # new: radio on another computer (linux/trusdx-netbridge.py), e.g. socket://pi.local:4532. Stop bits
                # and RTS are set by the bridge, which also un-keys the radio if this laptop drops off the network.
                ser = serial.serial_for_url(config['serial_url'], do_not_open = True, baudrate = 115200, write_timeout = 2)
                ser.open()
                try: ser._socket.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)   # 20 ms audio pieces, no Nagle delay
                except Exception: pass
                print(f"Radio over the network: {config['serial_url']}")
            else:
                ser = serial.Serial(None, 115200, write_timeout = 2,
                                    stopbits = serial.STOPBITS_TWO if config['stop_bits'] == 2 else serial.STOPBITS_ONE)
                ser.port = find_serial_device(trusdx_serial_dev)
                if config['rts_low']:
                    # DL2MAN CAT spec: "DTR should be HIGH, RTS should be LOW on RX, may be HIGH to key CW/PTT".
                    # pyserial asserts both by default; set the states before open() so they apply right away.
                    ser.dtr = True; ser.rts = False
                ser.open()
        except Exception as e:
            if config['serial_url']:
                print(f"Network radio {config['serial_url']} not reachable ({e}) - is the bridge running on the Pi?")
                time.sleep(3)
                raise
            dev = find_serial_device(trusdx_serial_dev)
            print(f"truSDX device not found ({e})" if not dev else f"truSDX on {dev} could not be opened ({e}) - is another program using it?")
            time.sleep(2)   # retry every few seconds instead of flooding the window
            raise
            
        #ser.dtr = True
        #ser.rts = False
        time.sleep(3) # wait for device to start after opening serial port
        ser.write(b";MD2;UA2;" if not config['unmute'] else b";MD2;UA1;") # enable audio streaming, mute trusdx
        #status[1] = True

        gen = RUN_GEN[0]
        threading.Thread(target=receive_serial_audio, args=(ser,ser2,out_stream,gen), daemon=True, name=f"rx-{gen}").start()
        threading.Thread(target=play_receive_audio, args=(out_stream,gen), daemon=True, name=f"play-{gen}").start()
        threading.Thread(target=transmit_audio_via_serial, args=(in_stream,ser,ser2,gen), daemon=True, name=f"tx-{gen}").start()

        print(f"(tr)uSDX driver OK! Available devices = [{virtual_audio_dev_in}, {virtual_audio_dev_out}, {cat_serial_dev}]" )
        #ts = time.time()
        while status[2]:    # wait and idle
            # display some stats every 1 seconds
            #log(f"{int(time.time()-ts)} buf: {len(buf)}")
            time.sleep(1)
    except Exception as e:
        log(e)
        status[2] = False
    except KeyboardInterrupt:
        print("Stopping")
        status[2] = False
    try:    # safety: never leave the trx keyed when the driver stops or restarts
        if status[0]:
            status[0] = False
            time.sleep(0.2)
            ser.write(b";RX;")
            ser.flush()
            print("Driver stopping while transmitting: sent RX; to un-key the (tr)uSDX")
    except Exception:
        pass

    try:
        # clean-up
        log("Closing")
        time.sleep(1)   
        if platform != "win32" and not config['cat_tcp'] > 0:  # Linux/macOS pty pair (none in TCP mode)
           pass   # the CAT port pair stays open for the next run (see PTY)
        ser2.close()
        ser.close()
    except Exception as e:
        log(e)
    # fix: close this run's audio streams (they were left open, so after a reconnect old and new streams
    # both fed BlackHole)
    RUN_GEN[0] += 1   # make sure every thread of this run stops before the next run starts
    for st in (in_stream, out_stream):
        try:
            if st: st.stop_stream(); st.close()
        except Exception as e:
            log(e)
    try:
        if pa: pa.terminate()
        log("Closed")
    except Exception as e:
        log(e)
        pass	

def _force_reconnect(signum, frame):
    """Test hook (macOS/Linux): kill -USR1 <pid> ends the current run exactly like a USB disconnect does."""
    print(f"{datetime.datetime.utcnow()} SIGUSR1: forcing a reconnect (test)")
    status[2] = False

def main():
    if hasattr(__import__('signal'), 'SIGUSR1'):
        import signal; signal.signal(signal.SIGUSR1, _force_reconnect)
    #print("(tr)uSDX audio driver")
    while 1:
        run();

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=f"{DRIVER_NAME} (audio + CAT over USB, based on trusdx-audio)", formatter_class=argparse.ArgumentDefaultsHelpFormatter)
    parser.add_argument("-v", "--verbose", action="store_true", default=False, help="increase verbosity")
    parser.add_argument("--vox", action="store_true", default=False, help="VOX audio-triggered PTT (Linux only)")
    parser.add_argument("--unmute", action="store_true", default=False, help="Enable (tr)usdx audio")
    parser.add_argument("--rx-audio", default="", metavar="NAME", help="audio device the driver plays receive audio to (name or part of it); default: BlackHole 2ch / CABLE Input / Linux default")
    parser.add_argument("--tx-audio", default="", metavar="NAME", help="audio device the driver records transmit audio from (name or part of it); default: BlackHole 2ch / CABLE Output / Linux default")
    parser.add_argument("--direct", action="store_true", default=False, help="Use system audio devices (no loopback)")
    parser.add_argument("--no-rtsdtr", action="store_true", default=False, help="Disable RTS/DTR-triggered PTT")
    parser.add_argument("--cat-tcp", type=int, default=0, metavar="PORT", help="CAT over TCP on 127.0.0.1:PORT instead of a virtual serial port (WSJT-X Serial Port: 127.0.0.1:PORT, PTT: CAT). Needed on Windows ARM64; 0 = off")
    #parser.add_argument("-B", "--block-size", type=int, default=512 if platform == "win32" else 32, help="RX Block size")
    parser.add_argument("-B", "--block-size", type=int, default=512, help="RX Block size")
    parser.add_argument("-T", "--tx-block-size", type=int, default=48, help="TX Block size")
    parser.add_argument("--tx-rate", type=int, default=10473, help="TX audio sample rate sent to the trx (default 10473 = what 2 stop bits carry; 11520 overflows it)")
    parser.add_argument("--stop-bits", type=int, choices=[1, 2], default=2, help="serial stop bits to the trx (2 = even byte pacing with spare time for the trx; 1 = factory)")
    parser.add_argument("--rts-low", action="store_true", default=False, help="hold RTS low on the trx port (DL2MAN spec: DTR high, RTS low in RX); default: pyserial default (both high)")
    parser.add_argument("--serial-url", default="", metavar="URL", help="radio on another computer running linux/trusdx-netbridge.py, e.g. socket://pi.local:4532 (stop bits/RTS are set on the bridge)")
    parser.add_argument("--net-buffer", type=int, default=200, metavar="MS", help="with --serial-url: TX audio cushion against network delays (adds this much TX delay)")
    parser.add_argument("--forward-if", action="store_true", default=False, help="send IF; polls to the trx instead of answering them from its FA/MD replies")
    parser.add_argument("--rawlog", default=os.environ.get('TRUSDX_RAWLOG', ''), help="debug: file to record raw data from the trx")
    args = parser.parse_args()
    config = vars(args)
    audio_tx_rate = config['tx_rate']
    if config['rawlog']: RAWLOG[0] = open(config['rawlog'], 'w')
    print(f"{DRIVER_NAME} {DRIVER_VERSION} - TX audio {audio_tx_rate} S/s, {config['stop_bits']} stop bits  (based on trusdx-audio by SQ3SWF / PE1NNZ)")
    if platform == "win32":
        try: __import__("ctypes").windll.kernel32.SetConsoleTitleW(f"{DRIVER_NAME} {DRIVER_VERSION}")
        except Exception: pass
    elif sys.stdout.isatty():
        print(f"\033]0;{DRIVER_NAME}\007", end="", flush=True)   # terminal window/tab title
    if config['verbose']: print(config)

    #try:
    main()
    #except Exception as e:
    #    print(f"Error: {e}")
    #    time.sleep(3)
