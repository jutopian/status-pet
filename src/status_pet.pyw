"""Status Pet - a pet-first, always-on-top system monitor.

Double-click to run. Point at the gadget for the view buttons (top-left) and the gear
(top-right, Settings). Drag to move, drag the bottom-right corner to resize, right-click for
the menu. Settings are saved in settings.json next to this file.

How it draws (see gfx.py):
- The gadget is a per-pixel-alpha window drawn with GDI+: smooth rounded corners, a soft
  shadow and real transparency (the one-line pet strip, the transparent-background option).
- The panel, the baked stage (sky, hills, ground) and the status rows form ONE cached base
  image, rebuilt only when a number, the size or the time of day changes. Each frame copies
  that base (a single memory copy) and draws only the pet, its effects and hover controls.
- About 30 fps while something moves; when everything is still the loop idles at 4 fps
  (12 fps at night, for the fireflies). Numbers and apps are read once a second.
"""
import ctypes
import math
import os
import random
import shutil
import sys
import time
import tkinter as tk
import tkinter.font as tkfont

import autostart
import gfx
from gadget_content import GadgetContentMixin
from gadget_move import GadgetMoveMixin
from gadget_pose import GadgetPoseMixin
from gadget_settings import GadgetSettingsMixin
import hats as hatlib
import i18n
import sprites as sp
import sprites_ghost as spg
import sprites_halloween as sph
import sprites_pumpkin as spp
from gfx import argb
from i18n import tr
from metrics import AppMonitor, GpuMonitor, SystemCpu, read_ram
from settings_ui import VERSION, SettingsUI
from tray import TrayIcon
from update_check import UpdateCheck, open_page

HERE = os.path.dirname(os.path.abspath(__file__))
SCRIPT = os.path.join(HERE, "status_pet.pyw")     # what "Start with Windows" runs (the .exe when installed)
APP_NAME = "Status Pet"                                  # the name people see
FROZEN = getattr(sys, "frozen", False)                   # the installed .exe (PyInstaller); else the .pyw
# Settings, the log and the hats folder: next to the script, or in the user's AppData when installed
# (the install folder may not be writable, and every Windows user gets their own settings).
DATA = os.path.join(os.environ.get("LOCALAPPDATA", HERE), APP_NAME) if FROZEN else HERE
SETTINGS_PATH = os.path.join(DATA, "settings.json")

# ---------- sizes (logical pixels; multiplied by the DPI scale on screen) ----------
W_MIN, W_MAX, W_DEF = 240, 400, 300
YH_MIN, YH_MAX, YH_DEF = 56, 130, 80
ROWS_FULL, ROWS_COMPACT, APP_ROW = 108, 32, 22
LINE_H, LINE_L, LINE_R, ITEM_GAP = 28, 14, 20, 12   # one-line bar: height, left padding, handle, gap
LZ_H = 40                       # one-line view with the pet: see-through strip above the bar
SZ_MIN, SZ_MAX = 75, 150        # status size in percent (rows only; not the pet or the stage)
SIZE_BASE = 1.05                # what 100% means: the old 105% is the new 100%
HEAD_TOP = 0                    # the slime's head-top row: hats sit on it (see hat_cells)
# How far a pet's body sits from the slime's top row: the pumpkin stands on the ground without feet (one row
# lower), the ghost floats with a hem instead of feet (one row higher).
PET_DY = {"pumpkin": spp.TOP, "ghost": spg.TOP}
MARGIN = 10                     # transparent margin around the panel: room for the soft shadow
XMIN = 22                       # pet walking range: XMIN .. width - XMIN
VB_X, VB_Y, VB_W, VB_H = 14, 14, 16, 16     # hover view buttons (top-left of the stage)
GB_W, GB_H = 20, 16                         # hover gear button (top-right of the stage)
POP_PAD = 4                                 # one-line popup: margin around its pill
POP_W, POP_H = 2 + 3 * VB_W + 5 + VB_W + 2, 16
VIEWS = ("full", "compact", "line")

# ---------- behaviour ----------
BUSY_AT, SLEEP_BELOW, SLEEP_AFTER = 85, 15, 60
FAST_MS, IDLE_MS, NIGHT_MS, HOVER_MS = 25, 250, 80, 100   # 25 ms: Windows timers round up, so ~30 fps
MAX_SPARKS, MAX_DROPS = 16, 18
MAX_SWEETS = sph.TRAIL_MAX + 2      # the Halloween trail plus the one still falling
EFFECTS = ("none", "magic", "painting", "build", "cook", "comp", "trick")   # busy effects: the Default (Effects
                                                                           # tab) and one per app
WORK_EFFECTS = ("build", "cook", "comp")     # Construction, Cooking, Computer: held items, then a work spot (sprites.py)
STATIONS = ("painting",) + WORK_EFFECTS      # step 3: the pet stops at a work spot that pops up beside it
METERS = ("cpu", "gpu", "ram")
EFFECT_RANGE = (40, 75)                      # Effects tab range default for each meter (%): step 1 at the start,
RANGE_GAP = 10                               # step 2 in the middle, step 3 at the end; the ends stay 10 apart
WALK_SPEED, RUN_SPEED, STRIDE = 26, 55, 7   # px/s wandering, px/s walking to a click, px per foot change
# The pumpkin hops instead of walking: it is in the air for HOP_AIR of every cycle and moves only then.
# Wandering it covers HOP_STEP px a hop (a little slower than a walking pet); to a click it hops faster and
# further, so it still arrives at RUN_SPEED. Heights are in sprite pixels.
HOP_AIR, HOP_CYCLE, HOP_STEP, HOP_HIGH = .40, .82, 12, 4
HOP_RUN_CYCLE, HOP_RUN_HIGH = .42, 5.5

# ---------- palette ----------
C = {"panel": "#1E1B26", "edge": "#34303F", "btn": "#272333", "track": "#2E2A3A", "label": "#8F88A8",
     "ink": "#ECE9F3", "ok": "#6FCF9C", "warn": "#F2C166", "crit": "#F08B7E", "magic": "#B9A8FF",
     "star": "#FFD86B", "heart": "#F27C8E", "accent": "#6CC486", "sel": "#3A3548", "hover": "#2A2636"}
SCENES = {
    "morning": {"sky": ("#2D5A6B", "#E7A79B"), "far": "#9DB9AE", "mid": "#7BA592", "gnd": "#5B8A6E", "edge": "#78AC88", "tuft": "#86BB94"},
    "day":     {"sky": ("#5E9FD8", "#CFE7F6"), "far": "#A7CFC4", "mid": "#84B99E", "gnd": "#5F9C74", "edge": "#7CBB8B", "tuft": "#8CCB9A"},
    "evening": {"sky": ("#3A2D6A", "#EE9670"), "far": "#6A4F86", "mid": "#4E3C70", "gnd": "#3B3059", "edge": "#54457A", "tuft": "#64548C"},
    "night":   {"sky": ("#0A0F21", "#1F2A4C"), "far": "#1B2644", "mid": "#16203A", "gnd": "#141D30", "edge": "#22314A", "tuft": "#2A3C58"},
}
STARS = ((.06, .12), (.15, .4), (.25, .1), (.34, .3), (.45, .14), (.54, .44), (.62, .08), (.7, .36), (.87, .5), (.93, .12))
FLIES = ((.14, .7, 0), (.34, .5, 1.7), (.66, .62, 3.1), (.82, .42, 4.4))

LOCK = ("  ###  ", " #   # ", " #   # ", "#######", "### ###", "### ###", "#######")   # 7 x 7, shown while locked
# Windows' own background programs, hidden from "+ Add running app".
NOT_APPS = {
    "system", "registry", "memory compression", "secure system", "system idle process", "smss.exe", "csrss.exe",
    "wininit.exe", "services.exe", "lsass.exe", "lsaiso.exe", "svchost.exe", "fontdrvhost.exe", "winlogon.exe",
    "dwm.exe", "explorer.exe", "sihost.exe", "taskhostw.exe", "runtimebroker.exe", "searchindexer.exe",
    "searchapp.exe", "searchui.exe", "searchhost.exe", "startmenuexperiencehost.exe", "shellexperiencehost.exe",
    "ctfmon.exe", "conhost.exe", "dllhost.exe", "audiodg.exe", "spoolsv.exe", "wmiprvse.exe", "smartscreen.exe",
    "securityhealthservice.exe", "securityhealthsystray.exe", "msmpeng.exe", "nissrv.exe", "python.exe",
    "pythonw.exe", "py.exe", "pyw.exe", "cmd.exe", "powershell.exe", "applicationframehost.exe",
    "textinputhost.exe", "lockapp.exe", "systemsettings.exe", "backgroundtaskhost.exe", "wudfhost.exe",
    "useroobebroker.exe", "sgrmbroker.exe", "unsecapp.exe", "wlanext.exe", "dashost.exe", "taskmgr.exe",
}
NOT_APP_ENDINGS = ("service.exe", "svc.exe", "host.exe", "helper.exe", "broker.exe", "updater.exe", "update.exe",
                   "crashpad_handler.exe", "container.exe", "agent.exe", "tray.exe", "daemon.exe")

_ARGB = {}


def A(color, alpha=1.0):
    """Cached ARGB for '#RRGGBB' at an opacity (rounded to 1/64 steps)."""
    key = (color, round(alpha * 64))
    v = _ARGB.get(key)
    if v is None:
        v = _ARGB[key] = argb(color, key[1] / 64)
    return v


def lerp_hex(a, b, k):
    ra, ga, ba = (int(a[i:i + 2], 16) for i in (1, 3, 5))
    rb, gb, bb = (int(b[i:i + 2], 16) for i in (1, 3, 5))
    return "#%02X%02X%02X" % (round(ra + (rb - ra) * k), round(ga + (gb - ga) * k), round(ba + (bb - ba) * k))


def level_color(pct):
    return C["crit"] if pct >= BUSY_AT else C["warn"] if pct >= 60 else C["ok"]


def time_phase():
    h = time.localtime().tm_hour
    return "morning" if 6 <= h < 10 else "day" if 10 <= h < 17 else "evening" if 17 <= h < 20 else "night"


def clamp(v, lo, hi):
    return max(lo, min(hi, v))


class _LastInput(ctypes.Structure):
    _fields_ = [("cbSize", ctypes.c_uint), ("dwTime", ctypes.c_uint)]


def input_idle():
    """Seconds since the last mouse or keyboard input anywhere (Windows keeps this; costs nothing)."""
    li = _LastInput(ctypes.sizeof(_LastInput), 0)
    if not ctypes.windll.user32.GetLastInputInfo(ctypes.byref(li)):
        return 0.0
    return ((ctypes.windll.kernel32.GetTickCount() - li.dwTime) & 0xFFFFFFFF) / 1000


class Pet:
    __slots__ = ("x", "dir", "phase", "pause", "glance", "target", "jump", "hearts", "sparks", "drops",
                 "blink_in", "blink", "surprise", "easel", "paint", "done", "sp", "turn", "hop", "vanish_in",
                 "fade_t", "sweets", "sweet_in")

    def __init__(self, x):
        self.x, self.dir, self.phase = x, random.choice((-1, 1)), 0.0
        self.pause = self.glance = self.blink = self.surprise = 0.0
        self.target = None
        self.jump = -1.0                  # seconds into a hop, -1 when not hopping
        self.hearts, self.sparks, self.drops = [], [], []
        self.sweets, self.sweet_in = [], 0.0   # Halloween: [x, y, vy, color, bounces] (vy None once it has landed)
        self.blink_in = 3.0
        self.easel = self.paint = self.done = 0.0   # easel pop-up amount, painting progress, "admire" timer
        self.sp, self.turn = 0.0, False   # eased walking speed (0..1); turn around when the pause ends
        self.hop = 0.0                    # seconds into the hop cycle (pets that hop instead of walking)
        self.vanish_in = random.uniform(*spg.VANISH_GAP)   # the ghost: seconds until it fades away
        self.fade_t = 0.0                 # seconds into that fade (0 = fully there)


class Gadget(GadgetContentMixin, GadgetMoveMixin, GadgetPoseMixin, GadgetSettingsMixin):
    SZ_MIN, SZ_MAX = SZ_MIN, SZ_MAX       # read by settings_ui
    EFFECTS, METERS, RANGE_GAP = EFFECTS, METERS, RANGE_GAP
    WORK_EFFECTS, STATIONS, SCRIPT = WORK_EFFECTS, STATIONS, SCRIPT
    PET_DY = PET_DY
    MARGIN, SIZE_BASE = MARGIN, SIZE_BASE   # read by gadget_settings (a test may still repoint SETTINGS_PATH)
    C, EFFECT_RANGE = C, EFFECT_RANGE               # read by gadget_content
    clamp = staticmethod(clamp)                     # ditto
    HEAD_TOP = HEAD_TOP                             # read by gadget_pose
    # read by gadget_move (SLEEP_AFTER is not here: a test may repoint it, see __init__'s self._sleep_after)
    SLEEP_BELOW, XMIN, WALK_SPEED, RUN_SPEED = SLEEP_BELOW, XMIN, WALK_SPEED, RUN_SPEED
    HOP_AIR, HOP_CYCLE, HOP_STEP, HOP_HIGH, HOP_RUN_CYCLE, HOP_RUN_HIGH = \
        HOP_AIR, HOP_CYCLE, HOP_STEP, HOP_HIGH, HOP_RUN_CYCLE, HOP_RUN_HIGH
    MAX_SPARKS, MAX_DROPS, MAX_SWEETS = MAX_SPARKS, MAX_DROPS, MAX_SWEETS
    FAST_MS, NIGHT_MS, IDLE_MS = FAST_MS, NIGHT_MS, IDLE_MS

    def __init__(self):
        self._settings_path = SETTINGS_PATH    # a live lookup, so a test that repoints SETTINGS_PATH before
                                                # constructing Gadget still takes effect (see gadget_settings.py)
        self._sleep_after = SLEEP_AFTER        # ditto: perf_harness.py repoints SLEEP_AFTER before Gadget()
        self.root = tk.Tk()
        self.root.withdraw()              # Tk runs the event loop, menu and Settings; the gadget is its own window
        self.root.title(APP_NAME)
        icon = os.path.join(HERE, "assets", "app_icon.ico")     # tools/make_icon.py; used by every dialog window
        if os.path.exists(icon):
            try:
                self.root.iconbitmap(default=icon)
            except tk.TclError:
                pass
        self.S = self.root.winfo_fpixels("1i") / 96.0
        self.ps = max(1, round(2 * self.S))     # device pixels per pet sprite pixel
        gfx.startup()

        st = self.settings = self._load_settings()
        self.W = clamp(st.get("w", W_DEF), W_MIN, W_MAX)
        self.YH = clamp(st.get("yard_h", YH_DEF), YH_MIN, YH_MAX)
        self.view = tk.StringVar(value=st.get("view") if st.get("view") in VIEWS else "full")
        lw = st.get("line_w")
        self.line_w = lw if isinstance(lw, (int, float)) else None
        self.line_disp = None
        lp = st.get("line_pad")               # one-line view: empty space left / right of the numbers
        self.line_pad = [max(0.0, float(v)) for v in lp] \
            if isinstance(lp, list) and len(lp) == 2 and all(isinstance(v, (int, float)) for v in lp) else [0.0, 0.0]
        i18n.set_lang(st.get("language") if st.get("language") in dict(i18n.LANGS) else i18n.system_lang())
        self.locked = st.get("locked") is True    # click-through, set only from the tray icon's menu
        self.topmost = tk.BooleanVar(value=st.get("topmost", True))
        self.ram_as_pct = tk.BooleanVar(value=st.get("ram_pct", False))
        self.show_pet = tk.BooleanVar(value=st.get("show_pet", True))
        self.transparent = tk.BooleanVar(value=st.get("transparent", False))
        size = st.get("status_size", 100)
        if st.get("size_base") is None and size == 105:   # saved before the new 100% (SIZE_BASE): looks the same
            size = 100
        self.status_size = tk.IntVar(value=round(clamp(size, SZ_MIN, SZ_MAX) / 5) * 5)
        self.character = st.get("character", "slime")
        ah = st.get("app_hats")
        self.app_hats = {k: hatlib.RENAMED.get(v, v) for k, v in ah.items() if v is None or isinstance(v, str)} \
            if isinstance(ah, dict) else {}
        dh = st.get("default_hat") if isinstance(st.get("default_hat"), str) else None
        self.default_hat = hatlib.RENAMED.get(dh, dh)
        self.default_effect = st.get("default_effect") if st.get("default_effect") in EFFECTS else "magic"
        ae = st.get("app_effects")
        self.app_effects = {k: v for k, v in ae.items() if v in EFFECTS or v == hatlib.FOLLOW} \
            if isinstance(ae, dict) else {}
        self.effect_range = self._read_ranges(st)
        self.pending, self.follow = [], False    # Tk actions queued by window-message code (see _run_pending)
        autostart.refresh(SCRIPT)
        self._sync()
        off = st.get("settings_off")
        self.settings_off = tuple(off) if isinstance(off, list) and len(off) == 2 else None
        self.custom_apps = [a for a in st.get("custom_apps", []) if isinstance(a, dict) and a.get("exe")]
        ids = {a["id"] for a in self.custom_apps}           # anything saved for an app not in the list is dropped
        tracked = st.get("tracked")
        self.tracked = {i for i in tracked if i in ids} if isinstance(tracked, list) else set()
        cols = st.get("app_colors")
        self.app_colors = {k: v for k, v in cols.items() if k in ids and isinstance(v, str) and len(v) == 7
                           and v[0] == "#"} if isinstance(cols, dict) else {}
        self.app_hats = {k: v for k, v in self.app_hats.items() if k in ids}
        self.app_effects = {k: v for k, v in self.app_effects.items() if k in ids}

        self.f_label = gfx.Font("Segoe UI Semibold", 9.5)
        self.f_value = gfx.Font("Segoe UI Semibold", 12.5)
        self.f_name = gfx.Font("Segoe UI", 11.5)
        self.f_small = gfx.Font("Segoe UI Semibold", 11)
        self.f_item = gfx.Font("Segoe UI Semibold", 10.5)
        self.meas = gfx.Surface(4, 4)     # text measuring
        px = lambda n: -round(n * self.S)
        self.tf_ui = tkfont.Font(family="Segoe UI", size=px(13))
        self.tf_b = tkfont.Font(family="Segoe UI Semibold", size=px(13))
        self.tf_head = tkfont.Font(family="Segoe UI Semibold", size=px(10.5))
        self.tf_small = tkfont.Font(family="Segoe UI", size=px(11.5))
        self.tf_x = tkfont.Font(family="Segoe UI", size=px(16))
        self._apply_fonts()

        self.win = gfx.LayeredWindow(self._on_msg, self.topmost.get())
        self.pop = gfx.LayeredWindow(self._on_pop_msg, self.topmost.get(), f"{APP_NAME} views")
        self.surf = self.pop_surf = self.stage = None
        self.base = None
        self.base_key = self.stage_key = self.pop_key = None
        self._pet_cache = {}
        self.hat_dir = os.path.join(DATA, "hats")
        if FROZEN and not os.path.isdir(self.hat_dir):       # first start after installing: the shipped hats
            try:
                shutil.copytree(os.path.join(HERE, "hats"), self.hat_dir)
            except OSError:
                pass
        self.reload_hats()

        self.cpu_reader, self.gpu_reader, self.app_reader = SystemCpu(), GpuMonitor(), AppMonitor()
        self.cpu = self.gpu = self.ram_pct = None
        self.ram_used, self.ram_total = 0.0, None
        self.app_rows = []                # rows shown under the bars: dicts with name, color, cpu, ram, more
        self.app_cpu = {}                 # app id -> total CPU, to pick the prop
        self.effect, self.fx_step, self.fx_inten = "none", 0, 0.0   # the busy effect playing and its step (0-3)
        self.hat_app = None               # the busiest tracked app: its hat is worn
        self.load, self.prev_load = 0.0, None

        self.pet = Pet(random.uniform(XMIN + 20, self.W - XMIN - 20))
        self.mood, self.calm_since = "walk", None
        self.away = 0.0                   # seconds since your last mouse / keyboard input
        self.t, self.last = 0.0, time.perf_counter()
        self.phase = time_phase()
        self.hover = False
        self.view_a = 0.0                 # hover controls fade-in (0..1)
        self.hover_grip = False
        self.drag = None
        self.settings_win = self.sdrag = self.ui = None
        self.size_lbl = self.count_lbl = None
        self.jobs = {}

        self.upd = UpdateCheck(VERSION)   # newest version from the website (background thread)
        self.upd_seen = None              # the `latest` the tray and Settings last showed
        self._build_menu()
        try:
            self.tray = TrayIcon(APP_NAME, self._tray_grid(), on_quit=lambda: self.pending.append(self.quit),
                                 on_lock=lambda: self.pending.append(self.toggle_lock),
                                 on_update=lambda: self.pending.append(self.open_update))
        except OSError:
            self.tray = None
        self._tray_texts()
        self._apply_lock()
        self._tray_char = self.character   # the tray already shows this pet
        self._update_tray_icon()          # the tray icon shows the current pet
        self._place_initial()
        self.upd.check()
        self.tick_stats()
        self.tick_frame()
        self.poll_hover()

    # ---------- geometry (logical pixels, panel top-left = 0, 0) ----------
    @property
    def is_line(self):
        return self.v_view == "line"

    @property
    def yard_bottom(self):
        return 8 + self.YH if self.v_pet and not self.is_line else 0

    @property
    def lz(self):
        return LZ_H if self.v_pet and self.is_line else 0

    @property
    def top(self):                        # where the status rows start
        return self.yard_bottom or self.lz

    @property
    def ground(self):                     # the pet's ground line
        return self.lz - 2 if self.is_line else 8 + self.YH - round(self.YH * .2)

    @property
    def xmax(self):
        return self.gw() - XMIN

    def rows_h(self):
        return LINE_H if self.is_line else ROWS_COMPACT if self.v_view == "compact" else ROWS_FULL

    def apps_h(self):
        return len(self.app_rows) * APP_ROW + 2 if self.app_rows and not self.is_line else 0

    def cur_h(self):
        return self.top + (self.rows_h() + self.apps_h()) * self.sz

    def w_min(self):
        return max(W_MIN, math.ceil(W_MIN * self.sz))

    def gw(self):
        if not self.is_line:
            return self.W
        return self.line_pad[0] + (self.line_disp if self.line_disp is not None else self.line_width()) + self.line_pad[1]

    def dev(self, v):                     # logical panel coordinate -> device pixel inside the window
        return (MARGIN + v) * self.S

    # ---------- status text ----------
    def ram_text(self, gb, short=False):
        if self.v_pct and self.ram_total:
            return f"{round(gb / self.ram_total * 100)}%"
        return f"{gb:.1f}" + ("G" if short else " GB")

    def stat_rows(self):
        ram = self.ram_text(self.ram_used) if self.ram_total else "—"
        return (("CPU", self.cpu, "—" if self.cpu is None else f"{round(self.cpu)}%"),
                ("GPU", self.gpu, "—" if self.gpu is None else f"{round(self.gpu)}%"),
                ("RAM", self.ram_pct, ram))

    def tw(self, s, font):
        return self.meas.measure(s, font)[0]

    def status_items(self, rows):
        items = []
        for label, pct, _ in self.stat_rows():
            val = (self.ram_text(self.ram_used, True) if self.ram_total else "—") if label == "RAM" else \
                ("—" if pct is None else f"{round(pct)}%")
            items.append({"dot": level_color(pct) if pct is not None else C["track"],
                          "parts": [[label, C["label"], 0], [val, C["ink"], 4]]})
        for h in rows:
            items.append({"dot": None if h["more"] else h["color"],
                          "parts": [[h["name"], C["label"] if h["more"] else C["ink"], 0], ["CPU", C["label"], 6],
                                    [f"{round(h['cpu'])}%", C["ink"], 4], ["RAM", C["label"], 8],
                                    [self.ram_text(h["ram"], True), C["ink"], 4]]})
        for it in items:
            it["w"] = self._item_w(it)
        return items

    def _item_w(self, it):
        return (10 if it["dot"] else 0) + sum(g + self.tw(s, self.f_item) for s, _, g in it["parts"])

    @staticmethod
    def _items_w(items):
        return sum(it["w"] for it in items) + ITEM_GAP * max(0, len(items) - 1)

    def _nat_w(self, items):
        return math.ceil(self._items_w(items) * self.sz) + LINE_L + LINE_R

    def line_min_w(self):
        return self._nat_w(self.status_items([]))

    def line_nat_w(self):
        return self._nat_w(self.status_items(self.app_rows))

    def line_target(self):
        return clamp(self.line_w if self.line_w is not None else 1e9, self.line_min_w(), self.line_nat_w())

    def line_items(self):
        """What fits the target width: values drop from the end."""
        avail = (self.line_target() - LINE_L - LINE_R) / self.sz
        items = self.status_items(self.app_rows)
        while len(items) > 3 and self._items_w(items) > avail:
            it = items[-1]
            if len(it["parts"]) > 3:
                it["parts"] = it["parts"][:3]
                it["w"] = self._item_w(it)
            else:
                items.pop()
        return items

    def line_width(self):
        return self._nat_w(self.line_items())

    # ---------- settings file + window placement: gadget_settings.GadgetSettingsMixin ----------

    def panel_rect(self):
        """The panel's rectangle on screen (device pixels): left, top, right, bottom."""
        l, t = self.win.x + MARGIN * self.S, self.win.y + MARGIN * self.S
        return l, t, l + self.gw() * self.S, t + self.cur_h() * self.S

    # ---------- options ----------
    def _sync(self):
        """Copies the Tk option variables into plain attributes. Window-message code must never touch Tk:
        Windows calls it while Tk waits for events, and a Tk call there breaks tkinter's thread state and
        aborts Python. So drawing and input read these copies, and Tk actions go through self.pending."""
        self.v_view = self.view.get()
        self.v_pet = self.show_pet.get()
        self.v_clear = self.transparent.get()
        self.v_pct = self.ram_as_pct.get()
        self.v_top = self.topmost.get()
        self.sz = self.status_size.get() / 100 * SIZE_BASE

    def _toggle_pct(self):
        self.ram_as_pct.set(not self.ram_as_pct.get())
        self._on_option()

    # ---------- menu ----------
    def _build_menu(self):
        m = tk.Menu(self.root, tearoff=0, font=self.tf_ui)      # the app's font, so Korean matches Settings
        m.add_checkbutton(label=tr("Always on top"), variable=self.topmost, command=self._apply_topmost)
        m.add_separator()
        for label, value in (("Full view", "full"), ("Compact view", "compact"), ("One line", "line")):
            m.add_radiobutton(label=tr(label), variable=self.view, value=value, command=self._on_view_change)
        m.add_separator()
        m.add_checkbutton(label=tr("Show RAM as %"), variable=self.ram_as_pct, command=self._on_option)
        m.add_checkbutton(label=tr("Show pet"), variable=self.show_pet, command=self._on_option)
        m.add_checkbutton(label=tr("Transparent background"), variable=self.transparent, command=self._on_option)
        m.add_command(label=tr("Settings…"), command=self.toggle_settings)
        m.add_separator()
        m.add_command(label=tr("Reset position"), command=self._reset_position)
        m.add_command(label=tr("Reset size"), command=self._reset_size)
        m.add_separator()
        m.add_command(label=tr("Quit"), command=self.quit)
        self.menu = m

    # ---------- language ----------
    def _apply_fonts(self):
        """Tk text follows the language: each language's own font (i18n.font), same sizes."""
        for f, bold in ((self.tf_ui, False), (self.tf_b, True), (self.tf_head, True), (self.tf_small, False),
                        (self.tf_x, False)):
            family, weight = i18n.font(bold)
            f.configure(family=family, weight=weight)

    def _tray_texts(self):
        if self.tray:
            self.tray.labels = {"lock": tr("Lock (click-through)"), "unlock": tr("Unlock"), "quit": tr("Quit {tip}"),
                                "locked": tr("{tip} (locked)")}
            self.tray.update_text = self.upd.latest and tr("Update available (v{v})", v=self.upd.latest)
            self.tray.set_locked(self.locked)

    # ---------- update notice ----------
    def open_update(self):
        open_page(self.upd.link)

    def _poll_update(self):
        """Once a second: a daily re-check, and showing a result the background check just found."""
        if self.upd.due():
            self.upd.check()
        if self.upd.latest != self.upd_seen:
            self.upd_seen = self.upd.latest
            self._tray_texts()
            if self.ui:
                self.ui.refresh()

    def set_language(self, code):
        """The General tab's Language picker: menus, tray, Settings and hat messages change at once."""
        i18n.set_lang(code)
        self._apply_fonts()
        old = self.menu
        self._build_menu()
        old.destroy()
        self._tray_texts()
        self.reload_hats()                # hat file messages are made while loading
        self._save_settings()
        if self.ui:
            self.ui.relang()

    def _apply_topmost(self):
        self._sync()
        on = self.v_top
        self.win.set_topmost(on)
        self.pop.set_topmost(on)
        if self.settings_win:
            self.settings_win.attributes("-topmost", on)
        self._save_settings()

    def toggle_lock(self):
        self.locked = not self.locked
        self._apply_lock()
        self.base_key = None
        self.render()
        self._save_settings()

    def _apply_lock(self):
        """Locked: the gadget and its one-line popup let the mouse through; no hover, clicks or drags."""
        for w in (self.win, self.pop):
            w.set_click_through(self.locked)
        if self.locked:
            if self.drag:
                self.drag = None
                self.win.capture(False)
            self.hover_grip = False
            self._set_hover(False)
        if self.tray:
            self.tray.set_locked(self.locked)

    def set_view(self, v):
        self.view.set(v)
        self._on_view_change()

    def _on_view_change(self):
        self._sync()
        self.line_disp = None             # a fresh one-line bar starts at its content width
        self._after_change()

    def _on_option(self):
        self._sync()
        self.W = clamp(self.W, self.w_min(), W_MAX)
        if self.size_lbl:
            self.size_lbl.config(text=f"{self.status_size.get()}%")
        self._after_change()

    def _update_tray_icon(self):
        """The tray icon shows the current pet: its face and body (the cat without its tail, to stay big)."""
        if not self.tray or self._tray_char == self.character:
            return
        self._tray_char = self.character
        self.tray.set_image(self._tray_grid())

    def _tray_grid(self):
        """The current pet as rows of colors for the tray icon."""
        cells = self.pet_cells(None)
        if self.character == "cat":
            cells = {k: v for k, v in cells.items() if sp.PX <= k[0] < sp.PX + 12}
        xs, ys = [c for c, _ in cells], [r for _, r in cells]
        return [[cells.get((x, y)) for x in range(min(xs), max(xs) + 1)] for y in range(min(ys), max(ys) + 1)]

    def _after_change(self):
        self._update_tray_icon()
        self.base_key = None
        self.render()
        self._place_settings()
        self._save_settings()

    def _reset_position(self):
        x, y = self._default_pos()
        self.win.move(x, y)
        self._after_change()

    def _reset_size(self):
        self.W, self.YH, self.line_w, self.line_disp = W_DEF, YH_DEF, None, None
        self.line_pad = [0.0, 0.0]
        self.status_size.set(100)
        self._on_option()

    # ---------- Settings window (Tk): always beside the gadget ----------
    def toggle_settings(self):
        if self.settings_win:
            self.close_settings()
        else:
            self.open_settings()

    def open_settings(self):
        if self.ui:
            self.settings_win.lift()
            return
        self.settings_off = None          # always opens right beside the gadget (a drag counts only while it's open)
        self.upd.check(min_gap=60)        # opening Settings doubles as "check now"
        self.ui = SettingsUI(self, C)     # builds and places itself (settings_ui.py)
        self.settings_win = self.ui.win
        self.render()                     # the gear lights up

    # ---------- app list, hats and busy effects: gadget_content.GadgetContentMixin ----------

    # ---------- pixel-art pose builders: gadget_pose.GadgetPoseMixin ----------

    def _add_app_menu(self, anchor):
        known = {a["exe"] for a in self.custom_apps}
        names = sorted(n for n in self.app_reader.exe_names
                       if n.endswith(".exe") and n not in NOT_APPS and not n.endswith(NOT_APP_ENDINGS)
                       and n not in known)
        m = tk.Menu(self.root, tearoff=0, font=self.tf_ui)
        if not names:
            m.add_command(label=tr("No other programs running"), state="disabled")
        for n in names[:30]:
            m.add_command(label=n[:-4], command=lambda n=n: self._add_app(n))
        m.tk_popup(anchor.winfo_rootx(), anchor.winfo_rooty() + anchor.winfo_height())

    def _add_app(self, exe):
        stem = exe[:-4]
        app_id = "custom:" + stem
        self.custom_apps.append({"id": app_id, "name": stem[:1].upper() + stem[1:], "exe": exe})
        self.tracked.add(app_id)
        self._save_settings()
        self._sample_apps()
        if self.ui:
            self.ui.shown.add(app_id)
            self.ui.refresh()

    def close_settings(self):
        if self.ui:
            self.ui.close()
            self.ui = self.settings_win = self.size_lbl = None
            self.render()

    def _place_settings(self):
        """Right of the gadget; left if only the left fits; the roomier side if neither. Or the user's own
        spot, kept relative to the gadget. Always inside the gadget's monitor."""
        w = self.settings_win
        if not w:
            return
        dw, dh = w.winfo_reqwidth(), w.winfo_reqheight()
        l, t, r, b = self.panel_rect()
        wl, wt, wr, wb = gfx.work_area((l + r) / 2, (t + b) / 2)
        gap = round(12 * self.S)
        if self.settings_off:
            x, y = l + self.settings_off[0], t + self.settings_off[1]
            # the user's own spot may be on another monitor: keep it inside THAT monitor, not the gadget's
            wl, wt, wr, wb = gfx.work_area(x + dw / 2, y + min(dh, 40) / 2)
        else:
            right, left = r + gap, l - gap - dw
            x = right if right + dw <= wr else left if left >= wl else (wr - dw if wr - r >= l - wl else wl)
            y = t + self.lz * self.S      # level with the visible panel (one-line view: below the see-through pet strip)
        x, y = clamp(int(x), wl, max(wl, wr - dw)), clamp(int(y), wt, max(wt, wb - dh))
        w.geometry(f"+{x}+{y}")

    def _settings_press(self, e):
        w = self.settings_win
        self.sdrag = (e.x_root, e.y_root, w.winfo_x(), w.winfo_y())

    def _settings_drag(self, e):
        if self.sdrag:
            sx, sy, wx, wy = self.sdrag
            self.settings_win.geometry(f"+{wx + e.x_root - sx}+{wy + e.y_root - sy}")

    def _settings_release(self, e):
        if self.sdrag:
            self.sdrag = None
            l, t, _, _ = self.panel_rect()
            self.settings_off = (self.settings_win.winfo_x() - l, self.settings_win.winfo_y() - t)
            self._save_settings()

    # ---------- input: the gadget window ----------
    def _local(self, lparam):
        x, y = gfx.mouse_xy(lparam)
        return x / self.S - MARGIN, y / self.S - MARGIN

    def _cursor_local(self):
        cx, cy = gfx.cursor_pos()
        return (cx - self.win.x) / self.S - MARGIN, (cy - self.win.y) / self.S - MARGIN

    def _in_grip(self, x, y):
        """Which resize grip is under x, y: "r" (right / corner), "l" (one-line view's left end) or False."""
        if self.is_line:
            if not self.lz <= y <= self.cur_h():
                return False
            return "r" if x >= self.gw() - 12 else "l" if x <= 12 else False
        return "r" if self.W - 18 <= x <= self.W and self.cur_h() - 18 <= y <= self.cur_h() else False

    def _view_at(self, x, y):
        if self.is_line or self.view_a < .5 or not self.v_pet:
            return None
        if not (VB_X <= x <= VB_X + VB_W * 3 + 4 and VB_Y - 2 <= y <= VB_Y + VB_H + 2):
            return None
        return VIEWS[clamp(int((x - VB_X - 2) // VB_W), 0, 2)]

    def _gear_x(self):
        return round(self.W - 14 - GB_W)

    def _gear_at(self, x, y):
        if self.is_line or self.view_a < .5 or not self.v_pet:
            return False
        gx = self._gear_x()
        return gx - 2 <= x <= gx + GB_W + 2 and VB_Y - 2 <= y <= VB_Y + GB_H + 2

    def _inside(self, x, y):
        return 0 <= x <= self.gw() and 0 <= y <= self.cur_h()

    def _on_msg(self, msg, wparam, lparam):
        if msg == gfx.WM_MOUSEACTIVATE:
            return gfx.MA_NOACTIVATE
        if msg == gfx.WM_SETCURSOR:
            x, y = self._cursor_local()
            if self.drag and self.drag["mode"] == "resize" or self._in_grip(x, y):
                gfx.set_cursor("we" if self.is_line else "nwse")
            elif self._view_at(x, y) or self._gear_at(x, y):
                gfx.set_cursor("hand")
            else:
                gfx.set_cursor("arrow")
            return 1
        if msg == gfx.WM_MOUSEMOVE:
            x, y = self._local(lparam)
            if self._inside(x, y):
                self._set_hover(True)
            if self.drag:
                self._on_drag()
            else:
                g = self._in_grip(x, y)
                if g != self.hover_grip:
                    self.hover_grip = g
                    self.base_key = None
            return 0
        if msg == gfx.WM_LBUTTONDOWN:
            x, y = self._local(lparam)
            if not self._inside(x, y):
                return 0
            cx, cy = gfx.cursor_pos()
            g = self._in_grip(x, y)
            self.drag = {"mode": "resize" if g else "move", "side": g, "sx": cx, "sy": cy,
                         "wx": self.win.x, "wy": self.win.y, "W": self.W, "YH": self.YH,
                         "LW": self.line_target(), "pad": list(self.line_pad), "GW": self.gw(),
                         "moved": False, "x": x, "y": y}
            self.win.capture(True)
            return 0
        if msg == gfx.WM_LBUTTONUP:
            d, self.drag = self.drag, None
            self.win.capture(False)
            if self.v_top and gfx.taskbar_above(self.win.hwnd):   # dragged under the taskbar: come back up now
                self.win.set_topmost(True)    # (plain Win32 calls, safe here; no Tk)
            if not d:
                return 0
            if d["mode"] == "resize" and self.is_line:
                goal, self.line_w = self.line_target(), self.line_width()   # the next drag starts where the bar ends
                if d["side"] == "l" and d["moved"]:   # left end: the numbers drop to what fits; keep the right end put
                    self.win.x += round((goal - self.line_w) * self.S)
                    self.line_disp = self.line_w
            if d["moved"] or d["mode"] == "resize":
                self.pending.append(self._save_settings)
                self.base_key = None
                return 0
            self._on_click(d["x"], d["y"])
            return 0
        if msg == gfx.WM_RBUTTONUP:
            cx, cy = gfx.cursor_pos()
            self.pending.append(lambda: self.menu.tk_popup(cx, cy))
            return 0
        return None

    def _on_drag(self):
        d = self.drag
        cx, cy = gfx.cursor_pos()
        dx, dy = cx - d["sx"], cy - d["sy"]
        if abs(dx) + abs(dy) > 3:
            d["moved"] = True
        if not d["moved"]:
            return
        if d["mode"] == "resize":
            if self.is_line:
                self._line_resize(d, dx)
            else:
                self.W = clamp(d["W"] + dx / self.S, self.w_min(), W_MAX)
                if self.v_pet:
                    self.YH = clamp(d["YH"] + dy / self.S, YH_MIN, YH_MAX)
            self.render()
        else:
            self.win.move(d["wx"] + dx, d["wy"] + dy)
            self._place_pop()
            if self.settings_win:
                self.follow = True        # Settings follows the gadget (moved by _run_pending)

    def _line_resize(self, d, dx):
        """One-line view, dragging an end: the numbers stay where they are on screen. Pulling an end out
        first fills the numbers back in, then adds empty space on that side; pushing it in takes the space
        away first, then shortens the numbers. The left end moves the window so the right end stays put."""
        i = 0 if d["side"] == "l" else 1
        nat, lo = self.line_nat_w(), self.line_min_w()
        wl, _, wr, _ = gfx.work_area(d["wx"], d["wy"])
        cap = (wr - wl) / self.S - 2 * MARGIN - d["pad"][1 - i]       # the whole bar at most one screen wide
        avail = min(d["LW"] + d["pad"][i] + (dx if i else -dx) / self.S, cap)
        if avail <= nat:
            self.line_w, self.line_pad[i] = clamp(avail, lo, nat), 0.0
        else:
            self.line_w, self.line_pad[i] = nat, avail - nat
        self.line_disp = self.line_target()
        if not i:
            self.win.x = d["wx"] + round((d["GW"] - self.gw()) * self.S)
        self._place_pop()

    def _on_click(self, x, y):
        v = self._view_at(x, y)
        if v:
            self.pending.append(lambda: self.set_view(v))
            return
        if self._gear_at(x, y):
            self.pending.append(self.toggle_settings)
            return
        yb, sz = self.yard_bottom, self.sz
        if y > self.top and (self.v_view != "full" or y > yb + (ROWS_FULL - 6) * sz or x >= self.W - 70 * sz):
            self.pending.append(self._toggle_pct)
            return
        if not yb and not self.lz:
            return
        p = self.pet
        if math.hypot(x - p.x, y - (self.ground - 10)) < 15:
            p.jump, p.pause = 0.0, 1.5
            self.calm_since = time.perf_counter()
            for i in range(3):
                p.hearts.append([p.x + (i - 1) * 8, self.ground - 26 - i * 2, -i * .12, i * 2])
            self.pending.append(self._kick)
            return
        if (8 <= x <= self.W - 8 and 8 <= y <= yb) if yb else y <= self.lz:
            p.target = clamp(x, XMIN, self.xmax)
            self.calm_since = time.perf_counter()
            self.pending.append(self._kick)

    # ---------- input: the one-line popup (view buttons + gear) ----------
    def _pop_cell(self, lparam):
        x, y = gfx.mouse_xy(lparam)
        lx = x / self.S - POP_PAD - 2
        if 0 <= lx < 3 * VB_W:
            return VIEWS[int(lx // VB_W)]
        if 3 * VB_W + 5 <= lx < 4 * VB_W + 5:
            return "gear"
        return None

    def _on_pop_msg(self, msg, wparam, lparam):
        if msg == gfx.WM_MOUSEACTIVATE:
            return gfx.MA_NOACTIVATE
        if msg == gfx.WM_SETCURSOR:
            gfx.set_cursor("hand")
            return 1
        if msg == gfx.WM_MOUSEMOVE:
            self._set_hover(True)
            return 0
        if msg == gfx.WM_LBUTTONUP:
            cell = self._pop_cell(lparam)
            if cell == "gear":
                self.pending.append(self.toggle_settings)
            elif cell:
                self.pending.append(lambda: self.set_view(cell))
            return 0
        if msg == gfx.WM_RBUTTONUP:
            cx, cy = gfx.cursor_pos()
            self.pending.append(lambda: self.menu.tk_popup(cx, cy))
            return 0
        return None

    def _pop_pos(self):
        l, t, r, b = self.panel_rect()
        wl, wt, _, _ = gfx.work_area(l, t)
        S = self.S
        x = l - POP_PAD * S
        y = t - (POP_H + 6 + POP_PAD) * S
        if y < wt:                        # near the top of the screen: below the bar instead
            y = b + (6 - POP_PAD) * S
        return round(x), round(y)

    def _place_pop(self):
        if self.pop.visible:
            self.pop.move(*self._pop_pos())

    def _set_hover(self, on):
        if on != self.hover:
            self.hover = on
            self.base_key = None
            self.pending.append(self._kick)

    def _run_pending(self):
        """Runs the Tk actions queued by window-message code. Only called from Tk's own timers."""
        while self.pending:
            fn = self.pending.pop(0)
            try:
                fn()
            except Exception:
                import traceback
                traceback.print_exc()
        if self.follow:
            self.follow = False
            self._place_settings()

    def poll_hover(self):
        """Hover = the cursor over the panel or the one-line popup (10x a second; cheap)."""
        self._run_pending()
        cx, cy = gfx.cursor_pos()
        l, t, r, b = self.panel_rect()
        pad = 6 * self.S
        inside = not self.locked and ((l <= cx < r and t <= cy < b) or self.pop.contains(cx, cy, pad)
                                      or self.drag is not None)
        self._set_hover(inside)
        if not inside and self.hover_grip:
            self.hover_grip = False
            self.base_key = None
        self.jobs["hover"] = self.root.after(HOVER_MS, self.poll_hover)

    # ---------- numbers (once a second) ----------
    def app_defs(self):
        return {a["id"]: ((a["exe"][:-4].lower(),), (), True) for a in self.custom_apps if a["id"] in self.tracked}

    def _sample_apps(self):
        sessions = self.app_reader.sample(self.app_defs())
        rows, cpu = [], {}
        for app_id, name, color in self.all_apps():
            ss = sessions.get(app_id)
            if not ss or app_id not in self.tracked:
                continue
            cpu[app_id] = sum(s["cpu"] for s in ss)
            items = [{"name": name if len(ss) == 1 else f"{name} {i + 1}", "color": color, "cpu": s["cpu"],
                      "ram": s["ram_gb"], "more": False} for i, s in enumerate(ss)]
            if len(items) > 3:
                rest = items[2:]
                items = items[:2] + [{"name": f"+{len(rest)} more", "color": None, "more": True,
                                      "cpu": sum(r["cpu"] for r in rest), "ram": sum(r["ram"] for r in rest)}]
            rows.extend(items)
        self.app_rows, self.app_cpu = rows, cpu
        self.hat_app = max(cpu, key=cpu.get) if cpu else None
        self._update_effect()

    def tick_stats(self):
        self.cpu = self.cpu_reader.sample()
        self.gpu = self.gpu_reader.sample()
        ram = read_ram()
        if ram:
            self.ram_used, self.ram_total = ram
            self.ram_pct = ram[0] / ram[1] * 100
        self._sample_apps()
        self.load = max(self.cpu or 0, self.gpu or 0, self.ram_pct or 0)
        if self.prev_load is not None and self.load - self.prev_load >= 30:
            self.pet.surprise = 1.3       # a sudden jump in load
        self.prev_load = self.load
        self.phase = time_phase()
        self.away = input_idle()
        self._stay_on_top()
        self._poll_update()
        self.jobs["stats"] = self.root.after(1000, self.tick_stats)

    def _stay_on_top(self):
        """The taskbar is "always on top" too: clicking it (or dragging near it) puts it in front of the gadget.
        Once a second: if the taskbar is above AND overlapping, take the top back. Only then, so the right-click
        menu, the "+ Add running app" list and file dialogs are never covered."""
        if not self.v_top:
            return
        for w in (self.win, self.pop):
            if w.visible and gfx.taskbar_above(w.hwnd):
                w.set_topmost(True)
        if self.settings_win and gfx.taskbar_above(gfx.tk_hwnd(self.settings_win)):
            self.settings_win.attributes("-topmost", True)

    # ---------- mood, movement and the frame loop: gadget_move.GadgetMoveMixin ----------

    # ---------- drawing ----------
    def render(self):
        S = self.S
        W, H = self.gw(), self.cur_h()
        wpx, hpx = math.ceil((W + 2 * MARGIN) * S), math.ceil((H + 2 * MARGIN) * S)
        if not self.surf or (self.surf.w, self.surf.h) != (wpx, hpx):
            if self.surf:
                self.surf.close()
            self.surf = gfx.Surface(wpx, hpx)
            self.base = (ctypes.c_ubyte * self.surf.nbytes)()
            self.base_key = None
        p = self.pet
        clear = self.v_clear
        hover_fx = self.hover if (clear or self.lz) else False
        rows_key = (self.stat_rows(), tuple((r["name"], round(r["cpu"]), round(r["ram"], 1)) for r in self.app_rows),
                    self.v_pct)
        key = (wpx, hpx, round(W * 4), self.v_view, self.v_pet, clear, hover_fx, self.sz, self.YH,
               self.phase if self.yard_bottom else None, rows_key, self.hover_grip, self.drag is not None,
               round(self.line_pad[0] * 4) if self.is_line else 0, self.locked)
        s = self.surf
        if key != self.base_key:
            self.base_key = key
            self._draw_base(s, W, H, clear, hover_fx)
            s.save_to(self.base)
        else:
            s.load_from(self.base)
        # per frame: night sky, pet, effects, hover controls
        s.reset()
        if self.yard_bottom:
            s.clip_round(self.dev(8), self.dev(8), (W - 16) * S, self.YH * S, 8 * S)
            if self.phase == "night":
                self._draw_night(s, W)
            self._draw_pet(s)
            self._draw_particles(s)
            s.unclip()
        elif self.lz:
            s.clip_rect(0, 0, s.w, self.dev(self.lz + 3))
            self._draw_pet(s)
            self._draw_particles(s)
            s.unclip()
        s.transform(S, MARGIN, MARGIN)
        if self.v_pet and not self.is_line and self.view_a > 0:
            self._draw_view_buttons(s)
            self._draw_gear(s)
        self.win.show(s, self.win.x, self.win.y)
        self._render_pop()

    def _draw_base(self, s, W, H, clear, hover_fx):
        S, lz = self.S, self.lz
        s.clear(0)
        s.transform(S, MARGIN, MARGIN)
        panel = not clear or self.hover
        if lz:                            # see-through pet strip: invisible, but 1/255 opacity keeps it clickable
            s.rect(0, 0, W, lz + 6, 0x01000000)
        if panel:
            for i in range(6):            # soft shadow, outermost ring first
                e = 1 + i * 1.3
                s.round_rect(-e, lz - e + 2.5, W + 2 * e, H - lz + 2 * e, 12 + e, fill=A("#000000", .035 + .008 * (5 - i)))
            if lz and hover_fx:
                s.round_rect(.5, .5, W - 1, H - 1, 12, stroke=A(C["edge"], .9))
            s.round_rect(.5, lz + .5, W - 1, H - lz - 1, 12, fill=A(C["panel"]), stroke=A(C["edge"]))
            s.line(12, lz + 1.5, W - 12, lz + 1.5, A("#FFFFFF", .06))
        if self.yard_bottom:
            key = (self.phase, round(W), self.YH, S)
            if key != self.stage_key:
                if self.stage:
                    self.stage.close()
                self.stage = self._bake_stage(self.phase, W - 16, self.YH)
                self.stage_key = key
            s.reset()
            s.clip_round(self.dev(8), self.dev(8), (W - 16) * S, self.YH * S, 8 * S)
            s.image(self.stage, round(self.dev(8)), round(self.dev(8)))
            s.unclip()
            s.transform(S, MARGIN, MARGIN)
            s.round_rect(8.5, 8.5, W - 17, self.YH - 1, 8, stroke=A("#000000", .25))
        self._draw_rows(s, W)
        s.transform(S, MARGIN, MARGIN)
        self._draw_grip(s, W, H)

    def _bake_stage(self, phase, w, h):
        """Sky, sun / moon, clouds, hills and ground in one image (rebuilt on resize or time of day)."""
        S = self.S
        g = gfx.Surface(max(1, round(w * S)), max(1, round(h * S)))
        g.transform(S)
        P = SCENES[phase]
        gy = h - round(h * .2)
        m = gy / 122
        Y = lambda v: v * m
        circ = lambda x, y, r, col, a=1.0: g.ellipse(x, y, r, r, A(col, a))
        g.vgradient(0, 0, w, gy, A(P["sky"][0]), A(P["sky"][1]))
        g.rect(0, gy - 1, w, h - gy + 1, A(P["sky"][1]))
        if phase == "morning":
            circ(w * .24, gy - Y(14), max(12, Y(26)), "#FFD9A8", .35)
            circ(w * .24, gy - Y(14), max(7, Y(12)), "#FFE2B8")
        elif phase == "day":
            circ(w - 58, Y(34), Y(22), "#FFF6D6", .35)
            circ(w - 58, Y(34), max(7, Y(11)), "#FFF0B8")
            for cx, cy, k in ((62, Y(32), max(.6, m)), (w * .56, Y(50), max(.45, m * .75))):
                for dx, dy, rx, ry in ((0, 0, 14, 6), (-10, 1.5, 9, 4.6), (11, 1.8, 10, 4.4), (-2, -4, 8, 6)):
                    g.ellipse(cx + dx * k, cy + dy * k, rx * k, ry * k, A("#FFFFFF", .88))
        elif phase == "evening":
            for x, y in STARS[:5]:
                circ(x * w, y * gy * .6, .8, "#FFFFFF", .5)
            circ(w * .7, gy - Y(24), max(14, Y(30)), "#FFB27A", .3)
            circ(w * .7, gy - Y(24), max(8, Y(15)), "#FFD08A")
        else:
            mx, my, R = w - 60, max(12, Y(30)), max(7, Y(10))
            circ(mx, my, R * 2, "#F4EDD2", .12)
            circ(mx, my, R, "#F4EDD2")
            circ(mx + R * .55, my - R * .2, R * .85, lerp_hex(P["sky"][0], P["sky"][1], (my - R * .2) / gy))   # crescent
        g.shape((0, gy - Y(18)), [("B", w * .2, gy - Y(42), w * .35, gy - Y(22), w * .5, gy - Y(30)),
                                   ("B", w * .65, gy - Y(38), w * .8, gy - Y(46), w, gy - Y(26)), ("L", w, h), ("L", 0, h)],
                A(P["far"]))
        g.shape((0, gy - Y(6)), [("B", w * .25, gy - Y(20), w * .45, gy - Y(4), w * .65, gy - Y(14)),
                                  ("B", w * .85, gy - Y(24), w * .9, gy - Y(10), w, gy - Y(16)), ("L", w, h), ("L", 0, h)],
                A(P["mid"]))
        g.rect(0, gy, w, h - gy, A(P["gnd"]))
        g.rect(0, gy, w, 2, A(P["edge"]))
        for f in (.06, .2, .39, .6, .75, .9):
            x = round(f * w)
            g.line(x, gy + 9, x + 2, gy + 4, A(P["tuft"]), 1.2)
            g.line(x + 3, gy + 9, x + 6, gy + 5, A(P["tuft"]), 1.2)
        return g

    def _draw_night(self, s, W):
        S, w = self.S, W - 16
        gy = self.YH - round(self.YH * .2)
        for i, (x, y) in enumerate(STARS):
            a = .35 + .5 * abs(math.sin(self.t * 1.3 + i))
            s.rect(round(self.dev(8 + x * w)), round(self.dev(8 + y * gy * .7)), self.ps, self.ps, A("#FFF6D8", a))
        for x, y, o in FLIES:
            fx = self.dev(8 + x * w + math.sin(self.t * .7 + o) * 8)
            fy = self.dev(8 + y * gy + math.cos(self.t * .9 + o) * 5)
            a = .35 + .5 * abs(math.sin(self.t * 1.6 + o))
            s.glow(fx, fy, 6 * S, 6 * S, A("#FFE58A", a * .4))
            s.rect(round(fx) - self.ps // 2, round(fy) - self.ps // 2, self.ps, self.ps, A("#FFE58A", a))

    def _draw_rows(self, s, W):
        sz, top = self.sz, self.top
        s.transform(self.S * sz, MARGIN / sz, (MARGIN + top) / sz)
        w = W / sz
        if self.is_line:
            self._draw_items(s, self.line_items(), (LINE_L + self.line_pad[0]) / sz, LINE_H / 2)
        elif self.v_view == "compact":
            self._draw_items(s, self.status_items([]), 16, 16)
        else:
            for i, (label, pct, text) in enumerate(self.stat_rows()):
                y0 = 14 + i * 30
                col = level_color(pct) if pct is not None else C["track"]
                s.spaced(label, 16, y0 + 6, self.f_label, A(C["label"]), 1.2)
                s.text(text, w - 16, y0 + 6, self.f_value, A(C["ink"]), "right")
                s.round_rect(16, y0 + 14, w - 32, 4, 2, fill=A(C["track"]))
                if pct is not None:
                    bw = max(4, (w - 32) * min(pct, 100) / 100)
                    s.round_rect(16, y0 + 14, bw, 4, 2, fill=A(col))
        if not self.is_line and self.app_rows:
            base = self.rows_h()
            s.line(16, base - 5, w - 16, base - 5, A(C["edge"]))
            for i, h in enumerate(self.app_rows):
                y = base + 7 + i * APP_ROW
                if not h["more"]:
                    s.ellipse(20, y, 3.2, 3.2, A(h["color"]))
                s.text(h["name"], 16 if h["more"] else 29, y, self.f_name, A(C["label"] if h["more"] else C["ink"]))
                x = w - 16
                for j, (txt, col, font) in enumerate(((self.ram_text(h["ram"]), C["ink"], self.f_small),
                                                      ("RAM", C["label"], self.f_label),
                                                      (f"{round(h['cpu'])}%", C["ink"], self.f_small),
                                                      ("CPU", C["label"], self.f_label))):
                    x -= s.text(txt, x, y, font, A(col), "right") + (10 if j == 1 else 4)
        if self.locked:                           # a small lock in the space before the first number
            sz, top = self.sz, self.top
            if self.is_line:
                cx, cy = self.line_pad[0] + LINE_L / 2, top + LINE_H / 2 * sz
            else:
                cx, cy = 8 * sz, top + (16 if self.v_view == "compact" else 20) * sz
            s.reset()
            u = max(1, round(self.S))
            ox, oy = round(self.dev(cx) - 3.5 * u), round(self.dev(cy) - 3.5 * u)
            col = A(C["label"])
            for r, row in enumerate(LOCK):
                for c, ch in enumerate(row):
                    if ch == "#":
                        s.rect(ox + c * u, oy + r * u, u, u, col)

    def _draw_items(self, s, items, x, y):
        for it in items:
            if it["dot"]:
                s.ellipse(x + 3, y, 3, 3, A(it["dot"]))
                x += 10
            for txt, col, gap in it["parts"]:
                x += gap
                x += s.text(txt, x, y, self.f_item, A(col))
            x += ITEM_GAP

    def _draw_grip(self, s, W, H):
        if self.v_clear and not self.hover:
            return
        side = self.drag["side"] if self.drag and self.drag["mode"] == "resize" else self.hover_grip
        if not side:
            return
        col = A(C["label"])
        if self.is_line:
            m, gx = (self.lz + H) / 2, 7 if side == "l" else W - 7    # the same grip on either end
            for d in (-1.5, 1.5):
                s.line(gx + d, m - 4, gx + d, m + 4, col, 1.2)
            return
        for a, b in ((4, 10), (4, 6)):
            s.line(W - b, H - a, W - a, H - b, col, 1.3)
        s.line(W - 14, H - 4, W - 4, H - 14, col, 1.3)

    def _pixel_icon(self, s, kind, cx, cy, color):
        """10 x 8 view icon (stage block + status lines) or the 9 x 9 gear, centred on device point cx, cy."""
        u = max(1, round(self.S))
        if kind == "gear":
            ox, oy = round(cx - 4.5 * u), round(cy - 4.5 * u)
            for r, row in enumerate(sp.GEAR):
                for c, ch in enumerate(row):
                    if ch == "#":
                        s.rect(ox + c * u, oy + r * u, u, u, color)
            return
        ox, oy = round(cx - 5 * u), round(cy - 4 * u)
        if kind != "line":
            s.rect(ox, oy, 10 * u, 4 * u, color)
        if kind == "full":
            s.rect(ox, oy + 5 * u, 10 * u, u, color)
            s.rect(ox, oy + 7 * u, 10 * u, u, color)
        elif kind == "compact":
            s.rect(ox, oy + 6 * u, 10 * u, u, color)
        else:
            s.rect(ox, oy + 3 * u, 10 * u, 2 * u, color)

    def _draw_view_buttons(self, s):
        a = self.view_a
        s.round_rect(VB_X, VB_Y, VB_W * 3 + 4, VB_H, 8, fill=A("#12101A", .5 * a))
        for i, v in enumerate(VIEWS):
            cx = VB_X + 2 + i * VB_W
            sel = self.v_view == v
            if sel:
                s.round_rect(cx, VB_Y + 2, VB_W, VB_H - 4, 6, fill=A("#FFFFFF", .22 * a))
            s.reset()
            self._pixel_icon(s, v, self.dev(cx + VB_W / 2), self.dev(VB_Y + VB_H / 2),
                             A("#FFFFFF", (1 if sel else .62) * a))
            s.transform(self.S, MARGIN, MARGIN)

    def _draw_gear(self, s):
        a, x = self.view_a, self._gear_x()
        lit = self.settings_win is not None
        s.round_rect(x, VB_Y, GB_W, GB_H, 8, fill=A("#FFFFFF", .28 * a) if lit else A("#12101A", .5 * a))
        s.reset()
        self._pixel_icon(s, "gear", self.dev(x + GB_W / 2), self.dev(VB_Y + GB_H / 2),
                         A("#FFFFFF", (1 if lit else .8) * a))
        s.transform(self.S, MARGIN, MARGIN)

    def _render_pop(self):
        """One-line view: the view buttons and gear float just outside the bar while hovered."""
        if not (self.is_line and self.hover):
            self.pop.hide()
            return
        S = self.S
        key = (self.v_view, self.settings_win is not None, S)
        if self.pop_surf is None or key != self.pop_key:
            self.pop_key = key
            if self.pop_surf:
                self.pop_surf.close()
            ps = self.pop_surf = gfx.Surface(math.ceil((POP_W + 2 * POP_PAD) * S), math.ceil((POP_H + 2 * POP_PAD) * S))
            ps.clear(0)
            ps.transform(S, POP_PAD, POP_PAD)
            for i in range(3):
                e = 1 + i * 1.2
                ps.round_rect(-e, -e + 1.5, POP_W + 2 * e, POP_H + 2 * e, 8 + e, fill=A("#000000", .06))
            ps.round_rect(.5, .5, POP_W - 1, POP_H - 1, 8, fill=A(C["btn"]), stroke=A(C["edge"]))
            dev = lambda v: (POP_PAD + v) * S
            for i, v in enumerate(VIEWS):
                x = 2 + i * VB_W
                sel = self.v_view == v
                if sel:
                    ps.transform(S, POP_PAD, POP_PAD)
                    ps.round_rect(x, 2, VB_W, VB_H - 4, 6, fill=A(C["sel"]))
                ps.reset()
                self._pixel_icon(ps, v, dev(x + VB_W / 2), dev(VB_H / 2), A("#FFFFFF" if sel else C["label"]))
            ps.transform(S, POP_PAD, POP_PAD)
            sx = 2 + 3 * VB_W + 2
            ps.line(sx + .5, 3, sx + .5, POP_H - 3, A(C["edge"]))
            gx = 2 + 3 * VB_W + 5
            lit = self.settings_win is not None
            if lit:
                ps.round_rect(gx, 2, VB_W, VB_H - 4, 6, fill=A(C["sel"]))
            ps.reset()
            self._pixel_icon(ps, "gear", dev(gx + VB_W / 2), dev(VB_H / 2), A("#FFFFFF" if lit else C["label"]))
        self.pop.show(self.pop_surf, *self._pop_pos())

    # ---------- the pet (device pixels, crisp sprite blocks) ----------
    def _runs(self, key, build, pal_mirror):
        """Cached sprite runs with ARGB colors: key -> [(col, row, length, argb)]."""
        r = self._pet_cache.get(key)
        if r is None:
            if len(self._pet_cache) > 400:
                self._pet_cache.clear()
            cells = {}
            build(cells)
            r = self._pet_cache[key] = [(c, row, n, A(col)) for c, row, n, col in sp.runs(cells, pal_mirror)]
        return r

    def _blit(self, s, runs, ox, oy, alpha=None):
        """alpha: one value for everything, or a function of the row (the ghost fades toward its hem)."""
        ps, per_row = self.ps, callable(alpha)
        for c, r, n, col in runs:
            if alpha is not None:
                a = alpha(r) if per_row else alpha
                if a <= 0:
                    continue
                col = (round(a * 255) << 24) | (col & 0xFFFFFF)
            s.rect(ox + c * ps, oy + r * ps, n * ps, ps, col)

    def _draw_pet(self, s):
        p, S, ps = self.pet, self.S, self.ps
        busy, painting, station, inten = self.mood == "busy", self._painting(), self._station(), self.fx_inten
        step = self.fx_step if busy else 0
        magic = step if self.effect == "magic" else 0             # 1 wand, 2 + magic circle, 3 + sparkles
        brush = step if self.effect == "painting" else 0          # 1 brush, 2 + palette, 3 + easel painting
        trick = step if self.effect == "trick" else 0             # 1 lantern, 2 + sweets, 3 + bats
        at_work = station and p.easel >= 1 and p.target is None
        work = None                               # Construction / Cooking / Computer: (effect, step, frame)
        if step and self.effect in WORK_EFFECTS:  # step 3 away from the work spot: still holding the step-2 items
            work = (self.effect, step if step < 3 or at_work else 2, sp.work_frame(self.effect, self.t))
        sleeping = self.mood == "sleep" and p.target is None and p.jump < 0
        walking = not sleeping and (p.target is not None or (not station and p.sp > .12))
        hops = self._hops()
        step = 0 if hops else int(p.phase / STRIDE) % 2 if walking else 0
        jump = math.sin(math.pi * p.jump / .45) * 10 if p.jump >= 0 else 0.0
        lift = self.hop_lift() * ps if hops and not sleeping else 0.0      # the pumpkin's hop, in sprite pixels
        gyd = round(self.dev(self.ground))
        ox = round(self.dev(p.x) - 10 * ps)
        oy0 = gyd - 18 * ps
        oy = oy0 - (max(1, round(S)) if step else 0) - round(jump * S) - round(lift)
        mirror = p.dir < 0
        colx = lambda c: ox + ((sp.MIRROR - c if mirror else c) + .5) * ps
        k = round(jump / 5 + lift / (2 * ps))     # ground shadow, smaller while hopping
        sh = A("#000000", .22)
        s.rect(ox + (5 + k) * ps, oy0 + 18 * ps, (10 - 2 * k) * ps, ps, sh)
        s.rect(ox + (6 + k) * ps, oy0 + 19 * ps, (8 - 2 * k) * ps, ps, sh)
        if magic >= 2:                            # a rotating pixel magic circle
            s.glow(self.dev(p.x), gyd + 2 * S, 34 * S, 8 * S, A(C["magic"], min(1.0, .3 + inten * .3)))
            a0 = self.t * (1.2 + inten * 2.5)
            light, mag = A("#E4DBFF"), A(C["magic"])
            for i in range(36):
                if i % 3 == 2:
                    continue
                ang = a0 + i / 36 * math.tau
                s.rect(ox + (10 + round(math.cos(ang) * 14)) * ps, oy0 + (19 + round(math.sin(ang) * 2.5)) * ps, ps, ps,
                       light if i % 6 < 2 else mag)
        if p.easel > 0 and self.effect in WORK_EFFECTS:
            self._work_spot(s, False, ox, oy0, mirror)
        elif p.easel > 0:
            fr = math.ceil(15 * (1 - p.easel))
            q = round(p.paint * 40) / 40
            runs = self._runs(("easel", q, fr, mirror),
                              lambda c: sp.stamp(c, sp.easel_rows(q), 17, 4, sp.EASEL_PAL, fr), mirror)
            self._blit(s, runs, ox, oy0)
        expr = ("sleep" if sleeping else "happy" if p.hearts else "surprised" if p.surprise > 0
                else "happy" if station and p.done > 0
                # "focused" (busy) is not used (it can look a bit sad); the sprite art is kept.
                else "blink" if p.blink > 0 else "glance" if p.glance > 0 else "neutral")
        wand = magic >= 1 and not sleeping
        wob = int(self.t * 1.5) % 2 if wand else 0
        if painting and p.easel >= 1 and p.target is None:
            dab = 1 if p.done > 0 else int(self.t * 5) % 2       # painting at the easel
        elif brush and not sleeping:
            dab = 1 if brush >= 2 and self.t % 1.4 > 1.15 else 0  # holding the brush; step 2: a small tap now and then
        else:
            dab = -1
        palette = brush >= 2 and not sleeping
        feet = 1 if jump > 0 else step
        hat = self.worn_hat()
        cat = self.character == "cat"
        dy = PET_DY.get(self.character, 0)
        lit = spp.glow_level(self.t, busy, walking, sleeping) if hops else 0.0
        if trick and sleeping:                    # asleep it puts the lantern down (it simply goes away)
            trick = 0
        carry_dy = round(math.sin(self.t * 2)) if trick and self.carries() else 0
        carry_lit = sph.lantern_lit(self.t) if trick else None
        if trick >= 3:                            # the bats behind the pet, on the far side of their rings
            back, front = sph.bats(self.t)
            self._blit_bats(s, back, ox, oy0)
        if lit > 0:                               # warm light spilling out of the carved holes
            s.glow(colx(sp.PX + 5), oy + (sp.PY + spp.TOP + 4) * ps, 30 * S, 22 * S,
                   A(spp.HALO, .10 + .22 * lit))
        if wand:                                  # the wand star: the cat holds it 1 row higher
            s.glow(colx(sp.PX + 14), oy + (sp.PY + (1.5 if cat else 2.5) + wob) * ps, 8 * S, 8 * S,
                   A(C["star"], .35 + .3 * abs(math.sin(self.t * 6))))

        if self.character == "ghost":
            oy = self._draw_ghost(s, ox, oy, mirror, expr, sleeping, hat, busy, wob if wand else -1, dab, palette,
                                  work, trick, carry_dy, carry_lit)
        else:
            def build(cells):
                self.pose_cells(cells, expr, feet, sleeping, hat, wob if wand else -1, dab, palette, work,
                                None if hops else lit, trick=trick, carry_dy=carry_dy)

            key = ("pet", self.character, expr, hat, wand, wob, dab, feet, mirror, sleeping, palette, work,
                   trick, carry_dy)
            self._blit(s, self._runs(key, build, mirror), ox, oy)
        if lit > 0:                               # the flickering carving: a few pixels, drawn fresh every frame
            col = A(spp.hole_color(lit))
            for c, r in spp.lit_cells(expr):
                c = sp.MIRROR - (sp.PX + c) if mirror else sp.PX + c
                s.rect(ox + c * ps, oy + (sp.PY + spp.TOP + r) * ps, ps, ps, col)
        if trick and self.character != "ghost":   # the lantern's own candle (the ghost bakes it into its props)
            c0, r0 = sph.CARRY_AT[0] + (1 if self.carries() else 0), sph.CARRY_AT[1] + dy + carry_dy
            col = A(sph.lantern_color(carry_lit))
            for c, r in sph.CARRY_FACE:
                cc = sp.MIRROR - (c0 + c) if mirror else c0 + c
                s.rect(ox + cc * ps, oy + (r0 + r) * ps, ps, ps, col)
        if trick >= 3:
            self._blit_bats(s, front, ox, oy0)    # the bats passing in front of the pet
        if p.easel > 0 and self.effect in WORK_EFFECTS:
            self._work_spot(s, True, ox, oy0, mirror)
        if work:                                  # steam and dust: a few pixels, drawn fresh every frame
            for c, r, col in sp.work_puffs(self.effect, work[1], self.t, cat, at_work, 0 if at_work else dy):
                s.rect(ox + (sp.MIRROR - c if mirror else c) * ps, (oy0 if at_work else oy) + r * ps, ps, ps, A(col))
        if sleeping:                              # pixel "z Z" drifting up
            zt = (self.t % 2.4) / 2.4
            zs = ((sp.Z_SMALL, 16, 8), (sp.Z_BIG, 19, 3)) if cat else ((sp.Z_SMALL, 16, 7), (sp.Z_BIG, 20, 2))
            for sprite, c, r, a in ((z[0], z[1], z[2], 1 - zt * .6) for z in zs):
                runs = self._runs(("z", len(sprite)), lambda cells, spr=sprite: sp.stamp(cells, spr, 0, 0, {"#": "#CFC4FF"}), False)
                self._blit(s, runs, ox + c * ps + round(zt * 4 * S), oy + r * ps - round(zt * 8 * S), a)

    def _blit_bats(self, s, flock, ox, oy0):
        """The Halloween bats: they whirl around the pet, so they are not mirrored with it."""
        for x, y, frame in flock:
            runs = self._runs(("bat", frame), lambda c, f=frame: sp.stamp(c, sph.BAT[f], 0, 0, sph.BAT_PAL), False)
            self._blit(s, runs, ox + x * self.ps, oy0 + y * self.ps)

    def _draw_ghost(self, s, ox, oy, mirror, expr, sleeping, hat, busy, wob, dab, palette, work,
                    trick=0, carry_dy=0, carry_lit=None):
        """The ghost in three passes, because each part fades differently: the sheet (more see-through toward
        the hem), the face (always readable) and the props floating beside it on their own bob.
        -> the row the body ended up on, so the sleeping "z Z" follows it."""
        p, ps = self.pet, self.ps
        vest = bool(work) and work[0] == "build" and work[1] >= 2
        dim = spg.SLEEP_DIM if sleeping else spg.vanish_dim(p.fade_t)
        y0 = sp.PY + spg.TOP + (spg.SLEEP_DROP if sleeping else 0)
        body_oy = oy + round(spg.bob(self.t, busy, sleeping) * ps)
        body = self._runs(("ghost", hat, vest, sleeping, mirror),
                          lambda c: self.ghost_cells(c, expr, sleeping, hat, vest, face=False), mirror)
        self._blit(s, body, ox, body_oy, lambda r: spg.row_alpha(r - y0, dim))
        face = self._runs(("ghost-face", expr, sleeping, mirror),
                          lambda c: self.ghost_cells(c, expr, sleeping, face=True, body=False), mirror)
        self._blit(s, face, ox, body_oy, spg.face_alpha(dim))
        if wob >= 0 or dab >= 0 or palette or work or trick:
            props = self._runs(("ghost-props", wob, dab, palette, work, mirror, trick, carry_dy, carry_lit),
                               lambda c: self.ghost_props(c, wob, dab, palette, work, trick, carry_dy, carry_lit),
                               mirror)
            self._blit(s, props, ox, oy + round(spg.prop_bob(self.t) * ps), max(0.0, 1 - dim))
        return body_oy

    def _work_spot(self, s, front, ox, oy0, mirror):
        """Step 3's work spot (behind or in front of the pet), rising out of the ground as p.easel goes 0 -> 1."""
        eff, p = self.effect, self.pet
        state = sp.work_state(eff, front, self.t, p.paint)
        if state is None:
            return
        top = round(19 - 16 * p.easel)            # rows above this are still hidden

        def build(cells):
            sp.work_spot(cells, eff, front, state)
            for k in [k for k in cells if k[1] < top]:
                del cells[k]
        self._blit(s, self._runs(("work", eff, front, state, top, mirror), build, mirror), ox, oy0)

    def _draw_particles(self, s):
        p, S, ps = self.pet, self.S, self.ps
        for x, y, age, life in p.sparks:
            k = age / life
            xd, yd = round(self.dev(x)), round(self.dev(y - k * 40))
            col = A(C["star"] if k < .5 else C["magic"], 1 - k)
            s.rect(xd, yd - ps, ps, ps * 3, col)
            s.rect(xd - ps, yd, ps * 3, ps, col)
        for x, y, _, _, age, col in p.drops:
            s.rect(round(self.dev(x)), round(self.dev(y)), ps, ps, A(col, min(1.0, 1.6 - age)))
        gyd = round(self.dev(self.ground))
        for x, y, vy, col, _ in p.sweets:         # Halloween sweets: 2 x 2, sitting on the ground row
            yd = gyd - ps if vy is None else round(self.dev(y)) - ps
            s.rect(round(self.dev(x)) - ps, yd, 2 * ps, 2 * ps, A(col))
        heart = self._runs(("heart",), lambda c: sp.stamp(c, sp.HEART, 0, 0, {"r": C["heart"]}), False)
        for x, y, age, o in p.hearts:
            if age < 0:
                continue
            k = age / 1.1
            self._blit(s, heart, round(self.dev(x + math.sin(k * 6 + o) * 3)) - 5 * ps // 2,
                       round(self.dev(y - k * 26)), 1 - k)

    # ---------- lifecycle ----------
    def quit(self):
        for job in self.jobs.values():
            try:
                self.root.after_cancel(job)
            except (tk.TclError, ValueError):
                pass
        self._save_settings()
        if self.tray:
            self.tray.remove()
        self.close_settings()
        self.gpu_reader.close()
        self.pop.destroy()
        self.win.destroy()
        self.root.destroy()

    def run(self):
        self.root.mainloop()


def _single_instance():
    """Returns False if another Status Pet is already running (the installer checks the same lock)."""
    k32 = ctypes.WinDLL("kernel32", use_last_error=True)
    k32.CreateMutexW.restype = ctypes.c_void_p
    global _MUTEX
    _MUTEX = k32.CreateMutexW(None, False, "Local\\StatusPet.SingleInstance")
    return ctypes.get_last_error() != 183   # ERROR_ALREADY_EXISTS


def _log_errors():
    """Double-clicked (pythonw) runs have no console: send errors and crash tracebacks to a log file."""
    import faulthandler
    import sys
    if sys.stderr is not None:
        return
    os.makedirs(DATA, exist_ok=True)
    log = open(os.path.join(DATA, "status_pet.log"), "a", encoding="utf-8", buffering=1)
    sys.stderr = sys.stdout = log
    try:
        os.dup2(log.fileno(), 2)          # C-level errors (fatal errors) too
    except OSError:
        pass
    faulthandler.enable(log)
    print(time.strftime("--- started %Y-%m-%d %H:%M:%S ---"), file=log)


if __name__ == "__main__":
    _log_errors()
    if _single_instance():
        try:
            ctypes.windll.shcore.SetProcessDpiAwareness(1)
        except (AttributeError, OSError):
            pass
        Gadget().run()
