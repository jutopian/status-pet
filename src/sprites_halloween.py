"""The Halloween effect ("trick or treat").

Everything here travels with the pet, so it keeps wandering at every step - there is no work spot to stand at.

Step 1: it carries a small carved pumpkin whose face flickers (`lantern_lit`). A pet with no hands (the ghost,
        the pumpkin) floats it beside itself, like its other props.
Step 2: + a 2 x 2 sweet drops behind the pet every 2.5-5.5 s, bounces and stays on the ground; the last
        TRAIL_MAX make a trail behind it (the gadget keeps the sweets, see Gadget._particles).
Step 3: + five bats whirl around the pet on two uneven rings at their own speeds, drawn behind it on the far
        side and in front on the near side, wings beating fast (`bats`). The pet hurries (HURRY) and drops a
        sweet about once a second.

Positions are columns and rows in the program's composite grid (the pet's body is 12 wide at sprites.PX, the
ground is row 18), facing right.
"""
import math

# ---------- step 1: the carried lantern ----------
CARRY = ["..ss..", ".OOOO.", "OAAAAO", "OAAAAO", "OAAAAO", ".OOOO."]
CARRY_PAL = {"s": "#6B4226", "O": "#7A3B0C", "A": "#F08A22"}
CARRY_AT = (14, 12)                               # top-left in the composite grid, like the wand's spot
CARRY_PAW = (16, 13)                              # the cat's paw on the handle
CARRY_FACE = ((2, 2), (3, 2), (2, 4), (3, 4))     # eyes and mouth, drawn every frame because they flicker

# ---------- step 2: the sweets ----------
SWEETS = ("#FF6FA1", "#5AB0FF", "#FFD34A", "#8BE06B", "#C89BFF")
TRAIL_MAX = 8                                     # only the last few stay on the ground
DROP_GAP = ((2.5, 5.5), (.7, 1.5))                # seconds between sweets at step 2 / step 3
GRAVITY, BOUNCE, BEHIND, DROP_H = 76.0, -.4, 13, 10   # px/s², how much a bounce keeps, where and how high it starts

# ---------- step 3: the bats ----------
BAT = [["b...b", "bbbbb", ".bBb."], [".b.b.", "bbbbb", "..B.."]]
BAT_PAL = {"b": "#3A2A4A", "B": "#6B5480"}
HURRY = 1.7                                       # how much faster the pet walks at step 3

_GLOW_LOW, _GLOW_ON, _GLOW_HOT = "#FFA23A", "#FFD36B", "#FFF3C4"


def _mix(a, b, t):
    p = lambda c: (int(c[1:3], 16), int(c[3:5], 16), int(c[5:7], 16))
    x, y = p(a), p(b)
    return "#" + "".join(f"{round(x[i] + (y[i] - x[i]) * t):02x}" for i in range(3))


def lantern_lit(t):
    """The carried lantern's candle: 0..1, two waves so it never settles. Rounded to 10 steps."""
    lit = .65 + .3 * math.sin(t * 4.3) + .2 * math.sin(t * 9.1 + 1)
    return round(min(1.0, max(.3, lit)) * 10) / 10


def lantern_color(lit):
    """Warm orange -> yellow -> almost white, like the pumpkin pet's carving."""
    if lit < .5:
        return _mix(_GLOW_LOW, _GLOW_ON, lit / .5)
    return _mix(_GLOW_ON, _GLOW_HOT, (lit - .5) / .5)


def bats(t):
    """Five bats on two uneven rings around the pet, each at its own speed, the ring breathing in and out.
    -> (behind the pet, in front of it), each [(col, row, frame)] in the composite grid."""
    back, front = [], []
    for i in range(5):
        spin = 2.6 + (.5 if i % 2 else -.35)
        a = t * spin + i * math.tau / 5
        rx = 8 + (2 if i % 2 else 0) + math.sin(t * 1.7 + i) * 1.2
        ry = 3 + (1.2 if i % 2 else 0)
        x = round(8 + math.cos(a) * rx)
        y = round(10 + math.sin(a) * ry - (2 if i % 2 else 0))
        (back if math.sin(a) < 0 else front).append((x, y, (int(t * 12) + i) % 2))
    return back, front

