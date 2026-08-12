# Quick start

If your Epson has stopped printing and says something about **ink pads** or
**service required**, this page gets you going again in about five minutes.

You do not need to know anything technical.

---

## What's actually wrong with your printer

Nothing is broken.

Your printer counts how much waste ink it thinks has soaked into the sponges
inside it. When that count gets high enough, the printer refuses to print and
tells you to call Epson.

This tool sets that count back to zero, and your printer starts working again.

**But the sponges are still full of ink.** More on that at the bottom. Read
it, because it matters.

---

## Step 1: plug the printer into your computer

Use a USB cable. The printer end is the **wide, flat, squarish socket**.

Your printer also has one or two **small square sockets marked LINE and EXT**.
Those are telephone jacks for the fax. Nothing you plug in there will work
for this. If your cable is in one of those, move it.

Turn the printer on and wait for it to finish starting up.

---

## Step 2: install Epson's driver

Skip this only if you already print from this computer normally.

Windows installs a basic driver on its own. It's enough to print a page, but
it is **not** enough for this tool, or any tool like it, to talk to your
printer. If you skip this step, Pad Zero will say it can't find your printer
even though it's plugged in.

1. Go to **epson.com**, search for your model (for example ET-4800)
2. Find **Drivers and Downloads**
3. Download the one called **Printer Driver**
4. Install it, then restart your computer

> **Do not install firmware updates while you're here.** Epson has released
> firmware that permanently blocks this kind of reset, and firmware cannot be
> undone. If anything offers a firmware update, decline it.

---

## Step 3: download Pad Zero

Get **PadZero.exe** from the [Releases page](../../releases).

There's nothing to install. It's a single file. Put it on your Desktop.

---

## Step 4: run it

Double-click **PadZero.exe**.

**Windows will probably warn you.** You'll see a blue box saying *"Windows
protected your PC"*. This happens to every small program that isn't signed
with an expensive certificate, and resetting printer counters looks
suspicious to antivirus software by its nature.

To continue: click **More info**, then **Run anyway**.

If you'd rather check first, every release publishes a SHA-256 fingerprint
you can verify, and all the source code is right here in this repository.

---

## Step 5: read what it tells you

The window shows your printer and a coloured dot:

| Dot | Meaning |
|---|---|
| 🟢 Green | Everything is fine. Nothing to do. |
| 🟡 Amber | Getting full. Your printer will stop soon. |
| 🔴 Red | Full. This is why your printer stopped. |

If it says **No printer found**, go back to Steps 1 and 2. It is almost
always the cable being in the wrong socket, or the Epson driver not being
installed.

---

## Step 6: reset it

Click **Reset the counter**.

Read the warning box, then confirm. It takes a few seconds. Pad Zero saves a
backup of your printer's settings automatically before it changes anything.

When it's finished:

**Turn the printer off. Wait ten seconds. Turn it back on.**

The reset does not take effect until you do that. Your printer should now
print normally.

---

## Important: this will happen again

Resetting the counter does not remove any ink. The sponges inside your
printer hold exactly as much ink as they did five minutes ago.

If they were genuinely full, your printer is now printing into full sponges,
and eventually ink can seep out of the bottom onto whatever it's sitting on.

**Two things to do:**

1. **Put a towel or a tray under the printer today.** Costs nothing, and
   saves a desk.
2. **Order a replacement pad or a waste ink tank kit.** Search Amazon for
   "epson waste ink pad kit" plus your model. They're usually $20 to $50.
   Fitting one is the actual fix. Resetting the counter is just what gets you
   printing until then.

The button inside Pad Zero labelled **Where to buy a pad** opens that search
for you.

---

## If something goes wrong

**"No printer found"** — cable in the wrong socket, or Epson's driver isn't
installed. Steps 1 and 2.

**"Model not recognised"** — your printer works but isn't in the database
yet, so Pad Zero won't change anything on it. Click **Save a backup** and
send us the file via [issues](../../issues) so support can be added.

**"The printer refused some of the changes"** — your printer's firmware
blocks resets. Nothing is damaged, and your backup is safe. This is what
firmware updates do, and it can't be reversed.

**The window won't open at all** — you may have downloaded the wrong file.
`PadZero.exe` is the one with a window. `padzero-cli.exe` is a command-line
version for advanced users and will flash and disappear if you double-click
it.

Anything else, open an [issue](../../issues) and describe what you saw.

---

## For advanced users

`padzero-cli.exe` does the same job from a command prompt:

```
padzero-cli --list          list connected printers
padzero-cli --info          model and counter levels
padzero-cli --dump          save a full backup
padzero-cli --reset         show what would change, change nothing
padzero-cli --reset --yes   apply it
padzero-cli --explain       what a reset does and does not fix
```
