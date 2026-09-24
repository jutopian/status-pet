"""Drives the Settings window OFF SCREEN and reports errors (nothing appears on the desktop).

Uses a throwaway settings file and a throwaway hats folder copy, so your own files are untouched.
"""
import ctypes, importlib.machinery, importlib.util, os, shutil, sys, tempfile, time, traceback

OUT = os.path.dirname(os.path.abspath(__file__))
PROJECT = os.path.dirname(OUT)
sys.path.insert(0, PROJECT)
ctypes.windll.shcore.SetProcessDpiAwareness(1)
import gfx                                           # noqa: E402

OFF = (-9000, -9000, -6000, -6000)                   # a "monitor" nobody can see
gfx.work_area = lambda x, y: OFF
loader = importlib.machinery.SourceFileLoader("sgp", os.path.join(PROJECT, "status_pet.pyw"))
spec = importlib.util.spec_from_loader("sgp", loader)
sgp = importlib.util.module_from_spec(spec)
loader.exec_module(sgp)
import settings_ui                                   # noqa: E402


def _no_tray(*a, **k):
    raise OSError("no tray icon in tests")


sgp.TrayIcon = _no_tray                              # keep your system tray untouched
sgp.UpdateCheck.check = lambda self, min_gap=0: None # no internet in tests; `latest` is set by hand

tmp = tempfile.mkdtemp(prefix="sg_settings_test_")
sgp.SETTINGS_PATH = os.path.join(tmp, "settings.json")
with open(sgp.SETTINGS_PATH, "w") as f:
    f.write('{"status_size": 105, "tracked": ["old_app"], "app_hats": {"old_app": "beret"}}')   # old-style file:
                                                     # 100%, and an app that is not in the list is dropped
shutil.copytree(os.path.join(PROJECT, "hats"), os.path.join(tmp, "hats"))
with open(os.path.join(tmp, "hats", "party_hat.png"), "wb") as f:
    f.write(b"not a png")                            # broken file: must be skipped with a warning

errors = []
_orig_init = sgp.Gadget.reload_hats


def step(name, fn):
    try:
        fn()
        g.root.update()
        print("ok  ", name)
    except Exception:
        errors.append(name)
        print("FAIL", name)
        traceback.print_exc()


sgp.Gadget.reload_hats = lambda self: (setattr(self, "hat_dir", os.path.join(tmp, "hats")), _orig_init(self))
g = sgp.Gadget()
g.poll_hover = lambda: None
g.win.move(-8000, -8000)
apps = {}
g.app_reader.sample = lambda defs: {a: [{"cpu": c, "ram_gb": 1.0}] for a, c in apps.items() if a in defs}
print("status size after migration:", g.status_size.get(), "sz:", round(g.sz, 3))
assert not g.tracked and not g.app_hats, ("an app not in the list should be dropped", g.tracked, g.app_hats)
SAMPLE = ("alpha.exe", "beta.exe", "gamma.exe", "delta.exe")   # sample apps, as if added with "+ Add running app"
ALPHA, BETA, GAMMA, DELTA = ("custom:" + e[:-4] for e in SAMPLE)
for e in SAMPLE:
    g._add_app(e)
print("hats:", list(g.hats), "problems:", g.hat_problems)

step("open settings", g.open_settings)
ui = g.ui
print("settings at", ui.win.winfo_x(), ui.win.winfo_y(), "size", ui.win.winfo_reqwidth(), ui.win.winfo_reqheight())
for tab in ("general", "pet", "items", "effects", "apps"):
    step("tab " + tab, lambda t=tab: ui._set_tab(t))
step("usage tick", ui._tick_usage)
print("usage:", ui.usage_val)
step("apps: open Alpha picker", lambda: ui._toggle_picker(ALPHA))
step("apps: set Alpha straw", lambda: ui._set_hat(ALPHA, "straw_hat"))
step("apps: Alpha running -> wears straw", lambda: (apps.update({ALPHA: 50}), g._sample_apps(), g.render()))
print("worn:", g.worn_hat())
step("apps: back to following Default", lambda: ui._set_hat(ALPHA, "@default"))
print("worn after reset:", g.worn_hat(), "saved app_hats:", g.app_hats)
step("items: Default hat = beret", lambda: (ui._set_tab("items"), g.set_default_hat("beret"), ui._set_tab("apps")))
step("no app -> default beret", lambda: (apps.clear(), g._sample_apps(), g.render()))
print("worn with no app:", g.worn_hat())
step("Beta follows Default", lambda: (apps.update({BETA: 30}), g._sample_apps()))
print("Beta wears (Default = beret):", g.worn_hat())
step("Beta: pick no hat, then Default straw", lambda: (g.set_app_hat(BETA, None), g.set_default_hat("straw_hat")))
print("Beta wears after explicit no hat:", g.worn_hat())
step("Beta: reset follows Default again", lambda: g.reset_app_hat(BETA))
print("Beta wears after reset:", g.worn_hat(), "follows default:", g.follows_default(BETA))
apps.clear()
g.set_default_hat("beret")
step("add a custom app", lambda: g._add_app("krita.exe"))
step("remove the custom app", lambda: ui._drop_app("custom:krita", "Krita"))
print("custom apps after remove:", [a["id"] for a in g.custom_apps], "tracked has it:", "custom:krita" in g.tracked)
menu_seen = []                                       # the menu is never shown: tk_popup only records its entries
sgp.tk.Menu.tk_popup = lambda self, x, y: menu_seen.append(
    [self.entrycget(i, "label") for i in range(self.index("end") + 1) if self.type(i) == "command"])
step("add-app menu: running programs not in the list", lambda: (
     setattr(g.app_reader, "exe_names", {"krita.exe", "alpha.exe", "svchost.exe"}), g._add_app_menu(ui.body)))
print("add-app menu entries:", menu_seen[-1] if menu_seen else None)
assert menu_seen and menu_seen[-1] == ["krita"], menu_seen
step("Same as Default switch on/off (Alpha)", lambda: (ui._toggle_picker(ALPHA), ui._toggle_follow(ALPHA, False)))
print("Alpha follows:", g.follows_default(ALPHA))
step("switch off again", lambda: ui._toggle_follow(ALPHA, True))
print("Alpha follows after off:", g.follows_default(ALPHA), "wears:", g.app_hat_id(ALPHA))
step("Gamma switch off keeps the Default hat as its own", lambda: (ui._toggle_picker(GAMMA), ui._toggle_follow(GAMMA, True)))
print("Gamma follows:", g.follows_default(GAMMA), "own pick:", g.app_hats.get(GAMMA, "-"))
step("apps: uncheck Beta (row stays)", lambda: g.set_tracked(BETA, False) or ui.refresh())
step("apps: more / fewer", lambda: (ui._toggle_more(), ui._toggle_more()))
step("apps: Reset hats (confirm)", lambda: (g.set_app_hat(GAMMA, "beret"), ui._ask_reset(), g.reset_all_hats(),
                                           ui._cancel()))
print("app hats after Reset hats:", g.app_hats)
step("items tab", lambda: ui._set_tab("items"))
step("items: many hats (pages)", lambda: [shutil.copyfile(os.path.join(tmp, "hats", "beret.png"), os.path.join(tmp, "hats", f"x{i}.png")) for i in range(8)]
     and (g.reload_hats(), ui.refresh(), setattr(ui, "pages", {"items": 1}), ui.refresh()))
step("items: click straw = Default hat", lambda: (ui._set_tab("items"), g.set_default_hat("straw_hat"), ui.refresh()))
print("default hat:", g.default_hat_id())
step("apps: color picker for Alpha + pick blue", lambda: (ui._set_tab("apps"), ui._toggle_picker("color:" + ALPHA),
                                                        g.set_app_color(ALPHA, "#31A8FF"), ui.refresh()))
print("Alpha color:", [a[2] for a in g.all_apps() if a[0] == ALPHA])
step("apps: color reset", lambda: (g.reset_app_color(ALPHA), ui.refresh()))
print("Alpha color after reset:", [a[2] for a in g.all_apps() if a[0] == ALPHA])
step("apps: Clear app list", lambda: (ui._set_tab("apps"), g.set_app_hat(ALPHA, "beret"), ui._ask_clear(), ui._clear_apps()))
print("after clear -> apps:", len(g.all_apps()), "tracked:", len(g.tracked), "app hats:", g.app_hats)
assert not g.all_apps() and not g.tracked and not g.app_hats
step("sample apps back via + Add running app", lambda: [g._add_app(e) for e in SAMPLE])
g.cpu_reader.sample = lambda: g.cpu or 0                # from here the checks set the load themselves
g.gpu_reader.sample = lambda: 0
sgp.read_ram = lambda: (8.0, 64.0)
g.gpu, g.ram_pct = 0, 12.5


def preview_at(effect, t):
    """The Effects tab preview, pointed at an effect for t seconds (steps 1-3 go by time)."""
    ui._fx_point(effect)
    ui.fx["t0"] = time.perf_counter() - t
    ui._fx_frame()


print("steps at 40-75:", g.effect_steps("cpu"), "| at 30-50:", (g.set_effect_range("gpu", 30, 50), g.effect_steps("gpu"))[1])
print("fit_range(95, 90):", g.fit_range(95, 90), "| old start 50 ->", g._read_ranges({"effect_start": {"cpu": 50}})["cpu"])
g.set_effect_range("gpu", 40, 75)
step("effects tab: preview Magic steps 1-3", lambda: (ui._set_tab("effects"), [preview_at("magic", t) for t in (.5, 1.8, 3)]))
step("effects tab: preview Painting steps 1-3", lambda: [preview_at("painting", t) for t in (.5, 1.8, 3, 7)])
step("effects tab: point at None, then leave", lambda: (preview_at("none", 1), ui._fx_point(None, "none")))
step("effects tab: Default = Painting", lambda: (g.set_default_effect("painting"), ui.refresh()))
print("Beta follows Default:", g.app_effect(BETA))
step("effects tab: CPU range 30-60", lambda: (g.set_effect_range("cpu", 30, 60), ui.refresh()))
print("cpu steps now:", g.effect_steps("cpu"))
step("apps: Alpha list, Effect side", lambda: (ui._set_tab("apps"), ui._toggle_picker(ALPHA), ui._set_pick_mode("effect")))
step("apps: Alpha -> Painting, then ↺", lambda: (ui._set_effect(ALPHA, "painting"), g.reset_app_effect(ALPHA),
                                                ui.refresh()))
print("Alpha effect after ↺:", g.app_effect(ALPHA), "saved:", g.app_effects)
step("apps: Beta Same as Default off, then on", lambda: (ui._toggle_picker(BETA), ui._toggle_follow_effect(BETA, True),
                                                        ui._toggle_follow_effect(BETA, False)))
print("Beta follows after on:", g.follows_default_effect(BETA), "saved:", g.app_effects)
step("apps: Gamma picks None (button without an effect)", lambda: ui._set_effect(GAMMA, "none"))
g.set_app_effect(DELTA, "painting")
g.set_effect_range("cpu", 50, 85)
for v, label in ((40, "calm"), (55, "step 1: brush"), (75, "step 2: palette"), (92, "step 3: easel")):
    step(f"gadget Delta (Painting) {v}%: {label}", lambda v=v: (setattr(g, "cpu", v), apps.update({DELTA: v}), g._sample_apps(),
                                                        g._update_mood(time.perf_counter()), g.render()))
    print(f"  cpu {v}: step {g.fx_step} effect {g.effect} mood {g.mood} easel {g._painting()}")
apps.clear()
for eff in ("build", "cook", "comp"):
    step(f"effects tab: preview {eff} steps 1-3", lambda eff=eff: (ui._set_tab("effects"),
                                                                 [preview_at(eff, t) for t in (.5, 1.8, 2.6, 3.5, 7)]))
    for ch in ("slime", "cat"):
        g.character = ch
        for v in (55, 75, 92):
            def at(v=v, eff=eff):
                g.set_default_effect(eff)
                g.cpu = v
                g._sample_apps()
                g._update_mood(time.perf_counter())
                for _ in range(6):
                    g._move(.3)
                    g._particles(.3)
                    g.t += .3
                g.render()
            step(f"gadget {eff} {ch} cpu {v}%", at)
            print(f"  {eff} {ch} cpu {v}: step {g.fx_step} station {g._station()} spot {round(g.pet.easel, 2)}"
                  f" progress {round(g.pet.paint, 2)}")
g.character = "slime"

# Halloween ("trick or treat") - lantern, sweets, bats. Everything travels with the pet: no work spot.
step("effects tab: preview trick steps 1-3",
     lambda: (ui._set_tab("effects"), [preview_at("trick", t) for t in (.5, 1.8, 3, 5)]))
for ch in ("slime", "cat", "pumpkin", "ghost"):
    g.character = ch
    for v in (55, 75, 92):
        def at(v=v):
            g.set_default_effect("trick")
            g.cpu = v
            g._sample_apps()
            g._update_mood(time.perf_counter())
            for _ in range(20):
                g._move(.25)
                g._particles(.25)
                g.t += .25
            g.render()
        step(f"gadget trick {ch} cpu {v}%", at)
        landed = [d for d in g.pet.sweets if d[2] is None]
        print(f"  trick {ch} cpu {v}: step {g.fx_step} station {g._station()} sweets {len(g.pet.sweets)}"
              f" landed {len(landed)}")


def trick_checks():
    import sprites_halloween as sph
    g.character, g.pet.sweets, g.pet.sweet_in = "slime", [], 0.0
    g.set_default_effect("trick")
    g.cpu = 95                                         # step 3: it hurries, sweats and spills sweets
    g._sample_apps()
    g._update_mood(time.perf_counter())
    x0 = g.pet.x
    for _ in range(400):                               # 10 seconds
        g._move(.025)
        g._particles(.025)
        g.t += .025
    landed = [d for d in g.pet.sweets if d[2] is None]
    assert 3 <= len(g.pet.sweets) <= sgp.MAX_SWEETS, f"sweets: {len(g.pet.sweets)}"   # about one a second
    assert landed and all(round(d[1]) == round(g.ground) for d in landed), "sweets should rest on the ground"
    assert len({d[3] for d in g.pet.sweets}) > 1, "the sweets should not all be the same color"
    assert not g._station() and abs(g.pet.x - x0) > 0, "at step 3 the pet must keep wandering"
    back, front = sph.bats(g.t)
    assert len(back) + len(front) == 5, f"bats: {len(back)}/{len(front)}"
    lits = {sph.lantern_lit(t / 10) for t in range(60)}
    assert min(lits) >= .3 and max(lits) <= 1 and len(lits) > 3, f"lantern flicker: {sorted(lits)}"
    g.cpu = 20                                         # the effect stops: the trail is cleared
    g._sample_apps()
    g._update_mood(time.perf_counter())
    g._particles(.1)
    assert not g.pet.sweets, "the trail should go when the effect stops"
    print("  trick: bats", len(back), "behind /", len(front), "in front | lantern", round(min(lits), 2), "-",
          round(max(lits), 2), "| moved", round(abs(g.pet.x - x0)), "px in 10 s")
step("trick: sweets land and trail, bats split, pet keeps moving", trick_checks)


def effect_pages():
    """The Effects tab pages its tiles (6 to a page) instead of growing a row, like the Items tab."""
    ui._set_tab("effects")
    ui.pages.pop("effect", None)
    g.set_default_effect("magic")
    ui.refresh()
    assert ui.pages["effect"] == 0, "Magic is on the first page"
    ui.pages["effect"] = 1                             # turn to the second page: Halloween is there
    ui.refresh()
    ui.pages.pop("effect", None)
    g.set_default_effect("trick")
    ui.refresh()
    assert ui.pages["effect"] == 1, "it should open on the page the Default effect is on"
    print("  effect pages:", -(-len(g.EFFECTS) // ((5 - 2) * 2)), "| Default trick on page", ui.pages["effect"] + 1)
step("effects tab: pages (‹ ›) instead of a third row", effect_pages)
g.character = "slime"
g.set_default_effect("magic")


def far_then_line():                                   # cooking at the far right, then the one-line view
    g.set_default_effect("cook")
    g.cpu = 92
    g._sample_apps()
    g._update_mood(time.perf_counter())
    g.pet.x, g.pet.target = g.xmax, None
    for _ in range(4):
        g._move(.3)
    far = g.pet.x
    g.view.set("line")
    g._on_option()
    g._move(.05)
    g.render()
    print(f"  far x {far:.0f} -> one-line x {g.pet.x:.0f} (stage right edge {g.xmax:.0f}) inside: {g.pet.x <= g.xmax}")
    g.view.set("full")
    g._on_option()


step("gadget: cooking far right, then one-line view", far_then_line)
g.set_default_effect("magic")
step("effects: reset + apps: Reset hats & effects", lambda: (g.reset_effects(), g.reset_all_hats(), ui._set_pick_mode("hat")))
print("after resets:", g.default_effect, g.effect_range, g.app_effects)
step("pet tab + pick Siamese", lambda: (ui._set_tab("pet"), ui._pick_char("cat")))
g.set_app_effect(DELTA, "painting")
for label, fn in (("cat walking + straw", lambda: (apps.update({BETA: 30}), g.set_default_hat("straw_hat"), g._sample_apps())),
                  ("cat busy Alpha (wand)", lambda: (setattr(g, "cpu", 95), apps.update({ALPHA: 95}), g._sample_apps(),
                                                     setattr(g, "mood", "busy"))),
                  ("cat Delta step 2 (palette)", lambda: (apps.clear(), setattr(g, "cpu", 75), apps.update({DELTA: 75}),
                                                          g._sample_apps(), setattr(g, "mood", "busy"))),
                  ("cat sleeping", lambda: (apps.clear(), setattr(g, "cpu", 1), g._sample_apps(), setattr(g, "load", 1),
                                            setattr(g, "mood", "sleep")))):
    step(label, lambda f=fn: (f(), g.render(), [g.pet.__setattr__("dir", d) or g.render() for d in (1, -1)]))
print("worn hat on cat:", g.worn_hat(), "cache has cat poses:", any(k[1] == "cat" for k in g._pet_cache if k[0] == "pet"))
step("effects preview with the cat (magic 3, painting 2 and 3)",
     lambda: (ui._set_tab("effects"), preview_at("magic", 3), preview_at("painting", 1.8), preview_at("painting", 7)))
step("items tab with the cat (preview)", lambda: ui._set_tab("items"))
step("pet tab + pick Jack-o'-lantern", lambda: (ui._set_tab("pet"), ui._pick_char("pumpkin")))
for label, fn in (("pumpkin hopping + crown", lambda: (apps.clear(), setattr(g, "cpu", 20), setattr(g, "mood", "walk"),
                                                       g.set_default_hat("crown"), g._sample_apps())),
                  ("pumpkin busy Alpha (wand)", lambda: (setattr(g, "cpu", 95), apps.update({ALPHA: 95}),
                                                         g._sample_apps(), setattr(g, "mood", "busy"))),
                  ("pumpkin cooking step 3", lambda: (apps.clear(), setattr(g, "cpu", 95), g.set_default_effect("cook"),
                                                      g._sample_apps(), setattr(g, "mood", "busy"))),
                  ("pumpkin sleeping", lambda: (setattr(g, "cpu", 1), g.set_default_effect("magic"), g._sample_apps(),
                                                setattr(g, "load", 1), setattr(g, "mood", "sleep")))):
    step(label, lambda f=fn: (f(), g.render(), [g.pet.__setattr__("dir", d) or g.render() for d in (1, -1)]))

def pumpkin_checks():
    import sprites_pumpkin as spp                       # the hat always covers the stem
    over = g.pet_cells("crown")[(5, -1)]                # a stem pixel, under the crown
    assert over != spp.PAL["s"], f"the crown does not cover the stem: {over}"
    dark = {g.pet_cells(None, expr="sleep")[(c, r)] for c, r in spp.FACES["sleep"]["dark"]}
    assert dark == {spp.HOLE}, f"asleep the carving should be dark: {dark}"
    lit = {spp.glow_level(t / 10) for t in range(60)}   # the candle only dips, it never goes out
    assert min(lit) >= .22 and max(lit) <= 1, f"glow out of range: {min(lit)}-{max(lit)}"
    g.mood, g.pet.target = "walk", None
    g.pet.x, g.pet.sp, g.pet.hop, air = 80.0, 1.0, 0.0, []
    for _ in range(120):                                # 2 seconds of hopping: on the ground between hops
        g._move(1 / 60)
        air.append(g.hop_lift())
    assert max(air) > 1 and min(air) == 0, f"the hop has no arc: {min(air)}-{max(air)}"
    assert sgp.XMIN <= g.pet.x <= g.xmax, f"hopped off the stage: {g.pet.x}"
    print("  crown over stem:", over, "| hop height:", round(max(air), 1), "px | moved:", round(g.pet.x - 80, 1), "px/2s")
step("pumpkin: hat over the stem, dark when asleep, hop arc", pumpkin_checks)
step("effects preview with the pumpkin (magic 3, cook 3)",
     lambda: (ui._set_tab("effects"), preview_at("magic", 3), preview_at("cook", 7)))
step("items tab with the pumpkin (preview)", lambda: ui._set_tab("items"))
step("pet tab + pick Ghost", lambda: (ui._set_tab("pet"), ui._pick_char("ghost")))
for label, fn in (("ghost drifting + crown", lambda: (apps.clear(), setattr(g, "cpu", 20), setattr(g, "mood", "walk"),
                                                      g.set_default_hat("crown"), g._sample_apps())),
                  ("ghost busy Alpha (floating wand)", lambda: (setattr(g, "cpu", 95), apps.update({ALPHA: 95}),
                                                                g._sample_apps(), setattr(g, "mood", "busy"))),
                  ("ghost building step 2 (floating hammer)", lambda: (apps.clear(), setattr(g, "cpu", 75),
                                                                       g.set_default_effect("build"), g._sample_apps(),
                                                                       setattr(g, "mood", "busy"))),
                  ("ghost mid-vanish", lambda: (setattr(g.pet, "fade_t", 0.75), g.set_default_effect("magic"),
                                                g._sample_apps())),
                  ("ghost sleeping", lambda: (setattr(g.pet, "fade_t", 0.0), setattr(g, "cpu", 1), g._sample_apps(),
                                              setattr(g, "load", 1), setattr(g, "mood", "sleep")))):
    step(label, lambda f=fn: (f(), g.render(), [g.pet.__setattr__("dir", d) or g.render() for d in (1, -1)]))

def ghost_checks():
    import sprites_ghost as spg
    a_top, a_hem = spg.row_alpha(0), spg.row_alpha(spg.ROWS - 1)
    assert 1 > a_top > a_hem >= .12, f"the hem should be the most see-through: {a_top} -> {a_hem}"
    assert spg.face_alpha() > a_hem, "the face must stay readable"
    deep = max(spg.vanish_dim(t / 20) for t in range(int(spg.VANISH_LEN * 20)))
    assert .8 <= deep <= .9 and spg.vanish_dim(0) == 0 and spg.vanish_dim(spg.VANISH_LEN) == 0, f"vanish: {deep}"
    g.mood, g.pet.target, g.pet.fade_t = "walk", None, 0.0
    g.pet.vanish_in, seen = 0.0, []
    for _ in range(180):                                # 3 seconds: it fades away and comes all the way back
        g._move(1 / 60)
        seen.append(spg.vanish_dim(g.pet.fade_t))
    assert max(seen) > .8 and seen[-1] == 0 and g.pet.vanish_in > 0, f"the vanish did not finish: {max(seen)}"
    bobs = {spg.bob(t / 10) for t in range(100)}
    assert len(bobs) > 1 and min(bobs) < 0 < max(bobs), f"the ghost should bob up and down: {bobs}"
    print("  ghost alpha top/hem:", round(a_top, 2), round(a_hem, 2), "| deepest vanish:", round(deep, 2),
          "| bob rows:", sorted(bobs))
step("ghost: fades to the hem, vanishes and comes back, bobs", ghost_checks)
step("effects preview with the ghost (magic 3, build 2)",
     lambda: (ui._set_tab("effects"), preview_at("magic", 3), preview_at("build", 1.8)))
step("items tab with the ghost (preview)", lambda: ui._set_tab("items"))
step("pet tab back to slime", lambda: (ui._set_tab("pet"), ui._pick_char("slime")))
step("general: switch show pet", lambda: (ui._set_tab("general"),))
step("escape closes", lambda: (ui._escape(), g.root.update()))
print("closed:", g.ui is None)
def line_ends():                                       # drag either end of the one-line bar
    g.set_view("line")
    apps.update({ALPHA: 40})                           # an app on the bar, so there is something to shorten
    g._sample_apps()
    g.line_pad, g.line_w, g.line_disp = [0.0, 0.0], None, None
    g.render()
    num = lambda: g.win.x + (sgp.MARGIN + g.line_pad[0] + sgp.LINE_L) * g.S    # where the numbers start on screen
    right = lambda: g.win.x + (sgp.MARGIN + g.gw()) * g.S
    drag = lambda side, dx: g._line_resize({"side": side, "wx": g.win.x, "wy": g.win.y, "LW": g.line_target(),
                                            "pad": list(g.line_pad), "GW": g.gw()}, dx * g.S)
    near = lambda a, b: abs(a - b) <= 1
    n0, r0, c0 = num(), right(), g.line_target()
    drag("l", -60)
    assert near(g.line_pad[0], 60) and near(num(), n0) and near(right(), r0), ("left out", g.line_pad, num(), n0)
    drag("r", 40)
    assert near(g.line_pad[1], 40) and near(num(), n0), ("right out", g.line_pad)
    drag("r", -40)
    assert g.line_pad[1] == 0 and near(g.line_target(), c0), ("right back", g.line_pad)
    r1 = right()
    drag("l", 90)                                      # past the space: the numbers get shorter, right end stays
    print(f"  numbers {c0:.0f} wide (shortest {g.line_min_w():.0f}) -> {g.line_target():.0f} after pushing the left end in")
    assert g.line_pad[0] == 0 and g.line_target() <= c0 and near(right(), r1), ("left in", g.line_pad, right(), r1)
    drag("l", -5000)                                   # never wider than the screen
    assert g.gw() <= (OFF[2] - OFF[0]) / g.S, ("cap", g.gw())
    assert g._in_grip(5, g.lz + 10) == "l" and g._in_grip(g.gw() - 5, g.lz + 10) == "r"
    assert g._in_grip(g.gw() / 2, g.lz + 10) is False
    for hg in ("l", "r"):
        g.hover_grip = hg
        g.base_key = None
        g.render()
    g.hover_grip = False
    g._save_settings()
    with open(sgp.SETTINGS_PATH) as f:
        assert f.read().count('"line_pad"') == 1
    print(f"  line_pad {[round(v) for v in g.line_pad]}, bar {g.gw():.0f} wide, pet stage right edge {g.xmax:.0f}")
    g._reset_size()
    assert g.line_pad == [0.0, 0.0]
    apps.clear()
    g._sample_apps()
    g.set_view("full")


step("one-line view: drag either end", line_ends)


def lock():                                            # click-through, lock drawn before the numbers
    ex = lambda w: ctypes.windll.user32.GetWindowLongPtrW(w.hwnd, gfx.GWL_EXSTYLE) & gfx.WS_EX_TRANSPARENT
    g.hover = True
    g.toggle_lock()
    assert g.locked and ex(g.win) and ex(g.pop) and not g.hover, ("lock", g.locked, ex(g.win), g.hover)
    for v in ("full", "compact", "line"):
        g.set_view(v)
        g.render()
    g.render()
    assert not g.pop.visible
    with open(sgp.SETTINGS_PATH) as f:
        assert '"locked": true' in f.read()
    g.toggle_lock()
    assert not g.locked and not ex(g.win) and not ex(g.pop)
    g.set_view("full")


step("lock / unlock", lock)


def korean():                                          # Korean and back: every tab and menu in Korean
    g.open_settings()
    g.set_language("ko")
    assert sgp.i18n.lang == "ko" and g.menu.entrycget(0, "label") == "항상 위에", g.menu.entrycget(0, "label")
    assert g.tf_ui.cget("family") == "Malgun Gothic" and g.tf_b.cget("weight") == "bold"
    for t in ("general", "pet", "items", "effects", "apps"):
        g.ui._set_tab(t)
        g.root.update()
    g.ui._toggle_picker(ALPHA)                         # Hat | Effect box, both sides
    g.ui._set_pick_mode("effect")
    g.ui._set_pick_mode("hat")
    g.ui._toggle_picker(ALPHA)
    with open(sgp.SETTINGS_PATH, encoding="utf-8") as f:
        assert '"language": "ko"' in f.read()
    print("  ko:", g.menu.entrycget(2, "label"), "/", sgp.i18n.tr("Reset hats & effects"), "/", sgp.i18n.tr("This app: "))
    g.set_language("en")
    assert g.menu.entrycget(0, "label") == "Always on top" and g.tf_ui.cget("family") == "Segoe UI"
    g.ui._set_tab("general")


step("language: Korean and back", korean)


def season_checks():                                   # in season first, afterwards last; always pickable
    import datetime
    import seasons
    day = lambda s: datetime.date.fromisoformat(s)
    pets = ["slime", "cat", "pumpkin", "ghost"]
    assert seasons.order(pets, day("2026-10-15")) == ["pumpkin", "ghost", "slime", "cat"]
    assert seasons.order(pets, day("2026-11-05"))[0] == "pumpkin"    # Halloween runs until Nov 5
    assert seasons.order(pets, day("2026-11-06")) == pets
    seasons.SEASONS["xmas"] = {"mark": [], "start": (11, 1), "end": (1, 6)}   # a made-up overlapping season
    seasons.SEASONAL["tree"] = "xmas"
    assert seasons.order(pets + ["tree"], day("2026-11-03")) == ["pumpkin", "ghost", "tree", "slime", "cat"]
    assert seasons.order(pets + ["tree"], day("2026-12-24")) == ["tree", "slime", "cat", "pumpkin", "ghost"]
    del seasons.SEASONS["xmas"], seasons.SEASONAL["tree"]
    assert seasons.order(list(sgp.EFFECTS), day("2026-10-15"))[:2] == ["none", "trick"]
    assert seasons.order(list(sgp.EFFECTS), day("2026-03-01"))[-1] == "trick"
    g.open_settings()
    for d in ("2026-10-15", "2026-03-01"):             # both orders of the Pet, Effects and Apps tabs
        os.environ["STATUS_PET_DATE"] = d
        g.ui.pages.pop("effect", None)
        for t in ("pet", "effects"):
            g.ui._set_tab(t)
            g.root.update()
        g.ui._set_tab("apps")
        g.ui._toggle_picker(ALPHA)
        g.ui._set_pick_mode("effect")
        g.root.update()
        g.ui._toggle_picker(ALPHA)
    assert g.ui._season_icon("halloween"), "the pumpkin mark should draw"
    g.ui._pick_char("pumpkin")                         # out of season it can still be picked
    assert g.character == "pumpkin"
    g.ui._pick_char("slime")
    del os.environ["STATUS_PET_DATE"]
    g.ui._set_tab("general")


step("seasons: in season first, out of season last", season_checks)


def update_notice():                                   # tray line + Settings footer link, Home icon
    import types
    import update_check
    assert update_check.newer("1.1", "1.0") and update_check.newer("1.10", "1.9") and update_check.newer("1.0.1", "1.0")
    assert not update_check.newer("1.0", "1.0") and not update_check.newer("0.9.2", "1.0") and not update_check.newer("", "1.0")
    opened = []
    sgp.open_page = lambda url: opened.append(url)
    g.tray = types.SimpleNamespace(labels={}, update_text=None, set_locked=lambda on: None,
                                   set_image=lambda grid: None, remove=lambda: None)
    g.open_settings()
    g.ui._set_tab("general")
    g._poll_update()
    assert g.tray.update_text is None
    g.upd.latest = "9.9"
    g._poll_update()
    assert g.tray.update_text == "Update available (v9.9)", g.tray.update_text
    g.root.update()
    footer = g.ui.body.winfo_children()[-1].winfo_children()
    link = [w for w in footer if w.cget("text") == "Update available · v9.9"]
    assert link, [w.cget("text") for w in footer]
    link[0].event_generate("<Button-1>")
    assert opened == [update_check.SITE], opened
    g.set_language("ko")
    assert g.tray.update_text == "업데이트 가능 (v9.9)", g.tray.update_text
    g.set_language("en")
    g.upd.latest = None
    g._poll_update()
    assert g.tray.update_text is None
    texts = [w.cget("text") for w in g.ui.body.winfo_children()[-1].winfo_children()]
    assert any(str(x).startswith("Status Pet · v") for x in texts), texts
    g.tray = None


step("update notice + Home", update_notice)
g.tray = None
step("reopen + one-line view render", lambda: (g.open_settings(), g.set_view("line"), g.render(), g.set_view("full")))
step("quit", g.quit)
shutil.rmtree(tmp, ignore_errors=True)
print("ERRORS:", errors or "none")
