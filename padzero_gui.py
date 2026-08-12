#!/usr/bin/env python3
r"""
padzero_gui.py - window front end for Pad Zero.

Written for someone who has never heard of an EEPROM. The window answers
three questions in plain words, in this order:

    1. Which printer am I looking at?
    2. Is anything wrong with it?
    3. What should I do about it?

Everything technical (key groups, EEPROM addresses, byte values) lives
behind a Details panel that is closed by default.

Implementation notes:
  * Printer work runs on a worker thread. A D4 handshake plus a counter
    read takes several seconds, and doing that on the UI thread makes
    Windows grey the window out and say "not responding".
  * Workers never touch widgets. Results come back through a queue that
    the UI polls, which is the only thread-safe way to drive tkinter.
  * Sized and spaced to stay readable in a 1080p screen recording.

SPDX-License-Identifier: AGPL-3.0-or-later
"""
import os
import sys


def _fix_tcl():
    """Point Tcl/Tk at its libraries before tkinter is imported.

    Python 3.14 on Windows keeps Tcl in <prefix>\\tcl\\tcl8.6, but a venv
    (and some frozen builds) look in <prefix>\\lib\\tcl8.6 and fail with
    "Can't find a usable init.tcl". Setting these two variables up front
    fixes it everywhere rather than only on the machine it was built on.
    """
    if os.environ.get("TCL_LIBRARY"):
        return
    roots = [getattr(sys, "base_prefix", sys.prefix), sys.prefix]
    if getattr(sys, "frozen", False):
        roots.insert(0, sys._MEIPASS)
    for root in roots:
        tcl_root = os.path.join(root, "tcl")
        if not os.path.isdir(tcl_root):
            continue
        for name in sorted(os.listdir(tcl_root)):
            full = os.path.join(tcl_root, name)
            if name.startswith("tcl8") and os.path.exists(
                    os.path.join(full, "init.tcl")):
                os.environ["TCL_LIBRARY"] = full
            elif name.startswith("tk8"):
                os.environ["TK_LIBRARY"] = full
        if os.environ.get("TCL_LIBRARY"):
            return


def _dpi_aware():
    """Tell Windows we will handle scaling ourselves, and report the factor.

    Without this, tkinter renders at 96 DPI and Windows bitmap-stretches the
    result to the display's actual scaling. On a 125% display every glyph is
    resampled, which looks soft and cheap. Declaring awareness makes Tk draw
    at native resolution; we then scale fonts and sizes to match so the
    window is the same physical size, just sharp.

    Must run before the first Tk window is created.
    """
    import ctypes
    try:
        # 2 = PROCESS_PER_MONITOR_DPI_AWARE
        ctypes.windll.shcore.SetProcessDpiAwareness(2)
    except Exception:
        try:
            ctypes.windll.user32.SetProcessDPIAware()
        except Exception:
            return 1.0
    try:
        hdc = ctypes.windll.user32.GetDC(0)
        dpi = ctypes.windll.gdi32.GetDeviceCaps(hdc, 88)  # LOGPIXELSX
        ctypes.windll.user32.ReleaseDC(0, hdc)
        if dpi:
            return max(1.0, dpi / 96.0)
    except Exception:
        pass
    return 1.0


_fix_tcl()
SCALE = _dpi_aware()


def S(n):
    """Scale a pixel measurement for this display."""
    return int(round(n * SCALE))


import queue                      # noqa: E402
import threading                  # noqa: E402
import tkinter as tk              # noqa: E402
import webbrowser                 # noqa: E402
from datetime import datetime     # noqa: E402
from tkinter import messagebox    # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
if not getattr(sys, "frozen", False):
    sys.path.insert(0, os.path.join(HERE, "reinkpy"))

import padzero as core            # noqa: E402

PADS_URL = "https://www.amazon.com/s?k=epson+waste+ink+pad+kit"
ISSUES_URL = "https://github.com/Damnitbran/padzero/issues"

# ------------------------------------------------------------------ theme
BG     = "#11161A"
CARD   = "#1A2227"
CARD2  = "#212B31"
FG     = "#E8EEF0"
DIM    = "#8B989E"
FAINT  = "#5C686D"
ACCENT = "#4FC3D6"
GOOD   = "#5FC79A"
WARN   = "#E0A94A"
BAD    = "#E8796B"
RULE   = "#2B363B"

F_APP    = ("Segoe UI", 13, "bold")
F_BIG    = ("Segoe UI", 24, "bold")
F_STATUS = ("Segoe UI", 14)
F_BODY   = ("Segoe UI", 11)
F_BTN    = ("Segoe UI", 12, "bold")
F_SMALL  = ("Segoe UI", 10)
F_MONO   = ("Consolas", 10)


def flat_button(parent, text, cmd, bg=CARD2, fg=FG, font=F_BODY,
                padx=18, pady=9):
    b = tk.Button(parent, text=text, command=cmd, font=font, bg=bg, fg=fg,
                  activebackground=RULE, activeforeground=FG,
                  disabledforeground=FAINT, relief="flat", bd=0,
                  padx=padx, pady=pady, cursor="hand2",
                  highlightthickness=0)
    return b


class App:
    def __init__(self, root):
        self.root = root
        self.q = queue.Queue()
        self.models = core.load_models()
        self.printer = None
        self.busy = False
        self.details_open = False
        self._known_paths = None
        # Every reading taken this session, so a reset shows as a visible
        # change over time rather than a number you have to have memorised.
        self.history = []

        root.title("Pad Zero")
        root.configure(bg=BG)
        root.geometry("%dx%d" % (S(720), S(720)))
        root.minsize(S(660), S(640))
        # Tk sizes point-based fonts using this factor. Setting it from the
        # real DPI makes every font in the window scale correctly now that
        # we have told Windows not to stretch us.
        try:
            root.tk.call("tk", "scaling", (96.0 * SCALE) / 72.0)
        except Exception:
            pass

        self._build()
        self.root.after(80, self._pump)
        self.root.after(1500, self._watch)
        self.scan()

    # ---------------------------------------------------------- structure
    def _build(self):
        bar = tk.Frame(self.root, bg=BG)
        bar.pack(fill="x", padx=S(24), pady=(S(18), 0))
        tk.Label(bar, text="Pad Zero", font=F_APP, bg=BG, fg=FG).pack(side="left")
        self.b_help = flat_button(bar, "What is this?", self.show_explain,
                                  bg=BG, fg=DIM, padx=S(10), pady=S(6))
        self.b_help.pack(side="right")

        # main card
        self.card = tk.Frame(self.root, bg=CARD)
        self.card.pack(fill="x", padx=S(24), pady=(S(16), 0))

        self.l_dot = tk.Label(self.card, text="", font=("Segoe UI", 30),
                              bg=CARD, fg=DIM)
        self.l_dot.pack(anchor="w", padx=S(26), pady=(S(20), 0))
        self.l_model = tk.Label(self.card, text="Looking for your printer...",
                                font=F_BIG, bg=CARD, fg=FG, anchor="w",
                                justify="left", wraplength=S(600))
        self.l_model.pack(fill="x", padx=S(26))
        self.l_verdict = tk.Label(self.card, text="", font=F_STATUS, bg=CARD,
                                  fg=DIM, anchor="w", justify="left",
                                  wraplength=S(600))
        self.l_verdict.pack(fill="x", padx=S(26), pady=(S(6), S(22)))

        # Everything below is packed to the BOTTOM edge first, before the
        # expanding content above it. With pack(), whatever is added last
        # gets clipped when the window is short, and the button that does
        # the actual job must never be the thing that disappears.
        self.l_status = tk.Label(self.root, text="", font=F_SMALL, bg=BG,
                                 fg=FAINT, anchor="w")
        self.l_status.pack(side="bottom", fill="x", padx=S(24), pady=(S(6), S(12)))

        self.details = tk.Frame(self.root, bg=CARD2)
        self.b_details = flat_button(self.root, "▸  Technical details",
                                     self.toggle_details, bg=BG, fg=FAINT,
                                     font=F_SMALL, padx=0, pady=6)
        self.b_details.pack(side="bottom", anchor="w", padx=S(24))
        self.l_details = tk.Label(self.details, text="", font=F_MONO, bg=CARD2,
                                  fg=DIM, anchor="w", justify="left")
        self.l_details.pack(fill="x", padx=16, pady=12)

        # All three actions live together at the bottom. The check button
        # used to sit in the top-right corner and people looked for it here.
        act = tk.Frame(self.root, bg=BG)
        act.pack(side="bottom", fill="x", padx=S(24), pady=(S(12), S(10)))
        self.b_reset = flat_button(act, "Reset the counter", self.do_reset,
                                   bg=ACCENT, fg="#0B1417", font=F_BTN,
                                   padx=S(26), pady=S(14))
        self.b_reset.pack(side="left")
        self.b_refresh = flat_button(act, "Check level now", self.scan,
                                     bg=CARD2, fg=FG, font=F_BTN,
                                     padx=S(20), pady=S(14))
        self.b_refresh.pack(side="left", padx=(S(10), 0))
        self.b_backup = flat_button(act, "Save a backup", self.do_backup,
                                    padx=S(16), pady=S(14))
        self.b_backup.pack(side="left", padx=(S(10), 0))

        # reading history, also pinned so it stays put as content changes
        self.hist_frame = tk.Frame(self.root, bg=BG)
        self.hist_frame.pack(side="bottom", fill="x", padx=S(24), pady=(0, S(4)))

        # scrolling content above the pinned controls
        self.levels = tk.Frame(self.root, bg=BG)
        self.levels.pack(fill="x", padx=S(24), pady=(S(18), 0))

        self.advice = tk.Frame(self.root, bg=BG)
        self.advice.pack(fill="both", expand=True, padx=S(24), pady=(S(14), 0))

    # ------------------------------------------------------------ threads
    def _run(self, fn, tag):
        if self.busy:
            return
        self.busy = True
        self._buttons(False)

        def worker():
            try:
                self.q.put((tag, fn(), None))
            except Exception as exc:
                self.q.put((tag, None, exc))

        threading.Thread(target=worker, daemon=True).start()

    def _pump(self):
        try:
            while True:
                tag, res, err = self.q.get_nowait()
                self.busy = False
                self._buttons(True)
                if err:
                    self.status("Something went wrong: %s" % err, BAD)
                    messagebox.showerror("Pad Zero", str(err))
                else:
                    getattr(self, "after_" + tag)(res)
        except queue.Empty:
            pass
        self.root.after(80, self._pump)

    @staticmethod
    def _summarise(counters):
        """One line describing a reading, for the history list."""
        if not counters:
            return "no counter data"
        pcts = [c for c in counters if c.get("percent") is not None]
        if pcts:
            return "   ".join("%s %.2f%%"
                              % (c["name"].split("_")[0], c["percent"])
                              for c in pcts)
        parts = []
        for c in counters:
            if "values" in c:
                nz = [(a, v) for a, v in zip(c["addrs"], c["values"]) if v]
                parts.append(", ".join("%d=%s" % (a, v) for a, v in nz)
                             or "all zero")
        return "   ".join(parts) or "no readable counters"

    def _log_reading(self, counters, note=""):
        stamp = datetime.now().strftime("%H:%M:%S")
        self.history.append((stamp, self._summarise(counters), note))
        self._render_history()

    def _render_history(self):
        self._clear(self.hist_frame)
        if len(self.history) < 2:
            return  # a single reading is not a history

        tk.Label(self.hist_frame, text="READINGS THIS SESSION",
                 font=("Segoe UI", 9, "bold"), bg=BG, fg=FAINT,
                 anchor="w").pack(fill="x", pady=(6, 4))

        for stamp, summary, note in self.history[-4:]:
            row = tk.Frame(self.hist_frame, bg=BG)
            row.pack(fill="x")
            tk.Label(row, text=stamp, font=("Consolas", 9), bg=BG,
                     fg=FAINT).pack(side="left")
            colour = ACCENT if note else DIM
            tk.Label(row, text=summary, font=("Consolas", 9), bg=BG,
                     fg=colour, anchor="w").pack(side="left", padx=(10, 0))
            if note:
                tk.Label(row, text=note, font=("Segoe UI", 9, "bold"), bg=BG,
                         fg=GOOD).pack(side="left", padx=(8, 0))

    def _watch(self):
        """Notice the cable being plugged or unplugged, and rescan.

        Without this the window keeps showing a healthy printer after you
        unplug it, which is worse than showing nothing: it says everything
        is fine about a device that is no longer there.

        Enumeration is a PnP lookup, not device I/O, and measures about
        0.08 ms, so polling it costs nothing. The expensive part (opening
        the device and negotiating D4) only happens when the set of
        interfaces actually changes.
        """
        try:
            if not self.busy:
                paths = tuple(sorted(core.list_usb_printers()))
                if self._known_paths is None:
                    self._known_paths = paths
                elif paths != self._known_paths:
                    self._known_paths = paths
                    if paths:
                        self.status("Printer connected, checking...", ACCENT)
                    else:
                        self.status("Printer unplugged", WARN)
                    self.scan()
        except Exception:
            pass  # never let the watchdog kill the window
        self.root.after(1500, self._watch)

    def _buttons(self, on):
        state = "normal" if on else "disabled"
        self.b_refresh.configure(state=state)
        self.b_backup.configure(state=state)
        self._reset_enabled(on)

    def _reset_enabled(self, on):
        """Enable or disable the reset button, and make it look it.

        tk keeps a button's background when you disable it, so the accent
        colour would stay bright and the control would still read as
        clickable. Repaint it so disabled actually looks disabled.
        """
        if on:
            self.b_reset.configure(state="normal", bg=ACCENT, fg="#0B1417")
        else:
            self.b_reset.configure(state="disabled", bg=CARD2, fg=FAINT)

    def status(self, text, colour=FAINT):
        self.l_status.configure(text=text, fg=colour)

    def _clear(self, frame):
        for w in frame.winfo_children():
            w.destroy()

    # --------------------------------------------------------------- scan
    def scan(self):
        self.status("Checking the USB connection...")
        self.l_dot.configure(text="●", fg=DIM)
        self.l_model.configure(text="Looking for your printer...")
        self.l_verdict.configure(text="", fg=DIM)
        self._clear(self.levels)
        self._clear(self.advice)
        self._run(self._scan_work, "scan")

    def _scan_work(self):
        for path in core.list_usb_printers():
            try:
                with core.quiet():
                    pr = core.Printer(path, self.models)
                    if pr.model:
                        return pr, pr.counters()
            except Exception:
                continue
        return None, None

    def after_scan(self, res):
        pr, counters = res
        self.printer = pr
        self._clear(self.levels)
        self._clear(self.advice)

        if not pr:
            self._state_no_printer()
            return

        worst = self._worst(counters)
        self._state_found(pr, counters, worst)
        self._log_reading(counters)

    @staticmethod
    def _worst(counters):
        pcts = [c["percent"] for c in (counters or [])
                if c.get("percent") is not None]
        return max(pcts) if pcts else None

    # ------------------------------------------------------------- states
    def _state_no_printer(self):
        self.l_dot.configure(text="●", fg=BAD)
        self.l_model.configure(text="No printer found")
        self.l_verdict.configure(
            text="Nothing is answering on USB. It is almost always one of "
                 "the things below, and they are quick to check.", fg=DIM)
        self._reset_enabled(False)
        self.b_backup.configure(state="disabled")
        self._details("")

        self._steps(self.advice, [
            ("Check which socket the cable is in",
             "The USB cable must go in the wide, flat USB socket. The two "
             "small square sockets marked LINE and EXT are telephone jacks "
             "for the fax and do nothing for this."),
            ("Install Epson's own driver",
             "Windows installs a basic driver that can print but cannot talk "
             "to the printer properly. Download the driver for your model "
             "from epson.com, install it, then click Check again."),
            ("Make sure the printer is switched on",
             "It needs to be powered up and finished starting, not asleep "
             "mid-boot."),
        ])
        self.status("Not connected", BAD)

    def _state_found(self, pr, counters, worst):
        self.l_model.configure(text=pr.model)
        self.b_backup.configure(state="normal")

        if pr.coverage == "none":
            self.l_dot.configure(text="●", fg=WARN)
            self.l_verdict.configure(
                text="This printer works, but Pad Zero has never been tested "
                     "on this model, so it will not change anything on it.",
                fg=WARN)
            self._reset_enabled(False)
            self._steps(self.advice, [
                ("Help get your model added",
                 "Click Save a backup, then send the file that appears. It "
                 "contains the settings needed to support your printer."),
            ], button=("Open the issue tracker",
                       lambda: webbrowser.open(ISSUES_URL)))
            self.status("Model not recognised. Reading only.", WARN)

        elif worst is None:
            self.l_dot.configure(text="●", fg=GOOD)
            self.l_verdict.configure(
                text="Connected and working. This model does not report a "
                     "percentage, but the counter can still be reset.", fg=DIM)
            self._reset_enabled(True)
            self.status("Ready", GOOD)

        elif worst >= 100:
            self.l_dot.configure(text="●", fg=BAD)
            self.l_verdict.configure(
                text="The waste ink counter is full. This is why your printer "
                     "has stopped printing.", fg=BAD)
            self._reset_enabled(True)
            self._pad_advice(urgent=True)
            self.status("Counter full", BAD)

        elif worst >= 85:
            self.l_dot.configure(text="●", fg=WARN)
            self.l_verdict.configure(
                text="Nearly full. Your printer will stop printing soon.",
                fg=WARN)
            self._reset_enabled(True)
            self._pad_advice(urgent=False)
            self.status("Nearly full", WARN)

        else:
            self.l_dot.configure(text="●", fg=GOOD)
            self.l_verdict.configure(
                text="Everything looks fine. There is nothing you need to do.",
                fg=GOOD)
            self._reset_enabled(True)
            self.status("Healthy", GOOD)

        self._bars(counters)
        rk = getattr(pr.ep.spec, "rkey", None)
        lines = ["model      %s" % pr.model,
                 "serial     %s" % (pr.serial or "?"),
                 "presents   %s" % (pr.detected or "?"),
                 "key group  %s / %r" % (hex(rk) if rk else "?",
                                         getattr(pr.ep.spec, "wkey", None)),
                 "coverage   %s" % pr.coverage]
        try:
            plan, src = pr.reset_plan()
            lines.append("reset map  %d addresses (%s)" % (len(plan), src))
        except Exception:
            pass
        for c in counters or []:
            if c.get("percent") is not None:
                lines.append("%-18s raw=%s bytes=%s"
                             % (c["name"], c.get("raw"), c.get("bytes")))
            elif "values" in c:
                lines.append("%-18s %s" % (c["name"], dict(
                    zip(c["addrs"], c["values"]))))
        self._details("\n".join(lines))

    # ------------------------------------------------------------ widgets
    def _bars(self, counters, previous=None):
        """Render counters as bars where we have percentages, and as a
        readable card where we only have raw values.

        Plenty of models (the ET-4810 among them) have known reset addresses
        but no divider to convert bytes into a percentage. Showing nothing at
        all leaves a hole in the window and makes the tool look broken, so
        say plainly what is and isn't known.
        """
        self._clear(self.levels)
        if not counters:
            return

        readable = [c for c in counters if c.get("percent") is not None]
        raw_only = [c for c in counters if c.get("percent") is None
                    and "values" in c]

        prev = {}
        if previous:
            prev = {c["name"]: c.get("percent") for c in previous
                    if c.get("percent") is not None}

        if readable:
            heading = "BEFORE AND AFTER" if prev else "HOW FULL THE COUNTER IS"
            tk.Label(self.levels, text=heading,
                     font=("Segoe UI", 9, "bold"), bg=BG,
                     fg=ACCENT if prev else FAINT,
                     anchor="w").pack(fill="x", pady=(0, 8))

        for c in readable:
            pct = c["percent"]
            was = prev.get(c["name"])
            row = tk.Frame(self.levels, bg=BG)
            row.pack(fill="x", pady=4)

            label = c["name"].replace("_", " ").replace("waste", "pad")
            tk.Label(row, text=label.title(), font=F_BODY, bg=BG, fg=DIM,
                     width=17, anchor="w").pack(side="left")

            # When we have a previous reading, show it struck through on the
            # left so the change is visible at a glance on a recording.
            if was is not None and abs(was - pct) > 0.005:
                old = BAD if was >= 100 else (WARN if was >= 85 else GOOD)
                tk.Label(row, text="%.1f%%" % was,
                         font=("Consolas", 11, "overstrike"),
                         bg=BG, fg=FAINT).pack(side="left", padx=(0, 6))
                tk.Label(row, text="→", font=F_BODY, bg=BG,
                         fg=FAINT).pack(side="left", padx=(0, 8))
                del old

            colour = BAD if pct >= 100 else (WARN if pct >= 85 else GOOD)
            width = S(330) if was is None else S(210)
            track = tk.Frame(row, bg=RULE, height=S(18), width=width)
            track.pack(side="left")
            track.pack_propagate(False)
            tk.Frame(track, bg=colour).place(
                relwidth=max(0.0, min(pct / 100.0, 1.0)), relheight=1)
            tk.Label(row, text="%5.1f%%" % pct, font=("Consolas", 11, "bold"),
                     bg=BG, fg=colour).pack(side="left", padx=(12, 0))

        if raw_only and not readable:
            # No divider is known for this model, so there is no honest
            # percentage to show. Say in words whether a reset would change
            # anything; the raw addresses live in Technical details, where
            # someone who wants them can find them.
            self._raw_summary(raw_only)

    def _raw_summary(self, raw_only):
        """Plain-English state for models with no percentage available.

        Compares what the counters hold now against what a reset would write.
        If they already match, there is genuinely nothing to clear, and
        saying so is far more use than a row of hex addresses.
        """
        pending = None
        try:
            plan, _src = self.printer.reset_plan()
            if plan:
                current = self.printer.read([a for a, _ in plan])
                pending = sum(1 for a, v in plan if current.get(a) != v)
        except Exception:
            pending = None

        box = tk.Frame(self.levels, bg=CARD)
        box.pack(fill="x")

        tk.Label(box, text="WASTE COUNTER", font=("Segoe UI", 9, "bold"),
                 bg=CARD, fg=FAINT, anchor="w").pack(
            fill="x", padx=S(18), pady=(S(14), S(4)))

        if pending == 0:
            headline, colour = "Nothing to clear", GOOD
            body = ("This printer's waste counter is already at its lowest "
                    "setting. There is nothing for Pad Zero to reset, and "
                    "nothing you need to do.")
        elif pending:
            headline, colour = "Some usage recorded", ACCENT
            body = ("Resetting would clear %d stored value%s. This printer "
                    "does not report a percentage, so Pad Zero cannot show "
                    "you a bar, but the reset works the same way."
                    % (pending, "" if pending == 1 else "s"))
        else:
            headline, colour = "Counter read successfully", DIM
            body = ("This printer does not report its level as a percentage. "
                    "Pad Zero can still read and reset it.")

        tk.Label(box, text=headline, font=("Segoe UI", 15, "bold"), bg=CARD,
                 fg=colour, anchor="w").pack(fill="x", padx=S(18))
        tk.Label(box, text=body, font=F_BODY, bg=CARD, fg=DIM, anchor="w",
                 justify="left", wraplength=S(600)).pack(
            fill="x", padx=S(18), pady=(S(4), S(8)))
        tk.Label(box,
                 text="The exact numbers are under Technical details below.",
                 font=F_SMALL, bg=CARD, fg=FAINT, anchor="w").pack(
            fill="x", padx=S(18), pady=(0, S(16)))

    def _steps(self, parent, steps, button=None):
        for i, (title, body) in enumerate(steps, 1):
            box = tk.Frame(parent, bg=CARD)
            box.pack(fill="x", pady=(0, 8))
            head = tk.Frame(box, bg=CARD)
            head.pack(fill="x", padx=16, pady=(12, 0))
            tk.Label(head, text=str(i), font=("Consolas", 12, "bold"),
                     bg=CARD, fg=ACCENT).pack(side="left")
            tk.Label(head, text=title, font=("Segoe UI", 11, "bold"), bg=CARD,
                     fg=FG, anchor="w").pack(side="left", padx=(12, 0))
            tk.Label(box, text=body, font=F_SMALL, bg=CARD, fg=DIM,
                     anchor="w", justify="left", wraplength=S(580)).pack(
                fill="x", padx=(44, 16), pady=(2, 12))
        if button:
            text, cmd = button
            flat_button(parent, text, cmd).pack(anchor="w", pady=(4, 0))

    def _pad_advice(self, urgent):
        box = tk.Frame(self.advice, bg=CARD)
        box.pack(fill="x")
        tk.Label(box,
                 text="Resetting will not empty the pads",
                 font=("Segoe UI", 11, "bold"), bg=CARD, fg=WARN,
                 anchor="w").pack(fill="x", padx=16, pady=(12, 2))
        tk.Label(box,
                 text=("The counter is only an estimate of how much ink has "
                       "soaked into the pads inside your printer. Resetting it "
                       "gets you printing again, but the ink is still in there. "
                       "If the pads are full it can eventually leak out of the "
                       "bottom.\n\n"
                       "Put a towel or tray under the printer, and order a "
                       "replacement pad or a waste tank kit."),
                 font=F_SMALL, bg=CARD, fg=DIM, anchor="w", justify="left",
                 wraplength=S(580)).pack(fill="x", padx=16, pady=(0, 10))
        flat_button(box, "Where to buy a pad",
                    lambda: webbrowser.open(PADS_URL),
                    bg=CARD2, fg=FG, font=F_SMALL, padx=14, pady=7).pack(
            anchor="w", padx=16, pady=(0, 14))

    def _details(self, text):
        self.l_details.configure(text=text or "Nothing connected.")

    def toggle_details(self):
        self.details_open = not self.details_open
        if self.details_open:
            self.details.pack(side="bottom", fill="x", padx=S(24), pady=(S(6), 0),
                              before=self.b_details)
            self.b_details.configure(text="▾  Technical details")
        else:
            self.details.pack_forget()
            self.b_details.configure(text="▸  Technical details")

    # ------------------------------------------------------------ actions
    def do_backup(self):
        if not self.printer:
            return
        self.status("Reading the printer's memory, this takes a moment...")
        self._run(self.printer.save_dump, "backup")

    def after_backup(self, path):
        self.status("Backup saved", GOOD)
        messagebox.showinfo(
            "Backup saved",
            "A copy of your printer's settings was saved to:\n\n%s\n\n"
            "Keep this. If anything ever goes wrong it can be used to put "
            "things back." % path)

    def do_reset(self):
        pr = self.printer
        if not pr:
            return
        try:
            plan, _src = pr.reset_plan()
        except Exception as exc:
            messagebox.showerror("Pad Zero", str(exc))
            return
        if not plan:
            messagebox.showwarning(
                "Pad Zero", "No reset is known for this model, so nothing "
                            "will be changed.")
            return

        ok = messagebox.askyesno(
            "Reset the waste ink counter?",
            "This tells your %s that its waste ink pads are empty, so it will "
            "start printing again.\n\n"
            "IT DOES NOT EMPTY THE PADS.\n\n"
            "The ink is still inside the printer. If the pads are full, ink "
            "can leak out of the bottom onto whatever it is sitting on. Put a "
            "towel underneath and fit a new pad when you can.\n\n"
            "A backup is saved automatically before anything is changed.\n\n"
            "Go ahead?" % pr.model,
            icon="warning", default="no")
        if not ok:
            self.status("Cancelled")
            return

        self.status("Saving a backup, then resetting...")
        self._run(lambda: self._reset_work(plan), "reset")

    def _reset_work(self, plan):
        before = self.printer.counters()
        path = self.printer.save_dump(tag="pre-reset")
        ok = True
        for addr, value in plan:
            ok = bool(self.printer.ep.write_eeprom((addr, value))) and ok
        return path, ok, self.printer.counters(), before

    def after_reset(self, res):
        path, ok, counters, before = res
        self._bars(counters, previous=before)
        self._log_reading(counters, note="<- after reset" if ok else "")
        if ok:
            self.status("Done. Turn the printer off and on again.", GOOD)
            messagebox.showinfo(
                "Reset complete",
                "The counter has been reset.\n\n"
                "NEXT: turn the printer off, wait ten seconds, and turn it "
                "back on. It should print again.\n\n"
                "Then order a replacement pad. The ink is still inside the "
                "printer and this will happen again.\n\n"
                "Backup saved to:\n%s" % path)
            # deliberately not re-scanning: that would wipe the before/after
            # comparison off the screen, which is the proof it worked
        else:
            self.status("Some changes were refused", BAD)
            messagebox.showerror(
                "Reset did not finish",
                "The printer refused some of the changes.\n\n"
                "Your backup is safe at:\n%s\n\n"
                "This usually means the printer's firmware blocks resets. "
                "Nothing has been damaged." % path)

    def show_explain(self):
        win = tk.Toplevel(self.root, bg=BG)
        win.title("What Pad Zero does")
        win.geometry("640x560")
        win.transient(self.root)
        frame = tk.Frame(win, bg=CARD)
        frame.pack(fill="both", expand=True, padx=18, pady=18)
        txt = tk.Text(frame, bg=CARD, fg=FG, font=F_BODY, wrap="word",
                      relief="flat", padx=20, pady=20, bd=0,
                      highlightthickness=0)
        txt.pack(fill="both", expand=True)
        txt.insert("1.0", core.EXPLAIN.strip())
        txt.configure(state="disabled")
        flat_button(win, "Close", win.destroy).pack(pady=(0, 16))


def main():
    """Start the window.

    A --windowed build has no console, so an unhandled exception would
    otherwise vanish silently and look like the program simply refusing to
    open. Catch everything and say something useful instead.
    """
    try:
        root = tk.Tk()
    except Exception as exc:
        try:
            import ctypes
            ctypes.windll.user32.MessageBoxW(
                0,
                "Pad Zero could not open its window.\n\n%s\n\n"
                "This is usually a missing Tcl/Tk installation." % exc,
                "Pad Zero", 0x10)
        except Exception:
            print("Could not start: %s" % exc)
        return 1

    try:
        App(root)
        root.mainloop()
    except Exception:
        import traceback
        detail = traceback.format_exc()
        try:
            messagebox.showerror(
                "Pad Zero stopped unexpectedly",
                "Something went wrong.\n\nPlease copy this and open an issue "
                "at:\n%s\n\n%s" % (ISSUES_URL, detail[-1500:]))
        except Exception:
            print(detail)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
