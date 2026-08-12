#!/usr/bin/env python3
r"""
selftest.py - prove Pad Zero actually works, end to end.

Runs against whatever Epson is plugged in and checks every layer:
enumeration, D4 handshake, model identification, database lookup, EEPROM
reads, the write path, the reset planner, and the safety rails.

The write test is deliberately a no-op: it reads an address, writes the
value it already holds, and confirms the printer acknowledged and the
value reads back the same. That exercises the complete write path
(read key, caesar-shifted write key, D4 channel, ":OK;" response,
read-back verification) while leaving the printer byte-for-byte
unchanged. Nothing here modifies your printer.

Usage:  python selftest.py
"""
import os
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "reinkpy"))

import padzero as core

PASS, FAIL, SKIP = "PASS", "FAIL", "SKIP"
results = []


def check(name, fn):
    t0 = time.time()
    try:
        ok, detail = fn()
    except Exception as exc:
        ok, detail = False, "%s: %s" % (type(exc).__name__, exc)
    verdict = PASS if ok is True else (SKIP if ok is None else FAIL)
    elapsed = time.time() - t0
    results.append((verdict, name, detail, elapsed))
    print("  [%s] %-42s %s" % (verdict, name, detail))
    return ok


print("=" * 74)
print("PAD ZERO SELF TEST")
print("=" * 74)

state = {}

# ---------------------------------------------------------------- layer 1
print("\n-- Transport ---------------------------------------------------")


def t_enumerate():
    paths = core.list_usb_printers()
    state["paths"] = paths
    if not paths:
        return False, "no USB printer interfaces found"
    return True, "%d interface(s) via SetupAPI" % len(paths)


def t_open():
    for p in state.get("paths", []):
        try:
            with core.quiet():
                pr = core.Printer(p, core.load_models())
                if pr.model:
                    state["printer"] = pr
                    return True, "CreateFileW + D4 handshake OK"
        except Exception:
            continue
    return False, "no interface completed a D4 handshake"


check("Enumerate USB printer interfaces", t_enumerate)
check("Open device and negotiate IEEE 1284.4", t_open)

pr = state.get("printer")
if not pr:
    print("\nNo printer available. Remaining tests cannot run.")
    print("Check the cable is in the USB port (not LINE/EXT) and that")
    print("Epson's driver is installed.")
    sys.exit(1)

# ---------------------------------------------------------------- layer 2
print("\n-- Identification ----------------------------------------------")

check("Read device ID from the wire",
      lambda: (bool(pr.detected), "printer reports %r" % pr.detected))
check("Resolve to a known model",
      lambda: (bool(pr.has_specs), "matched %s" % pr.model))
check("Load per-model keys",
      lambda: (getattr(pr.ep.spec, "rkey", None) is not None,
               "read key %s, write key %r"
               % (hex(pr.ep.spec.rkey), pr.ep.spec.wkey)))
check("Read serial number",
      lambda: (bool(pr.serial), pr.serial or "unavailable"))


def t_db():
    db = core.load_models()
    if not db:
        return False, "models.json missing or empty"
    hit = pr.model in db
    return True, "%d models loaded, this one %s" % (
        len(db), "present" if hit else "absent (partial coverage)")


check("Load model database", t_db)

# ---------------------------------------------------------------- layer 3
print("\n-- Reading -----------------------------------------------------")


def t_read_one():
    v = pr.read([0]).get(0)
    state["addr0"] = v
    return v is not None, "EEPROM[0] = %s" % v


def t_read_repeat():
    a = pr.read([0]).get(0)
    b = pr.read([0]).get(0)
    return a == b and a is not None, "two reads agree (%s == %s)" % (a, b)


def t_read_many():
    addrs = [0, 1, 47, 48, 49, 54, 55]
    vals = pr.read(addrs)
    got = sum(1 for a in addrs if vals.get(a) is not None)
    return got == len(addrs), "%d/%d addresses returned a value" % (
        got, len(addrs))


def t_counters():
    c = pr.counters()
    state["counters"] = c
    if not c:
        return None, "model exposes no counter data"
    pcts = [x["percent"] for x in c if x.get("percent") is not None]
    if pcts:
        return True, "%d counter(s), highest %.2f%%" % (len(c), max(pcts))
    return True, "%d counter group(s), raw values only" % len(c)


def t_dump():
    d = pr.dump(0, 63)
    good = sum(1 for v in d.values() if v is not None)
    state["dump_ok"] = good
    return good == 64, "%d/64 addresses read in a block dump" % good


check("Read a single EEPROM address", t_read_one)
check("Repeated read is stable", t_read_repeat)
check("Read a batch of addresses", t_read_many)
check("Decode waste counters", t_counters)
check("Block dump 0-63", t_dump)

# ---------------------------------------------------------------- layer 4
print("\n-- Writing (no-op, changes nothing) ----------------------------")


def t_write_noop():
    """Write an address's existing value back to itself.

    Proves the write path works without altering the printer: same key,
    same caesar shift, same D4 channel, same ":OK;" handshake, same
    read-back verification as a real reset.
    """
    plan, _src = pr.reset_plan()
    if not plan:
        return None, "no reset map for this model"
    addr = plan[0][0]
    before = pr.read([addr]).get(addr)
    if before is None:
        return False, "could not read address %d first" % addr
    state["noop_addr"] = addr
    state["noop_val"] = before
    ok = pr.ep.write_eeprom((addr, before))
    after = pr.read([addr]).get(addr)
    if not ok:
        return False, "printer refused the write at %d" % addr
    if after != before:
        return False, "value changed! %s -> %s at %d" % (before, after, addr)
    return True, "wrote %s to addr %d, still %s" % (before, addr, after)


def t_plan():
    plan, src = pr.reset_plan()
    if not plan:
        return None, "no reset map for this model"
    cur = pr.read([a for a, _ in plan])
    changes = sum(1 for a, v in plan if cur.get(a) != v)
    return True, "%d addresses from %s, %d would change" % (
        len(plan), src, changes)


check("Write path (writes existing value back)", t_write_noop)
check("Reset planner", t_plan)

# ---------------------------------------------------------------- layer 5
print("\n-- Safety rails ------------------------------------------------")


def t_unknown_blocked():
    """An unrecognised model must be read-only."""
    fake = core.Printer.__new__(core.Printer)
    fake.models = {}
    fake.ep = pr.ep
    fake.io = pr.io
    fake.dev = pr.dev

    class NoSpec:
        model = None
    saved = pr.ep.spec
    try:
        fake.ep = type("E", (), {"spec": NoSpec(), "detected_model": None})()
        cov = core.Printer.coverage.fget(fake)
        return cov == "none", "unknown model reports coverage=%r" % cov
    finally:
        pr.ep.spec = saved


def t_backup_written():
    path = pr.save_dump(tag="selftest")
    if not os.path.exists(path):
        return False, "no file written"
    size = os.path.getsize(path)
    state["backup"] = path
    return size > 500, "%s (%d bytes)" % (os.path.basename(path), size)


def t_backup_valid():
    import json
    path = state.get("backup")
    if not path:
        return None, "no backup to check"
    with open(path, encoding="utf-8") as fh:
        data = json.load(fh)
    keys = {"model", "serial", "eeprom"}
    if not keys.issubset(data):
        return False, "missing keys: %s" % (keys - set(data))
    n = sum(1 for v in data["eeprom"].values() if v is not None)
    return n > 200, "valid JSON, %d addresses recorded" % n


check("Unknown model is read-only", t_unknown_blocked)
check("Backup file is written", t_backup_written)
check("Backup contains usable data", t_backup_valid)

# ---------------------------------------------------------------- summary
print("\n" + "=" * 74)
npass = sum(1 for r in results if r[0] == PASS)
nfail = sum(1 for r in results if r[0] == FAIL)
nskip = sum(1 for r in results if r[0] == SKIP)
total = time.time()

print("RESULT: %d passed, %d failed, %d skipped  (%d checks)"
      % (npass, nfail, nskip, len(results)))
if nfail:
    print("\nFailures:")
    for v, name, detail, _ in results:
        if v == FAIL:
            print("  %-44s %s" % (name, detail))
print("\nPrinter: %s  serial %s" % (pr.model, pr.serial))
if state.get("noop_val") is not None:
    print("Write test used address %d, value %s, unchanged."
          % (state["noop_addr"], state["noop_val"]))
print("=" * 74)

sys.exit(1 if nfail else 0)
