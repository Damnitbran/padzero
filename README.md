# Pad Zero

Read and reset the waste ink counter on Epson inkjet printers. Free, open
source, no paid tier.

---

## Read this first

**This will not empty your waste ink pads.**

Your printer keeps a counter estimating how much waste ink has soaked into
the absorbent pads inside it. There is no sensor. It's an estimate that
climbs every time the printer cleans its head, charges ink, powers on, or
prints borderless. When the estimate crosses a threshold, the printer stops
printing and tells you to contact Epson.

This tool sets that counter back to zero. That is the whole of what it does.

The ink is still in the pads. If they were genuinely saturated, resetting
means the printer keeps pumping ink into full foam, and eventually that ink
weeps out of the bottom onto whatever the printer is sitting on.

**Reset the counter to get printing again, then fix it properly.** Replace
the pad, or fit an external waste tank. Both are cheap and widely available.
Put something absorbent under the printer in the meantime.

Run `padzero --explain` and the tool will tell you the same thing.

---

## Install

Download `padzero.exe` from [Releases](../../releases). No installer, no
Python needed.

Windows will likely show **"Windows protected your PC"**. The binary is
unsigned, and counter-resetting is exactly the behaviour antivirus
heuristics look for. Click *More info*, then *Run anyway*. Or verify the
SHA-256 published with the release. Or build from source yourself.

## Use

```
padzero --list          list connected printers
padzero --info          model, key group, waste counters
padzero --dump          save a full EEPROM backup
padzero --reset         show what would change (writes nothing)
padzero --reset --yes   apply the reset
padzero --explain       what a reset does and does not fix
```

Typical session:

```
> padzero --info
==============================================================
  ET-4800
==============================================================
  serial     : X8GN172325
  key group  : 0x364a / b'Nbsjcbzb'
  coverage   : full - percentages and reset available

--- WASTE COUNTERS ---
  main_waste             :  79.85%  [###########################.......]
  borderless_waste       :  79.98%  [###########################.......]
  third_waste            :  80.00%  [###########################.......]

> padzero --reset --yes
```

Power-cycle the printer afterwards.

## Requirements

- Windows
- The **manufacturer's printer driver** installed. Windows' generic IPP
  class driver is enough to print but not enough to talk to the printer. If
  you skip this, the tool (and every other reset tool) will appear to hang.
- A **USB cable in the printer's USB port**. Not `LINE` or `EXT`, which are
  the fax telephone jacks.

Those two account for most "it doesn't work" reports.

## How it works

Epson permits the `||` factory commands over USB but blocks them on the
network interface. SNMP answers status queries and refuses EEPROM reads with
`:NA;`, and raw port 9100 accepts writes but never replies. So USB it is.

On Windows the bidirectional USB pipe is the `GUID_DEVINTERFACE_USBPRINT`
device interface, opened with `CreateFileW` and
`FILE_SHARE_READ|FILE_SHARE_WRITE`. Python's `open()` can't do it, because
it passes no share flags and the spooler already holds the device, so the
handle comes from `ctypes`.

[reinkpy](https://codeberg.org/atufi/reinkpy) layers IEEE 1284.4 (D4) on
top of that pipe and supplies per-model keys and reset addresses.
`models.json`, built from
[epson_print_conf](https://github.com/Ircama/epson_print_conf), adds the
dividers that turn raw bytes into percentages.

**No driver replacement required.** No Zadig, no WinUSB, no WSL, no admin.

## Model coverage

Neither upstream database covers every printer, so the tool reports what it
actually knows:

| Coverage | Meaning |
|---|---|
| `full` | percentages and reset both available |
| `partial` | reset available; raw byte values shown instead of percentages |
| `none` | read-only. The tool refuses to write to a model it doesn't know |

Verified on real hardware:

| Model | Key group | Coverage | Status |
|---|---|---|---|
| ET-4800 | `0x364A` | full | reset verified 79.85% to 0.00% |
| ET-4810 | `0x574B` | partial | detected and read |

`models.json` carries data for 110 models, but **listed is not the same as
verified**. If yours works, please open an issue and say so. That's how this
table grows.

## Safety

- Dry run is the default; writing needs `--yes`
- A full EEPROM dump is written to `dumps\` before any write, always
- Unknown models are read-only, with no override
- Every write is read back and verified

Writing wrong values to EEPROM can corrupt head alignment or model identity,
and there is no undo. Hence the rails. Please don't remove them in a fork.

## Adding your printer

If your model reports `coverage: none`:

```
padzero --dump
```

Open an issue with the resulting JSON and your exact model name. Coverage
grows from real hardware, never from guessing at similar-looking models. The
ET-4800 and ET-4810 differ by one digit and use entirely different keys.

## Build from source

```
pip install pyinstaller pywin32
pip install "reinkpy @ git+https://codeberg.org/atufi/reinkpy"

python -m PyInstaller --onefile --name padzero --console ^
  --add-data "models.json;." ^
  --add-data "reinkpy\reinkpy\epson.toml;reinkpy" ^
  --hidden-import reinkpy --hidden-import reinkpy.epson ^
  --hidden-import reinkpy.d4 padzero.py
```

`epson.toml` must land *inside* the `reinkpy` package directory, because
reinkpy loads it through `importlib.resources` rather than a relative path.

## Credits

Standing entirely on:

- [reinkpy](https://codeberg.org/atufi/reinkpy) for IEEE 1284.4 and the
  model database
- [epson_print_conf](https://github.com/Ircama/epson_print_conf) for waste
  counter parameters
- [ReInk](https://github.com/lion-simba/reink), the original work, roughly
  15 years ago

## Licence

AGPL-3.0-or-later. See [LICENSE](LICENSE).

## Disclaimer

Not affiliated with, authorised by, or endorsed by Seiko Epson Corporation.
"Epson" is used only to identify the printers this works with.

Using this may void your warranty. It writes to your printer's non-volatile
memory. It is provided with no warranty of any kind (see the licence). You
are responsible for what you do to your own hardware.
