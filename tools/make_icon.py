"""Builds assets/app_icon.ico: the wizard-hat slime.

One 16 x 16 pixel design made from the gadget's own sprites, scaled by whole numbers (x1 ... x16) so every size
stays sharp. Each size is stored as a PNG inside the .ico (Windows Vista and later read these).
Run: python tools/make_icon.py
"""
import os
import struct
import sys
import tempfile
import tkinter as tk

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
import sprites as sp  # noqa: E402

SIZES = (16, 24, 32, 48, 64, 128, 256)
OUT = os.path.join(ROOT, "assets", "app_icon.ico")


def icon_cells():
    """{(col, row): color} on the 16 x 16 grid: body at columns 2-13, rows 7-15; hat on top like the gadget."""
    cells = {}
    sp.stamp(cells, sp.BODY, 2, 7)
    for f in sp.FACES["neutral"]:
        cells[(2 + f[0], 7 + f[1])] = sp.PAL[f[2] if len(f) > 2 else "e"]
    sp.stamp(cells, sp.HAT, 2, 0)
    return cells


def png_bytes(root, cells, size):
    """One size as PNG bytes. 24 px isn't a whole multiple of 16: it uses the 16 px art, centred."""
    k = size // 16
    pad = (size - 16 * k) // 2
    img = tk.PhotoImage(master=root, width=size, height=size)
    for (c, r), col in cells.items():
        x, y = pad + c * k, pad + r * k
        img.put(col, to=(x, y, x + k, y + k))
    fd, path = tempfile.mkstemp(suffix=".png")
    os.close(fd)
    try:
        img.write(path, format="png")
        with open(path, "rb") as f:
            return f.read()
    finally:
        os.remove(path)


def main():
    root = tk.Tk()
    root.withdraw()
    cells = icon_cells()
    pngs = [png_bytes(root, cells, s) for s in SIZES]
    root.destroy()
    head = struct.pack("<HHH", 0, 1, len(SIZES))
    offset = 6 + 16 * len(SIZES)
    entries, data = b"", b""
    for s, png in zip(SIZES, pngs):
        entries += struct.pack("<BBBBHHII", s % 256, s % 256, 0, 0, 1, 32, len(png), offset + len(data))
        data += png
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "wb") as f:
        f.write(head + entries + data)
    with open(os.path.join(os.path.dirname(OUT), "app_icon_256.png"), "wb") as f:
        f.write(pngs[-1])
    print(f"wrote {OUT} ({', '.join(map(str, SIZES))} px)")


if __name__ == "__main__":
    main()
