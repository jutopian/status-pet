"""Notification-area ("tray") icon: shows the gadget is running; right-click it to quit.

Pure ctypes, no installs. The icon's hidden window lives on the Tk thread, and Tk's own
event loop dispatches its messages, so there is no extra thread and no polling.
"""
import ctypes
import ctypes.wintypes as wt
import math

user32 = ctypes.WinDLL("user32", use_last_error=True)
gdi32 = ctypes.WinDLL("gdi32", use_last_error=True)
shell32 = ctypes.WinDLL("shell32", use_last_error=True)
kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)

LRESULT = wt.LPARAM
WNDPROC = ctypes.WINFUNCTYPE(LRESULT, wt.HWND, wt.UINT, wt.WPARAM, wt.LPARAM)

NIM_ADD, NIM_MODIFY, NIM_DELETE = 0, 1, 2
NIF_MESSAGE, NIF_ICON, NIF_TIP = 1, 2, 4
WM_NULL, WM_CONTEXTMENU, WM_RBUTTONUP, WM_APP = 0x0000, 0x007B, 0x0205, 0x8000
TPM_RIGHTBUTTON, TPM_BOTTOMALIGN, TPM_NONOTIFY, TPM_RETURNCMD = 0x0002, 0x0020, 0x0080, 0x0100
ERROR_CLASS_ALREADY_EXISTS = 1410
CMD_QUIT, CMD_LOCK, CMD_UPDATE = 1, 2, 3
CLASS_NAME = "StatusPetTray"


class WNDCLASSW(ctypes.Structure):
    _fields_ = [("style", wt.UINT), ("lpfnWndProc", WNDPROC), ("cbClsExtra", ctypes.c_int),
                ("cbWndExtra", ctypes.c_int), ("hInstance", wt.HINSTANCE), ("hIcon", wt.HICON),
                ("hCursor", wt.HANDLE), ("hbrBackground", wt.HBRUSH), ("lpszMenuName", wt.LPCWSTR),
                ("lpszClassName", wt.LPCWSTR)]


class NOTIFYICONDATAW(ctypes.Structure):
    _fields_ = [("cbSize", wt.DWORD), ("hWnd", wt.HWND), ("uID", wt.UINT), ("uFlags", wt.UINT),
                ("uCallbackMessage", wt.UINT), ("hIcon", wt.HICON), ("szTip", wt.WCHAR * 128),
                ("dwState", wt.DWORD), ("dwStateMask", wt.DWORD), ("szInfo", wt.WCHAR * 256),
                ("uVersion", wt.UINT), ("szInfoTitle", wt.WCHAR * 64), ("dwInfoFlags", wt.DWORD),
                ("guidItem", ctypes.c_byte * 16), ("hBalloonIcon", wt.HICON)]


class BITMAPINFOHEADER(ctypes.Structure):
    _fields_ = [("biSize", wt.DWORD), ("biWidth", wt.LONG), ("biHeight", wt.LONG), ("biPlanes", wt.WORD),
                ("biBitCount", wt.WORD), ("biCompression", wt.DWORD), ("biSizeImage", wt.DWORD),
                ("biXPelsPerMeter", wt.LONG), ("biYPelsPerMeter", wt.LONG), ("biClrUsed", wt.DWORD),
                ("biClrImportant", wt.DWORD)]


class ICONINFO(ctypes.Structure):
    _fields_ = [("fIcon", wt.BOOL), ("xHotspot", wt.DWORD), ("yHotspot", wt.DWORD),
                ("hbmMask", wt.HBITMAP), ("hbmColor", wt.HBITMAP)]


user32.RegisterClassW.argtypes = [ctypes.POINTER(WNDCLASSW)]
user32.RegisterClassW.restype = wt.ATOM
user32.CreateWindowExW.argtypes = [wt.DWORD, wt.LPCWSTR, wt.LPCWSTR, wt.DWORD, ctypes.c_int, ctypes.c_int,
                                   ctypes.c_int, ctypes.c_int, wt.HWND, wt.HMENU, wt.HINSTANCE, wt.LPVOID]
user32.CreateWindowExW.restype = wt.HWND
user32.DefWindowProcW.argtypes = [wt.HWND, wt.UINT, wt.WPARAM, wt.LPARAM]
user32.DefWindowProcW.restype = LRESULT
user32.DestroyWindow.argtypes = [wt.HWND]
user32.RegisterWindowMessageW.argtypes = [wt.LPCWSTR]
user32.RegisterWindowMessageW.restype = wt.UINT
user32.CreatePopupMenu.restype = wt.HMENU
user32.AppendMenuW.argtypes = [wt.HMENU, wt.UINT, ctypes.c_size_t, wt.LPCWSTR]
user32.TrackPopupMenu.argtypes = [wt.HMENU, wt.UINT, ctypes.c_int, ctypes.c_int, ctypes.c_int, wt.HWND, wt.LPVOID]
user32.TrackPopupMenu.restype = ctypes.c_int
user32.DestroyMenu.argtypes = [wt.HMENU]
user32.SetMenuDefaultItem.argtypes = [wt.HMENU, wt.UINT, wt.UINT]
user32.SetForegroundWindow.argtypes = [wt.HWND]
user32.PostMessageW.argtypes = [wt.HWND, wt.UINT, wt.WPARAM, wt.LPARAM]
user32.CreateIconIndirect.argtypes = [ctypes.POINTER(ICONINFO)]
user32.CreateIconIndirect.restype = wt.HICON
user32.DestroyIcon.argtypes = [wt.HICON]
gdi32.CreateDIBSection.argtypes = [wt.HDC, ctypes.POINTER(BITMAPINFOHEADER), wt.UINT,
                                   ctypes.POINTER(ctypes.c_void_p), wt.HANDLE, wt.DWORD]
gdi32.CreateDIBSection.restype = wt.HBITMAP
gdi32.CreateBitmap.argtypes = [ctypes.c_int, ctypes.c_int, wt.UINT, wt.UINT, wt.LPVOID]
gdi32.CreateBitmap.restype = wt.HBITMAP
gdi32.DeleteObject.argtypes = [wt.HANDLE]
shell32.Shell_NotifyIconW.argtypes = [wt.DWORD, ctypes.POINTER(NOTIFYICONDATAW)]
shell32.Shell_NotifyIconW.restype = wt.BOOL
kernel32.GetModuleHandleW.argtypes = [wt.LPCWSTR]
kernel32.GetModuleHandleW.restype = wt.HMODULE


def _grid_pixels(grid, s):
    """Pixel art (rows of '#RRGGBB' / None) as s*s top-down BGRA pixels: whole-pixel scale, centred, crisp."""
    h, w = len(grid), max(len(r) for r in grid)
    k = max(1, min(s // w, s // h))
    ox, oy = (s - w * k) // 2, (s - h * k) // 2
    buf = bytearray(s * s * 4)
    for y, row in enumerate(grid):
        for x, col in enumerate(row):
            if not col:
                continue
            px = bytes((int(col[5:7], 16), int(col[3:5], 16), int(col[1:3], 16), 255))
            for yy in range(oy + y * k, min(s, oy + y * k + k)):
                for xx in range(ox + x * k, min(s, ox + x * k + k)):
                    if 0 <= yy and 0 <= xx:
                        i = (yy * s + xx) * 4
                        buf[i:i + 4] = px
    return bytes(buf)


def _make_icon(pixels_for):
    """pixels_for(size) -> BGRA bytes."""
    s = user32.GetSystemMetrics(49)            # SM_CXSMICON: tray icon size at the current DPI
    bih = BITMAPINFOHEADER(ctypes.sizeof(BITMAPINFOHEADER), s, -s, 1, 32, 0, 0, 0, 0, 0, 0)
    bits = ctypes.c_void_p()
    color = gdi32.CreateDIBSection(None, ctypes.byref(bih), 0, ctypes.byref(bits), None, 0)
    if not color:
        return None
    pixels = pixels_for(s)
    ctypes.memmove(bits, pixels, len(pixels))
    mask = gdi32.CreateBitmap(s, s, 1, 1, None)  # unused: the color bitmap's alpha decides
    icon = user32.CreateIconIndirect(ctypes.byref(ICONINFO(True, 0, 0, mask, color)))
    gdi32.DeleteObject(mask)
    gdi32.DeleteObject(color)
    return icon


class TrayIcon:
    """Adds the icon on creation; call remove() before the program exits."""

    def __init__(self, tip, grid, on_quit, on_lock=None, on_update=None):
        self.on_quit = on_quit
        self.on_lock = on_lock                 # given: the menu also has Lock / Unlock (see set_locked)
        self.on_update = on_update             # called by the "Update available" line
        self.update_text = None                # that line's text while a newer version is out, else None
        self.locked = False
        self.labels = {"lock": "Lock (click-through)", "unlock": "Unlock", "quit": "Quit {tip}",
                       "locked": "{tip} (locked)"}    # shown texts; the app swaps in its language's
        # set before the window exists: Windows calls _proc during CreateWindowExW
        self.callback_msg = WM_APP + 1
        self.taskbar_created = user32.RegisterWindowMessageW("TaskbarCreated")   # Explorer restarted
        self._proc_ref = WNDPROC(self._proc)   # keep the callback alive as long as the window
        hinst = kernel32.GetModuleHandleW(None)
        wc = WNDCLASSW(lpfnWndProc=self._proc_ref, hInstance=hinst, lpszClassName=CLASS_NAME)
        if not user32.RegisterClassW(ctypes.byref(wc)) and ctypes.get_last_error() != ERROR_CLASS_ALREADY_EXISTS:
            raise OSError("could not register the tray window class")
        self.tip = tip
        self.hwnd = user32.CreateWindowExW(0, CLASS_NAME, tip, 0, 0, 0, 0, 0, None, None, hinst, None)
        if not self.hwnd:
            raise OSError("could not create the tray window")
        self.icon = _make_icon(lambda s: _grid_pixels(grid, s))   # grid: the first picture (see set_image)
        self.nid = NOTIFYICONDATAW(cbSize=ctypes.sizeof(NOTIFYICONDATAW), hWnd=self.hwnd, uID=1,
                                   uFlags=NIF_MESSAGE | NIF_ICON | NIF_TIP,
                                   uCallbackMessage=self.callback_msg, hIcon=self.icon, szTip=tip)
        self.shown = bool(shell32.Shell_NotifyIconW(NIM_ADD, ctypes.byref(self.nid)))

    def _proc(self, hwnd, msg, wparam, lparam):
        if msg == self.callback_msg:
            if lparam & 0xFFFF in (WM_RBUTTONUP, WM_CONTEXTMENU):
                self._menu()
            return 0
        if msg == self.taskbar_created:
            self.shown = bool(shell32.Shell_NotifyIconW(NIM_ADD, ctypes.byref(self.nid)))
            return 0
        return user32.DefWindowProcW(hwnd, msg, wparam, lparam)

    def _menu(self):
        pt = wt.POINT()
        user32.GetCursorPos(ctypes.byref(pt))
        menu = user32.CreatePopupMenu()
        if self.update_text and self.on_update:           # on top, bold (the menu's default item)
            user32.AppendMenuW(menu, 0, CMD_UPDATE, self.update_text)
            user32.SetMenuDefaultItem(menu, CMD_UPDATE, 0)
            user32.AppendMenuW(menu, 0x800, 0, None)
        if self.on_lock:
            user32.AppendMenuW(menu, 0, CMD_LOCK, self.labels["unlock" if self.locked else "lock"])
            user32.AppendMenuW(menu, 0x800, 0, None)        # MF_SEPARATOR
        user32.AppendMenuW(menu, 0, CMD_QUIT, self.labels["quit"].format(tip=self.tip))
        user32.SetForegroundWindow(self.hwnd)  # lets the menu close when clicking elsewhere
        cmd = user32.TrackPopupMenu(menu, TPM_RIGHTBUTTON | TPM_BOTTOMALIGN | TPM_NONOTIFY | TPM_RETURNCMD,
                                    pt.x, pt.y, 0, self.hwnd, None)
        user32.DestroyMenu(menu)
        user32.PostMessageW(self.hwnd, WM_NULL, 0, 0)
        if cmd == CMD_QUIT:
            self.on_quit()
        elif cmd == CMD_LOCK:
            self.on_lock()
        elif cmd == CMD_UPDATE:
            self.on_update()

    def set_locked(self, on):
        """The menu offers Unlock while locked, and the tooltip says "(locked)"."""
        self.locked = on
        self.nid.szTip = self.labels["locked"].format(tip=self.tip) if on else self.tip
        if self.shown:
            shell32.Shell_NotifyIconW(NIM_MODIFY, ctypes.byref(self.nid))

    def set_image(self, grid):
        """Swaps the icon for pixel art (rows of '#RRGGBB' / None), e.g. the gadget's current pet."""
        icon = _make_icon(lambda s: _grid_pixels(grid, s))
        if not icon or not self.hwnd:
            return
        old, self.icon = self.icon, icon
        self.nid.hIcon = icon
        if self.shown:
            shell32.Shell_NotifyIconW(NIM_MODIFY, ctypes.byref(self.nid))
        if old:
            user32.DestroyIcon(old)

    def remove(self):
        if self.hwnd:
            shell32.Shell_NotifyIconW(NIM_DELETE, ctypes.byref(self.nid))
            if self.icon:
                user32.DestroyIcon(self.icon)
            user32.DestroyWindow(self.hwnd)
            self.hwnd = None
