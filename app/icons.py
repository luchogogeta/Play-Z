"""Extrae el ícono real de un .exe usando las APIs de Windows.

Todo vía ctypes (sin dependencias nuevas). El método directo con
`win32ui`/`DrawIcon` no conserva bien la transparencia (queda con fondo
negro), así que se usa `GetIconInfo` + `GetDIBits` para leer los píxeles
del ícono con su canal alfa real.
"""

from __future__ import annotations

import ctypes
from ctypes import wintypes

from PIL import Image

_shell32 = ctypes.windll.shell32
_user32 = ctypes.windll.user32
_gdi32 = ctypes.windll.gdi32

DIB_RGB_COLORS = 0
BI_RGB = 0

# Sin argtypes/restype explícitos, ctypes adivina el marshaling de cada
# handle según el valor de Python que le pasás en cada llamada — y para
# HICON/HBITMAP eso a veces revienta con OverflowError según el valor
# numérico del handle (que cambia en cada corrida). Se declaran todos
# a mano para que sea determinístico.
_shell32.ExtractIconExW.argtypes = [
    wintypes.LPCWSTR,
    ctypes.c_int,
    ctypes.POINTER(wintypes.HICON),
    ctypes.POINTER(wintypes.HICON),
    wintypes.UINT,
]
_shell32.ExtractIconExW.restype = wintypes.UINT

_user32.DestroyIcon.argtypes = [wintypes.HICON]
_user32.DestroyIcon.restype = wintypes.BOOL

_user32.GetDC.argtypes = [wintypes.HWND]
_user32.GetDC.restype = wintypes.HDC

_user32.ReleaseDC.argtypes = [wintypes.HWND, wintypes.HDC]
_user32.ReleaseDC.restype = ctypes.c_int

_gdi32.DeleteObject.argtypes = [wintypes.HGDIOBJ]
_gdi32.DeleteObject.restype = wintypes.BOOL


class _IconInfo(ctypes.Structure):
    _fields_ = [
        ("fIcon", wintypes.BOOL),
        ("xHotspot", wintypes.DWORD),
        ("yHotspot", wintypes.DWORD),
        ("hbmMask", wintypes.HBITMAP),
        ("hbmColor", wintypes.HBITMAP),
    ]


class _Bitmap(ctypes.Structure):
    _fields_ = [
        ("bmType", ctypes.c_long),
        ("bmWidth", ctypes.c_long),
        ("bmHeight", ctypes.c_long),
        ("bmWidthBytes", ctypes.c_long),
        ("bmPlanes", wintypes.WORD),
        ("bmBitsPixel", wintypes.WORD),
        ("bmBits", ctypes.c_void_p),
    ]


class _BitmapInfoHeader(ctypes.Structure):
    _fields_ = [
        ("biSize", wintypes.DWORD),
        ("biWidth", ctypes.c_long),
        ("biHeight", ctypes.c_long),
        ("biPlanes", wintypes.WORD),
        ("biBitCount", wintypes.WORD),
        ("biCompression", wintypes.DWORD),
        ("biSizeImage", wintypes.DWORD),
        ("biXPelsPerMeter", ctypes.c_long),
        ("biYPelsPerMeter", ctypes.c_long),
        ("biClrUsed", wintypes.DWORD),
        ("biClrImportant", wintypes.DWORD),
    ]


class _BitmapInfo(ctypes.Structure):
    _fields_ = [("bmiHeader", _BitmapInfoHeader), ("bmiColors", wintypes.DWORD * 3)]


_user32.GetIconInfo.argtypes = [wintypes.HICON, ctypes.POINTER(_IconInfo)]
_user32.GetIconInfo.restype = wintypes.BOOL

_gdi32.GetObjectW.argtypes = [wintypes.HGDIOBJ, ctypes.c_int, ctypes.c_void_p]
_gdi32.GetObjectW.restype = ctypes.c_int

_gdi32.GetDIBits.argtypes = [
    wintypes.HDC,
    wintypes.HBITMAP,
    wintypes.UINT,
    wintypes.UINT,
    ctypes.c_void_p,
    ctypes.POINTER(_BitmapInfo),
    wintypes.UINT,
]
_gdi32.GetDIBits.restype = ctypes.c_int

_icon_cache: dict[str, Image.Image | None] = {}


def _hicon_to_image(hicon) -> Image.Image | None:
    icon_info = _IconInfo()
    if not _user32.GetIconInfo(hicon, ctypes.byref(icon_info)):
        return None
    try:
        bmp = _Bitmap()
        if not _gdi32.GetObjectW(icon_info.hbmColor, ctypes.sizeof(_Bitmap), ctypes.byref(bmp)):
            return None
        width, height = bmp.bmWidth, bmp.bmHeight
        if width <= 0 or height <= 0:
            return None

        bmi = _BitmapInfo()
        bmi.bmiHeader.biSize = ctypes.sizeof(_BitmapInfoHeader)
        bmi.bmiHeader.biWidth = width
        bmi.bmiHeader.biHeight = -height  # negativo = filas de arriba hacia abajo
        bmi.bmiHeader.biPlanes = 1
        bmi.bmiHeader.biBitCount = 32
        bmi.bmiHeader.biCompression = BI_RGB

        buffer = ctypes.create_string_buffer(width * height * 4)
        hdc = _user32.GetDC(None)
        try:
            _gdi32.GetDIBits(
                hdc, icon_info.hbmColor, 0, height, buffer, ctypes.byref(bmi), DIB_RGB_COLORS
            )
        finally:
            _user32.ReleaseDC(None, hdc)

        return Image.frombuffer("RGBA", (width, height), buffer.raw, "raw", "BGRA", 0, 1)
    finally:
        _gdi32.DeleteObject(icon_info.hbmColor)
        _gdi32.DeleteObject(icon_info.hbmMask)


def extract_app_icon(exe_path: str, size: int = 36) -> Image.Image | None:
    """Ícono real de una app (con caché por ruta de ejecutable).

    Devuelve None si no se pudo extraer (proceso protegido, ruta
    inaccesible, etc.) — quien llame debe tener un respaldo visual.
    """
    if not exe_path:
        return None

    if exe_path not in _icon_cache:
        large = (wintypes.HICON * 1)()
        small = (wintypes.HICON * 1)()
        try:
            count = _shell32.ExtractIconExW(exe_path, 0, large, small, 1)
        except Exception:
            count = 0

        hicon = (large[0] or small[0]) if count else None
        leftover = small[0] if (hicon and hicon != small[0] and small[0]) else None

        image = None
        try:
            if hicon:
                image = _hicon_to_image(hicon)
        except Exception:
            image = None
        finally:
            if hicon:
                _user32.DestroyIcon(hicon)
            if leftover:
                _user32.DestroyIcon(leftover)

        _icon_cache[exe_path] = image

    cached = _icon_cache[exe_path]
    return cached.resize((size, size), Image.LANCZOS) if cached else None
