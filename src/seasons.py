"""Seasonal pets and effects: always in the app and always pickable. In their season they move to the
front of their Settings list; after it they go to the back. Their tiles carry the season's small pixel mark in the corner.
When several seasons are listed, they follow the calendar (see order()).
"""
import datetime
import os

import sprites_pumpkin as spp

SEASONS = {   # start / end (month, day), both days included; a season may run over New Year (start after end)
    "halloween": {"mark": ["..sv..", ".OsOO.", "OhaaAO", "OdaadO", ".OOOO."], "start": (10, 1), "end": (11, 5)},
}
MARK_PAL = spp.PAL   # mark letters -> colors ("." = empty); the pumpkin uses the jack-o'-lantern pet's colors
SEASONAL = {"pumpkin": "halloween", "ghost": "halloween", "trick": "halloween"}   # pet / effect id -> season


def today():
    """The date; STATUS_PET_DATE=YYYY-MM-DD pretends another day (for testing)."""
    fake = os.environ.get("STATUS_PET_DATE")
    if fake:
        try:
            return datetime.date.fromisoformat(fake)
        except ValueError:
            pass
    return datetime.date.today()


def season_of(key):
    return SEASONAL.get(key)


def _open(s, md):
    return s["start"] <= md <= s["end"] if s["start"] <= s["end"] else md >= s["start"] or md <= s["end"]


def in_season(key, day=None):
    s = SEASONS.get(SEASONAL.get(key))
    day = day or today()
    return s is not None and _open(s, (day.month, day.day))


def _days_from(md, day):
    """Days from `day` to the next (month, day), 0..365."""
    d = datetime.date(day.year, *md)
    if d < day:
        d = datetime.date(day.year + 1, *md)
    return (d - day).days


def _days_since(md, day):
    """Days from the last (month, day) up to `day`, 0..365."""
    d = datetime.date(day.year, *md)
    if d > day:
        d = datetime.date(day.year - 1, *md)
    return (day - d).days


def order(keys, day=None, pinned=("none",)):
    """Settings order: pinned keys (e.g. "No effect") first, then what is in season (the one that started
    first leads), then the everyday ones, then seasonal ones out of season (the one coming back soonest leads).
    Everything else keeps its original order."""
    day = day or today()

    def rank(k):
        if k in pinned:
            return 0, 0
        s = SEASONS.get(SEASONAL.get(k))
        if s is None:
            return 2, 0
        if _open(s, (day.month, day.day)):
            return 1, -_days_since(s["start"], day)
        return 3, _days_from(s["start"], day)
    return sorted(keys, key=rank)
