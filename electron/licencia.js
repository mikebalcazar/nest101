/* La puerta de licencia de nest101  ·  contrato 0.20.1 de la suite.
 *
 * Encargo de Mike (19-sep-2026): que la app se abra entrando con la cuenta de
 * la suite —correo y contraseña, o Google— y que la licencia vaya ligada al
 * correo. La clave tecleada se queda como segunda forma; las dos viven en la
 * MISMA pantalla, que sirve la suite, así que aquí no se construye ninguna.
 *
 * Este archivo es sólo lo que necesita Electron: abrir esa pantalla y recoger
 * el token. Lo demás —la huella del equipo, guardar, el latido— está en
 * `licencia-nucleo.js`, que se puede medir con node a secas.
 *
 * SIN INTERNET: el token trae su propio `hasta` firmado. Mientras ese día no
 * pase, la app abre sin preguntarle a nadie. Cuando pasa y no hay forma de
 * llegar a la suite, NO abre, y lo dice con esas palabras: es mejor una frase
 * clara que una app que se comporta raro.
 */

const { BrowserWindow, app } = require("electron");
const path = require("path");
const n = require("./licencia-nucleo");

const API = (process.env.SUITE101_API || n.API_POR_OMISION).replace(/\/+$/, "");
const PROGRAMA = "nest101";
const NOMBRE = "nest101";

const carpeta = () => app.getPath("userData");
const huella = () => n.huella(carpeta());
const guardada = () => n.guardada(carpeta());

/** Abre la pantalla de la suite y espera a que active. La pantalla es la
 *  misma para el camino de la cuenta y el de la clave tecleada; aquí sólo se
 *  escucha el final: `window.__t101_licencia` y el fragmento `#listo`. */
function pedirEnPantalla(version, aviso) {
  return new Promise((resolve) => {
    const v = new BrowserWindow({
      width: 480, height: 700, resizable: false, minimizable: false, maximizable: false,
      title: `Activar ${NOMBRE}`,
      autoHideMenuBar: true,
      icon: path.join(__dirname, "..", "build", "icon.ico"),
      // Partición propia y persistente: la sesión de la suite se queda, así
      // que la segunda vez no hay que volver a escribir la contraseña.
      webPreferences: { contextIsolation: true, nodeIntegration: false, partition: "persist:suite101" },
    });
    v.setMenu(null);

    let listo = false;
    const recoger = async (url) => {
      if (listo || !String(url).includes("#listo")) return;
      let dato = null;
      try { dato = await v.webContents.executeJavaScript("window.__t101_licencia"); } catch { /* se cerró */ }
      if (!dato?.token) return;
      listo = true;
      n.guardar(carpeta(), { token: dato.token, hasta: dato.hasta, licencia: dato.licencia, correo: dato.correo || null });
      // Que alcance a leerse el «listo» antes de que la ventana desaparezca.
      setTimeout(() => { if (!v.isDestroyed()) v.destroy(); }, 900);
      resolve({ ok: true });
    };
    v.webContents.on("did-navigate-in-page", (_e, url) => { recoger(url); });
    v.webContents.on("did-navigate", (_e, url) => { recoger(url); });
    v.on("closed", () => { if (!listo) resolve({ ok: false, motivo: "cancelado" }); });

    v.loadURL(n.direccionDeLaPantalla({ api: API, programa: PROGRAMA, nombre: NOMBRE, huella: huella(), version, aviso }))
      .catch(() => {
        if (!v.isDestroyed()) v.destroy();
        resolve({ ok: false, motivo: "sin_red" });
      });
  });
}

/** La puerta completa, que es lo que llama el arranque.
 *
 *  `{ ok: true }` cuando la app puede abrir; `{ ok: false, motivo }` cuando
 *  no: 'cancelado' (cerró la ventana) o 'sin_red' (venció y no se pudo llegar
 *  a la suite).
 */
async function asegurar({ version, avisar } = {}) {
  const d = guardada();

  if (d) {
    /* Con el token todavía vigente por su propia fecha se abre y ya. El
     * latido se manda igual, pero SIN detener el arranque: lo que se entere
     * se aplica en el siguiente. Un taller no tiene por qué esperar a que
     * responda un servidor para abrir un plano. */
    if (n.alCorriente(d)) {
      n.latido({ api: API, carpeta: carpeta(), nombre: NOMBRE, d, version })
        .then((r) => { if (r.vencida) n.olvidar(carpeta()); })
        .catch(() => {});
      return { ok: true, licencia: d.licencia };
    }
    if (avisar) avisar("Revisando la licencia");
    const r = await n.latido({ api: API, carpeta: carpeta(), nombre: NOMBRE, d, version });
    if (r.ok) return { ok: true, licencia: guardada()?.licencia };
    if (r.sinRed) return { ok: false, motivo: "sin_red" };
    n.olvidar(carpeta());
    return pedirEnPantalla(version, r.porque);
  }

  if (avisar) avisar("Activando tu licencia");
  return pedirEnPantalla(version);
}

/* #100 — «¿Con qué cuenta estoy?», y poder cambiarla.
 *
 * Faltaba: una vez activado, no había manera de ver con qué correo quedó el
 * equipo ni hasta cuándo, y la única forma de pasarlo a otra cuenta era
 * borrar a mano un archivo dentro de AppData. Eso no se le pide a nadie.
 *
 * El diálogo vive aquí y no en `main.js` a propósito: `main.js` ya lleva el
 * arranque, el backend, el menú y los avisos, y esto es de la licencia. Desde
 * allá se llama con un renglón. El texto que se enseña se arma en el núcleo,
 * para poder medirlo sin abrir una ventana.
 */
function resumen() {
  return n.resumen(guardada(), { nombre: NOMBRE, huella: huella() });
}

/** El menú «Licencia de este equipo…». Devuelve true si se va a reiniciar. */
function abrirMenu() {
  const { dialog } = require("electron");
  const r = resumen();
  const cual = dialog.showMessageBoxSync({
    type: r.activa ? "info" : "warning",
    title: "Licencia",
    message: r.titulo,
    detail: r.lineas.join("\n"),
    buttons: r.activa ? ["Cerrar", "Cambiar de cuenta…"] : ["Cerrar", "Activar ahora…"],
    defaultId: 0, cancelId: 0, noLink: true,
  });
  if (cual !== 1) return false;

  // Se pregunta otra vez porque esto cierra el programa y libera el lugar de
  // este equipo. Un clic de más vale menos que un taller cerrado sin querer.
  const seguro = dialog.showMessageBoxSync({
    type: "question", title: "Cambiar de cuenta",
    message: "Se va a cerrar nest101 y se abrirá de nuevo para entrar con otra cuenta.",
    detail: "El lugar de este equipo se libera en la cuenta de ahora. "
          + "Tus proyectos y tu carpeta de taller no se tocan.",
    buttons: ["Cancelar", "Cerrar y cambiar"], defaultId: 0, cancelId: 0, noLink: true,
  });
  if (seguro !== 1) return false;
  cambiarDeCuenta();
  return true;
}

/** Olvida lo guardado y reinicia para volver a pasar la puerta.
 *
 *  Se reinicia en vez de abrir la pantalla encima: la puerta está en el
 *  arranque, ANTES del motor de cálculo, y volver a pasarla con el programa ya
 *  abierto dejaría medio programa con la cuenta vieja. Reiniciar es una vuelta
 *  más larga y no deja estados a medias.
 */
function cambiarDeCuenta() {
  n.olvidar(carpeta());
  app.relaunch();
  app.exit(0);
}

module.exports = { asegurar, huella, guardada, resumen, abrirMenu, cambiarDeCuenta, API, PROGRAMA, NOMBRE };
