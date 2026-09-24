"""Mood, movement and the per-frame animation tick for the gadget (status_pet.Gadget mixes this in).

Pure state update: no drawing here (see status_pet.render/_draw_pet for that) and no Tk/win32
calls beyond scheduling the next tick via self.root.after (tick_frame/_kick run on Tk's own timer, not
from a raw window message, so that's safe). Gadget exposes the module's movement constants as class
attributes (SLEEP_BELOW, XMIN, HOP_*, WALK_SPEED, RUN_SPEED, MAX_*, FAST_MS/NIGHT_MS/IDLE_MS) since none
of them are ever monkeypatched by a test; SLEEP_AFTER is the one exception, so __init__ instead stores it
as self._sleep_after, read live at construction time (a test may repoint it before building Gadget).
"""
import random
import time

import sprites as sp
import sprites_ghost as spg
import sprites_halloween as sph


class GadgetMoveMixin:
    # ---------- mood and movement ----------
    def _update_mood(self, now):
        if self.fx_step >= 1:                     # an effect has started (Effects tab "Start at")
            self.mood, self.calm_since = "busy", None
            return
        if (self.cpu or 0) < self.SLEEP_BELOW and (self.gpu or 0) < self.SLEEP_BELOW:
            if self.calm_since is None:
                self.calm_since = now
            # sleeps only while you are away too; any mouse / keyboard input wakes it
            if now - self.calm_since >= self._sleep_after and self.away >= self._sleep_after \
                    and self.pet.target is None:
                self.mood = "sleep"
                return
        else:
            self.calm_since = None
        self.mood = "walk"

    def _painting(self):
        return self.mood == "busy" and self.fx_step >= 3 and self.effect == "painting"   # at the easel

    def _station(self):
        return self.mood == "busy" and self.fx_step >= 3 and self.effect in self.STATIONS  # easel or a work spot

    def _hops(self):
        return self.character == "pumpkin"

    def _restless(self):
        """Pets that never hold still: the pumpkin's candle flickers, the ghost bobs and fades. The frame loop
        keeps a few frames a second for them even when nothing else is happening."""
        return self.character == "ghost" or (self._hops() and self.mood != "sleep")

    def _hop_dist(self, t, cycle, dist):
        """How far a hopping pet has travelled after t seconds of hopping: one hop covers `dist`, all of it while
        it is in the air."""
        n, r = divmod(t, cycle)
        return dist * (n + min(1.0, r / self.HOP_AIR))

    def _hop_move(self, dt, cycle, dist, moving):
        """Runs the hop clock and returns how far the pet moved this frame. A hop that has started always
        finishes, so it never stops in mid-air; standing still, it waits on the ground."""
        p = self.pet
        if not moving and p.hop % cycle >= self.HOP_AIR:
            p.hop = self.HOP_AIR                  # resting on the ground, ready for the next hop
            return 0.0
        was, p.hop = p.hop, p.hop + dt
        return self._hop_dist(p.hop, cycle, dist) - self._hop_dist(was, cycle, dist)

    def hop_lift(self):
        """How high a hopping pet is off the ground right now, in sprite pixels (0 while it rests)."""
        p = self.pet
        cycle, high = (self.HOP_RUN_CYCLE, self.HOP_RUN_HIGH) if p.target is not None \
            else (self.HOP_CYCLE, self.HOP_HIGH)
        r = p.hop % cycle
        if r >= self.HOP_AIR:
            return 0.0
        u = r / self.HOP_AIR
        return 4 * u * (1 - u) * high              # a real arc: up fast, hangs, comes down

    def _move(self, dt):
        p = self.pet
        if self.character == "ghost":             # every 7-15 s it fades away and comes back over 1.5 s
            if p.fade_t > 0 or p.vanish_in <= 0:
                p.fade_t += dt
                if p.fade_t >= spg.VANISH_LEN:
                    p.fade_t, p.vanish_in = 0.0, random.uniform(*spg.VANISH_GAP)
            else:
                p.vanish_in -= dt
        if p.jump >= 0:
            p.jump += dt
            if p.jump > .45:
                p.jump = -1.0
        p.surprise -= dt
        p.blink_in -= dt
        if p.blink_in <= 0:
            p.blink, p.blink_in = .14, 2.5 + random.random() * 3
        p.blink -= dt
        hi = max(self.XMIN, self.xmax)            # the stage can shrink (one-line view, resize) while the pet stands
        if not self.XMIN <= p.x <= hi:            # still at a work spot: bring it back inside
            p.x = self.clamp(p.x, self.XMIN, hi)
            if p.easel > 0:
                p.dir = -1 if p.x + 46 > hi else 1
        if p.target is not None:
            p.target = self.clamp(p.target, self.XMIN, hi)
        station = self._station()
        show = station and p.target is None       # step 3: the easel / work spot pops up on the side with room
        if show and p.easel == 0:
            p.dir = -1 if p.x + 46 > self.xmax else 1
            if self.effect != getattr(self, "_spot_effect", None):   # another effect's spot: start from empty
                p.paint = p.done = 0.0
                self._spot_effect = self.effect
        p.easel = self.clamp(p.easel + dt * (4 if show else -5), 0.0, 1.0)
        if p.target is not None:
            d = p.target - p.x
            p.dir = (d > 0) - (d < 0) or p.dir
            step = (self._hop_move(dt, self.HOP_RUN_CYCLE, self.RUN_SPEED * self.HOP_RUN_CYCLE, True)
                    if self._hops() else self.RUN_SPEED * dt)
            if abs(d) <= step:
                p.x, p.target, p.jump, p.pause, p.sp = p.target, None, 0.0, 1.2, 0.0
            else:
                p.x += p.dir * step
                p.phase += step
            return
        if p.glance > 0:
            p.glance -= dt
        if self.mood == "sleep":
            p.sp = 0.0
            return
        if station:
            p.sp = 0.0
            if p.easel < 1 or self.effect == "cook":   # cooking goes on and on
                return
            inten = self.fx_inten
            if p.done > 0:                # admire the finished picture / wall / paper stack, then start over
                p.done -= dt
                if p.done <= 0:
                    p.paint = 0.0
            else:
                p.paint += dt * (.12 + .2 * inten)
                if p.paint >= 1:
                    p.paint, p.done = 1.0, 1.6
            return
        # wandering: the speed eases in and out; turns happen only while standing
        if p.pause > 0:
            p.pause -= dt
            if p.pause <= 0 and p.turn:
                p.dir, p.turn = -p.dir, False
        elif random.random() < .06 * dt:          # every so often it looks your way
            p.glance = p.pause = 1.2
        elif random.random() < .25 * dt:
            p.pause, p.turn = 1 + random.random() * 2, random.random() < .35
        want = 0 if p.pause > 0 else 1
        p.sp += (want - p.sp) * min(1, dt * 4)
        speed = self.WALK_SPEED * (sph.HURRY if self.effect == "trick" and self.fx_step >= 3 else 1)
        dx = (self._hop_move(dt, self.HOP_CYCLE, self.HOP_STEP * (sph.HURRY if speed > self.WALK_SPEED else 1),
                             p.sp >= .5) if self._hops() else speed * p.sp * dt)
        p.x += p.dir * dx
        p.phase += dx
        if p.x <= self.XMIN:
            p.x, p.dir = self.XMIN, 1
        elif p.x >= self.xmax:
            p.x, p.dir = self.xmax, -1

    def _particles(self, dt):
        p = self.pet
        for h in p.hearts:
            h[2] += dt
        p.hearts = [h for h in p.hearts if h[2] < 1.1]
        inten = self.fx_inten
        gy = self.ground
        if self.mood == "busy" and self.fx_step >= 3 and self.effect == "magic" and len(p.sparks) < self.MAX_SPARKS \
                and random.random() < (10 + inten * 22) * dt:
            p.sparks.append([p.x + (random.random() - .5) * 34, gy - 4, 0.0, .9 + random.random() * .6])
        for s in p.sparks:
            s[2] += dt
        p.sparks = [s for s in p.sparks if s[2] < s[3]]
        if self._painting() and p.easel >= 1 and p.target is None and p.done <= 0 and len(p.drops) < self.MAX_DROPS \
                and random.random() < (6 + inten * 10) * dt:
            col = sp.MIRROR - 23 if p.dir < 0 else 23          # the canvas centre column
            x = p.x + (col - 10 + .5) * 2
            p.drops.append([x, gy - 36 + 17, (random.random() * 2 - 1) * 30 + p.dir * 12, -(35 + random.random() * 35),
                            0.0, random.choice(("#31A8FF", "#FF6FA1", "#FFD86B", "#6CC486"))])
        keep = []
        for d in p.drops:
            d[4] += dt
            d[0] += d[2] * dt
            d[1] += d[3] * dt
            d[3] += 160 * dt
            if d[1] < gy + 2 and d[4] < 1.4:
                keep.append(d)
        p.drops = keep
        self._sweets(dt, gy)

    def _sweets(self, dt, gy):
        """Halloween step 2+: a sweet drops behind the pet every few seconds (far more often at step 3),
        bounces and stays on the ground; only the last few are kept, so a short trail follows the pet."""
        p = self.pet
        if self.effect != "trick" or self.mood != "busy" or self.fx_step < 2:
            if p.sweets:
                p.sweets, p.sweet_in = [], 0.0
            return
        p.sweet_in -= dt
        if p.sweet_in <= 0:                       # one drops behind the pet, on the side it just came from
            p.sweets.append([p.x - p.dir * sph.BEHIND, gy - sph.DROP_H, 0.0, random.choice(sph.SWEETS), 0])
            del p.sweets[:-self.MAX_SWEETS]       # the oldest of the trail goes
            p.sweet_in = random.uniform(*sph.DROP_GAP[1 if self.fx_step >= 3 else 0])
        for d in p.sweets:
            if d[2] is None:                      # already lying on the ground
                continue
            d[2] += sph.GRAVITY * dt
            d[1] += d[2] * dt
            if d[1] >= gy:                        # it hit the ground: bounce, then settle
                d[1], d[2], d[4] = gy, d[2] * sph.BOUNCE, d[4] + 1
                if d[4] > 2 or abs(d[2]) < 6:
                    d[2] = None

    def _glide(self, dt):
        if not self.is_line:
            return False
        dragging = self.drag and self.drag["mode"] == "resize"
        goal = self.line_target() if dragging else self.line_width()
        if self.line_disp is None or dragging:
            self.line_disp = goal
            return False
        self.line_disp += (goal - self.line_disp) * min(1, dt * 14)
        if abs(goal - self.line_disp) < .3:
            self.line_disp = goal
            return False
        return True

    # ---------- frame loop ----------
    def _kick(self):
        """Run the next frame soon (something just started moving)."""
        if self.in_frame:                 # a running frame picks its own (fast) next delay
            return
        job = self.jobs.get("frame")
        if job and self.slow:
            self.root.after_cancel(job)
            self.jobs["frame"] = self.root.after(1, self.tick_frame)

    slow = in_frame = False

    def tick_frame(self):
        try:
            self.in_frame = True
            self._run_pending()
            now = time.perf_counter()
            dt = min(now - self.last, .1)
            self.last = now
            self.t += dt
            self._update_mood(now)
            p = self.pet
            pet_on = bool(self.yard_bottom or self.lz)
            if pet_on:
                self._move(dt)
                self._particles(dt)
            gliding = self._glide(dt)
            want = 1.0 if self.hover and not self.is_line else 0.0
            fading = self.view_a != want
            self.view_a = self.clamp(self.view_a + dt * (10 if want else -8), 0.0, 1.0)
            self.render()
            moving = pet_on and (p.target is not None or p.sp > .02 or p.jump >= 0 or p.hearts or p.sparks
                                 or p.drops or self.mood == "busy" or p.blink > 0 or p.surprise > 0
                                 or 0 < p.easel < 1 or p.glance > 0)
            animating = moving or gliding or fading or self.drag is not None or self.hover
            night = pet_on and self.yard_bottom and self.phase == "night"
            delay = self.FAST_MS if animating else self.NIGHT_MS if night else self.IDLE_MS
            if pet_on and self._restless():
                delay = min(delay, self.NIGHT_MS)  # the candle keeps flickering / the ghost keeps bobbing
        except Exception:
            import traceback
            traceback.print_exc()
            delay = self.IDLE_MS
        self.in_frame, self.slow = False, delay > self.FAST_MS
        self.jobs["frame"] = self.root.after(delay, self.tick_frame)
