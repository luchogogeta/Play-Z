"""Atajo de teclado global para traer la ventana grande al frente, aunque
Play-Z no tenga el foco (por ejemplo, estando en medio de un juego) — como
el Alt+Z de GeForce Experience.

Usa RegisterHotKey de Windows en un hilo propio con su propio loop de
mensajes: RegisterHotKey asocia el atajo a la cola de mensajes del hilo que
lo pide, así que todo (registrar, cambiar, escuchar) tiene que pasar por
ese mismo hilo — se coordina posteando mensajes, no llamando directo desde
otro hilo.
"""

from __future__ import annotations

import ctypes
import threading
from ctypes import wintypes

user32 = ctypes.windll.user32
kernel32 = ctypes.windll.kernel32

WM_HOTKEY = 0x0312
WM_QUIT = 0x0012
_WM_CHANGE_HOTKEY = 0x8000 + 1  # WM_APP + 1, para uso privado nuestro

MOD_ALT = 0x0001
MOD_CONTROL = 0x0002
MOD_SHIFT = 0x0004
MOD_WIN = 0x0008
MOD_NOREPEAT = 0x4000

_HOTKEY_ID = 1


class _MSG(ctypes.Structure):
    _fields_ = [
        ("hwnd", wintypes.HWND),
        ("message", wintypes.UINT),
        ("wParam", wintypes.WPARAM),
        ("lParam", wintypes.LPARAM),
        ("time", wintypes.DWORD),
        ("pt", wintypes.POINT),
    ]


user32.RegisterHotKey.argtypes = [wintypes.HWND, ctypes.c_int, wintypes.UINT, wintypes.UINT]
user32.RegisterHotKey.restype = wintypes.BOOL
user32.UnregisterHotKey.argtypes = [wintypes.HWND, ctypes.c_int]
user32.UnregisterHotKey.restype = wintypes.BOOL
user32.GetMessageW.argtypes = [ctypes.POINTER(_MSG), wintypes.HWND, wintypes.UINT, wintypes.UINT]
user32.GetMessageW.restype = ctypes.c_int
user32.PeekMessageW.argtypes = [
    ctypes.POINTER(_MSG),
    wintypes.HWND,
    wintypes.UINT,
    wintypes.UINT,
    wintypes.UINT,
]
user32.PeekMessageW.restype = wintypes.BOOL
user32.TranslateMessage.argtypes = [ctypes.POINTER(_MSG)]
user32.TranslateMessage.restype = wintypes.BOOL
user32.DispatchMessageW.argtypes = [ctypes.POINTER(_MSG)]
user32.DispatchMessageW.restype = ctypes.c_long
user32.PostThreadMessageW.argtypes = [wintypes.DWORD, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM]
user32.PostThreadMessageW.restype = wintypes.BOOL
kernel32.GetCurrentThreadId.restype = wintypes.DWORD

_MODIFIER_NAMES = {
    "alt": MOD_ALT,
    "ctrl": MOD_CONTROL,
    "control": MOD_CONTROL,
    "shift": MOD_SHIFT,
    "win": MOD_WIN,
    "windows": MOD_WIN,
}

_VK_NAMES: dict[str, int] = {}
for _i in range(26):
    _VK_NAMES[chr(ord("a") + _i)] = 0x41 + _i
for _i in range(10):
    _VK_NAMES[str(_i)] = 0x30 + _i
for _i in range(1, 25):
    _VK_NAMES[f"f{_i}"] = 0x70 + _i - 1

DEFAULT_SHORTCUT = "alt+z"


def parse_shortcut(text: str) -> tuple[int, int] | None:
    """'Alt+Z' -> (MOD_ALT, VK del 'Z'). None si el texto no se entiende.

    Se exige al menos un modificador (Alt/Ctrl/Shift/Win) para no terminar
    registrando una tecla suelta que se use para escribir normalmente.
    """
    parts = [p.strip().lower() for p in text.split("+") if p.strip()]
    if len(parts) < 2:
        return None
    *mods, key = parts
    modifiers = 0
    for mod in mods:
        if mod not in _MODIFIER_NAMES:
            return None
        modifiers |= _MODIFIER_NAMES[mod]
    vk = _VK_NAMES.get(key)
    if vk is None:
        return None
    return modifiers, vk


class HotkeyListener:
    """Escucha el atajo global en un hilo propio y llama a `callback` (en
    ESE hilo) cada vez que se presiona — quien reciba el callback es
    responsable de pasarlo de vuelta al hilo de Tkinter."""

    def __init__(self, callback, *, initial_shortcut: str = DEFAULT_SHORTCUT):
        self._callback = callback
        self._thread_id: int | None = None
        self._current_modifiers = 0
        self._current_vk = 0
        self._result_event = threading.Event()
        self._last_result = False
        ready = threading.Event()
        parsed = parse_shortcut(initial_shortcut) or parse_shortcut(DEFAULT_SHORTCUT)
        self._initial = parsed

        self._thread = threading.Thread(
            target=self._run, args=(ready,), daemon=True, name="hotkey-listener"
        )
        self._thread.start()
        ready.wait(timeout=2)

    @property
    def is_active(self) -> bool:
        return self._current_vk != 0

    def _run(self, ready: threading.Event) -> None:
        self._thread_id = kernel32.GetCurrentThreadId()
        msg = _MSG()
        # Fuerza la creación de la cola de mensajes de este hilo antes de
        # que nadie (otro hilo) intente postearle nada.
        user32.PeekMessageW(ctypes.byref(msg), None, 0, 0, 0)
        ready.set()

        if self._initial:
            self._do_register(*self._initial)

        while True:
            ret = user32.GetMessageW(ctypes.byref(msg), None, 0, 0)
            if ret in (0, -1):
                break
            if msg.message == WM_HOTKEY:
                try:
                    self._callback()
                except Exception:
                    pass
            elif msg.message == _WM_CHANGE_HOTKEY:
                self._last_result = self._do_register(msg.wParam, msg.lParam)
                self._result_event.set()
            user32.TranslateMessage(ctypes.byref(msg))
            user32.DispatchMessageW(ctypes.byref(msg))

        if self._current_vk:
            user32.UnregisterHotKey(None, _HOTKEY_ID)

    def _do_register(self, modifiers: int, vk: int) -> bool:
        if self._current_vk:
            user32.UnregisterHotKey(None, _HOTKEY_ID)
            self._current_modifiers = self._current_vk = 0
        ok = bool(user32.RegisterHotKey(None, _HOTKEY_ID, modifiers | MOD_NOREPEAT, vk))
        if ok:
            self._current_modifiers, self._current_vk = modifiers, vk
        return ok

    def set_shortcut(self, modifiers: int, vk: int, timeout: float = 2.0) -> bool:
        """Cambia el atajo activo. Devuelve False si Windows lo rechaza
        (por ejemplo, porque otro programa ya lo tiene registrado)."""
        if self._thread_id is None:
            return False
        self._result_event.clear()
        user32.PostThreadMessageW(self._thread_id, _WM_CHANGE_HOTKEY, modifiers, vk)
        if self._result_event.wait(timeout):
            return self._last_result
        return False

    def stop(self) -> None:
        if self._thread_id:
            user32.PostThreadMessageW(self._thread_id, WM_QUIT, 0, 0)
