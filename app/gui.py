"""Interfaz gráfica (Tkinter): mezclador por app + controles multimedia.

Diseño tipo tarjetas, con tema claro/oscuro intercambiable (se recuerda
entre sesiones) y un poco de identidad visual (avatares por app, acento
de color, tipografía consistente).
"""

from __future__ import annotations

import ctypes
import ctypes.wintypes
import io
import tkinter as tk
from tkinter import ttk

from PIL import Image, ImageTk

from .audio_devices import (
    get_master_volume,
    list_output_devices,
    set_default_output_device,
    set_master_muted,
    set_master_volume,
)
from .audio_sessions import AppAudioSession, list_app_sessions
from .icons import extract_app_icon
from .media_control import get_now_playing, next_track, play_pause, previous_track
from .media_control import run as run_async
from .theme import FONT, THEMES, avatar_color, load_settings, save_settings
from .tray import TrayIcon, build_icon_image

REFRESH_MS = 1500
WINDOW_WIDTH = 460
EXPANDED_HEIGHT = 720
COLLAPSED_HEIGHT = 410
SPI_GETWORKAREA = 0x0030


def _fetch_now_playing():
    """Wrapper sincrónico y a prueba de excepciones sobre get_now_playing()."""
    try:
        return run_async(get_now_playing())
    except Exception:
        return None


def _do_previous() -> None:
    run_async(previous_track())


def _do_play_pause() -> None:
    run_async(play_pause())


def _do_next() -> None:
    run_async(next_track())


_ART_SCRIM_TOP = 110  # oscurecido arriba de la portada (0-255)
_ART_SCRIM_BOTTOM = 235  # oscurecido abajo, donde va el texto/controles
_ART_SCRIM_COLOR = (8, 8, 12)


def _cover_fit(image: Image.Image, width: int, height: int) -> Image.Image:
    """Recorta y escala una imagen para llenar width×height sin deformarla
    (mismo criterio que `background-size: cover` en CSS)."""
    src_ratio = image.width / image.height
    dst_ratio = width / height
    if src_ratio > dst_ratio:
        new_height = height
        new_width = max(1, round(height * src_ratio))
    else:
        new_width = width
        new_height = max(1, round(width / src_ratio))
    resized = image.resize((new_width, new_height), Image.LANCZOS)
    left = (new_width - width) // 2
    top = (new_height - height) // 2
    return resized.crop((left, top, left + width, top + height))


def _compose_art_background(thumbnail: Image.Image | None, width: int, height: int, fallback: str) -> Image.Image:
    """Fondo del panel de reproducción: la portada/miniatura recortada con un
    degradado oscuro (más fuerte abajo, donde va el texto) para que se siga
    leyendo; o un color plano si no hay portada disponible."""
    width, height = max(width, 1), max(height, 1)
    if thumbnail is None:
        return Image.new("RGB", (width, height), fallback)

    cropped = _cover_fit(thumbnail, width, height)

    gradient = Image.new("L", (1, height))
    for y in range(height):
        t = y / max(height - 1, 1)
        gradient.putpixel((0, y), round(_ART_SCRIM_TOP + t * (_ART_SCRIM_BOTTOM - _ART_SCRIM_TOP)))
    gradient = gradient.resize((width, height))

    scrim = Image.new("RGB", (width, height), _ART_SCRIM_COLOR)
    return Image.composite(scrim, cropped, gradient)


class VolumeSlider(tk.Canvas):
    """Control de volumen dibujado a mano: barra redondeada + thumb circular.

    El ttk.Scale por defecto (tema clam) se ve tosco y bloqueado a los
    colores del tema de ttk; dibujarlo con Canvas da control total y un
    resultado mucho más prolijo (como los sliders de Spotify o Windows 11).
    """

    HEIGHT = 20
    TRACK_WIDTH = 4
    THUMB_RADIUS = 6

    def __init__(self, parent: tk.Widget, value: float, on_change, on_release=None, **kwargs):
        super().__init__(parent, height=self.HEIGHT, highlightthickness=0, bd=0, **kwargs)
        self._value = max(0.0, min(1.0, value))
        self._on_change = on_change
        self._on_release = on_release
        self._dragging = False
        self._track_color = "#888888"
        self._fill_color = "#8b7cff"
        self._thumb_color = "#ffffff"

        self.bind("<Configure>", lambda e: self._redraw())
        self.bind("<ButtonPress-1>", self._on_press)
        self.bind("<B1-Motion>", self._on_drag)
        self.bind("<ButtonRelease-1>", self._on_button_release)

    def set_colors(self, *, track: str, fill: str, thumb: str) -> None:
        self._track_color = track
        self._fill_color = fill
        self._thumb_color = thumb
        self._redraw()

    def set(self, value: float) -> None:
        if self._dragging:
            return
        self._value = max(0.0, min(1.0, value))
        self._redraw()

    def get(self) -> float:
        return self._value

    @property
    def is_dragging(self) -> bool:
        return self._dragging

    def _usable_width(self) -> float:
        return max(self.winfo_width() - 2 * self.THUMB_RADIUS, 1)

    def _value_to_x(self, value: float) -> float:
        return self.THUMB_RADIUS + value * self._usable_width()

    def _x_to_value(self, x: float) -> float:
        return max(0.0, min(1.0, (x - self.THUMB_RADIUS) / self._usable_width()))

    def _redraw(self) -> None:
        self.delete("all")
        width = self.winfo_width()
        y = self.HEIGHT / 2
        x0, x1 = self.THUMB_RADIUS, width - self.THUMB_RADIUS
        if x1 <= x0:
            return

        self.create_line(x0, y, x1, y, width=self.TRACK_WIDTH, fill=self._track_color, capstyle=tk.ROUND)
        fill_x = self._value_to_x(self._value)
        if fill_x > x0:
            self.create_line(x0, y, fill_x, y, width=self.TRACK_WIDTH, fill=self._fill_color, capstyle=tk.ROUND)

        r = self.THUMB_RADIUS
        self.create_oval(fill_x - r, y - r, fill_x + r, y + r, fill=self._thumb_color, outline="")

    def _set_from_event(self, event, *, final: bool) -> None:
        self._value = self._x_to_value(event.x)
        self._redraw()
        if self._on_change:
            self._on_change(self._value)
        if final and self._on_release:
            self._on_release(self._value)

    def _on_press(self, event) -> None:
        self._dragging = True
        self._set_from_event(event, final=False)

    def _on_drag(self, event) -> None:
        if self._dragging:
            self._set_from_event(event, final=False)

    def _on_button_release(self, event) -> None:
        self._dragging = False
        self._set_from_event(event, final=True)


class MasterVolumeControl:
    """Fila de volumen general del sistema (todas las apps a la vez), con
    su propio mute — se usa tanto en la ventana completa como en el flyout."""

    def __init__(self, parent: tk.Widget):
        self.frame = tk.Frame(parent, bd=0, highlightthickness=0)
        self._muted = False
        self._colors: dict | None = None
        self._bg_color = ""

        self.mute_btn = tk.Button(
            self.frame,
            bd=0,
            highlightthickness=0,
            takefocus=0,
            cursor="hand2",
            font=(FONT, 11),
            command=self._on_mute_toggle,
        )
        self.mute_btn.pack(side="left")

        self.slider = VolumeSlider(self.frame, value=1.0, on_change=self._on_slider_change)
        self.slider.pack(side="left", fill="x", expand=True, padx=(8, 8))

        self.percent_label = tk.Label(self.frame, text="100%", font=(FONT, 9), width=4, anchor="e")
        self.percent_label.pack(side="left")

    def _on_slider_change(self, value: float) -> None:
        set_master_volume(value)
        self.percent_label.configure(text=f"{round(value * 100)}%")

    def _on_mute_toggle(self) -> None:
        self._muted = not self._muted
        set_master_muted(self._muted)
        self._update_mute_button()

    def _update_mute_button(self) -> None:
        if self._colors is None:
            return
        self.mute_btn.configure(
            text="🔇" if self._muted else "🔊",
            bg=self._bg_color,
            fg=self._colors["danger"] if self._muted else self._colors["fg_muted"],
            activebackground=self._colors["surface_alt"],
        )

    def refresh(self) -> None:
        volume, muted = get_master_volume()
        self.slider.set(volume)
        self._muted = muted
        self._update_mute_button()
        if not self.slider.is_dragging:
            self.percent_label.configure(text=f"{round(volume * 100)}%")

    def apply_theme(self, colors: dict, bg_color: str) -> None:
        self._colors = colors
        self._bg_color = bg_color
        self.frame.configure(bg=bg_color)
        self.percent_label.configure(bg=bg_color, fg=colors["fg_muted"])
        self.slider.configure(bg=bg_color)
        self.slider.set_colors(track=colors["surface_alt"], fill=colors["accent"], thumb=colors["fg"])
        self._update_mute_button()


class CanvasTransportControls:
    """Botones ⏮ ⏯ ⏭ dibujados directo sobre un Canvas, sin fondo cuadrado,
    para no tapar la imagen de fondo. Solo play lleva un círculo de color;
    anterior/siguiente son íconos "flotantes" con una sombra sutil para
    leerse sobre cualquier imagen (se apaga sola si no hay portada)."""

    def __init__(
        self,
        canvas: tk.Canvas,
        *,
        gap: float = 46,
        play_radius: float = 21,
        side_font_size: int = 14,
        play_font_size: int = 16,
    ):
        self.canvas = canvas
        self._gap = gap
        self._play_radius = play_radius

        side_font = (FONT, side_font_size)
        play_font = (FONT, play_font_size, "bold")

        self._prev_shadow = canvas.create_text(0, 0, text="⏮", font=side_font)
        self._prev_label = canvas.create_text(0, 0, text="⏮", font=side_font)
        self._play_circle = canvas.create_oval(0, 0, 1, 1, outline="")
        self._play_label = canvas.create_text(0, 0, text="⏯", font=play_font)
        self._next_shadow = canvas.create_text(0, 0, text="⏭", font=side_font)
        self._next_label = canvas.create_text(0, 0, text="⏭", font=side_font)

        self._bind_click((self._prev_shadow, self._prev_label), _do_previous)
        self._bind_click((self._play_circle, self._play_label), _do_play_pause)
        self._bind_click((self._next_shadow, self._next_label), _do_next)

    def _bind_click(self, items: tuple[int, ...], command) -> None:
        for item in items:
            self.canvas.tag_bind(item, "<Button-1>", lambda e: command())
            self.canvas.tag_bind(item, "<Enter>", lambda e: self.canvas.config(cursor="hand2"))
            self.canvas.tag_bind(item, "<Leave>", lambda e: self.canvas.config(cursor=""))

    def position(self, center_x: float, y: float) -> None:
        gap, r = self._gap, self._play_radius
        self.canvas.coords(self._prev_shadow, center_x - gap + 1, y + 1)
        self.canvas.coords(self._prev_label, center_x - gap, y)
        self.canvas.coords(self._play_circle, center_x - r, y - r, center_x + r, y + r)
        self.canvas.coords(self._play_label, center_x, y)
        self.canvas.coords(self._next_shadow, center_x + gap + 1, y + 1)
        self.canvas.coords(self._next_label, center_x + gap, y)

    def apply_theme(self, colors: dict, has_art: bool) -> None:
        if has_art:
            icon_fill, icon_shadow = "#ffffff", "#000000"
        else:
            icon_fill = colors["fg_muted"]
            icon_shadow = colors["surface"]  # se funde con el fondo plano: invisible

        for shadow, label in ((self._prev_shadow, self._prev_label), (self._next_shadow, self._next_label)):
            self.canvas.itemconfig(shadow, fill=icon_shadow)
            self.canvas.itemconfig(label, fill=icon_fill)
        self.canvas.itemconfig(self._play_circle, fill=colors["accent"])
        self.canvas.itemconfig(self._play_label, fill=colors["accent_fg"])


class AppRow:
    """Tarjeta de una app: ícono, nombre, % de volumen, slider y mute."""

    def __init__(self, parent: tk.Widget, session: AppAudioSession, colors: dict):
        self.pid = session.pid
        self._session = session
        self.colors = colors

        self.card = tk.Frame(parent, bd=0, highlightthickness=1)
        self.card.pack(fill="x", pady=(0, 10))
        self.card.columnconfigure(1, weight=1)

        self._build_icon(session)
        self.avatar.grid(row=0, column=0, rowspan=2, padx=(14, 12), pady=14)

        self.name_label = tk.Label(
            self.card, text=session.name, anchor="w", font=(FONT, 10, "bold")
        )
        self.name_label.grid(row=0, column=1, sticky="ew", pady=(12, 0))

        self.percent_label = tk.Label(self.card, text="", anchor="e", font=(FONT, 9))
        self.percent_label.grid(row=0, column=2, sticky="e", padx=(4, 14), pady=(12, 0))

        self.mute_btn = tk.Button(
            self.card,
            bd=0,
            highlightthickness=0,
            takefocus=0,
            cursor="hand2",
            font=(FONT, 11),
            command=self._on_mute_toggle,
        )
        self.mute_btn.grid(row=0, column=3, rowspan=2, padx=(0, 14))

        self.slider = VolumeSlider(
            self.card, value=session.volume, on_change=self._on_slider_change
        )
        self.slider.grid(row=1, column=1, columnspan=2, sticky="ew", padx=(0, 8), pady=(2, 14))

        self._set_percent_label(session.volume)
        self.apply_theme(colors)

    def _build_icon(self, session: AppAudioSession) -> None:
        """Ícono real de la app si se pudo extraer; si no, un avatar de color."""
        icon_image = extract_app_icon(session.exe_path, size=36) if session.exe_path else None
        if icon_image is not None:
            self._icon_photo = ImageTk.PhotoImage(icon_image)
            self.avatar = tk.Label(self.card, image=self._icon_photo, bd=0, highlightthickness=0)
        else:
            self.avatar = tk.Canvas(self.card, width=36, height=36, highlightthickness=0, bd=0)
            self.avatar.create_oval(2, 2, 34, 34, fill=avatar_color(session.name), outline="")
            letter = (session.name[:1] or "?").upper()
            self.avatar.create_text(18, 18, text=letter, fill="#ffffff", font=(FONT, 12, "bold"))

    def _set_percent_label(self, volume: float) -> None:
        self.percent_label.configure(text=f"{round(volume * 100)}%")

    def _on_slider_change(self, value: float) -> None:
        self._set_percent_label(value)
        self._session.set_volume(value)

    def _on_mute_toggle(self) -> None:
        muted = not self._session.muted
        self._session.set_muted(muted)
        self._update_mute_button(muted)

    def _update_mute_button(self, muted: bool) -> None:
        self.mute_btn.configure(
            text="🔇" if muted else "🔊",
            fg=self.colors["danger"] if muted else self.colors["fg_muted"],
        )

    def update_from(self, session: AppAudioSession) -> None:
        self._session = session
        self.slider.set(session.volume)
        if not self.slider.is_dragging:
            self._set_percent_label(session.volume)
        self._update_mute_button(session.muted)

    def apply_theme(self, colors: dict) -> None:
        self.colors = colors
        self.card.configure(bg=colors["surface"], highlightbackground=colors["border"])
        self.avatar.configure(bg=colors["surface"])
        self.name_label.configure(bg=colors["surface"], fg=colors["fg"])
        self.percent_label.configure(bg=colors["surface"], fg=colors["fg_muted"])
        self.mute_btn.configure(bg=colors["surface"], activebackground=colors["surface_alt"])
        self.slider.configure(bg=colors["surface"])
        self.slider.set_colors(track=colors["surface_alt"], fill=colors["accent"], thumb=colors["fg"])
        self._update_mute_button(self._session.muted)

    def destroy(self) -> None:
        self.card.destroy()


class MediaPanel:
    """Tarjeta superior: la portada/miniatura de fondo + qué está sonando +
    play/pause/siguiente/anterior — como el "now playing" de Spotify.

    El texto queda abajo a la izquierda y los controles abajo a la derecha,
    para no quedar los dos apilados justo en el centro de la imagen (que
    suele ser donde está lo importante de una foto o miniatura)."""

    HEIGHT = 150
    CONTROLS_GAP = 44
    CONTROLS_MARGIN = 30

    def __init__(self, parent: tk.Widget, colors: dict):
        self.colors = colors
        self._thumbnail_raw: bytes | None = None
        self._thumbnail: Image.Image | None = None
        self._bg_photo = None
        self._bg_id = None

        self.frame = tk.Canvas(parent, height=self.HEIGHT, highlightthickness=1, bd=0)
        self.frame.bind("<Configure>", lambda e: self._redraw())

        self._title_id = self.frame.create_text(
            18, self.HEIGHT - 78, anchor="w", text="Nada sonando", font=(FONT, 13, "bold")
        )
        self._artist_id = self.frame.create_text(
            18, self.HEIGHT - 54, anchor="w", text="Reproducí algo para verlo acá", font=(FONT, 10)
        )

        self.controls = CanvasTransportControls(
            self.frame, gap=self.CONTROLS_GAP, play_radius=21, side_font_size=14, play_font_size=16
        )

        self.apply_theme(colors)

    def refresh(self) -> None:
        now_playing = _fetch_now_playing()

        if now_playing is None:
            self.frame.itemconfig(self._title_id, text="Nada sonando")
            self.frame.itemconfig(self._artist_id, text="Reproducí algo para verlo acá")
            self._set_thumbnail(None)
            return

        self.frame.itemconfig(self._title_id, text=now_playing.title)
        self.frame.itemconfig(self._artist_id, text=now_playing.artist or "—")
        self._set_thumbnail(now_playing.thumbnail)

    def _set_thumbnail(self, raw: bytes | None) -> None:
        if raw == self._thumbnail_raw:
            return  # misma portada que ya teníamos: no recomponer de nuevo
        self._thumbnail_raw = raw
        image = None
        if raw:
            try:
                image = Image.open(io.BytesIO(raw)).convert("RGB")
            except Exception:
                image = None
        self._thumbnail = image
        self._redraw()

    def _redraw(self) -> None:
        width = self.frame.winfo_width()
        if width <= 1:
            return
        composed = _compose_art_background(self._thumbnail, width, self.HEIGHT, self.colors["surface"])
        self._bg_photo = ImageTk.PhotoImage(composed)
        if self._bg_id is None:
            self._bg_id = self.frame.create_image(0, 0, anchor="nw", image=self._bg_photo)
            self.frame.tag_lower(self._bg_id)
        else:
            self.frame.itemconfig(self._bg_id, image=self._bg_photo)
        self.controls.position(width - self.CONTROLS_MARGIN - self.CONTROLS_GAP, self.HEIGHT - 24)
        self._update_text_style()

    def _update_text_style(self) -> None:
        colors = self.colors
        has_art = self._thumbnail is not None
        self.frame.itemconfig(self._title_id, fill="#ffffff" if has_art else colors["fg"])
        self.frame.itemconfig(self._artist_id, fill="#e2e2e8" if has_art else colors["fg_muted"])
        self.controls.apply_theme(colors, has_art)

    def apply_theme(self, colors: dict) -> None:
        self.colors = colors
        self.frame.configure(bg=colors["surface"], highlightbackground=colors["border"])
        self._redraw()


class Flyout(tk.Toplevel):
    """Panelito de controles que aparece justo arriba del ícono de la bandeja
    del sistema, como el de volumen o red de Windows — solo los controles,
    sin abrir la ventana completa."""

    WIDTH = 280
    ART_HEIGHT = 130
    MARGIN = 10
    CONTROLS_GAP = 36
    CONTROLS_MARGIN = 24

    def __init__(self, master: "MainWindow"):
        super().__init__(master)
        self._master_window = master
        self.overrideredirect(True)
        self.attributes("-topmost", True)
        self.withdraw()

        self._thumbnail_raw: bytes | None = None
        self._thumbnail: Image.Image | None = None
        self._bg_photo = None
        self._bg_id = None
        self.colors: dict = {}

        self.card = tk.Frame(self, bd=0, highlightthickness=1)
        self.card.pack(fill="both", expand=True)

        self.art_canvas = tk.Canvas(self.card, height=self.ART_HEIGHT, highlightthickness=0, bd=0)
        self.art_canvas.pack(fill="x")
        self.art_canvas.bind("<Configure>", lambda e: self._redraw())

        self._title_id = self.art_canvas.create_text(
            16, self.ART_HEIGHT - 58, anchor="w", text="Nada sonando", font=(FONT, 11, "bold")
        )
        self._artist_id = self.art_canvas.create_text(
            16, self.ART_HEIGHT - 40, anchor="w", text="", font=(FONT, 9)
        )

        self.controls = CanvasTransportControls(
            self.art_canvas, gap=self.CONTROLS_GAP, play_radius=18, side_font_size=12, play_font_size=14
        )

        self.master_volume = MasterVolumeControl(self.card)
        self.master_volume.frame.pack(fill="x", padx=16, pady=(10, 16))

        self.bind("<FocusOut>", lambda e: self.hide())

    def refresh(self) -> None:
        now_playing = _fetch_now_playing()
        if now_playing is None:
            self.art_canvas.itemconfig(self._title_id, text="Nada sonando")
            self.art_canvas.itemconfig(self._artist_id, text="")
            self._set_thumbnail(None)
        else:
            self.art_canvas.itemconfig(self._title_id, text=now_playing.title)
            self.art_canvas.itemconfig(self._artist_id, text=now_playing.artist or "—")
            self._set_thumbnail(now_playing.thumbnail)
        self.master_volume.refresh()

    def _set_thumbnail(self, raw: bytes | None) -> None:
        if raw == self._thumbnail_raw:
            return
        self._thumbnail_raw = raw
        image = None
        if raw:
            try:
                image = Image.open(io.BytesIO(raw)).convert("RGB")
            except Exception:
                image = None
        self._thumbnail = image
        self._redraw()

    def _redraw(self) -> None:
        if not self.colors:
            return
        width = self.art_canvas.winfo_width()
        if width <= 1:
            return
        composed = _compose_art_background(self._thumbnail, width, self.ART_HEIGHT, self.colors["surface"])
        self._bg_photo = ImageTk.PhotoImage(composed)
        if self._bg_id is None:
            self._bg_id = self.art_canvas.create_image(0, 0, anchor="nw", image=self._bg_photo)
            self.art_canvas.tag_lower(self._bg_id)
        else:
            self.art_canvas.itemconfig(self._bg_id, image=self._bg_photo)
        self.controls.position(width - self.CONTROLS_MARGIN - self.CONTROLS_GAP, self.ART_HEIGHT - 20)
        self._update_text_style()

    def _update_text_style(self) -> None:
        colors = self.colors
        has_art = self._thumbnail is not None
        self.art_canvas.itemconfig(self._title_id, fill="#ffffff" if has_art else colors["fg"])
        self.art_canvas.itemconfig(self._artist_id, fill="#e2e2e8" if has_art else colors["fg_muted"])
        self.controls.apply_theme(colors, has_art)

    def apply_theme(self, colors: dict) -> None:
        self.colors = colors
        self.configure(bg=colors["bg"])
        self.card.configure(bg=colors["surface"], highlightbackground=colors["border"])
        self.art_canvas.configure(bg=colors["surface"])
        self.master_volume.apply_theme(colors, colors["surface"])
        self._redraw()

    def _position(self) -> None:
        self.update_idletasks()
        height = self.winfo_reqheight()
        work_x, work_y, work_w, work_h = self._master_window._work_area()
        x = work_x + work_w - self.WIDTH - self.MARGIN
        y = work_y + work_h - height - self.MARGIN
        self.geometry(f"{self.WIDTH}x{height}+{x}+{y}")

    def show(self) -> None:
        self.refresh()
        self._position()
        self.deiconify()
        self.lift()
        self.attributes("-topmost", True)
        self.focus_force()

    def hide(self) -> None:
        self.withdraw()

    def toggle(self) -> None:
        if self.state() == "withdrawn":
            self.show()
        else:
            self.hide()


class MainWindow(tk.Tk):
    def __init__(self):
        super().__init__()
        settings = load_settings()
        self.theme_name = settings["theme"]
        self.colors = THEMES[self.theme_name]
        self.list_expanded = settings["list_expanded"]
        self.rows: dict[int, AppRow] = {}

        self._maximized = False
        self._restore_geometry = ""
        self._drag_offset: tuple[int, int] | None = None

        self.title("Play-Z")
        self.resizable(True, True)
        self.minsize(360, 260)
        self.overrideredirect(True)
        self._nudge_taskbar_registration()
        self.protocol("WM_DELETE_WINDOW", self._on_close)

        self.style = ttk.Style(self)
        self.style.theme_use("clam")

        self._icon_photo = ImageTk.PhotoImage(build_icon_image())
        self.iconphoto(True, self._icon_photo)

        self.flyout = Flyout(self)

        self._build_layout()
        self._apply_theme()
        self._apply_list_visibility()
        self._center_window()
        self._setup_tray()
        self._refresh_loop()

    def _setup_tray(self) -> None:
        self.tray = TrayIcon(
            on_toggle_flyout=lambda: self.after(0, self.flyout.toggle),
            on_show_window=lambda: self.after(0, self._show_from_tray),
            on_play_pause=lambda: self.after(0, _do_play_pause),
            on_next=lambda: self.after(0, _do_next),
            on_previous=lambda: self.after(0, _do_previous),
            on_quit=lambda: self.after(0, self._quit),
        )
        self.tray.run_detached()

    def _hide_to_tray(self) -> None:
        self.withdraw()

    def _show_from_tray(self) -> None:
        self.flyout.hide()
        self.deiconify()
        self.overrideredirect(True)
        self.lift()
        self.focus_force()

    def _quit(self) -> None:
        self.tray.stop()
        self.destroy()

    def _nudge_taskbar_registration(self) -> None:
        """Sin esto, una ventana sin bordes (overrideredirect) suele no
        aparecer en la barra de tareas de Windows."""
        self.wm_attributes("-toolwindow", True)
        self.after(10, lambda: self.wm_attributes("-toolwindow", False))

    def _build_layout(self) -> None:
        self._build_titlebar()
        self._build_output_selector()

        self.master_volume = MasterVolumeControl(self)
        self.master_volume.frame.pack(fill="x", padx=20, pady=(0, 16))

        self.media_panel = MediaPanel(self, self.colors)
        self.media_panel.frame.pack(fill="x", padx=20, pady=(0, 16))

        self.section_toggle = tk.Label(
            self, font=(FONT, 9, "bold"), anchor="w", cursor="hand2"
        )
        self.section_toggle.pack(fill="x", padx=22, pady=(0, 8))
        self.section_toggle.bind("<Button-1>", lambda e: self._toggle_list())

        self.list_container = tk.Frame(self, bd=0, highlightthickness=0)

        self.canvas = tk.Canvas(self.list_container, highlightthickness=0, bd=0)
        self.scrollbar = ttk.Scrollbar(
            self.list_container,
            orient="vertical",
            command=self.canvas.yview,
            style="Nice.Vertical.TScrollbar",
        )
        self.rows_frame = tk.Frame(self.canvas, bd=0, highlightthickness=0)

        self.rows_frame.bind(
            "<Configure>", lambda e: self.canvas.configure(scrollregion=self.canvas.bbox("all"))
        )
        self.canvas_window = self.canvas.create_window((0, 0), window=self.rows_frame, anchor="nw")
        self.canvas.bind(
            "<Configure>", lambda e: self.canvas.itemconfig(self.canvas_window, width=e.width)
        )
        self.canvas.configure(yscrollcommand=self.scrollbar.set)
        self.canvas.bind("<Enter>", lambda e: self.canvas.bind_all("<MouseWheel>", self._on_mousewheel))
        self.canvas.bind("<Leave>", lambda e: self.canvas.unbind_all("<MouseWheel>"))

        self.canvas.pack(side="left", fill="both", expand=True)
        self.scrollbar.pack(side="right", fill="y")

        self.empty_label = tk.Label(
            self.rows_frame,
            text="No se detectó audio activo todavía…",
            font=(FONT, 10),
            wraplength=320,
            justify="center",
        )

    def _build_titlebar(self) -> None:
        self.titlebar = tk.Frame(self, bd=0, highlightthickness=0, height=40)
        self.titlebar.pack(fill="x", side="top")
        self.titlebar.pack_propagate(False)

        self.title_label = tk.Label(
            self.titlebar, text="🎵  Play-Z", font=(FONT, 11, "bold"), anchor="w"
        )
        self.title_label.pack(side="left", padx=(16, 0))

        self.close_btn = self._make_titlebar_button(
            self.titlebar, "✕", self._on_close, hover_bg="#e0455c", hover_fg="#ffffff"
        )
        self.close_btn.pack(side="right")

        self.maximize_btn = self._make_titlebar_button(self.titlebar, "☐", self._toggle_maximize)
        self.maximize_btn.pack(side="right")

        self.minimize_btn = self._make_titlebar_button(self.titlebar, "—", self._minimize)
        self.minimize_btn.pack(side="right")

        self.theme_btn = self._make_titlebar_button(self.titlebar, "", self._toggle_theme)
        self.theme_btn.pack(side="right", padx=(0, 10))

        for widget in (self.titlebar, self.title_label):
            widget.bind("<ButtonPress-1>", self._start_move)
            widget.bind("<B1-Motion>", self._do_move)
            widget.bind("<Double-Button-1>", lambda e: self._toggle_maximize())

    def _make_titlebar_button(self, parent, text, command, *, hover_bg=None, hover_fg=None):
        btn = tk.Button(
            parent,
            text=text,
            command=command,
            bd=0,
            highlightthickness=0,
            takefocus=0,
            cursor="hand2",
            font=(FONT, 10),
            width=4,
        )
        btn._hover_bg = hover_bg
        btn._hover_fg = hover_fg
        btn.bind("<Enter>", lambda e, b=btn: self._on_titlebar_btn_enter(b))
        btn.bind("<Leave>", lambda e, b=btn: self._on_titlebar_btn_leave(b))
        return btn

    def _on_titlebar_btn_enter(self, btn: tk.Button) -> None:
        btn.configure(bg=btn._hover_bg or self.colors["surface_alt"], fg=btn._hover_fg or self.colors["fg"])

    def _on_titlebar_btn_leave(self, btn: tk.Button) -> None:
        btn.configure(bg=self.colors["bg"], fg=self.colors["fg_muted"])

    def _build_output_selector(self) -> None:
        """Selector de dispositivo de salida (parlantes/auriculares), como
        el que tiene EarTrumpet arriba de todo."""
        self._device_by_name: dict[str, str] = {}

        self.output_row = tk.Frame(self, bd=0, highlightthickness=0)
        self.output_row.pack(fill="x", padx=20, pady=(0, 8))

        self.output_icon = tk.Label(self.output_row, text="🔊", font=(FONT, 11))
        self.output_icon.pack(side="left")

        self.output_var = tk.StringVar()
        self.output_combo = ttk.Combobox(
            self.output_row,
            textvariable=self.output_var,
            state="readonly",
            font=(FONT, 9),
        )
        self.output_combo.pack(side="left", fill="x", expand=True, padx=(8, 0))
        self.output_combo.bind("<<ComboboxSelected>>", self._on_output_device_selected)

        self._refresh_output_devices()

    def _refresh_output_devices(self) -> None:
        try:
            devices = list_output_devices()
        except Exception:
            devices = []

        self._device_by_name = {d.name: d.id for d in devices}
        self.output_combo.configure(values=list(self._device_by_name.keys()))

        current = next((d.name for d in devices if d.is_default), None)
        # No pisar la selección mientras el desplegable está abierto.
        if current and self.output_var.get() != current:
            self.output_var.set(current)

    def _on_output_device_selected(self, _event) -> None:
        device_id = self._device_by_name.get(self.output_var.get())
        if device_id:
            try:
                set_default_output_device(device_id)
            except Exception:
                pass
        self.output_combo.selection_clear()

    def _start_move(self, event) -> None:
        if self._maximized:
            return
        self._drag_offset = (event.x_root - self.winfo_x(), event.y_root - self.winfo_y())

    def _do_move(self, event) -> None:
        if self._maximized or self._drag_offset is None:
            return
        x = event.x_root - self._drag_offset[0]
        y = event.y_root - self._drag_offset[1]
        self.geometry(f"+{x}+{y}")

    def _on_close(self) -> None:
        self._hide_to_tray()

    def _minimize(self) -> None:
        self.overrideredirect(False)
        self.iconify()
        self.bind("<Map>", self._on_restore_from_iconic)

    def _on_restore_from_iconic(self, _event) -> None:
        if self.state() == "normal":
            self.overrideredirect(True)
            self.unbind("<Map>")

    @staticmethod
    def _work_area() -> tuple[int, int, int, int]:
        rect = ctypes.wintypes.RECT()
        ctypes.windll.user32.SystemParametersInfoW(SPI_GETWORKAREA, 0, ctypes.byref(rect), 0)
        return rect.left, rect.top, rect.right - rect.left, rect.bottom - rect.top

    def _toggle_maximize(self) -> None:
        if self._maximized:
            self.geometry(self._restore_geometry)
            self._maximized = False
            self.maximize_btn.configure(text="☐")
        else:
            self._restore_geometry = self.geometry()
            x, y, width, height = self._work_area()
            self.geometry(f"{width}x{height}+{x}+{y}")
            self._maximized = True
            self.maximize_btn.configure(text="❐")

    def _on_mousewheel(self, event) -> None:
        self.canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")

    def _current_height(self) -> int:
        return EXPANDED_HEIGHT if self.list_expanded else COLLAPSED_HEIGHT

    def _center_window(self) -> None:
        self.update_idletasks()
        width, height = WINDOW_WIDTH, self._current_height()
        x = (self.winfo_screenwidth() - width) // 2
        y = (self.winfo_screenheight() - height) // 2
        self.geometry(f"{width}x{height}+{x}+{y}")

    def _apply_list_visibility(self) -> None:
        if self.list_expanded:
            self.list_container.pack(fill="both", expand=True, padx=20, pady=(0, 18))
        else:
            self.list_container.pack_forget()
        self.section_toggle.configure(
            text=("▾  Aplicaciones con audio" if self.list_expanded else "▸  Aplicaciones con audio")
        )

    def _toggle_list(self) -> None:
        self.list_expanded = not self.list_expanded
        save_settings(list_expanded=self.list_expanded)
        self._apply_list_visibility()

        self.update_idletasks()
        width = self.winfo_width()
        x, y = self.winfo_x(), self.winfo_y()
        self.geometry(f"{width}x{self._current_height()}+{x}+{y}")

    def _toggle_theme(self) -> None:
        self.theme_name = "light" if self.theme_name == "dark" else "dark"
        self.colors = THEMES[self.theme_name]
        save_settings(theme=self.theme_name)
        self._apply_theme()

    def _apply_theme(self) -> None:
        colors = self.colors

        self.configure(bg=colors["bg"])
        self.titlebar.configure(bg=colors["bg"])
        self.title_label.configure(bg=colors["bg"], fg=colors["fg"])
        self.theme_btn.configure(text="☀️" if self.theme_name == "dark" else "🌙")
        for btn in (self.theme_btn, self.minimize_btn, self.maximize_btn, self.close_btn):
            btn.configure(bg=colors["bg"], fg=colors["fg_muted"], activebackground=colors["surface_alt"])
        self.section_toggle.configure(bg=colors["bg"], fg=colors["fg_muted"])
        self.output_row.configure(bg=colors["bg"])
        self.output_icon.configure(bg=colors["bg"], fg=colors["fg_muted"])
        self.master_volume.apply_theme(colors, colors["bg"])
        self.list_container.configure(bg=colors["bg"])
        self.canvas.configure(bg=colors["bg"])
        self.rows_frame.configure(bg=colors["bg"])
        self.empty_label.configure(bg=colors["bg"], fg=colors["fg_muted"])

        self.style.configure(
            "Nice.Vertical.TScrollbar",
            background=colors["border"],
            troughcolor=colors["bg"],
            bordercolor=colors["bg"],
            arrowcolor=colors["fg_muted"],
            relief="flat",
        )
        self.style.configure(
            "TCombobox",
            fieldbackground=colors["surface"],
            background=colors["surface"],
            foreground=colors["fg"],
            arrowcolor=colors["fg_muted"],
            bordercolor=colors["border"],
            lightcolor=colors["surface"],
            darkcolor=colors["surface"],
        )
        self.style.map(
            "TCombobox",
            fieldbackground=[("readonly", colors["surface"])],
            foreground=[("readonly", colors["fg"])],
        )
        # El desplegable del Combobox es un Listbox de Tk puro: se tematiza
        # aparte, vía la option database.
        self.option_add("*TCombobox*Listbox.background", colors["surface"])
        self.option_add("*TCombobox*Listbox.foreground", colors["fg"])
        self.option_add("*TCombobox*Listbox.selectBackground", colors["accent"])
        self.option_add("*TCombobox*Listbox.selectForeground", colors["accent_fg"])
        self.option_add("*TCombobox*Listbox.font", (FONT, 9))

        self.media_panel.apply_theme(colors)
        self.flyout.apply_theme(colors)
        for row in self.rows.values():
            row.apply_theme(colors)

    def _refresh_loop(self) -> None:
        self._refresh_sessions()
        self._refresh_output_devices()
        self.master_volume.refresh()
        self.media_panel.refresh()
        if self.flyout.state() != "withdrawn":
            self.flyout.refresh()
        self.after(REFRESH_MS, self._refresh_loop)

    def _refresh_sessions(self) -> None:
        try:
            sessions = list_app_sessions()
        except Exception:
            sessions = []

        seen_pids: set[int] = set()
        for session in sessions:
            seen_pids.add(session.pid)
            row = self.rows.get(session.pid)
            if row is None:
                row = AppRow(self.rows_frame, session, self.colors)
                self.rows[session.pid] = row
            else:
                row.update_from(session)

        for pid in list(self.rows.keys()):
            if pid not in seen_pids:
                self.rows.pop(pid).destroy()

        if self.rows:
            self.empty_label.pack_forget()
        else:
            self.empty_label.pack(pady=32)


def main() -> None:
    app = MainWindow()
    try:
        app.mainloop()
    finally:
        app.tray.stop()
