"""Interfaz gráfica (Tkinter): mezclador por app + controles multimedia.

Diseño tipo tarjetas, con tema claro/oscuro intercambiable (se recuerda
entre sesiones) y un poco de identidad visual (avatares por app, acento
de color, tipografía consistente).
"""

from __future__ import annotations

import ctypes
import ctypes.wintypes
import tkinter as tk
from tkinter import ttk

from .audio_sessions import AppAudioSession, list_app_sessions
from .media_control import get_now_playing, next_track, play_pause, previous_track
from .media_control import run as run_async
from .theme import FONT, THEMES, avatar_color, load_settings, save_settings

REFRESH_MS = 1500
WINDOW_WIDTH = 460
EXPANDED_HEIGHT = 640
COLLAPSED_HEIGHT = 330
SPI_GETWORKAREA = 0x0030


class AppRow:
    """Tarjeta de una app: avatar, nombre, % de volumen, slider y mute."""

    def __init__(self, parent: tk.Widget, session: AppAudioSession, colors: dict):
        self.pid = session.pid
        self._dragging = False
        self._session = session
        self.colors = colors

        self.card = tk.Frame(parent, bd=0, highlightthickness=1)
        self.card.pack(fill="x", pady=(0, 10))
        self.card.columnconfigure(1, weight=1)

        self.avatar = tk.Canvas(self.card, width=36, height=36, highlightthickness=0, bd=0)
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

        self.volume_var = tk.DoubleVar(value=session.volume * 100)
        self.scale = ttk.Scale(
            self.card,
            from_=0,
            to=100,
            orient="horizontal",
            variable=self.volume_var,
            command=self._on_scale_move,
            style="Vol.Horizontal.TScale",
        )
        self.scale.grid(row=1, column=1, columnspan=2, sticky="ew", padx=(0, 8), pady=(2, 14))
        self.scale.bind("<ButtonPress-1>", lambda e: setattr(self, "_dragging", True))
        self.scale.bind("<ButtonRelease-1>", self._on_scale_release)

        self._draw_avatar()
        self._set_percent_label(session.volume)
        self.apply_theme(colors)

    def _draw_avatar(self) -> None:
        self.avatar.delete("all")
        self.avatar.create_oval(2, 2, 34, 34, fill=avatar_color(self._session.name), outline="")
        letter = (self._session.name[:1] or "?").upper()
        self.avatar.create_text(18, 18, text=letter, fill="#ffffff", font=(FONT, 12, "bold"))

    def _set_percent_label(self, volume: float) -> None:
        self.percent_label.configure(text=f"{round(volume * 100)}%")

    def _on_scale_move(self, value: str) -> None:
        volume = float(value) / 100
        self._set_percent_label(volume)
        if self._dragging:
            self._session.set_volume(volume)

    def _on_scale_release(self, _event) -> None:
        self._dragging = False
        self._session.set_volume(self.volume_var.get() / 100)

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
        if not self._dragging:
            self.volume_var.set(session.volume * 100)
            self._set_percent_label(session.volume)
        self._update_mute_button(session.muted)

    def apply_theme(self, colors: dict) -> None:
        self.colors = colors
        self.card.configure(bg=colors["surface"], highlightbackground=colors["border"])
        self.avatar.configure(bg=colors["surface"])
        self.name_label.configure(bg=colors["surface"], fg=colors["fg"])
        self.percent_label.configure(bg=colors["surface"], fg=colors["fg_muted"])
        self.mute_btn.configure(bg=colors["surface"], activebackground=colors["surface_alt"])
        self._update_mute_button(self._session.muted)

    def destroy(self) -> None:
        self.card.destroy()


class MediaPanel:
    """Tarjeta superior: qué está sonando + play/pause/siguiente/anterior."""

    def __init__(self, parent: tk.Widget, colors: dict):
        self.colors = colors
        self.frame = tk.Frame(parent, bd=0, highlightthickness=1)
        self.frame.columnconfigure(1, weight=1)

        self.art = tk.Canvas(self.frame, width=56, height=56, highlightthickness=0, bd=0)
        self.art.grid(row=0, column=0, rowspan=2, padx=16, pady=16)

        self.title_label = tk.Label(self.frame, text="Nada sonando", anchor="w", font=(FONT, 13, "bold"))
        self.title_label.grid(row=0, column=1, sticky="ew", pady=(16, 0), padx=(0, 16))

        self.artist_label = tk.Label(
            self.frame, text="Reproducí algo para verlo acá", anchor="w", font=(FONT, 10)
        )
        self.artist_label.grid(row=1, column=1, sticky="ew", padx=(0, 16))

        self.controls = tk.Frame(self.frame, bd=0, highlightthickness=0)
        self.controls.grid(row=2, column=0, columnspan=2, pady=(4, 18))

        self.prev_btn = self._make_button(self.controls, "⏮", self._previous, size=13)
        self.prev_btn.grid(row=0, column=0, padx=6)

        self.play_btn = self._make_button(self.controls, "⏯", self._play_pause, size=16, bold=True)
        self.play_btn.grid(row=0, column=1, padx=10)

        self.next_btn = self._make_button(self.controls, "⏭", self._next, size=13)
        self.next_btn.grid(row=0, column=2, padx=6)

        self.apply_theme(colors)

    @staticmethod
    def _make_button(parent, text, command, *, size, bold=False):
        weight = "bold" if bold else "normal"
        return tk.Button(
            parent,
            text=text,
            command=command,
            bd=0,
            highlightthickness=0,
            takefocus=0,
            cursor="hand2",
            width=3,
            font=(FONT, size, weight),
        )

    def _previous(self) -> None:
        run_async(previous_track())

    def _play_pause(self) -> None:
        run_async(play_pause())

    def _next(self) -> None:
        run_async(next_track())

    def refresh(self) -> None:
        try:
            now_playing = run_async(get_now_playing())
        except Exception:
            now_playing = None

        if now_playing is None:
            self.title_label.configure(text="Nada sonando")
            self.artist_label.configure(text="Reproducí algo para verlo acá")
            return

        self.title_label.configure(text=now_playing.title)
        self.artist_label.configure(text=now_playing.artist or "—")

    def apply_theme(self, colors: dict) -> None:
        self.colors = colors
        self.frame.configure(bg=colors["surface"], highlightbackground=colors["border"])
        self.art.configure(bg=colors["surface"])
        self.art.delete("all")
        self.art.create_rectangle(2, 2, 54, 54, fill=colors["surface_alt"], outline="")
        self.art.create_text(28, 28, text="♪", fill=colors["accent"], font=(FONT, 20, "bold"))
        self.title_label.configure(bg=colors["surface"], fg=colors["fg"])
        self.artist_label.configure(bg=colors["surface"], fg=colors["fg_muted"])
        self.controls.configure(bg=colors["surface"])
        for btn in (self.prev_btn, self.next_btn):
            btn.configure(bg=colors["surface"], fg=colors["fg_muted"], activebackground=colors["surface_alt"])
        self.play_btn.configure(bg=colors["accent"], fg=colors["accent_fg"], activebackground=colors["accent"])


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

        self.title("Reproductor")
        self.resizable(True, True)
        self.minsize(360, 260)
        self.overrideredirect(True)
        self._nudge_taskbar_registration()
        self.protocol("WM_DELETE_WINDOW", self._on_close)

        self.style = ttk.Style(self)
        self.style.theme_use("clam")

        self._build_layout()
        self._apply_theme()
        self._apply_list_visibility()
        self._center_window()
        self._refresh_loop()

    def _nudge_taskbar_registration(self) -> None:
        """Sin esto, una ventana sin bordes (overrideredirect) suele no
        aparecer en la barra de tareas de Windows."""
        self.wm_attributes("-toolwindow", True)
        self.after(10, lambda: self.wm_attributes("-toolwindow", False))

    def _build_layout(self) -> None:
        self._build_titlebar()

        self.media_panel = MediaPanel(self, self.colors)
        self.media_panel.frame.pack(fill="x", padx=20, pady=(14, 16))

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
            self.titlebar, text="🎵  Reproductor", font=(FONT, 11, "bold"), anchor="w"
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
        self.destroy()

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
        self.list_container.configure(bg=colors["bg"])
        self.canvas.configure(bg=colors["bg"])
        self.rows_frame.configure(bg=colors["bg"])
        self.empty_label.configure(bg=colors["bg"], fg=colors["fg_muted"])

        self.style.configure(
            "Vol.Horizontal.TScale",
            troughcolor=colors["surface_alt"],
            background=colors["surface"],
            lightcolor=colors["accent"],
            darkcolor=colors["accent"],
            bordercolor=colors["surface"],
        )
        self.style.configure(
            "Nice.Vertical.TScrollbar",
            background=colors["border"],
            troughcolor=colors["bg"],
            bordercolor=colors["bg"],
            arrowcolor=colors["fg_muted"],
            relief="flat",
        )

        self.media_panel.apply_theme(colors)
        for row in self.rows.values():
            row.apply_theme(colors)

    def _refresh_loop(self) -> None:
        self._refresh_sessions()
        self.media_panel.refresh()
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
    app.mainloop()
