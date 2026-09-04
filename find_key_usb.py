"""
find_key_usb.py - locate an unknown Epson model's EEPROM read key over USB.

For a model that isn't in the databases, the network brute-forcer
(find_key.py) is useless: these Epsons refuse the '||' factory commands on
SNMP and answer ":NA;" no matter what the key is. It has to be done over
the USB cable.

TRANSPORT (this is the part that matters)
-----------------------------------------
Factory commands do NOT travel down the raw USB print pipe. reinkpy
negotiates IEEE 1284.4 and opens a dedicated 'EPSON-CTRL' D4 socket, and
that is where '||' commands are answered. Writing them to the raw pipe
instead is silently swallowed by the print engine on at least some models -
the printer stays chatty (it keeps pushing unsolicited '@BDC ST2' status
packets back) while never answering a single EEPROM read, which looks
exactly like a dead cable but isn't.

So this tool drives the same transport padzero.py uses: WinUsbPrintIO ->
reinkpy.UsbDevice -> EpsonD4.ctrl_channel. The old raw path is kept behind
--raw because it is known to work on the ET-4800 and is useful for
comparison, but it is not the default and should not be trusted on a model
you haven't confirmed.

How it tells a wrong key from a right one:
  * wrong key  -> the printer replies ":NA;" (not available)
  * right key  -> the printer replies "EE:AAAAVV" (address echo + value)

PREFLIGHT
---------
Before sweeping, it asks for printer status over the same D4 control
channel the key search will use. If that answers, the channel is proven and
any later silence is a real result about the printer rather than about our
plumbing. If it doesn't, we move to the next USB interface rather than
burning an hour on a pipe nothing is listening to.

Interface selection is automatic. Multifunction Epsons publish several USB
interfaces and only one speaks D4. Epson devices (VID 04B8) are tried
first. Override with -d N.

Two modes:
  (default)  try the ~170 read keys already known from the reinkpy and
             epson_print_conf databases - about a minute.
  --full     sweep the whole 16-bit key space (roughly an hour, resumable
             with --start).

Read-only: only ever sends read ('A') commands. Never writes EEPROM.

Requirements: the genuine Epson driver (not the generic Windows "IPP Class
Driver") and a USB cable. No pysnmp, no Wi-Fi.
"""
import argparse
import re
import struct
import sys
import time

# Importing padzero puts the bundled reinkpy on sys.path and silences its
# very chatty D4 handshake logging. Do this before importing reinkpy.
import padzero
from padzero import open_transport, quiet

from usb_direct import (list_usb_printers, UsbPrinter, factory, wrap, exchange,
                        check_channel, describe, is_epson)

# Distinct read keys harvested from reinkpy/reinkpy/epson.toml (rkey) and
# epson_print_conf's printer dictionary (read_key). Kept in sync with the
# same list in find_key.py.
KNOWN_KEYS = [
    0x0001, 0x0005, 0x0006, 0x000D, 0x0013, 0x0015, 0x0028, 0x0065, 0x0066,
    0x0069, 0x0077, 0x0106, 0x0143, 0x0144, 0x0145, 0x0161, 0x0163, 0x0168,
    0x0169, 0x0175, 0x0193, 0x0264, 0x0282, 0x0301, 0x0338, 0x0371, 0x0378,
    0x0388, 0x0392, 0x0395, 0x0406, 0x0414, 0x0443, 0x0450, 0x0474, 0x0479,
    0x0501, 0x0504, 0x0508, 0x0511, 0x0518, 0x0528, 0x0533, 0x0539, 0x0543,
    0x054A, 0x0551, 0x0553, 0x0555, 0x0557, 0x0565, 0x0585, 0x0596, 0x0604,
    0x0607, 0x0614, 0x0619, 0x0624, 0x0625, 0x0631, 0x0636, 0x0637, 0x0649,
    0x0704, 0x0718, 0x0719, 0x0720, 0x0736, 0x0768, 0x0789, 0x0797, 0x0810,
    0x0823, 0x0824, 0x0832, 0x0837, 0x0849, 0x0855, 0x0872, 0x0877, 0x0879,
    0x0881, 0x0882, 0x0886, 0x0928, 0x0941, 0x0946, 0x0950, 0x0953, 0x0972,
    0x0976, 0x0981, 0x0986, 0x0987, 0x0A0D, 0x0C0D, 0x0C0F, 0x0E10, 0x1108,
    0x110F, 0x120E, 0x1404, 0x1413, 0x1504, 0x1542, 0x1606, 0x1710, 0x1713,
    0x1808, 0x180D, 0x184A, 0x1907, 0x1A07, 0x1E09, 0x1F0D, 0x2010, 0x204A,
    0x220B, 0x234B, 0x240D, 0x2710, 0x2810, 0x2A06, 0x2B0D, 0x2D08, 0x2D0B,
    0x3010, 0x310C, 0x3208, 0x330B, 0x334B, 0x340C, 0x354B, 0x364A, 0x364B,
    0x370E, 0x3848, 0x394B, 0x3B10, 0x3E11, 0x450E, 0x4513, 0x4548, 0x460E,
    0x4C04, 0x4C07, 0x4D04, 0x4E04, 0x4F10, 0x5010, 0x5110, 0x5202, 0x520C,
    0x520E, 0x530A, 0x5311, 0x540B, 0x5411, 0x560F, 0x574B, 0x5807, 0x5B0E,
    0x5E0A, 0x5F11, 0x600F, 0x6241, 0x6300, 0x6311, 0x884A, 0xE6B5,
]

READ_CMD = ("|", "A")   # reinkpy spells the '||' factory read this way


def classify(reply):
    """Turn a raw control-channel reply into a verdict."""
    if not reply:
        return "empty", None
    txt = reply.decode("ascii", "replace")
    m = re.search(r"EE:([0-9A-Fa-f]{6})", txt)
    if m:
        return "hit", m.group(1)
    if ":NA;" in txt:
        return "na", None
    return "other", txt.strip()[:60]


# ------------------------------------------------------------ D4 (default)
class D4Probe:
    """Key probe over reinkpy's EPSON-CTRL D4 socket - the transport that
    padzero.py itself uses, and the only one factory commands are actually
    answered on."""

    label = "D4 control channel"

    def __init__(self, path):
        import reinkpy
        self.path = path
        self.io = open_transport(path)
        self.dev = reinkpy.UsbDevice(self.io)
        self.ep = self.dev.epson
        self._held = None

    def preflight(self):
        """Ask for status over the same channel the sweep will use."""
        try:
            with quiet():
                st = self.ep.do_status()
        except Exception as e:
            return False, "%s: %s" % (type(e).__name__, e)
        if st and b"@BDC" in st:
            return True, "printer answered status on the control channel"
        return False, "no status reply over D4 (%d bytes)" % len(st or b"")

    def __enter__(self):
        # Hold the control channel open across the whole sweep so we
        # negotiate D4 once instead of once per key.
        self._held = self.ep.ctrl_channel
        self._held.__enter__()
        return self

    def __exit__(self, *exc):
        try:
            self._held.__exit__(*exc)
        except Exception:
            pass
        self._held = None

    def probe(self, rkey, addr):
        self.ep.spec.rkey = rkey
        try:
            with quiet():
                reply = self.ep.ctrl((READ_CMD, struct.pack("<H", addr)))[0]
        except Exception as e:
            return "other", "%s: %s" % (type(e).__name__, e)
        return classify(reply)


# ---------------------------------------------------------------- raw path
class RawProbe:
    """The original transport: remote-mode bytes written straight to the USB
    printer interface, no D4 negotiation. Known to work on the ET-4800.
    Known to be silently ignored on the EP-M476T. Kept for comparison."""

    label = "raw USB pipe (no D4)"

    def __init__(self, path):
        self.path = path
        self.dev = UsbPrinter(path)

    def preflight(self):
        alive, reply = check_channel(self.dev)
        if alive:
            return True, "printer answered the raw status query"
        return False, "no reply to raw status query (%d bytes)" % len(reply)

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.dev.close()

    def probe(self, rkey, addr):
        cmd = wrap(factory("A", struct.pack("<H", addr), rkey=rkey))
        return classify(exchange(self.dev, cmd, want=b"EE:"))


# ------------------------------------------------------------------ picking
def reinkpy_missing():
    """The source ZIP does not ship reinkpy - it is vendored at build time
    (see .gitignore / requirements.txt). Running find_key_usb.py straight
    out of the ZIP therefore has no D4 layer. Say so properly instead of
    surfacing a bare ModuleNotFoundError from inside the probe."""
    try:
        import reinkpy  # noqa: F401
        return False
    except ImportError:
        return True


def explain_missing_reinkpy():
    print("=" * 62)
    print("reinkpy is not installed, so the D4 control channel - the only")
    print("channel that answers EEPROM commands - is unavailable.")
    print("")
    print("This is expected if you just downloaded the source ZIP. reinkpy")
    print("is fetched at build time and is not included in it.")
    print("")
    print("EASIEST FIX: download find_key_usb.exe from the Releases page.")
    print("It has reinkpy built in and needs no Python at all.")
    print("")
    print("Or, to keep running from source:")
    print('    pip install "reinkpy @ git+https://codeberg.org/atufi/reinkpy"')
    print("")
    print("Do NOT use --raw to get around this. It cannot find a key the")
    print("control channel can't, and it can leave the printer stuck in a")
    print("'cancelling' loop until you power-cycle it.")
    print("=" * 62)


def enumerate_candidates(index):
    """List USB printer interfaces and decide which to try, Epson first."""
    try:
        paths = list_usb_printers()
    except OSError as e:
        print("SetupAPI enumeration failed: %s" % e)
        return None

    if not paths:
        print("No USB printers found at all.")
        print("")
        print("  * Is the USB cable plugged in at both ends?")
        print("  * Is the printer installed as a USB printer rather than a")
        print("    network / WSD one? A network queue publishes no USB")
        print("    interface for this tool to open.")
        print("  * Is the genuine Epson driver installed rather than the")
        print("    generic Windows 'IPP Class Driver'? Check with:")
        print("      Get-Printer | Select-Object Name, DriverName")
        return None

    print("USB printer interfaces found:")
    for i, p in enumerate(paths):
        print("  [%d] %s" % (i, describe(p)))
        print("      %s" % p)
    print("")

    if index is not None:
        if index >= len(paths):
            print("No interface at index %d." % index)
            return None
        return [(index, paths[index])]

    epson = [(i, p) for i, p in enumerate(paths) if is_epson(p)]
    other = [(i, p) for i, p in enumerate(paths) if not is_epson(p)]
    if not epson:
        print("NOTE: none of these are Epson (VID 04B8). Trying them anyway,")
        print("but your printer is probably not among them.")
        print("")
    return epson + other


def open_live(order, cls, skip_preflight=False):
    """Open the first interface whose control channel actually answers."""
    for i, path in order:
        print("Trying interface [%d]  %s" % (i, describe(path)))
        print("  transport: %s" % cls.label)
        try:
            with quiet():
                probe = cls(path)
        except Exception as e:
            print("  cannot open: %s: %s" % (type(e).__name__, e))
            continue

        if skip_preflight:
            print("  preflight skipped by request.")
            return probe, i

        ok, why = probe.preflight()
        print("  preflight: %s" % why)
        if ok:
            print("")
            return probe, i
        print("  -> not it, moving on.")

    return None, None


def main():
    ap = argparse.ArgumentParser(
        description="Find an Epson EEPROM read key over USB")
    ap.add_argument("-d", "--device", type=int, default=None,
                    help="index of the USB printer interface "
                         "(default: pick automatically, Epson first)")
    ap.add_argument("--addr", type=int, default=0,
                    help="EEPROM address to probe (default 0)")
    ap.add_argument("--full", action="store_true",
                    help="sweep all 65536 keys instead of the known list")
    ap.add_argument("--start", type=lambda s: int(s, 0), default=0,
                    help="with --full, resume from this key")
    ap.add_argument("--raw", action="store_true",
                    help="DIAGNOSTIC ONLY. Use the old non-D4 raw pipe. "
                         "This writes remote-mode bytes down the print data "
                         "path, which some models mistake for a malformed "
                         "print job and then sit in a 'cancelling' loop "
                         "until power-cycled. Never a workaround for a "
                         "missing reinkpy.")
    ap.add_argument("--skip-preflight", action="store_true",
                    help="do not require a status reply before sweeping")
    args = ap.parse_args()

    if not args.raw and reinkpy_missing():
        explain_missing_reinkpy()
        return 1

    if args.raw:
        print("!" * 62)
        print("--raw is a diagnostic, not a fallback. It writes to the print")
        print("data path, which some models mistake for a malformed print")
        print("job and then sit in a 'cancelling' loop until power-cycled.")
        print("It is read-only and cannot alter your counters, but if the")
        print("printer starts behaving oddly, power-cycle it and stop.")
        print("!" * 62)
        print("")

    order = enumerate_candidates(args.device)
    if not order:
        return 1

    cls = RawProbe if args.raw else D4Probe
    probe, which = open_live(order, cls, args.skip_preflight)
    if probe is None:
        print("=" * 62)
        print("NO USABLE INTERFACE - nothing answered on %s." % cls.label)
        print("")
        print("Status is not key-protected, so this is NOT a 'wrong key'")
        print("result and --full would not help.")
        print("")
        if not args.raw:
            print("Do NOT reach for --raw to get past this. It talks down")
            print("the print data path, which some printers mistake for a")
            print("broken print job and then sit in a 'cancelling' loop.")
            print("It cannot find a key that the control channel can't.")
        else:
            print("Check that the interface list above shows EPSON / VID")
            print("04B8, and that Get-Printer shows Epson's own driver")
            print("rather than the 'IPP Class Driver'.")
        print("=" * 62)
        return 1

    keys = range(args.start, 0x10000) if args.full else KNOWN_KEYS
    total = (0x10000 - args.start) if args.full else len(keys)

    print("=" * 62)
    print("USB READ KEY SEARCH   interface [%d]   addr %d" % (which, args.addr))
    print("transport: %s" % cls.label)
    print("mode: %s   candidates: %d"
          % ("FULL SWEEP" if args.full else "known keys", total))
    print("=" * 62)

    with probe:
        hits = []
        na_count = 0
        empty_count = 0
        other = None
        t0 = time.time()
        for i, rkey in enumerate(keys):
            kind, data = probe.probe(rkey, args.addr)
            if kind == "hit":
                print("")
                print("*** HIT ***  read_key = 0x%04X  ->  EE:%s" % (rkey, data))
                print("    address 0x%s  value 0x%s (%d)"
                      % (data[:4], data[4:], int(data[4:], 16)))
                hits.append(rkey)
                if not args.full:
                    break
            elif kind == "na":
                na_count += 1
            elif kind == "empty":
                empty_count += 1
            elif other is None:
                other = data

            if args.full and i and i % 250 == 0:
                el = time.time() - t0
                rate = i / el if el else 0
                left = (total - i) / rate if rate else 0
                print("  %6d/%d  %.0f keys/s  ~%.0f min left  (last 0x%04X)"
                      % (i, total, rate, left / 60, rkey))
            elif not args.full and i and i % 25 == 0:
                print("  tried %d/%d ..." % (i, total))

        print("")
        print("=" * 62)
        if hits:
            print("FOUND %d working key(s): %s"
                  % (len(hits), ", ".join("0x%04X" % k for k in hits)))
            print("")
            print("Post this key on the thread so the model can be added.")
        elif empty_count and empty_count >= na_count:
            print("Passed the status preflight, then went silent for %d of"
                  % empty_count)
            print("%d key probes." % total)
            print("The printer is talking but not answering the EEPROM read")
            print("at all - which points at firmware having that command")
            print("switched off rather than at a wrong key.")
            if other:
                print("First unusual reply: %s" % other)
        else:
            print("NO WORKING KEY FOUND among %d candidates (%d refused)."
                  % (total, na_count))
            print("")
            print("Every probe got a clean ':NA;', so the channel is good and")
            print("these keys are simply wrong for this model.")
            if args.full:
                print("The full 16-bit space is exhausted -> the EEPROM read")
                print("command is disabled in firmware on this unit.")
            else:
                print("Re-run with --full for the whole key space (about an")
                print("hour) before concluding lockout.")
        print("Elapsed: %.1f s" % (time.time() - t0))
        print("=" * 62)
    return 0


if __name__ == "__main__":
    sys.exit(main())
