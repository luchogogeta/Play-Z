"""Traducciones de los textos de la interfaz (idioma configurable).

No se traduce el nombre de la app ("Play-Z") ni los nombres reales de
dispositivos/aplicaciones (esos ya vienen en el idioma de Windows).
"""

from __future__ import annotations

STRINGS: dict[str, dict[str, str]] = {
    "es": {
        "media_no_track_title": "Nada sonando",
        "media_no_track_artist": "Reproducí algo para verlo acá",
        "section_apps": "Aplicaciones con audio",
        "empty_apps": "No se detectó audio activo todavía…",
        "tray_controls": "Controles",
        "tray_show_window": "Mostrar ventana completa",
        "tray_previous": "⏮  Anterior",
        "tray_play_pause": "⏯  Play / pausa",
        "tray_next": "⏭  Siguiente",
        "tray_quit": "Salir",
        "settings_title": "Configuración",
        "settings_language": "Idioma",
        "settings_theme": "Tema",
        "settings_theme_light": "Claro",
        "settings_theme_dark": "Oscuro",
        "settings_startup": "Iniciar con Windows",
        "settings_shortcut": "Atajo para mostrar la ventana",
        "settings_shortcut_hint": "Ej: Alt+Z, Ctrl+Shift+P",
        "settings_shortcut_apply": "Aplicar",
        "settings_shortcut_record": "🎹 Grabar",
        "settings_shortcut_stop": "Cancelar",
        "settings_shortcut_recording": "Presioná la combinación… (Esc para cancelar)",
        "settings_shortcut_active": "✓ Activo",
        "settings_shortcut_inactive": "✕ No se pudo activar — ¿otro programa ya lo usa?",
        "settings_shortcut_invalid": "Escribí una combinación válida (con Alt, Ctrl, Shift o Win)",
        "settings_close": "Cerrar",
    },
    "en": {
        "media_no_track_title": "Nothing playing",
        "media_no_track_artist": "Play something to see it here",
        "section_apps": "Apps with audio",
        "empty_apps": "No active audio detected yet…",
        "tray_controls": "Controls",
        "tray_show_window": "Show full window",
        "tray_previous": "⏮  Previous",
        "tray_play_pause": "⏯  Play / pause",
        "tray_next": "⏭  Next",
        "tray_quit": "Exit",
        "settings_title": "Settings",
        "settings_language": "Language",
        "settings_theme": "Theme",
        "settings_theme_light": "Light",
        "settings_theme_dark": "Dark",
        "settings_startup": "Start with Windows",
        "settings_shortcut": "Shortcut to show the window",
        "settings_shortcut_hint": "E.g.: Alt+Z, Ctrl+Shift+P",
        "settings_shortcut_apply": "Apply",
        "settings_shortcut_record": "🎹 Record",
        "settings_shortcut_stop": "Cancel",
        "settings_shortcut_recording": "Press the combination… (Esc to cancel)",
        "settings_shortcut_active": "✓ Active",
        "settings_shortcut_inactive": "✕ Couldn't activate — is another app using it?",
        "settings_shortcut_invalid": "Type a valid combination (with Alt, Ctrl, Shift, or Win)",
        "settings_close": "Close",
    },
}

LANGUAGE_NAMES: dict[str, str] = {"es": "Español", "en": "English"}

_current_language = "es"


def set_language(code: str) -> None:
    global _current_language
    if code in STRINGS:
        _current_language = code


def get_language() -> str:
    return _current_language


def tr(key: str) -> str:
    """Traduce una clave al idioma actual (con reserva en español)."""
    table = STRINGS.get(_current_language, STRINGS["es"])
    return table.get(key, STRINGS["es"].get(key, key))
