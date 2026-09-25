"""Regression test: real mouse input must not crash Status Pet.

Windows SENDS WM_SETCURSOR / WM_MOUSEMOVE while Tk waits for events. If the window code calls
Tk from there, tkinter's thread state breaks and Python aborts (0xc0000409). This sends those
messages from another thread, like a real mouse, to the gadget running OFF SCREEN for 4 seconds.
Passes if the process exits normally.
"""
import ctypes, importlib.machinery, importlib.util, os, sys, threading, time

PROJECT = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "src")   # the app
sys.path.insert(0, PROJECT)
ctypes.windll.shcore.SetProcessDpiAwareness(1)
import gfx  # noqa: E402

gfx.work_area = lambda x, y: (-9000, -9000, -6000, -6000)
loader = importlib.machinery.SourceFileLoader("sgp", os.path.join(PROJECT, "status_pet.pyw"))
spec = importlib.util.spec_from_loader("sgp", loader)
sgp = importlib.util.module_from_spec(spec)
loader.exec_module(sgp)
sgp.SETTINGS_PATH = os.path.join(os.environ["TEMP"], "sgp_hover_test.json")

g = sgp.Gadget()
g.win.move(-8000, -8000)
hwnd = g.win.hwnd
u = ctypes.windll.user32
u.SendMessageW.argtypes = [ctypes.c_void_p, ctypes.c_uint, ctypes.c_size_t, ctypes.c_ssize_t]
u.SendMessageW.restype = ctypes.c_ssize_t
sent = [0]


def inside():                                             # the "real" cursor sits on the panel
    l, t, r, b = g.panel_rect()
    return int((l + r) / 2), int(t + 20)


gfx.cursor_pos = inside


def click(x, y):
    lp = (round(g.dev(y)) << 16) | round(g.dev(x))
    u.SendMessageW(hwnd, 0x201, 1, lp)                      # WM_LBUTTONDOWN
    u.SendMessageW(hwnd, 0x202, 0, lp)                      # WM_LBUTTONUP
    sent[0] += 2


def mouse():
    time.sleep(.8)
    end = time.time() + 4
    x, y = round(g.dev(g.gw() / 2)), round(g.dev(g.cur_h() - 8))
    n = 0
    while time.time() < end:
        u.SendMessageW(hwnd, 0x20, hwnd, 1 | (0x200 << 16))     # WM_SETCURSOR over the client area
        u.SendMessageW(hwnd, 0x200, 0, (y << 16) | x)           # WM_MOUSEMOVE
        sent[0] += 2
        n += 1
        if n % 60 == 0:                                         # now and then: gear, a number, the stage
            click(g._gear_x() + GB_CENTRE, sgp.VB_Y + 8)
            click(g.W - 30, g.yard_bottom + 20)
            click(40, 30)
            clicks[0] += 3
        time.sleep(.004)


GB_CENTRE = sgp.GB_W / 2
clicks = [0]


threading.Thread(target=mouse, daemon=True).start()
g.root.after(5500, g.quit)
g.run()
print(f"PASS: survived {sent[0]} mouse messages ({clicks[0]} clicks); RAM as % = {g.v_pct}, "
      f"Settings open = {g.settings_win is not None}")
