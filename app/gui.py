"""Interfaz gráfica (Tkinter): mezclador por app + controles multimedia."""

from __future__ import annotations

import tkinter as tk
from tkinter import ttk

from .audio_sessions import AppAudioSession, list_app_sessions
from .media_control import next_track, play_pause, previous_track, run as run_async
from .media_control import get_now_playing

REFRESH_MS = 1500


class SessionRow:
    """Una fila de la lista: nombre de app + slider de volumen + mute."""

    def __init__(self, parent: tk.Widget, session: AppAudioSession):
        self.pid = session.pid
        self._dragging = False

        self.frame = ttk.Frame(parent, padding=(8, 4))
        self.frame.columnconfigure(1, weight=1)

        self.name_label = ttk.Label(self.frame, text=session.name, width=24)
        self.name_label.grid(row=0, column=0, sticky="w")

        self.volume_var = tk.DoubleVar(value=session.volume * 100)
        self.scale = ttk.Scale(
            self.frame,
            from_=0,
            to=100,
            orient="horizontal",
            variable=self.volume_var,
            command=self._on_scale_move,
        )
        self.scale.grid(row=0, column=1, sticky="ew", padx=8)
        self.scale.bind("<ButtonPress-1>", lambda e: setattr(self, "_dragging", True))
        self.scale.bind("<ButtonRelease-1>", self._on_scale_release)

        self.mute_var = tk.BooleanVar(value=session.muted)
        self.mute_check = ttk.Checkbutton(
            self.frame, text="Mute", variable=self.mute_var, command=self._on_mute_toggle
        )
        self.mute_check.grid(row=0, column=2, padx=4)

        self._session = session

    def _on_scale_move(self, _value: str) -> None:
        if self._dragging:
            self._session.set_volume(self.volume_var.get() / 100)

    def _on_scale_release(self, _event) -> None:
        self._dragging = False
        self._session.set_volume(self.volume_var.get() / 100)

    def _on_mute_toggle(self) -> None:
        self._session.set_muted(self.mute_var.get())

    def update_from(self, session: AppAudioSession) -> None:
        self._session = session
        if not self._dragging:
            self.volume_var.set(session.volume * 100)
        self.mute_var.set(session.muted)

    def destroy(self) -> None:
        self.frame.destroy()


class MediaPanel:
    """Título/artista de lo que suena + botones de reproducción."""

    def __init__(self, parent: tk.Widget):
        self.frame = ttk.Frame(parent, padding=10)
        self.frame.columnconfigure(0, weight=1)

        self.title_label = ttk.Label(
            self.frame, text="Nada sonando", font=("Segoe UI", 12, "bold")
        )
        self.title_label.grid(row=0, column=0, sticky="w")

        self.artist_label = ttk.Label(self.frame, text="")
        self.artist_label.grid(row=1, column=0, sticky="w")

        buttons = ttk.Frame(self.frame)
        buttons.grid(row=2, column=0, pady=(8, 0))

        ttk.Button(buttons, text="⏮", width=4, command=self._previous).grid(row=0, column=0)
        ttk.Button(buttons, text="⏯", width=4, command=self._play_pause).grid(row=0, column=1)
        ttk.Button(buttons, text="⏭", width=4, command=self._next).grid(row=0, column=2)

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
            self.title_label.config(text="Nada sonando")
            self.artist_label.config(text="")
            return

        self.title_label.config(text=now_playing.title)
        self.artist_label.config(text=now_playing.artist)


class MainWindow(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Reproductor")
        self.geometry("420x480")
        self.minsize(360, 320)

        self.media_panel = MediaPanel(self)
        self.media_panel.frame.pack(fill="x")

        ttk.Separator(self).pack(fill="x")

        ttk.Label(self, text="Aplicaciones con audio", padding=(8, 6)).pack(anchor="w")

        list_container = ttk.Frame(self)
        list_container.pack(fill="both", expand=True)

        canvas = tk.Canvas(list_container, highlightthickness=0)
        scrollbar = ttk.Scrollbar(list_container, orient="vertical", command=canvas.yview)
        self.rows_frame = ttk.Frame(canvas)

        self.rows_frame.bind(
            "<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )
        canvas.create_window((0, 0), window=self.rows_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)

        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

        self.rows: dict[int, SessionRow] = {}

        self._refresh_loop()

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
                row = SessionRow(self.rows_frame, session)
                row.frame.pack(fill="x")
                self.rows[session.pid] = row
            else:
                row.update_from(session)

        for pid in list(self.rows.keys()):
            if pid not in seen_pids:
                self.rows.pop(pid).destroy()


def main() -> None:
    app = MainWindow()
    app.mainloop()
