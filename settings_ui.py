"""The Settings window (Tk): tabs General · Pet · Items · Effects · Apps.

The window is rebuilt from scratch on every change (it is small and only open now and then), so the
code stays a plain "draw what the state says" function per tab. Nothing here runs while it is closed.
"""
import ctypes
import math
import time
import tkinter as tk

import autostart
import gfx
import hats as hatlib
import i18n
from i18n import tr
import seasons
import sprites as sp
import sprites_halloween as sph
import sprites_pumpkin as spp
from selfusage import SelfUsage
from update_check import open_page

VERSION = "1.0"
KEY = "#010203"                 # window color made fully transparent: gives the rounded corners
PER_PAGE = 5                    # tiles per row; past that, ‹ › arrows
TILE, SOFT, PICK_BG, HOVER = "#272333", "#293333", "#17151E", "#2A2636"
BORDER, TOG_ON, DANGER, DANGER_EDGE = "#4A4458", "#3F7E57", "#5A2E36", "#7A3A44"
HOME = ("    #    ", "   ###   ", "  ## ##  ", " ##   ## ", "##     ##", " #     # ",
        " # ##  # ", " # ##  # ", " ####### ")   # 9 x 9 Home icon (title row, opens the website)
TABS = (("general", "General"), ("pet", "Pet"), ("items", "Items"), ("effects", "Effects"), ("apps", "Apps"))
CHARACTERS = (("slime", "Slime"), ("cat", "Siamese"), ("pumpkin", "Jack-o'-lantern"), ("ghost", "Ghost"))
SWATCHES = ("#FF8A3D", "#F2C166", "#6CC486", "#37B6AA", "#37A5CC", "#31A8FF", "#9585F0", "#E0417A",
            "#F08B7E", "#C9CED6")      # app dot colors (orange, yellow, green, teal, cyan, blue, purple, pink, coral, grey)


def rrect(cv, x0, y0, x1, y1, r, **kw):
    """Rounded rectangle as one smooth polygon item."""
    r = max(0, min(r, (x1 - x0) / 2, (y1 - y0) / 2))
    pts = (x0 + r, y0, x1 - r, y0, x1, y0, x1, y0 + r, x1, y1 - r, x1, y1, x1 - r, y1, x0 + r, y1, x0, y1, x0, y1 - r,
           x0, y0 + r, x0, y0)
    return cv.create_polygon(pts, smooth=True, **kw)


def mix(a, b, k):
    """Color a, faded k (0..1) of the way into color b."""
    a, b = int(a[1:], 16), int(b[1:], 16)
    return "#%02X%02X%02X" % tuple(round(((a >> s) & 255) * (1 - k) + ((b >> s) & 255) * k) for s in (16, 8, 0))


class SettingsUI:
    def __init__(self, g, C):
        self.g, self.C = g, C
        S = g.S
        self.px = lambda n: round(n * S)
        self.W = self.px(280)
        self.inset = self.px(4)                    # body sits inside the rounded corners
        self.cw = self.W - 2 * self.inset - 2 * self.px(10)   # content width
        self.tab = "general"
        self.picker = None                         # app id whose hat list is open ("__default" for Default)
        self.pages = {}
        self.more = False
        self.confirm_clear = False
        self.shown = set(g.tracked)                # rows in the closed app list (nothing jumps while open)
        self.confirm = None
        self.note = None                           # short footer message (e.g. "Removed …")
        self.imgs = []
        self.placed = False
        self.cache = {}                            # finished pictures reused across rebuilds (kept while open)
        self.usage = SelfUsage()
        self.usage_val = (None, None)
        self.usage_lbl = None
        self.jobs = []
        self.fx = {"effect": None, "t0": 0.0}     # Effects tab preview: the effect pointed at, since when
        self.fx_job = None                         # its next frame (runs only while an effect is pointed at)
        self.fx_vars = []
        self.pick_mode = "hat"                     # the app list's "Hat | Effect" side
        self.link_font = g.tf_small.copy()
        self.link_font.configure(underline=True)
        self.tiny = g.tf_small.copy()
        self.tiny.configure(size=-self.px(9.5))
        self.lang_fonts = {}                            # code -> font copy: each name shown in its own font
        for code, _name in i18n.LANGS:
            f = g.tf_small.copy()
            f.configure(family=i18n.font(code=code)[0])
            self.lang_fonts[code] = f
        self.lang_open = False                          # General tab: the language list is open

        win = self.win = tk.Toplevel(g.root)
        win.withdraw()
        win.overrideredirect(True)
        win.attributes("-topmost", g.topmost.get())
        win.configure(bg=KEY)
        win.attributes("-transparentcolor", KEY)
        self.cv = tk.Canvas(win, bg=KEY, highlightthickness=0, bd=0)
        self.cv.pack(fill="both", expand=True)
        self.body = tk.Frame(self.cv, bg=C["panel"])
        self.body_item = self.cv.create_window(self.inset, self.inset, window=self.body, anchor="nw",
                                               width=self.W - 2 * self.inset)
        win.bind("<Escape>", self._escape)
        g.settings_win = win                       # so _place_settings can place it before it shows
        self.refresh()
        win.deiconify()
        win.focus_force()
        self._tick_usage()

    # ---------- life ----------
    def close(self):
        if self.fx_job:
            self.win.after_cancel(self.fx_job)
        for j in self.jobs:
            try:
                self.win.after_cancel(j)
            except (tk.TclError, ValueError):
                pass
        self.win.destroy()

    def relang(self):
        """The language changed: the window's own font copies follow the gadget's fonts, then redraw."""
        for f in (self.link_font, self.tiny):
            f.configure(family=self.g.tf_small.cget("family"), weight=self.g.tf_small.cget("weight"))
        self.refresh()

    def _escape(self, _e=None):
        if self.picker or self.confirm or self.confirm_clear or self.lang_open:
            self.picker = self.confirm = None
            self.confirm_clear = self.lang_open = False
            self.refresh()
        else:
            self.g.close_settings()

    def _later(self, ms, fn):
        self.jobs.append(self.win.after(ms, fn))

    def refresh(self):
        for w in self.body.winfo_children():
            w.destroy()
        self.imgs = []
        self.usage_lbl = self.g.size_lbl = None
        self._build()
        self.body.update_idletasks()
        h = self.body.winfo_reqheight()
        self.cv.itemconfigure(self.body_item, height=h)
        H = h + 2 * self.inset
        self.cv.configure(width=self.W, height=H)
        self.cv.delete("bg")
        rrect(self.cv, 0, 0, self.W - 1, H - 1, self.px(12), fill=self.C["panel"], outline=self.C["edge"], tags="bg")
        self.cv.tag_lower("bg")
        self.win.update_idletasks()
        if not self.placed:                        # place once; after that a tab switch or change never moves it
            self.placed = True
            self.g._place_settings()

    # ---------- small widgets ----------
    def _label(self, parent, text, fg=None, font=None, **kw):
        return tk.Label(parent, text=text, bg=kw.pop("bg", self.C["panel"]), fg=fg or self.C["ink"],
                        font=font or self.g.tf_ui, **kw)

    def _line(self, parent=None):
        tk.Frame(parent or self.body, bg=self.C["edge"], height=1).pack(fill="x")

    def _head(self, parent, text, right=""):
        row = tk.Frame(parent, bg=self.C["panel"])
        row.pack(fill="x", pady=(0, self.px(6)))
        self._label(row, text.upper(), self.C["label"], self.g.tf_head).pack(side="left")
        if right:
            self._label(row, right, self.C["label"], self.g.tf_small).pack(side="right")
        return row

    def _link(self, parent, text, cmd):
        lb = self._label(parent, text, self.C["label"], self.link_font, cursor="hand2")
        lb.bind("<Button-1>", lambda e: cmd())
        lb.bind("<Enter>", lambda e: lb.config(fg=self.C["ink"]))
        lb.bind("<Leave>", lambda e: lb.config(fg=self.C["label"]))
        return lb

    def _button(self, parent, text, cmd, bg=HOVER, edge=None):
        b = tk.Label(parent, text=text, bg=bg, fg=self.C["ink"], font=self.g.tf_small, cursor="hand2",
                     padx=self.px(9), pady=self.px(2), highlightthickness=1,
                     highlightbackground=edge or self.C["edge"])
        b.bind("<Button-1>", lambda e: cmd())
        return b

    def _aa(self, parent, w, h, draw, cmd=None, bg=None, key=None):
        """A small smooth (anti-aliased) picture drawn with GDI+ (gfx) on the background color: Tk can't smooth
        edges. draw(surface) draws in design units (1 = one logical pixel). With a key, the finished picture is
        kept and reused on the next rebuild (the window is rebuilt on every change)."""
        bg = bg or self.C["panel"]
        ck = key and (key, w, h, bg)
        img = self.cache.get(ck) if ck else None
        if img is None:
            s = gfx.Surface(w, h)
            s.clear(gfx.argb(bg))
            s.transform(self.g.S)
            draw(s)
            buf = (ctypes.c_ubyte * s.nbytes)()
            s.save_to(buf)
            s.close()
            rgb = bytearray(w * h * 3)
            raw = bytes(buf)
            rgb[0::3], rgb[1::3], rgb[2::3] = raw[2::4], raw[1::4], raw[0::4]
            img = tk.PhotoImage(master=self.win, data=b"P6 %d %d 255\n" % (w, h) + bytes(rgb), format="PPM")
            if ck:
                self.cache[ck] = img
            else:
                self.imgs.append(img)
        lb = tk.Label(parent, image=img, bg=bg, bd=0, highlightthickness=0, cursor="hand2" if cmd else "")
        if cmd:
            lb.bind("<Button-1>", lambda e: cmd())
        return lb

    def _switch(self, parent, on, cmd, bg=None):
        """Toggle switch: 28 x 16 pill (#2E2A3A off, #3F7E57 on), 12 px knob (#8F88A8 off, #ECE9F3 on)."""
        def draw(s):
            s.round_rect(0, 0, 28, 16, 8, fill=gfx.argb(TOG_ON if on else self.C["track"]))
            s.ellipse(20 if on else 8, 8, 6, 6, gfx.argb(self.C["ink"] if on else self.C["label"]))
        return self._aa(parent, self.px(28), self.px(16), draw, cmd, bg, key=("switch", on))

    def _check(self, parent, on, cmd):
        """Checkbox: 14 px, radius 4; off = 1.5 px #4A4458 border, on = green fill + dark check mark."""
        def draw(s):
            if on:
                s.round_rect(0, 0, 14, 14, 4, fill=gfx.argb(self.C["accent"]))
                s.line(3.5, 7.2, 5.8, 9.5, gfx.argb(self.C["panel"]), 2)
                s.line(5.8, 9.5, 10.5, 4.5, gfx.argb(self.C["panel"]), 2)
            else:
                s.round_rect(.75, .75, 12.5, 12.5, 3.5, stroke=gfx.argb(BORDER), width=1.5)
        return self._aa(parent, self.px(14), self.px(14), draw, cmd, key=("check", on))

    def _dot(self, parent, color):
        d = self.px(8)
        cv = tk.Canvas(parent, width=d, height=d, bg=self.C["panel"], highlightthickness=0, bd=0)
        cv.create_oval(0, 0, d - 1, d - 1, fill=color, outline="")
        return cv

    def _nohat(self, cv, cx, cy, r):
        col = self.C["label"]
        cv.create_oval(cx - r, cy - r, cx + r, cy + r, outline=col, width=max(1, self.px(1.5)))
        d = r * .7
        cv.create_line(cx - d, cy + d, cx + d, cy - d, fill=col, width=max(1, self.px(1.5)))

    def _season_mark(self, cv, key, w):
        """A seasonal tile shows its season's pixel mark in the top-right corner."""
        season = seasons.season_of(key)
        icon = season and self._season_icon(season)
        if icon:
            cv.create_image(w - self.px(3), self.px(3), image=icon, anchor="ne")

    def _season_icon(self, season):
        """The season's pixel mark (seasons.SEASONS[...]["mark"]) at the pet's pixel size; None if it has none."""
        rows = seasons.SEASONS[season].get("mark")
        if not rows:
            return None
        grid = [[seasons.MARK_PAL.get(ch) for ch in row] for row in rows]
        return self._image(grid, self.g.ps, key=("season", season))

    # ---------- pixel images ----------
    def _image(self, grid, k, key=None):
        """grid: rows of '#RRGGBB' / None -> a Tk image, k screen pixels per sprite pixel (kept for reuse when keyed)."""
        ck = key and (key, k)
        if ck in self.cache:
            return self.cache[ck]
        h, w = len(grid), max(len(r) for r in grid)
        img = tk.PhotoImage(master=self.win, width=w * k, height=h * k)
        for y, row in enumerate(grid):
            for x, col in enumerate(row):
                if col:
                    img.put(col, to=(x * k, y * k, x * k + k, y * k + k))
        if ck:
            self.cache[ck] = img
        else:
            self.imgs.append(img)
        return img

    @staticmethod
    def _grid(cells):
        xs, ys = [c for c, _ in cells], [r for _, r in cells]
        x0, y0 = min(xs), min(ys)
        grid = [[None] * (max(xs) - x0 + 1) for _ in range(max(ys) - y0 + 1)]
        for (c, r), col in cells.items():
            grid[r - y0][c - x0] = col
        return grid

    def _hat_img(self, hat_id, k):
        rows = self.g.hats[hat_id]["rows"]
        return self._image(rows, k, key=("hat", hat_id, id(rows)))   # id(rows): a reloaded hat gets a new picture

    # ---------- tiles and pages ----------
    def _tile(self, parent, w, h, draw=None, sel=False, cmd=None, dashed=False, text=None, enter=None, leave=None):
        cv = tk.Canvas(parent, width=w, height=h, bg=parent["bg"], highlightthickness=0, bd=0,
                       cursor="hand2" if cmd else "")

        def paint(hover=False):
            cv.delete("frame")
            if dashed:
                rrect(cv, 1, 1, w - 2, h - 2, self.px(7), fill="", outline=self.C["label"] if hover else BORDER,
                      dash=(3, 2), tags="frame")
            else:
                rrect(cv, 0, 0, w - 1, h - 1, self.px(7), fill=SOFT if sel else TILE,
                      outline=self.C["accent"] if sel else BORDER if hover and cmd else TILE, tags="frame")
            cv.tag_lower("frame")

        paint()
        if text:
            cv.create_text(w / 2, h / 2, text=text, fill=self.C["label"], font=self.g.tf_x)
        if draw:
            draw(cv, w, h)
        cv.bind("<Enter>", lambda e: (paint(True), enter and enter()))
        cv.bind("<Leave>", lambda e: (paint(False), leave and leave()))
        if cmd:
            cv.bind("<Button-1>", lambda e: cmd(e))
        return cv

    def _pager(self, parent, name, keys, width, tile_h, make, lead=None, arrows=True):
        """Keys in pages of one row. make(parent, key, tile_w, tile_h) -> widget; lead() is shown first on each page.
        arrows=False puts the ‹ › + dots on their own centred bar under the row (the Effects tab's style) instead
        of inline in the row (used by the Items tab)."""
        per = PER_PAGE - 1 if lead else PER_PAGE
        pages = max(1, -(-len(keys) // per))
        page = self.pages.get(name, 0)
        if page >= pages:
            page = self.pages[name] = 0
        gap, aw = self.px(4), self.px(16)
        inline = arrows and pages > 1
        inner = width - (2 * (aw + gap) if inline else 0)
        tw = (inner - gap * (PER_PAGE - 1)) // PER_PAGE
        wrap = tk.Frame(parent, bg=parent["bg"])
        row = tk.Frame(wrap, bg=parent["bg"])
        row.pack(anchor="w")

        def arrow(text, step, on):
            def go(_e):
                self.pages[name] = page + step
                self.refresh()
            cv = self._tile(row, aw, tile_h, cmd=go if on else None,
                            draw=lambda c, w, h: c.create_text(w / 2, h / 2, text=text, font=self.g.tf_ui,
                                                               fill=self.C["ink"] if on else BORDER))
            cv.pack(side="left", padx=(0, gap))

        if inline:
            arrow("‹", -1, page > 0)
        items = ([lead] if lead else []) + keys[page * per:page * per + per]
        for i, k in enumerate(items):
            wgt = k(row, tw, tile_h) if callable(k) else make(row, k, tw, tile_h)
            wgt.pack(side="left", anchor="n", padx=(0, gap))
        if inline:
            for _ in range(PER_PAGE - len(items)):          # keep the › arrow in place on a short last page
                tk.Frame(row, bg=parent["bg"], width=tw, height=1).pack(side="left", padx=(0, gap))
            arrow("›", 1, page < pages - 1)
            d = self.px(4)
            dots = tk.Canvas(wrap, width=pages * d * 2, height=d + self.px(3), bg=parent["bg"], highlightthickness=0)
            for i in range(pages):
                dots.create_oval(i * d * 2 + d / 2, self.px(3), i * d * 2 + d * 1.5, self.px(3) + d,
                                 fill=self.C["label"] if i == page else BORDER, outline="")
            dots.pack(pady=(self.px(2), 0))
        elif pages > 1:                                     # below-row bar (Items tab): keep row width steady, too
            for _ in range(PER_PAGE - len(items)):
                tk.Frame(row, bg=parent["bg"], width=tw, height=1).pack(side="left", padx=(0, gap))
            self._page_bar(wrap, name, pages).pack(fill="x", pady=(self.px(4), 0))
        return wrap

    def _page_bar(self, parent, name, pages, width=None):
        """‹ dots › under a block of tiles, for pages that are a grid rather than one row (the Effects tab).
        Same arrows and dots as the Items tab's row pager."""
        px, C = self.px, self.C
        page = self.pages.get(name, 0)
        bar = tk.Frame(parent, bg=parent["bg"], width=width)
        inner = tk.Frame(bar, bg=parent["bg"])
        inner.pack()                                       # centred under the tiles
        d, aw, ah = px(4), px(16), px(14)

        def arrow(text, step, on):
            def go(_e):
                self.pages[name] = page + step
                self.refresh()
            self._tile(inner, aw, ah, cmd=go if on else None,
                       draw=lambda c, w, h: c.create_text(w / 2, h / 2, text=text, font=self.g.tf_ui,
                                                          fill=C["ink"] if on else BORDER)
                       ).pack(side="left", padx=(0, px(4)))
        arrow("‹", -1, page > 0)
        dots = tk.Canvas(inner, width=pages * d * 2, height=ah, bg=parent["bg"], highlightthickness=0)
        for i in range(pages):
            y = ah / 2 - d / 2
            dots.create_oval(i * d * 2 + d / 2, y, i * d * 2 + d * 1.5, y + d,
                             fill=C["label"] if i == page else BORDER, outline="")
        dots.pack(side="left", padx=(0, px(4)))
        arrow("›", 1, page < pages - 1)
        return bar

    # ---------- the window ----------
    def _build(self):
        C, px, body = self.C, self.px, self.body
        head = tk.Frame(body, bg=C["panel"], padx=px(10), pady=px(4), cursor="fleur")
        head.pack(fill="x")
        title = self._label(head, tr("Settings"), font=self.g.tf_b, cursor="fleur")
        title.pack(side="left")
        x = self._label(head, "×", C["label"], self.g.tf_x, cursor="hand2", padx=px(6))
        x.pack(side="right")
        x.bind("<Button-1>", lambda e: self.g.close_settings())
        x.bind("<Enter>", lambda e: x.config(bg=HOVER, fg=C["ink"]))
        x.bind("<Leave>", lambda e: x.config(bg=C["panel"], fg=C["label"]))
        self._home(head).pack(side="right", padx=(0, px(2)))
        for w in (head, title):
            w.bind("<ButtonPress-1>", self.g._settings_press)
            w.bind("<B1-Motion>", self.g._settings_drag)
            w.bind("<ButtonRelease-1>", self.g._settings_release)
        self._line()

        tabs = tk.Frame(body, bg=C["panel"], padx=px(6))
        tabs.pack(fill="x", pady=(px(4), 0))
        for key, name in TABS:
            cur = key == self.tab
            cell = tk.Frame(tabs, bg=C["panel"])
            cell.pack(side="left", expand=True, fill="x")
            lb = self._label(cell, tr(name), C["ink"] if cur else C["label"], self.g.tf_b if cur else self.g.tf_small,
                             cursor="hand2", pady=px(4))
            lb.pack(fill="x")
            tk.Frame(cell, bg=C["accent"] if cur else C["panel"], height=px(2)).pack(fill="x")
            lb.bind("<Button-1>", lambda e, k=key: self._set_tab(k))
        self._line()

        sec = tk.Frame(body, bg=C["panel"], padx=px(10), pady=px(10))
        sec.pack(fill="x")
        reset = getattr(self, "_tab_" + self.tab)(sec)
        self._line()
        self._footer(reset)

    def _home(self, parent):
        """Pixel Home icon left of ×; grey, lit on hover (like ×); click -> the website."""
        C = self.C
        u = max(1, round(self.g.S * 1.25))
        n = len(HOME) * u
        imgs = []
        for col in (C["label"], C["ink"]):
            img = tk.PhotoImage(master=self.win, width=n, height=n)
            for r, row in enumerate(HOME):
                for c, ch in enumerate(row):
                    if ch == "#":
                        img.put(col, to=(c * u, r * u, c * u + u, r * u + u))
            imgs.append(img)
        self.imgs.extend(imgs)
        lb = tk.Label(parent, image=imgs[0], bg=C["panel"], bd=0, cursor="hand2", padx=self.px(6), pady=self.px(5))
        lb.bind("<Button-1>", lambda e: open_page())
        lb.bind("<Enter>", lambda e: lb.config(image=imgs[1], bg=HOVER))
        lb.bind("<Leave>", lambda e: lb.config(image=imgs[0], bg=C["panel"]))
        return lb

    def _set_tab(self, key):
        self.tab, self.picker, self.confirm = key, None, None
        self.fx["effect"] = None
        self.lang_open = False
        self.refresh()

    def _footer(self, reset):
        C, px = self.C, self.px
        f = tk.Frame(self.body, bg=C["panel"], padx=px(10), pady=px(6))
        f.pack(fill="x")
        if self.confirm == self.tab and reset:
            label, fn = reset
            self._label(f, tr(f"Reset {label}?"), font=self.g.tf_small).pack(side="left")

            def do():
                fn()
                self.confirm = self.picker = None
                self.refresh()
            self._button(f, tr("Reset"), do, DANGER, DANGER_EDGE).pack(side="right")
            self._button(f, tr("Cancel"), self._cancel).pack(side="right", padx=(0, px(6)))
            return
        latest = self.g.upd.latest
        if latest and not self.note:                       # a newer version is out -> link to the website
            lb = self._label(f, tr("Update available · v{v}", v=latest), C["accent"], self.link_font, cursor="hand2")
            lb.bind("<Button-1>", lambda e: self.g.open_update())
            lb.pack(side="left")
        else:
            self._label(f, self.note or f"Status Pet · v{VERSION}",
                        C["warn"] if self.note else C["label"], self.g.tf_small).pack(side="left")
        if reset:
            self._link(f, tr("Reset " + reset[0]), self._ask_reset).pack(side="right")

    def _ask_reset(self):
        self.confirm = self.tab
        self.refresh()

    def _cancel(self):
        self.confirm = None
        self.refresh()

    def _flash(self, msg):
        self.note = msg
        self.refresh()

        def clear():
            self.note = None
            if self.win.winfo_exists():
                self.refresh()
        self._later(2200, clear)

    # ---------- General ----------
    def _tab_general(self, sec):
        g, C, px = self.g, self.C, self.px
        row = tk.Frame(sec, bg=C["panel"])
        row.pack(fill="x")
        self._label(row, tr("Status size")).pack(side="left")
        g.size_lbl = self._label(row, f"{g.status_size.get()}%", C["label"], g.tf_small)
        g.size_lbl.pack(side="right")
        tk.Scale(sec, from_=g.SZ_MIN, to=g.SZ_MAX, resolution=5, orient="horizontal", showvalue=False,
                 variable=g.status_size, command=lambda v: g._on_option(), length=self.cw,
                 width=px(8), sliderlength=px(14), sliderrelief="flat", bd=0, highlightthickness=0,
                 bg=C["accent"], activebackground=C["ink"], troughcolor=C["track"]).pack(fill="x", pady=(px(4), px(6)))
        for label, var in (("Show pet", g.show_pet), ("Transparent background", g.transparent)):
            r = tk.Frame(sec, bg=C["panel"])
            r.pack(fill="x", pady=px(3))
            self._label(r, tr(label)).pack(side="left")

            def flip(v=var):
                v.set(not v.get())
                g._on_option()
                self.refresh()
            self._switch(r, var.get(), flip).pack(side="right")
        r = tk.Frame(sec, bg=C["panel"])                   # Windows keeps this one (autostart.py), not the settings file
        r.pack(fill="x", pady=px(3))
        self._label(r, tr("Start with Windows")).pack(side="left")

        def flip_start():
            if not autostart.set_on(not autostart.is_on(), g.SCRIPT):
                self._flash(tr("Couldn't change Windows startup"))
            self.refresh()
        self._switch(r, autostart.is_on(), flip_start).pack(side="right")
        r = tk.Frame(sec, bg=C["panel"])                   # language picker (not touched by "Reset")
        r.pack(fill="x", pady=px(3))
        self._label(r, tr("Language")).pack(side="left")
        self._lang_box(r).pack(side="right")
        if self.lang_open:
            self._lang_list(sec)
        self.usage_lbl =self._label(sec, tr("This app: ") + "…", C["label"], g.tf_small, anchor="w")
        self.usage_lbl.pack(fill="x", pady=(px(6), 0))
        self._show_usage()

        def reset():
            g.status_size.set(100)
            g.show_pet.set(True)
            g.transparent.set(False)
            g._on_option()
        return "general settings", reset

    def _show_usage(self):
        cpu, ram = self.usage_val
        if self.usage_lbl:
            parts = [f"CPU {cpu:.1f}%" if cpu is not None else "CPU …", f"RAM {ram:.0f} MB" if ram else "RAM …"]
            self.usage_lbl.config(text=tr("This app: ") + " · ".join(parts))

    def _tick_usage(self):
        """Every 2 s while Settings is open: the gadget's own CPU and RAM."""
        self.usage_val = self.usage.sample()
        self._show_usage()
        self._later(2000, self._tick_usage)

    # ---------- Pet ----------
    def _tab_pet(self, sec):
        g, C, px = self.g, self.C, self.px
        self._head(sec, tr("Character"))
        grids = {k: self._grid(g.pet_cells(None, char=k, bg=TILE)) for k, _ in CHARACTERS}
        th = max(len(gr) for gr in grids.values()) * g.ps + px(14)

        def make(parent, key, w, h):
            img = self._image(grids[key], g.ps)

            def draw(c, w, h):
                c.create_image(w / 2, h / 2, image=img)
                self._season_mark(c, key, w)
            return self._tile(parent, w, h, sel=g.character == key, draw=draw, cmd=lambda e, k=key: self._pick_char(k))
        self._pager(sec, "pet", seasons.order([k for k, _ in CHARACTERS]), self.cw, th, make).pack(fill="x")
        return None                                        # nothing to reset: just pick a character

    def _pick_char(self, key):
        self.g.character = key
        self.g._after_change()
        self.refresh()

    # ---------- Items ----------
    def _tab_items(self, sec):
        g, C, px = self.g, self.C, self.px
        ids = list(g.hats)
        self._head(sec, tr("Default hat"), str(len(ids)))
        cur = g.default_hat_id()                           # the green tile = the Default hat (None = "No hat")
        tallest = max(g.hats, key=lambda k: len(g.hats[k]["rows"])) if g.hats else None
        th = len(self._grid(g.pet_cells(tallest, bg=TILE))) * g.ps + px(8)   # the current pet in its tallest hat, actual size
        preview = {}

        def show(hat_id):
            cv, (w, h) = preview["cv"], preview["size"]
            cv.delete("pet")
            img = self._image(self._grid(g.pet_cells(hat_id, bg=TILE)), g.ps)
            cv.create_image(w / 2, h - px(4), image=img, anchor="s", tags="pet")

        def lead(parent, w, h):
            box = tk.Frame(parent, bg=C["panel"])
            cv = self._tile(box, w, h)
            preview.update(cv=cv, size=(w, h))
            show(cur)
            cv.pack()
            self._label(box, tr("Preview"), C["label"], self.tiny).pack(pady=(px(2), 0))
            return box

        def make(parent, key, w, h):
            img = self._hat_img(key, g.ps) if key else None

            def draw(c, w, h):
                if img:
                    c.create_image(w / 2, h / 2, image=img)
                else:
                    self._nohat(c, w / 2, h / 2, px(7))

            def enter():
                show(key)                                  # pointing at a hat previews it on your pet

            def leave():
                if preview:
                    show(cur)

            def click(e):
                g.set_default_hat(key)                     # clicking a hat makes it the Default hat
                self.refresh()
            cv = self._tile(parent, w, h, draw=draw, sel=key == cur, cmd=click, enter=enter, leave=leave)
            return cv
        self._pager(sec, "items", [None] + ids, self.cw, th, make, lead=lead, arrows=False).pack(fill="x")
        for p in g.hat_problems:
            self._label(sec, p, C["warn"], g.tf_small, anchor="w", justify="left",
                        wraplength=self.cw).pack(fill="x", pady=(px(4), 0))
        return None                                        # nothing to reset: hats are all built in

    # ---------- Effects ----------
    def _tab_effects(self, sec):
        """The Default effect (like the Items tab's Default hat) and where the effects start for each meter."""
        g, C, px = self.g, self.C, self.px
        self._head(sec, tr("Default effect"))
        gap = px(4)
        tw = (self.cw - gap * (PER_PAGE - 1)) // PER_PAGE
        th = 25 * g.ps                                     # room for the easel and the magic circle
        row = tk.Frame(sec, bg=C["panel"])
        row.pack(anchor="w")
        box = tk.Frame(row, bg=C["panel"])
        box.grid(row=0, column=0, rowspan=2, sticky="n", padx=(0, gap))
        pw = 2 * tw + gap                                  # the Preview is two tiles wide
        cv = self._tile(box, pw, th)
        cv.pack()
        self._label(box, tr("Preview"), C["label"], self.tiny).pack(pady=(px(2), 0))
        self.fx["cv"], self.fx["size"] = cv, (pw, th)
        self._fx_frame()
        cols, per = PER_PAGE - 2, (PER_PAGE - 2) * 2       # tiles right of the Preview: 3 across, 2 down
        effects = seasons.order(g.EFFECTS)                 # in-season effects first, out-of-season ones last
        pages = max(1, -(-len(effects) // per))
        page = self.pages.get("effect")
        if page is None or page >= pages:                  # first time: the page the Default effect is on
            page = self.pages["effect"] = effects.index(g.default_effect) // per
        for i in range(per):                               # keep the block the same width on a short last page
            r, c = divmod(i, cols)
            e = effects[page * per + i] if page * per + i < len(effects) else None
            pad = dict(sticky="n", padx=(0, gap if c < cols - 1 else 0), pady=(gap if r else 0, 0))
            if e is None:
                tk.Frame(row, bg=C["panel"], width=tw, height=1).grid(row=r, column=1 + c, **pad)
                continue
            img = self._effect_img(e, g.ps) if e != "none" else None

            def draw(c, w, h, img=img, e=e):
                if img:
                    c.create_image(w / 2, h / 2, image=img)
                else:
                    self._nohat(c, w / 2, h / 2, px(7))
                self._season_mark(c, e, w)
            self._tile(row, tw, th, draw=draw, sel=g.default_effect == e,
                       cmd=lambda ev, e=e: (g.set_default_effect(e), self.refresh()),
                       enter=lambda e=e: self._fx_point(e), leave=lambda e=e: self._fx_point(None, e)
                       ).grid(row=r, column=1 + c, **pad)
        if pages > 1:
            self._page_bar(row, "effect", pages).grid(row=2, column=1, columnspan=cols, sticky="ew",
                                                      pady=(px(4), 0))
        self._head(sec, tr("Effect range")).pack_configure(pady=(px(10), px(6)))
        for m in g.METERS:
            r = tk.Frame(sec, bg=C["panel"])
            r.pack(fill="x")
            self._label(r, m.upper()).pack(side="left")
            val = self._label(r, "", C["label"], g.tf_small)
            val.pack(side="right")
            self._range_slider(sec, m, val).pack(fill="x", pady=(px(4), px(6)))
        return "effect settings", g.reset_effects

    def _range_slider(self, parent, meter, val):
        """Two-handle slider for one meter's effect range (0-100, steps of 5, ends at least RANGE_GAP apart),
        with small ticks under the three step points. val: the label that shows "40–75%"."""
        g, C, px = self.g, self.C, self.px
        w, th, hw = self.cw, px(8), px(14)
        cv = tk.Canvas(parent, width=w, height=th + px(5), bg=C["panel"], highlightthickness=0, bd=0, cursor="hand2")
        x_of = lambda p: hw / 2 + (w - hw) * p / 100
        grab = [None]                                          # 0 = start handle, 1 = end handle, while dragging

        def draw():
            cv.delete("all")
            lo, hi = g.effect_range[meter]
            cv.create_rectangle(0, 0, w, th, fill=C["track"], width=0)
            cv.create_rectangle(x_of(lo), 0, x_of(hi), th, fill=mix(C["track"], C["accent"], .45), width=0)
            for p in g.effect_steps(meter):
                x = round(x_of(p))
                cv.create_rectangle(x, th + px(2), x + max(1, px(1)), th + px(5), fill=C["label"], width=0)
            for i, p in enumerate((lo, hi)):
                x = x_of(p)
                cv.create_rectangle(x - hw / 2, 0, x + hw / 2, th, width=0,
                                    fill=C["ink"] if grab[0] == i else C["accent"])
            val.config(text=f"{lo}–{hi}%")

        def pct_at(x):
            return round(max(0, min(100, (x - hw / 2) / (w - hw) * 100)) / 5) * 5

        def drag(e):
            lo, hi = g.effect_range[meter]
            p, gap = pct_at(e.x), g.RANGE_GAP
            if grab[0] == 0:
                lo = max(0, min(p, hi - gap))
            else:
                hi = min(100, max(p, lo + gap))
            if [lo, hi] != g.effect_range[meter]:
                g.set_effect_range(meter, lo, hi)
            draw()

        def press(e):
            lo, hi = g.effect_range[meter]
            p = (e.x - hw / 2) / (w - hw) * 100
            grab[0] = 0 if abs(p - lo) < abs(p - hi) or (p < lo and abs(p - lo) == abs(p - hi)) else 1
            drag(e)

        def release(e):
            grab[0] = None
            draw()
        cv.bind("<ButtonPress-1>", press)
        cv.bind("<B1-Motion>", drag)
        cv.bind("<ButtonRelease-1>", release)
        draw()
        return cv

    def _effect_img(self, effect, k):
        """Magic = wand + sparkle, Painting = palette + brush, Construction = hammer + cone, Cooking = pan + egg,
        Computer = laptop + mug, Halloween = lantern + sweet: the same small picture on tiles and app buttons."""
        cells = {}
        if effect == "magic":
            sp.stamp(cells, sp.WAND, 3, 2)
            for c, r in ((1, 0), (0, 1), (1, 1), (2, 1), (1, 2)):
                cells[(c, r)] = self.C["star"]
            cells[(8, 5)] = self.C["magic"]
        elif effect == "build":
            sp.stamp(cells, sp.HAMMER, 0, 0, sp.HAMMER_PAL)
            sp.stamp(cells, sp.CONE, 5, 3, sp.CONE_PAL)
        elif effect == "cook":
            sp.stamp(cells, sp.PAN, 0, 0, sp.PAN_PAL)
            for c, r, col in sp.EGG:
                cells[(c, r)] = col
        elif effect == "comp":
            sp.stamp(cells, sp.LAPTOP[0], 0, 2, sp.LAPTOP_PAL)
            sp.stamp(cells, sp.MUG, 8, 4, sp.MUG_PAL)
        elif effect == "trick":
            sp.stamp(cells, sph.CARRY, 0, 1, sph.CARRY_PAL)
            for c, r in sph.CARRY_FACE:                    # the lantern's lit face, still in a picture
                cells[(c, r + 1)] = sph.lantern_color(.8)
            for c in (7, 8):                               # a sweet lying beside it
                for r in (5, 6):
                    cells[(c, r)] = sph.SWEETS[0]
        else:
            sp.stamp(cells, sp.PALETTE, 0, 4, sp.PALETTE_PAL)
            sp.stamp(cells, sp.BRUSH, 4, 0)
        return self._image(self._grid(cells), k, key=("fx", effect))

    def _fx_point(self, effect, leaving=None):
        """Pointing at an effect tile plays it in the Preview; leaving the tile stops it."""
        if leaving is not None:
            if self.fx["effect"] != leaving:
                return
            effect = None
        self.fx["effect"], self.fx["t0"] = effect, time.perf_counter()
        self._fx_frame()

    def _fx_frame(self):
        """Draws one Preview frame; about 20 a second, only while an effect is pointed at."""
        if self.fx_job:
            self.win.after_cancel(self.fx_job)
            self.fx_job = None
        cv = self.fx.get("cv")
        if cv is None or not cv.winfo_exists():
            return
        effect = self.fx["effect"] if self.fx["effect"] != "none" else None
        cells, centre = self._fx_cells(effect, time.perf_counter() - self.fx["t0"] if effect else 0.0)
        (w, h), ps = self.fx["size"], self.g.ps
        ox, oy = round(w / 2 - centre * ps), h - 22 * ps  # column `centre` in the middle; row 18 = feet
        cv.delete("fx")
        for c, r, n, col in sp.runs(cells):
            x, y = ox + c * ps, oy + r * ps
            if y >= self.px(2):                            # clear of the tile's rounded top edge
                cv.create_rectangle(x, y, x + n * ps, y + ps, fill=col, outline="", tags="fx")
        if effect:
            self.fx_job = self.win.after(50, self._fx_frame)

    def _fx_cells(self, effect, t):
        """The pet with one effect, stepping 1 -> 2 -> 3 and round again. -> (cells, centre column)."""
        g, C = self.g, self.C
        step = st = 0
        if effect:
            st = t % (2.4 + (4.6 if effect in g.STATIONS else 3.2))
            step = 1 if st < 1.2 else 2 if st < 2.4 else 3
            st -= (step - 1) * 1.2                         # seconds into the current step
        magic = step if effect == "magic" else 0
        brush = step if effect == "painting" else 0
        cells = {}
        if magic >= 2:                                     # the rotating magic circle, behind the pet
            for i in range(36):
                if i % 3 != 2:
                    a = t * 1.5 + i / 36 * math.tau
                    cells[(10 + round(math.cos(a) * 14), 19 + round(math.sin(a) * 2.5))] = \
                        "#E4DBFF" if i % 6 < 2 else C["magic"]
        up = 0.0
        if brush == 3:                                     # the easel pops up, then the picture fills in
            up = min(1.0, st / .4)
            q = round(min(1.0, max(0.0, (st - .4) / 8)) * 40) / 40
            sp.stamp(cells, sp.easel_rows(q), 17, 4, sp.EASEL_PAL, math.ceil(15 * (1 - up)))
        dab = -1
        if brush:
            dab = int(t * 5) % 2 if brush == 3 and up >= 1 else 1 if brush == 2 and st % 1.4 > 1.15 else 0
        trick = step if effect == "trick" else 0
        if trick:
            for i in range(min(sph.TRAIL_MAX, 2 + step)):  # sweets already lying on the ground
                for c in (2 + i * 3, 3 + i * 3):
                    for r in (17, 18):
                        cells[(c, r)] = sph.SWEETS[i % len(sph.SWEETS)]
            if trick >= 3:
                back, front = sph.bats(t)
                for x, y, frame in back + front:
                    sp.stamp(cells, sph.BAT[frame], x, y, sph.BAT_PAL)
        work = None
        if effect in g.WORK_EFFECTS:                       # Construction / Cooking / Computer
            if step == 3:                                  # the work spot pops up, then the wall / papers grow
                up = min(1.0, st / .4)
                prog = min(1.0, max(0.0, (st - .4) / 4))
                self._fx_spot(cells, effect, False, t, prog, up)
            work = (effect, step if step < 3 or up >= 1 else 2, sp.work_frame(effect, t))
        g.pose_cells(cells, "neutral", hat=g.default_hat_id(),
                     wob=int(t * 1.5) % 2 if magic else -1, dab=dab, palette=brush >= 2, work=work,
                     lit=spp.glow_level(t, busy=bool(step)), bg=TILE, trick=trick,
                     carry_dy=round(math.sin(t * 2)) if trick and g.carries() else 0,
                     carry_lit=sph.lantern_lit(t) if trick else None)
        if work:
            if step == 3:
                self._fx_spot(cells, effect, True, t, prog, up)
            for c, r, col in sp.work_puffs(effect, work[1], t, g.character == "cat", step == 3 and up >= 1,
                                       0 if step == 3 and up >= 1 else g.PET_DY.get(g.character, 0)):
                cells[(c, r)] = col
        if magic == 3:                                     # sparkles rising and fading
            for i in range(7):
                k = (i * .618 + t * .6) % 1
                c, r = 2 + (i * 7) % 17, 16 - round(k * 18)
                col = mix(C["star"] if k < .5 else C["magic"], TILE, k)
                for dc, dr in ((0, -1), (0, 0), (0, 1), (-1, 0), (1, 0)):
                    cells[(c + dc, r + dr)] = col
        return cells, {"painting": 14.5, "build": 12, "cook": 12, "comp": 13}.get(effect, 10)

    @staticmethod
    def _fx_spot(cells, effect, front, t, prog, up):
        """The Preview's step-3 work spot, rising out of the ground as up goes 0 -> 1."""
        spot = {}
        sp.work_spot(spot, effect, front, sp.work_state(effect, front, t, prog))
        top = round(19 - 16 * up)
        cells.update((k, v) for k, v in spot.items() if k[1] >= top)

    # ---------- Apps ----------
    def _tab_apps(self, sec):
        g, C, px = self.g, self.C, self.px
        apps = g.all_apps()
        closed = [a for a in apps if a[0] in self.shown]
        rows = apps if self.more else closed
        self._head(sec, tr("Tracked apps"), tr("{n} on", n=len(g.tracked)))
        lst = tk.Frame(sec, bg=C["panel"])
        lst.pack(fill="x")
        # (the Default hat is chosen in the Items tab; no Default row here)
        for app_id, name, color in rows:
            on = app_id in g.tracked
            r = tk.Frame(lst, bg=C["panel"])
            r.pack(fill="x", pady=(px(3), 0))

            def toggle(i=app_id):
                g.set_tracked(i, i not in g.tracked)
                self.refresh()
            self._check(r, on, toggle).pack(side="left")
            dot = self._dot(r, color)                      # click the dot: pick the app's color
            dot.configure(cursor="hand2")
            dot.bind("<Button-1>", lambda e, i=app_id: self._toggle_picker("color:" + i))
            dot.pack(side="left", padx=(px(9), px(9)))
            nm = self._label(r, name, C["ink"] if on else C["label"], cursor="hand2")
            nm.pack(side="left")
            nm.bind("<Button-1>", lambda e, t=toggle: t())
            self._hat_button(r, app_id, g.app_hat_id(app_id)).pack(side="right")
            # × on every app: it leaves the list ("+ Add running app" brings it back while it runs)
            x = self._label(r, "×", C["label"], g.tf_ui, cursor="hand2", padx=px(4))
            x.pack(side="right", padx=(0, px(2)))
            x.bind("<Button-1>", lambda e, i=app_id, n=name: self._drop_app(i, n))
            x.bind("<Enter>", lambda e, w=x: w.config(fg=C["crit"]))
            x.bind("<Leave>", lambda e, w=x: w.config(fg=C["label"]))
            if self.picker == app_id:
                self._picker(lst, app_id, name, g.app_hat_id(app_id))
            elif self.picker == "color:" + app_id:
                self._color_picker(lst, app_id, name, color)
        more_n = len(apps) - len(closed)
        if self.more or more_n:
            self._text_row(sec, tr("− Fewer apps" if self.more else "+ More apps"), "" if self.more else str(more_n),
                           self._toggle_more)
        if apps:                                            # "Clear app list": empties the list, after a confirm
            r = tk.Frame(sec, bg=C["panel"])
            r.pack(fill="x", pady=(px(6), 0))
            if self.confirm_clear:
                self._label(r, tr("Clear app list?"), font=g.tf_small).pack(side="left")
                self._button(r, tr("Clear"), self._clear_apps, DANGER, DANGER_EDGE).pack(side="right")
                self._button(r, tr("Cancel"), self._cancel_clear).pack(side="right", padx=(0, px(6)))
            else:
                self._link(r, tr("Clear app list"), self._ask_clear).pack(side="left")
        add = tk.Label(sec, text=tr("+ Add running app…"), bg=HOVER, fg=C["ink"], font=g.tf_small, anchor="w",
                       padx=px(10), pady=px(5), cursor="hand2", highlightthickness=1, highlightbackground=C["edge"])
        add.pack(fill="x", pady=(px(8), px(6)))
        add.bind("<Button-1>", lambda e: g._add_app_menu(add))
        add.bind("<Enter>", lambda e: add.config(bg="#332E42"))
        add.bind("<Leave>", lambda e: add.config(bg=HOVER))
        self._label(sec, tr("Checked apps appear in the gadget only while they run."), C["label"], g.tf_small,
                    anchor="w", justify="left", wraplength=self.cw).pack(fill="x")

        return "hats & effects", g.reset_all_hats          # every app back to following Default

    def _text_row(self, parent, left, right, cmd):
        """A clickable text line in the app list's style ("+ More apps  5")."""
        m = tk.Frame(parent, bg=self.C["panel"], cursor="hand2")
        m.pack(fill="x", pady=(self.px(4), 0))
        a = self._label(m, left, font=self.g.tf_small, cursor="hand2")
        a.pack(side="left")
        b = self._label(m, right, self.C["label"], self.g.tf_small, cursor="hand2")
        b.pack(side="right")
        for w in (m, a, b):
            w.bind("<Button-1>", lambda e: cmd())

    def _drop_app(self, app_id, name):
        """×: the app leaves the list."""
        self.g.remove_app(app_id)
        self.shown.discard(app_id)
        if self.picker == app_id:
            self.picker = None
        self._flash(tr("Removed from the list: {name}", name=name))

    def _ask_clear(self):
        self.confirm_clear = True
        self.refresh()

    def _cancel_clear(self):
        self.confirm_clear = False
        self.refresh()

    def _clear_apps(self):
        self.g.clear_apps()
        self.g._sample_apps()
        self.g.base_key = None
        self.confirm_clear = self.more = False
        self.shown, self.picker = set(), None
        self._flash(tr("App list cleared"))

    def _toggle_more(self):
        self.more = not self.more
        self.shown = set(self.g.tracked)
        self.picker = None
        self.refresh()

    def _hat_button(self, parent, key, hat_id):
        g, C, px = self.g, self.C, self.px
        u = max(1, round(g.S))
        img = self._hat_img(hat_id, u) if hat_id else None
        iw = img.width() if img else px(10)
        eff = g.app_effect(key)                            # the app's effect, shown after its hat
        eimg = self._effect_img(eff, u) if eff != "none" else None
        ew = eimg.width() + px(4) if eimg else 0
        w, h = iw + ew + px(22), px(18)
        opened = self.picker == key
        cv = tk.Canvas(parent, width=w, height=h, bg=C["panel"], highlightthickness=0, bd=0, cursor="hand2")

        def paint(hover=False):
            cv.delete("bg")
            if hover or opened:
                rrect(cv, 0, 0, w - 1, h - 1, px(5), fill=HOVER, outline="", tags="bg")
                cv.tag_lower("bg")
        paint()
        if img:
            cv.create_image(px(6) + iw / 2, h / 2, image=img)
        else:
            self._nohat(cv, px(6) + iw / 2, h / 2, px(5))
        if eimg:
            cv.create_image(px(6) + iw + px(4) + eimg.width() / 2, h / 2, image=eimg)
        cv.create_text(w - px(8), h / 2, text="▾", fill=C["label"], font=self.tiny)
        cv.bind("<Enter>", lambda e: paint(True))
        cv.bind("<Leave>", lambda e: paint(False))
        cv.bind("<Button-1>", lambda e: self._toggle_picker(key))
        return cv

    def _toggle_picker(self, key):
        self.picker = None if self.picker == key else key
        self.pages["pick"] = 0
        self.refresh()

    def _picker(self, parent, key, name, cur):
        """The list under an app row: "Hat | Effect" on top, then one row of tiles; ↺ goes back to following Default."""
        g, C, px = self.g, self.C, self.px
        box = tk.Frame(parent, bg=PICK_BG, highlightthickness=1, highlightbackground=C["edge"],
                       padx=px(4), pady=px(4))
        box.pack(fill="x", pady=(px(3), px(4)), padx=(px(6), 0))
        head = tk.Frame(box, bg=PICK_BG)
        head.pack(fill="x", pady=(0, px(4)))
        app = key != "__default"
        fx = app and self.pick_mode == "effect"            # the Effect side of "Hat | Effect"
        if app:
            self._segment(head, (("hat", tr("Hat")), ("effect", tr("Effect"))), self.pick_mode, self._set_pick_mode)
        else:
            self._label(head, tr("Hat for {name}", name=name), C["label"], g.tf_small, bg=PICK_BG).pack(side="left", padx=(px(2), 0))
        if app:
            same = key not in (g.app_effects if fx else g.app_hats)   # no pick of its own: following Default
            s = px(20)
            rb = tk.Canvas(head, width=s, height=s, bg=PICK_BG, highlightthickness=0, bd=0,
                           cursor="" if same else "hand2")
            rrect(rb, 0, 0, s - 1, s - 1, px(6), fill=HOVER, outline=C["edge"])
            rb.create_text(s / 2, s / 2, text="↺", fill=BORDER if same else C["ink"], font=g.tf_small)
            if not same:
                rb.bind("<Button-1>", lambda e: ((g.reset_app_effect if fx else g.reset_app_hat)(key), self.refresh()))
            rb.pack(side="right")
        follow = app and (g.follows_default_effect(key) if fx else g.follows_default(key))
        if app:                                             # "[switch] Same as Default": one unit, on the tiles' left edge
            row = tk.Frame(box, bg=PICK_BG)
            row.pack(fill="x", pady=(0, px(4)))
            flip = lambda: (self._toggle_follow_effect if fx else self._toggle_follow)(key, follow)
            self._switch(row, follow, flip, bg=PICK_BG).pack(side="left")
            lb = self._label(row, tr("Same as Default"), font=g.tf_small, bg=PICK_BG, cursor="hand2")
            lb.pack(side="left", padx=(px(6), 0))
            lb.bind("<Button-1>", lambda e: flip())      # the words toggle it too
        keys = seasons.order(g.EFFECTS) if fx else [None] + list(g.hats)
        if fx:
            cur = g.app_effect(key)
        maxh = max([len(h["rows"]) for h in g.hats.values()] + [8])   # same height on both sides
        th = maxh * g.ps + px(8)
        width = self.cw - px(6) - 2 * px(4) - 2

        def make(parent2, item, w, h):                     # item: a hat id / None, or an effect
            if item is None or item == "none":
                pic = lambda c, w, h: self._nohat(c, w / 2, h / 2, px(7))
            else:
                img = self._effect_img(item, g.ps) if fx else self._hat_img(item, g.ps)
                pic = lambda c, w, h: c.create_image(w / 2, h / 2, image=img)

            def draw(c, w, h):
                pic(c, w, h)
                if fx:
                    self._season_mark(c, item, w)
                if follow:                                  # following Default: the tiles are dimmed
                    rrect(c, 0, 0, w - 1, h - 1, px(7), fill=PICK_BG, outline="", stipple="gray50")
            return self._tile(parent2, w, h, draw=draw, sel=not follow and item == cur,
                              cmd=lambda e: self._set_effect(key, item) if fx else self._set_hat(key, item))
        self._pager(box, "pick", keys, width, th, make).pack(fill="x")

    def _color_picker(self, parent, app_id, name, cur):
        """Under an app row: 10 color swatches; ↺ puts the plain grey back."""
        g, C, px = self.g, self.C, self.px
        box = tk.Frame(parent, bg=PICK_BG, highlightthickness=1, highlightbackground=C["edge"],
                       padx=px(4), pady=px(4))
        box.pack(fill="x", pady=(px(3), px(4)), padx=(px(6), 0))
        head = tk.Frame(box, bg=PICK_BG)
        head.pack(fill="x", pady=(0, px(4)))
        self._label(head, tr("Color for {name}", name=name), C["label"], g.tf_small, bg=PICK_BG).pack(side="left", padx=(px(2), 0))
        same = app_id not in g.app_colors
        s = px(20)
        rb = tk.Canvas(head, width=s, height=s, bg=PICK_BG, highlightthickness=0, bd=0, cursor="" if same else "hand2")
        rrect(rb, 0, 0, s - 1, s - 1, px(6), fill=HOVER, outline=C["edge"])
        rb.create_text(s / 2, s / 2, text="↺", fill=BORDER if same else C["ink"], font=g.tf_small)
        if not same:
            rb.bind("<Button-1>", lambda e: (g.reset_app_color(app_id), self.refresh()))
        rb.pack(side="right")
        row = tk.Frame(box, bg=PICK_BG)
        row.pack(anchor="w")
        for col in SWATCHES:
            sel = col.upper() == cur.upper()

            def draw(sf, col=col, sel=sel):
                if sel:                                     # a light ring around the current color
                    sf.ellipse(9, 9, 8.5, 8.5, gfx.argb(C["ink"]))
                    sf.ellipse(9, 9, 7, 7, gfx.argb(PICK_BG))
                sf.ellipse(9, 9, 5.5, 5.5, gfx.argb(col))
            self._aa(row, px(18), px(18), draw, lambda c=col: (g.set_app_color(app_id, c), self.refresh()),
                     bg=PICK_BG, key=("swatch", col, sel)).pack(side="left", padx=(0, px(3)))

    def _toggle_follow(self, key, following):
        g = self.g
        if not following:
            g.set_app_hat(key, hatlib.FOLLOW)
        else:
            g.set_app_hat(key, g.default_hat_id())        # off: keep the same hat, but as the app's own pick
        self.refresh()

    def _toggle_follow_effect(self, key, following):
        g = self.g
        if not following:
            g.set_app_effect(key, hatlib.FOLLOW)
        else:
            g.set_app_effect(key, g.default_effect)       # off: keep the same effect, but as the app's own pick
        self.refresh()

    def _set_effect(self, key, effect):
        self.g.set_app_effect(key, effect)
        self.refresh()

    def _set_pick_mode(self, mode):
        self.pick_mode = mode
        self.pages["pick"] = 0
        self.refresh()

    def _segment(self, parent, options, cur, cmd, bg=PICK_BG, side="left", fonts=None):
        """A small two-way switch ("Hat | Effect"); the current side is lit."""
        C, px = self.C, self.px
        seg = tk.Frame(parent, bg=bg, highlightthickness=1, highlightbackground=C["edge"])
        seg.pack(side=side, padx=(px(2), 0) if side == "left" else 0)
        for k, text in options:
            on = k == cur
            lb = tk.Label(seg, text=text, bg=C["sel"] if on else bg, fg=C["ink"] if on else C["label"],
                          font=(fonts or {}).get(k, self.g.tf_small), padx=px(7), pady=px(1), bd=0,
                          cursor="" if on else "hand2")
            lb.pack(side="left")
            if not on:
                lb.bind("<Button-1>", lambda e, k=k: cmd(k))
                lb.bind("<Enter>", lambda e, w=lb: w.config(fg=C["ink"]))
                lb.bind("<Leave>", lambda e, w=lb: w.config(fg=C["label"]))

    def _lang_box(self, parent):
        """The closed language box: current language's own name in its own font, e.g. "한국어 ▾"."""
        C, px = self.C, self.px
        code = i18n.lang
        box = tk.Frame(parent, bg=PICK_BG, highlightthickness=1,
                       highlightbackground=C["accent"] if self.lang_open else C["edge"], cursor="hand2")
        lb = tk.Label(box, text=dict(i18n.LANGS)[code] + " ▾", bg=PICK_BG, fg=C["ink"], font=self.lang_fonts[code],
                     padx=px(7), pady=px(1))
        lb.pack()
        for w in (box, lb):
            w.bind("<Button-1>", lambda e: self._toggle_lang())
        return box

    def _lang_list(self, sec):
        """The 10-language list under the language row; the current one is marked, click picks it at once."""
        C, px = self.C, self.px
        box = tk.Frame(sec, bg=PICK_BG, highlightthickness=1, highlightbackground=C["edge"])
        box.pack(fill="x", pady=(0, px(4)))
        for code, name in i18n.LANGS:
            on = code == i18n.lang
            row_bg = SOFT if on else PICK_BG
            row = tk.Frame(box, bg=row_bg, cursor="" if on else "hand2")
            row.pack(fill="x")
            lb = tk.Label(row, text=name, bg=row_bg, fg=C["accent"] if on else C["ink"],
                         font=self.lang_fonts[code], anchor="w", padx=px(8), pady=px(3))
            lb.pack(fill="x")
            if not on:
                def enter(_e, r=row, l=lb):
                    r.config(bg=HOVER)
                    l.config(bg=HOVER)

                def leave(_e, r=row, l=lb):
                    r.config(bg=PICK_BG)
                    l.config(bg=PICK_BG)
                for w in (row, lb):
                    w.bind("<Button-1>", lambda e, c=code: self._pick_lang(c))
                    w.bind("<Enter>", enter)
                    w.bind("<Leave>", leave)
        return box

    def _toggle_lang(self):
        self.lang_open = not self.lang_open
        self.refresh()

    def _pick_lang(self, code):
        self.lang_open = False
        self.g.set_language(code)          # rebuilds this window itself (Gadget.set_language -> SettingsUI.relang)

    def _set_hat(self, key, hat_id):
        if key == "__default":
            self.g.set_default_hat(hat_id)
        else:
            self.g.set_app_hat(key, hat_id)
        self.refresh()
