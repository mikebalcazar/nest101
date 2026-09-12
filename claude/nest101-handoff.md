<!-- Copiado tal cual del documento de Drive «nest101 handoff», el 12-sep-2026,
     con el conector de Google Drive. Sólo se le quitaron los escapes que Google
     mete al exportar a markdown (\- \+ \: y demás). No se corrigió el contenido:
     es el documento del chat que reconstruyó nest101, y vale como está. -->

> **Nota del 12-sep-2026, al meter esto al repositorio.** Dos cosas de este
> documento ya no aplican, y conviene saberlo antes de seguirlas al pie de la
> letra:
>
> - **Ya no hace falta ningún PAT.** Desde el 10-sep la GitHub App de Claude
>   está instalada en `mikebalcazar` y el proxy pone la credencial en una
>   sesión de Claude Code. Si te encuentras un token en un archivo, no lo uses:
>   avísale a Mike para que lo revoque. Lo manda `OPERAR.md` §1.
> - **El repositorio ya existe y ya tiene la fuente**: es éste, y lo que estás
>   leyendo llegó en el mismo trabajo. El «pendiente 1» de este documento está
>   cerrado.
>
> Todo lo demás —las mediciones, las decisiones y las trampas— sigue vigente.

# nest101 handoff

**Para:** el chat que tome nest101 con los repositorios ya autorizados.
**De:** el chat que tomó nest101 el 10-sep-2026.
**Regla de este documento:** todo lo que aquí se afirma se midió. Lo que no se
pudo medir se dice como tal. Si un renglón de aquí no coincide con lo que ves en
un archivo, manda el archivo — es lo que dice `OPERAR.md` §3 y es la razón por la
que este documento existe.

* * *

## 0 · Lo primero, en este orden

1. **Lee `OPERAR.md`.** Está en el repo `descargas` y también en el árbol de
   nest101. Es el contrato: cómo se opera, cómo se mide, qué no se hace nunca.

2. **Comprueba tu alcance antes de prometer nada.** Con el PAT que está en
   `t101x\github-token.txt`:

```bash
git ls-remote https://x-access-token:$T@github.com/mikebalcazar/nest101
git push <...> HEAD:refs/heads/prueba
```

   Si el push contesta *«not in this session's authorized repository set»*, el
   repo no está conectado a tu sesión: **eso se le dice a Mike y se para ahí**.
   No es el PAT. Ver §6.

3. **Restaura el árbol de fuentes.** Está en
   `C:\Users\mikeb\OneDrive\Escritorio\t101x\nest101\nest101-fuente-X.0.2.zip`
   — 112 archivos, 1.4 MB. **Es la única fuente que existe de nest101.** No hay
   otra copia en ninguna parte salvo dentro de los instaladores.

4. **Empuja.** El repo `mikebalcazar/nest101` existe, es privado y está vacío
   (se creó el 10-sep-2026 para esto). El primer commit ya estaba redactado; su
   mensaje está en §4 y conviene conservarlo, porque explica de dónde salió todo.

* * *

## 1 · Qué es nest101

Aplicación de escritorio para Windows: **despiece de gabinetes para corte CNC**.

- Cascarón **Electron 33.4.11** (`electron/main.js`, `preload.js`, `splash.html`).
- Motor **FastAPI con Python 3.11 embebido** (`server.py`), que Electron levanta
  en `127.0.0.1:8760` —o el primer puerto libre— y del que carga la interfaz.
- Interfaz HTML + JS + **Three.js**, servida por el propio backend (`ui/`).
- `core/` modelos paramétricos, nesting, isométrico, cubierta, catálogo del
  taller, actualizador · `export/` DXF, XLSX, PDF, fichas, visor 3D ·
  `identificador/` lectura de planos con visión.
- Un proyecto es una **carpeta**; cada mueble es un `.t101x` (JSON por dentro).
- `verificar.py` corre **93 comprobaciones**: cierre dimensional, holguras,
  cajones, barrenos dentro de su pieza, nesting sin traslapes.

El puente entre la interfaz y el escritorio se llama **`window.despz`**
(definido en `preload.js`). Apúntalo: por confundirlo hubo un bug de meses.

* * *

## 2 · Versiones

| Versión | Dónde está | Nota |
| --- | --- | --- |
| 0.15.3 | instalada en el equipo de Mike | |
| 0.15.4 | en `t101x`, en 10 pedazos | nunca se unió |
| **0.15.6** | **publicada** en Releases, 8-sep-2026 | la última que ven los talleres |
| X.0.1 | `t101x\nest101\X.0.1\` | recompilación de prueba. Mike la instaló: abre |
| **X.0.2** | `t101x\nest101\X.0.2\` | descarga automática + arreglo del puente |

La **línea X** es la de prueba de los chats. Por dentro va como `10.0.x` (X = 10
en romano) porque electron-builder exige semver, y de paso evita que el
actualizador crea que la 0.15.6 es más nueva.

**La línea X no se publica nunca en `nest101.json`.** Hay al menos otro equipo
del taller con nest101 instalado, y ese archivo es lo que leen todos los
programas: publicar ahí un `10.0.x` haría que las máquinas se bajaran solas
167 MB de una compilación de prueba. Lo que se publique va como **0.16.0**.

* * *

## 3 · De dónde salió el código

nest101 se compiló y publicó durante meses **desde chats, sin repositorio**. El
10-sep se comprobó leyendo la lista completa de repos de Mike: no existía ninguno
de nest101 (ni de draw101). El código sólo vivía dentro del instalador publicado.

El árbol actual se **reconstruyó desde el instalador 0.15.6**: el Python viaja
sin compilar dentro del `.exe` y el `app.asar` trae el cascarón entero, así que
la reconstrucción es la fuente real y no una copia aproximada.

**La prueba:** se compiló ese árbol y se comparó el resultado empaquetado contra
el de la 0.15.6 oficial — **9 164 archivos cada uno, cero diferencias**.

Lo único que no viajaba en el instalador, y por tanto lo único escrito de nuevo,
es la configuración de compilación de `package.json`.

* * *

## 4 · Lo que está hecho y todavía no está subido

Todo esto está dentro del zip de §0.3 y forma el primer commit:

**\#093 · la actualización se baja sola.** La revisión automática ya existía
(\#092, en la 0.15.6); faltaba el segundo paso.

- `core/actualizar.py`: política `descargar_solo` (encendida de fábrica),
  estado de descarga con candado, `arrancar_descarga()` idempotente en un hilo
  `daemon`, `destino_de()`, `ya_bajada()`.
- `server.py`: `GET /api/actualizacion/descarga` (progreso), el `POST …/descargar` ya **no bloquea** —antes tenía la petición abierta los 180 MB—,
  y `PUT …/auto` acepta `descargar`.
- `ui/app.js`: el botón de arriba se vuelve la barra de progreso («Bajando la
  0.16.0 47 %»), al terminar dice «Instalar la 0.16.0», reloj de sondeo que se
  apaga solo, interruptor nuevo en Configuración general.
- `assets/idioma/en.json`: 10 cadenas nuevas traducidas.

Tres decisiones que no hay que deshacer sin pensarlo: **bajar no es instalar**
(correr el instalador lo decide la persona); **sin red no pasa nada** (se traga
el error, el taller trabaja sin red la mitad del tiempo); **un fallo no se
reintenta en bucle**.

**Arreglo de un bug real de la 0.15.6.** El puente se llama `window.despz`, pero
`instalarAhora()` y `abrirEnlace()` llamaban a `window.t101`, que no existe.
Consecuencia: en la 0.15.6 el botón «Instalar ahora» **no hacía absolutamente
nada**, y el enlace de descarga abría una ventana de Electron en vez del
navegador. Cuatro apariciones corregidas.

**Andamiaje del repositorio:** `README.md`, `OPERAR.md` (copiado de `descargas`,
como manda el contrato), `.gitignore` y `.github/workflows/apps.yml` (§6).

**Cómo se probó, con números:** se le dijo al programa que tenía instalada la
0.15.0; encontró la 0.15.6 publicada, se la bajó sola en segundo plano, y el
sha256 del archivo bajado coincidió con el que declara `nest101.json`
(`93326039…`), con los 166 928 819 bytes exactos. Llamarlo dos veces no la
vuelve a bajar. Los cuatro caminos del interruptor, por HTTP. Las 93
comprobaciones pasan. `node --check` pasa en `ui/app.js` y `electron/main.js`.

* * *

## 5 · Cómo se compila

```bash
npm install
npx electron-builder --win nsis --x64
```

En Linux hace falta **wine** (`wine` + `wine32:i386`): sin él electron-builder
aborta al firmar. `runtime/python/` (371 MB, CPython 3.11 para Windows con las 8
librerías) **no se versiona**: lo arma el workflow con la receta de `LEEME.md`, o
se saca de un instalador ya publicado, que es más rápido y más fiel.

**La versión se escribe en dos lugares** y los dos tienen que coincidir:
`package.json` → `version` y `server.py` → `VERSION`. Desfasarlos deja un
programa que se cree otra versión de la que es y no se actualiza nunca.

`verificar.py` se corre **con el Python embebido** (`runtime\python\python.exe`),
no con el del sistema: correrlo con otro mide otra cosa.

⚠️ **`appId` sin resolver.** Quedó como `com.taller101.nest101`. No se pudo
recuperar el de las compilaciones oficiales —no está ni en el instalador ni en
el desinstalador—. Si no coincide, el instalador nuevo no reconoce la
instalación anterior y deja una entrada duplicada en «Agregar o quitar
programas». Antes de publicar la 0.16.0 conviene mirar el registro de una
máquina que ya tenga nest101 instalado y tomar el `appId` de ahí.

* * *

## 6 · Publicar: el contrato y los muros

**El contrato** (escrito en `core/actualizar.py`, vive en `descargas`):

- Lo que leen los programas instalados:
  `raw.githubusercontent.com/mikebalcazar/descargas/main/nest101.json`
- Enlace fijo que nunca cambia:
  `github.com/mikebalcazar/descargas/releases/download/nest101-ultima/nest101-setup.exe`
- Cada versión con su tag `nest101-<versión>`, sus notas y su sha256.

**El workflow.** `.github/workflows/apps.yml` (`workflow_dispatch`, entradas
`version`, `notas`, `publicar`) compila en un corredor Windows, arma el runtime
con caché, corre las 93 comprobaciones con el Python embebido, publica las dos
releases, actualiza `nest101.json` y la tabla del `README` de descargas, y
**termina bajándose lo que acaba de publicar para comprobar la huella**. Está
escrito pero **nunca se ha ejecutado**: la primera corrida hay que hacerla con
`publicar = false` y leer lo que midió antes de publicar de verdad.

**Los tres muros del proxy de salida del chat**, medidos el 10-sep:

1. `api.github.com` → 403. Es la única puerta para crear una release y subirle
   un archivo. Por eso el corredor.
2. `github.com` como página web → 403. No se pueden listar repos ni leer
   releases desde el chat.
3. `git push` → el proxy **no inyecta credencial** para repos que no estén en el
   conjunto autorizado de la sesión. **Clonar y leer sí funciona.**

El coordinador dejó el mismo aviso en `suite101-repos.md`: un 403 al empujar **no
es el PAT**; es la sesión. No hay que ampliar un PAT que ya está bien.

* * *

## 7 · Lo que hace falta de Mike

| Qué | Dónde | Por qué |
| --- | --- | --- |
| Conectar `nest101` y `descargas` como **fuentes de la sesión** | app de Claude, en la tarea | sin esto no hay `git push` ni API, con el token que sea |
| **PAT** que incluya `nest101` (Contents RW · PR RW · Actions RW · Workflows RW · Administration RW) | pegado en `t101x\github-token.txt`, nunca en el chat | el PAT viejo no incluía nest101: contestaba 403 |
| Secreto **`TOKEN_DESCARGAS`** en el repo nest101 | Settings ▸ Secrets and variables ▸ Actions | el workflow compila en nest101 pero publica en descargas, y el token de Actions no alcanza a otro repo |

Mike genera los tokens él: es su regla y está bien que lo sea. El chat no
escribe credenciales en formularios ni las pega en ningún archivo del repo.

* * *

## 8 · Lo siguiente, en orden

1. Empujar el árbol a `mikebalcazar/nest101` (rama `main`).
2. Correr `apps.yml` con **`publicar = false`** y leer lo que midió.
3. Resolver el `appId` (§5) mirando una instalación real.
4. Publicar la **0.16.0** — que es la \#093 y el arreglo del puente, ya probados.
5. Comprobar el círculo completo: que una máquina con la 0.15.6 vea la 0.16.0,
   se la baje sola y ofrezca instalarla. **Ese es el examen final**, y hasta que
   no pase, la función no está terminada.
6. Corregirle la descripción al repo `taller101`: dice «despiezador t101», que es
   un rótulo viejo de nest101 y manda a cualquiera por el camino equivocado.
   Adentro es el SUPERVISOR (Worker + D1).
7. Pendiente de fondo, sin empezar: **exportar los datos de nest101 a la base
   unificada de la suite** (Cloudflare Durable Objects, una base por
   organización vía OrgDB). Hoy nest101 es 100 % autónomo y guarda en archivos.

* * *

## 9 · Inventario en `t101x\nest101\`

| Archivo | Qué es |
| --- | --- |
| `nest101-fuente-X.0.2.zip` | **el árbol completo**, 112 archivos. La única fuente |
| `ESTADO-nest101.md` | el estado largo, con todas las mediciones |
| `X.0.1\` | instalador de prueba en 9 pedazos + `UNIR-X.bat` |
| `X.0.2\` | instalador con la descarga automática, 9 pedazos + `UNIR-X2.bat` |

Y en la carpeta de arriba, `t101x\`: `github-token.txt`, los instaladores viejos
0.15.3 y 0.15.4, y `t101xylo-0.15.2-setup.exe` — **«xylo» era el nombre anterior
de nest101**, por si aparece en algún documento viejo.

* * *

## 10 · Cosas que cuestan una tarde si se ignoran

- **El mensaje de un commit no es prueba de nada.** Se abre el archivo y se mide.
- **Nunca publicar la línea X** en `nest101.json` (§2).
- **La versión va en dos lugares** (§5).
- **`window.despz`, no `window.t101`** (§1).
- **`verificar.py` con el Python embebido**, no con el del sistema (§5).
- **No rodear el proxy.** Si no alcanza, se reporta y se usa el corredor (§6).
- El repo `taller101` **no** es nest101, aunque su descripción lo diga (§8.6).
