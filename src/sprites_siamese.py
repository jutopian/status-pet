"""Pixel art for the Siamese cat.

Same format as sprites.py: each sprite is a list of rows; "." is empty, every other letter is a color from PAL.
One sprite pixel is drawn as a small square block, like the slime.

How it is wired in:
- The base art faces the viewer with the TAIL ON THE LEFT. Drawn as is, the cat walks right (tail behind,
  wand / brush in front). Walking left, mirror the whole pose, exactly like the slime. No other tail rules.
- Grid: 17 columns x 13 rows. Columns 0-4 are the tail area; the 12-wide body starts at column BODY_X = 5,
  so a slime offset "PX + n" becomes "BODY_X + n". Rows 0-1 are the ears, row HEAD_TOP = 2 is the top of the
  head (the slime's row 0), rows 11-12 are the feet (row 12 stands on the ground).
  The cat is 3 rows taller than the slime (2 ear rows, 2-row feet) and 5 columns wider on the tail side.
- Placing it in the slime's composite grid: put column BODY_X on sprites.PX and row 12 on the slime's feet row
  (sprites.PY + 9), i.e. origin (PX - BODY_X, PY - 3). Then sprites.MIRROR works unchanged.
  In the cat's own grid, mirroring is col -> MIRROR - col (MIRROR = 21 keeps the body in place).
- The step frame: FEET[1] plus TAIL_SWAY (the tail tip swings 1 px outward), plus the program's usual 1 px lift.
- Hats: use the program's own hat code (Gadget.hat_cells) with the body at (BODY_X, HEAD_TOP), i.e. the cat's
  head top takes the place of the slime's row 0; then redraw EARS on top so they poke through. The cat has no hat
  rules of its own, so hats face the same way as on the slime; if the slime's hat direction changes, the cat
  follows automatically.
- Props: sprites.WAND at (PROP_X, WAND_Y + wob), sprites.BRUSH at (PROP_X, BRUSH_Y + dab), then the paw pixel
  (WAND_PAW / BRUSH_PAW, moved down by wob / dab). The wand star centre is column PROP_X + 3.
- Sleep: draw LOAF from row LOAF_Y instead of BODY + FEET; face pixels and ears move down by LOAF_Y.
- Sweat and "z Z" are not mirrored (like the slime): SWEAT_AT, Z_SMALL_AT, Z_BIG_AT (top-left of each sprite).
  SWEAT_AT sits 2 rows above the slime's spot so it never touches the tail.
- build() puts a pose together; it is the reference for how the pieces combine.
"""

PAL = {
    "O": "#2A1D18", "C": "#F3E6CF", "S": "#D9C3A2", "m": "#5A3E32",   # outline, cream body, body shade, brown points
    "E": "#5AB0FF", "k": "#1E1B26", "w": "#FFFFFF",                   # blue eye, pupil, eye glint
    "p": "#F59BAA", "t": "#F07F8E", "L": "#E9D5B5",                   # nose / cheeks, open mouth, closed eyes
}

BODY_X, HEAD_TOP, MIRROR = 5, 2, 21

BODY = [
    "......O........O.",
    ".....OmO......OmO",
    ".....OmmOOOOOOmmO",
    ".....OCCCmmmmCCCO",
    ".....OCCmmmmmmCCO",
    "..O..OCmmmmmmmmCO",
    ".OmO.OCCmmmmmmCCO",
    ".OmO.OCCCmmmmCCCO",
    "..Om.OCCCCCCCCCCO",
    "...OmOSCCCCCCCCSO",
    "....O.OSSSSSSSSO.",
]
FEET = [                                                   # rows 11-12: standing / mid-step
    [".......mmOOOOmm..", ".......mm....mm.."],
    [".......mmOOOOmm..", "........mm..mm..."],
]
TAIL_SWAY = {5: ".O...", 6: "OmO.."}                       # step frame: replaces columns 0-4 of rows 5 and 6

LOAF_Y = 2                                                 # curled-up sleep pose, drawn from row 2
LOAF = [
    "......O........O.",
    ".....OmO......OmO",
    "...OOOmmOOOOOOmmO",
    "..OCCOCCCmmmmCCCO",
    ".OCCCOCCmmmmmmCCO",
    ".OCCCOCmmmmmmmmCO",
    ".OCCSOCCmmmmmmCCO",
    ".OCSSOCCCmmmmCCCO",
    ".OSSSOmmCCCCCCmmO",
    ".OmmmmmmmmmmmmmmO",
    "..OOOOOOOOOOOOOO.",
]

# Face pixels as (col, row, key): col counted from the body's left edge (add BODY_X), row on the grid.
_NOSE = [(5, 6, "p"), (6, 6, "p")]
_CHEEKS = [(1, 6, "p"), (10, 6, "p")]
FACES = {
    "neutral":   [(3, 4, "E"), (3, 5, "k"), (8, 4, "E"), (8, 5, "k"), *_NOSE, *_CHEEKS],
    "blink":     [(2, 5, "L"), (3, 5, "L"), (8, 5, "L"), (9, 5, "L"), *_NOSE, *_CHEEKS],
    "glance":    [(3, 5, "E"), (3, 6, "k"), (8, 5, "E"), (8, 6, "k"), *_NOSE, *_CHEEKS],
    "happy":     [(2, 5, "L"), (3, 4, "L"), (4, 5, "L"), (7, 5, "L"), (8, 4, "L"), (9, 5, "L"), (5, 7, "t"),
                  (6, 7, "t"), *_NOSE, *_CHEEKS],
    "focused":   [(3, 5, "E"), (4, 5, "E"), (7, 5, "E"), (8, 5, "E"), *_NOSE],
    "tired":     [(3, 4, "L"), (4, 4, "L"), (3, 5, "E"), (7, 4, "L"), (8, 4, "L"), (8, 5, "E"), *_NOSE],
    "surprised": [(3, 4, "w"), (4, 4, "E"), (3, 5, "E"), (4, 5, "k"), (7, 4, "E"), (8, 4, "w"), (7, 5, "k"),
                  (8, 5, "E"), (5, 8, "O"), (6, 8, "O"), *_NOSE],
    "sleep":     [(2, 4, "L"), (3, 5, "L"), (4, 4, "L"), (7, 4, "L"), (8, 5, "L"), (9, 4, "L"), *_NOSE, *_CHEEKS],
}


def _ears(rows, dy=0):
    """Ear cells (rows 0-2, the outer 3 columns of the body on each side) as (col, row, key)."""
    out = []
    for r, row in enumerate(rows[:3]):
        for c, ch in enumerate(row):
            if ch != "." and (BODY_X <= c < BODY_X + 3 or BODY_X + 9 <= c < BODY_X + 12):
                out.append((c, r + dy, ch))
    return out


EARS = _ears(BODY)
LOAF_EARS = _ears(LOAF, LOAF_Y)

PROP_X, WAND_Y, BRUSH_Y = BODY_X + 11, HEAD_TOP + 1, HEAD_TOP
WAND_PAW = (BODY_X + 12, HEAD_TOP + 5)                     # + wob
BRUSH_PAW = (BODY_X + 12, HEAD_TOP + 3)                    # + dab

SWEAT_AT = (BODY_X - 3, HEAD_TOP - 2)
Z_SMALL_AT = (BODY_X + 12, LOAF_Y)
Z_BIG_AT = (BODY_X + 15, LOAF_Y - 5)


def _stamp(cells, sprite, c0, r0, pal):
    for r, row in enumerate(sprite):
        for c, ch in enumerate(row):
            if ch != ".":
                cells[(c0 + c, r0 + r)] = pal[ch]


def build(cells, face="neutral", feet=0, sway=False, loaf=False, hat=None, wand=-1, brush=-1, props=None,
          hat_front=False):
    """Writes one pose into cells {(col, row): color}, facing right (mirror it for walking left).

    hat: a function hat(cells, bx, head_top) that stamps the worn hat for a 12-wide body whose left column is bx,
    exactly as it does for the slime. In the program: lambda c, bx, top: self.hat_cells(c, hat_id, bx, top)
    (the slime's HEAD_TOP there is 0, so "by" is the head-top row). wand / brush: -1 = none, else the wob / dab
    frame (0 or 1).
    props: (WAND, BRUSH, pal), normally (sprites.WAND, sprites.BRUSH, sprites.PAL); needed only with a prop.
    hat_front: the hat covers the ears (a "_front" hat file); otherwise the ears are redrawn over it.
    """
    dy = LOAF_Y if loaf else 0
    if loaf:
        _stamp(cells, LOAF, 0, LOAF_Y, PAL)
    else:
        rows = list(BODY)
        if sway:
            for r, tip in TAIL_SWAY.items():
                rows[r] = tip + rows[r][len(tip):]
        _stamp(cells, rows, 0, 0, PAL)
        _stamp(cells, FEET[feet], 0, 11, PAL)
    for c, r, key in FACES[face]:
        cells[(BODY_X + c, r + dy)] = PAL[key]
    if hat:
        hat(cells, BODY_X, HEAD_TOP + dy)
        if not hat_front:
            for c, r, key in (LOAF_EARS if loaf else EARS):
                cells[(c, r)] = PAL[key]
    if wand >= 0:
        _stamp(cells, props[0], PROP_X, WAND_Y + wand, props[2])
        cells[(WAND_PAW[0], WAND_PAW[1] + wand)] = PAL["m"]
    if brush >= 0:
        _stamp(cells, props[1], PROP_X, BRUSH_Y + brush, props[2])
        cells[(BRUSH_PAW[0], BRUSH_PAW[1] + brush)] = PAL["m"]
    return cells
