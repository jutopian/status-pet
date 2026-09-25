"""Pixel art for the jack-o'-lantern pet.

Same format as sprites.py: each sprite is a list of rows; "." is empty, every other letter is a color from PAL.
One sprite pixel is drawn as a small square block, like the slime.

How it is wired in:
- Grid: the body is 12 columns wide, the same as the slime and the cat, so every hat and prop fits. It is 9 rows
  tall and stands straight on the ground (no feet), so in the program's composite grid its top row is
  sprites.PY + TOP and its bottom row is the slime's feet row (sprites.PY + 9).
- The stem stands 1 pixel wide in the middle, on the 3 rows above the body, with a vine leaf trailing behind
  (the art faces right, so the leaf is on the left; mirroring the whole pose puts it behind again).
- Hats: on this pet a hat is ALWAYS drawn over the stem, whether or not its file name ends
  in "_front". So the caller stamps the stem first and the hat after it.
- The carved holes glow like a candle: `glow_level()` gives how bright they are right now (0 = out, 1 = brightest)
  and `hole_color()` turns that into the color of a lit hole. Three waves that never line up plus the odd
  sputter; the dimmest lit color is still brighter than the pumpkin itself. Asleep the holes are dark.
- Faces: resting / hopping (happy) / working (focused) / surprised / asleep, plus a glance (the eyes look your
  way) so it answers the program's "looks at you now and then" like the other pets.
- Moving: it does not walk, it hops - about 0.4 s through the air in a low arc, then a rest on the ground. There
  is no landing squash (it pushed the face out of place). The hop itself lives in the program (Gadget._move).
"""
import math

PAL = {
    "O": "#7A3B0C", "A": "#F08A22", "a": "#D9701A", "d": "#B4560F", "h": "#FFB35C",   # outline, skin, ribs, shade, shine
    "s": "#6B4226", "v": "#5EA83C",                                                   # stem, vine leaf
}

BODY = [
    "...OOOOOO...",
    ".OOhAAAAaOO.",
    "OAAaAAAAaAAO",
    "OAAaAAAAaAAO",
    "OAAaAAAAaAAO",
    "OAAaAAAAaAAO",
    "OdAaAAAAaAdO",
    ".OddddddddO.",
    "..OOOOOOOO..",
]
STEM = [                                  # 3 rows above the body; the leaf trails behind while it faces right
    ".....s......",
    "..v..s......",
    ".vv.sss.....",
]

TOP = 1          # body top row = sprites.PY + TOP (its bottom row is then the slime's feet row)
STEM_H = len(STEM)

# Carved holes as (col, row) on the 12-wide body. "lit" holes glow, "dark" holes stay unlit.
_EYES = [(3, 2), (2, 3), (3, 3), (4, 3), (8, 2), (7, 3), (8, 3), (9, 3)]
_MOUTH = [(3, 5), (4, 5), (5, 5), (6, 5), (7, 5), (8, 5), (3, 6), (5, 6), (6, 6), (8, 6)]
FACES = {
    "neutral":   {"lit": _EYES + _MOUTH},
    "glance":    {"lit": [(4, 2), (3, 3), (4, 3), (5, 3), (7, 2), (6, 3), (7, 3), (8, 3)] + _MOUTH},
    "happy":     {"lit": _EYES + _MOUTH + [(4, 7), (5, 7), (6, 7), (7, 7)]},
    "focused":   {"lit": [(2, 3), (3, 3), (4, 3), (7, 3), (8, 3), (9, 3), (5, 5), (6, 5), (4, 6), (7, 6)]},
    "surprised": {"lit": [(2, 2), (3, 2), (2, 3), (3, 3), (8, 2), (9, 2), (8, 3), (9, 3), (5, 5), (6, 5), (5, 6),
                          (6, 6)]},
    "sleep":     {"lit": [], "dark": [(2, 3), (3, 3), (4, 3), (7, 3), (8, 3), (9, 3), (5, 6), (6, 6)]},
}
# the program's other faces map onto these (it has more moods than a carved pumpkin can show)
ALIAS = {"blink": "neutral", "tired": "neutral"}

HOLE = "#1A0A03"                                  # an unlit hole
GLOW_LOW, GLOW_ON, GLOW_HOT = "#FFA23A", "#FFD36B", "#FFF3C4"     # dimmest lit -> warm -> almost white
HALO = "#FF8C28"                                  # the soft light spilling out of the holes


def _mix(a, b, t):
    p = lambda c: (int(c[1:3], 16), int(c[3:5], 16), int(c[5:7], 16))
    x, y = p(a), p(b)
    return "#" + "".join(f"{round(x[i] + (y[i] - x[i]) * t):02x}" for i in range(3))


def hole_color(lit):
    """The color of a lit hole. lit: 0 = out (a dark hole), 1 = brightest."""
    if lit <= 0:
        return HOLE
    if lit < .5:
        return _mix(GLOW_LOW, GLOW_ON, lit / .5)
    return _mix(GLOW_ON, GLOW_HOT, (lit - .5) / .5)


def glow_level(t, busy=False, moving=False, sleeping=False):
    """Candle flicker -> 0..1. Three waves that never line up plus the odd sputter; brighter and quicker while
    it works or hops. It only dips, it never goes out. Rounded to 20 steps so cached drawings can be reused."""
    if sleeping:
        return 0.0
    base = .86 if busy else .68 if moving else .38
    speed = 7 if busy else 3.2 if moving else 1.6
    amp = .16 if busy else .14 if moving else .13
    wave = .5 * math.sin(t * speed) + .3 * math.sin(t * speed * 2.37 + 1.1) + .2 * math.sin(t * speed * 5.13 + 2.6)
    tick = int(t * (9 if busy else 5))
    noise = math.fabs(math.sin(tick * 127.1) * 43758.5453) % 1      # the same number all through one tick
    sputter = -(.10 + noise * .45) if noise < .14 else .12 if noise > .93 else 0.0
    return round(min(1.0, max(.22, base + amp * wave + sputter)) * 20) / 20


def hop(phase, cycle, air, high):
    """One hop: how far through the air it is (0..1, or None while resting on the ground) and how high it is
    lifted, in sprite pixels. A real arc - up fast, hangs, comes down."""
    part = air / cycle
    if phase >= part:
        return None, 0.0
    u = phase / part
    return u, 4 * u * (1 - u) * high


def lit_cells(face):
    """The carved holes that glow, as (col, row) on the body."""
    return FACES.get(ALIAS.get(face, face), FACES["neutral"]).get("lit", ())


def build(cells, x0, y0, face="neutral", lit=.5, hat=None):
    """Stamps the pumpkin into cells {(col, row): color}: body top-left at (x0, y0), then the stem, then the hat
    (always over the stem), then the carved holes. `hat` is called as hat(cells, x0, y0).

    lit = None leaves the glowing holes out, so the rest can be cached while the candle flickers; the gadget
    then draws them itself every frame (see lit_cells)."""
    for r, row in enumerate(BODY):
        for c, ch in enumerate(row):
            if ch != ".":
                cells[(x0 + c, y0 + r)] = PAL[ch]
    for r, row in enumerate(STEM):
        for c, ch in enumerate(row):
            if ch != ".":
                cells[(x0 + c, y0 - STEM_H + r)] = PAL[ch]
    if hat:
        hat(cells, x0, y0)
    f = FACES.get(ALIAS.get(face, face), FACES["neutral"])
    for c, r in f.get("dark", ()):
        cells[(x0 + c, y0 + r)] = HOLE
    if lit is not None:
        col = hole_color(lit)
        for c, r in f.get("lit", ()):
            cells[(x0 + c, y0 + r)] = col
    return cells
