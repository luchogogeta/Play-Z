# Reproductor

Un reproductor/mezclador pequeño para Windows: controla el volumen de cada
aplicación por separado y maneja la reproducción (play/pause, siguiente,
anterior) de lo que esté sonando, todo desde una sola ventana.

## Descripción

- **Volumen por aplicación**: lista las apps que tienen audio activo (Spotify,
  el navegador, un juego, Discord, etc.) y permite subir, bajar o silenciar
  cada una de forma independiente al volumen general de Windows. Usa las
  APIs de Windows Core Audio a través de [`pycaw`](https://github.com/AndreMiras/pycaw).
- **Controles multimedia**: muestra el título y artista de lo que se está
  reproduciendo y permite reproducir/pausar, pasar a la siguiente canción o
  volver a la anterior. Funciona con cualquier app compatible con los
  controles multimedia de Windows (System Media Transport Controls), sin
  integración específica por app.

## Requisitos

- Windows 10/11
- Python 3.10+

## Instalación

```bash
pip install -r requirements.txt
```

## Uso

```bash
python main.py
```

## Estructura

```
main.py                  Punto de entrada
app/audio_sessions.py    Volumen por aplicación (pycaw / Core Audio)
app/media_control.py     Play/pause/siguiente/anterior (WinRT SMTC)
app/gui.py               Interfaz gráfica (Tkinter)
```

## Estado

🚧 En desarrollo inicial.

## Cómo contribuir

1. Cloná el repositorio.
2. Creá una rama para tu cambio (`git checkout -b mi-mejora`).
3. Abrí un Pull Request describiendo qué resuelve.

## Licencia

MIT
