# Reproductor

Un reproductor/mezclador pequeño para Windows: controla el volumen de cada
aplicación por separado y maneja la reproducción (play/pause, siguiente,
anterior) de lo que esté sonando, todo desde una sola ventana.

## Descripción

- **Volumen por aplicación**: lista las apps que tienen audio activo (Spotify,
  el navegador, un juego, Discord, etc.), con su ícono real, y permite
  subir, bajar o silenciar cada una de forma independiente al volumen
  general de Windows. Usa las APIs de Windows Core Audio a través de
  [`pycaw`](https://github.com/AndreMiras/pycaw).
- **Cambiar la salida de audio**: un desplegable arriba de todo, igual que
  en [EarTrumpet](https://github.com/File-New-Project/EarTrumpet), para
  elegir a qué parlantes o auriculares sale el sonido sin tener que abrir
  la configuración de Windows.
- **Volumen general**: un slider con mute para el volumen general del
  sistema (todas las apps a la vez), disponible tanto en la ventana
  completa como en el panelito de la bandeja.
- **Controles multimedia**: muestra el título y artista de lo que se está
  reproduciendo, con la portada o miniatura real de fondo (la carátula en
  Spotify/YouTube Music, la miniatura del video en YouTube, etc.), y
  permite reproducir/pausar, pasar a la siguiente canción o volver a la
  anterior. Funciona con cualquier app compatible con los controles
  multimedia de Windows (System Media Transport Controls), sin
  integración específica por app.
- **Bandeja del sistema**: al cerrar la ventana (✕) el programa no se
  cierra, se minimiza al área de notificación (al lado del reloj) y sigue
  corriendo. Un clic en el ícono abre un panelito de controles (título,
  artista, ⏮ ⏯ ⏭) justo arriba de la barra de tareas, como el de volumen o
  red de Windows — sin abrir la ventana completa. Clic derecho para el
  resto de las opciones (abrir la ventana completa, controles, salir).

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

La ventana arranca mostrando solo los controles de reproducción. Hacé clic
en "▸ Aplicaciones con audio" para desplegar el volumen de cada app; el
tema (claro/oscuro, botón ☀️/🌙 arriba a la derecha) y si el panel queda
desplegado se recuerdan para la próxima vez.

## Generar el .exe

Para no tener que abrirlo desde una consola de Python, se puede empaquetar
como un ejecutable con [PyInstaller](https://pyinstaller.org/):

```bash
pip install -r requirements-dev.txt
pyinstaller Reproductor.spec
```

Esto genera la carpeta `dist/Reproductor/`, con `Reproductor.exe` adentro
junto a una carpeta `_internal/` con sus dependencias. Para abrir la app,
doble clic en `Reproductor.exe` (sin ventana de consola) — o creá un
acceso directo a ese `.exe` en el Escritorio o el menú inicio. Toda la
carpeta `dist/Reproductor/` se puede mover junta a cualquier lado, pero
tiene que viajar completa (el `.exe` no funciona separado de `_internal/`).

> Se usa `--onedir` (carpeta) en vez de `--onefile` (un solo archivo) a
> propósito: un `.exe` de un solo archivo se descomprime a una carpeta
> temporal cada vez que se abre, lo que acá tardaba varios segundos. Con
> `--onedir` los archivos ya están en disco y arranca casi al instante.

## Generar el instalador

Para pasarle la app a alguien más sin que tenga que lidiar con una carpeta
suelta, hay un instalador hecho con [Inno Setup](https://jrsoftware.org/isinfo.php)
(gratis). Con Inno Setup instalado:

```bash
pyinstaller Reproductor.spec
"C:\Program Files (x86)\Inno Setup 6\ISCC.exe" installer.iss
```

(La ruta del `ISCC.exe` puede variar según dónde haya quedado instalado
Inno Setup — con winget suele quedar en
`%LocalAppData%\Programs\Inno Setup 6\ISCC.exe`.)

Esto genera `dist/Instalar-Reproductor.exe`: un instalador normal (elegís
carpeta, se crea acceso directo en el menú inicio y, si querés, en el
escritorio) que no pide permisos de administrador — instala en la carpeta
del usuario actual — y deja un desinstalador propio en "Agregar o quitar
programas".

> Como no está firmado con un certificado de firma de código (eso tiene
> costo y no se hizo sin pedirlo explícitamente), Windows SmartScreen
> puede mostrar una advertencia la primera vez que alguien lo abre. Se
> resuelve con "Más información → Ejecutar de todas formas".

## Estructura

```
main.py                  Punto de entrada
app/audio_sessions.py    Volumen por aplicación (pycaw / Core Audio)
app/audio_devices.py     Elegir el dispositivo de salida (pycaw / IPolicyConfig)
app/icons.py             Ícono real de cada app (ctypes / GDI)
app/media_control.py     Play/pause/siguiente/anterior (WinRT SMTC)
app/gui.py               Interfaz gráfica (Tkinter)
app/theme.py             Colores claro/oscuro y preferencias guardadas
app/tray.py              Ícono de la bandeja del sistema
Reproductor.spec         Configuración de PyInstaller para el .exe
installer.iss            Configuración de Inno Setup para el instalador
icon.ico                 Ícono de la app (ventana, .exe, accesos directos)
```

## Estado

🚧 En desarrollo inicial.

## Cómo contribuir

1. Cloná el repositorio.
2. Creá una rama para tu cambio (`git checkout -b mi-mejora`).
3. Abrí un Pull Request describiendo qué resuelve.

## Licencia

MIT
