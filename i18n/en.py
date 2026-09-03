# Default (English) GUI copy. Keep this wording in lockstep with the window.

STRINGS = {
    "app_title": "Pad Zero",
    "what_is_this": "What is this?",
    "looking_for_printer": "Looking for your printer...",
    "technical_details_closed": "▸  Technical details",
    "technical_details_open": "▾  Technical details",
    "reset_the_counter": "Reset the counter",
    "check_level_now": "Check level now",
    "save_a_backup": "Save a backup",
    "lost_connection_status": "Lost the connection to the printer",
    "lost_connection_body": (
        "PadZero couldn't get a clean connection to the printer.\n\n"
        "This is almost always a stuck USB connection, not a problem with your printer.\n\n"
        "Try this:\n"
        "1. Unplug the USB cable, wait a few seconds, then plug it back in.\n"
        "2. Click Reset again.\n\n"
        "If it still fails, restart your PC and try once more - that clears the USB "
        "connection completely."
    ),
    "something_went_wrong": "Something went wrong: {error}",
    "no_counter_data": "no counter data",
    "no_readable_counters": "no readable counters",
    "counter_read_ok": "counter read OK",
    "nothing_to_clear_short": "nothing to clear",
    "stored_value_one": "{n} stored value",
    "stored_value_other": "{n} stored values",
    "readings_this_session": "READINGS THIS SESSION",
    "printer_connected_checking": "Printer connected, checking...",
    "printer_unplugged": "Printer unplugged",
    "checking_usb": "Checking the USB connection...",
    "no_printer_found": "No printer found",
    "no_printer_verdict": (
        "Nothing is answering on USB. It is almost always one of the things below, "
        "and they are quick to check."
    ),
    "step_socket_title": "Check which socket the cable is in",
    "step_socket_body": (
        "The USB cable must go in the wide, flat USB socket. The two small square "
        "sockets marked LINE and EXT are telephone jacks for the fax and do nothing "
        "for this."
    ),
    "step_driver_title": "Install Epson's own driver",
    "step_driver_body": (
        "Windows installs a basic driver that can print but cannot talk to the printer "
        "properly. Download the driver for your model from epson.com, install it, then "
        "click Check again."
    ),
    "step_power_title": "Make sure the printer is switched on",
    "step_power_body": (
        "It needs to be powered up and finished starting, not asleep mid-boot."
    ),
    "not_connected": "Not connected",
    "untested_verdict": (
        "This printer works, but Pad Zero has never been tested on this model, so it "
        "will not change anything on it."
    ),
    "help_add_model_title": "Help get your model added",
    "help_add_model_body": (
        "Click Save a backup, then send the file that appears. It contains the "
        "settings needed to support your printer."
    ),
    "open_issue_tracker": "Open the issue tracker",
    "model_not_recognised": "Model not recognised. Reading only.",
    "connected_no_percent": (
        "Connected and working. This model does not report a percentage, but the "
        "counter can still be reset."
    ),
    "ready": "Ready",
    "counter_full_verdict": (
        "The waste ink counter is full. This is why your printer has stopped printing."
    ),
    "counter_full_status": "Counter full",
    "nearly_full_verdict": "Nearly full. Your printer will stop printing soon.",
    "nearly_full_status": "Nearly full",
    "everything_fine": "Everything looks fine. There is nothing you need to do.",
    "healthy": "Healthy",
    "about_percentages": "About these percentages",
    "about_percentages_body": (
        "This exact model is not in the percentage database yet, so the figures above "
        "are worked out from {n} closely matching Epson models that store their "
        "counters at the same places. Treat them as a good estimate rather than an "
        "exact reading. The reset itself is not affected."
    ),
    "how_full": "HOW FULL THE COUNTER IS",
    "before_and_after": "BEFORE AND AFTER",
    "approximate_suffix": "   (APPROXIMATE)",
    "waste_counter_heading": "WASTE COUNTER",
    "nothing_to_clear": "Nothing to clear",
    "nothing_to_clear_body": (
        "This printer's waste counter is already at its lowest setting. There is "
        "nothing for Pad Zero to reset, and nothing you need to do."
    ),
    "some_usage": "Some usage recorded",
    "some_usage_body_one": (
        "Resetting would clear {n} stored value. This printer does not report a "
        "percentage, so Pad Zero cannot show you a bar, but the reset works the "
        "same way."
    ),
    "some_usage_body_other": (
        "Resetting would clear {n} stored values. This printer does not report a "
        "percentage, so Pad Zero cannot show you a bar, but the reset works the "
        "same way."
    ),
    "counter_read_successfully": "Counter read successfully",
    "counter_read_successfully_body": (
        "This printer does not report its level as a percentage. Pad Zero can still "
        "read and reset it."
    ),
    "exact_numbers_hint": "The exact numbers are under Technical details below.",
    "resetting_will_not_empty": "Resetting will not empty the pads",
    "pad_advice_body": (
        "The counter is only an estimate of how much ink has soaked into the pads "
        "inside your printer. Resetting it gets you printing again, but the ink is "
        "still in there. If the pads are full it can eventually leak out of the "
        "bottom.\n\n"
        "Put a towel or tray under the printer, and order a replacement pad or a "
        "waste tank kit."
    ),
    "where_to_buy_pad": "Where to buy a pad",
    "nothing_connected": "Nothing connected.",
    "reading_memory": "Reading the printer's memory, this takes a moment...",
    "backup_saved_status": "Backup saved",
    "backup_saved_title": "Backup saved",
    "backup_saved_body": (
        "A copy of your printer's settings was saved to:\n\n{path}\n\n"
        "Keep this. If anything ever goes wrong it can be used to put things back."
    ),
    "no_reset_known": "No reset is known for this model, so nothing will be changed.",
    "reset_confirm_title": "Reset the waste ink counter?",
    "reset_confirm_body": (
        "This tells your {model} that its waste ink pads are empty, so it will start "
        "printing again.\n\n"
        "IT DOES NOT EMPTY THE PADS.\n\n"
        "The ink is still inside the printer. If the pads are full, ink can leak out "
        "of the bottom onto whatever it is sitting on. Put a towel underneath and "
        "fit a new pad when you can.\n\n"
        "A backup is saved automatically before anything is changed.\n\n"
        "Go ahead?"
    ),
    "cancelled": "Cancelled",
    "saving_backup_then_resetting": "Saving a backup, then resetting...",
    "after_reset_note": "<- after reset",
    "done_power_cycle": "Done. Turn the printer off and on again.",
    "reset_complete_title": "Reset complete",
    "reset_complete_body": (
        "The counter has been reset.\n\n"
        "NEXT: turn the printer off, wait ten seconds, and turn it back on. It "
        "should print again.\n\n"
        "Then order a replacement pad. The ink is still inside the printer and this "
        "will happen again.\n\n"
        "Backup saved to:\n{path}"
    ),
    "some_changes_refused": "Some changes were refused",
    "reset_did_not_finish_title": "Reset did not finish",
    "reset_did_not_finish_body": (
        "The printer refused some of the changes.\n\n"
        "Your backup is safe at:\n{path}\n\n"
        "This usually means the printer's firmware blocks resets. Nothing has been "
        "damaged."
    ),
    "what_pad_zero_does": "What Pad Zero does",
    "explain_body": (
        "What this tool does, and what it does not\n\n"
        "  Your printer keeps a counter estimating how much waste ink has gone into\n"
        "  the absorbent pads inside it. There is no sensor. It is an estimate that\n"
        "  goes up every time the printer cleans its head, charges ink, powers on,\n"
        "  or prints borderless.\n\n"
        "  When that estimate crosses a threshold the printer refuses to print and\n"
        "  tells you to contact Epson.\n\n"
        "  This tool sets the counter back to zero. That is all it does.\n\n"
        "  It does NOT empty the pads. The ink is still in there. If the pads were\n"
        "  genuinely saturated, resetting the counter means the printer will keep\n"
        "  pumping ink into full foam, and eventually that ink comes out of the\n"
        "  bottom of the printer onto whatever it is sitting on.\n\n"
        "  The real fix is replacing the pad or fitting an external waste tank.\n"
        "  Reset the counter to get printing again, then fix it properly.\n\n"
        "  Put something absorbent under the printer in the meantime."
    ),
    "close": "Close",
    "could_not_open_window": (
        "Pad Zero could not open its window.\n\n{error}\n\n"
        "This is usually a missing Tcl/Tk installation."
    ),
    "could_not_start": "Could not start: {error}",
    "stopped_unexpectedly_title": "Pad Zero stopped unexpectedly",
    "stopped_unexpectedly_body": (
        "Something went wrong.\n\nPlease copy this and open an issue at:\n{url}\n\n{detail}"
    ),
}
