"""Pixel art for Status Pet.

Each sprite is a list of rows; "." is empty, every other letter is a color from its palette.
One sprite pixel is drawn as a small square block (2 x 2 logical pixels).
"""
import math

PAL = {
    "o": "#2F6B45", "g": "#6CC486", "l": "#A3E4B6", "d": "#55AA6E", "f": "#3F8A57",   # body
    "e": "#1E1B26", "w": "#FFFFFF", "c": "#F59BAA", "t": "#F07F8E",                    # face
    "K": "#3B2F7A", "p": "#9585F0", "P": "#B9ADFF", "q": "#6F5FD6", "b": "#5E4FC0", "y": "#FFD86B",   # wizard hat
    "B": "#18214A", "n": "#3E55A8", "N": "#5C74CC", "v": "#25336C",                    # beret
    "h": "#7A5A40", "Y": "#FFF6CF", "H": "#D9B38C", "s": "#AEB4C2", "u": "#31A8FF",    # wand, brush
}

BODY = [
    "...oooooo...",
    ".oollggggoo.",
    "olgggggggggo",
    "oggggggggggo",
    "oggggggggggo",
    "oggggggggggo",
    "odggggggggdo",
    ".oddddddddo.",
    "..ffooooff..",
]
FEET = ["..ff....ff..", "...ff..ff..."]        # standing / mid-step
HAT = [
    ".......KK..", "......KPK..", ".....KPyK..", "....KPyyyK.", "....KPpypqK", "...KPppppqK", "...KbbbbbbK",
    "KP" + "p" * 7 + "qK", "." + "K" * 9 + ".",
]
BERET = ["........B...", "....BBBBBB..", "..BNNnnnnnB.", ".B" + "n" * 8 + "vB", ".B" + "v" * 8 + "B.", "..BBBBBBBB.."]
WAND = ["...y.", "..yYy", "...y.", "..h..", ".h...", "h...."]
BRUSH = ["...u.", "..uu.", "..s..", ".H...", "H...."]
PALETTE = [".AAAA..", "AmHyHA.", "AHuHgHA", ".AAAAA."]          # Painting step 2
PALETTE_PAL = {"A": "#A9825C", "H": "#D9B38C", "m": "#FF6FA1", "y": "#FFD86B", "u": "#31A8FF", "g": "#6CC486"}
EASEL = [
    ".....DD.....", ".FFFFFFFFFF.", ".FxxxxxxxxF.", ".FxxxxxxxxF.", ".FxxxxxxxxF.", ".FxxxxxxxxF.", ".FxxxxxxxxF.",
    ".FFFFFFFFFF.", "WWWWWWWWWWWW", "..W..DD..W..", "..W..DD..W..", ".W...DD...W.", ".W...DD...W.", "W....DD....W",
    "W....DD....W",
]
PAINTING = ["ssssssss", "ssysssss", "ssssssgg", "gggggggg", "ggmggggm"]   # canvas rows 2-6, cols 2-9
EASEL_PAL = {"W": "#8A6440", "D": "#5E4329", "F": "#D8CBB0", "x": "#F4EFE4", "s": "#7FB6E6", "g": "#6CC486",
             "y": "#FFD86B", "m": "#FF6FA1"}
# Work effects: Construction ("build"), Cooking ("cook"), Computer ("comp").
# Positions are in the composite grid, facing right.
HAMMER = [".NNNN", ".MMMD", "...h.", "..h..", ".h...", "h...."]
HAMMER_PAL = {"N": "#D5DAE3", "M": "#8C93A3", "D": "#4E5360", "h": "#A86B3C"}
CONE = ["..O..", ".OOo.", ".WWW.", "OOOOo", "BBBBB"]
CONE_PAL = {"O": "#FF7A1A", "o": "#D9570B", "W": "#F4F4F4", "B": "#3A3D45"}
WALL = ["RRRjRRRj", "rrrjrrrj", "RjRRRjRR", "rjrrrjrr", "RRRjRRRj", "rrrjrrrj", "RjRRRjRR", "rjrrrjrr"]
WALL_PAL = {"R": "#C4553A", "r": "#9A3E2A", "j": "#D9CFC0"}
BARRIER = ["YYKKYYKKYY", "YKKYYKKYYK", "KKYYKKYYKK", ".L......L.", ".L......L.", "LLL....LLL"]
BARRIER_PAL = {"Y": "#FFC21A", "K": "#26262B", "L": "#8C93A3"}
VEST_SLIME = [(1, 4), (2, 4), (3, 4), (8, 4), (9, 4), (10, 4), (1, 5), (2, 5), (3, 5), (8, 5), (9, 5), (10, 5),
              (1, 6, "S"), (2, 6, "S"), (3, 6, "S"), (8, 6, "S"), (9, 6, "S"), (10, 6, "S"), (2, 7), (3, 7), (8, 7),
              (9, 7)]
VEST_CAT = [(1, 8), (2, 8), (3, 8), (8, 8), (9, 8), (10, 8), (1, 9, "S"), (2, 9, "S"), (3, 9, "S"), (8, 9, "S"),
            (9, 9, "S"), (10, 9, "S"), (2, 10), (3, 10), (8, 10), (9, 10)]
VEST_PAL = {"V": "#FF7A1A", "S": "#E6EEF2"}
PAN = [".....KKK..", "....KMMMK.", "...KMnMMMK", "...KMMMMMK", "...KMMMMMK", "..hhKMMMK.", ".h...KKK..", "h........."]
PAN_PAL = {"K": "#2B2E35", "M": "#4E5360", "n": "#7A8090", "h": "#A86B3C"}
EGG = [(5, 2, "#FFFFFF"), (6, 2, "#FFFFFF"), (5, 3, "#FFFFFF"), (6, 3, "#FFC21A"), (7, 3, "#FFFFFF"),
       (6, 4, "#FFFFFF"), (7, 4, "#FFFFFF")]
STOVE = ["SSSSSSSSSS", "dZdZddZdZd", "dWWWWWWWWd", "dWWWWWWWWd", "dddddddddd", ".Z......Z."]
STOVE_PAL = {"S": "#A9B0BA", "d": "#E4E7EC", "W": "#2B2F38", "Z": "#3A3D45", "F": "#FF7A1A", "f": "#FFD84A"}
FLAME = ["..FfFFfF..", "..fFfFFf.."]
FRY = [["....r...c.....", "..rryrGrrcr...", ".KMMMMMMMMKhhh", "..KKKKKKKK...."],
       ["..r..c........", "....y...r.....", ".G....r.......", "...r.....c....", ".K..r.........", ".KMM..........",
        "..KKMMMMMMKhhh", "....KKKKKK...."]]
FRY_PAL = {"r": "#F3E3A8", "G": "#7BC96F", "c": "#FF8A3D", "y": "#FFD84A", "K": "#2B2E35", "M": "#4E5360", "h": "#A86B3C"}
LAPTOP = [[".KKKKK.", ".KxXxK.", ".KxxxK.", ".KKKKK.", "sssssss"],
          [".KKKKK.", ".KXxXK.", ".KxXxK.", ".KKKKK.", "sssssss"]]
LAPTOP_PAL = {"K": "#2B2E35", "x": "#3D7BFF", "X": "#9CC3FF", "s": "#AEB4C2"}
MUG = [".RRR", "RRRR", ".RRR"]
MUG_PAL = {"R": "#E8364A"}
DESK = ["......KKKKKKKK", "......K......K", "......K......K", "......K......K", "......K......K", "......KKKKKKKK",
        ".........KK...", "........KKKK..", "DDDDDDDDDDDDDD", "eeeeeeeeeeeeee", ".e..........e.", ".e..........e.",
        ".e..........e."]
DESK_PAL = {"K": "#2B2E35", "D": "#A0703F", "e": "#7A5230"}
STEAM, DUST, CAT_PAW = "#D8DDE4", "#D8D4CC", "#5A3E32"
PAPER, SCREEN, SCREEN_OFF = ("#F4F4F0", "#CDD2DA"), ("#3D7BFF", "#9CC3FF"), "#1B2340"
WORK_FULL = {"build": 8, "comp": 7}            # step 3: wall rows / paper sheets until "done" (cooking never ends)

HEART = ["rr.rr", "rrrrr", ".rrr.", "..r.."]
SWEAT = [".s.", "sss", "sws", ".s."]
SWEAT_PAL = {"s": "#9ED8FF", "w": "#FFFFFF"}
SIGN = ["..AAA..", ".AaaaA.", "AaaaaaA", "AaaaaaA", "AaaaaaA", ".AaaaA.", "..AAA.."]
Z_SMALL = ["###", ".#.", "###"]
Z_BIG = ["####", "..#.", ".#..", "####"]
GEAR = ["...###...", ".#.###.#.", "..#####..", "####.####", "###...###", "####.####", "..#####..", ".#.###.#.",
        "...###..."]

# Face pixels as (col, row, key) on the 12 x 10 body; key "e" unless given.
_CHEEKS = [(1, 4, "c"), (2, 4, "c"), (9, 4, "c"), (10, 4, "c")]
_SMILE = [(4, 5), (7, 5), (5, 6), (6, 6)]
FACES = {
    "neutral":   [(3, 2), (3, 3), (8, 2), (8, 3), *_SMILE, *_CHEEKS],
    "blink":     [(3, 3), (8, 3), *_SMILE, *_CHEEKS],
    "glance":    [(3, 3), (3, 4), (8, 3), (8, 4), *_SMILE, *_CHEEKS],
    "happy":     [(2, 3), (3, 2), (4, 3), (7, 3), (8, 2), (9, 3), (4, 5), (5, 5), (6, 5), (7, 5), (5, 6, "t"),
                  (6, 6, "t"), *_CHEEKS],
    "focused":   [(2, 2), (2, 3), (3, 3), (9, 2), (9, 3), (8, 3), (5, 5), (6, 5)],
    "tired":     [(2, 3), (3, 3), (4, 3), (3, 4), (7, 3), (8, 3), (9, 3), (8, 4), (4, 6), (5, 5), (6, 6), (7, 5)],
    "surprised": [(2, 2), (3, 2, "w"), (2, 3), (3, 3), (8, 2), (9, 2, "w"), (8, 3), (9, 3), (5, 5), (6, 5), (5, 6),
                  (6, 6)],
    "sleep":     [(2, 3), (3, 4), (4, 3), (7, 3), (8, 4), (9, 3), (5, 6), (6, 6)],
}

# Composite grid: body at (PX, PY); column 10's left edge is the pet's centre line; row 18 is the feet row.
PX, PY, MIRROR = 4, 9, 19


def stamp(cells, sprite, c0, r0, pal=PAL, from_row=0):
    """Writes a sprite's pixels into cells {(col, row): color}."""
    for r, row in enumerate(sprite):
        if r < from_row:
            continue
        for c, ch in enumerate(row):
            if ch != ".":
                cells[(c0 + c, r0 + r)] = pal[ch]


def runs(cells, mirror=False):
    """Merges cells into horizontal runs [(col, row, length, color)] so each run is one rectangle."""
    rows = {}
    for (c, r), col in cells.items():
        rows.setdefault(r, []).append((MIRROR - c if mirror else c, col))
    out = []
    for r, items in rows.items():
        items.sort()
        i = 0
        while i < len(items):
            j = i
            while j + 1 < len(items) and items[j + 1][0] == items[j][0] + 1 and items[j + 1][1] == items[i][1]:
                j += 1
            out.append((items[i][0], r, j - i + 1, items[i][1]))
            i = j + 1
    return out


def work_frame(effect, t):
    """The held item's 2-frame animation: hammer tap (build), pan shake (cook), laptop screen (comp)."""
    return int(t * (3 if effect == "build" else 6 if effect == "cook" else 2.5)) % 2


def work_vest(cells, cat, x0, y0):
    """Construction step 2+: the orange safety vest, on a body whose left column is x0 (row y0 = the slime's top
    row / the cat's grid row 0). Drawn before the hat."""
    for v in (VEST_CAT if cat else VEST_SLIME):
        cells[(x0 + v[0], y0 + v[1])] = VEST_PAL[v[2] if len(v) > 2 else "V"]


def work_held(cells, effect, step, f, cat, dy=0, dx=0):
    """Held items: steps 1-2 hammer / pan (+ egg) / laptop in the front hand, and from step 2 the coffee mug in
    the other hand (Computer). f = work_frame(). The cat shows a paw on the handle. dy moves everything down for
    a pet whose body sits lower than the slime's (the pumpkin); dx pushes the items out to the side for a pet
    with no hands, which floats them beside itself (the ghost)."""
    if 1 <= step < 3:
        if effect == "build":
            stamp(cells, HAMMER, 15 + dx, (9 if cat else 10) + f + dy, HAMMER_PAL)
            paw = (16, 13 + f + dy)
        elif effect == "cook":
            y = (7 if cat else 8) - f + dy
            stamp(cells, PAN, 15 + dx, y, PAN_PAL)
            if step >= 2:
                for c, r, col in EGG:
                    cells[(15 + dx + c, y + r)] = col
            paw = (16, 13 - f + dy)
        elif effect == "comp":
            stamp(cells, LAPTOP[f], 15 + dx, (10 if cat else 11) + dy, LAPTOP_PAL)
            paw = (16, 14 + dy)
        else:
            paw = None
        if cat and paw:
            cells[paw] = CAT_PAW
    if effect == "comp" and step >= 2:
        x, y = (1, 13) if cat else (0, 14)
        stamp(cells, MUG, x - dx, y + dy, MUG_PAL)


def _steam(out, x, y, h, t, n, speed, thin):
    """Rising, wiggling wisps of steam as (col, row, color)."""
    for k in range(n):
        ph = (t * speed + k / n) % 1
        if ph < .92:
            out.append((x + round(math.sin(ph * 5 + k * 2.1)) + (0 if thin else (k % 2) * 2), y - int(ph * h), STEAM))


def work_puffs(effect, step, t, cat, at_work, dy=0):
    """Small moving bits drawn every frame, not cached: steam, dust. at_work = step 3 with the work spot up.
    dy moves them down with a pet whose body sits lower (the pumpkin); the work spot's own bits stay put.
    -> [(col, row, color)] in the composite grid, facing right."""
    out = []
    if effect == "build" and step == 2 and not at_work and work_frame("build", t):
        d = int(t * 3) % 4
        for i, (x, y) in enumerate(((19, 9), (21, 8), (20, 10), (22, 10), (23, 9))):
            if (i + d) % 2 == 0:
                out.append((x + (d >> 1), y - (d & 1), DUST))
    elif effect == "cook":
        if at_work:
            _steam(out, 19, 7 if int(t * 2.6) % 2 else 8, 6, t, 5, .6, False)
        elif step >= 2:
            _steam(out, 21, (7 if cat else 8) - work_frame("cook", t) - 1, 5, t, 4, .7, False)
    elif effect == "comp" and step >= 2:
        x, y = (1, 13) if cat else (0, 14)
        _steam(out, x + 2, y - 1, 3, t, 2, .55, True)
    return [(c, r + dy, col) for c, r, col in out] if dy else out


def work_state(effect, front, t, prog):
    """Everything that changes the look of the step-3 work spot, as a small tuple (a cache key).
    prog: 0..1 of the wall / paper stack."""
    if effect == "build":
        return () if front else (min(8, int(prog * 8)), int(t * 4) % 2)
    if effect == "cook":
        return None if front else (int(t * 8) % 2, int(t * 2.6) % 2)
    if effect == "comp" and front:
        full = prog * 7
        n = min(7, int(full))
        fr = full - int(full)
        return int(t * 3) % 15, n, round(2 + (13 - n - 2) * fr), round(math.sin(fr * 9))
    return None


def work_spot(cells, effect, front, state):
    """Step 3's work spot on the ground (behind the pet, or in front of it when front). state: work_state()."""
    if state is None:
        return
    if effect == "build" and not front:
        b, blink = state
        stamp(cells, BARRIER, -5, 13, BARRIER_PAL)
        stamp(cells, WALL[8 - b:], 22, 19 - b, WALL_PAL)
        if b < 8 and blink:                                   # the next brick going on
            stamp(cells, ["RRR" if b % 2 else "rrr"], 26 if b % 2 else 22, 18 - b, WALL_PAL)
    elif effect == "build":
        stamp(cells, CONE, 17, 14, CONE_PAL)
    elif effect == "cook":
        flame, toss = state
        stamp(cells, STOVE, 16, 13, STOVE_PAL)
        stamp(cells, [FLAME[flame]], 16, 12, STOVE_PAL)
        stamp(cells, FRY[toss], 15, 4 if toss else 8, FRY_PAL)
    elif effect == "comp":
        off, n, yy, xo = state
        stamp(cells, DESK, 13, 6, DESK_PAL)
        for r in range(4):                                     # code lines scrolling on the monitor
            ln = 2 + ((r + off) * 37 % 5)
            for c in range(6):
                cells[(20 + c, 7 + r)] = (SCREEN[1 if (r + off) % 3 == 0 else 0]) if c < ln else SCREEN_OFF
        for i in range(n):
            for c in range(4):
                cells[(14 + c, 13 - i)] = PAPER[i % 2]
        if n < 7:                                              # the next sheet floating down
            for c in range(4):
                cells[(14 + c + xo, yy)] = PAPER[n % 2]


def easel_rows(progress):
    """The easel with its picture painted up to progress (0..1): column by column, top to bottom."""
    cols = progress * 8
    n = int(cols)
    out = []
    for r, row in enumerate(EASEL):
        if 2 <= r <= 6:
            pr = PAINTING[r - 2]
            s = "".join(pr[i] if i < n or (i == n and r - 2 < (cols - n) * 5) else "x" for i in range(8))
            row = row[:2] + s + row[10:]
        out.append(row)
    return out
