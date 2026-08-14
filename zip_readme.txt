PAD ZERO
Reset the waste ink counter on Epson printers. Free and open source.

https://github.com/Damnitbran/padzero


WHAT TO DO
----------
1. Unzip this folder anywhere (Desktop is fine).
2. Double-click PadZero.exe.
3. A window opens and finds your printer.

That's it. Nothing to install.


WINDOWS WILL WARN YOU
---------------------
You'll probably see a blue box: "Windows protected your PC".

That happens to every small program not signed with a certificate, and
resetting printer counters looks suspicious to antivirus software by its
nature. Click "More info", then "Run anyway".

If you'd rather check first, every release publishes a SHA-256 fingerprint
and all the source code is on GitHub. Verify with:

    certutil -hashfile PadZero.exe SHA256


YOU ONLY NEED THE USB CABLE FOR THIS
------------------------------------
Pad Zero talks to your printer over USB, so the cable has to be plugged in
while you use it.

That does NOT change how you print. If you printed over wi-fi before, you
still do. Unplug the cable when you're done and carry on as normal. You
only need to plug back in if you ever have to reset the counter again.


BEFORE IT CAN SEE YOUR PRINTER
------------------------------
Two things cause nearly every "no printer found" report:

1. The USB cable must be in the printer's USB port. The small square
   sockets marked LINE and EXT are telephone jacks for the fax.

2. Epson's own driver must be installed. The basic driver Windows
   installs by itself can print a page but cannot talk to the printer
   properly. Get the "Printer Driver" for your model from epson.com.

   Don't accept firmware updates while you're there. Epson has shipped
   firmware that permanently blocks resets, and it can't be undone.


IMPORTANT: THIS DOES NOT EMPTY YOUR PADS
----------------------------------------
Your printer counts how much waste ink it thinks has soaked into the
sponges inside it. This tool sets that count back to zero, which gets you
printing again.

The ink is still in there. If the sponges are genuinely full, the printer
will keep pumping ink into full sponges and it can eventually seep out of
the bottom.

Put a towel or tray under the printer, and order a replacement pad or a
waste tank kit. That's the actual fix. Resetting the counter is what keeps
you going until then.


WILL IT WORK ON MY MODEL?
-------------------------
1,423 Epson models can be reset. Check the list:
https://github.com/Damnitbran/padzero/blob/main/COVERAGE.md

If yours isn't there, run padzero-cli.exe --dump and open an issue with
the file, and it can be added.


COMMAND LINE VERSION
--------------------
There's a padzero-cli.exe on the releases page if you want one. If you're
not sure whether you do, you don't.


Licence: AGPL-3.0-or-later. Not affiliated with Seiko Epson Corporation.
