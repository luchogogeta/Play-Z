"""Registrar (o quitar) que Play-Z arranque junto con Windows.

Usa la clave "Run" de HKEY_CURRENT_USER: es por-usuario, así que no hace
falta ser administrador ni pedir elevación.
"""

from __future__ import annotations

import sys
import winreg
from pathlib import Path

_RUN_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"
_VALUE_NAME = "Play-Z"


def _startup_command() -> str:
    """Comando a ejecutar al iniciar sesión: el .exe empaquetado, o el
    intérprete de Python + main.py si se está corriendo desde el código."""
    if getattr(sys, "frozen", False):
        return f'"{sys.executable}"'
    script = str(Path(__file__).resolve().parent.parent / "main.py")
    return f'"{sys.executable}" "{script}"'


def is_enabled() -> bool:
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, _RUN_KEY, 0, winreg.KEY_READ) as key:
            winreg.QueryValueEx(key, _VALUE_NAME)
        return True
    except OSError:
        return False


def set_enabled(enabled: bool) -> None:
    with winreg.OpenKey(winreg.HKEY_CURRENT_USER, _RUN_KEY, 0, winreg.KEY_SET_VALUE) as key:
        if enabled:
            winreg.SetValueEx(key, _VALUE_NAME, 0, winreg.REG_SZ, _startup_command())
        else:
            try:
                winreg.DeleteValue(key, _VALUE_NAME)
            except FileNotFoundError:
                pass
