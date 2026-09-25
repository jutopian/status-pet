"""Builds the Status Pet installer: dist/StatusPet-Setup-<version>.exe (nothing is uploaded).

Steps: the icon (tools/make_icon.py) -> the installer pictures (tools/make_setup_art.py) -> the app folder with PyInstaller (build/dist/Status Pet, no Python needed on
the other PC) -> the installer with Inno Setup (installer/status_pet.iss).
Needs: pip install pyinstaller, and Inno Setup (ISCC.exe). Run: python tools/build_installer.py
"""
import glob
import os
import shutil
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.path.join(ROOT, "src")                 # the app
sys.path.insert(0, SRC)
from settings_ui import VERSION  # noqa: E402

BUILD = os.path.join(ROOT, "build")
STAGE = os.path.join(BUILD, "stage")


def iscc():
    for p in (os.path.join(os.environ.get("LOCALAPPDATA", ""), "Programs", "Inno Setup 7", "ISCC.exe"),
              r"C:\Program Files\Inno Setup 7\ISCC.exe", r"C:\Program Files (x86)\Inno Setup 7\ISCC.exe",
              os.path.join(os.environ.get("LOCALAPPDATA", ""), "Programs", "Inno Setup 6", "ISCC.exe"),
              r"C:\Program Files (x86)\Inno Setup 6\ISCC.exe"):
        if os.path.exists(p):
            return p
    sys.exit("Inno Setup (ISCC.exe) not found")


def run(cmd):
    print(">", " ".join(cmd))
    subprocess.run(cmd, check=True, cwd=ROOT)


def main():
    run([sys.executable, os.path.join("tools", "make_icon.py")])
    shutil.rmtree(BUILD, ignore_errors=True)
    run([sys.executable, os.path.join("tools", "make_setup_art.py")])   # installer pictures -> build/art
    os.makedirs(os.path.join(STAGE, "hats"))
    for f in glob.glob(os.path.join(SRC, "hats", "*.png")):     # the hat PNGs in hats/ only
        shutil.copy(f, os.path.join(STAGE, "hats"))
    shutil.copytree(os.path.join(SRC, "assets"), os.path.join(STAGE, "assets"))
    run([sys.executable, "-m", "PyInstaller", "--noconfirm", "--clean", "--windowed", "--name", "Status Pet",
         "--icon", os.path.join(SRC, "assets", "app_icon.ico"),
         "--add-data", os.path.join(STAGE, "hats") + os.pathsep + "hats",
         "--add-data", os.path.join(STAGE, "assets") + os.pathsep + "assets",
         "--distpath", os.path.join(BUILD, "dist"), "--workpath", os.path.join(BUILD, "work"),
         "--specpath", BUILD, os.path.join(SRC, "status_pet.pyw")])
    run([iscc(), f"/DAppVersion={VERSION}", os.path.join(ROOT, "installer", "status_pet.iss")])
    print("done:", os.path.join(ROOT, "dist", f"StatusPet-Setup-{VERSION}.exe"))


if __name__ == "__main__":
    main()
