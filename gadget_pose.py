"""Builds the pet's pixel-art pose as {(col, row): color} cells, for every character and its hat/props.

Pure sprite-data composition: no Tk, win32 or drawing here (see status_pet._draw_pet for that).
Mixed into status_pet.Gadget, which exposes self.HEAD_TOP, self.PET_DY and self.C (copied from
its own module constants, since none of them are ever monkeypatched by a test).
"""
import sprites as sp
import sprites_ghost as spg
import sprites_halloween as sph
import sprites_pumpkin as spp
import sprites_siamese as spc

_BG_DEFAULT = object()     # pose_cells/pet_cells: "use the gadget's panel color" (can't read self.C as a
                            # plain default value, since a def's defaults run before any instance exists)


class GadgetPoseMixin:
    def hat_cells(self, cells, hat_id, bx, by):
        """Stamps a hat for the body at bx, by: centred over the head, bottom row just below the head top."""
        rows = self.hats[hat_id]["rows"]
        x0 = bx + (12 - len(rows[0])) // 2
        y0 = by + self.HEAD_TOP + 1 - (len(rows) - 1)
        for r, row in enumerate(rows):
            for c, col in enumerate(row):
                if col:
                    cells[(x0 + c, y0 + r)] = col

    def cat_cells(self, cells, expr, feet=0, loaf=False, hat=None, wand=-1, brush=-1, vest=False):
        """The Siamese (sprites_siamese.py) in the slime's composite grid: its body column on sp.PX and its feet
        row on the slime's feet row, so mirroring, props and effects line up the same way."""
        def over(c, bx, top):                     # the vest goes on before the hat
            if vest:
                sp.work_vest(c, True, bx, 0)
            if hat:
                self.hat_cells(c, hat, bx, top)
        local = spc.build({}, face=expr, feet=feet, sway=feet == 1, loaf=loaf, hat=over if hat or vest else None,
                          wand=wand, brush=brush, props=(sp.WAND, sp.BRUSH, sp.PAL),
                          hat_front=bool(hat) and self.hats[hat]["front"])
        dx, dy = sp.PX - spc.BODY_X, sp.PY - 3
        for (c, r), col in local.items():
            cells[(c + dx, r + dy)] = col

    def pumpkin_cells(self, cells, expr, sleeping=False, hat=None, wand=-1, brush=-1, vest=False, lit=.5):
        """The jack-o'-lantern (sprites_pumpkin.py) in the slime's composite grid: same 12-wide body, one row
        lower because it has no feet. Its hat always covers the stem."""
        y0 = sp.PY + spp.TOP

        def over(c, bx, by):                      # the vest goes on before the hat, as on the other pets
            if vest:
                sp.work_vest(c, False, bx, by)
            if hat:
                self.hat_cells(c, hat, bx, by)
        spp.build(cells, sp.PX, y0, face="sleep" if sleeping else expr, lit=lit,
                  hat=over if (hat or vest) else None)
        if wand >= 0:
            sp.stamp(cells, sp.WAND, sp.PX + 11, y0 + 1 + wand)
        if brush >= 0:
            sp.stamp(cells, sp.BRUSH, sp.PX + 11, y0 + brush)

    def ghost_cells(self, cells, expr, sleeping=False, hat=None, vest=False, face=True, dim=0.0, bg=None,
                    body=True):
        """The ghost (sprites_ghost.py) in the composite grid: 12 wide like the others, floating where the
        slime's feet are. bg = None leaves the colors plain, so the gadget can fade whole rows as it draws
        them; a color bakes the see-through look in (Settings pictures, the tray icon)."""
        y0 = sp.PY + spg.TOP + (spg.SLEEP_DROP if sleeping else 0)

        def over(c, bx, by):
            if vest:                              # a safety vest on a sheet: it fades along with the body
                sp.work_vest(c, False, bx, by)
            if hat:
                self.hat_cells(c, hat, bx, by)
        if body:
            spg.body_cells(cells, sp.PX, y0, over if (hat or vest) else None, bg, dim)
        if face:
            col = spg._mix(bg, spg.PAL["k"], spg.face_alpha(dim)) if bg else spg.PAL["k"]
            for c, r in spg.face_cells("sleep" if sleeping else expr):
                cells[(sp.PX + c, y0 + r)] = col
        return cells

    def ghost_props(self, cells, wob=-1, dab=-1, palette=False, work=None, trick=0, carry_dy=0, carry_lit=None):
        """No hands: the wand, brush, palette, work items and Halloween lantern float beside the ghost."""
        dx, dy = spg.PROP_DX, spg.TOP
        if wob >= 0:
            sp.stamp(cells, sp.WAND, sp.PX + 11 + dx, sp.PY + 1 + wob + dy)
        if dab >= 0:
            sp.stamp(cells, sp.BRUSH, sp.PX + 11 + dx, sp.PY + dab + dy)
        if palette:
            sp.stamp(cells, sp.PALETTE, sp.PX - 4 - dx, sp.PY + 4 + dy, sp.PALETTE_PAL)
        if work:
            sp.work_held(cells, *work, False, dy, dx)
        if trick:
            self.lantern(cells, carry_dy, False, carry_lit, dx)
        return cells

    def lantern(self, cells, carry_dy=0, cat=False, lit=None, dx=0):
        """Halloween step 1+: the small carved pumpkin the pet carries. A pet with no hands floats it a column
        further out, bobbing. lit = None leaves its flickering face out, so the rest can be cached."""
        c0, r0 = sph.CARRY_AT
        c0, r0 = c0 + dx, r0 + self.PET_DY.get(self.character, 0) + carry_dy
        sp.stamp(cells, sph.CARRY, c0, r0, sph.CARRY_PAL)
        if cat:
            cells[sph.CARRY_PAW] = sp.CAT_PAW
        if lit is not None:
            col = sph.lantern_color(lit)
            for c, r in sph.CARRY_FACE:
                cells[(c0 + c, r0 + r)] = col
        return c0, r0

    def carries(self):
        """A pet with no hands floats the lantern beside itself (the pumpkin and the ghost)."""
        return self.character in ("pumpkin", "ghost")

    def pose_cells(self, cells, expr, feet=0, sleeping=False, hat=None, wob=-1, dab=-1, palette=False, work=None,
                   lit=.5, bg=_BG_DEFAULT, trick=0, carry_dy=0, carry_lit=None):
        """The pet in the composite grid (column 10 = centre line, row 18 = feet) with its hat and props:
        wob >= 0 = the wand, dab >= 0 = the brush, palette = Painting step 2+, work = (effect, step, frame) for
        Construction / Cooking / Computer, lit = how bright the pumpkin's carving glows. Used by the gadget and
        the Effects tab preview."""
        if bg is _BG_DEFAULT:
            bg = self.C["panel"]
        cat = self.character == "cat"
        dy = self.PET_DY.get(self.character, 0)
        vest = bool(work) and work[0] == "build" and work[1] >= 2
        if cat:
            self.cat_cells(cells, expr, feet, sleeping, hat, wob, dab, vest)
        elif self.character == "pumpkin":
            self.pumpkin_cells(cells, expr, sleeping, hat, wob, dab, vest, lit)
        elif self.character == "ghost":
            self.ghost_cells(cells, expr, sleeping, hat, vest, bg=bg)
            self.ghost_props(cells, wob, dab, palette, work, trick, carry_dy, carry_lit)
            return cells
        else:
            sp.stamp(cells, sp.BODY, sp.PX, sp.PY)
            sp.stamp(cells, [sp.FEET[feet]], sp.PX, sp.PY + 9)
            for f in sp.FACES[expr]:
                cells[(sp.PX + f[0], sp.PY + f[1])] = sp.PAL[f[2] if len(f) > 2 else "e"]
            if vest:
                sp.work_vest(cells, False, sp.PX, sp.PY)
            if hat:
                self.hat_cells(cells, hat, sp.PX, sp.PY)
            if wob >= 0:
                sp.stamp(cells, sp.WAND, sp.PX + 11, sp.PY + 1 + wob)
            if dab >= 0:
                sp.stamp(cells, sp.BRUSH, sp.PX + 11, sp.PY + dab)
        if palette:                               # held low on the back side (on the cat: over the tail's tip)
            c, r = (sp.PX - 5, sp.PY + 5) if cat else (sp.PX - 4, sp.PY + 4 + dy)
            sp.stamp(cells, sp.PALETTE, c, r, sp.PALETTE_PAL)
        if work:
            sp.work_held(cells, *work, cat, dy)
        if trick:
            self.lantern(cells, carry_dy, cat, carry_lit, 1 if self.carries() else 0)
        return cells

    def pet_cells(self, hat_id, expr="neutral", char=None, bg=_BG_DEFAULT):
        """The standing pet (and hat) as {(col, row): color} (for Settings pictures; they crop to the pixels).
        bg = what the picture sits on, for a see-through pet (the ghost)."""
        if bg is _BG_DEFAULT:
            bg = self.C["panel"]
        cells, char = {}, char or self.character
        hat_id = hat_id if hat_id in self.hats else None
        if char == "cat":
            self.cat_cells(cells, expr, hat=hat_id)
            return cells
        if char == "pumpkin":
            hat = (lambda c, bx, by: self.hat_cells(c, hat_id, bx, by)) if hat_id else None
            return spp.build(cells, 0, 0, face=expr, lit=.55, hat=hat)
        if char == "ghost":
            hat = (lambda c, bx, by: self.hat_cells(c, hat_id, bx, by)) if hat_id else None
            return spg.build(cells, 0, 0, face=expr, hat=hat, bg=bg)
        sp.stamp(cells, sp.BODY, 0, 0)
        sp.stamp(cells, [sp.FEET[0]], 0, 9)
        for f in sp.FACES[expr]:
            cells[(f[0], f[1])] = sp.PAL[f[2] if len(f) > 2 else "e"]
        if hat_id in self.hats:
            self.hat_cells(cells, hat_id, 0, 0)
        return cells
