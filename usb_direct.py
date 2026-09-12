"""
usb_direct.py - bidirectional USB access to the printer on Windows,
without replacing any drivers.

Background: the '||' factory commands are refused on the SNMP control
OID (":NA;") and port 9100 returns nothing at all. But WIC Reset wrote
EEPROM successfully over USB with the stock Epson driver installed, so
a bidirectional USB path exists on Windows.

That path is usbprint.sys's device interface. Windows publishes every
USB printer under GUID_DEVINTERFACE_USBPRINT; the interface path can be
opened with CreateFileW and driven with WriteFile/ReadFile. No Zadig,
no WinUSB, no WSL, no admin rights.

This module:
  * enumerates USB printer interfaces via SetupAPI
  * opens one and does a write/read exchange
  * builds the same '||' factory commands used elsewhere in this project

Read-only unless you call write_eeprom().
"""
import ctypes
import re
import struct
import sys
import threading
from ctypes import wintypes

# ---------------------------------------------------------------- Win32
setupapi = ctypes.WinDLL("setupapi", use_last_error=True)
kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)


class GUID(ctypes.Structure):
    _fields_ = [
        ("Data1", wintypes.DWORD),
        ("Data2", wintypes.WORD),
        ("Data3", wintypes.WORD),
        ("Data4", ctypes.c_ubyte * 8),
    ]


class SP_DEVICE_INTERFACE_DATA(ctypes.Structure):
    _fields_ = [
        ("cbSize", wintypes.DWORD),
        ("InterfaceClassGuid", GUID),
        ("Flags", wintypes.DWORD),
        ("Reserved", ctypes.POINTER(wintypes.ULONG)),
    ]


# {28D78FAD-5A12-11D1-AE5B-0000F803A8C2}
GUID_DEVINTERFACE_USBPRINT = GUID(
    0x28D78FAD, 0x5A12, 0x11D1,
    (ctypes.c_ubyte * 8)(0xAE, 0x5B, 0x00, 0x00, 0xF8, 0x03, 0xA8, 0xC2),
)

DIGCF_PRESENT = 0x02
DIGCF_DEVICEINTERFACE = 0x10
INVALID_HANDLE_VALUE = ctypes.c_void_p(-1).value

GENERIC_READ = 0x80000000
GENERIC_WRITE = 0x40000000
FILE_SHARE_READ = 0x01
FILE_SHARE_WRITE = 0x02
OPEN_EXISTING = 3

setupapi.SetupDiGetClassDevsW.restype = wintypes.HANDLE
setupapi.SetupDiGetClassDevsW.argtypes = [
    ctypes.POINTER(GUID), wintypes.LPCWSTR, wintypes.HWND, wintypes.DWORD]
setupapi.SetupDiEnumDeviceInterfaces.argtypes = [
    wintypes.HANDLE, ctypes.c_void_p, ctypes.POINTER(GUID), wintypes.DWORD,
    ctypes.POINTER(SP_DEVICE_INTERFACE_DATA)]
setupapi.SetupDiEnumDeviceInterfaces.restype = wintypes.BOOL
setupapi.SetupDiGetDeviceInterfaceDetailW.argtypes = [
    wintypes.HANDLE, ctypes.POINTER(SP_DEVICE_INTERFACE_DATA), ctypes.c_void_p,
    wintypes.DWORD, ctypes.POINTER(wintypes.DWORD), ctypes.c_void_p]
setupapi.SetupDiGetDeviceInterfaceDetailW.restype = wintypes.BOOL
setupapi.SetupDiDestroyDeviceInfoList.argtypes = [wintypes.HANDLE]

kernel32.CreateFileW.restype = wintypes.HANDLE
kernel32.CreateFileW.argtypes = [
    wintypes.LPCWSTR, wintypes.DWORD, wintypes.DWORD, ctypes.c_void_p,
    wintypes.DWORD, wintypes.DWORD, wintypes.HANDLE]
kernel32.WriteFile.argtypes = [
    wintypes.HANDLE, ctypes.c_void_p, wintypes.DWORD,
    ctypes.POINTER(wintypes.DWORD), ctypes.c_void_p]
kernel32.ReadFile.argtypes = [
    wintypes.HANDLE, ctypes.c_void_p, wintypes.DWORD,
    ctypes.POINTER(wintypes.DWORD), ctypes.c_void_p]
kernel32.CloseHandle.argtypes = [wintypes.HANDLE]
kernel32.GetCurrentThreadId.restype = wintypes.DWORD
kernel32.OpenThread.restype = wintypes.HANDLE
kernel32.OpenThread.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
kernel32.CancelSynchronousIo.restype = wintypes.BOOL
kernel32.CancelSynchronousIo.argtypes = [wintypes.HANDLE]

THREAD_TERMINATE = 0x0001          # the access CancelSynchronousIo needs
ERROR_OPERATION_ABORTED = 995

# How long one ReadFile/WriteFile may sit with no answer from the printer
# before it is abandoned. A healthy printer answers a D4 packet in
# milliseconds; the slowest reply seen on real hardware is well under a
# second. Fifteen seconds is long enough that a sleepy printer waking up
# is not mistaken for a dead one.
IO_TIMEOUT = 15.0


class PrinterSilent(Exception):
    """The printer stopped answering and the wait was abandoned.

    Deliberately not an OSError. The transport wrapper in padzero.py turns
    OSError into an empty read so reinkpy can retry, and reinkpy retries
    in nested loops. A timeout that came back as OSError would be waited
    out dozens of times over. This one goes straight up to the caller.
    """


EPSON_VID = "04b8"

_ID_RE = re.compile(r"vid_([0-9a-f]{4})&pid_([0-9a-f]{4})(?:&mi_([0-9a-f]{2}))?",
                    re.I)


def parse_ids(path):
    """Pull (vid, pid, interface) out of a device-interface path.
    Any element that isn't present comes back as None."""
    m = _ID_RE.search(path)
    if not m:
        return None, None, None
    vid, pid, mi = m.groups()
    return vid.lower(), pid.lower(), (mi.lower() if mi else None)


def is_epson(path):
    """True if this interface path belongs to an Epson device (VID 04B8)."""
    return parse_ids(path)[0] == EPSON_VID


def describe(path):
    """Short human-readable label for an interface path."""
    vid, pid, mi = parse_ids(path)
    if vid is None:
        return "unrecognised path"
    who = "EPSON" if vid == EPSON_VID else "VID %s" % vid.upper()
    label = "%s  PID %s" % (who, pid.upper())
    if mi is not None:
        label += "  interface %s" % mi.upper()
    return label


def list_usb_printers():
    """Return the device-interface paths of all present USB printers."""
    paths = []
    hdev = setupapi.SetupDiGetClassDevsW(
        ctypes.byref(GUID_DEVINTERFACE_USBPRINT), None, None,
        DIGCF_PRESENT | DIGCF_DEVICEINTERFACE)
    if hdev == INVALID_HANDLE_VALUE:
        raise ctypes.WinError(ctypes.get_last_error())
    try:
        idx = 0
        while True:
            iface = SP_DEVICE_INTERFACE_DATA()
            iface.cbSize = ctypes.sizeof(SP_DEVICE_INTERFACE_DATA)
            if not setupapi.SetupDiEnumDeviceInterfaces(
                    hdev, None, ctypes.byref(GUID_DEVINTERFACE_USBPRINT),
                    idx, ctypes.byref(iface)):
                break

            need = wintypes.DWORD(0)
            setupapi.SetupDiGetDeviceInterfaceDetailW(
                hdev, ctypes.byref(iface), None, 0, ctypes.byref(need), None)
            buf = ctypes.create_string_buffer(need.value)
            # SP_DEVICE_INTERFACE_DETAIL_DATA_W.cbSize is 8 on x64, 6 on x86
            ctypes.memmove(buf, struct.pack(
                "I", 8 if ctypes.sizeof(ctypes.c_void_p) == 8 else 6), 4)
            if setupapi.SetupDiGetDeviceInterfaceDetailW(
                    hdev, ctypes.byref(iface), buf, need.value,
                    ctypes.byref(need), None):
                paths.append(ctypes.wstring_at(
                    ctypes.addressof(buf) + ctypes.sizeof(wintypes.DWORD)))
            idx += 1
    finally:
        setupapi.SetupDiDestroyDeviceInfoList(hdev)
    return paths


class UsbPrinter:
    """Bidirectional handle onto a USB printer device interface.

    Every read and write is synchronous, and usbprint.sys puts no time
    limit on either: a ReadFile against a printer that has stopped
    replying never returns. Seen in the wild as Pad Zero sitting on
    "Saving a backup" forever. So each call is guarded by a timer on
    another thread that calls CancelSynchronousIo on this one when the
    limit passes, which makes the stuck call fail with
    ERROR_OPERATION_ABORTED, and that is reported as PrinterSilent.

    The handle stays plain synchronous. Overlapped I/O would also give a
    timeout, but it changes every call's signature and cannot be tested
    here without the printer. The watchdog leaves the working path
    byte-for-byte as it was.
    """

    timeout = IO_TIMEOUT

    def __init__(self, path):
        self.path = path
        self._seq = 0
        self._dead = False
        self.h = kernel32.CreateFileW(
            path, GENERIC_READ | GENERIC_WRITE,
            FILE_SHARE_READ | FILE_SHARE_WRITE, None,
            OPEN_EXISTING, 0, None)
        if self.h == INVALID_HANDLE_VALUE:
            raise ctypes.WinError(ctypes.get_last_error())

    def _guarded(self, what, call):
        """Run call() (a ReadFile or WriteFile) under the watchdog.

        Returns True if the Win32 call succeeded. Raises PrinterSilent if
        the watchdog had to abort it, and OSError for any other failure.
        Once the printer has gone silent every later call fails at once:
        reinkpy's channel teardown does one more exchange on the way out,
        and it should not be waited for a second time.
        """
        if self._dead:
            raise PrinterSilent(
                "The printer stopped answering and has not come back.")

        self._seq += 1
        seq = self._seq
        fired = threading.Event()
        thread = kernel32.OpenThread(THREAD_TERMINATE, False,
                                     kernel32.GetCurrentThreadId())

        def abandon():
            # A timer that fires late, after this call has already
            # returned, must not abort whatever call comes next.
            if self._seq == seq and not self._dead:
                fired.set()
                kernel32.CancelSynchronousIo(thread)

        timer = threading.Timer(self.timeout, abandon)
        timer.daemon = True
        timer.start()
        try:
            ok = call()
            err = ctypes.get_last_error()
        finally:
            timer.cancel()
            if thread:
                kernel32.CloseHandle(thread)
        if ok:
            return True
        if fired.is_set() or err == ERROR_OPERATION_ABORTED:
            self._dead = True
            raise PrinterSilent(
                "The printer stopped answering: no reply to a %s for %d "
                "seconds." % (what, self.timeout))
        raise ctypes.WinError(err)

    def write(self, data: bytes) -> int:
        wrote = wintypes.DWORD(0)
        self._guarded("write", lambda: kernel32.WriteFile(
            self.h, data, len(data), ctypes.byref(wrote), None))
        return wrote.value

    def read(self, size=4096) -> bytes:
        buf = ctypes.create_string_buffer(size)
        got = wintypes.DWORD(0)
        self._guarded("read", lambda: kernel32.ReadFile(
            self.h, buf, size, ctypes.byref(got), None))
        return buf.raw[: got.value]

    def close(self):
        if self.h and self.h != INVALID_HANDLE_VALUE:
            kernel32.CloseHandle(self.h)
            self.h = None

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.close()


# ---------------------------------------------------------------- Epson
RKEY = 0x364A
WKEY = b"Maribaya"

INIT = b"\x1b@"
REMOTE_MODE = b"\x1b" + b"(R" + struct.pack("<H", 8) + b"\x00REMOTE1"
EXIT_REMOTE = b"\x1b\x00\x00\x00"


def caesar(key: bytes) -> bytes:
    return bytes(0 if b == 0 else b + 1 for b in key)


def factory(letter: str, payload: bytes, rkey: int = RKEY) -> bytes:
    c = ord(letter)
    head = struct.pack("<HBBB", rkey, c, ~c & 0xFF,
                       (c >> 1 & 0x7F) | (c << 7 & 0x80))
    body = head + payload
    return b"||" + struct.pack("<H", len(body)) + body


def remote(cmd: str, payload: bytes = b"") -> bytes:
    """Build a plain (non-factory) REMOTE1 command such as 'st'.

    Factory commands are the '||' ones built by factory(); these are the
    ordinary two-letter remote-mode commands, which are not key-protected.
    """
    return cmd.encode("ascii") + struct.pack("<H", len(payload)) + payload


def wrap(*cmds: bytes) -> bytes:
    return INIT + INIT + REMOTE_MODE + b"".join(cmds) + EXIT_REMOTE + INIT


def exchange(dev: UsbPrinter, data: bytes, want: bytes = b"", tries: int = 6):
    """
    Write `data`, then read repeatedly until `want` shows up.

    The printer keeps a queue of replies - the first ReadFile after a
    command often returns a previously buffered '@BDC ST2' status packet
    rather than the answer we just asked for. So we keep reading and
    accumulate until the marker appears or we run out of attempts.
    """
    dev.write(data)
    seen = b""
    for _ in range(tries):
        try:
            chunk = dev.read()
        except OSError:
            break
        if not chunk:
            continue
        seen += chunk
        if want and want in seen:
            break
    return seen


def status(dev: UsbPrinter, tries: int = 6) -> bytes:
    """Send the 'st' status query and return whatever came back.

    Every Epson answers 'st' with an '@BDC ST2' payload regardless of the
    read key, and regardless of whether EEPROM access is permitted. That
    makes it the one command that tests the *channel* rather than the key.
    """
    return exchange(dev, wrap(remote("st", b"\x01")), want=b"@BDC", tries=tries)


def check_channel(dev: UsbPrinter):
    """Preflight. Returns (alive, reply).

    alive=True means this interface really is a printer that talks back, so
    any later silence is the printer refusing a command rather than us
    holding a handle onto the wrong device.
    """
    reply = status(dev)
    return (b"@BDC" in reply), reply


def read_eeprom(dev: UsbPrinter, addr: int):
    reply = exchange(dev, wrap(factory("A", struct.pack("<H", addr))), want=b"EE:")
    m = re.search(r"EE:([0-9A-Fa-f]{6})", reply.decode("ascii", "replace"))
    if not m:
        return None, reply
    payload = m.group(1)
    echoed, value = int(payload[:4], 16), int(payload[4:], 16)
    return (value if echoed == addr else None), reply


def write_eeprom(dev: UsbPrinter, addr: int, value: int):
    cmd = wrap(factory("B", struct.pack("<HB", addr, value) + caesar(WKEY)))
    reply = exchange(dev, cmd, want=b":OK;")
    return (b":OK;" in reply), reply


if __name__ == "__main__":
    print("=" * 64)
    print("USB PRINTER DEVICE INTERFACES")
    print("=" * 64)
    try:
        paths = list_usb_printers()
    except OSError as e:
        sys.exit("SetupAPI enumeration failed: %s" % e)

    if not paths:
        sys.exit("No USB printers found. Is the cable connected, and is the "
                 "printer installed as a USB printer rather than a network one?")

    for i, p in enumerate(paths):
        print("  [%d] %s" % (i, describe(p)))
        print("      %s" % p)

    if not any(is_epson(p) for p in paths):
        print("")
        print("  NOTE: none of these are Epson (VID 04B8). Whatever this")
        print("  tool opens, it will not be your printer.")

    which = int(sys.argv[1]) if len(sys.argv) > 1 else 0
    addr = int(sys.argv[2]) if len(sys.argv) > 2 else 0

    print("")
    print("Opening [%d] %s ..." % (which, describe(paths[which])))
    try:
        dev = UsbPrinter(paths[which])
    except OSError as e:
        sys.exit("CreateFile failed: %s (the spooler may hold it exclusively)" % e)

    with dev:
        print("Opened OK.")
        print("")
        print("--- channel preflight ('st' status query) ---")
        alive, reply = check_channel(dev)
        print("  raw : %r" % reply[:200])
        if alive:
            print("")
            print("  Channel OK - the printer answered.")
        else:
            print("")
            print("  NO ANSWER. This interface accepted a handle but never")
            print("  replied, so it is almost certainly not your printer.")
            print("  Try the other index numbers listed above.")

        print("")
        print("--- read EEPROM[%d] ---" % addr)
        val, raw = read_eeprom(dev, addr)
        print("  raw : %r" % raw[:200])
        if val is None:
            txt = raw.decode("ascii", "replace")
            if ":NA;" in txt:
                print("")
                print("  Refused (:NA;) - channel fine, read key is wrong.")
                print("  This is the GOOD failure. Run find_key_usb.py next.")
            else:
                print("")
                print("  No EE: payload.")
        else:
            print("")
            print("  *** EEPROM[%d] = %d - USB BIDIRECTIONAL WORKS ***" % (addr, val))
