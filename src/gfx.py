"""Drawing and window helpers for Status Pet, using only what ships with Windows.

- Surface: a 32-bit premultiplied-alpha bitmap drawn with GDI+ (anti-aliased shapes,
  gradients, text). Its pixels live in a DIB section, so the window can show them directly.
- LayeredWindow: a borderless per-pixel-alpha window (UpdateLayeredWindow). Fully
  transparent pixels let clicks through; everything else belongs to the window.
The windows live on the Tk thread, so Tk's event loop dispatches their messages.
"""
import ctypes
import ctypes.wintypes as wt

gdiplus = ctypes.WinDLL("gdiplus")
user32 = ctypes.WinDLL("user32", use_last_error=True)
gdi32 = ctypes.WinDLL("gdi32", use_last_error=True)
kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)

VP, F, I, U32 = ctypes.c_void_p, ctypes.c_float, ctypes.c_int, ctypes.c_uint32
PVP = ctypes.POINTER(VP)

PARGB = 0x000E200B               # PixelFormat32bppPARGB
UNIT_PIXEL = 2
SMOOTH_AA, PIXEL_OFFSET_HALF, TEXT_AA_GRIDFIT = 4, 4, 3
LINECAP_ROUND, WRAP_TILE_FLIP_XY, FLUSH_SYNC = 2, 3, 1
CLIP_REPLACE, CLIP_INTERSECT = 0, 1
FMT_FLAGS = 0x1000 | 0x4000 | 0x0800   # no wrap, no clip, measure trailing spaces


class _StartupInput(ctypes.Structure):
    _fields_ = [("GdiplusVersion", U32), ("DebugEventCallback", VP),
                ("SuppressBackgroundThread", wt.BOOL), ("SuppressExternalCodecs", wt.BOOL)]


class PointF(ctypes.Structure):
    _fields_ = [("X", F), ("Y", F)]


class RectF(ctypes.Structure):
    _fields_ = [("X", F), ("Y", F), ("Width", F), ("Height", F)]


def _sig(name, *args):
    fn = getattr(gdiplus, name)
    fn.argtypes, fn.restype = list(args), I
    return fn


GdiplusStartup = _sig("GdiplusStartup", ctypes.POINTER(ctypes.c_size_t), ctypes.POINTER(_StartupInput), VP)
CreateBitmapFromScan0 = _sig("GdipCreateBitmapFromScan0", I, I, I, I, VP, PVP)
GetImageGraphicsContext = _sig("GdipGetImageGraphicsContext", VP, PVP)
SetSmoothingMode = _sig("GdipSetSmoothingMode", VP, I)
SetPixelOffsetMode = _sig("GdipSetPixelOffsetMode", VP, I)
SetTextRenderingHint = _sig("GdipSetTextRenderingHint", VP, I)
SetInterpolationMode = _sig("GdipSetInterpolationMode", VP, I)
GraphicsClear = _sig("GdipGraphicsClear", VP, U32)
CreateSolidFill = _sig("GdipCreateSolidFill", U32, PVP)
SetSolidFillColor = _sig("GdipSetSolidFillColor", VP, U32)
DeleteBrush = _sig("GdipDeleteBrush", VP)
FillRectangle = _sig("GdipFillRectangle", VP, VP, F, F, F, F)
FillEllipse = _sig("GdipFillEllipse", VP, VP, F, F, F, F)
CreatePen1 = _sig("GdipCreatePen1", U32, F, I, PVP)
SetPenColor = _sig("GdipSetPenColor", VP, U32)
SetPenWidth = _sig("GdipSetPenWidth", VP, F)
SetPenStartCap = _sig("GdipSetPenStartCap", VP, I)
SetPenEndCap = _sig("GdipSetPenEndCap", VP, I)
DeletePen = _sig("GdipDeletePen", VP)
DrawLine = _sig("GdipDrawLine", VP, VP, F, F, F, F)
CreatePath = _sig("GdipCreatePath", I, PVP)
ResetPath = _sig("GdipResetPath", VP)
AddPathArc = _sig("GdipAddPathArc", VP, F, F, F, F, F, F)
AddPathLine = _sig("GdipAddPathLine", VP, F, F, F, F)
AddPathBezier = _sig("GdipAddPathBezier", VP, F, F, F, F, F, F, F, F)
AddPathEllipse = _sig("GdipAddPathEllipse", VP, F, F, F, F)
StartPathFigure = _sig("GdipStartPathFigure", VP)
ClosePathFigure = _sig("GdipClosePathFigure", VP)
FillPath = _sig("GdipFillPath", VP, VP, VP)
DrawPath = _sig("GdipDrawPath", VP, VP, VP)
DeletePath = _sig("GdipDeletePath", VP)
CreateLineBrush = _sig("GdipCreateLineBrush", ctypes.POINTER(PointF), ctypes.POINTER(PointF), U32, U32, I, PVP)
CreatePathGradientFromPath = _sig("GdipCreatePathGradientFromPath", VP, PVP)
SetPathGradientCenterColor = _sig("GdipSetPathGradientCenterColor", VP, U32)
SetPathGradientSurroundColorsWithCount = _sig("GdipSetPathGradientSurroundColorsWithCount", VP,
                                              ctypes.POINTER(U32), ctypes.POINTER(I))
CreateFontFamilyFromName = _sig("GdipCreateFontFamilyFromName", ctypes.c_wchar_p, VP, PVP)
DeleteFontFamily = _sig("GdipDeleteFontFamily", VP)
CreateFont = _sig("GdipCreateFont", VP, F, I, I, PVP)
DeleteFont = _sig("GdipDeleteFont", VP)
StringFormatGetGenericTypographic = _sig("GdipStringFormatGetGenericTypographic", PVP)
CloneStringFormat = _sig("GdipCloneStringFormat", VP, PVP)
SetStringFormatFlags = _sig("GdipSetStringFormatFlags", VP, I)
DrawString = _sig("GdipDrawString", VP, ctypes.c_wchar_p, I, VP, ctypes.POINTER(RectF), VP, VP)
MeasureString = _sig("GdipMeasureString", VP, ctypes.c_wchar_p, I, VP, ctypes.POINTER(RectF), VP,
                     ctypes.POINTER(RectF), ctypes.POINTER(I), ctypes.POINTER(I))
SetClipRect = _sig("GdipSetClipRect", VP, F, F, F, F, I)
SetClipPath = _sig("GdipSetClipPath", VP, VP, I)
ResetClip = _sig("GdipResetClip", VP)
ScaleWorldTransform = _sig("GdipScaleWorldTransform", VP, F, F, I)
TranslateWorldTransform = _sig("GdipTranslateWorldTransform", VP, F, F, I)
ResetWorldTransform = _sig("GdipResetWorldTransform", VP)
DrawImageRectI = _sig("GdipDrawImageRectI", VP, VP, I, I, I, I)
Flush = _sig("GdipFlush", VP, I)
DeleteGraphics = _sig("GdipDeleteGraphics", VP)
DisposeImage = _sig("GdipDisposeImage", VP)

_token = ctypes.c_size_t()
_fmt = None


def startup():
    """Starts GDI+ once per process."""
    global _fmt
    if _token.value:
        return
    if GdiplusStartup(ctypes.byref(_token), ctypes.byref(_StartupInput(1, None, False, False)), None):
        raise OSError("GDI+ could not start")
    generic, fmt = VP(), VP()
    StringFormatGetGenericTypographic(ctypes.byref(generic))
    CloneStringFormat(generic, ctypes.byref(fmt))
    SetStringFormatFlags(fmt, FMT_FLAGS)
    _fmt = fmt


def argb(color, alpha=1.0):
    """'#RRGGBB' (+ opacity 0..1) -> 0xAARRGGBB."""
    a = max(0, min(255, round(alpha * 255)))
    return (a << 24) | int(color[1:7], 16)


class Font:
    _families = {}

    def __init__(self, family, px, bold=False):
        fam = Font._families.get(family)
        if fam is None:
            fam = VP()
            if CreateFontFamilyFromName(family, None, ctypes.byref(fam)):
                CreateFontFamilyFromName("Segoe UI", None, ctypes.byref(fam))   # fallback
            Font._families[family] = fam
        self.handle = VP()
        CreateFont(fam, px, 1 if bold else 0, UNIT_PIXEL, ctypes.byref(self.handle))
        self.px = px


# ---------- DIB + GDI+ surface ----------
class BITMAPINFOHEADER(ctypes.Structure):
    _fields_ = [("biSize", wt.DWORD), ("biWidth", wt.LONG), ("biHeight", wt.LONG), ("biPlanes", wt.WORD),
                ("biBitCount", wt.WORD), ("biCompression", wt.DWORD), ("biSizeImage", wt.DWORD),
                ("biXPelsPerMeter", wt.LONG), ("biYPelsPerMeter", wt.LONG), ("biClrUsed", wt.DWORD),
                ("biClrImportant", wt.DWORD)]


gdi32.CreateDIBSection.argtypes = [wt.HDC, ctypes.POINTER(BITMAPINFOHEADER), wt.UINT, PVP, wt.HANDLE, wt.DWORD]
gdi32.CreateDIBSection.restype = VP
gdi32.CreateCompatibleDC.argtypes = [VP]
gdi32.CreateCompatibleDC.restype = VP
gdi32.SelectObject.argtypes = [VP, VP]
gdi32.SelectObject.restype = VP
gdi32.DeleteObject.argtypes = [VP]
gdi32.DeleteDC.argtypes = [VP]


class Surface:
    """w x h device pixels. Draw in world units: set a scale with transform(), or reset() for device pixels."""

    def __init__(self, w, h):
        self.w, self.h = w, h
        bih = BITMAPINFOHEADER(ctypes.sizeof(BITMAPINFOHEADER), w, -h, 1, 32, 0, 0, 0, 0, 0, 0)
        self.bits = VP()
        self.hbmp = gdi32.CreateDIBSection(None, ctypes.byref(bih), 0, ctypes.byref(self.bits), None, 0)
        if not self.hbmp:
            raise OSError("could not create a bitmap")
        self.dc = gdi32.CreateCompatibleDC(None)
        self._old = gdi32.SelectObject(self.dc, self.hbmp)
        self.nbytes = w * h * 4
        self.bitmap, self.g = VP(), VP()
        CreateBitmapFromScan0(w, h, w * 4, PARGB, self.bits, ctypes.byref(self.bitmap))
        GetImageGraphicsContext(self.bitmap, ctypes.byref(self.g))
        SetSmoothingMode(self.g, SMOOTH_AA)
        SetPixelOffsetMode(self.g, PIXEL_OFFSET_HALF)
        SetTextRenderingHint(self.g, TEXT_AA_GRIDFIT)
        SetInterpolationMode(self.g, 5)          # nearest neighbour: images are copied 1:1
        self.brush, self.pen, self.path = VP(), VP(), VP()
        CreateSolidFill(0, ctypes.byref(self.brush))
        CreatePen1(0, 1.0, UNIT_PIXEL, ctypes.byref(self.pen))
        SetPenStartCap(self.pen, LINECAP_ROUND)
        SetPenEndCap(self.pen, LINECAP_ROUND)
        CreatePath(0, ctypes.byref(self.path))
        self._measure = {}

    # transforms and clipping
    def reset(self):
        ResetWorldTransform(self.g)

    def transform(self, scale, dx=0.0, dy=0.0):
        """World units: device = (world + (dx, dy)) * scale."""
        ResetWorldTransform(self.g)
        ScaleWorldTransform(self.g, scale, scale, 0)
        TranslateWorldTransform(self.g, dx, dy, 0)

    def clip_rect(self, x, y, w, h):
        SetClipRect(self.g, x, y, w, h, CLIP_REPLACE)

    def clip_round(self, x, y, w, h, r):
        self._round_path(x, y, w, h, r)
        SetClipPath(self.g, self.path, CLIP_REPLACE)

    def unclip(self):
        ResetClip(self.g)

    # pixels
    def clear(self, color=0):
        GraphicsClear(self.g, color)

    def save_to(self, buf):
        Flush(self.g, FLUSH_SYNC)
        ctypes.memmove(buf, self.bits, self.nbytes)

    def load_from(self, buf):
        ctypes.memmove(self.bits, buf, self.nbytes)

    def pixel(self, x, y):
        """(a, r, g, b) at device pixel x, y (premultiplied)."""
        Flush(self.g, FLUSH_SYNC)
        b, g, r, a = ctypes.string_at(self.bits.value + (y * self.w + x) * 4, 4)
        return a, r, g, b

    # shapes
    def rect(self, x, y, w, h, color):
        SetSolidFillColor(self.brush, color)
        FillRectangle(self.g, self.brush, x, y, w, h)

    def ellipse(self, cx, cy, rx, ry, color):
        SetSolidFillColor(self.brush, color)
        FillEllipse(self.g, self.brush, cx - rx, cy - ry, rx * 2, ry * 2)

    def _round_path(self, x, y, w, h, r):
        p = self.path
        ResetPath(p)
        r = max(0.01, min(r, w / 2, h / 2))
        d = r * 2
        AddPathArc(p, x, y, d, d, 180, 90)
        AddPathArc(p, x + w - d, y, d, d, 270, 90)
        AddPathArc(p, x + w - d, y + h - d, d, d, 0, 90)
        AddPathArc(p, x, y + h - d, d, d, 90, 90)
        ClosePathFigure(p)

    def round_rect(self, x, y, w, h, r, fill=None, stroke=None, width=1.0):
        self._round_path(x, y, w, h, r)
        if fill is not None:
            SetSolidFillColor(self.brush, fill)
            FillPath(self.g, self.brush, self.path)
        if stroke is not None:
            SetPenColor(self.pen, stroke)
            SetPenWidth(self.pen, width)
            DrawPath(self.g, self.pen, self.path)

    def line(self, x0, y0, x1, y1, color, width=1.0):
        SetPenColor(self.pen, color)
        SetPenWidth(self.pen, width)
        DrawLine(self.g, self.pen, x0, y0, x1, y1)

    def vgradient(self, x, y, w, h, top, bottom):
        brush = VP()
        CreateLineBrush(ctypes.byref(PointF(0, y)), ctypes.byref(PointF(0, y + h)), top, bottom,
                        WRAP_TILE_FLIP_XY, ctypes.byref(brush))
        FillRectangle(self.g, brush, x, y, w, h)
        DeleteBrush(brush)

    def glow(self, cx, cy, rx, ry, color):
        """Soft radial glow: color in the centre fading to transparent at the edge."""
        p = self.path
        ResetPath(p)
        AddPathEllipse(p, cx - rx, cy - ry, rx * 2, ry * 2)
        brush = VP()
        CreatePathGradientFromPath(p, ctypes.byref(brush))
        SetPathGradientCenterColor(brush, color)
        edge, n = U32(color & 0x00FFFFFF), I(1)
        SetPathGradientSurroundColorsWithCount(brush, ctypes.byref(edge), ctypes.byref(n))
        FillPath(self.g, brush, p)
        DeleteBrush(brush)

    def shape(self, start, segments, color):
        """Filled outline: start point, then ('L', x, y) lines and ('B', c1x, c1y, c2x, c2y, x, y) curves."""
        p = self.path
        ResetPath(p)
        StartPathFigure(p)
        cx, cy = start
        for seg in segments:
            if seg[0] == "L":
                AddPathLine(p, cx, cy, seg[1], seg[2])
                cx, cy = seg[1], seg[2]
            else:
                AddPathBezier(p, cx, cy, *seg[1:])
                cx, cy = seg[5], seg[6]
        ClosePathFigure(p)
        SetSolidFillColor(self.brush, color)
        FillPath(self.g, self.brush, p)

    def image(self, other, x, y):
        """Copies another surface onto this one at device pixel x, y (1:1)."""
        ResetWorldTransform(self.g)
        DrawImageRectI(self.g, other.bitmap, x, y, other.w, other.h)

    # text
    def measure(self, s, font):
        """Width and line height in world units (cached per font)."""
        key = (s, font.handle.value)
        m = self._measure.get(key)
        if m is None:
            box = RectF()
            MeasureString(self.g, s, len(s), font.handle, ctypes.byref(RectF(0, 0, 0, 0)), _fmt,
                          ctypes.byref(box), None, None)
            m = self._measure[key] = (box.Width, box.Height)
        return m

    def text(self, s, x, y, font, color, align="left"):
        """Draws s vertically centred on y; align: left / right / center (at x)."""
        w, h = self.measure(s, font)
        if align == "right":
            x -= w
        elif align == "center":
            x -= w / 2
        SetSolidFillColor(self.brush, color)
        DrawString(self.g, s, len(s), font.handle, ctypes.byref(RectF(x, y - h / 2, 0, 0)), _fmt, self.brush)
        return w

    def spaced(self, s, x, y, font, color, spacing):
        """Letter-spaced text (small uppercase labels)."""
        for ch in s:
            x += self.text(ch, x, y, font, color) + spacing

    def close(self):
        DeleteBrush(self.brush)
        DeletePen(self.pen)
        DeletePath(self.path)
        DeleteGraphics(self.g)
        DisposeImage(self.bitmap)
        gdi32.SelectObject(self.dc, self._old)
        gdi32.DeleteObject(self.hbmp)
        gdi32.DeleteDC(self.dc)


# ---------- per-pixel alpha window ----------
LRESULT = wt.LPARAM
WNDPROC = ctypes.WINFUNCTYPE(LRESULT, wt.HWND, wt.UINT, wt.WPARAM, wt.LPARAM)


class WNDCLASSW(ctypes.Structure):
    _fields_ = [("style", wt.UINT), ("lpfnWndProc", WNDPROC), ("cbClsExtra", I), ("cbWndExtra", I),
                ("hInstance", wt.HINSTANCE), ("hIcon", wt.HICON), ("hCursor", wt.HANDLE),
                ("hbrBackground", wt.HBRUSH), ("lpszMenuName", wt.LPCWSTR), ("lpszClassName", wt.LPCWSTR)]


class BLENDFUNCTION(ctypes.Structure):
    _fields_ = [("op", ctypes.c_ubyte), ("flags", ctypes.c_ubyte), ("alpha", ctypes.c_ubyte), ("fmt", ctypes.c_ubyte)]


class MONITORINFO(ctypes.Structure):
    _fields_ = [("cbSize", wt.DWORD), ("rcMonitor", wt.RECT), ("rcWork", wt.RECT), ("dwFlags", wt.DWORD)]


user32.RegisterClassW.argtypes = [ctypes.POINTER(WNDCLASSW)]
user32.RegisterClassW.restype = wt.ATOM
user32.CreateWindowExW.argtypes = [wt.DWORD, wt.LPCWSTR, wt.LPCWSTR, wt.DWORD, I, I, I, I, wt.HWND, wt.HMENU,
                                   wt.HINSTANCE, wt.LPVOID]
user32.CreateWindowExW.restype = wt.HWND
user32.DefWindowProcW.argtypes = [wt.HWND, wt.UINT, wt.WPARAM, wt.LPARAM]
user32.DefWindowProcW.restype = LRESULT
user32.DestroyWindow.argtypes = [wt.HWND]
user32.ShowWindow.argtypes = [wt.HWND, I]
user32.SetWindowPos.argtypes = [wt.HWND, wt.HWND, I, I, I, I, wt.UINT]
user32.UpdateLayeredWindow.argtypes = [wt.HWND, VP, ctypes.POINTER(wt.POINT), ctypes.POINTER(wt.SIZE), VP,
                                       ctypes.POINTER(wt.POINT), wt.DWORD, ctypes.POINTER(BLENDFUNCTION), wt.DWORD]
user32.UpdateLayeredWindow.restype = wt.BOOL
user32.GetDC.argtypes = [wt.HWND]
user32.GetDC.restype = VP
user32.SetCapture.argtypes = [wt.HWND]
user32.LoadCursorW.argtypes = [wt.HINSTANCE, VP]
user32.LoadCursorW.restype = VP
user32.SetCursor.argtypes = [VP]
user32.MonitorFromPoint.argtypes = [wt.POINT, wt.DWORD]
user32.MonitorFromPoint.restype = VP
user32.GetMonitorInfoW.argtypes = [VP, ctypes.POINTER(MONITORINFO)]
kernel32.GetModuleHandleW.argtypes = [wt.LPCWSTR]
kernel32.GetModuleHandleW.restype = wt.HMODULE

WS_POPUP = 0x80000000
WS_EX_LAYERED, WS_EX_TOOLWINDOW, WS_EX_TOPMOST, WS_EX_NOACTIVATE = 0x80000, 0x80, 0x8, 0x08000000
WS_EX_TRANSPARENT, GWL_EXSTYLE = 0x20, -20         # click-through: the mouse goes to the window underneath
user32.GetWindowLongPtrW.argtypes = [VP, ctypes.c_int]
user32.GetWindowLongPtrW.restype = ctypes.c_ssize_t
user32.SetWindowLongPtrW.argtypes = [VP, ctypes.c_int, ctypes.c_ssize_t]
user32.SetWindowLongPtrW.restype = ctypes.c_ssize_t
SWP_NOSIZE, SWP_NOMOVE, SWP_NOZORDER, SWP_NOACTIVATE = 0x1, 0x2, 0x4, 0x10
HWND_TOPMOST, HWND_NOTOPMOST = -1, -2
SW_HIDE, SW_SHOWNOACTIVATE = 0, 4
WM_MOUSEMOVE, WM_LBUTTONDOWN, WM_LBUTTONUP, WM_RBUTTONUP = 0x200, 0x201, 0x202, 0x205
WM_SETCURSOR, WM_MOUSEACTIVATE, MA_NOACTIVATE = 0x20, 0x21, 3
CURSORS = {"arrow": 32512, "hand": 32649, "nwse": 32642, "we": 32644}
CLASS_NAME = "StatusPetWindow"
_windows = {}                     # hwnd -> LayeredWindow


@WNDPROC
def _wndproc(hwnd, msg, wparam, lparam):
    win = _windows.get(hwnd)
    if win is not None:
        try:
            r = win.on_message(msg, wparam, lparam)
            if r is not None:
                return r
        except Exception:          # never let a Python error escape into Windows
            import traceback
            traceback.print_exc()
    return user32.DefWindowProcW(hwnd, msg, wparam, lparam)


_registered = False
_screen_dc = None


def _register():
    global _registered, _screen_dc
    if _registered:
        return
    wc = WNDCLASSW(lpfnWndProc=_wndproc, hInstance=kernel32.GetModuleHandleW(None), lpszClassName=CLASS_NAME,
                   hCursor=user32.LoadCursorW(None, VP(CURSORS["arrow"])))
    user32.RegisterClassW(ctypes.byref(wc))
    _screen_dc = user32.GetDC(None)
    _registered = True


def mouse_xy(lparam):
    """Client coordinates packed in a mouse message (signed 16-bit each)."""
    return ctypes.c_short(lparam & 0xFFFF).value, ctypes.c_short((lparam >> 16) & 0xFFFF).value


def cursor_pos():
    pt = wt.POINT()
    user32.GetCursorPos(ctypes.byref(pt))
    return pt.x, pt.y


def set_cursor(kind):
    user32.SetCursor(user32.LoadCursorW(None, VP(CURSORS[kind])))


user32.GetWindow.argtypes = [VP, wt.UINT]
user32.GetWindow.restype = VP
user32.GetWindowRect.argtypes = [VP, ctypes.POINTER(wt.RECT)]
user32.IsWindowVisible.argtypes = [VP]
user32.GetClassNameW.argtypes = [VP, wt.LPWSTR, ctypes.c_int]
user32.GetParent.argtypes = [VP]
user32.GetParent.restype = VP
TASKBAR_CLASSES = ("Shell_TrayWnd", "Shell_SecondaryTrayWnd")


def tk_hwnd(widget):
    """The real window handle of a Tk Toplevel (Tk's winfo_id is the inner client window)."""
    return user32.GetParent(widget.winfo_id())


def taskbar_above(hwnd):
    """True if a Windows taskbar sits above this window in the z-order AND overlaps it.
    Menus, tooltips and dialogs above it don't count, so re-raising only when this is True never covers them."""
    r = wt.RECT()
    if not hwnd or not user32.GetWindowRect(hwnd, ctypes.byref(r)):
        return False
    h, buf, tr = user32.GetWindow(hwnd, 3), ctypes.create_unicode_buffer(32), wt.RECT()   # 3 = GW_HWNDPREV
    for _ in range(200):                  # only windows above ours; the topmost band is short
        if not h:
            return False
        if user32.IsWindowVisible(h) and user32.GetClassNameW(h, buf, 32) and buf.value in TASKBAR_CLASSES \
                and user32.GetWindowRect(h, ctypes.byref(tr)) \
                and tr.left < r.right and r.left < tr.right and tr.top < r.bottom and r.top < tr.bottom:
            return True
        h = user32.GetWindow(h, 3)
    return False


def work_area(x, y):
    """(left, top, right, bottom) of the work area of the monitor nearest to the point."""
    mi = MONITORINFO(cbSize=ctypes.sizeof(MONITORINFO))
    user32.GetMonitorInfoW(user32.MonitorFromPoint(wt.POINT(int(x), int(y)), 2), ctypes.byref(mi))
    r = mi.rcWork
    return r.left, r.top, r.right, r.bottom


class LayeredWindow:
    """on_message(msg, wparam, lparam) -> result or None (default handling)."""

    def __init__(self, on_message, topmost=True, title="Status Pet"):
        _register()
        self.on_message = on_message
        ex = WS_EX_LAYERED | WS_EX_TOOLWINDOW | WS_EX_NOACTIVATE | (WS_EX_TOPMOST if topmost else 0)
        self.hwnd = user32.CreateWindowExW(ex, CLASS_NAME, title, WS_POPUP, 0, 0, 1, 1, None, None,
                                           kernel32.GetModuleHandleW(None), None)
        if not self.hwnd:
            raise OSError("could not create the gadget window")
        _windows[self.hwnd] = self
        self.x = self.y = self.w = self.h = 0
        self.visible = False
        self._blend = BLENDFUNCTION(0, 0, 255, 1)   # AC_SRC_OVER, per-pixel alpha

    def show(self, surface, x, y):
        """Puts the surface's pixels on screen with its top-left at device x, y."""
        self.x, self.y, self.w, self.h = int(x), int(y), surface.w, surface.h
        Flush(surface.g, FLUSH_SYNC)
        user32.UpdateLayeredWindow(self.hwnd, _screen_dc, ctypes.byref(wt.POINT(self.x, self.y)),
                                   ctypes.byref(wt.SIZE(surface.w, surface.h)), surface.dc,
                                   ctypes.byref(wt.POINT(0, 0)), 0, ctypes.byref(self._blend), 2)
        if not self.visible:
            user32.ShowWindow(self.hwnd, SW_SHOWNOACTIVATE)
            self.visible = True

    def move(self, x, y):
        self.x, self.y = int(x), int(y)
        user32.SetWindowPos(self.hwnd, None, self.x, self.y, 0, 0, SWP_NOSIZE | SWP_NOZORDER | SWP_NOACTIVATE)

    def hide(self):
        if self.visible:
            user32.ShowWindow(self.hwnd, SW_HIDE)
            self.visible = False

    def set_topmost(self, on):
        user32.SetWindowPos(self.hwnd, HWND_TOPMOST if on else HWND_NOTOPMOST, 0, 0, 0, 0,
                            SWP_NOMOVE | SWP_NOSIZE | SWP_NOACTIVATE)

    def set_click_through(self, on):
        """On: the window ignores the mouse; clicks and hovering reach whatever is underneath."""
        ex = user32.GetWindowLongPtrW(self.hwnd, GWL_EXSTYLE)
        user32.SetWindowLongPtrW(self.hwnd, GWL_EXSTYLE, ex | WS_EX_TRANSPARENT if on else ex & ~WS_EX_TRANSPARENT)

    def capture(self, on):
        if on:
            user32.SetCapture(self.hwnd)
        else:
            user32.ReleaseCapture()

    def contains(self, x, y, pad=0):
        return self.visible and self.x - pad <= x < self.x + self.w + pad and self.y - pad <= y < self.y + self.h + pad

    def destroy(self):
        if self.hwnd:
            _windows.pop(self.hwnd, None)
            user32.DestroyWindow(self.hwnd)
            self.hwnd = None
