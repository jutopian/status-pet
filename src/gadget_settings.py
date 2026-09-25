"""Settings file (settings.json) load/save, and where the gadget first appears on screen.

Split out of status_pet.Gadget (which mixes this in) so that file doesn't have to hold
every concern. Gadget sets self._settings_path, self.MARGIN and self.SIZE_BASE (copied from the
module's own constants at class-definition time, except _settings_path which __init__ reads live
so a test can still redirect SETTINGS_PATH before constructing Gadget).
"""
import ctypes
import json

import gfx
import i18n


class GadgetSettingsMixin:
    def _load_settings(self):
        try:
            with open(self._settings_path, encoding="utf-8") as f:
                data = json.load(f)
            return data if isinstance(data, dict) else {}
        except (OSError, ValueError):
            return {}

    def _save_settings(self):
        data = {"x": self.win.x, "y": self.win.y, "w": round(self.W), "yard_h": round(self.YH),
                "view": self.view.get(), "line_w": self.line_w,
                "line_pad": [round(v, 1) for v in self.line_pad], "locked": self.locked, "language": i18n.lang, "topmost": self.topmost.get(),
                "ram_pct": self.ram_as_pct.get(), "show_pet": self.show_pet.get(),
                "transparent": self.transparent.get(), "status_size": self.status_size.get(),
                "settings_off": list(self.settings_off) if self.settings_off else None,
                "tracked": sorted(self.tracked), "custom_apps": self.custom_apps, "size_base": self.SIZE_BASE,
                "character": self.character, "app_hats": self.app_hats, "default_hat": self.default_hat,
                "app_colors": self.app_colors,
                "default_effect": self.default_effect, "app_effects": self.app_effects,
                "effect_range": self.effect_range}
        try:
            with open(self._settings_path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2)
        except OSError:
            pass

    # ---------- window placement ----------
    def _default_pos(self):
        left, top, right, _ = gfx.work_area(*gfx.cursor_pos())
        return int(right - (self.gw() + self.MARGIN + 14) * self.S), int(top + 14 * self.S)

    @staticmethod
    def _on_screen(x, y):
        gsm = ctypes.windll.user32.GetSystemMetrics
        vx, vy, vw, vh = gsm(76), gsm(77), gsm(78), gsm(79)
        return vx - 20 <= x < vx + vw - 80 and vy - 20 <= y < vy + vh - 80

    def _place_initial(self):
        x, y = self.settings.get("x"), self.settings.get("y")
        if not isinstance(x, int) or not isinstance(y, int) or not self._on_screen(x, y):
            x, y = self._default_pos()
        self.win.x, self.win.y = x, y
