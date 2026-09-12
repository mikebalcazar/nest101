# nest101

Despiece de gabinetes para corte CNC. Aplicación de escritorio para Windows.

Un cascarón de **Electron** que levanta un motor de **FastAPI en Python 3.11
embebido** en `127.0.0.1`, y le carga la interfaz desde ese mismo servidor. No
hace falta instalar Python ni Node: el runtime viaja dentro del instalador.

```
electron/       cascarón de escritorio (main.js, preload.js, splash.html)
core/           motor: modelos paramétricos, nesting, isométrico, cubierta,
                catálogo del taller, actualizador
export/         DXF, XLSX, PDF, fichas de corte, visor 3D
identificador/  lectura de planos con visión
ui/             interfaz (HTML + JS + Three.js), servida por el backend
server.py       el backend
cli.py          corrida sin interfaz
verificar.py    93 comprobaciones: cierre dimensional, holguras, barrenos,
                nesting sin traslapes
runtime/python/ CPython 3.11 para Windows (NO se versiona: lo arma el workflow)
```

Los proyectos son carpetas; cada mueble es un archivo `.t101x`, JSON por dentro.

## De dónde salió este repositorio

nest101 se compiló y publicó durante meses **desde chats, sin repositorio**. El
10-sep-2026 se comprobó que no existía en ninguna cuenta: el código sólo vivía
dentro del instalador publicado. El árbol que está aquí se **reconstruyó desde
el instalador 0.15.6** —el Python viaja sin compilar, y el `app.asar` trae el
cascarón entero—, y se comprobó midiendo: el árbol empaquetado de una
compilación propia y el de la 0.15.6 oficial tienen **9 164 archivos cada uno y
cero diferencias**.

Lo único que no viajaba en el instalador, y por tanto lo único escrito de nuevo,
es la configuración de compilación de `package.json`.

El árbol que está aquí es el de `nest101-fuente-X.0.2.zip`, que Mike dejó en
Drive. Su huella, para que se pueda comprobar que es el mismo:

```
sha256  063302b87a2a1053b524ad5bdc9d245252cc10de7585bf0a8c61dbbe300a28b4
bytes   1 443 997
```

El estado completo del proyecto —qué está hecho, qué falta y las trampas que
cuestan una tarde— está en [`claude/nest101-handoff.md`](claude/nest101-handoff.md).

## Correr en desarrollo

```bash
pip install fastapi uvicorn ezdxf openpyxl reportlab pillow numpy
npm install
npm start            # Electron levanta el backend solo
python server.py --port 8760   # o sólo el backend, en el navegador
python verificar.py            # las 93 comprobaciones
```

## Compilar el instalador

```bash
npx electron-builder --win nsis --x64
```

En Linux hace falta wine (`wine` + `wine32:i386`): sin él electron-builder
aborta al firmar. En Windows no hace falta nada más.

`runtime/python/` se arma con la receta de `LEEME.md`, o se saca de un
instalador ya publicado, que es más rápido y más fiel.

## Publicar una versión

No se publica a mano. Se dispara el workflow `apps`
(`.github/workflows/apps.yml`) con la versión, y el corredor compila, mide,
publica en `mikebalcazar/descargas` y **comprueba bajándose lo que acaba de
publicar**. El contrato que leen los programas ya instalados es
`descargas/nest101.json`.

**La versión se escribe en dos lugares** —`package.json` y `server.py`— y el
workflow los pone de acuerdo. Desfasarlos deja un programa que se cree otra
versión de la que es y no se actualiza nunca.

Cómo opera un chat en este repositorio: `OPERAR.md`.
