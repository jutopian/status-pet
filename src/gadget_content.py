"""App list, hat and busy-effect bookkeeping for the gadget (status_pet.Gadget mixes this in).

Everything here reads/writes settings-shaped state (self.custom_apps, self.app_hats, self.effect_range,
...) and calls self._save_settings() / self._sample_apps(); none of it touches Tk, win32 or drawing.
C, EFFECT_RANGE, RANGE_GAP, METERS and clamp are exposed by Gadget as class attributes (copied from its
own module constants) since none of them are ever monkeypatched by a test.
"""
import hats as hatlib


class GadgetContentMixin:
    def all_apps(self):
        """(id, name, color) for every app added with "+ Add running app" (color: the user's pick, else grey)."""
        return [(a["id"], a["name"], self.app_colors.get(a["id"], self.C["label"])) for a in self.custom_apps]

    def set_app_color(self, app_id, color):
        self.app_colors[app_id] = color
        self._after_color()

    def reset_app_color(self, app_id):
        self.app_colors.pop(app_id, None)
        self._after_color()

    def _after_color(self):
        self._save_settings()
        self._sample_apps()               # the gadget's app rows take the new color
        self.base_key = None

    def set_tracked(self, app_id, on):
        if on:
            self.tracked.add(app_id)
        else:
            self.tracked.discard(app_id)
        self._save_settings()
        self._sample_apps()
        self.base_key = None

    def remove_app(self, app_id):
        """× on an app: it leaves the list (it can be added again while it runs)."""
        self.custom_apps = [a for a in self.custom_apps if a["id"] != app_id]
        self.tracked.discard(app_id)
        self.app_hats.pop(app_id, None)
        self.app_effects.pop(app_id, None)
        self.app_colors.pop(app_id, None)
        self._save_settings()
        self._sample_apps()
        self.base_key = None

    def clear_apps(self):
        """Apps tab "Clear app list": an empty list (the programs themselves are untouched)."""
        self.custom_apps, self.tracked = [], set()
        self.app_hats, self.app_effects, self.app_colors = {}, {}, {}
        self._save_settings()
        self._sample_apps()
        self.base_key = None

    # ---------- hats (PNG files in hats/, see hats.py) ----------
    def reload_hats(self):
        """Reads the hats folder: at start and after a hat is added or removed."""
        self.hats, self.hat_problems = hatlib.load(self.root, self.hat_dir)
        self._pet_cache.clear()

    def app_hat_id(self, app_id):
        """The app's hat: the user's pick, else the Default hat. None = no hat."""
        h = self.app_hats.get(app_id, hatlib.FOLLOW)
        if h == hatlib.FOLLOW:
            return self.default_hat_id()
        return h if h in self.hats else None

    def follows_default(self, app_id):
        """True when the app wears whatever the Default row says (no pick of its own)."""
        return self.app_hats.get(app_id, hatlib.FOLLOW) == hatlib.FOLLOW

    def default_hat_id(self):
        return self.default_hat if self.default_hat in self.hats else None

    def set_app_hat(self, app_id, hat_id):
        """A pick is kept even if it equals the Default hat, so it doesn't change when Default does."""
        if hat_id == hatlib.FOLLOW:
            self.app_hats.pop(app_id, None)       # back to following Default
        else:
            self.app_hats[app_id] = hat_id        # None (saved as null) = no hat
        self._save_settings()

    def reset_all_hats(self):
        """Apps tab "Reset hats & effects": every app back to following the Default hat and effect."""
        self.app_hats, self.app_effects = {}, {}
        self._save_settings()
        self._update_effect()

    def reset_app_hat(self, app_id):
        """↺: back to following the Default hat."""
        self.app_hats.pop(app_id, None)
        self._save_settings()

    def set_default_hat(self, hat_id):
        self.default_hat = hat_id
        self._save_settings()

    def worn_hat(self):
        """The busiest tracked app's hat; the Default hat while none of them runs."""
        return self.app_hat_id(self.hat_app) if self.hat_app else self.default_hat_id()

    # ---------- busy effects (Default in the Effects tab, one per app in the Apps tab) ----------
    def fit_range(self, lo, hi):
        """-> [lo, hi] on steps of 5 inside 0..100, at least RANGE_GAP apart."""
        lo = round(self.clamp(lo, 0, 100 - self.RANGE_GAP) / 5) * 5
        hi = round(self.clamp(hi, 0, 100) / 5) * 5
        return [lo, max(hi, lo + self.RANGE_GAP)]

    def _read_ranges(self, st):
        """Saved "effect_range" {meter: [lo, hi]}; settings saved with the old single "Start at" slider keep
        their old step 1 and step 3 (start, and 70% of the way from it to 100)."""
        fr = st.get("effect_range") if isinstance(st.get("effect_range"), dict) else {}
        fs = st.get("effect_start") if isinstance(st.get("effect_start"), dict) else {}
        out = {}
        for m in self.METERS:
            v = fr.get(m)
            if isinstance(v, list) and len(v) == 2 and all(isinstance(x, (int, float)) for x in v):
                out[m] = self.fit_range(*v)
            elif isinstance(fs.get(m), (int, float)):
                out[m] = self.fit_range(fs[m], fs[m] + .7 * (100 - fs[m]))
            else:
                out[m] = list(self.EFFECT_RANGE)
        return out

    def effect_steps(self, meter):
        """Where steps 1, 2 and 3 start for one meter (%): the range's start, middle and end (40, 75 -> 40, 58, 75)."""
        lo, hi = self.effect_range[meter]
        return [lo, round((lo + hi) / 2), hi]

    def app_effect(self, app_id):
        e = self.app_effects.get(app_id, hatlib.FOLLOW)
        return self.default_effect if e == hatlib.FOLLOW else e

    def follows_default_effect(self, app_id):
        return self.app_effects.get(app_id, hatlib.FOLLOW) == hatlib.FOLLOW

    def set_app_effect(self, app_id, effect):
        """An effect, or hatlib.FOLLOW (stored as "no pick")."""
        if effect == hatlib.FOLLOW:
            self.app_effects.pop(app_id, None)
        else:
            self.app_effects[app_id] = effect
        self._after_effect()

    def reset_app_effect(self, app_id):
        self.app_effects.pop(app_id, None)
        self._after_effect()

    def set_default_effect(self, effect):
        self.default_effect = effect
        self._after_effect()

    def set_effect_range(self, meter, lo, hi):
        self.effect_range[meter] = self.fit_range(lo, hi)
        self._after_effect()

    def reset_effects(self):
        """Effects tab "Reset effect settings": Magic as the Default, every meter on 40-75%."""
        self.default_effect = "magic"
        self.effect_range = {m: list(self.EFFECT_RANGE) for m in self.METERS}
        self._after_effect()

    def _after_effect(self):
        self._save_settings()
        self._update_effect()

    def _update_effect(self):
        """Which effect plays (the busiest tracked app's, else the Default) and its step: the highest step any
        meter has reached (0 = none). fx_inten (0..1) grows past step 3 and speeds the effect up."""
        step, inten = 0, 0.0
        for m, v in zip(self.METERS, (self.cpu or 0, self.gpu or 0, self.ram_pct or 0)):
            at = self.effect_steps(m)
            n = sum(v >= a for a in at)
            step = max(step, n)
            if n == 3:
                inten = max(inten, (v - at[2]) / max(1, 100 - at[2]))
        self.fx_step, self.fx_inten = step, min(1.0, inten)
        self.effect = self.app_effect(self.hat_app) if self.hat_app else self.default_effect
