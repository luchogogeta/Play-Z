"""Dispositivo de salida de audio (parlantes/auriculares): listar y cambiar
cuál usa Windows por defecto — lo mismo que hace el selector de EarTrumpet.

Usa la misma interfaz COM interna de Windows (IPolicyConfig) que EarTrumpet,
NirSoft SoundVolumeView, etc.: no es una API pública documentada por
Microsoft, pero es estable desde Windows 7 y ya viene resuelta dentro de
pycaw (AudioUtilities.SetDefaultDevice), así que no hace falta declararla
a mano.
"""

from __future__ import annotations

from dataclasses import dataclass

from pycaw.pycaw import DEVICE_STATE, AudioUtilities, EDataFlow, ERole


@dataclass
class OutputDevice:
    id: str
    name: str
    is_default: bool


def list_output_devices() -> list[OutputDevice]:
    """Parlantes/auriculares activos, marcando cuál es el predeterminado."""
    try:
        default_id = AudioUtilities.GetSpeakers().id
    except Exception:
        default_id = None

    devices: list[OutputDevice] = []
    for dev in AudioUtilities.GetAllDevices(EDataFlow.eRender.value, DEVICE_STATE.ACTIVE.value):
        name = dev.FriendlyName or dev.id
        devices.append(OutputDevice(id=dev.id, name=name, is_default=(dev.id == default_id)))
    return devices


def set_default_output_device(device_id: str) -> None:
    """Cambia el dispositivo de salida predeterminado (uso normal + multimedia).

    No se toca eCommunications a propósito: es el dispositivo que Windows usa
    para llamadas, y suele querer quedar independiente del de reproducción
    general.
    """
    AudioUtilities.SetDefaultDevice(device_id, roles=[ERole.eConsole, ERole.eMultimedia])


def get_master_volume() -> tuple[float, bool]:
    """Volumen general (0.0-1.0) y mute del dispositivo de salida actual."""
    try:
        endpoint = AudioUtilities.GetSpeakers().EndpointVolume
        return endpoint.GetMasterVolumeLevelScalar(), bool(endpoint.GetMute())
    except Exception:
        return 1.0, False


def set_master_volume(value: float) -> None:
    """Fija el volumen general (0.0 a 1.0) del dispositivo de salida actual."""
    value = max(0.0, min(1.0, value))
    try:
        AudioUtilities.GetSpeakers().EndpointVolume.SetMasterVolumeLevelScalar(value, None)
    except Exception:
        pass


def set_master_muted(muted: bool) -> None:
    """Silencia o reactiva el volumen general del dispositivo de salida actual."""
    try:
        AudioUtilities.GetSpeakers().EndpointVolume.SetMute(muted, None)
    except Exception:
        pass
