"""Controles multimedia globales (play/pause/siguiente/anterior) vía WinRT.

Usa el mismo mecanismo que los controles multimedia de Windows (System Media
Transport Controls), así que funciona con cualquier app compatible
(Spotify, Chrome/Edge reproduciendo video, etc.) sin integración específica.
"""

from __future__ import annotations

import asyncio
import threading
from dataclasses import dataclass

from winsdk.windows.media.control import (
    GlobalSystemMediaTransportControlsSessionManager as MediaManager,
)
from winsdk.windows.media.control import (
    GlobalSystemMediaTransportControlsSessionPlaybackStatus as PlaybackStatus,
)
from winsdk.windows.storage.streams import DataReader

_PLAYING = int(PlaybackStatus.PLAYING)


@dataclass
class NowPlaying:
    title: str
    artist: str
    app_id: str
    is_playing: bool
    thumbnail: bytes | None = None


async def _current_session():
    manager = await MediaManager.request_async()
    return manager.get_current_session()


async def _read_thumbnail(thumbnail_ref) -> bytes | None:
    """Baja la miniatura/portada (PNG o JPEG) que expone la app que suena:
    la carátula en Spotify/YouTube Music, la miniatura del video en YouTube,
    etc. Es la misma imagen que muestra el propio panel de Windows."""
    if thumbnail_ref is None:
        return None
    try:
        stream = await thumbnail_ref.open_read_async()
        reader = DataReader(stream)
        await reader.load_async(stream.size)
        return bytes(reader.read_buffer(stream.size))
    except Exception:
        return None


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
        thumbnail=await _read_thumbnail(info.thumbnail),
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


_loop: asyncio.AbstractEventLoop | None = None
_loop_lock = threading.Lock()


def _ensure_loop() -> asyncio.AbstractEventLoop:
    """Un event loop propio, corriendo en su propio hilo para siempre.

    pycaw/comtypes inicializa el hilo principal como apartamento COM STA.
    Las llamadas de WinRT que involucran streams (como bajar la miniatura)
    necesitan bombear mensajes de esa apartamento para completar, cosa que
    un asyncio.run() simple en el hilo de Tkinter no hace — se cuelgan para
    siempre. Corriendo todo esto en un hilo aparte, con su propia
    apartamento, se evita el conflicto.
    """
    global _loop
    with _loop_lock:
        if _loop is None:
            ready = threading.Event()

            def _runner():
                global _loop
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                _loop = loop
                ready.set()
                loop.run_forever()

            threading.Thread(target=_runner, daemon=True, name="media-control").start()
            ready.wait()
        return _loop


def run(coro):
    """Ejecuta una corrutina async de forma síncrona (para llamar desde Tkinter)."""
    loop = _ensure_loop()
    return asyncio.run_coroutine_threadsafe(coro, loop).result(timeout=10)
