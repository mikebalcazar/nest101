/* El núcleo de la puerta de licencia: todo lo que no necesita Electron.
 *
 * Está aparte para que se pueda medir con node a secas, sin abrir una ventana
 * ni levantar la app. Lo de Electron —abrir la pantalla de la suite y recoger
 * el token— vive en `licencia.js`, que es corto porque lo demás está aquí.
 *
 * La carpeta donde se guarda entra como parámetro por la misma razón: la
 * prueba le pasa una temporal y no toca la del usuario.
 */

const path = require("path");
const fs = require("fs");
const os = require("os");
const crypto = require("crypto");

const API_POR_OMISION = "https://suite101-api.mike-929.workers.dev";

/** Los motivos por los que la suite dice que no, con palabras.
 *
 *  Esta lista es además la REGLA: sólo un motivo que esté aquí cuenta como
 *  «la suite dice que no». Ver `esUnNo()`.
 */
const porque = (nombre) => ({
  sin_pago: `La licencia de ${nombre} de esta cuenta no está al corriente.`,
  suspendida: `La licencia de ${nombre} de esta cuenta está suspendida.`,
  maquina_desconocida: "Este equipo ya no tiene lugar en la licencia. Hay que volver a activarlo.",
  licencia_desconocida: "Esa licencia ya no existe.",
  token_invalido: "La activación de este equipo ya no sirve. Hay que volver a entrar.",
});

/** El identificador de este equipo, que es lo que cuenta un «lugar».
 *
 *  NO es la MAC ni el número de serie del disco: es un azar que se guarda la
 *  primera vez. No identifica a la persona, no se puede volver atrás, y si
 *  alguien reinstala Windows cuenta como equipo nuevo — que es lo honesto,
 *  porque para la suite es un equipo nuevo. El nombre del equipo entra sólo
 *  como sal: no se manda ni se puede sacar del resultado.
 */
function huella(carpeta) {
  const archivo = path.join(carpeta, "equipo.json");
  try {
    const guardado = JSON.parse(fs.readFileSync(archivo, "utf8"));
    if (typeof guardado.id === "string" && guardado.id.length >= 16) return guardado.id;
  } catch { /* no había, o venía roto: se hace uno */ }
  const semilla = crypto.randomBytes(32).toString("hex") + os.hostname() + os.platform();
  const id = crypto.createHash("sha256").update(semilla).digest("base64url");
  try {
    fs.mkdirSync(carpeta, { recursive: true });
    fs.writeFileSync(archivo, JSON.stringify({ id, hecho: new Date().toISOString() }, null, 2));
  } catch { /* sin disco donde guardar, cada arranque será un equipo nuevo:
               molesto, pero mejor que no arrancar */ }
  return id;
}

const archivoLicencia = (carpeta) => path.join(carpeta, "licencia.json");

function guardada(carpeta) {
  try {
    const d = JSON.parse(fs.readFileSync(archivoLicencia(carpeta), "utf8"));
    return typeof d?.token === "string" ? d : null;
  } catch { return null; }
}

function guardar(carpeta, d) {
  try {
    fs.mkdirSync(carpeta, { recursive: true });
    fs.writeFileSync(archivoLicencia(carpeta), JSON.stringify(d, null, 2));
  } catch { /* la app abre igual; mañana volverá a pedir cuenta */ }
}

function olvidar(carpeta) {
  try { fs.unlinkSync(archivoLicencia(carpeta)); } catch { /* ya no estaba */ }
}

/** ¿El token sigue vivo por su propia fecha? Es lo que deja abrir sin
 *  internet: el token trae su horizonte firmado. */
const alCorriente = (d) => !!d?.hasta && Date.parse(d.hasta) > Date.now();

/** El latido: token viejo → token nuevo, y de paso la app se entera de lo que
 *  cambió del lado de Mike.
 *
 *  `{ ok: true }` · `{ vencida: true, porque }` cuando la suite dice que no ·
 *  `{ sinRed: true }` cuando no se pudo llegar, que NO es lo mismo: por un
 *  rato malo del servidor no se borra la licencia de nadie.
 */
async function latido({ api, carpeta, nombre, d, version, traer = fetch }) {
  let r;
  try {
    r = await traer(`${api}/licencias/latido`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ token: d.token, huella: huella(carpeta), version }),
    });
  } catch { return { sinRed: true }; }
  let cuerpo = null;
  try { cuerpo = await r.json(); } catch { /* no vino JSON */ }
  if (r.ok && cuerpo?.ok) {
    guardar(carpeta, { ...d, token: cuerpo.data.token, hasta: cuerpo.data.hasta, licencia: cuerpo.data.licencia });
    return { ok: true };
  }
  if (!esUnNo(cuerpo)) return { sinRed: true };                      // #100
  return { vencida: true, porque: porque(nombre)[cuerpo.error] };
}

/** ¿Esto es de verdad un «no» de la suite, o es ruido del camino?  (#100)
 *
 *  Antes se preguntaba al revés: todo lo que no fuera un 5xx se contaba como
 *  «la suite dice que no», y eso borraba la licencia del equipo. Medido, cinco
 *  situaciones normales la borraban:
 *
 *    429  demasiadas peticiones — tres equipos del taller abriendo a la vez
 *    408  se agotó el tiempo
 *    401  del proxy de la empresa, no de la suite
 *    404  el día que cambie una dirección
 *    200  con una página HTML de «acceso bloqueado» de un proxy corporativo
 *
 *  Ninguna quiere decir que la licencia esté mal, y todas dejaban al taller
 *  con la app pidiendo activarse otra vez. El recado de Jr. lo avisaba: «un
 *  mal rato del servidor deja a un taller sin su programa, y no se nota
 *  probando a mano con buen internet».
 *
 *  Así que ahora es lista blanca: la suite dice que no cuando contesta un JSON
 *  con un motivo que conocemos. Todo lo demás es «no se pudo llegar», y la
 *  licencia guardada no se toca.
 *
 *  Un motivo nuevo que la suite invente mañana caería aquí como «no se pudo
 *  llegar», y es el lado correcto para equivocarse: el token trae su propio
 *  `hasta` firmado, así que la cosa se cierra sola cuando venza. Al revés —
 *  cerrarle a un taller que sí pagó— no se arregla solo.
 */
function esUnNo(cuerpo) {
  const motivo = cuerpo && typeof cuerpo.error === "string" ? cuerpo.error : "";
  return Object.prototype.hasOwnProperty.call(porque(""), motivo);
}

/** Lo que se le enseña a la persona cuando pregunta «¿con qué cuenta estoy?».
 *  (#100)
 *
 *  Hacía falta una manera de verlo y de cambiarlo desde la propia app. Sin
 *  esto, la única forma de pasar la licencia a otra cuenta era borrar a mano
 *  un archivo dentro de AppData, y eso no se le pide a nadie.
 *
 *  Va aquí, y no en la ventana, para poder medir el texto sin abrir Electron.
 *  `ahora` entra como parámetro por lo mismo: una prueba no puede depender de
 *  qué día se corra.
 */
function resumen(d, { nombre, huella: h, ahora = Date.now() } = {}) {
  const equipo = h ? `${String(h).slice(0, 8)}…` : "—";
  if (!d) {
    return { activa: false, titulo: `${nombre} no está activado en este equipo`,
             lineas: ["Se activa al abrir la aplicación.", `Equipo: ${equipo}`] };
  }
  const t = d.hasta ? Date.parse(d.hasta) : NaN;
  const vigente = Number.isFinite(t) && t > ahora;
  // Los días se cuentan hacia arriba: si faltan 29 horas, faltan 2 días, no 1.
  // Decir de menos preocupa sin motivo; decir de más es mentir.
  const dias = Number.isFinite(t) ? Math.ceil((t - ahora) / 86400000) : null;
  const cuando = !Number.isFinite(t) ? "sin fecha"
    : vigente ? `${new Date(t).toLocaleDateString("es-MX")} (${dias === 1 ? "falta 1 día" : `faltan ${dias} días`})`
    : `venció el ${new Date(t).toLocaleDateString("es-MX")}`;
  return {
    activa: vigente,
    titulo: vigente ? `${nombre} está activado en este equipo`
                    : `La licencia de ${nombre} venció en este equipo`,
    lineas: [
      `Cuenta: ${d.correo || "—"}`,
      `Licencia: ${d.licencia || "—"}`,
      `Válida hasta: ${cuando}`,
      `Equipo: ${equipo}`,
    ],
  };
}

/** La dirección de la pantalla que abre la app. Se arma aquí para poder
 *  medirla sin abrir ventana. */
function direccionDeLaPantalla({ api, programa, nombre, huella: h, version, aviso }) {
  const u = new URL(`${api}/licencias/entrar`);
  u.searchParams.set("programa", programa);
  u.searchParams.set("huella", h);
  u.searchParams.set("app", nombre);
  if (version) u.searchParams.set("version", version);
  if (aviso) u.searchParams.set("aviso", aviso);
  return u.toString();
}

module.exports = { API_POR_OMISION, huella, guardada, guardar, olvidar, alCorriente, latido, porque, esUnNo, resumen, direccionDeLaPantalla, archivoLicencia };
