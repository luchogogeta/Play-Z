"""Controles multimedia globales (play/pause/siguiente/anterior) vía WinRT.

Usa el mismo mecanismo que los controles multimedia de Windows (System Media
Transport Controls), así que funciona con cualquier app compatible
(Spotify, Chrome/Edge reproduciendo video, etc.) sin integración específica.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass

from winsdk.windows.media.control import (
    GlobalSystemMediaTransportControlsSessionManager as MediaManager,
)
from winsdk.windows.media.control import (
    GlobalSystemMediaTransportControlsSessionPlaybackStatus as PlaybackStatus,
)

_PLAYING = int(PlaybackStatus.PLAYING)


@dataclass
class NowPlaying:
    title: str
    artist: str
    app_id: str
    is_playing: bool


async def _current_session():
    manager = await MediaManager.request_async()
    return manager.get_current_session()


async def get_now_playing() -> NowPlaying | None:
    """Devuelve la app/canción que está sonando actualmente, si hay alguna."""
    session = await _current_session()
    if session is None:
        return None

    info = await session.try_get_media_properties_async()
    playback_info = session.get_playback_info()
    status = playback_info.playback_status if playback_info else None

    return NowPlaying(
        title=info.title or "(sin título)",
        artist=info.artist or "",
        app_id=session.source_app_user_model_id or "",
        is_playing=status == _PLAYING,
    )


async def play_pause() -> None:
    session = await _current_session()
    if session:
        await session.try_toggle_play_pause_async()


async def next_track() -> None:
    session = await _current_session()
    if session:
        await session.try_skip_next_async()


async def previous_track() -> None:
    session = await _current_session()
    if session:
        await session.try_skip_previous_async()


def run(coro):
    """Ejecuta una corrutina async de forma síncrona (para llamar desde Tkinter)."""
    return asyncio.run(coro)
