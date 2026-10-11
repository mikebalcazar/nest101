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
function pedirEnPantalla(version, aviso, avisar = () => {}) {
  return new Promise((resolve) => {
    let resuelto = false;
    const acabar = (r) => { if (!resuelto) { resuelto = true; resolve(r); } };

    let v;
    try {
      v = new BrowserWindow({
        width: 480, height: 700, resizable: false, minimizable: false, maximizable: false,
        title: `Activar ${NOMBRE}`,
        autoHideMenuBar: true,
        // #106 — Sin `icon`: apuntaba a `build/icon.ico`, que NO viaja dentro
        // del paquete (`files` del package.json empaqueta sólo `electron/**`).
        // Medido: una ruta que no existe no revienta, pero tampoco pinta nada,
        // y dejarla escrita hacía creer que el ícono estaba puesto.
        webPreferences: { contextIsolation: true, nodeIntegration: false, partition: "persist:suite101" },
      });
    } catch (e) {
      avisar("no se pudo abrir la ventana de activación: " + e.message);
      acabar({ ok: false, motivo: "ventana", detalle: e.message });
      return;
    }
    v.setMenu(null);

    let listo = false;
    let fallo = null;          // #106 — el motivo real, para no llamarlo «cancelado»

    const recoger = async (url) => {
      if (listo || !String(url).includes("#listo")) return;
      let dato = null;
      try { dato = await v.webContents.executeJavaScript("window.__t101_licencia"); } catch { /* se cerró */ }
      if (!dato?.token) return;
      listo = true;
      n.guardar(carpeta(), { token: dato.token, hasta: dato.hasta, licencia: dato.licencia, correo: dato.correo || null });
      avisar("licencia activada y guardada");
      // Que alcance a leerse el «listo» antes de que la ventana desaparezca.
      setTimeout(() => { if (!v.isDestroyed()) v.destroy(); }, 900);
      acabar({ ok: true });
    };
    v.webContents.on("did-navigate-in-page", (_e, url) => { recoger(url); });
    v.webContents.on("did-navigate", (_e, url) => { recoger(url); });

    /* #106 — Lo que de verdad le pasó a Mike.
     *
     * Antes, si la pantalla no cargaba se DESTRUÍA la ventana y se resolvía
     * «sin_red»… sólo que destruir dispara `closed`, que resolvía primero y
     * con «cancelado». Arriba, el arranque sólo enseñaba diálogo para
     * «sin_red», así que el programa se cerraba callado: una ventana que
     * aparece y desaparece, y ni una palabra.
     *
     * Ahora la ventana NO se destruye: se queda enseñando el motivo, que es
     * algo que el taller puede leer y reportar. Y el motivo viaja aparte del
     * cierre, así que ya no se confunde con haber cancelado.
     */
    v.webContents.on("did-fail-load", (_e, codigo, desc, url, esPrincipal) => {
      // -3 es ERR_ABORTED: una redirección que pisa a la anterior. Es normal
      // —la pantalla de la suite redirige al volver de Google— y tomarla por
      // falla era cerrar la ventana a media activación.
      if (!esPrincipal || codigo === -3 || listo) return;
      fallo = { codigo, desc };
      avisar(`la pantalla de activación no cargó: ${desc} (${codigo})`);
      if (!v.isDestroyed()) v.loadURL(pantallaDeFallo(desc, codigo)).catch(() => {});
    });

    v.on("closed", () => {
      if (listo) return;
      acabar(fallo
        ? { ok: false, motivo: "sin_red", detalle: `${fallo.desc} (${fallo.codigo})` }
        : { ok: false, motivo: "cancelado" });
    });

    const direccion = n.direccionDeLaPantalla({
      api: API, programa: PROGRAMA, nombre: NOMBRE, huella: huella(), version, aviso });
    avisar("abriendo la pantalla de activación");
    v.loadURL(direccion).catch((e) => {
      // No se destruye nada: `did-fail-load` ya dejó el motivo en pantalla.
      // Esta rama sólo existe para que la promesa no quede colgada sin rastro.
      if (!fallo) {
        fallo = { codigo: 0, desc: e.message };
        avisar("no se pudo cargar la pantalla de activación: " + e.message);
        if (!v.isDestroyed()) v.loadURL(pantallaDeFallo(e.message, 0)).catch(() => {});
      }
    });
  });
}

/** La pantalla propia que se enseña cuando la de la suite no carga.
 *
 *  Va como `data:` y no como archivo porque tiene que poder enseñarse incluso
 *  si lo que falló fue leer del disco, y porque así no hay un archivo más que
 *  empaquetar —que es justo lo que salió mal con el ícono—. */
function pantallaDeFallo(desc, codigo) {
  const texto = `
    <!doctype html><meta charset="utf-8">
    <style>
      body{font:14px/1.6 system-ui,Segoe UI,sans-serif;background:#16181c;color:#e7e9ee;
           margin:0;padding:34px 30px}
      h1{font-size:17px;margin:0 0 14px}
      p{color:#aeb4c0;margin:0 0 12px}
      code{background:#0f1115;border:1px solid #2a2e37;border-radius:5px;
           padding:2px 6px;color:#cfd4de;font-size:12.5px}
      .ojo{border-left:3px solid #d08b2c;background:#241d12;padding:10px 12px;
           border-radius:0 6px 6px 0;margin:16px 0}
    </style>
    <h1>No se pudo abrir la pantalla de activación</h1>
    <p>nest101 necesita entrar una vez a la suite para activar este equipo, y
       no llegó.</p>
    <div class="ojo"><code>${String(desc).replace(/[<&]/g, "")} (${codigo})</code></div>
    <p>Lo más común es que esta computadora salga a internet por un proxy o una
       VPN de la empresa que no deja pasar a la suite. También puede ser que no
       haya internet en este momento.</p>
    <p>Cierra esta ventana y vuelve a abrir nest101 cuando se arregle. El
       detalle queda apuntado en <code>arranque.log</code>, en la carpeta de
       datos de nest101.</p>`;
  return "data:text/html;charset=utf-8," + encodeURIComponent(texto);
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
    return pedirEnPantalla(version, r.porque, avisar);
  }

  if (avisar) avisar("Activando tu licencia");
  return pedirEnPantalla(version, undefined, avisar);
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

/** #106 — Por qué no abrió, en palabras, para el diálogo del arranque. */
const noAbrio = (motivo, detalle) => n.noAbrio(motivo, detalle, NOMBRE);

module.exports = { asegurar, huella, guardada, resumen, abrirMenu, cambiarDeCuenta, noAbrio, API, PROGRAMA, NOMBRE };
