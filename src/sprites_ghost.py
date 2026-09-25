"""Pixel art for the ghost pet. The body is 10 columns wide; the hat slot still sits centered on the 12-wide
grid.

Same format as sprites.py: each sprite is a list of rows; "." is empty, every other letter is a color from PAL.
One sprite pixel is drawn as a small square block, like the slime.

How it is wired in:
- Grid: the body is 10 columns wide (narrower than the other pets, centered on the shared 12-wide grid so
  hats still line up), 9 rows plus a 2-row hem, and it has no feet. In the
  program's composite grid its top row is sprites.PY + TOP and the hem's bottom row is the slime's feet row; the
  bob then lifts it off the ground.
- See-through: the whole pet is drawn with alpha, more see-through toward the hem (`row_alpha`), and the face
  stays readable (`face_alpha`). A hat does not fade - only a vanishing ghost takes its hat with it.
  `build(..., bg=...)` bakes the same look into solid colors for pictures that cannot use alpha (the Settings
  tiles and the tray icon).
- Vanishing: every 7-15 seconds (a new wait each time) it fades away and comes back over 1.5 s (`vanish_dim`).
  Asleep it sinks (SLEEP_DROP) and nearly disappears (SLEEP_DIM).
- Bobbing and drifting: `bob()` is a slow rise and fall that never stops - the pet is never still. The hem does
  not ripple.
- No hands: props (wand, brush, hammer, pan, laptop) float beside it, one column further out than on the other
  pets and with a bob of their own (`prop_bob`).
- Faces: resting / drifting (happy) / working / Boo! / asleep. The program's "surprised" is the Boo! face.
"""
import math

PAL = {"W": "#EDF2FF", "w": "#D6DEF5", "u": "#B9C4E8", "k": "#241E33"}   # sheet, shade, deep shade, face

BODY = [
    "....WWWWW...",
    "..WWWWWWWW..",
    ".WWWWWWWWWW.",
    ".WWWWWWWWWW.",
    ".WWWWWWWWWW.",
    ".WWWWWWWWWw.",
    ".WWWWWWWWww.",
    ".wWWWWWWWww.",
    ".wwwwwwwwww.",
]
HEM = ["..ww.ww.ww..", "..w..w..w..."]     # a still, scalloped hem

ROWS = len(BODY) + len(HEM)
TOP = -1         # body top row = sprites.PY + TOP (the hem's bottom row is then the slime's feet row)
PROP_DX = 1      # props float one column further out than on a pet with hands

FADE = .25       # how see-through it is ("Light")
SLEEP_DIM, SLEEP_DROP = .45, 2            # asleep it nearly disappears and sinks 2 rows
VANISH_LEN, VANISH_GAP, VANISH_DEEP = 1.5, (7.0, 15.0), .88   # seconds, wait between, how far it fades

FACES = {
    "neutral":   [(3, 3), (3, 4), (8, 3), (8, 4), (5, 6), (6, 6)],
    "happy":     [(2, 4), (3, 3), (4, 4), (7, 4), (8, 3), (9, 4), (5, 6), (6, 6), (5, 7), (6, 7)],
    "focused":   [(3, 4), (4, 4), (7, 4), (8, 4), (5, 6), (6, 6)],
    "boo":       [(2, 3), (3, 3), (2, 4), (3, 4), (8, 3), (9, 3), (8, 4), (9, 4), (4, 6), (5, 6), (6, 6), (7, 6),
                  (4, 7), (5, 7), (6, 7), (7, 7), (5, 8), (6, 8)],
    "sleep":     [(2, 4), (3, 4), (4, 4), (7, 4), (8, 4), (9, 4), (5, 6), (6, 6)],
}
# the program has more moods than this face can show; "surprised" is the ghost's Boo!
ALIAS = {"surprised": "boo", "blink": "neutral", "glance": "neutral", "tired": "neutral"}


def row_alpha(r, dim=0.0, fade=FADE):
    """How solid the pet is on body row r (0 = the top row): more see-through toward the hem. Rows above the
    body are a hat, which only fades when the whole ghost vanishes."""
    if r < 0:
        return 1 - dim
    down = min(1.0, max(0.0, r / (ROWS - 1)))
    return max(.12, (1 - fade * (.35 + .65 * down)) * (1 - dim))


def face_alpha(dim=0.0, fade=FADE):
    """The eyes and mouth stay readable however see-through the sheet is."""
    return max(.35, (1 - fade * .25) * (1 - dim))


def bob(t, busy=False, sleeping=False):
    """Rows up or down: it is always drifting up and down, never standing."""
    speed = 2.2 if busy else .7 if sleeping else 1.4
    size = .6 if sleeping else 1.6 if busy else 1.3
    return round(math.sin(t * speed) * size)


def prop_bob(t):
    """A floating prop keeps its own rhythm, so it never looks stuck to the pet."""
    return round(math.sin(t * 1.9 + 1) * 1.4)


def vanish_dim(fade_t):
    """fade_t = seconds into a vanish (0 .. VANISH_LEN) -> how far it has faded, 0 -> deep -> 0."""
    if fade_t <= 0 or fade_t >= VANISH_LEN:
        return 0.0
    return math.sin(fade_t / VANISH_LEN * math.pi) * VANISH_DEEP


def face_cells(face):
    """The eyes and mouth as (col, row) on the body."""
    return FACES.get(ALIAS.get(face, face), FACES["neutral"])


def _mix(bg, col, a):
    p = lambda c: (int(c[1:3], 16), int(c[3:5], 16), int(c[5:7], 16))
    b, x = p(bg), p(col)
    return "#" + "".join(f"{round(b[i] + (x[i] - b[i]) * a):02x}" for i in range(3))


def body_cells(cells, x0, y0, hat=None, bg=None, dim=0.0):
    """The sheet and its hem (and the hat, always behind nothing - it simply sits on top), body top-left at
    (x0, y0). With bg, the see-through look is baked into solid colors; without it the caller draws the rows
    with alpha (row_alpha)."""
    for r, row in enumerate(BODY + HEM):
        for c, ch in enumerate(row):
            if ch != ".":
                col = PAL[ch]
                cells[(x0 + c, y0 + r)] = _mix(bg, col, row_alpha(r, dim)) if bg else col
    if hat:
        before = set(cells) if bg else ()
        hat(cells, x0, y0)
        if bg:                                # a hat only fades when the whole ghost vanishes
            for k in cells.keys() - before:
                cells[k] = _mix(bg, cells[k], max(.12, 1 - dim))
    return cells


def build(cells, x0, y0, face="neutral", hat=None, bg="#1E1B26", dim=0.0):
    """The whole pet in solid colors, for pictures that cannot use alpha (Settings tiles, the tray icon)."""
    body_cells(cells, x0, y0, hat, bg, dim)
    col = _mix(bg, PAL["k"], face_alpha(dim)) if bg else PAL["k"]
    for c, r in face_cells(face):
        cells[(x0 + c, y0 + r)] = col
    return cells
