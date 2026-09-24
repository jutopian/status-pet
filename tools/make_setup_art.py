"""Pictures for the installer.

Writes 24-bit BMPs (what Inno Setup reads) into build/art, each at 100% and 200% (name@2x.bmp):
- side_welcome / side_finish (164 x 314): night-sky yard; wizard-hat pet with wand in a magic circle / happy + hearts
- badge / badge_focused (55 x 55): the whole pet with its hat, top-right of the middle pages
Pure Python (no extra packages). Magenta #FF00FF = see-through: the installer swaps it for the page color.
Run: python tools/make_setup_art.py (tools/build_installer.py runs it).
"""
import math
import os
import struct
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
import sprites as sp  # noqa: E402

OUT = os.path.join(ROOT, "build", "art")
KEY = (255, 0, 255)
PAGE = (255, 255, 255)             # the Setup pages' background, around the badge
MAGIC, MAGIC_LIGHT, STAR, HEART = "#B9A8FF", "#E4DBFF", "#FFD86B", "#F27C8E"

# 5 x 7 pixel letters for the side picture's name line (only the ones used)
FONT = {
    "S": [".####", "#....", "#....", ".###.", "....#", "....#", "####."],
    "T": ["#####", "..#..", "..#..", "..#..", "..#..", "..#..", "..#.."],
    "A": [".###.", "#...#", "#...#", "#####", "#...#", "#...#", "#...#"],
    "U": ["#...#", "#...#", "#...#", "#...#", "#...#", "#...#", ".###."],
    "P": ["####.", "#...#", "#...#", "####.", "#....", "#....", "#...."],
    "E": ["#####", "#....", "#....", "####.", "#....", "#....", "#####"],
    "V": ["#...#", "#...#", "#...#", "#...#", "#...#", ".#.#.", "..#.."],
    "W": ["#...#", "#...#", "#...#", "#.#.#", "#.#.#", "##.##", "#...#"],
    "L": ["#....", "#....", "#....", "#....", "#....", "#....", "#####"],
    "C": [".###.", "#...#", "#....", "#....", "#....", "#...#", ".###."],
    "O": [".###.", "#...#", "#...#", "#...#", "#...#", "#...#", ".###."],
    "M": ["#...#", "##.##", "#.#.#", "#.#.#", "#...#", "#...#", "#...#"],
    "H": ["#...#", "#...#", "#...#", "#####", "#...#", "#...#", "#...#"],
    "0": [".###.", "#...#", "#..##", "#.#.#", "##..#", "#...#", ".###."],
    "9": [".###.", "#...#", "#...#", ".####", "....#", "...#.", ".##.."],
    ".": [".....", ".....", ".....", ".....", ".....", ".##..", ".##.."],
    "!": ["..#..", "..#..", "..#..", "..#..", "..#..", ".....", "..#.."],
    " ": ["....."] * 7,
}


def rgb(c):
    return c if isinstance(c, tuple) else (int(c[1:3], 16), int(c[3:5], 16), int(c[5:7], 16))


def mix(a, b, k):
    return tuple(round(x + (y - x) * k) for x, y in zip(rgb(a), rgb(b)))


class Pic:
    def __init__(self, w, h, bg=KEY):
        self.w, self.h = w, h
        self.px = [[rgb(bg)] * w for _ in range(h)]

    def rect(self, x, y, w, h, col, alpha=1.0):
        col = rgb(col)
        for yy in range(max(0, round(y)), min(self.h, round(y + h))):
            row = self.px[yy]
            for xx in range(max(0, round(x)), min(self.w, round(x + w))):
                row[xx] = col if alpha >= 1 else mix(row[xx], col, alpha)

    def cells(self, cells, ox, oy, k):
        for (c, r), col in cells.items():
            self.rect(ox + c * k, oy + r * k, k, k, col)

    def text(self, s, cx, y, k, col):
        w = len(s) * 6 * k - k
        x = round(cx - w / 2)
        for ch in s:
            for r, row in enumerate(FONT[ch]):
                for c, bit in enumerate(row):
                    if bit == "#":
                        self.rect(x + c * k, y + r * k, k, k, col)
            x += 6 * k

    def scaled(self, k):
        out = Pic(self.w * k, self.h * k)
        out.px = [[p for p in row for _ in range(k)] for row in self.px for _ in range(k)]
        return out

    def save(self, name):
        pad = (4 - self.w * 3 % 4) % 4
        data = b"".join(b"".join(bytes((b, g, r)) for r, g, b in row) + b"\0" * pad for row in reversed(self.px))
        head = struct.pack("<2sIHHI", b"BM", 54 + len(data), 0, 0, 54)
        info = struct.pack("<IiiHHIIiiII", 40, self.w, self.h, 1, 24, 0, len(data), 2835, 2835, 0, 0)
        with open(os.path.join(OUT, name + ".bmp"), "wb") as f:
            f.write(head + info + data)


def pet(face, hat=True, wand=False):
    """The slime on a 12 x 17 grid (hat rows 0-8, body rows 7-15, feet row 16), like the gadget."""
    cells = {}
    sp.stamp(cells, sp.BODY, 0, 7)
    sp.stamp(cells, [sp.FEET[0]], 0, 16)
    for f in sp.FACES[face]:
        cells[(f[0], 7 + f[1])] = sp.PAL[f[2] if len(f) > 2 else "e"]
    if hat:
        sp.stamp(cells, sp.HAT, 0, 0)
    if wand:
        sp.stamp(cells, sp.WAND, 11, 8)
    return cells


def plus(p, x, y, s, col):
    p.rect(x, y, s, s, col)
    p.rect(x - s, y, 3 * s, s, col)
    p.rect(x, y - s, s, 3 * s, col)


def side(happy):
    p = Pic(164, 314)
    top, mid, low = rgb("#1E1B3A"), rgb("#3B3166"), rgb("#4A3E7A")
    for y in range(314):
        t = y / 313
        p.rect(0, y, 164, 1, mix(top, mid, t / .7) if t < .7 else mix(mid, low, (t - .7) / .3))
    for i, (x, y) in enumerate(((18, 22), (52, 40), (120, 18), (140, 60), (30, 86), (96, 70), (146, 120), (12, 150),
                                (70, 112), (128, 160))):
        col = "#CFC4FF" if i % 3 else STAR
        p.rect(x, y, 3, 3, col)
        if i % 3 == 0:
            p.rect(x - 3, y, 9, 3, col)
            p.rect(x, y - 3, 3, 9, col)
    for y in range(30, 56):                                   # crescent moon: a pixel disc minus a smaller one
        for x in range(114, 142):
            if math.hypot(x - 127, y - 43) <= 10 and math.hypot(x - 132, y - 39) > 9:
                p.rect(x, y, 1, 1, "#FFF6CF")
    p.rect(0, 262, 164, 52, "#3F8A57")
    p.rect(0, 262, 164, 6, "#55AA6E")
    for x in range(4, 164, 14):
        p.rect(x, 256, 3, 6, "#6CC486")
        p.rect(x + 5, 258, 3, 4, "#6CC486")
    p.rect(44, 262, 72, 6, (0, 0, 0), .22)
    if not happy:                                             # the gadget's purple magic circle under the pet
        for y in range(236, 274):                             # stops above the name, so it stays easy to read
            for x in range(8, 136):
                d = math.hypot(x - 72, y - 264) / 62
                if d < 1:
                    p.rect(x, y, 1, 1, MAGIC, .4 * (1 - d))
        for i in range(36):
            if i % 3 != 2:
                a = i / 36 * math.tau
                p.rect(round(72 + math.cos(a) * 54) - 2, round(265 + math.sin(a) * 10) - 2, 4, 4,
                       MAGIC_LIGHT if i % 6 < 2 else MAGIC)
    p.cells(pet("happy" if happy else "neutral", wand=not happy), 36, 160, 6)
    if happy:
        heart = {}
        sp.stamp(heart, sp.HEART, 0, 0, {"r": HEART})
        p.cells(heart, 112, 132, 5)
        p.cells(heart, 26, 146, 4)
    else:
        for x, y in ((122, 150), (134, 136), (110, 130)):
            plus(p, x, y, 4, STAR)
    p.text("STATUS PET", 82, 276, 2, "#FFFFFF")
    if happy:
        p.text("WELCOME HOME!", 82, 298, 1, "#DDE9E0")
    return p


def badge(face):
    p = Pic(55, 55, PAGE)
    r = 10
    for y in range(55):
        for x in range(55):
            cx, cy = min(max(x, r), 54 - r), min(max(y, r), 54 - r)
            if math.hypot(x - cx, y - cy) <= r:
                p.px[y][x] = rgb("#2B2545")
    p.cells(pet(face), 16, 10, 2)
    return p


def main():
    os.makedirs(OUT, exist_ok=True)
    for name, pic in (("side_welcome", side(False)), ("side_finish", side(True)), ("badge", badge("neutral")),
                      ("badge_focused", badge("focused"))):
        pic.save(name)
        pic.scaled(2).save(name + "@2x")
    print("wrote", OUT)


if __name__ == "__main__":
    main()
