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
    """Bidirectional handle onto a USB printer device interface."""

    def __init__(self, path):
        self.path = path
        self.h = kernel32.CreateFileW(
            path, GENERIC_READ | GENERIC_WRITE,
            FILE_SHARE_READ | FILE_SHARE_WRITE, None,
            OPEN_EXISTING, 0, None)
        if self.h == INVALID_HANDLE_VALUE:
            raise ctypes.WinError(ctypes.get_last_error())

    def write(self, data: bytes) -> int:
        wrote = wintypes.DWORD(0)
        if not kernel32.WriteFile(self.h, data, len(data),
                                  ctypes.byref(wrote), None):
            raise ctypes.WinError(ctypes.get_last_error())
        return wrote.value

    def read(self, size=4096) -> bytes:
        buf = ctypes.create_string_buffer(size)
        got = wintypes.DWORD(0)
        if not kernel32.ReadFile(self.h, buf, size, ctypes.byref(got), None):
            raise ctypes.WinError(ctypes.get_last_error())
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
        sys.exit("No USB printers found. Is the cable connected?")

    for i, p in enumerate(paths):
        print("  [%d] %s" % (i, p))

    which = int(sys.argv[1]) if len(sys.argv) > 1 else 0
    addr = int(sys.argv[2]) if len(sys.argv) > 2 else 0

    print("\nOpening [%d] ..." % which)
    try:
        dev = UsbPrinter(paths[which])
    except OSError as e:
        sys.exit("CreateFile failed: %s\n(The spooler may hold it exclusively.)" % e)

    with dev:
        print("Opened OK.\n")
        print("--- read EEPROM[%d] ---" % addr)
        val, raw = read_eeprom(dev, addr)
        print("  raw : %r" % raw[:200])
        if val is None:
            txt = raw.decode("ascii", "replace")
            if ":NA;" in txt:
                print("\n  Refused (:NA;) over USB as well.")
            else:
                print("\n  No EE: payload.")
        else:
            print("\n  *** EEPROM[%d] = %d - USB BIDIRECTIONAL WORKS ***" % (addr, val))
