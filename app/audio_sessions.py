"""Acceso a las sesiones de audio por aplicación (Windows Core Audio via pycaw).

Permite listar qué aplicaciones tienen una sesión de audio activa y controlar
su volumen / mute de forma independiente al volumen general de Windows.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from pycaw.pycaw import AudioUtilities


@dataclass
class AppAudioSession:
    """Representa el volumen de una aplicación individual."""

    pid: int
    name: str
    volume: float  # 0.0 - 1.0
    muted: bool
    _volume_interface: Any = field(repr=False)

    def set_volume(self, value: float) -> None:
        """Fija el volumen de esta aplicación (0.0 a 1.0)."""
        value = max(0.0, min(1.0, value))
        self._volume_interface.SetMasterVolume(value, None)
        self.volume = value

    def set_muted(self, muted: bool) -> None:
        """Silencia o reactiva el audio de esta aplicación."""
        self._volume_interface.SetMute(muted, None)
        self.muted = muted


def list_app_sessions() -> list[AppAudioSession]:
    """Devuelve una sesión por cada aplicación con audio activo o reciente.

    Se excluyen las sesiones sin proceso asociado (sonidos del sistema).
    """
    result: list[AppAudioSession] = []
    for session in AudioUtilities.GetAllSessions():
        process = session.Process
        if process is None:
            continue
        try:
            name = process.name()
        except Exception:
            name = f"PID {process.pid}"

        volume_interface = session.SimpleAudioVolume
        if volume_interface is None:
            continue

        result.append(
            AppAudioSession(
                pid=process.pid,
                name=name,
                volume=volume_interface.GetMasterVolume(),
                muted=bool(volume_interface.GetMute()),
                _volume_interface=volume_interface,
            )
        )
    return result
