"""Ventana de configuración: idioma, tema, atajo global y arranque con Windows."""

from __future__ import annotations

import tkinter as tk
from tkinter import ttk
from typing import Callable

from . import startup
from .i18n import LANGUAGE_NAMES, get_language, set_language, tr
from .theme import FONT, save_settings


class SettingsWindow(tk.Toplevel):
    def __init__(
        self,
        master: tk.Tk,
        *,
        colors: dict,
        theme_name: str,
        current_shortcut: str,
        shortcut_active: bool,
        on_theme_change: Callable[[str], None],
        on_language_change: Callable[[], None],
        on_shortcut_apply: Callable[[str], bool],
    ):
        super().__init__(master)
        self._on_theme_change = on_theme_change
        self._on_language_change = on_language_change
        self._on_shortcut_apply = on_shortcut_apply
        self._colors = colors

        self.resizable(False, False)
        self.transient(master)

        self._build(theme_name, current_shortcut, shortcut_active)
        self.apply_theme(colors)
        self._center_over(master)

        # El grab se pide después de que la ventana ya es visible; pedirlo
        # antes suele fallar en Windows con "grab failed: window not viewable".
        self.after(10, self._grab)
        self.protocol("WM_DELETE_WINDOW", self.destroy)

    def _grab(self) -> None:
        try:
            self.grab_set()
        except tk.TclError:
            pass

    def _build(self, theme_name: str, current_shortcut: str, shortcut_active: bool) -> None:
        self.container = tk.Frame(self, padx=24, pady=20)
        self.container.pack(fill="both", expand=True)
        self.container.columnconfigure(0, weight=1)

        self.language_label = tk.Label(self.container, font=(FONT, 10, "bold"), anchor="w")
        self.language_label.grid(row=0, column=0, sticky="w", pady=(0, 6))

        self._name_to_code = {v: k for k, v in LANGUAGE_NAMES.items()}
        self.language_var = tk.StringVar(value=LANGUAGE_NAMES.get(get_language(), get_language()))
        self.language_combo = ttk.Combobox(
            self.container,
            textvariable=self.language_var,
            state="readonly",
            values=list(LANGUAGE_NAMES.values()),
            font=(FONT, 9),
            width=22,
        )
        self.language_combo.grid(row=1, column=0, sticky="ew", pady=(0, 18))
        self.language_combo.bind("<<ComboboxSelected>>", self._on_language_selected)

        self.theme_label = tk.Label(self.container, font=(FONT, 10, "bold"), anchor="w")
        self.theme_label.grid(row=2, column=0, sticky="w", pady=(0, 6))

        self.theme_var = tk.StringVar(value=theme_name)
        self.theme_row = tk.Frame(self.container)
        self.theme_row.grid(row=3, column=0, sticky="w", pady=(0, 18))
        self.light_radio = tk.Radiobutton(
            self.theme_row,
            value="light",
            variable=self.theme_var,
            command=self._on_theme_selected,
            font=(FONT, 9),
            bd=0,
            highlightthickness=0,
            cursor="hand2",
        )
        self.light_radio.pack(side="left", padx=(0, 18))
        self.dark_radio = tk.Radiobutton(
            self.theme_row,
            value="dark",
            variable=self.theme_var,
            command=self._on_theme_selected,
            font=(FONT, 9),
            bd=0,
            highlightthickness=0,
            cursor="hand2",
        )
        self.dark_radio.pack(side="left")

        self.shortcut_label = tk.Label(self.container, font=(FONT, 10, "bold"), anchor="w")
        self.shortcut_label.grid(row=4, column=0, sticky="w", pady=(0, 6))

        shortcut_row = tk.Frame(self.container)
        shortcut_row.grid(row=5, column=0, sticky="ew", pady=(0, 2))
        shortcut_row.columnconfigure(0, weight=1)
        self._shortcut_row = shortcut_row

        self.shortcut_var = tk.StringVar(value=current_shortcut)
        self.shortcut_entry = tk.Entry(
            shortcut_row, textvariable=self.shortcut_var, font=(FONT, 9), bd=1, relief="solid"
        )
        self.shortcut_entry.grid(row=0, column=0, sticky="ew", padx=(0, 8))
        self.shortcut_entry.bind("<Return>", lambda e: self._on_shortcut_applied())

        self.shortcut_apply_btn = tk.Button(
            shortcut_row,
            command=self._on_shortcut_applied,
            font=(FONT, 9),
            bd=0,
            highlightthickness=0,
            cursor="hand2",
        )
        self.shortcut_apply_btn.grid(row=0, column=1)

        self.shortcut_hint_label = tk.Label(self.container, font=(FONT, 8), anchor="w")
        self.shortcut_hint_label.grid(row=6, column=0, sticky="w", pady=(4, 0))

        self.shortcut_status_label = tk.Label(self.container, font=(FONT, 8, "bold"), anchor="w")
        self.shortcut_status_label.grid(row=7, column=0, sticky="w", pady=(2, 22))
        self._set_shortcut_status(active=shortcut_active, invalid=False)

        self.startup_var = tk.BooleanVar(value=startup.is_enabled())
        self.startup_check = tk.Checkbutton(
            self.container,
            variable=self.startup_var,
            command=self._on_startup_toggled,
            font=(FONT, 9),
            bd=0,
            highlightthickness=0,
            cursor="hand2",
        )
        self.startup_check.grid(row=8, column=0, sticky="w", pady=(0, 22))

        self.close_btn = tk.Button(
            self.container,
            command=self.destroy,
            font=(FONT, 9),
            bd=0,
            highlightthickness=0,
            cursor="hand2",
            width=12,
        )
        self.close_btn.grid(row=9, column=0, sticky="e")

        self._refresh_texts()

    def _refresh_texts(self) -> None:
        self.title(tr("settings_title"))
        self.language_label.configure(text=tr("settings_language"))
        self.theme_label.configure(text=tr("settings_theme"))
        self.light_radio.configure(text=tr("settings_theme_light"))
        self.dark_radio.configure(text=tr("settings_theme_dark"))
        self.shortcut_label.configure(text=tr("settings_shortcut"))
        self.shortcut_hint_label.configure(text=tr("settings_shortcut_hint"))
        self.shortcut_apply_btn.configure(text=tr("settings_shortcut_apply"))
        self.startup_check.configure(text=tr("settings_startup"))
        self.close_btn.configure(text=tr("settings_close"))

    def _on_language_selected(self, _event) -> None:
        code = self._name_to_code.get(self.language_var.get())
        if code and code != get_language():
            set_language(code)
            save_settings(language=code)
            self._refresh_texts()
            self._on_language_change()
        self.language_combo.selection_clear()

    def _on_theme_selected(self) -> None:
        self._on_theme_change(self.theme_var.get())

    def _on_shortcut_applied(self) -> None:
        text = self.shortcut_var.get().strip()
        ok = self._on_shortcut_apply(text)
        self._set_shortcut_status(active=ok, invalid=not ok)

    def _set_shortcut_status(self, *, active: bool, invalid: bool) -> None:
        colors = self._colors
        if active:
            key, color_key = "settings_shortcut_active", "accent"
        elif invalid:
            key, color_key = "settings_shortcut_invalid", "danger"
        else:
            key, color_key = "settings_shortcut_inactive", "danger"
        self.shortcut_status_label.configure(text=tr(key), fg=colors.get(color_key, colors["fg_muted"]))

    def _on_startup_toggled(self) -> None:
        try:
            startup.set_enabled(self.startup_var.get())
        except OSError:
            # No se pudo escribir el registro: revertir el check visualmente.
            self.startup_var.set(not self.startup_var.get())

    def apply_theme(self, colors: dict) -> None:
        self._colors = colors
        self.configure(bg=colors["bg"])
        self.container.configure(bg=colors["bg"])
        self.theme_row.configure(bg=colors["bg"])
        self._shortcut_row.configure(bg=colors["bg"])
        for widget in (self.language_label, self.theme_label, self.shortcut_label):
            widget.configure(bg=colors["bg"], fg=colors["fg"])
        self.shortcut_hint_label.configure(bg=colors["bg"], fg=colors["fg_muted"])
        for widget in (self.light_radio, self.dark_radio, self.startup_check):
            widget.configure(
                bg=colors["bg"],
                fg=colors["fg"],
                selectcolor=colors["surface_alt"],
                activebackground=colors["bg"],
                activeforeground=colors["fg"],
            )
        self.shortcut_entry.configure(
            bg=colors["surface"], fg=colors["fg"], insertbackground=colors["fg"]
        )
        self.shortcut_apply_btn.configure(
            bg=colors["surface"], fg=colors["fg"], activebackground=colors["surface_alt"]
        )
        self.close_btn.configure(
            bg=colors["surface"], fg=colors["fg"], activebackground=colors["surface_alt"]
        )
        # el color del status depende de si está activo/inválido, no solo del tema
        self.shortcut_status_label.configure(bg=colors["bg"])

    def _center_over(self, master: tk.Tk) -> None:
        self.update_idletasks()
        width, height = self.winfo_reqwidth(), self.winfo_reqheight()
        x = master.winfo_rootx() + (master.winfo_width() - width) // 2
        y = master.winfo_rooty() + (master.winfo_height() - height) // 2
        self.geometry(f"{width}x{height}+{x}+{y}")
