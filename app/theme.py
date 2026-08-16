"""Paleta de colores, tipografía y persistencia de preferencias (tema, panel)."""

from __future__ import annotations

import json
import os
from pathlib import Path

FONT = "Segoe UI"

THEMES: dict[str, dict[str, str]] = {
    "dark": {
        "bg": "#121317",
        "surface": "#1c1e26",
        "surface_alt": "#262936",
        "border": "#2a2d3a",
        "fg": "#f2f3f7",
        "fg_muted": "#9295a6",
        "accent": "#8b7cff",
        "accent_fg": "#ffffff",
        "danger": "#ff6b6b",
    },
    "light": {
        "bg": "#f4f4f8",
        "surface": "#ffffff",
        "surface_alt": "#eeeef4",
        "border": "#e2e3ea",
        "fg": "#1b1c22",
        "fg_muted": "#6b6d7a",
        "accent": "#6c5ce7",
        "accent_fg": "#ffffff",
        "danger": "#e0455c",
    },
}

# Colores para los avatares de cada aplicación (se elige por hash del nombre).
AVATAR_COLORS = [
    "#ff6b6b",
    "#feca57",
    "#1dd1a1",
    "#54a0ff",
    "#a29bfe",
    "#ff9ff3",
    "#00d2d3",
    "#ff9f43",
]

_LANGUAGES = ("es", "en")
_DEFAULTS = {"theme": "dark", "list_expanded": False, "language": "es"}


def _settings_path() -> Path:
    """Carpeta de datos del usuario, estable tanto en dev como empaquetado (.exe)."""
    base = Path(os.environ.get("LOCALAPPDATA", str(Path.home()))) / "Play-Z"
    base.mkdir(parents=True, exist_ok=True)
    return base / "settings.json"


def avatar_color(name: str) -> str:
    """Devuelve un color estable para una app, según su nombre."""
    if not name:
        return AVATAR_COLORS[0]
    index = sum(ord(char) for char in name) % len(AVATAR_COLORS)
    return AVATAR_COLORS[index]


def load_settings() -> dict:
    """Lee las preferencias guardadas (tema, si el panel de apps está desplegado)."""
    settings = dict(_DEFAULTS)
    try:
        data = json.loads(_settings_path().read_text(encoding="utf-8"))
        if data.get("theme") in THEMES:
            settings["theme"] = data["theme"]
        if isinstance(data.get("list_expanded"), bool):
            settings["list_expanded"] = data["list_expanded"]
        if data.get("language") in _LANGUAGES:
            settings["language"] = data["language"]
    except (OSError, ValueError):
        pass
    return settings


def save_settings(**changes) -> None:
    """Actualiza y persiste las preferencias (recibe solo las claves que cambian)."""
    settings = load_settings()
    settings.update(changes)
    try:
        _settings_path().write_text(json.dumps(settings), encoding="utf-8")
    except OSError:
        pass
