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

const { BrowserWindow, app, net } = require("electron");
const n = require("./licencia-nucleo");

const API = (process.env.SUITE101_API || n.API_POR_OMISION).replace(/\/+$/, "");
const PROGRAMA = "nest101";
const NOMBRE = "nest101";

const carpeta = () => app.getPath("userData");
const huella = () => n.huella(carpeta());
const guardada = () => n.guardada(carpeta());

/* #108 — Lo que de verdad pasa cuando la pantalla de activación no carga.
 *
 * Con la 0.19.3 Mike ya vio el motivo, y el motivo no cuadraba:
 *
 *     ERR_FAILED (-2) loading 'https://…/licencias/entrar?…'
 *     TypeError: Object has been destroyed   ← 1 ms después
 *
 * Medido desde aquí: esa MISMA dirección abre perfecto en su Chrome, en su
 * máquina, en ese momento. Así que no es la red, ni el proxy, ni la VPN: lo
 * que se muere es la ventana. Y dos detalles del registro lo confirman: no
 * hubo `did-fail-load` —la promesa se rechazó por el camino genérico, que es
 * el de «la navegación se detuvo sin llegar»— y, un milisegundo después, el
 * contenido de la ventana ya estaba destruido.
 *
 * No se adivina. Esta versión apunta lo que falta para saberlo:
 *
 *  · si el proceso de la ventana se cae, y CON QUÉ MOTIVO (`render-process-gone`
 *    trae `reason` y `exitCode`: «crashed», «killed», «launch-failed»… un
 *    antivirus de empresa matando el proceso se ve ahí y en ningún otro lado);
 *  · si la suite contesta DESDE EL PROCESO PRINCIPAL, sin ventana de por medio
 *    (`net.request`): separa «esta computadora no llega» de «la ventana no
 *    pudo enseñarlo», que es justo lo que no se podía distinguir;
 *  · cada paso de la navegación, con su hora.
 *
 * Y de paso intenta otra vez con una ventana limpia, sin la sesión guardada:
 * si lo que estorba es la carpeta `Partitions/suite101` —cosa que pasa—, el
 * segundo intento abre y el taller ni se entera.
 */
function pedirEnPantalla(version, aviso, avisar = () => {}) {
  const direccion = n.direccionDeLaPantalla({
    api: API, programa: PROGRAMA, nombre: NOMBRE, huella: huella(), version, aviso });

  // El primer intento usa la sesión guardada, que es la que hace que la
  // segunda vez no haya que volver a escribir la contraseña. Si falla, el
  // segundo va con una sesión de usar y tirar: cuesta volver a entrar, y vale
  // más eso que no abrir.
  return unIntento({ direccion, avisar, guardarSesion: true, quedarse: false })
    .then(async (r) => {
      if (r.ok || r.motivo === "cancelado") return r;
      avisar("segundo intento, con una sesión limpia");
      const r2 = await unIntento({ direccion, avisar, guardarSesion: false, quedarse: true });
      // Se reporta el motivo del SEGUNDO, que es el último que se vio, pero
      // sin perder el del primero: si son distintos, eso es el dato.
      if (!r2.ok && r.detalle && r2.detalle && r.detalle !== r2.detalle) {
        r2.detalle = `${r2.detalle} · el primer intento fue: ${r.detalle}`;
      }
      return r2;
    });
}

/** Un intento de abrir la pantalla. `quedarse` dice si la ventana se queda en
 *  pantalla enseñando el motivo (el último intento) o se cierra calladita para
 *  dejar sitio al siguiente. */
function unIntento({ direccion, avisar, guardarSesion, quedarse }) {
  return new Promise((resolve) => {
    let resuelto = false, listo = false, fallo = null, probada = false, dichoRed = "";
    const acabar = (r) => { if (!resuelto) { resuelto = true; resolve(r); } };
    const ahora = () => new Date().toISOString().slice(11, 23);

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
        webPreferences: {
          contextIsolation: true, nodeIntegration: false,
          ...(guardarSesion ? { partition: "persist:suite101" } : {}),
        },
      });
    } catch (e) {
      avisar("no se pudo abrir la ventana de activación: " + e.message);
      acabar({ ok: false, motivo: "ventana", detalle: e.message });
      return;
    }
    v.setMenu(null);
    const wc = v.webContents;

    /** Enseñar algo en la ventana sin que eso pueda tumbar el programa.
     *  La 0.19.3 llamaba a `loadURL` comprobando sólo la ventana, y el que
     *  estaba muerto era su CONTENIDO: `v.isDestroyed()` decía que no y
     *  `loadURL` reventaba con «Object has been destroyed». Se comprueban los
     *  dos, y aun así va dentro de un try: entre la comprobación y la llamada
     *  puede morirse. */
    const enPantalla = (desc, codigo) => {
      if (!quedarse) return;
      try {
        if (v.isDestroyed() || wc.isDestroyed()) {
          avisar("no se pudo enseñar el motivo: la ventana ya no está");
          return;
        }
        wc.loadURL(pantallaDeFallo(desc, codigo)).catch((e) =>
          avisar("no se pudo enseñar el motivo: " + e.message));
      } catch (e) {
        avisar("no se pudo enseñar el motivo: " + e.message);
      }
    };

    const cerrar = () => {
      try { if (!v.isDestroyed()) v.destroy(); } catch { /* ya no estaba */ }
    };

    /** Lo que se hace cuando la pantalla no cargó, venga por donde venga. */
    const noCargo = async (desc, codigo) => {
      if (listo || fallo) return;
      fallo = { codigo, desc };
      avisar(`la pantalla de activación no cargó: ${desc} (${codigo})`);
      if (!probada) {                       // una sola vez por intento
        probada = true;
        dichoRed = await probarRed(direccion, avisar);
      }
      if (quedarse) enPantalla(desc, codigo);
      else cerrar();
    };

    /* ---- el rastro: cada paso, con su hora ---- */
    wc.on("did-start-loading", () => avisar(`${ahora()} empieza a cargar`));
    wc.on("did-stop-loading", () => avisar(`${ahora()} deja de cargar`));
    wc.on("dom-ready", () => avisar(`${ahora()} la pantalla ya tiene contenido`));
    wc.on("destroyed", () => avisar(`${ahora()} el contenido de la ventana se destruyó`));
    wc.on("unresponsive", () => avisar(`${ahora()} la ventana dejó de responder`));
    v.on("close", () => avisar(`${ahora()} se está cerrando la ventana`));

    /* El dato que no teníamos: si el proceso de la ventana se cae y por qué.
     * `reason` dice «crashed», «killed», «oom», «launch-failed»… y un
     * antivirus de empresa que mata el proceso se ve justo aquí. */
    wc.on("render-process-gone", (_e, d) => {
      avisar(`${ahora()} el proceso de la ventana se fue: ${d.reason} (salida ${d.exitCode})`);
      noCargo(`el proceso de la ventana se fue (${d.reason})`, d.exitCode || 0);
    });

    const recoger = async (url) => {
      if (listo || !String(url).includes("#listo")) return;
      let dato = null;
      try { dato = await wc.executeJavaScript("window.__t101_licencia"); } catch { /* se cerró */ }
      if (!dato?.token) return;
      listo = true;
      n.guardar(carpeta(), { token: dato.token, hasta: dato.hasta, licencia: dato.licencia, correo: dato.correo || null });
      avisar("licencia activada y guardada");
      // Que alcance a leerse el «listo» antes de que la ventana desaparezca.
      setTimeout(() => { try { if (!v.isDestroyed()) v.destroy(); } catch { /* ya */ } }, 900);
      acabar({ ok: true });
    };
    wc.on("did-navigate-in-page", (_e, url) => { recoger(url); });
    wc.on("did-navigate", (_e, url) => { recoger(url); });

    // -3 es ERR_ABORTED: una redirección que pisa a la anterior. Es normal
    // —la pantalla de la suite redirige al volver de Google— y tomarla por
    // falla era cerrar la ventana a media activación.
    wc.on("did-fail-load", (_e, codigo, desc, _url, esPrincipal) => {
      if (!esPrincipal || codigo === -3 || listo) return;
      noCargo(desc, codigo);
    });

    v.on("closed", () => {
      if (listo) return;
      // El resultado de la prueba sin ventana viaja en el detalle: es lo
      // primero que hay que saber al leer el aviso, porque decide si el
      // problema es la red o el programa.
      acabar(fallo
        ? { ok: false, motivo: "sin_red",
            detalle: `${fallo.desc} (${fallo.codigo})${dichoRed ? ` · ${dichoRed}` : ""}` }
        : { ok: false, motivo: "cancelado" });
    });

    avisar(`abriendo la pantalla de activación${guardarSesion ? "" : " (sesión limpia)"}`);
    v.loadURL(direccion).catch((e) => {
      // Esta rama es el camino genérico de Electron: la navegación se detuvo
      // sin llegar y sin `did-fail-load`. Es justo por donde se cayó la
      // 0.19.3 en la máquina de Mike.
      noCargo(e.message, 0);
    });
  });
}

/** Una llamada a la suite DESDE EL PROCESO PRINCIPAL, sin ventana de por medio.
 *
 *  Es la que separa las dos cosas que hasta ahora se confundían: «esta
 *  computadora no llega a la suite» y «la ventana no pudo enseñarla». Si esto
 *  contesta 200 y la ventana no cargó, el problema no es la red — y eso cambia
 *  por completo qué hay que arreglar.
 *
 *  No decide nada: sólo deja el renglón en el registro. */
function probarRed(url, avisar) {
  return new Promise((resolve) => {
    let acabo = false;
    const fin = (t) => { if (!acabo) { acabo = true; avisar("prueba de red sin ventana: " + t); resolve(t); } };
    const reloj = setTimeout(() => fin("no contestó en 15 s"), 15000);
    try {
      const p = net.request({ method: "GET", url });
      p.on("response", (r) => {
        r.on("data", () => {});
        r.on("end", () => {});
        clearTimeout(reloj);
        fin(`la suite contestó ${r.statusCode}`);
      });
      p.on("error", (e) => { clearTimeout(reloj); fin("no se pudo: " + e.message); });
      p.end();
    } catch (e) {
      clearTimeout(reloj);
      fin("no se pudo ni intentar: " + e.message);
    }
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
