const { contextBridge, ipcRenderer } = require("electron");

contextBridge.exposeInMainWorld("despz", {
  elegirCarpeta: () => ipcRenderer.invoke("elegir-carpeta"),
  // rutaActual: si ya se guardó antes, sobreescribe sin volver a preguntar
  guardarArchivo: (nombre, contenido, rutaActual) =>
    ipcRenderer.invoke("guardar-archivo", nombre, contenido, rutaActual),
  abrirArchivo: () => ipcRenderer.invoke("abrir-archivo"),
  // #018 — recientes: abrir por ruta, sin pasar por el diálogo
  leerArchivo: (ruta) => ipcRenderer.invoke("leer-archivo", ruta),
  abrirCarpeta: (ruta) => ipcRenderer.invoke("abrir-carpeta", ruta),
  abrirEnlace: (url) => ipcRenderer.invoke("abrir-enlace", url),   // #087
  instalar: (archivo) => ipcRenderer.invoke("instalar", archivo), // #092

  // #038 — el proyecto es una carpeta con los .t101x de sus muebles
  abrirProyecto: () => ipcRenderer.invoke("abrir-proyecto"),
  leerProyecto: (carpeta) => ipcRenderer.invoke("leer-proyecto", carpeta),
  guardarProyecto: (carpeta, datos) =>
    ipcRenderer.invoke("guardar-proyecto", carpeta, datos),
  onMenu: (cb) => ipcRenderer.on("menu", (_e, comando) => cb(comando)),

  // #015 — diálogo nativo Guardar / No guardar / Cancelar
  preguntarGuardar: (nombre, accion) =>
    ipcRenderer.invoke("preguntar-guardar", nombre, accion),

  /** #015 — la ventana pide permiso antes de cerrarse.
   *  cb() devuelve true si se puede cerrar. */
  alCerrar: (cb) => ipcRenderer.on("consultar-cierre", async () => {
    let ok = true;
    try { ok = await cb(); } catch { ok = true; }
    ipcRenderer.send("resolver-cierre", ok);
  }),

  // #016 — la app se abrió con un .t101x (doble clic o «Abrir con»)
  alAbrirArchivo: (cb) =>
    ipcRenderer.on("abrir-archivo-externo", (_e, datos) => cb(datos)),
});
