"""GUI strings for Pad Zero.

English is the default. Spanish is used when Windows (or LANG) is a Spanish
locale. Set PADZERO_LANG=en or es to force one language.

Technical-detail keys (model, serial, key group, …) stay in English; they
are not in this catalog.
"""
from __future__ import annotations

import locale
import os

from i18n import en as _en
from i18n import es as _es

_SUPPORTED = {"en", "es"}
_CATALOGS = {"en": _en.STRINGS, "es": _es.STRINGS}


def language_from_tag(tag: str | None) -> str:
    if not tag:
        return "en"
    normalized = tag.replace("-", "_").split(".")[0].strip().lower()
    if normalized == "es" or normalized.startswith(("es_", "spanish")):
        return "es"
    return "en"


def current_language() -> str:
    override = os.environ.get("PADZERO_LANG", "").strip().lower()
    if override in _SUPPORTED:
        return override

    try:
        locale_name = locale.getlocale()[0]
    except ValueError:
        locale_name = None

    if locale_name:
        return language_from_tag(locale_name)

    for key in ("LC_ALL", "LC_MESSAGES", "LANG"):
        if language_from_tag(os.environ.get(key)) == "es":
            return "es"
    return "en"


def load(language: str | None = None) -> dict[str, str]:
    code = language if language in _SUPPORTED else current_language()
    return _CATALOGS[code]


STRINGS = load()


def t(key: str, **kwargs) -> str:
    """Look up a GUI string; fall back to English if a key is missing."""
    text = STRINGS.get(key) or _en.STRINGS.get(key) or key
    if kwargs:
        return text.format(**kwargs)
    return text


missing = set(_en.STRINGS) - set(_es.STRINGS)
extra = set(_es.STRINGS) - set(_en.STRINGS)
if missing or extra:
    raise RuntimeError(
        "i18n catalogs are out of sync: missing=%s extra=%s" % (sorted(missing), sorted(extra))
    )
