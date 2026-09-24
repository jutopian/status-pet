"""Shown texts in 10 languages. Code keeps writing English; tr() gives the current language's text.

The first start follows the Windows language; after that the General tab's Language picker decides (saved as
"language" in the settings file). Each language's table lives in its own file under lang/ (lang/ko.py, lang/ja.py,
...) so one language can be fixed alone. Names stay in English in every language: Status Pet, CPU / GPU / RAM,
app names, pet / hat / effect names.
"""
import ctypes
import importlib

LANGS = (                          # the Language picker: each name always written in its own language
    ("en", "English"),
    ("ko", "한국어"),
    ("ja", "日本語"),
    ("zh_hans", "简体中文"),
    ("zh_hant", "繁體中文"),
    ("es", "Español"),
    ("pt_br", "Português"),
    ("de", "Deutsch"),
    ("fr", "Français"),
    ("ru", "Русский"),
)
FONTS = {                          # language -> Tk font family (built into Windows); anything missing -> Segoe UI
    "ko": "Malgun Gothic",
    "ja": "Yu Gothic UI",
    "zh_hans": "Microsoft YaHei UI",
    "zh_hant": "Microsoft JhengHei UI",
}
lang = "en"
_tables = {}                       # language -> {English: translated}, loaded the first time it's needed


def _table(code):
    if code not in _tables:
        try:
            _tables[code] = importlib.import_module("lang." + code).TEXTS
        except ImportError:
            _tables[code] = {}
    return _tables[code]


def system_lang():
    """The Windows UI language, mapped to one of LANGS ("en" when it isn't one of them)."""
    try:
        buf = ctypes.create_unicode_buffer(85)
        ctypes.windll.kernel32.GetUserDefaultLocaleName(buf, 85)
        loc = buf.value.lower()
    except (AttributeError, OSError):
        return "en"
    if loc.startswith("zh"):
        return "zh_hant" if loc.split("-")[-1] in ("tw", "hk", "mo") else "zh_hans"
    if loc.startswith("pt"):
        return "pt_br"
    primary = loc.split("-")[0]
    return primary if primary in dict(LANGS) else "en"


def set_lang(code):
    global lang
    lang = code if code in dict(LANGS) else "en"


def tr(text, **kw):
    """The shown text for English `text` in the current language (English when there is no translation)."""
    if lang != "en":
        text = _table(lang).get(text, text)
    return text.format(**kw) if kw else text


def font(bold=False, code=None):
    """(family, weight) for Tk text in language `code` (current language when not given)."""
    family = FONTS.get(code if code is not None else lang)
    if family:
        return family, "bold" if bold else "normal"
    return ("Segoe UI Semibold" if bold else "Segoe UI"), "normal"
