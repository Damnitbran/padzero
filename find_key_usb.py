"""
find_key_usb.py - locate an unknown Epson model's EEPROM read key over USB.

This is the USB counterpart to find_key.py. find_key.py talks over SNMP /
Wi-Fi Direct, but these Epsons refuse the '||' factory commands on the
network (":NA;") and only answer them over USB. So for a model that isn't
in the databases, the network brute-forcer will report NA no matter what
the key is - it has to be done over the USB cable.

How it tells a wrong key from a right one:
  * wrong key  -> the printer replies ":NA;" (not available)
  * right key  -> the printer replies "EE:AAAAVV" (address echo + value)
So we sweep candidate keys and stop at the first that yields an EE: payload.

Two modes:
  (default)  try the ~170 read keys already known from the reinkpy and
             epson_print_conf databases - about a minute. If the model is
             simply mis-/un-catalogued but reuses a sibling's key, this
             finds it.
  --full     sweep the whole 16-bit key space 0x0000-0xFFFF (roughly an
             hour, resumable with --start).

Read-only: only ever sends read ('A') commands. Never writes EEPROM.

Requirements: the genuine Epson driver installed (not the generic Windows
"IPP Class Driver"), and a USB cable. No pysnmp, no Wi-Fi needed.
"""
import argparse
import re
import struct
import sys
import time

from usb_direct import list_usb_printers, UsbPrinter, factory, wrap, exchange

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


def probe(dev, rkey, addr):
    """Send one read with `rkey`. Return ('hit', payload) / ('na', None) /
    ('empty', None) / ('other', text)."""
    cmd = wrap(factory("A", struct.pack("<H", addr), rkey=rkey))
    reply = exchange(dev, cmd, want=b"EE:")
    if not reply:
        return "empty", None
    txt = reply.decode("ascii", "replace")
    m = re.search(r"EE:([0-9A-Fa-f]{6})", txt)
    if m:
        return "hit", m.group(1)
    if ":NA;" in txt:
        return "na", None
    return "other", txt.strip()[:60]


def pick_printer(index):
    try:
        paths = list_usb_printers()
    except OSError as e:
        print("SetupAPI enumeration failed: %s" % e)
        return None
    if not paths:
        print("No USB printers found. Is the cable connected and the")
        print("genuine Epson driver installed (not the IPP Class Driver)?")
        return None
    print("USB printer interfaces:")
    for i, p in enumerate(paths):
        print("  [%d] %s" % (i, p))
    if index >= len(paths):
        print("\nNo interface at index %d." % index)
        return None
    print("\nOpening [%d] ..." % index)
    try:
        dev = UsbPrinter(paths[index])
    except OSError as e:
        print("CreateFile failed: %s" % e)
        print("(The spooler may hold the device. Close other printer apps.)")
        return None
    return dev


def main():
    ap = argparse.ArgumentParser(
        description="Find an Epson EEPROM read key over USB")
    ap.add_argument("-d", "--device", type=int, default=0,
                    help="index of the USB printer interface (default 0)")
    ap.add_argument("--addr", type=int, default=0,
                    help="EEPROM address to probe (default 0)")
    ap.add_argument("--full", action="store_true",
                    help="sweep all 65536 keys instead of the known list")
    ap.add_argument("--start", type=lambda s: int(s, 0), default=0,
                    help="with --full, resume from this key")
    args = ap.parse_args()

    dev = pick_printer(args.device)
    if dev is None:
        return 1

    keys = range(args.start, 0x10000) if args.full else KNOWN_KEYS
    total = (0x10000 - args.start) if args.full else len(keys)

    print("=" * 62)
    print("USB READ KEY SEARCH   addr %d" % args.addr)
    print("mode: %s   candidates: %d"
          % ("FULL SWEEP" if args.full else "known keys", total))
    print("=" * 62)

    with dev:
        hits = []
        na_count = 0
        empty_count = 0
        t0 = time.time()
        for i, rkey in enumerate(keys):
            kind, data = probe(dev, rkey, args.addr)
            if kind == "hit":
                print("\n*** HIT ***  read_key = 0x%04X  ->  EE:%s" % (rkey, data))
                print("    address 0x%s  value 0x%s (%d)"
                      % (data[:4], data[4:], int(data[4:], 16)))
                hits.append(rkey)
                if not args.full:
                    break
            elif kind == "na":
                na_count += 1
            elif kind == "empty":
                empty_count += 1

            if args.full and i and i % 250 == 0:
                el = time.time() - t0
                rate = i / el if el else 0
                left = (total - i) / rate if rate else 0
                print("  %6d/%d  %.0f keys/s  ~%.0f min left  (last 0x%04X)"
                      % (i, total, rate, left / 60, rkey))
            elif not args.full and i and i % 25 == 0:
                print("  tried %d/%d ..." % (i, total))

        print("\n" + "=" * 62)
        if hits:
            print("FOUND %d working key(s): %s"
                  % (len(hits), ", ".join("0x%04X" % k for k in hits)))
            print("\nPost this key on the thread so the model can be added.")
        elif empty_count and empty_count >= na_count:
            print("The printer never replied (%d empty reads)." % empty_count)
            print("USB comms look dead - wrong device index, or the stock")
            print("Epson driver isn't installed. This is NOT a key result.")
        else:
            print("NO WORKING KEY FOUND among %d candidates (%d refused)."
                  % (total, na_count))
            if args.full:
                print("The full 16-bit space is exhausted -> the EEPROM read")
                print("command is disabled in firmware on this unit.")
            else:
                print("Not conclusive. Re-run with --full for the whole key")
                print("space (about an hour) before concluding lockout.")
        print("Elapsed: %.1f s" % (time.time() - t0))
        print("=" * 62)
    return 0


if __name__ == "__main__":
    sys.exit(main())
