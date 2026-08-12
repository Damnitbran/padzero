"""
build_modeldb.py - extract waste-counter metadata into a standalone JSON file.

reinkpy knows which EEPROM addresses to reset for ~170 key groups, but not
how to turn raw bytes into a percentage. epson_print_conf knows the waste
OIDs and dividers for ~100 models, but covers fewer models overall.

This pulls epson_print_conf's per-model waste data out into models.json so
the tool can show real percentages where they're known, and fall back to
raw byte values where they aren't. Keeping it as data rather than code
means new models can be contributed without touching Python.

Run once; re-run when the upstream databases are updated.
"""
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "epson_print_conf"))

import epson_print_conf

cfg = epson_print_conf.EpsonPrinter.PRINTER_CONFIG

WASTE_KEYS = ("main_waste", "borderless_waste", "first_waste",
              "second_waste", "third_waste", "fourth_waste")

out = {}
alias_count = 0

for model, parm in cfg.items():
    entry = {}

    if "read_key" in parm:
        entry["read_key"] = parm["read_key"]
    if "write_key" in parm:
        wk = parm["write_key"]
        entry["write_key"] = wk.decode("latin-1") if isinstance(wk, bytes) else wk

    waste = {}
    for k in WASTE_KEYS:
        if k in parm and isinstance(parm[k], dict) and "oids" in parm[k]:
            waste[k] = {"oids": list(parm[k]["oids"]),
                        "divider": parm[k].get("divider")}
    if waste:
        entry["waste"] = waste

    if "raw_waste_reset" in parm:
        entry["raw_waste_reset"] = {str(k): v
                                    for k, v in parm["raw_waste_reset"].items()}

    if "stats" in parm:
        entry["stats"] = {k: list(v) for k, v in parm["stats"].items()
                          if isinstance(v, (list, tuple))}

    if not entry:
        continue

    out[model] = entry

    # fan aliases out to full entries so lookup is a single dict hit
    for alias in parm.get("alias", []) or []:
        if alias not in out:
            out[alias] = dict(entry, _alias_of=model)
            alias_count += 1

path = os.path.join(HERE, "models.json")
with open(path, "w", encoding="utf-8") as fh:
    json.dump(out, fh, indent=1, sort_keys=True)

with_waste = sum(1 for v in out.values() if "waste" in v)
with_reset = sum(1 for v in out.values() if "raw_waste_reset" in v)

print("models.json written to %s" % path)
print("  %d models total (%d of them aliases)" % (len(out), alias_count))
print("  %d with waste levels (dividers)" % with_waste)
print("  %d with an explicit reset map" % with_reset)

for probe in ("ET-4800", "ET-4810", "ET-2800", "ET-2850", "L3550"):
    e = out.get(probe)
    if not e:
        print("  %-10s : ABSENT" % probe)
    else:
        print("  %-10s : waste=%s reset=%s" % (
            probe, "yes" if "waste" in e else "no",
            "yes" if "raw_waste_reset" in e else "no"))
