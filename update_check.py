"""Update notice: learns the newest version from one small file on the website.

The file (version.json next to the landing page) looks like {"version": "1.1", "url": "https://..."}; "url" is
optional and defaults to the landing page. A new version ships by editing that file. Checked in a
background thread (the download never blocks the gadget): at start, then once a day, and when Settings opens.
No internet, a bad file or an older/equal version -> `latest` stays None and nothing is shown.
Testing: STATUS_PET_UPDATE=1.1 pretends the website says 1.1 (no internet used).
"""
import json
import os
import re
import threading
import time
import urllib.request
import webbrowser

SITE = "https://jutopian.github.io/status-pet/"
URL = SITE + "version.json"
DAY = 24 * 3600


def _parts(v):
    return tuple(int(n) for n in re.findall(r"\d+", v))


def newer(a, b):
    """True when version text `a` is newer than `b` ("1.10" > "1.9", "1.0.1" > "1.0")."""
    pa, pb = _parts(a), _parts(b)
    n = max(len(pa), len(pb))
    return bool(pa) and pa + (0,) * (n - len(pa)) > pb + (0,) * (n - len(pb))


def open_page(url=SITE):
    """Opens a web page in the default browser; only plain https links (the file can't point anywhere odd)."""
    webbrowser.open(url if url.startswith("https://") else SITE)


class UpdateCheck:
    def __init__(self, current):
        self.current = current
        self.latest = None                 # the newer version text once found, else None
        self.link = SITE
        self.last = -DAY                   # time.monotonic() of the last check started
        self.busy = False

    def check(self, min_gap=0.0):
        """Starts a check in the background unless one is running or the last one is less than min_gap s old."""
        now = time.monotonic()
        fake = os.environ.get("STATUS_PET_UPDATE")
        if fake:
            self.last, self.latest = now, fake if newer(fake, self.current) else None
            return
        if self.busy or now - self.last < min_gap:
            return
        self.busy, self.last = True, now
        threading.Thread(target=self._run, daemon=True).start()

    def due(self):
        return time.monotonic() - self.last >= DAY

    def _run(self):
        try:
            req = urllib.request.Request(URL, headers={"Cache-Control": "no-cache"})
            with urllib.request.urlopen(req, timeout=10) as r:
                data = json.loads(r.read(4096).decode("utf-8"))
            v = str(data.get("version", "")).strip()
            if newer(v, self.current):
                url = str(data.get("url") or SITE)
                self.link = url if url.startswith("https://") else SITE
                self.latest = v
            else:
                self.latest = None
        except Exception:                  # offline, timeout, bad file: keep what we knew, try again later
            pass
        finally:
            self.busy = False
