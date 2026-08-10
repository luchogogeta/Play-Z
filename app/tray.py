"""Icono en la bandeja del sistema (área de notificación, al lado del reloj)."""

from __future__ import annotations

from typing import Callable

import pystray
from PIL import Image, ImageDraw

from .theme import THEMES

_ACCENT = THEMES["dark"]["accent"]


def build_icon_image(size: int = 64) -> Image.Image:
    """Dibuja a mano un ícono simple: círculo de color + nota musical."""
    image = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(image)
    draw.ellipse((2, 2, size - 2, size - 2), fill=_ACCENT)

    white = "#ffffff"
    draw.ellipse((size * 0.27, size * 0.56, size * 0.47, size * 0.74), fill=white)
    draw.rectangle((size * 0.44, size * 0.20, size * 0.51, size * 0.66), fill=white)
    draw.polygon(
        [
            (size * 0.44, size * 0.20),
            (size * 0.72, size * 0.30),
            (size * 0.72, size * 0.42),
            (size * 0.44, size * 0.34),
        ],
        fill=white,
    )
    return image


class TrayIcon:
    """Ícono de bandeja: corre en su propio hilo, todo se delega por callbacks.

    Los callbacks los ejecuta pystray en un hilo aparte del de Tkinter, así
    que quien los reciba (MainWindow) es responsable de pasarlos de vuelta
    al hilo principal (por ejemplo con `self.after(0, ...)`).
    """

    def __init__(
        self,
        *,
        on_toggle_flyout: Callable[[], None],
        on_show_window: Callable[[], None],
        on_play_pause: Callable[[], None],
        on_next: Callable[[], None],
        on_previous: Callable[[], None],
        on_quit: Callable[[], None],
    ):
        # Clic izquierdo (acción por defecto): abre el panelito de controles
        # arriba de la bandeja, como el volumen o la red de Windows.
        menu = pystray.Menu(
            pystray.MenuItem(
                "Controles", lambda icon, item: on_toggle_flyout(), default=True, visible=False
            ),
            pystray.MenuItem("Mostrar ventana completa", lambda icon, item: on_show_window()),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem("⏮  Anterior", lambda icon, item: on_previous()),
            pystray.MenuItem("⏯  Play / pausa", lambda icon, item: on_play_pause()),
            pystray.MenuItem("⏭  Siguiente", lambda icon, item: on_next()),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem("Salir", lambda icon, item: on_quit()),
        )
        self._icon = pystray.Icon("Play-Z", build_icon_image(), "Play-Z", menu)

    def run_detached(self) -> None:
        """Arranca el ícono en su propio hilo (soportado en Windows)."""
        self._icon.run_detached()

    def stop(self) -> None:
        try:
            self._icon.stop()
        except Exception:
            pass
