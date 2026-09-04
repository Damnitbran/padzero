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
import io
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
def parse_range(text):
    """'0-255' or '0x00-0xff' -> (lo, hi)."""
    try:
        lo, hi = text.split("-", 1)
        lo, hi = int(lo, 0), int(hi, 0)
    except ValueError:
        raise SystemExit("Bad --range %r, expected something like 0-255" % text)
    if lo < 0 or hi < lo:
        raise SystemExit("Bad --range %r" % text)
    return lo, hi


def dump_block(probe, rkey, lo, hi, which):
    """Read every address in [lo, hi] with `rkey` and write a report.

    Read-only. Returns the output path, or None if nothing could be read.
    """
    print("=" * 62)
    print("EEPROM DUMP   interface [%d]   key 0x%04X   addr %d-%d"
          % (which, rkey, lo, hi))
    print("read-only: this only ever sends read commands")
    print("=" * 62)

    model = serial = "unknown"
    dev = getattr(probe, "dev", None)
    if dev is not None:
        try:
            with quiet():
                model = probe.ep.detected_model or "unknown"
        except Exception:
            pass
        try:
            with quiet():
                serial = dev.serial_number or "unknown"
        except Exception:
            pass

    rows = []
    refused = silent = 0
    t0 = time.time()
    for addr in range(lo, hi + 1):
        kind, data = probe.probe(rkey, addr)
        if kind == "hit":
            echoed, value = int(data[:4], 16), int(data[4:], 16)
            rows.append((addr, value, echoed == addr))
        elif kind == "na":
            refused += 1
            rows.append((addr, None, True))
        else:
            silent += 1
            rows.append((addr, None, True))
        if addr and (addr - lo) % 64 == 0:
            print("  read %d/%d ..." % (addr - lo, hi - lo + 1))

    got = [r for r in rows if r[1] is not None]
    if not got:
        print("")
        print("Nothing readable in that range with key 0x%04X." % rkey)
        print("(%d refused, %d silent)" % (refused, silent))
        return None

    name = "eeprom-%s-%04X.txt" % (
        re.sub(r"[^A-Za-z0-9._-]", "_", str(model)), rkey)
    with io.open(name, "w", encoding="utf-8", newline="\n") as f:
        f.write("Pad Zero EEPROM dump (read-only)\n")
        f.write("model      : %s\n" % model)
        f.write("serial     : %s\n" % serial)
        f.write("read_key   : 0x%04X\n" % rkey)
        f.write("range      : %d-%d\n" % (lo, hi))
        f.write("readable   : %d of %d  (%d refused, %d no reply)\n"
                % (len(got), hi - lo + 1, refused, silent))
        f.write("\naddr(dec)  addr(hex)  value(dec)  value(hex)\n")
        for addr, value, ok in rows:
            if value is None:
                f.write("%9d  %9s  %10s  %10s\n"
                        % (addr, "0x%02X" % addr, "-", "-"))
            else:
                f.write("%9d  %9s  %10d  %10s%s\n"
                        % (addr, "0x%02X" % addr, value, "0x%02X" % value,
                           "" if ok else "   <- address echo mismatch"))

    nonzero = [(a, v) for a, v, _ in rows if v]
    print("")
    print("Read %d of %d addresses (%d refused, %d no reply)."
          % (len(got), hi - lo + 1, refused, silent))
    print("Non-zero values: %d" % len(nonzero))
    if nonzero:
        preview = ", ".join("%d=%d" % (a, v) for a, v in nonzero[:12])
        print("  %s%s" % (preview, " ..." if len(nonzero) > 12 else ""))
    print("")
    print("Saved to: %s" % name)
    print("Elapsed: %.1f s" % (time.time() - t0))
    print("=" * 62)
    print("")
    print("NOTE: this file contains your printer's serial number. If you'd")
    print("rather not post that publicly, send it in a direct message.")
    return name


WRITE_CMD = ("|", "B")


def candidate_wkeys(rkey, everything=False):
    """Write keys worth trying for a model whose read key is `rkey`.

    epson.toml stores both `wkey` (what goes on the wire) and `wkey1` (the
    same string shifted down a byte, which is the readable Indonesian word).
    Groups that share a read key do NOT necessarily share a write key - the
    0x364A family alone contains both Maribaya and Arantifo - which is the
    whole reason this probe exists.
    """
    import importlib.resources as ir
    import tomllib
    data = tomllib.loads(
        ir.files("reinkpy").joinpath("epson.toml").read_bytes().decode("utf-8"))

    same, other = [], []
    for g in data.get("EPSON", []):
        wk = g.get("wkey")
        if not wk:
            continue
        entry = (wk, g.get("wkey1") or "?", (g.get("models") or ["?"])[0])
        (same if g.get("rkey") == rkey else other).append(entry)

    seen, out = set(), []
    for wk, wk1, model in same + (other if everything else []):
        if wk in seen:
            continue
        seen.add(wk)
        out.append((wk, wk1, model))
    return out


def try_wkeys(probe, rkey, addr, everything=False):
    """Identify the write key with a no-op write.

    Reads `addr`, then writes the SAME value back under each candidate key.
    A wrong key is refused and changes nothing; a right key returns ':OK;'
    and writes the value that was already there. Either way the printer is
    left exactly as found, which is what makes this safe to run on someone
    else's printer.
    """
    print("=" * 62)
    print("WRITE KEY PROBE   key 0x%04X   addr %d" % (rkey, addr))
    print("=" * 62)

    kind, data = probe.probe(rkey, addr)
    if kind != "hit":
        print("Could not read addr %d first (%s). Aborting - this probe only"
              % (addr, kind))
        print("writes a value back that it has already read.")
        return None
    current = int(data[4:], 16)
    print("addr %d currently reads %d (0x%02X)." % (addr, current, current))
    print("Each candidate writes that same value back, so a successful")
    print("write is a no-op and a failed one changes nothing.")
    print("")

    cands = candidate_wkeys(rkey, everything)
    if not cands:
        print("No candidate write keys found for read key 0x%04X." % rkey)
        return None

    # Negative control. This key is deliberate nonsense and must be refused.
    # If the printer accepts it, then ':OK;' is not evidence of a valid key
    # on this model - most likely the firmware short-circuits a write whose
    # value already matches, and answers before it ever checks the key.
    CONTROL = "Qqqqqqqq"
    cands = list(cands) + [(CONTROL, "CONTROL", "deliberate nonsense")]

    print("Trying %d candidate(s), including one deliberate dud as a check."
          % len(cands))
    print("")

    accepted = []
    control_accepted = False
    for wk, wk1, model in cands:
        payload = struct.pack("<HB", addr, current) + wk.encode("ascii")
        try:
            with quiet():
                reply = probe.ep.ctrl((WRITE_CMD, payload))[0]
        except Exception as e:
            print("  %-10s (%-10s) error: %s" % (wk1, model, type(e).__name__))
            continue
        ok = b":OK;" in (reply or b"")
        print("  %-10s (as used by %-19s) -> %s"
              % (wk1, model, "ACCEPTED" if ok else "refused"))
        if ok and wk1 == "CONTROL":
            control_accepted = True
        elif ok:
            accepted.append((wk, wk1))

    print("")
    after, data2 = probe.probe(rkey, addr)
    if after == "hit":
        back = int(data2[4:], 16)
        print("addr %d now reads %d (was %d) - %s"
              % (addr, back, current,
                 "unchanged, as intended" if back == current
                 else "CHANGED, this is unexpected, stop and report it"))
    else:
        print("Could not re-read addr %d to confirm (%s)." % (addr, after))

    print("=" * 62)
    if control_accepted:
        print("INCONCLUSIVE - the deliberate dud key was accepted too.")
        print("")
        print("This printer answers ':OK;' to a write whose value already")
        print("matches, without checking the key first. So 'ACCEPTED' here")
        print("means nothing, and no-op probing cannot identify the key on")
        print("this model. Ignore any result above.")
        print("")
        print("This is not a fault in your printer and nothing was changed.")
        return None
    if accepted:
        print("WRITE KEY: %s" % ", ".join(
            "%s (wire: %s)" % (w1, w) for w, w1 in accepted))
        print("")
        print("The dud key was correctly refused, so these are real results.")
        print("Post this on the thread along with the read key.")
    else:
        print("No candidate was accepted.")
        print("Either this model uses a write key not in the database, or")
        print("writes are disabled in firmware. Not a reason to guess.")
    return accepted


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
    ap.add_argument("--dump", action="store_true",
                    help="read a block of EEPROM with a known key and save "
                         "it to a file (read-only). Needs --key.")
    ap.add_argument("--key", type=lambda s: int(s, 0), default=None,
                    help="read key for --dump, e.g. --key 0x364A")
    ap.add_argument("--range", default="0-255", metavar="LO-HI",
                    help="address range for --dump (default 0-255)")
    ap.add_argument("--try-wkey", action="store_true",
                    help="identify the write key by writing a value back to "
                         "the address it was just read from (a no-op). "
                         "Needs --key.")
    ap.add_argument("--wkey-addr", type=int, default=47,
                    help="address for --try-wkey (default 47)")
    ap.add_argument("--all-wkeys", action="store_true",
                    help="with --try-wkey, also try keys from groups with a "
                         "different read key")
    args = ap.parse_args()

    if args.try_wkey and args.key is None:
        print("--try-wkey needs a key. Find it first, then pass it back:")
        print("    python find_key_usb.py --try-wkey --key 0x364A")
        return 1

    if args.try_wkey and args.raw:
        print("--try-wkey will not run on the raw pipe. Writes must go over")
        print("the D4 control channel.")
        return 1

    if args.dump and args.key is None:
        print("--dump needs a key. Run without --dump first to find it,")
        print("then pass it back, e.g.:")
        print("    python find_key_usb.py --dump --key 0x364A")
        return 1

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

    if args.try_wkey:
        with probe:
            try_wkeys(probe, args.key, args.wkey_addr, args.all_wkeys)
        return 0

    if args.dump:
        lo, hi = parse_range(args.range)
        with probe:
            dump_block(probe, args.key, lo, hi, which)
        return 0

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
