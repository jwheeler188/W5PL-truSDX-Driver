"""Tests for trusdx-txrx.py with a simulated (tr)uSDX. No radio, sound card or virtual cable needed.

Run from the repository folder:   python3 -m unittest discover -s tests -v
Needs pyserial (pip install pyserial). pyaudio is replaced by a stub if it isn't installed.

FakeRadio behaves like firmware 2.00x on the CAT link as measured with the real radio:
  - UA1;/UA2; starts the RX audio stream ("US" + 8-bit samples, ~7812 B/s); UA0; stops it
  - TX0; keys it (no RX audio while transmitting); RX; un-keys it
  - after TX it does not stream again until it gets UA after RX; (the driver sends ;RX; ;UA2;)
  - FA;/MD;/IF; queries are answered inside the stream: ...audio;FA00014074000;audio...
  - fault mode needs_ua0: after a TX it ignores UA1/UA2 until UA0; has been sent (the failure the streaming reset
    is for; reported once on 2.00x as "RX audio broken after one TX until the radio is rebooted")
"""
import importlib.util, os, re, sys, threading, time, types, unittest

HERE = os.path.dirname(os.path.abspath(__file__))
DRIVER = os.path.join(HERE, "..", "trusdx-txrx.py")

if "pyaudio" not in sys.modules:
    try: import pyaudio  # noqa: F401
    except Exception: sys.modules["pyaudio"] = types.SimpleNamespace(paInt16=8, paInt8=16, PyAudio=None)


def load_driver(**options):
    """A fresh copy of the driver module (clean global state), configured like the command line would."""
    spec = importlib.util.spec_from_file_location("trusdx_driver_under_test", DRIVER)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    m.config = vars(m.build_parser().parse_args([]))
    m.config.update(options)
    m.audio_tx_rate = m.config["tx_rate"]
    m.start_ts[0] = time.time() - 10        # skip the start-up grace period
    return m


class FakeRadio:
    """Serial-port stand-in for the radio (pyserial interface used by the driver)."""
    def __init__(self, needs_ua0=False, streaming=False):
        self.lock = threading.Lock()
        self.out = bytearray()              # radio -> driver
        self.log = []                       # (time, bytes) of everything the driver wrote
        self.pending = b""                  # driver bytes not yet parsed
        self.tx = False
        self.streaming = streaming
        self.need_ua_after_tx = False       # after TX: no stream until UA (and with needs_ua0: until UA0 first)
        self.needs_ua0 = needs_ua0
        self.ua0_seen = False
        self.started = False                # "US" sent since streaming (re)started
        self.alive = True
        threading.Thread(target=self._stream, daemon=True).start()

    # pyserial interface
    def write(self, data):
        with self.lock:
            self.log.append((time.time(), bytes(data)))
            self.pending += bytes(data)
            self._parse()
        return len(data)
    def flush(self): pass
    @property
    def in_waiting(self):
        with self.lock: return len(self.out)
    def read(self, n=1):
        with self.lock:
            d = bytes(self.out[:n]); del self.out[:n]; return d
    def close(self): self.alive = False

    # radio behaviour
    def _parse(self):
        # commands end in ';'; TX audio never contains ';' (the driver replaces it), so splitting on ';' is safe
        *cmds, self.pending = self.pending.split(b";")
        for c in cmds:
            m = re.search(rb"(UA[012]|TX0|RX|FA|MD|IF)(\d*)$", c)
            if not m: continue
            cmd, arg = m.group(1), m.group(2)
            if cmd == b"TX0": self.tx = True; self.streaming = False
            elif cmd == b"RX":
                if self.tx: self.need_ua_after_tx = True; self.ua0_seen = False
                self.tx = False
            elif cmd == b"UA0": self.streaming = False; self.ua0_seen = True
            elif cmd in (b"UA1", b"UA2") and not self.tx:
                if self.need_ua_after_tx and self.needs_ua0 and not self.ua0_seen: continue   # fault: ignored
                self.need_ua_after_tx = False
                if not self.streaming: self.streaming = True; self.started = False
            elif cmd in (b"FA", b"MD", b"IF") and not arg and self.streaming:
                reply = {b"FA": b"FA00014074000;", b"MD": b"MD2;",
                         b"IF": b"IF00014074000     +00000000002000000;"}[cmd]
                self.out += b";" + reply

    def _stream(self):
        while self.alive:
            time.sleep(0.01)
            with self.lock:
                if self.streaming and not self.tx:
                    if not self.started: self.out += b"US"; self.started = True
                    self.out += bytes([0x80]) * 78        # 10 ms of RX audio at 7812 S/s

    def written(self):
        with self.lock: return b"".join(d for _, d in self.log)
    def times_of(self, needle):
        with self.lock: return [t for t, d in self.log if needle in d]


class FakeCat:
    """The app's end of the CAT port (what WSJT-X/hamlib would write and read)."""
    def __init__(self):
        self.inbuf, self.outbuf, self.lock = bytearray(), bytearray(), threading.Lock()
        self.cts = self.dsr = False
    def send(self, cmd):                    # the app writes a command
        with self.lock: self.inbuf += cmd
    def inWaiting(self):
        with self.lock: return len(self.inbuf)
    def read_until(self, expected=b";"):
        with self.lock:
            i = self.inbuf.find(expected)
            n = i + 1 if i >= 0 else len(self.inbuf)
            d = bytes(self.inbuf[:n]); del self.inbuf[:n]; return d
    def write(self, d):
        with self.lock: self.outbuf += d
    def flush(self): pass
    def replies(self):
        with self.lock: return bytes(self.outbuf)


class FakeAudioIn:
    """TX audio from the app: 20 ms pieces of 16-bit samples, paced like a real input stream."""
    def __init__(self, value=0): self.value = value
    def get_read_available(self): return 1
    def read(self, n, exception_on_overflow=False):
        time.sleep(n / 10473)
        return int(self.value).to_bytes(2, "little", signed=True) * n
    def stop_stream(self): pass
    def start_stream(self): pass


class Station:
    """Driver threads running against FakeRadio and FakeCat, like run() starts them."""
    def __init__(self, m, radio):
        self.m, self.radio, self.cat = m, radio, FakeCat()
        m.status[2] = True
        m.RUN_GEN[0] += 1
        gen = m.RUN_GEN[0]
        threading.Thread(target=m.receive_serial_audio, args=(radio, self.cat, None, gen), daemon=True).start()
        threading.Thread(target=m.transmit_audio_via_serial, args=(FakeAudioIn(), radio, self.cat, gen), daemon=True).start()
    def wait(self, cond, timeout):
        t0 = time.time()
        while time.time() - t0 < timeout:
            if cond(): return True
            time.sleep(0.02)
        return cond()
    def stop(self):
        self.m.status[2] = False; self.m.RUN_GEN[0] += 1; self.radio.close(); time.sleep(0.05)
    def streaming_back(self):
        return self.m.rx_seen_ts[0] > self.m.t_unkey[0] > 0


class EncodeTx(unittest.TestCase):
    def setUp(self): self.m = load_driver()

    def samples(self, *values):
        return b"".join(int(v).to_bytes(2, "little", signed=True) for v in values)

    def test_full_scale_and_silence(self):
        self.assertEqual(list(self.m.encode_tx(self.samples(0, 32767, -32768))), [128, 255, 0])

    def test_never_a_semicolon(self):
        out = self.m.encode_tx(self.samples(*range(-32768, 32768, 7)))
        self.assertNotIn(b";", out)

    def test_gain_scales_and_clips(self):
        self.assertEqual(list(self.m.encode_tx(self.samples(256 * 10), 2.0)), [128 + 20])
        self.assertEqual(list(self.m.encode_tx(self.samples(30000, -30000), 2.0)), [255, 0])

    def test_level_report_counts_clipping(self):
        self.m.encode_tx(self.samples(16384, -8192), 1.0)
        self.assertIn("peak 50%", self.m.tx_level_report())
        self.m.encode_tx(self.samples(20000, 1000), 2.0)
        r = self.m.tx_level_report()
        self.assertIn("1 of 2 samples clipped", r)
        self.assertIn("before clipping 122%", r)
        self.assertEqual(self.m.tx_level_report(), "")          # reset after each report

    def test_gain_option_rejects_zero(self):
        import contextlib, io
        with self.assertRaises(SystemExit), contextlib.redirect_stderr(io.StringIO()):
            self.m.build_parser().parse_args(["--tx-gain", "0"])


class NetworkUrl(unittest.TestCase):
    def test_socket_handler_imported_by_the_driver(self):
        """Compiled builds only contain modules the driver imports; pyserial loads socket:// by name at run time."""
        src = open(DRIVER).read()
        self.assertIn("\nimport serial.urlhandler.protocol_socket", src)
        load_driver()
        self.assertIn("serial.urlhandler.protocol_socket", sys.modules)


class UnkeyTiming(unittest.TestCase):
    def test_usb_unkey_sequence(self):
        """Measured sequence for 2.00x over USB: audio, 200 ms quiet, ;RX;, 100 ms, ;UA2;"""
        m = load_driver(); radio = FakeRadio(streaming=True)
        m.rx_seen_ts[0] = time.time()                      # streaming, so TX is allowed
        m.start_tx(radio, None, "test")
        self.assertTrue(radio.tx)
        t_audio = time.time(); radio.write(b"\x80" * 100)
        m.stop_tx(radio, None, "test")
        t_rx, t_ua = radio.times_of(b";RX;")[0], radio.times_of(b";UA2;")[0]
        self.assertGreaterEqual(t_rx - t_audio, 0.19)
        self.assertGreaterEqual(t_ua - t_rx, 0.09)
        self.assertFalse(radio.tx)
        self.assertNotIn(b"UA0;", radio.written())        # no streaming reset unless asked for or needed
        radio.close()

    def test_network_unkey_leaves_timing_to_the_bridge(self):
        m = load_driver(serial_url="socket://example:4532"); radio = FakeRadio(streaming=True)
        m.rx_seen_ts[0] = time.time()
        m.start_tx(radio, None, "test")
        t0 = time.time(); m.stop_tx(radio, None, "test")
        self.assertLess(time.time() - t0, 0.1)            # xara/hamlib must not wait (xara: 1 s PTT limit)
        radio.close()

    def test_tx_refused_when_radio_not_streaming(self):
        m = load_driver(); radio = FakeRadio(streaming=False)
        radio.needs_ua0 = True; radio.need_ua_after_tx = True   # ignores UA: never streams
        m.start_tx(radio, None, "test")
        self.assertNotIn(b"TX0;", radio.written())
        self.assertFalse(m.status[0])
        radio.close()


class StreamingRecovery(unittest.TestCase):
    def key_and_unkey(self, st, seconds=0.5):
        st.cat.send(b"TX0;")
        self.assertTrue(st.wait(lambda: st.radio.tx, 3), "radio was not keyed")
        time.sleep(seconds)
        st.cat.send(b"RX;")
        self.assertTrue(st.wait(lambda: not st.radio.tx, 2), "radio was not un-keyed")

    def test_normal_radio_streams_again_without_a_reset(self):
        m = load_driver(); st = Station(m, FakeRadio(streaming=True))
        try:
            self.assertTrue(st.wait(lambda: m.rx_seen_ts[0] > 0, 2))
            self.key_and_unkey(st)
            self.assertTrue(st.wait(st.streaming_back, 2), "RX audio did not come back")
            time.sleep(3.5)                                  # past the 2nd un-key and the reset check
            self.assertNotIn(b"UA0;", st.radio.written())
        finally: st.stop()

    def test_radio_that_needs_ua0_is_recovered(self):
        m = load_driver(); st = Station(m, FakeRadio(streaming=True, needs_ua0=True))
        try:
            self.assertTrue(st.wait(lambda: m.rx_seen_ts[0] > 0, 2))
            self.key_and_unkey(st)
            self.assertTrue(st.wait(st.streaming_back, 6), "RX audio did not come back after the streaming reset")
            self.assertTrue(st.wait(lambda: m.reset_seq[0] == 0, 1), "streaming reset did not finish")
            w = st.radio.written()
            self.assertEqual(w.count(b";UA0;"), 1)           # one reset, after the 2nd un-key had not helped
            self.assertGreater(w.find(b";UA0;"), w.rfind(b";RX;;UA2;"))
            self.assertRegex(w[w.find(b";UA0;"):], rb"^;UA0;;UA2;;RX;")   # off, on, RX - in that order
        finally: st.stop()

    def test_reset_after_tx_option(self):
        m = load_driver(reset_after_tx=True); st = Station(m, FakeRadio(streaming=True))
        try:
            self.assertTrue(st.wait(lambda: m.rx_seen_ts[0] > 0, 2))
            self.key_and_unkey(st)
            self.assertTrue(st.wait(lambda: b";UA0;" in st.radio.written(), 1), "no reset after TX")
            self.assertTrue(st.wait(st.streaming_back, 2))
        finally: st.stop()


class CatDuringTx(unittest.TestCase):
    def test_band_change_held_until_rx(self):
        m = load_driver(); st = Station(m, FakeRadio(streaming=True))
        try:
            self.assertTrue(st.wait(lambda: m.rx_seen_ts[0] > 0, 2))
            st.cat.send(b"TX0;")
            self.assertTrue(st.wait(lambda: st.radio.tx, 3))
            st.cat.send(b"FA00007074000;")
            time.sleep(0.3)
            self.assertNotIn(b"FA00007074000;", st.radio.written())   # not sent into the TX audio stream
            st.cat.send(b"RX;")
            self.assertTrue(st.wait(lambda: b"FA00007074000;" in st.radio.written(), 3), "band change was lost")
        finally: st.stop()

    def test_poll_during_tx_answered_from_cache(self):
        m = load_driver(); st = Station(m, FakeRadio(streaming=True))
        try:
            self.assertTrue(st.wait(lambda: m.rx_seen_ts[0] > 0, 2))
            st.cat.send(b"IF;")
            self.assertTrue(st.wait(lambda: b"IF0001407" in st.cat.replies(), 2), "no IF reply in RX")
            st.cat.send(b"TX0;")
            self.assertTrue(st.wait(lambda: st.radio.tx, 3))
            before = st.radio.written().count(b"IF;")
            st.cat.send(b"IF;")
            self.assertTrue(st.wait(lambda: st.cat.replies().count(b"IF0001407") >= 2, 2))
            self.assertEqual(st.cat.replies().rsplit(b"IF", 1)[1][26:27], b"1")   # P8: transmitting
            self.assertEqual(st.radio.written().count(b"IF;"), before)          # not sent to the radio
            st.cat.send(b"RX;")
        finally: st.stop()


class RxParsing(unittest.TestCase):
    def test_audio_and_cat_reply_separated(self):
        m = load_driver(); cat = FakeCat(); m.status[3] = True
        m.handle_rx_audio(None, cat, None, b"US" + b"\x80" * 10)
        m.handle_rx_audio(None, cat, None, b"\x81" * 5 + b";")
        m.handle_rx_audio(None, cat, None, b"FA00014074000;")
        self.assertEqual(b"".join(m.buf), b"\x80" * 10 + b"\x81" * 5 + b";")
        self.assertEqual(cat.replies(), b"FA00014074000;")

    def test_ua_echo_not_forwarded(self):
        m = load_driver(); cat = FakeCat(); m.status[3] = True
        m.handle_rx_audio(None, cat, None, b"UA2;")
        self.assertEqual(cat.replies(), b"")


if __name__ == "__main__":
    unittest.main()
