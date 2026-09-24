"""Drives Status Pet through fake scenarios OFF SCREEN and measures its own CPU.

Nothing appears on the desktop: the gadget, its popup and the Settings window are placed far
outside every monitor, and no screen is captured. Pixel checks read the gadget's own image.
"""
import ctypes, importlib.machinery, importlib.util, os, sys, time, traceback

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

sgp.SETTINGS_PATH = os.path.join(OUT, "perf_settings_test.json")
if os.path.exists(sgp.SETTINGS_PATH):
    os.remove(sgp.SETTINGS_PATH)
sgp.SLEEP_AFTER = 2
vals = {"cpu": 34, "gpu": 28, "ram": 36, "apps": {}, "phase": "day"}
sgp.read_ram = lambda: (vals["ram"] / 100 * 64, 64.0)
sgp.time_phase = lambda: vals["phase"]
sgp.input_idle = lambda: 999.0                       # pretend the user is away, so the idle scenario can doze

g = sgp.Gadget()
g.poll_hover = lambda: None                          # hover is set by each scenario instead
g.cpu_reader.sample = lambda: vals["cpu"]
g.gpu_reader.sample = lambda: vals["gpu"]
g.app_reader.sample = lambda defs: {a: [{"cpu": c, "ram_gb": r} for c, r in lst]
                                    for a, lst in vals["apps"].items() if a in defs}
g.win.move(-8000, -8000)
A, B = "custom:alpha", "custom:beta"                 # a new install starts with an empty list; the scenarios need these
for exe in ("alpha.exe", "beta.exe", "gamma.exe"):
    g._add_app(exe)
g.set_app_hat(A, "wizard_hat")                       # Alpha: wizard hat + the Default effect (Magic)
g.set_app_hat(B, "beret")                            # Beta: beret + Painting
g.set_app_effect(B, "painting")

cost, errors = [], []
_render = g.render


def timed():
    t0 = time.perf_counter()
    try:
        _render()
    except Exception:
        errors.append(traceback.format_exc())
    cost.append(time.perf_counter() - t0)


g.render = timed

# name, cpu, gpu, ram, running apps {id: [(cpu, ram_gb), ...]}, phase, options
SCEN = [
    ("normal / day / Beta (beret)", 34, 28, 36, {B: [(4, 3.4)]}, "day", {}),
    ("busy Alpha / evening (magic)", 94, 71, 52, {A: [(88, 18.4), (3, 4.0)], B: [(1, 2.1)]}, "evening", {}),
    ("busy Beta / day (easel)", 92, 60, 48, {B: [(80, 6.2)]}, "day", {}),
    ("RAM 96% / night", 30, 25, 96, {A: [(6, 41.2)]}, "night", {}),
    ("idle -> dozing / night", 5, 3, 22, {}, "night", {}),
    ("compact / morning / 5 Alpha", 60, 40, 55,
     {A: [(61, 8.2), (14, 3.1), (4, 1.2), (2, .9), (1, .5)]}, "morning", {"view": "compact"}),
    ("hovered: view buttons + gear", 34, 28, 36, {}, "day", {"hover": True}),
    ("one line + pet / hovered popup", 34, 28, 36, {A: [(20, 8)], B: [(3, 2)]}, "day",
     {"view": "line", "hover": True}),
    ("one line, pet hidden", 34, 28, 36, {A: [(20, 8)]}, "day", {"view": "line", "pet": False}),
    ("transparent / walking", 34, 28, 36, {}, "evening", {"clear": True}),
    ("status 150% / Settings open", 50, 40, 55, {A: [(20, 8)]}, "day", {"sz": 150, "settings": True}),
    ("resized 380x120 / busy Alpha", 92, 90, 60, {A: [(90, 20)]}, "day", {"size": (380, 120)}),
    ("busy / construction wall", 92, 60, 48, {}, "day", {"effect": "build"}),
    ("busy / cooking stove (cat)", 92, 60, 48, {}, "day", {"effect": "cook", "char": "cat"}),
    ("busy / computer desk", 92, 60, 48, {}, "day", {"effect": "comp"}),
    ("step 2 / computer walking", 62, 40, 48, {}, "day", {"effect": "comp"}),
    ("pumpkin hopping / evening", 34, 28, 36, {}, "evening", {"char": "pumpkin"}),
    ("pumpkin busy Alpha (magic)", 94, 71, 52, {A: [(88, 18.4)]}, "night", {"char": "pumpkin"}),
    ("ghost drifting / night", 34, 28, 36, {}, "night", {"char": "ghost"}),
    ("Halloween step 3 (bats + sweets)", 94, 71, 52, {}, "night", {"effect": "trick"}),
    ("Halloween step 3 on the ghost", 94, 71, 52, {}, "night", {"effect": "trick", "char": "ghost"}),
]
report = []


def alpha(x, y):
    s = g.surf
    return s.pixel(max(0, min(s.w - 1, round(x))), max(0, min(s.h - 1, round(y))))[0]


def run(i=0):
    if i == len(SCEN):
        print("\n".join(report))
        print(f"S = {g.S}  logical CPUs = {os.cpu_count()}  drawing errors = {len(errors)}")
        for e in errors[:3]:
            print(e)
        g.quit()
        return
    name, c, gp, r, apps, ph, o = SCEN[i]
    vals.update(cpu=c, gpu=gp, ram=r, apps=apps, phase=ph)
    g.close_settings()
    g.view.set(o.get("view", "full"))
    g.show_pet.set(o.get("pet", True))
    g.transparent.set(o.get("clear", False))
    g.status_size.set(o.get("sz", 100))
    g.W, g.YH = o.get("size", (sgp.W_DEF, sgp.YH_DEF))
    g.line_w = g.line_disp = None
    g.hover = o.get("hover", False)
    g.default_effect = o.get("effect", "magic")
    g.character = o.get("char", "slime")
    g.tick_stats()
    g._on_option()
    if o.get("settings"):
        g.open_settings()
    cost.clear()
    x0 = g.pet.x
    t0, p0 = time.perf_counter(), time.process_time()

    def done():
        wall, cpu = time.perf_counter() - t0, time.process_time() - p0
        avg = sum(cost) / len(cost) * 1000 if cost else 0
        W, H = g.gw(), g.cur_h()
        checks = f"panel a={alpha(g.dev(W / 2), g.dev(H - 4))} corner a={alpha(1, 1)}"
        if g.lz:
            checks += f" strip a={alpha(g.dev(3), g.dev(3))}"
        report.append(f"{name:36s} mood={g.mood:5s} fx={g.effect:8s} step={g.fx_step} fps={len(cost) / wall:5.1f} "
                      f"render={avg:.2f} ms CPU={cpu / wall * 100:5.2f}% of one core moved={abs(g.pet.x - x0):4.0f}px "
                      f"{checks}")
        run(i + 1)

    g.root.after(5000, done)


g.root.after(800, run)
g.run()
