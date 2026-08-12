First release.

Reads and resets the waste ink counter on Epson inkjet printers over USB on
Windows. No driver replacement — no Zadig, no WinUSB, no WSL, no admin.

## Read this first

**This does not empty your waste ink pads.** It resets the counter that
tracks them. The ink is still in the foam. If the pads are genuinely
saturated, a reset means the printer keeps pumping ink into full foam and
eventually it weeps out of the bottom.

Reset to get printing again, then replace the pad or fit a waste tank. Put
something absorbent under the printer meanwhile. `padzero --explain` says
the same thing.

## Download

`padzero.exe` — 10.6 MB, single file, no Python needed.

    SHA-256  39162ED5E39E0877439801E7987854E4F16112289E289DE4FD9D093426AC915F

Verify before running:

    certutil -hashfile padzero.exe SHA256

**Windows will warn you.** The binary is unsigned, and resetting counters is
exactly what antivirus heuristics look for. You'll see "Windows protected
your PC" — *More info* → *Run anyway*, or verify the hash above, or build it
yourself from source.

## Usage

    padzero --list          list connected printers
    padzero --info          model, key group, waste counters
    padzero --dump          save a full EEPROM backup
    padzero --reset         show what would change (writes nothing)
    padzero --reset --yes   apply it
    padzero --explain       what a reset does and does not fix

Power-cycle the printer afterwards.

## Two things that cause most failures

1. **Install the manufacturer's printer driver.** Windows' generic IPP class
   driver is enough to print but not enough to talk to the printer. Without
   it, this and every other reset tool will appear to hang.
2. **Plug USB into the printer's USB port** — not `LINE` or `EXT`, which are
   the fax telephone jacks.

## Verified hardware

| Model | Key group | Coverage | Status |
|---|---|---|---|
| ET-4800 | `0x364A` | full | reset verified 79.85% → 0.00% |
| ET-4810 | `0x574B` | partial | detected and read |

`models.json` carries data for 110 models, but listed is not verified. If
yours works, please open an issue — that's how the table grows. If it
reports `coverage: none`, run `padzero --dump` and attach the JSON.

## Safety

Dry run is the default. A full EEPROM dump is written to `dumps\` before any
write. Unknown models are read-only with no override. Every write is read
back and verified.

## Credits

Standing on [reinkpy](https://codeberg.org/atufi/reinkpy),
[epson_print_conf](https://github.com/Ircama/epson_print_conf), and
[ReInk](https://github.com/lion-simba/reink).

AGPL-3.0-or-later. Not affiliated with Seiko Epson Corporation.
