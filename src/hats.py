"""Hats for the pet: small built-in PNG files in the hats/ folder, read once at start.

Rules for a hat PNG: 1 image pixel = 1 sprite pixel, transparent background, at most MAX_W x MAX_H.
Empty rows above and below are trimmed; the bottom row sits on the pet's head and the image (its full
width, so side padding can nudge it) is centred over the head. The file name is the hat's name: straw_hat.png -> "Straw hat".
Layer: by default a hat sits behind the character's ears (the cat's ears poke through). A file name ending in
FRONT_TAG (hard_hat_front.png) is drawn over the ears instead; the shown name drops the tag ("Hard hat").
"""
import os
import tkinter as tk

from i18n import tr

MAX_W, MAX_H = 24, 16
BUILTIN = ("wizard_hat", "beret", "straw_hat", "crown", "chef_hat", "hard_hat_front", "blue_cap_front")
                                                        # every shipped hat; all hats in hats/ are built in now
FOLLOW = "@default"                                        # an app's hat choice meaning "same as the Default row"
FRONT_TAG = "_front"                                       # file name tag: drawn over the ears
RENAMED = {"hard_hat": "hard_hat_front"}                   # old saved hat ids -> current file names


def is_front(hat_id):
    return hat_id.endswith(FRONT_TAG)


def hat_name(hat_id):
    if is_front(hat_id):
        hat_id = hat_id[:-len(FRONT_TAG)]
    return hat_id.replace("_", " ").replace("-", " ").strip().capitalize()


def _read(root, path):
    """PNG -> rows of '#RRGGBB' / None, trimmed to the visible pixels. Raises ValueError with a reason."""
    try:
        img = tk.PhotoImage(master=root, file=path)
    except tk.TclError:
        raise ValueError(tr("couldn't be read")) from None
    w, h = img.width(), img.height()
    rows = []
    for y in range(h):
        row = []
        for x in range(w):
            if img.transparency_get(x, y):
                row.append(None)
            else:
                r, g, b = img.get(x, y)
                row.append("#%02X%02X%02X" % (r, g, b))
        rows.append(row)
    while rows and not any(rows[0]):              # trim transparent borders (inner empty rows are kept)
        rows.pop(0)
    while rows and not any(rows[-1]):
        rows.pop()
    if not rows:
        raise ValueError(tr("is empty (fully transparent)"))
    # side columns are kept on purpose: the image width is what gets centred over the head
    if len(rows[0]) > MAX_W or len(rows) > MAX_H:
        raise ValueError(tr("is too big ({w} x {h}; max {mw} x {mh})", w=len(rows[0]), h=len(rows), mw=MAX_W, mh=MAX_H))
    return rows


def load(root, folder):
    """-> (hats, problems). hats: {id: {"name", "rows", "builtin", "front"}}, built-in hats first, then by name.
    problems: short messages about files that were skipped."""
    hats, problems = {}, []
    try:
        files = sorted(f for f in os.listdir(folder) if f.lower().endswith(".png"))
    except OSError:
        return hats, problems
    found = {}
    for f in files:
        hat_id = os.path.splitext(f)[0].lower()
        try:
            found[hat_id] = _read(root, os.path.join(folder, f))
        except ValueError as e:
            problems.append(f"{f} {e}")
    for hat_id in sorted(found, key=lambda i: (i not in BUILTIN, BUILTIN.index(i) if i in BUILTIN else 0, i)):
        hats[hat_id] = {"name": hat_name(hat_id), "rows": found[hat_id], "builtin": hat_id in BUILTIN,
                        "front": is_front(hat_id)}
    return hats, problems


