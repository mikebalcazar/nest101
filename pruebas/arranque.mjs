/* #106 — La puerta de licencia, medida con Electron de verdad.
 *
 * Mike, 11-oct-2026: «nest 0.19.2 no abre. Se ve que apenas aparece una
 * ventana pero muy rápido y desaparece». Su `arranque.log` acababa en
 * «Activando tu licencia»: la pantalla de activación no cargó, la ventana se
 * destruía sola y el programa se cerraba sin una palabra, reportando además el
 * motivo equivocado («cancelado», aunque nadie cancelara).
 *
 * Esto lo reproduce. `pruebas/licencia.mjs` mide el núcleo con node a secas;
 * aquí hace falta Electron porque lo que se arregló son ventanas:
 *
 *     npx electron pruebas/arranque.mjs        # sale 0 si todo está bien
 *
 * En Linux sin pantalla: `xvfb-run -a npx electron --no-sandbox pruebas/arranque.mjs`.
 * No corre en el armado —el corredor no tiene pantalla y Electron no está
 * instalado en el runtime que viaja—, se corre a mano al tocar la puerta.
 */
import { app } from "electron";
import http from "node:http";
import fs from "node:fs";
import os from "node:os";
import path from "node:path";
import { createRequire } from "node:module";
import { fileURLToPath } from "node:url";

const require = createRequire(import.meta.url);
// La puerta, por ruta propia: `app.getAppPath()` apunta a pruebas/ cuando
// Electron arranca con este archivo.
const PUERTA = fileURLToPath(new URL("../electron/licencia.js", import.meta.url));
const FALLAS = [];
const chk = (cond, msg) => {
  console.log((cond ? "  OK   " : "  FALLA") + " " + msg);
  if (!cond) FALLAS.push(msg);
};
const esperar = (ms) => new Promise((r) => setTimeout(r, ms));

/* La comprobación que importa, y la que delata lo de Mike: si el programa se
 * cierra solo antes de acabar, eso ES la falla. Con el código de la 0.19.2
 * esta prueba no imprimía ni una línea —se moría a media medición y salía con
 * 0, igual que en su máquina—, que es la clase de falla que no se puede ni
 * reportar. */
/* Como en `main.js`: mientras la puerta está abierta, quedarse sin ventanas NO
 * cierra el programa. Entre el primer intento y el segundo hay un instante sin
 * ninguna, y sin este escucha Electron cerraría la aplicación ahí mismo —que
 * es exactamente lo que `enLaPuerta` evita allá. */
app.on("window-all-closed", () => {});

let acabo = false;
app.on("will-quit", (e) => {
  if (acabo) return;
  e.preventDefault();
  console.log("  FALLA el programa se cerró solo a media prueba, sin decir nada");
  console.log("\n1 FALLAS");
  acabo = true;
  app.exit(1);
});

/** La ventana de activación, si está abierta. */
const ventanaActivar = () => require("electron").BrowserWindow.getAllWindows()
  .find((v) => !v.isDestroyed() && /Activar/.test(v.getTitle() || ""));

app.whenReady().then(async () => {
  // Nada toca la licencia real: userData va a una carpeta de usar y tirar.
  const tmp = fs.mkdtempSync(path.join(os.tmpdir(), "t106-"));
  app.setPath("userData", tmp);

  // ---------------------------------------------------------------- 1 · no carga
  //
  // Es EXACTAMENTE lo de Mike: la suite no se alcanza. Aquí se consigue
  // apuntando a un puerto donde no hay nada, que falla igual de rápido.
  // Un puerto alto y cerrado: falla con ERR_CONNECTION_REFUSED, que es la
  // misma familia de fallo que un proxy que no deja pasar.
  process.env.SUITE101_API = "http://127.0.0.1:49151";
  const licencia = require(PUERTA);

  const dicho = [];
  const puerta = licencia.asegurar({ version: "0.0.0", avisar: (t) => dicho.push(t) });
  await esperar(2500);

  const v = ventanaActivar();
  chk(!!v, "la ventana de activación se queda abierta cuando la pantalla no carga");
  if (v) {
    const url = v.webContents.getURL();
    chk(url.startsWith("data:text/html"),
        "y enseña el motivo en vez de desaparecer");
    const texto = await v.webContents.executeJavaScript("document.body.innerText")
      .catch(() => "");
    chk(/proxy|VPN/i.test(texto), "el motivo nombra el proxy y la VPN, que es lo más común");
    chk(/ERR_|\(\d|\(-?\d/.test(texto), `y trae el código crudo para reportarlo: ${
      (texto.match(/ERR_[A-Z_]+/) || ["sin código"])[0]}`);
    chk(dicho.some((t) => /no cargó/.test(t)),
        `queda apuntado en el registro: «${dicho.find((x) => /no cargó/.test(x))}»`);
    // #108 — lo que se agregó para poder diagnosticar la máquina de Mike
    chk(dicho.some((t) => /prueba de red sin ventana/.test(t)),
        `se prueba la red SIN ventana, que es lo que separa los dos casos: «${
          dicho.find((x) => /prueba de red/.test(x))}»`);
    chk(dicho.some((t) => /sesión limpia/.test(t)),
        "y se intenta otra vez con una sesión limpia, por si estorba la guardada");
    chk(dicho.filter((t) => /abriendo la pantalla/.test(t)).length === 2,
        `dos intentos, ni uno más: ${dicho.filter((t) => /abriendo la pantalla/.test(t)).length}`);
    v.close();                      // es lo que haría el usuario
  }
  const r1 = await puerta;
  chk(r1.ok === false && r1.motivo === "sin_red",
      `cerrar esa ventana es «sin_red», no «cancelado»: ${JSON.stringify(r1)}`);
  chk(!!r1.detalle, `y el detalle viaja para el diálogo: ${r1.detalle}`);
  chk(!fs.existsSync(path.join(tmp, "licencia.json")),
      "no se inventó ninguna licencia por el camino");

  // ---------------------------------------------------------------- 2 · sí carga
  //
  // La pantalla abre y el usuario la cierra sin entrar: eso SÍ es cancelado.
  const servidor = http.createServer((_q, s) => {
    s.writeHead(200, { "Content-Type": "text/html; charset=utf-8" });
    s.end("<!doctype html><meta charset=utf-8><h1>pantalla de la suite</h1>");
  });
  await new Promise((r) => servidor.listen(0, "127.0.0.1", r));
  process.env.SUITE101_API = `http://127.0.0.1:${servidor.address().port}`;
  delete require.cache[require.resolve(PUERTA)];
  const licencia2 = require(PUERTA);

  const puerta2 = licencia2.asegurar({ version: "0.0.0", avisar: () => {} });
  await esperar(2000);
  const v2 = ventanaActivar();
  chk(!!v2, "con la pantalla sirviendo, la ventana abre normal");
  if (v2) {
    const t2 = await v2.webContents.executeJavaScript("document.body.innerText").catch(() => "");
    chk(/pantalla de la suite/.test(t2), "y enseña la pantalla de la suite, no la de fallo");
    v2.close();
  }
  const r2 = await puerta2;
  chk(r2.ok === false && r2.motivo === "cancelado",
      `cerrarla sin entrar sí es «cancelado»: ${JSON.stringify(r2)}`);
  servidor.close();

  // ---------------------------------------------------------------- 3 · se dice
  for (const [motivo, debe] of [
      ["sin_red", /proxy/i], ["cancelado", /vuelve a abrir/i],
      ["ventana", /falla del programa/i], ["inventado", /no se sabe/i]]) {
    const d = licencia2.noAbrio(motivo, "detalle de prueba");
    chk(debe.test(d.detalle) && d.titulo.length > 10 && /arranque\.log/.test(d.detalle),
        `«${motivo}» se explica y manda al registro: ${d.titulo}`);
  }

  // ---------------------------------------------------------------- 4 · #111
  //
  // El hecho en el que se apoya el arreglo de la 0.19.7: `window-all-closed`
  // se emite DENTRO de `destroy()`, de forma síncrona. Por eso la guardia
  // tiene que estar puesta ANTES de cerrar el splash, no después. Si Electron
  // cambiara esto algún día, aquí se sabría.
  {
    const { BrowserWindow } = require("electron");
    // que no quede ninguna ventana de los pasos anteriores: el evento sólo
    // sale cuando se cierra la ÚLTIMA
    for (const w of BrowserWindow.getAllWindows()) { try { w.destroy(); } catch { /* ya */ } }
    await esperar(300);
    let guardia = false, vistoCon = null;
    const escucha = () => { vistoCon = guardia; };
    app.on("window-all-closed", escucha);
    const s = new BrowserWindow({ show: false });
    s.destroy();
    guardia = true;
    app.removeListener("window-all-closed", escucha);
    chk(vistoCon === false,
        "cerrar la última ventana emite «window-all-closed» ahí mismo, antes del siguiente renglón");
  }

  fs.rmSync(tmp, { recursive: true, force: true });
  acabo = true;
  console.log(`\n${FALLAS.length ? FALLAS.length + " FALLAS" : "todo bien"}`);
  app.exit(FALLAS.length ? 1 : 0);
});
