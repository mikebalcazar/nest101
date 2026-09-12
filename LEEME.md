# nest101 — lo que no está en el repositorio, y cómo vuelve

`README.md` manda a este archivo desde el día que se armó el repositorio, y
hasta el 12-sep-2026 este archivo no traía la receta: traía el manual de
instalación de «DESPIEZADOR v0.4», que quedó viejo hace versiones y que
`README.md` ya cubre mejor. Eso es lo que se cambió aquí. El manual viejo sigue
dentro de `nest101-fuente-X.0.2.zip`, cuya huella está en `README.md`.

Tres cosas se quedan fuera del repositorio a propósito. Ninguna es código
nuestro: son binarios de otros que no cambian con lo que escribimos y que
pesarían más que todo lo demás junto.

| Qué falta | Cuánto pesa | Cómo vuelve |
|---|---|---|
| `runtime/python/` | 371 MB | CPython 3.11 para Windows con las 8 librerías. Dos caminos, abajo. |
| `node_modules/` | no medido | `npm install`. Electron y electron-builder; sólo hacen falta para armar el instalador. |
| `dist/` | ~167 MB el instalador | `npx electron-builder --win nsis --x64`. |

## `runtime/python/`, camino corto: sacarlo de un instalador publicado

Es el más rápido **y el más fiel**: es exactamente el intérprete con el que el
taller ya está trabajando, no uno parecido armado hoy.

```bash
# 1. bajar la última publicada (el enlace fijo nunca cambia)
curl -L -o nest101-setup.exe \
  https://github.com/mikebalcazar/descargas/releases/download/nest101-ultima/nest101-setup.exe

# 2. comprobar la huella ANTES de sacarle nada
sha256sum nest101-setup.exe
curl -s https://raw.githubusercontent.com/mikebalcazar/descargas/main/nest101.json | grep sha256
# los dos renglones tienen que decir lo mismo. Si no, se para: un instalador a
# medias no avisa, sólo falla raro después.

# 3. sacar el intérprete
7z x nest101-setup.exe -oinstalador
cp -a instalador/resources/python runtime/python
```

Se usa **sha256** y no md5 en todo lo que se comprueba aquí porque es lo que ya
usa el resto de la suite —`nest101.json`, las releases y los `UNIR-X.bat` que
juntan los pedazos del instalador del lado de Windows—. Dos huellas distintas
para lo mismo se acaban contradiciendo, y la que se contradice es la que nadie
revisa.

## `runtime/python/`, camino largo: armarlo

Sólo cuando cambia la versión de Python o se agrega una librería. Lo hace el
workflow `apps.yml` en un corredor Windows, con caché; a mano es esto:

```bash
# CPython 3.11 empotrable para Windows, 64 bits
curl -L -o py.zip https://www.python.org/ftp/python/3.11.9/python-3.11.9-embed-amd64.zip
unzip -q py.zip -d runtime/python
# habilitar site-packages: en python311._pth se le quita el # a "import site"
sed -i 's/^#import site/import site/' runtime/python/python311._pth
# las ocho librerías, para Windows, desde Linux
pip download --only-binary=:all: --platform win_amd64 --python-version 3.11 \
  -d ruedas fastapi uvicorn ezdxf openpyxl reportlab pillow numpy
pip install --no-deps --target runtime/python ruedas/*.whl
```

Y se comprueba antes de armar nada:

```bash
find runtime/python -type f | wc -l    # contra el conteo del origen
du -sh runtime/python                  # ~371 MB
```

## Lo que se comprueba después

`verificar.py` se corre **con el Python embebido**
(`runtime\python\python.exe`), no con el del sistema: correrlo con otro mide
otra cosa. Son 93 comprobaciones: cierre dimensional, holguras, cajones,
barrenos dentro de su pieza y nesting sin traslapes.

Cómo se publica una versión, y las dos cosas que no hay que desfasar nunca,
están en `README.md`. Cómo opera un chat aquí, en `OPERAR.md`.
