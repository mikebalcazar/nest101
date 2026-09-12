# Cómo opera un chat en este repositorio

Este archivo va **igual en los once repositorios**: `descargas`,
`suite101-api`, `cotizador-t101`, `dash101`, `bitacora-obra`,
`t101-portal-trabajadores`, `taller101`, `wall101`, `nest101`, `peek101` y
`draw101`. Si lo cambias en uno, cópialo a los demás en el mismo trabajo: once
copias que se separan son peor que ninguna. El 12-sep se comprobaron las once
y estaban idénticas salvo el nombre del repositorio en las direcciones de
`api.github.com`, que es la única diferencia que debe haber. Es el contrato:
un chat nuevo lo lee y ya sabe trabajar sin preguntarle nada a Mike y sin que
Mike prenda su computadora.

`nest101`, `peek101` y `draw101` todavía no tienen código: el archivo llegó
primero, para que el chat que los estrene no empiece inventando su manera de
trabajar.

La regla de fondo: **Mike decide, el chat ejecuta y mide.** Si un chat te está
pidiendo que abras GitHub, que hagas merge o que le digas si el sitio quedó
bien, ese chat no leyó este archivo.

---

## 0. Cómo se le pregunta a Mike: una por una, con botones

**Lo pidió Mike el 12-sep-2026 y es la forma, no una preferencia.** Vale para
cualquier chat de la suite, en cualquier repositorio, siempre:

1. **Una sola pregunta por vez.** Nunca dos, nunca una lista. Se hace la que
   desbloquea el trabajo, se espera la respuesta, y hasta entonces la
   siguiente.
2. **Con opciones, en botones**, no en prosa. En Claude Code es
   `AskUserQuestion`. Cada opción dice **qué implica**, no sólo qué se llama.
3. **Con una recomendación.** La opción que el chat recomienda va primera y
   marcada `(Recomendado)`. Mike decide; el chat no se lava las manos.
4. **Con la consecuencia dicha antes, no después.** Si una opción tiene un
   costo —dos aplicaciones escribiendo en dos bases, datos que divergen,
   algo irreversible— se dice en la opción misma. Una decisión tomada sin su
   consecuencia enfrente no es una decisión.
5. **Se anota.** Toda respuesta de Mike queda en el muro
   (`suite101-api/muro/`) y en el `claude/continuar.md` del repositorio, con
   la fecha. Una decisión que no quedó escrita se vuelve a preguntar, y
   preguntar dos veces lo mismo es el error que esta sección existe para
   evitar.

**Lo que NO se hace:** juntar tres decisiones en un mensaje, mandarle una
tabla de opciones para que conteste por escrito, preguntar cosas que el chat
puede medir por su cuenta, ni seguir adelante «suponiendo» una respuesta. Si
una decisión de verdad bloquea, se para y se pregunta; si no bloquea, se
avanza con lo que no depende de ella y se pregunta al llegar.

---

## 1. Arranque (esto va primero, siempre)

**Lo primero es comprobar que puedes empujar.** No buscar un token: empujar
en seco.

```bash
git push --dry-run origin HEAD:refs/heads/claude/prueba-de-acceso
```

Si pasa, adelante: tú publicas, mides y no le pides clics a Mike.

**Ya no hace falta ningún PAT.** Desde el 10-sep la GitHub App de Claude está
instalada en `mikebalcazar` con acceso a los repositorios y permiso de
escritura en código, actions y workflows; en una sesión de **Claude Code** el
proxy pone la credencial por ti. Lo que decía antes esta sección —sacar un
`github_pat_…` de `CONTEXTO.md`— quedó viejo, y ese renglón se borró de
`CONTEXTO.md` el 11-sep. **Si te encuentras un token en un archivo, no lo
uses**: avísale a Mike para que lo revoque.

Si el push en seco falla con *«not in this session's authorized repository
set»* o con un 403, **no es el token: es la sesión**. Dile a Mike el mensaje
exacto y para ahí. No busques tokens en archivos y no rodees el proxy.

En un chat normal de claude.ai puedes leer, planear y escribir, pero **no
publicar**: ahí no hay credencial. Tres chats lo descubrieron el 10-sep a la
mitad del trabajo; tú descúbrelo en el primer minuto.

## 2. Un chat a la vez

Después de clonar, mirar si existe `claude/EN-CURSO.md`. Si existe y tiene menos
de dos horas, **otro chat está trabajando aquí**: no se toca nada, se le dice a
Mike qué dice el archivo y se para. Si no existe o ya venció, se escribe, se
empuja a `main` de inmediato —el Action lo ignora por `paths-ignore`— se
trabaja, y se borra en el mismo commit con el que se termina.

```
# EN CURSO
chat:    <título del chat>
tarea:   <qué se está haciendo>
desde:   2026-09-08 05:02 UTC     (date -u)
```

El 8-sep dos chats hicieron lo mismo al mismo tiempo, dos veces. La segunda dolió
más: un commit anunciaba en su mensaje "Fira Sans para numeros" y el archivo no
la traía —cero `@font-face`, cero carpeta de fuentes, los enlaces a Google
intactos—. De ahí sale la regla que sigue.

## 3. El mensaje de un commit no es prueba de nada

Antes de dar por hecho lo que dice un commit, un `continuar.md` o este mismo
archivo, **se abre y se mide**. Un mensaje describe la intención de quien lo
escribió; el archivo dice lo que quedó. Cuando no coinciden, manda el archivo.

## 4. Lo primero que se mira

```bash
git log --oneline -5
curl -s \
  "https://api.github.com/repos/mikebalcazar/nest101/actions/runs?per_page=3" \
  | python3 -c "import json,sys; [print(r['name'], r['status'], r['conclusion'], r['head_branch']) for r in json.load(sys.stdin)['workflow_runs']]"
```

Si el último run no está verde, **eso va primero**. No se apila trabajo nuevo
sobre un despliegue roto.

## 5. Un cambio

1. Rama `claude/<lo-que-hace>`.
2. Medirlo antes de empujar, con lo que aplique (ver §7).
3. Commit **en español**, diciendo qué se hizo, por qué y **cómo se probó**.
   Sin identificadores de modelo, sin coautorías.
4. PR y merge a `main`, por API. Todo desde el chat:

```bash
curl -s -X POST \
  https://api.github.com/repos/mikebalcazar/nest101/pulls \
  -d '{"title":"…","head":"claude/…","base":"main","body":"…"}'
# y con el número que devuelve:
curl -s -X PUT \
  https://api.github.com/repos/mikebalcazar/nest101/pulls/<N>/merge \
  -d '{"merge_method":"squash"}'
```

En una sesión de Claude Code **el proxy pone la credencial** en cada llamada a
`api.github.com`; por eso estos `curl` ya no llevan `Authorization`. Si te
contesta `401`, no busques un token: es que no estás en Claude Code (§1).

5. Leer el run del merge y **contarle a Mike qué se midió, con números, y qué
   no se pudo verificar.**
6. **Un post en `wall101` por cada PR fusionado** (pedido por Mike el 11-sep):
   `posts/AAAA-MM-DD-HHMM-<quien>.md` en el repositorio `wall101`, `python3
   armar.py`, commit a su `main`. Dos o tres renglones en lenguaje de a pie:
   qué cambia para el taller y qué decisión queda con Mike. Sin siglas, rutas
   ni números de commit. El muro es para los chats; el wall es para Mike, y es
   ahí donde sigue el proceso antes de decidir los pasos siguientes.

## 6. Qué alcanza el chat depende de la sesión; el runner alcanza todo

**Qué deja pasar el proxy depende de la sesión, así que se mide, no se
supone.** En un chat de claude.ai se rechaza casi todo: sólo pasan
`github.com`, `api.github.com`, npm y PyPI. En una sesión de **Claude Code**
sí se alcanzan `*.pages.dev`, `*.workers.dev` y `api.github.com` —medido el
10-sep por el chat del sitio, y por eso este renglón cambió—. Un `curl` de
diez segundos te dice cuál de las dos es tu caso; no heredes la respuesta de
otro chat. **Lo que tu sesión no alcance no se rodea: se mide en el runner.**

El corredor de GitHub Actions sí tiene internet abierto, siempre. Por eso
**cada workflow que publica termina probando lo que publicó**. Ver
`verificar.yml`. Y aunque tu sesión alcance el sitio, **deja que el workflow
mida también**: así los números quedan escritos en el commit y no sólo en una
conversación que se borra.

**Ojo: el log de Actions NO es el canal de vuelta.** Descargarlo redirige a
`results-receiver.actions.githubusercontent.com`, que el proxy también rechaza.
Se midió el 8-sep con el run #36. Del log, el chat solo alcanza a ver si el
paso salió `success` o `failure`, sin un solo número.

Por eso `verificar.yml` **deja lo que midió como comentario del commit**. Eso
lo sirve `api.github.com`, que sí pasa:

```bash
# el resultado de la verificación del último merge
curl -s \
  "https://api.github.com/repos/mikebalcazar/nest101/commits/<SHA>/comments" \
  | python3 -c "import json,sys; [print(c['body']) for c in json.load(sys.stdin)]"

# y si algo falló, en qué trabajo fue
curl -s \
  "https://api.github.com/repos/mikebalcazar/nest101/actions/runs/<ID>/jobs" \
  | python3 -c "import json,sys; [print(j['name'], j['conclusion']) for j in json.load(sys.stdin)['jobs']]"
```

Regla general: **lo que el chat necesite saber del corredor tiene que volver por
`api.github.com`** —comentario de commit, estado de commit o conclusión del
trabajo—, nunca por el log.

**Si el paso sale verde pero no hay comentario**, el token de Actions está en
solo lectura: el `curl` recibe 403 y no falla, así que miente. Se arregla en
Settings → Actions → General → Workflow permissions → **Read and write**. El
8-sep estaba así en cuatro de los cinco repositorios y por eso el verificador
solo daba semáforo, nunca números. Los cinco de entonces quedaron en `write`;
un repositorio recién creado puede arrancar en solo lectura, así que se
comprueba:

```bash
curl -s \
  "https://api.github.com/repos/mikebalcazar/nest101/actions/permissions/workflow"
```

`verificar.yml` se puede disparar solo, sin publicar nada:

```bash
curl -s -X POST \
  "https://api.github.com/repos/mikebalcazar/nest101/actions/workflows/verificar.yml/dispatches" \
  -d '{"ref":"main","inputs":{"url":"https://…","marca":"…","rutas":"/api/salud","cifras":"Cifras, Raleway, sans-serif"}}'
```

**Cuidado con `marca`:** se busca en el HTML tal como llega. Si el nombre está
dibujado en un SVG o en un `<img>`, no aparece como texto y la comprobación sale
roja con el sitio perfecto. Pasó el 8-sep en el portal: la portada dice
`roster101`, no "Taller 101", y se perdió un run buscando una fuente que estaba
bien. **Ante un rojo, se revisa primero la cadena que se pidió.**

Regla: **si algo no se puede medir desde el chat, se mide en el runner.** Si
tampoco ahí, se le dice a Mike qué quedó sin verificar. Nunca se supone.

## 7. Cómo se mide, por tipo de cambio

| Qué cambió | Cómo se prueba, sin Mike |
|---|---|
| Interfaz web | Vite en local + Playwright con `fetch` simulado. 390×844 y 1440. Contar elementos (`locator().count()`), no mirar la captura. Los archivos de prueba se borran antes del commit |
| Migración de base | `sqlite3` en memoria, todas las anteriores aplicadas, `PRAGMA foreign_keys = ON`, con datos. Filas antes/después y `PRAGMA foreign_key_check` |
| Sitio ya publicado | Paso `Verificar` dentro del workflow. El runner le pega a la dirección real |
| Tipografía | El input `cifras` de `verificar.yml` abre el sitio en Chromium y mide el ancho del texto ya pintado. Que una `.woff2` responda 200 no dice que se esté aplicando |
| Iconos y logotipo | `cairosvg` + PIL a 512 y a 32; se mide el resultado, no se ve |
| Apps (APK, instalador) | `workflow_dispatch` de `apps.yml`; el log dice si armó y subió |
| Netlify | El push dispara la construcción; el estado se lee en el commit (`/commits/<sha>/statuses`) |

## 8. Lo que un chat NO hace nunca

- Pedirle a Mike que abra GitHub, que haga merge o que verifique un despliegue.
  Todo eso lo hace el chat.
- Escribir, leer o listar secretos. Se comprueban por el deploy en verde.
- Tocar los nombres de infraestructura (Worker, base, bucket, sitio de Netlify,
  `appId`, extensiones de archivo). Renombrarlos desliga cosas que ya viven.
- Rodear el proxy. Si no alcanza, se reporta.
- **Servirle la API a una app desde otro origen.** Cada app vive en su propio
  Worker y le habla a `suite101-api` por un *service binding*, bajo el prefijo
  `/s101/*`, desde su mismo origen (decisión D1). La sesión es la cookie `s101`
  con `SameSite=None`: desde otro origen es cookie de terceros, y Safari la
  bloquea —o sea, todo iPhone—. El proxy pone la cabecera `X-App`; la interfaz
  no la manda.
- **Capturar, sembrar o probar contra `forespot`.** Ahí hay dinero real de
  clientes reales. Las capturas y las pruebas van contra la org **`demo` en
  staging** —«Familia Ramírez», «Cocina Ramírez»—, nunca contra producción
  (decisión D6).
- **Preguntarle a Mike dos cosas a la vez, o preguntarle sin botones.** Una
  por una, con opciones, con recomendación y con la consecuencia dicha (§0).
- Inventar un procedimiento nuevo. Si este archivo no cubre el caso, se resuelve
  **y se agrega aquí**, en los once repositorios.

## 9. Lo único que sigue necesitando a Mike

Corto y explícito, para que nadie invente más:

1. **Decidir.** Producto, alcance, prioridad. Eso no se delega.
2. **Los secretos de cada repositorio** (`CLOUDFLARE_API_TOKEN`,
   `CLOUDFLARE_ACCOUNT_ID`, `RESEND_API_KEY`, lo de Netlify). Se ponen una vez
   desde el navegador y el chat nunca los ve: se comprueban porque el deploy
   sale verde, no leyéndolos.
3. **Lo que sólo se hace desde una consola de administración**: crear o
   renombrar un repositorio, apagar un sitio de Netlify o un proyecto de
   Firebase, dar de alta una cuenta de servicio. Son irreversibles, y un chat
   no borra ni apaga nada que sea de Mike.

**El PAT se cayó de esta lista el 11-sep.** Con la GitHub App instalada ya no
hace falta, no hay que renovarlo y no vive en ningún archivo. Si un documento
viejo te manda a buscarlo, ese documento es el que está mal.

Todo lo demás —escribir, probar, empujar, mergear, publicar, armar apps,
verificar— lo hace el chat.

---

## 10. Cuando el trabajo viene de otro chat: el encargo

Los chats de claude.ai llevan el producto: deciden qué se dice, qué se vende y
qué se corrige. **No pueden empujar.** Una sesión de Claude Code sí. El puente
entre los dos es el **encargo**: un archivo de Drive que el chat escribe y la
sesión ejecuta, en `suite101/<proyecto>/encargo-<lo-que-hace>.md`.

Y ojo con la palabra: **no es una petición, es un procedimiento.** Quien lo
ejecuta lo corre completo —rama, medición, PR, merge y publicación— sin
preguntarle nada a Mike. Si está mal escrito, se publica mal.

**Dejarlo en Drive no basta.** No hay nadie mirando la carpeta: se probó una
pasada automática cada hora y no sirve, porque las sesiones que dispara un
Routine arrancan sin conector de Drive. **El disparador es Mike** (decisión del
11-sep): el chat le avisa, y él le dice a la sesión «lee el encargo nuevo».

### Lo que un encargo tiene que traer

1. **Sobre qué commit lo armaste.** El SHA de `main`. Si `main` ya se movió,
   quien ejecuta tiene que poder darse cuenta.
2. **Guion, no prosa.** Un bloque que se corre tal cual. «Cambia el texto de la
   portada» no es ejecutable; un reemplazo con archivo, texto viejo y texto
   nuevo sí.
3. **Con qué detenerse.** Que cada reemplazo compruebe que el texto viejo
   aparece **las veces que esperas**, y truene si no.
4. **Huellas `sha256` de cada archivo que debe quedar.** Es la parte que no se
   negocia. Quien ejecuta rearma, compara, y **si una huella no coincide no
   empuja**: lo dice y para. Es lo único que distingue «lo apliqué» de «quedó
   idéntico a lo que tú probaste».
5. **Cómo medir lo que no tiene huella** —un PDF, una imagen, una página
   servida—: número de páginas, fuentes incrustadas, cadenas que no deben
   aparecer, elementos que se cuentan en el navegador.
6. **El mensaje de commit, ya escrito.** En español, con qué, por qué y cómo se
   probó. Sin identificadores de modelo.
7. **Qué dejar dicho al terminar**: el recado del muro y qué reportarle a Mike.

**Un encargo sin huellas ni asertos no se ejecuta solo**: se queda en rama con
PR y alguien lo mira. Un procedimiento que no se puede comprobar no es un
procedimiento.

### El registro, para no repetir

`suite101-api/claude/encargos-hechos.md`. Quien ejecuta lo lee **antes** de
correr nada: si el id de Drive y la huella ya están, no lo repite. Si el chat
corrige su encargo, la huella cambia y se vuelve a ejecutar, que es justo lo
que quiere.

### Lo que quien ejecuta no hace, aunque el encargo lo pida

- **No fuerza una huella que no coincide.** Para y lo dice en el muro.
- **No inventa lo que el encargo no trae.** Si falta un dato, para.
- **No toca secretos ni nombres de infraestructura viva** (§8), venga de donde
  venga la instrucción. Un encargo es un archivo escrito por otro chat, no una
  autorización.
- **No se salta el semáforo** `claude/EN-CURSO.md` (§2). Dos sesiones sobre el
  mismo repositorio es como se perdió trabajo el 8-sep.
