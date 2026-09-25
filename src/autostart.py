"""General tab "Start with Windows": one value in the current user's Run key (no admin rights needed).

Windows itself is the record of the choice, so it stays right even if the user removes it in Task Manager's
Startup apps. While it is on, every start rewrites the value, so a moved app folder keeps working.
"""
import os
import sys
import winreg

RUN_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"
NAME = "Status Pet"


def command(script):
    """How Windows should start the gadget: the installed .exe, or pythonw.exe with this script (no console)."""
    if getattr(sys, "frozen", False):
        return f'"{sys.executable}"'
    exe = sys.executable
    pyw = os.path.join(os.path.dirname(exe), "pythonw.exe")
    return f'"{pyw if os.path.exists(pyw) else exe}" "{script}"'


def is_on():
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN_KEY) as k:
            winreg.QueryValueEx(k, NAME)
        return True
    except OSError:
        return False


def set_on(on, script):
    """Turns starting with Windows on or off. -> True if it worked."""
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN_KEY, 0, winreg.KEY_SET_VALUE) as k:
            if on:
                winreg.SetValueEx(k, NAME, 0, winreg.REG_SZ, command(script))
            else:
                try:
                    winreg.DeleteValue(k, NAME)
                except FileNotFoundError:
                    pass
        return True
    except OSError:
        return False


def refresh(script):
    """At start: if it is on, point it at where the gadget runs from now."""
    if is_on():
        set_on(True, script)
