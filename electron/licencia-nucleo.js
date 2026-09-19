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

/** Los motivos por los que la suite dice que no, con palabras. */
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
  if (r.status >= 500) return { sinRed: true };
  return { vencida: true, porque: porque(nombre)[cuerpo?.error] || `La suite no aceptó la licencia (${cuerpo?.error || r.status}).` };
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

module.exports = { API_POR_OMISION, huella, guardada, guardar, olvidar, alCorriente, latido, porque, direccionDeLaPantalla, archivoLicencia };
