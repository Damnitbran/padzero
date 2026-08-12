"""
find_key.py - locate the ET-4800's EEPROM read key.

Every EEPROM read so far comes back as "||:41:NA;" (not available).
That is either a wrong read_key or a firmware lockout. This tells us
which, by trying keys and watching for an "EE:" payload.

Two modes:
  (default)  try the 170 distinct read keys known from reinkpy's
             database plus epson_print_conf's - fast, ~1 minute.
             If the ET-4800 is simply mis-catalogued, this finds it.
  --full     sweep the entire 16-bit key space, 0x0000-0xFFFF.
             Slow (roughly an hour), resumable via --start.

A hit prints the key and the decoded value. If nothing hits in --full,
the command is disabled in firmware, not mis-keyed.

Read-only: only ever sends read ('A') commands.
"""
import argparse
import asyncio
import re
import struct
import sys
import time

try:
    asyncio.get_event_loop()
except RuntimeError:
    asyncio.set_event_loop(asyncio.new_event_loop())

from pysnmp.hlapi.v1arch import (
    SnmpDispatcher, CommunityData, UdpTransportTarget,
    ObjectType, ObjectIdentity, get_cmd,
)

BASE = "1.3.6.1.4.1.1248.1.2.2.44.1.1.2.1"

# Distinct read keys harvested from reinkpy/reinkpy/epson.toml (rkey) and
# epson_print_conf's printer dictionary (read_key). 0x364A is the value both
# databases claim for the ET-4800 - included so the run is self-checking.
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


def build_read_oid(rkey: int, addr: int = 0) -> str:
    c = 0x41  # 'A' = read
    payload = struct.pack("<HBBB", rkey, c, ~c & 0xFF,
                          (c >> 1 & 0x7F) | (c << 7 & 0x80))
    payload += struct.pack("<H", addr)
    msg = b"||" + struct.pack("<H", len(payload)) + payload
    return BASE + "." + ".".join(str(b) for b in msg)


def main():
    ap = argparse.ArgumentParser(description="Find the ET-4800 EEPROM read key")
    ap.add_argument("-a", "--address", default="192.168.223.1")
    ap.add_argument("-c", "--community", default="public")
    ap.add_argument("--addr", type=int, default=0, help="EEPROM address to probe")
    ap.add_argument("--full", action="store_true",
                    help="sweep all 65536 keys instead of the known list")
    ap.add_argument("--start", type=lambda s: int(s, 0), default=0,
                    help="with --full, resume from this key")
    ap.add_argument("-t", "--timeout", type=float, default=2.0)
    args = ap.parse_args()

    loop = asyncio.get_event_loop()
    dispatcher = SnmpDispatcher()
    auth = CommunityData(args.community, mpModel=0)
    transport = loop.run_until_complete(
        UdpTransportTarget.create((args.address, 161),
                                  timeout=args.timeout, retries=0)
    )

    def probe(rkey):
        oid = build_read_oid(rkey, args.addr)

        async def _run():
            return await get_cmd(dispatcher, auth, transport,
                                 ObjectType(ObjectIdentity(oid)))
        try:
            errInd, errStat, errIdx, vbs = loop.run_until_complete(_run())
        except Exception:
            return None
        if errInd or (errStat and int(errStat) != 0):
            return None
        for _n, v in vbs:
            try:
                return v.asOctets()
            except AttributeError:
                return None
        return None

    keys = range(args.start, 0x10000) if args.full else KNOWN_KEYS
    total = len(keys) if not args.full else 0x10000 - args.start

    print("=" * 62)
    print("READ KEY SEARCH -> %s   addr %d" % (args.address, args.addr))
    print("mode: %s   candidates: %d" % ("FULL SWEEP" if args.full else "known keys", total))
    print("=" * 62)

    # sanity: confirm the control channel is alive before trusting failures
    probe_status = probe(0x364A)
    if probe_status is None:
        print("\n!! No reply at all on the control channel.")
        print("   Are you connected to the printer's Wi-Fi Direct network?")
        return 1
    print("Control channel alive. Baseline reply: %r\n" % probe_status[:24])

    hits = []
    t0 = time.time()
    for i, rkey in enumerate(keys):
        resp = probe(rkey)
        if resp:
            txt = resp.decode("ascii", "replace")
            if "EE:" in txt:
                m = re.search(r"EE:([0-9A-Fa-f]{6})", txt)
                print("\n*** HIT ***  read_key = 0x%04X  -> %s" % (rkey, txt.strip()))
                if m:
                    payload = m.group(1)
                    print("    address %s  value 0x%s (%d)"
                          % (payload[:4], payload[4:], int(payload[4:], 16)))
                hits.append(rkey)
                if not args.full:
                    break

        if i % 250 == 0 and i:
            el = time.time() - t0
            rate = i / el if el else 0
            left = (total - i) / rate if rate else 0
            print("  %6d/%d  %.0f keys/s  ~%.0f min left  (last 0x%04X)"
                  % (i, total, rate, left / 60, rkey))
        elif not args.full and i % 25 == 0:
            print("  tried %d/%d ..." % (i, total))

    print("\n" + "=" * 62)
    if hits:
        print("FOUND %d working key(s): %s"
              % (len(hits), ", ".join("0x%04X" % k for k in hits)))
    else:
        print("NO WORKING KEY FOUND among %d candidates." % total)
        if args.full:
            print("The full 16-bit space is exhausted -> the EEPROM read")
            print("command is DISABLED IN FIRMWARE on this unit.")
        else:
            print("Not conclusive yet. Re-run with --full for the whole")
            print("key space (about an hour) before concluding lockout.")
    print("Elapsed: %.1f s" % (time.time() - t0))
    print("=" * 62)
    return 0


if __name__ == "__main__":
    sys.exit(main())
