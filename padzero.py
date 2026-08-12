#!/usr/bin/env python3
r"""
padzero.py - read and reset Epson waste ink counters.

Free software. It will not actually replace your pads - see --explain.

How it works
------------
Epson permits the '||' factory commands over USB but blocks them on the
network interface (SNMP answers status queries and refuses EEPROM reads
with ":NA;"). On Windows the bidirectional USB pipe is the
GUID_DEVINTERFACE_USBPRINT device interface, opened with CreateFileW and
FILE_SHARE_READ|FILE_SHARE_WRITE. Python's open() cannot do this - it
passes no share flags and the spooler already holds the device - so the
handle comes from ctypes.

reinkpy layers IEEE 1284.4 (D4) on top of that pipe and supplies the
per-model keys and reset addresses. models.json (built by
build_modeldb.py from epson_print_conf) adds the dividers needed to turn
raw bytes into percentages.

Neither source covers every printer, so coverage is reported honestly:

    specs + dividers  -> percentages and reset
    specs only        -> raw values and reset, no percentages
    neither           -> read-only, refuses to write

Safety
------
* dry run is the default; writing requires --yes
* a full EEPROM dump is written to disk before any write, always
* unknown models cannot be written to at all
* every write is read back and verified

SPDX-License-Identifier: AGPL-3.0-or-later
"""
import argparse
import contextlib
import io
import json
import logging
import os
import sys
from datetime import datetime

HERE = os.path.dirname(os.path.abspath(__file__))

# Frozen builds unpack read-only data into a temp dir (sys._MEIPASS) while
# anything we WRITE has to live next to the .exe, not in the temp dir that
# disappears on exit.
if getattr(sys, "frozen", False):
    BUNDLE = sys._MEIPASS
    APPDIR = os.path.dirname(sys.executable)
else:
    BUNDLE = HERE
    APPDIR = HERE
    sys.path.insert(0, os.path.join(HERE, "reinkpy"))

# reinkpy narrates every D4 handshake at INFO. Useful when debugging,
# noise for everyone else. -v puts it back.
logging.basicConfig(level=logging.CRITICAL)
for _n in ("reinkpy", "reinkpy.d4", "reinkpy.epson", "reinkpy.usb"):
    # CRITICAL, not ERROR: reinkpy logs a full traceback at ERROR when a
    # non-control interface fails to negotiate D4, which is expected and
    # not worth showing.
    logging.getLogger(_n).setLevel(logging.CRITICAL)


@contextlib.contextmanager
def quiet():
    """Swallow output from probes that are expected to fail.

    A composite Epson exposes several USB printer interfaces; only the
    printer one speaks D4. Probing the fax interface raises deep inside
    reinkpy's channel setup, which is fine - we just don't want the
    traceback on screen.
    """
    buf = io.StringIO()
    with contextlib.redirect_stderr(buf), contextlib.redirect_stdout(buf):
        yield buf

from usb_direct import UsbPrinter, list_usb_printers

MODELS_JSON = os.path.join(BUNDLE, "models.json")
DUMP_DIR = os.path.join(APPDIR, "dumps")


# --------------------------------------------------------------- transport
class WinUsbPrintIO:
    """reinkpy-shaped transport over the Windows USB printer interface."""

    def __init__(self, path):
        self.path = path
        self._dev = None
        self._nctx = 0

    @property
    def info(self):
        return {"file_path": self.path, "transport": "winusbprint"}

    def __enter__(self):
        if self._nctx == 0:
            self._dev = UsbPrinter(self.path)
        self._nctx += 1
        return self

    def __exit__(self, *exc):
        self._nctx -= 1
        if self._nctx == 0 and self._dev:
            self._dev.close()
            self._dev = None

    def write(self, data):
        return self._dev.write(bytes(data))

    def read(self, size=None):
        try:
            return self._dev.read(size or 4096)
        except OSError:
            return b""

    def __str__(self):
        return "usb"

    def __repr__(self):
        return "WinUsbPrintIO(%r)" % self.path


def load_models():
    if not os.path.exists(MODELS_JSON):
        return {}
    with open(MODELS_JSON, encoding="utf-8") as fh:
        return json.load(fh)


# ----------------------------------------------------------------- printer
class Printer:
    def __init__(self, path, models):
        import reinkpy
        self.path = path
        self.io = WinUsbPrintIO(path)
        self.dev = reinkpy.UsbDevice(self.io)
        self.ep = self.dev.epson
        self.models = models

    @property
    def model(self):
        return getattr(self.ep.spec, "model", None) or self.ep.detected_model

    @property
    def detected(self):
        return self.ep.detected_model

    @property
    def serial(self):
        return self.dev.serial_number

    @property
    def has_specs(self):
        return bool(getattr(self.ep.spec, "model", None))

    @property
    def extra(self):
        """models.json entry, if this model is covered there."""
        return self.models.get(self.model or "", {})

    @property
    def coverage(self):
        if not self.has_specs:
            return "none"
        return "full" if self.extra.get("waste") else "partial"

    # -- reading ----------------------------------------------------------
    def read(self, addrs):
        return dict(self.ep.read_eeprom(*addrs))

    def counters(self):
        """
        Percentages where a divider is known, otherwise raw byte values.
        Returns a list of dicts so the caller can render either shape.
        """
        out = []
        waste = self.extra.get("waste")
        if waste:
            for name, cfg in waste.items():
                vals = self.read(cfg["oids"])
                b = [vals.get(a) for a in cfg["oids"]]
                if any(v is None for v in b):
                    out.append({"name": name, "error": "read failed"})
                    continue
                raw = int("".join("%02X" % v for v in reversed(b)), 16)
                div = cfg.get("divider")
                out.append({"name": name, "bytes": b, "raw": raw,
                            "percent": round(raw / div, 2) if div else None})
            return out

        # no divider data - report the raw bytes reinkpy would reset
        for m in getattr(self.ep.spec, "mem", []) or []:
            addrs = list(m.get("addr", []))
            if not addrs:
                continue
            vals = self.read(addrs)
            out.append({"name": m.get("desc") or "counters",
                        "addrs": addrs,
                        "values": [vals.get(a) for a in addrs],
                        "percent": None})
        return out

    def dump(self, first=0, last=255):
        return self.read(range(first, last + 1))

    def save_dump(self, tag=""):
        os.makedirs(DUMP_DIR, exist_ok=True)
        stamp = datetime.now().strftime("%Y-%m-%d_%H%M%S")
        name = "%s_%s%s.json" % (self.model or "unknown", stamp,
                                 ("_" + tag) if tag else "")
        path = os.path.join(DUMP_DIR, name)
        data = {"model": self.model, "detected": self.detected,
                "serial": self.serial, "timestamp": stamp,
                "eeprom": {str(k): v for k, v in self.dump().items()}}
        with open(path, "w", encoding="utf-8") as fh:
            json.dump(data, fh, indent=1)
        return path

    # -- reset plan -------------------------------------------------------
    def reset_plan(self):
        """
        [(addr, value), ...] to apply. models.json's verified map wins;
        otherwise fall back to reinkpy's per-model mem entries.
        """
        raw = self.extra.get("raw_waste_reset")
        if raw:
            return sorted((int(k), v) for k, v in raw.items()), "models.json"

        plan = {}
        for m in getattr(self.ep.spec, "mem", []) or []:
            addrs = list(m.get("addr", []))
            vals = list(m.get("reset") or m.get("min") or [0] * len(addrs))
            for a, v in zip(addrs, vals):
                plan[a] = v
        return sorted(plan.items()), "reinkpy specs"

    def apply(self, plan):
        ok = True
        for addr, value in plan:
            good = self.ep.write_eeprom((addr, value))
            print("    %3d -> %-3d  %s" % (addr, value, "OK" if good else "FAILED"))
            ok = ok and bool(good)
        return ok


# ------------------------------------------------------------------- views
def bar(pct, width=34):
    filled = max(0, min(int(round(pct / 100 * width)), width))
    return "#" * filled + "." * (width - filled)


def show_counters(rows):
    if not rows:
        print("  (no counter information for this model)")
        return
    for r in rows:
        if r.get("error"):
            print("  %-22s : %s" % (r["name"], r["error"]))
        elif r.get("percent") is not None:
            p = r["percent"]
            flag = "  FULL" if p >= 100 else ("  near full" if p >= 90 else "")
            print("  %-22s : %6.2f%%  [%s]%s" % (r["name"], p, bar(p), flag))
        elif "values" in r:
            pairs = ", ".join("%d=%s" % (a, v)
                              for a, v in zip(r["addrs"], r["values"]))
            print("  %-22s : %s" % (r["name"], pairs))
        else:
            print("  %-22s : raw %s" % (r["name"], r.get("raw")))


def show_before_after(before, after):
    """Print each counter's old and new value side by side.

    This is the proof that the reset did something, so it is worth showing
    plainly rather than making someone compare two separate readouts.
    """
    if not after:
        print("  (no counter information for this model)")
        return

    old = {}
    for r in (before or []):
        if r.get("percent") is not None:
            old[r["name"]] = ("pct", r["percent"])
        elif "values" in r:
            old[r["name"]] = ("raw", list(r["values"]))

    for r in after:
        name = r["name"]
        if r.get("error"):
            print("  %-22s : %s" % (name, r["error"]))
            continue

        if r.get("percent") is not None:
            was = old.get(name)
            if was and was[0] == "pct":
                arrow = "->" if abs(was[1] - r["percent"]) > 0.005 else "= "
                print("  %-22s : %6.2f%%  %s  %6.2f%%"
                      % (name, was[1], arrow, r["percent"]))
            else:
                print("  %-22s : %6.2f%%" % (name, r["percent"]))
            continue

        if "values" in r:
            was = old.get(name)
            if was and was[0] == "raw":
                pairs = []
                for a, o, n in zip(r["addrs"], was[1], r["values"]):
                    pairs.append("%d:%s%s" % (a, o, "" if o == n else "->%s" % n))
                print("  %-22s : %s" % (name, "  ".join(pairs)))
            else:
                print("  %-22s : %s" % (name, ", ".join(
                    "%d=%s" % (a, v) for a, v in zip(r["addrs"], r["values"]))))


EXPLAIN = """
What this tool does, and what it does not

  Your printer keeps a counter estimating how much waste ink has gone into
  the absorbent pads inside it. There is no sensor. It is an estimate that
  goes up every time the printer cleans its head, charges ink, powers on,
  or prints borderless.

  When that estimate crosses a threshold the printer refuses to print and
  tells you to contact Epson.

  This tool sets the counter back to zero. That is all it does.

  It does NOT empty the pads. The ink is still in there. If the pads were
  genuinely saturated, resetting the counter means the printer will keep
  pumping ink into full foam, and eventually that ink comes out of the
  bottom of the printer onto whatever it is sitting on.

  The real fix is replacing the pad or fitting an external waste tank.
  Reset the counter to get printing again, then fix it properly.

  Put something absorbent under the printer in the meantime.
"""


# -------------------------------------------------------------------- main
def main():
    ap = argparse.ArgumentParser(
        description="Read and reset Epson waste ink counters (free software)",
        epilog="Reading is safe. --reset --yes permanently modifies printer memory.")
    ap.add_argument("-l", "--list", action="store_true", help="list connected printers")
    ap.add_argument("-d", "--device", type=int, default=0, help="which printer (default 0)")
    ap.add_argument("-i", "--info", action="store_true", help="model and counters (safe)")
    ap.add_argument("--dump", action="store_true", help="save a full EEPROM dump (safe)")
    ap.add_argument("--reset", action="store_true", help="reset the waste counters")
    ap.add_argument("--yes", action="store_true", help="required to actually write")
    ap.add_argument("--explain", action="store_true", help="what a reset does and does not fix")
    ap.add_argument("-v", "--verbose", action="store_true", help="show protocol logging")
    args = ap.parse_args()

    if args.verbose:
        for _n in ("reinkpy", "reinkpy.d4", "reinkpy.epson"):
            logging.getLogger(_n).setLevel(logging.INFO)

    if args.explain:
        print(EXPLAIN)
        return 0
    if not (args.list or args.info or args.dump or args.reset):
        args.info = True

    models = load_models()
    paths = list_usb_printers()
    if not paths:
        print("No USB printer found.")
        print("  * check the cable is in the printer's USB port, not LINE or EXT")
        print("    (those are the fax phone jacks and fit nothing useful)")
        print("  * install the manufacturer's driver - Windows' generic IPP")
        print("    driver is enough to print but not enough to talk to the printer")
        return 1

    if args.list:
        print("Connected printers:")
        for i, p in enumerate(paths):
            try:
                with quiet():
                    pr = Printer(p, models)
                    model, serial, cov = pr.model, pr.serial, pr.coverage
            except Exception:
                model = None
            if model:
                print("  [%d] %-14s sn:%-20s coverage:%s"
                      % (i, model, serial or "?", cov))
            else:
                print("  [%d] (not a control interface - skipped)" % i)
        return 0

    if args.device >= len(paths):
        print("No printer at index %d (found %d)." % (args.device, len(paths)))
        return 1

    pr = Printer(paths[args.device], models)

    print("=" * 62)
    print("  %s" % (pr.model or "UNKNOWN MODEL"))
    print("=" * 62)
    print("  serial     : %s" % (pr.serial or "?"))
    print("  presents as: %s" % (pr.detected or "?"))
    rk = getattr(pr.ep.spec, "rkey", None)
    print("  key group  : %s / %r" % (hex(rk) if rk else "?",
                                      getattr(pr.ep.spec, "wkey", None)))
    cov = {"full": "full - percentages and reset available",
           "partial": "partial - reset available, no percentage data",
           "none": "NONE - this model is not in either database"}[pr.coverage]
    print("  coverage   : %s" % cov)

    if pr.coverage == "none":
        print("\n  Refusing to write to an unrecognised model.")
        print("  Reading is still safe - run --dump and open an issue with")
        print("  the file so this printer can be added properly.")

    before = None
    if args.info or args.reset:
        print("\n--- WASTE COUNTERS ---")
        before = pr.counters()
        show_counters(before)

    if args.dump:
        path = pr.save_dump()
        print("\nEEPROM dump -> %s" % path)

    if args.reset:
        print("\n--- RESET ---")
        if pr.coverage == "none":
            print("  Blocked: unknown model.")
            return 1

        plan, source = pr.reset_plan()
        if not plan:
            print("  No reset map known for this model. Blocked.")
            return 1

        print("  plan from %s, %d addresses" % (source, len(plan)))
        current = pr.read([a for a, _ in plan])
        changes = [(a, current.get(a), v) for a, v in plan if current.get(a) != v]
        for a, was, will in [(a, current.get(a), v) for a, v in plan]:
            mark = " " if was == will else "*"
            print("   %s %3d : %-4s -> %s" % (mark, a, was, will))
        print("  %d of %d addresses would change" % (len(changes), len(plan)))

        if not args.yes:
            print("\n  Dry run. Nothing was written. Add --yes to apply.")
            return 0

        path = pr.save_dump(tag="pre-reset")
        print("\n  backup -> %s" % path)
        print("  writing...")
        ok = pr.apply(plan)
        print("\n  Reset %s" % ("complete" if ok else "had FAILURES - see above"))

        print("\n--- BEFORE AND AFTER ---")
        show_before_after(before, pr.counters())
        print("\n  Power-cycle the printer for this to take effect.")
        print("  Remember: the pads are exactly as full as they were.")
        print("  Run --explain if that needs unpacking.")

    return 0


if __name__ == "__main__":
    sys.exit(main())
