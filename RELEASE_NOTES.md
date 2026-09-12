## Just want it working? Download **PadZero.zip**

Unzip it, double-click `PadZero.exe`, a window opens. Done. No install, no
Python, nothing to set up. A short README is in the zip too.

The zip is there because Chrome and Edge make you click through several
warnings to download a bare `.exe`. If your browser doesn't mind, plain
`PadZero.exe` is right there as well.

(`padzero-cli.exe` is the same tool for the command line. If you're not sure
you want it, you don't.)

---

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
| **PadZero.zip** | Everyone. Unzip, double-click. Avoids browser warnings. 12.6 MB |
| PadZero.exe | Same program, no zip. 12.8 MB |
| `padzero-cli.exe` | Command line, for people who want one. 9.8 MB |
| `find_key_usb.exe` | Only if your model isn't listed yet. Finds its key over USB. 9.9 MB |

No installer, no Python, nothing to set up.

    PadZero.zip       42887CFE1C718087C9F5E7719529872F6A648CEB52B0E01B09DB215F3D782243
    PadZero.exe       AE2F9B9A1274DF5FFC2FD2A813AFD18C37C4EDC1BF77BE27AC14A63ACFA3694D
    padzero-cli.exe   D2615690583071D028B19144A53F57B86082BDD950EA54145E846D2FE3F8AB93
    find_key_usb.exe  BD3A1A3AEE5ECBCB275EE0203A5773F08C906AC982D339D8450CF5EDE9B51A92

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

## What's new in v0.4.0

- **Printers that report their full name now get recognised.** A Stylus
  TX200 tells the computer it is a "Stylus TX200". The model database calls
  the same printer "TX200". Those two strings aren't equal, so Pad Zero said
  it didn't know the printer and refused to write to it, even though every
  bit of data it needed was sitting right there. It now drops the range name
  and looks again. This affected Stylus, Stylus Photo, WorkForce and
  Expression models. Reported by a TX200 owner.
- **Three more models confirmed on real hardware.** ET-2860 and L3111, both
  reported reset by their owners, plus an ET-4800 done from Linux.
- **Linux and macOS answered properly in the README.** Short version: you
  don't need Pad Zero. reinkpy, which does all the real work here, runs
  natively on Linux and performs the same reset. Two commands, they're in
  the README now.

## What's new in v0.3.0

- **Clearer message when the USB connection drops.** If the printer stops
  responding mid-reset (almost always a stuck USB connection, not a fault),
  the window now tells you to unplug the cable and try again, instead of
  showing a confusing internal error. Reported by an L120 user whose reset
  worked after a restart.
- **New tool for unlisted models: `find_key_usb.exe`.** If your printer
  isn't in the list yet, this searches for the key it needs over USB. It's
  read-only and never changes anything. If it finds a key, open an issue
  with the result and the model can be added for everyone.

## What was new in v0.2.0

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

| Model | Key group | Status |
|---|---|---|
| ET-4800 | `0x364A` | reset verified 79.85% to 0.00% |
| ET-4810 | `0x574B` | detected, read, write path verified |
| ET-2800 | `0x364A` | reported working by two owners |
| ET-2710 | `0x0797` | reported working by an owner |
| ET-2860 | `0x364A` | reported working by an owner |
| L3111 | `0x0797` | reported working by an owner |
| L4150 | `0x0849` | reported working by an owner |
| XP-960 | `0x0928` | reported working by an owner |
| EP-M476T | `0x364A` | worked out from scratch with the owner, then reset |

**1,424 Epson models can be reset.** Check yours in
[COVERAGE.md](../../blob/main/COVERAGE.md).

Listed is not the same as verified: only the seven above have been confirmed
on real hardware. If yours works, please open an issue and it moves up. If it
reports `coverage: none`, click **Save a backup** and attach the file.

## Safety

Unknown models are read-only with no override. A full backup is written
before any change. Every write is read back and verified. The CLI defaults to
a dry run.

## Credits

Standing on [reinkpy](https://codeberg.org/atufi/reinkpy),
[epson_print_conf](https://github.com/Ircama/epson_print_conf), and
[ReInk](https://github.com/lion-simba/reink).

Free, and staying that way. If it saved your printer there's a coffee tip
jar at [ko-fi.com/gangstabran](https://ko-fi.com/gangstabran), but nothing
here depends on it.

AGPL-3.0-or-later. Not affiliated with Seiko Epson Corporation.
