**Pad Zero now has a window.** Double-click and go, no command line needed.

New here? Read the [Quick start guide](../../blob/main/QUICKSTART.md). It
assumes you know nothing technical and takes about five minutes.

## Read this first

**This does not empty your waste ink pads.** It resets the counter that
tracks them. The ink is still in the foam. If the pads are genuinely
saturated, a reset means the printer keeps pumping ink into full foam and
eventually it weeps out of the bottom.

Reset to get printing again, then replace the pad or fit a waste tank. Put
something absorbent under the printer meanwhile.

## Download

| File | Who it's for |
|---|---|
| **PadZero.exe** | Everyone. Double-click, a window opens. 13.6 MB |
| `padzero-cli.exe` | Command line, for people who want one. 10.6 MB |

No installer, no Python, nothing to set up.

    PadZero.exe      887F88D2DE6878174CCD2F5637E271368E81BD8D9E683A241BB0BEBD202C3E7E
    padzero-cli.exe  C409C59D346A1334F01E59F96D803CB8A53A8D1F6BD0581A22D78A68DC53FCC0

Verify before running:

    certutil -hashfile PadZero.exe SHA256

**Windows will warn you.** The binaries are unsigned, and resetting counters
is exactly what antivirus heuristics look for. You'll see "Windows protected
your PC". Click *More info*, then *Run anyway*. Or check the hash above. Or
build it yourself from source.

## Before and after

After a reset, both the window and the CLI show what each counter was and
what it is now, so you can see it worked rather than taking it on trust:

    main_waste             :  79.85%  ->    0.00%
    borderless_waste       :  79.98%  ->    0.00%
    third_waste            :  80.00%  ->    0.00%

Models that report raw values instead of percentages mark the addresses that
changed:

    Platen pad counters    : 28:0  47:0  50:0  51:0  55:94  252:25->0  253:0

## What's new in this release

- **Window front end.** Coloured status (green / amber / red), a plain
  English verdict, a bar per counter, and one button.
- **Troubleshooting built in.** If no printer is found, the window shows the
  two things that are almost always responsible, with instructions, rather
  than an error message.
- **Automatic backup** before any change, in both the window and the CLI.
- **Technical details are hidden by default** behind a panel that starts
  closed. Key groups and EEPROM addresses are there when you want them.
- **Quick start guide** written for people who have never heard of an EEPROM.
- CLI renamed to `padzero-cli.exe` so it can't be confused with the window
  version.

## Two things that cause most failures

1. **Install Epson's own printer driver.** Windows' generic driver is enough
   to print but not enough to talk to the printer. Without it, this and every
   other reset tool will say it can't find your printer.
2. **Plug USB into the printer's USB port**, not `LINE` or `EXT`, which are
   the fax telephone jacks.

Don't accept firmware updates while you're on Epson's site. Epson has
shipped firmware that permanently blocks resets, and it can't be rolled back.

## Verified hardware

| Model | Key group | Coverage | Status |
|---|---|---|---|
| ET-4800 | `0x364A` | full | reset verified 79.85% to 0.00% |
| ET-4810 | `0x574B` | partial | detected and read |

`models.json` carries data for 110 models, but listed is not verified. If
yours works, please open an issue. That's how the table grows. If it reports
`coverage: none`, click **Save a backup** and attach the file.

## Safety

Unknown models are read-only with no override. A full backup is written
before any change. Every write is read back and verified. The CLI defaults to
a dry run.

## Credits

Standing on [reinkpy](https://codeberg.org/atufi/reinkpy),
[epson_print_conf](https://github.com/Ircama/epson_print_conf), and
[ReInk](https://github.com/lion-simba/reink).

AGPL-3.0-or-later. Not affiliated with Seiko Epson Corporation.
