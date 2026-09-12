const { app, BrowserWindow, ipcMain, dialog, shell, Menu } = require("electron");
const { spawn } = require("child_process");
const path = require("path");
const fs = require("fs");
const net = require("net");
const http = require("http");

let ventana = null;
let backend = null;
let PUERTO = 8760;
let cerrarConfirmado = false;      // #015
let archivoPendiente = null;       // #016: ruta con la que arrancó la app

const RAIZ = path.join(__dirname, "..");        // carpeta del proyecto Python
const esDev = !app.isPackaged;
const raizPy = esDev ? RAIZ : path.join(process.resourcesPath, "app_py");
const EXTS = [".t101x", ".json"];

/* ---------- #016: ¿con qué archivo nos abrieron? ---------- */
function archivoDeArgv(argv) {
  const args = argv.slice(esDev ? 2 : 1);
  for (const a of args) {
    if (a.startsWith("-")) continue;
    const ext = path.extname(a).toLowerCase();
    if (EXTS.includes(ext) && fs.existsSync(a)) return path.resolve(a);
  }
  return null;
}

function abrirEnVentana(ruta) {
  if (!ruta || !ventana) return;
  try {
    const contenido = fs.readFileSync(ruta, "utf-8");
    ventana.webContents.send("abrir-archivo-externo", { ruta, contenido });
    if (ventana.isMinimized()) ventana.restore();
    ventana.focus();
  } catch (e) {
    dialog.showErrorBox("No se pudo abrir el proyecto",
      `${ruta}\n\n${e.message}`);
  }
}

/* ---------- puerto libre ---------- */
function puertoLibre(desde) {
  return new Promise((res) => {
    const s = net.createServer();
    s.listen(desde, "127.0.0.1", () => { const p = s.address().port; s.close(() => res(p)); });
    s.on("error", () => res(puertoLibre(desde + 1)));
  });
}

/* ====================================================================== #020
   Arranque del backend: que se pueda diagnosticar cuando falla.

   La 0.4.1 fallaba en 3 de 4 equipos con un mensaje que no decía nada y que
   además mentía (recomendaba «pip install» aunque Python viaja dentro). Ahora:
   todo lo que dice Python se guarda en un registro, se prueban las librerías
   una por una antes de rendirse, se espera más, y si el Python incluido no
   sirve se intenta con el del sistema.
   ====================================================================== */
const LIBRERIAS = ["fastapi", "uvicorn", "pydantic", "numpy",
                   "reportlab", "ezdxf", "openpyxl", "PIL"];
const ESPERA_MS = 120000;          // primer arranque en equipo lento con antivirus
let rutaRegistro = null;
const bitacora = [];

function registrar(txt) {
  const linea = `[${new Date().toISOString()}] ${txt}`;
  bitacora.push(linea);
  console.log(linea);
  try {
    if (!rutaRegistro) {
      const dir = app.getPath("userData");
      fs.mkdirSync(dir, { recursive: true });
      rutaRegistro = path.join(dir, "arranque.log");
      fs.writeFileSync(rutaRegistro, "");     // una corrida por archivo
    }
    fs.appendFileSync(rutaRegistro, linea + "\n");
  } catch { /* si no se puede escribir, queda en memoria */ }
}

function pythonIncluido() {
  const emb = process.platform === "win32"
    ? path.join(process.resourcesPath, "python", "python.exe")
    : path.join(process.resourcesPath, "python", "bin", "python3");
  return !esDev && fs.existsSync(emb) ? emb : null;
}

function candidatosPython() {
  const lista = [];
  const emb = pythonIncluido();
  if (emb) lista.push({ py: emb, quien: "el Python incluido en la app" });
  lista.push(process.platform === "win32"
    ? { py: "python", quien: "el Python del sistema" }
    : { py: "python3", quien: "el Python del sistema" });
  return lista;
}

/** Corre un python con argumentos y devuelve {codigo, salida}. */
function correr(py, args, ms = 60000) {
  return new Promise((resolve) => {
    let salida = "";
    let p;
    try {
      p = spawn(py, args, { cwd: raizPy, env: { ...process.env, PYTHONUNBUFFERED: "1", PYTHONDONTWRITEBYTECODE: "1" } });
    } catch (e) {
      return resolve({ codigo: -1, salida: String(e.message) });
    }
    const reloj = setTimeout(() => { try { p.kill(); } catch {}
      resolve({ codigo: -2, salida: salida + "\n(se agotó el tiempo)" }); }, ms);
    p.stdout.on("data", (d) => (salida += d.toString()));
    p.stderr.on("data", (d) => (salida += d.toString()));
    p.on("error", (e) => { clearTimeout(reloj); resolve({ codigo: -1, salida: String(e.message) }); });
    p.on("close", (c) => { clearTimeout(reloj); resolve({ codigo: c, salida: salida.trim() }); });
  });
}

/** Antes de rendirse por «no respondió», se averigua QUÉ falla. */
async function revisarPython(py) {
  const v = await correr(py, ["-c", "import sys; print(sys.version)"], 45000);
  if (v.codigo !== 0) {
    return { ok: false, motivo: "Python no arrancó", detalle: v.salida || `código ${v.codigo}` };
  }
  registrar(`Python responde: ${v.salida.split("\n")[0]}`);
  const faltan = [];
  for (const lib of LIBRERIAS) {
    const r = await correr(py, ["-c", `import ${lib}`], 60000);
    if (r.codigo !== 0) {
      faltan.push(lib);
      registrar(`librería ${lib}: FALLA — ${(r.salida || "").split("\n").slice(-2).join(" ")}`);
    }
  }
  if (faltan.length) {
    return { ok: false, motivo: `No cargaron: ${faltan.join(", ")}`,
             detalle: bitacora.filter((l) => l.includes("FALLA")).join("\n") };
  }
  registrar("las 8 librerías cargan");
  return { ok: true };
}

/* #021 — la consulta al backend NO usa fetch.
   En el proceso principal de Electron, fetch pasa por la pila de red de Chromium,
   que respeta el proxy del sistema y NO exime a 127.0.0.1 por omisión. Con un
   proxy o una VPN configurada, la app dice «el backend no respondió» aunque el
   servidor esté arriba y contestando. El http de Node va directo al socket: ni
   proxy, ni resolución de nombres, ni sorpresas. */
function pedir(ruta, ms = 4000) {
  return new Promise((resolve) => {
    const req = http.request(
      { host: "127.0.0.1", port: PUERTO, path: ruta, method: "GET",
        agent: false, timeout: ms },
      (res) => {
        let cuerpo = "";
        res.on("data", (d) => (cuerpo += d));
        res.on("end", () => resolve({ ok: res.statusCode === 200, cuerpo }));
      });
    req.on("timeout", () => { req.destroy(); resolve({ ok: false, cuerpo: "" }); });
    req.on("error", () => resolve({ ok: false, cuerpo: "" }));
    req.end();
  });
}

function esperarSalud(ms) {
  const t0 = Date.now();
  return new Promise((resolve) => {
    (async function probar() {
      const r = await pedir("/api/salud");
      if (r.ok) return resolve(true);
      const t = Date.now() - t0;
      if (t > ms) return resolve(false);
      if (t > 6000 && Math.round(t / 1000) % 5 === 0)
        splashDice(`Iniciando… ${Math.round(t / 1000)} s`);
      setTimeout(probar, 250);
    })();
  });
}

/** Intenta con cada Python disponible. Devuelve null si arrancó, o el motivo. */
async function arrancarBackend() {
  for (const { py, quien } of candidatosPython()) {
    registrar(`intentando con ${quien}: ${py}`);
    splashDice(`Revisando ${quien}…`);
    const revision = await revisarPython(py);
    if (!revision.ok) {
      registrar(`descartado ${quien}: ${revision.motivo}`);
      continue;
    }
    splashDice("Iniciando el motor de cálculo…");
    let ultimaSalida = "";
    backend = spawn(py, [path.join(raizPy, "server.py"), "--port", String(PUERTO)],
                    { cwd: raizPy, env: { ...process.env, PYTHONUNBUFFERED: "1", PYTHONDONTWRITEBYTECODE: "1" } });
    backend.stdout.on("data", (d) => (ultimaSalida += d.toString()));
    backend.stderr.on("data", (d) => { ultimaSalida += d.toString(); registrar("py: " + d.toString().trim()); });
    backend.on("error", (e) => registrar("no se pudo lanzar: " + e.message));
    backend.on("close", (c) => registrar(`el servidor terminó con código ${c}`));

    if (await esperarSalud(ESPERA_MS)) {
      registrar(`servidor arriba en el puerto ${PUERTO} con ${quien}`);
      return null;
    }
    registrar(`${quien}: el servidor no respondió en ${ESPERA_MS / 1000} s`);
    registrar("lo último que imprimió: " + (ultimaSalida.trim() || "(nada)"));
    try { backend.kill(); } catch {}
    backend = null;
  }
  return "Ningún Python pudo levantar el motor de cálculo.";
}

/* ---------- ventana de arranque: que no parezca colgado ---------- */
let splash = null;
function crearSplash() {
  // #079 — transparente y sin marco: lo que se ve es el mueble recortado, no
  // un recuadro. `backgroundColor` en "#00000000" es el que hace que Windows no
  // pinte nada detrás; sin él vuelve el bloque gris.
  splash = new BrowserWindow({
    width: 520, height: 560, frame: false, resizable: false, center: true,
    transparent: true, backgroundColor: "#00000000", hasShadow: false,
    show: true, skipTaskbar: false, alwaysOnTop: true, title: "nest101",
  });
  splash.loadFile(path.join(__dirname, "splash.html"));
}

function splashDice(msg) {
  registrar(msg);
  try {
    splash?.webContents.executeJavaScript(`window.paso(${JSON.stringify(msg)})`).catch(() => {});
  } catch { /* el splash es un lujo, no un requisito */ }
}

function cerrarSplash() {
  try { splash?.destroy(); } catch {}
  splash = null;
}

/** El mensaje honesto: qué pasó, dónde está el registro, y nada de «pip install». */
function avisarFalloArranque(motivo) {
  const emb = pythonIncluido();
  const detalle = bitacora.slice(-14).join("\n");
  const r = dialog.showMessageBoxSync({
    type: "error",
    title: "nest101 no pudo iniciar",
    message: "No arrancó el motor de cálculo.",
    detail:
      `${motivo}\n\n` +
      (emb ? "Python viene incluido en la aplicación, así que no falta instalarlo.\n"
           : "No se encontró el Python incluido en la instalación: puede estar incompleta.\n") +
      "Lo más común es que un antivirus esté bloqueando el proceso, o que la " +
      "instalación quedara incompleta.\n\n" +
      `Registro: ${rutaRegistro || "(no se pudo escribir)"}\n\n` +
      `Últimas líneas:\n${detalle}`,
    buttons: ["Abrir el registro", "Cerrar"],
    defaultId: 0,
    cancelId: 1,
    noLink: true,
  });
  if (r === 0 && rutaRegistro) shell.openPath(rutaRegistro);
}

/* ---------- ventana ---------- */
function crearVentana() {
  ventana = new BrowserWindow({
    width: 1560, height: 940, minWidth: 1160, minHeight: 720,
    backgroundColor: "#0f1115",
    title: "nest101",
    show: false,
    webPreferences: { preload: path.join(__dirname, "preload.js"), contextIsolation: true },
  });
  ventana.once("ready-to-show", () => { cerrarSplash(); ventana.show(); });
  ventana.loadURL(`http://127.0.0.1:${PUERTO}/index.html`);
  ventana.on("closed", () => (ventana = null));

  /* #015 — no cerrar encima de trabajo sin guardar.
     Se pregunta UNA vez; a partir de ahí el cierre no se puede detener. Cuando
     el usuario ya dijo que sí, se usa `destroy()` y no `close()`: `close()`
     vuelve a pasar por la página, y una página que se niega a descargarse deja
     la app imposible de cerrar salvo desde el administrador de tareas. */
  ventana.on("close", (e) => {
    if (cerrarConfirmado || !ventana) return;
    e.preventDefault();
    ventana.webContents.send("consultar-cierre");
    // si el renderer no contesta en 4 s, se cierra igual: nunca dejar la app trabada
    setTimeout(() => {
      if (!cerrarConfirmado && ventana) { cerrarConfirmado = true; ventana.destroy(); }
    }, 4000);
  });

  // si la ventana no carga, no dejar al usuario mirando un 404
  ventana.webContents.on("did-fail-load", (_e, code, desc, url) => {
    if (code === -3) return;                       // abortado por navegación normal
    dialog.showErrorBox("No se pudo cargar la interfaz",
      `${desc} (${code})\n${url}\n\nEl backend respondió, pero la interfaz no cargó.`);
  });
  ventana.webContents.on("did-finish-load", async () => {
    try {
      const r = await pedir("/api/diagnostico");
      const d = JSON.parse(r.cuerpo || "{}");
      if (!d.ui_encontrada) {
        dialog.showErrorBox("Instalación incompleta",
          "El backend arrancó pero no encontró la carpeta 'ui'.\n\n" +
          `Buscada en: ${d.raiz}\n\nReinstala la aplicación.`);
      }
    } catch { /* el diagnóstico es informativo */ }
    if (archivoPendiente) {                       // #016
      const r = archivoPendiente;
      archivoPendiente = null;
      setTimeout(() => abrirEnVentana(r), 700);   // deja que la UI termine de armarse
    }
  });
}

function menu() {
  const plantilla = [
    { label: "Archivo", submenu: [
        { label: "Nuevo", accelerator: "CmdOrCtrl+N", click: () => envia("nuevo") },
        { label: "Abrir…", accelerator: "CmdOrCtrl+O", click: () => envia("abrir") },
        { label: "Guardar", accelerator: "CmdOrCtrl+S", click: () => envia("guardar") },
        { type: "separator" },
        { label: "Pantalla de inicio", accelerator: "CmdOrCtrl+I", click: () => envia("inicio") },
        { type: "separator" },
        { label: "Exportar DXF + Excel + PDF", accelerator: "CmdOrCtrl+E", click: () => envia("exportar") },
        { type: "separator" }, { role: "quit", label: "Salir" } ] },
    { label: "Edición", submenu: [
        { label: "Deshacer", accelerator: "CmdOrCtrl+Z", click: () => envia("deshacer") },
        { label: "Rehacer", accelerator: "CmdOrCtrl+Shift+Z", click: () => envia("rehacer") },
        { type: "separator" },
        { role: "cut", label: "Cortar" }, { role: "copy", label: "Copiar" },
        { role: "paste", label: "Pegar" }, { role: "selectAll", label: "Seleccionar todo" } ] },
    { label: "Ayuda", submenu: [
        { label: "Registro de arranque", click: () => {
            if (rutaRegistro && fs.existsSync(rutaRegistro)) shell.openPath(rutaRegistro);
            else dialog.showMessageBox({ type: "info", title: "Registro de arranque",
              message: "Todavía no hay registro de esta sesión.",
              detail: "Se escribe cada vez que la aplicación arranca." });
          } },
        { label: "Diagnóstico del equipo…", click: () => {
            const bat = path.join(path.dirname(app.getPath("exe")), "Diagnostico.bat");
            if (fs.existsSync(bat)) shell.openPath(bat);
            else dialog.showMessageBox({ type: "info", title: "Diagnóstico",
              message: "No se encontró Diagnostico.bat junto a la aplicación." });
          } },
        { type: "separator" },
        { label: "Carpeta de la instalación", click: () =>
            shell.openPath(path.dirname(app.getPath("exe"))) } ] },
    { label: "Ver", submenu: [
        { role: "reload", label: "Recargar" },
        { role: "toggleDevTools", label: "Herramientas de desarrollo" },
        { type: "separator" },
        { role: "resetZoom", label: "Zoom normal" },
        { role: "zoomIn", label: "Acercar" }, { role: "zoomOut", label: "Alejar" },
        { type: "separator" }, { role: "togglefullscreen", label: "Pantalla completa" } ] },
  ];
  Menu.setApplicationMenu(Menu.buildFromTemplate(plantilla));
}
const envia = (c) => ventana?.webContents.send("menu", c);

/* ---------- IPC ---------- */
ipcMain.handle("elegir-carpeta", async () => {
  const r = await dialog.showOpenDialog(ventana, {
    title: "Carpeta de salida", properties: ["openDirectory", "createDirectory"] });
  return r.canceled ? null : r.filePaths[0];
});

ipcMain.handle("guardar-archivo", async (_e, nombre, contenido, rutaActual) => {
  let destino = rutaActual;
  if (!destino) {
    const r = await dialog.showSaveDialog(ventana, {
      title: "Guardar proyecto", defaultPath: nombre,
      filters: [{ name: "Proyecto nest101", extensions: ["t101x"] },
                { name: "Formato anterior", extensions: ["json"] }] });
    if (r.canceled) return null;
    destino = r.filePath;
  }
  fs.writeFileSync(destino, contenido, "utf-8");
  return destino;
});

ipcMain.handle("abrir-archivo", async () => {
  const r = await dialog.showOpenDialog(ventana, {
    title: "Abrir proyecto", properties: ["openFile"],
    filters: [{ name: "Proyecto nest101", extensions: ["t101x", "json"] }] });
  if (r.canceled) return null;
  return { ruta: r.filePaths[0], contenido: fs.readFileSync(r.filePaths[0], "utf-8") };
});

/* ---------- #038 · el proyecto es una carpeta ----------
   Un proyecto son varios muebles, y cada mueble sigue siendo su propio .t101x.
   La carpeta que los contiene ES el proyecto: no hay índice que mantener, no
   hay rutas que se rompan al mover archivos, y un mueble suelto se sigue
   mandando por correo. `proyecto.json` sólo guarda de quién es el trabajo. */
ipcMain.handle("abrir-proyecto", async () => {
  const r = await dialog.showOpenDialog(ventana, {
    title: "Abrir proyecto (elige su carpeta)",
    properties: ["openDirectory", "createDirectory"] });
  if (r.canceled) return null;
  return leerCarpetaProyecto(r.filePaths[0]);
});

ipcMain.handle("leer-proyecto", (_e, carpeta) => {
  try { return leerCarpetaProyecto(carpeta); }
  catch (e) { return { error: String(e.message || e) }; }
});

function leerCarpetaProyecto(carpeta) {
  const ficha = path.join(carpeta, "proyecto.json");
  let datos = { nombre: path.basename(carpeta), cliente: "", obra: "" };
  try { datos = { ...datos, ...JSON.parse(fs.readFileSync(ficha, "utf-8")) }; }
  catch { /* carpeta sin ficha: se toma el nombre de la carpeta y ya */ }
  const muebles = fs.readdirSync(carpeta)
    .filter((n) => n.toLowerCase().endsWith(".t101x"))
    .sort((a, b) => a.localeCompare(b, "es"))
    .map((n) => {
      const ruta = path.join(carpeta, n);
      try { return { ruta, nombre: n.replace(/\.t101x$/i, ""),
                     contenido: fs.readFileSync(ruta, "utf-8") }; }
      catch { return null; }
    })
    .filter(Boolean);
  return { carpeta, ...datos, muebles };
}

ipcMain.handle("guardar-proyecto", (_e, carpeta, datos) => {
  try {
    fs.mkdirSync(carpeta, { recursive: true });
    fs.writeFileSync(path.join(carpeta, "proyecto.json"),
                     JSON.stringify(datos, null, 2), "utf-8");
    return carpeta;
  } catch (e) { return { error: String(e.message || e) }; }
});

ipcMain.handle("abrir-carpeta", (_e, ruta) => shell.openPath(ruta));

// #087 — El enlace de descarga se abre en el NAVEGADOR del equipo, no dentro de
// la app. Dos razones: una descarga de 180 MB en una ventana de Electron no
// tiene barra de progreso ni carpeta de destino, y el navegador ya sabe reanudar
// si se corta. Sólo se abre http(s): un `file://` o un `javascript:` colado aquí
// sería abrir cualquier cosa del disco desde una página.
// #092 — Corre el instalador que la app acaba de bajar y comprobar, y se sale.
// El instalador de NSIS no puede escribir encima de un programa abierto, así
// que hay que cerrar; se hace DESPUÉS de lanzarlo y con un respiro, para que
// el proceso hijo quede vivo cuando el padre se muera.
ipcMain.handle("instalar", (_e, archivo) => {
  try {
    const p = path.resolve(String(archivo));
    // Sólo un .exe de la carpeta de descargas del taller. Un `archivo` que
    // llegara de otro lado sería ejecutar lo que sea desde una página.
    const permitido = path.join(app.getPath("home"), "Taller 101", "descargas");
    if (!p.toLowerCase().endsWith(".exe") || !p.startsWith(permitido)) return false;
    if (!fs.existsSync(p)) return false;
    const hijo = require("child_process").spawn(p, [], {
      detached: true, stdio: "ignore",
    });
    hijo.unref();
    setTimeout(() => app.quit(), 1200);
    return true;
  } catch { return false; }
});

ipcMain.handle("abrir-enlace", (_e, url) => {
  try {
    const u = new URL(String(url));
    if (u.protocol === "http:" || u.protocol === "https:") return shell.openExternal(u.href);
  } catch { /* URL mal formada: no se abre nada */ }
  return false;
});

/* #018 — abrir un proyecto de la lista de recientes, sin diálogo */
ipcMain.handle("leer-archivo", (_e, ruta) => {
  try {
    if (!ruta || !fs.existsSync(ruta)) return { error: "El archivo ya no está en esa ruta." };
    return { ruta, contenido: fs.readFileSync(ruta, "utf-8") };
  } catch (err) {
    return { error: err.message };
  }
});

/* #015 — diálogo nativo de guardar / descartar / cancelar */
ipcMain.handle("preguntar-guardar", async (_e, nombre, accion) => {
  const r = await dialog.showMessageBox(ventana, {
    type: "warning",
    buttons: ["Guardar", "No guardar", "Cancelar"],
    defaultId: 0,
    cancelId: 2,
    title: "Cambios sin guardar",
    message: `«${nombre}» tiene cambios sin guardar.`,
    detail: `Si continúas sin guardar, se pierden.\n\nAcción: ${accion}`,
  });
  return ["guardar", "descartar", "cancelar"][r.response];
});

/* respuesta del renderer al intento de cierre */
ipcMain.on("resolver-cierre", (_e, puedeCerrar) => {
  if (!puedeCerrar || !ventana) return;
  cerrarConfirmado = true;
  ventana.destroy();          // ver el comentario del handler de «close»
});

/* ---------- ciclo de vida ---------- */
// #016 — una sola instancia: el segundo doble clic abre el archivo en la ventana viva
/* #021 — la ventana carga http://127.0.0.1:PUERTO/index.html. Chromium sí usa el
   proxy del sistema, y un proxy o VPN sin excepción para loopback deja la ventana
   en blanco aunque el backend responda. Se exime el loopback antes de crear
   cualquier sesión. */
app.commandLine.appendSwitch("proxy-bypass-list", "<-loopback>");
app.commandLine.appendSwitch("no-proxy-server");

const soloUna = app.requestSingleInstanceLock();
if (!soloUna) {
  app.quit();
} else {
  app.on("second-instance", (_e, argv) => {
    const r = archivoDeArgv(argv);
    if (r) abrirEnVentana(r);
    else if (ventana) { if (ventana.isMinimized()) ventana.restore(); ventana.focus(); }
  });

  // macOS entrega el archivo por evento, no por argv
  app.on("open-file", (e, ruta) => {
    e.preventDefault();
    if (ventana) abrirEnVentana(ruta);
    else archivoPendiente = ruta;
  });

  app.whenReady().then(async () => {
    archivoPendiente = archivoDeArgv(process.argv);
    crearSplash();                                   // #020: nunca una espera muda
    registrar(`nest101 ${app.getVersion()} · ${process.platform} ${process.arch}`);
    registrar(`recursos: ${process.resourcesPath}`);
    PUERTO = await puertoLibre(8760);
    registrar(`puerto ${PUERTO}`);

    try {
      const { session } = require("electron");
      await session.defaultSession.setProxy({ mode: "direct" });
      const vp = await session.defaultSession.resolveProxy(`http://127.0.0.1:${PUERTO}/`);
      registrar(`proxy para el backend: ${vp}`);
    } catch (e) { registrar("no se pudo revisar el proxy: " + e.message); }

    let motivo = null;
    try {
      motivo = await arrancarBackend();
    } catch (e) {
      motivo = e && e.message ? e.message : String(e);
      registrar("excepción al arrancar: " + motivo);
    }
    if (motivo) {
      cerrarSplash();
      avisarFalloArranque(motivo);
      app.quit();
      return;
    }
    menu();
    crearVentana();
    app.on("activate", () => { if (!BrowserWindow.getAllWindows().length) crearVentana(); });
  });
}

app.on("window-all-closed", () => { if (process.platform !== "darwin") app.quit(); });
app.on("before-quit", () => { try { backend?.kill(); } catch {} });
process.on("exit", () => { try { backend?.kill(); } catch {} });
