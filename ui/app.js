import * as THREE from "./vendor/three.module.min.js";
import { montarLeerPlano } from "./leer-plano.js";
import { ponerIdioma, T, T2 } from "./idioma.js";    // #085

/* ============================================================ estado */
const S = {
  proyecto: { nombre: "Cocina sin nombre", cliente: "", catalogo: [], estandar: null, gabinetes: [] },
  sel: -1,
  presets: [],
  ultimo: null,
  explosion: 0,
  aristas: true,
  cotas: true,          // #002 #013
  mover: true,          // #004
  colorPor: "material", // #009: "material" | "rol"
  tema: "oscuro",       // #027
  sub: null,            // #023: {gi, tipo, i} de la sub-pieza seleccionada
  biblioteca: [],       // #026: modelos guardados por el usuario
  modulos: [],          // #086: categorías de la librería
  catSel: null,         // #086: categoría abierta en la tienda
  cubiertas3d: [],      // #028: tramos de cubierta que devuelve el servidor
  solidos: [],
  // #015 — no perder el trabajo
  sucio: false,         // hay cambios sin guardar
  rutaActual: null,     // último archivo guardado/abierto
  abierto: false,       // #018: ¿hay un proyecto abierto? (aunque esté vacío)
  pila: [],             // historial para deshacer
  pilaPos: -1,
  aplicandoHistorial: false,
};
/* Con qué nace un mueble nuevo. Sale de `/api/defaults` al arrancar; el día que
   haya perfil de taller, saldrá de ahí y no hay que tocar nada más. */
const DEF = { catalogo: [], estandar: null };

const CLAVE_REC = "despz.recuperacion";
const CLAVE_RECIENTES = "despz.recientes";     // #018
const CLAVE_TEMA = "despz.tema";               // #027
const MAX_RECIENTES = 8;
const $ = (id) => document.getElementById(id);
const api = async (ruta, opt) => {
  const r = await fetch(ruta, opt);
  if (!r.ok) {
    const txt = await r.text();
    let msg = txt.slice(0, 400);
    try { const j = JSON.parse(txt); if (j.detail) msg = j.detail; } catch {}
    const err = new Error(msg);
    err.medidas = r.status === 422;      // #014: medida imposible, no falla técnica
    throw err;
  }
  return r.json();
};
const estado = (t, err) => {
  const e = $("estado");
  e.textContent = t;
  e.style.color = err ? "var(--warn)" : "var(--txt3)";
};
const num = (v, d = 0) => (v === "" || v === null || isNaN(+v) ? d : +v);
const money = (v) => "$" + (v || 0).toLocaleString("es-MX", { maximumFractionDigits: 0 });

// Ventana de inspección para las pruebas: leer el estado sin tocarlo.
if (typeof window !== "undefined") window.__S = S;

/* ============================================================ #027 · tema
   El 3D no es CSS: el fondo del lienzo, la rejilla y las aristas se pintan con
   números en Three.js, así que el tema tiene que tocarlos también. Si no, el
   modo claro deja un agujero negro en medio de la pantalla. */
const TEMAS = {
  oscuro: { lienzo: 0x0b0d11, rejilla1: 0x333a47, rejilla2: 0x1c212a,
            arista: 0x1b1e24, cota: 0x3aa3dc },
  claro:  { lienzo: 0xdfe3e9, rejilla1: 0xa8b2bf, rejilla2: 0xc6cdd6,
            arista: 0x6b7480, cota: 0x0071aa },
};

function leerTema() {
  try { return localStorage.getItem(CLAVE_TEMA) === "claro" ? "claro" : "oscuro"; }
  catch { return "oscuro"; }
}

function aplicarTema(t, guardar = true) {
  S.tema = t === "claro" ? "claro" : "oscuro";
  document.documentElement.dataset.tema = S.tema;
  if (guardar) { try { localStorage.setItem(CLAVE_TEMA, S.tema); } catch {} }
  const b = $("bTema");
  if (b) {
    b.textContent = S.tema === "claro" ? "◑" : "◐";
    b.title = S.tema === "claro" ? "Cambiar a oscuro" : "Cambiar a claro";
  }
  pintar3DConTema();
  if (S.hayLogo) pintarLogo();          // la marca cambia de color con el tema
}

function pintar3DConTema() {
  const c = TEMAS[S.tema] || TEMAS.oscuro;
  if (escena) escena.background = new THREE.Color(c.lienzo);
  if (rejilla) {
    rejilla.material.dispose();
    const nueva = new THREE.GridHelper(8000, 16, c.rejilla1, c.rejilla2);
    rejilla.geometry.dispose();
    rejilla.geometry = nueva.geometry;
    rejilla.material = nueva.material;
  }
  [grupo3D, grupoCub].forEach((gr) => gr?.traverse((o) => {
    if (o.isLineSegments) o.material.color.setHex(c.arista);
  }));
  if (S.lineasCota) S.lineasCota.traverse((o) => o.material?.color?.setHex(c.cota));
}

/* ============================================================ arranque */
init();
async function init() {
  // #085 — El idioma va PRIMERO, antes de pintar nada. Si se pusiera al final,
  // la app abriría un instante en español y cambiaría a la vista: se ve como
  // un error aunque no lo sea.
  try {
    // `?idioma=es` manda sobre el ajuste del taller y no lo cambia: sirve para
    // abrir la app una vez en otro idioma, y es lo que usan las pruebas de
    // interfaz, que comparan textos en español.
    const forzado = new URLSearchParams(location.search).get("idioma");
    const idi = await api("/api/idioma");
    await ponerIdioma(forzado || idi.activo);
  } catch { /* sin servidor de idioma, sale en español y la app abre igual */ }
  const d = await api("/api/defaults");
  S.proyecto.catalogo = d.catalogo;
  S.proyecto.estandar = d.estandar;
  DEF.catalogo = d.catalogo;           // #036 — con qué nace cada mueble nuevo
  DEF.estandar = d.estandar;
  S.presets = d.presets;
  aplicarTema(leerTema(), false);      // #027
  cablear();
  cargarLogo();                        // #083 — pregunta si la empresa puso el suyo
  revisarActualizacion();              // #087 — en segundo plano, sin estorbar
  cargarAvisos();                      // #091 — el punto del menú Ayuda
  pintarMateriales();
  pintarEstandar();
  init3D();
  pintarLista();
  pintarGabinete();
  pintarResultados(null);
  pintarPestanas();                    // #036
  pintarLlave();                       // #040
  // #018 — la app siempre abre en la pantalla de inicio
  mostrarInicio();
  // #015 — si quedó trabajo sin guardar, se ofrece encima del inicio
  revisarRecuperacion();
  try {
    const s = await api("/api/salud");
    $("iVersion").textContent = T2("versión %s", s.version);
  } catch { $("iVersion").textContent = ""; }
}

/* Un proyecto nuevo arranca VACÍO. Antes se le ponía un bajo de cortesía, y lo
   primero que hacía cualquiera era borrarlo: nadie empieza una cocina por el
   mueble que el programa eligió por él. */
async function arrancarVacio() {
  S.proyecto.gabinetes = [];
  S.sel = -1;
  S.abierto = true;
  pintarLista(); pintarGabinete();
  await recalcular(false);
  S.sucio = false;
  reiniciarHistorial();
  pintarTitulo();
  ocultarInicio();
}

/* Logotipo del taller: assets opcional. Si no está, se queda el nombre escrito
   en Sansation — la app nunca se rompe por falta de una imagen. */
function urlLogo() {
  // #083 — si la empresa puso el suyo, ése manda: es el que va a salir en los
  // planos, y verlo aquí es la manera de saber cómo van a salir.
  if (S.logoPropio) return "/api/logo/imagen?v=" + (S.logoVer || 0);
  // #027 — la marca blanca desaparece sobre el panel claro: hay dos archivos
  return S.tema === "claro" ? "vendor/marca/logo-claro.png" : "vendor/marca/logo.png";
}

/* ---------------------------------------------------------------- #083
   El logotipo de la empresa.

   Mike: «para el pie de plano, implementa que podamos elegir el logo de la
   empresa que usa el software, el PNG se queda guardado en algún caché para
   generar siempre con ese logo los planos. Y adicional, la opción de cambiarlo
   sencillo, a lo mejor dando click derecho sobre el logo».

   El archivo lo guarda el servidor en la carpeta de trabajo del taller, junto
   al perfil y al catálogo. Aquí sólo se elige y se manda. */
async function cargarLogo() {
  try {
    const d = await api("/api/logo");
    S.logoPropio = !!d.propio;
    S.logoVer = Date.now();          // rompe la caché del navegador al cambiarlo
  } catch (e) {
    S.logoPropio = false;            // sin servidor se ve el de nest101 y ya
  }
  pintarLogo();
}

function menuLogo(ev) {
  ev.preventDefault();
  document.querySelectorAll(".menuctx").forEach((m) => m.remove());
  const m = document.createElement("div");
  m.className = "menuctx";
  m.style.left = Math.min(ev.clientX, innerWidth - 220) + "px";
  m.style.top = Math.min(ev.clientY, innerHeight - 90) + "px";
  const opciones = [["Cambiar logo…", elegirLogo]];
  if (S.logoPropio) opciones.push([`Quitar el logo (volver a ${"nest101"})`, quitarLogo]);
  opciones.forEach(([txt, fn]) => {
    const b = document.createElement("button");
    b.textContent = txt;
    b.onclick = () => { m.remove(); fn(); };
    m.appendChild(b);
  });
  document.body.appendChild(m);
  // Se cierra con el siguiente clic, venga de donde venga. `once` evita que el
  // mismo clic que abrió el menú lo cierre en el acto.
  setTimeout(() => document.addEventListener("mousedown", () => m.remove(), { once: true }), 0);
}

function elegirLogo() {
  // Un <input type=file> en vez del diálogo de Electron: funciona igual en la
  // app y en el navegador, y no hay que mantener dos caminos.
  const inp = document.createElement("input");
  inp.type = "file";
  inp.accept = "image/png,image/jpeg";
  inp.onchange = async () => {
    const f = inp.files && inp.files[0];
    if (!f) return;
    const fd = new FormData();
    fd.append("archivo", f, f.name);
    estado("Guardando el logotipo…");
    try {
      const r = await fetch("/api/logo", { method: "PUT", body: fd });
      const d = await r.json().catch(() => ({}));
      if (!r.ok) throw new Error(d.detail || "no se pudo guardar");
      estado("Logotipo cambiado. Los planos nuevos salen con él.");
      await cargarLogo();
    } catch (e) {
      estado(String(e.message || e), true);
    }
  };
  inp.click();
}

async function quitarLogo() {
  try {
    await fetch("/api/logo", { method: "DELETE" });
    estado("Se quitó el logotipo: los planos vuelven a firmarse con nest101.");
    await cargarLogo();
  } catch (e) {
    estado("No se pudo quitar el logotipo", true);
  }
}

function pintarLogo() {
  const url = urlLogo();
  const prueba = new Image();
  prueba.onload = () => {
    S.hayLogo = true;
    // #081 — El logotipo TAPA al nombre escrito, en la barra y en el inicio.
    // En #079 se dejaban los dos a la vista porque decían cosas distintas: el
    // logo era el del taller y el texto el del programa. Ahora el logotipo ya
    // dice «nest101», y dejar los dos es escribir el nombre dos veces seguidas.
    // El texto sigue existiendo: es lo que se ve si el archivo del logo falta.
    [["bLogoImg", "bLogoTxt", 21, true], ["iLogoImg", "iLogoTxt", 46, true]]
      .forEach(([i, t, h, tapa]) => {
        const img = $(i);
        if (!img) return;
        img.src = url;
        img.style.height = h + "px";
        img.hidden = false;
        // #083 — el clic derecho va sobre el logotipo, que es donde uno lo
        // busca. El title lo dice, porque un menú que nadie sabe que existe es
        // un menú que no existe.
        img.title = (S.logoPropio ? "El logotipo de tu empresa" : "Logotipo nest101")
                  + " — clic derecho para cambiarlo";
        img.oncontextmenu = menuLogo;
        const txt = $(t);
        if (txt && tapa) txt.style.display = "none";
      });
  };
  // Si la imagen no carga —archivo borrado a mano, servidor caído— no se toca
  // nada: se queda el nombre escrito, que es el respaldo de siempre.
  prueba.onerror = () => { S.hayLogo = false; };
  prueba.src = url;
}

/* ============================================================ eventos */
function cablear() {
  document.querySelectorAll(".tabs button").forEach((b) =>
    b.onclick = () => {
      document.querySelectorAll(".tabs button").forEach((x) => x.classList.remove("on"));
      document.querySelectorAll(".pane").forEach((x) => x.classList.remove("on"));
      b.classList.add("on");
      $(b.dataset.p).classList.add("on");
    });
  document.querySelectorAll(".rtabs button").forEach((b) =>
    b.onclick = () => {
      document.querySelectorAll(".rtabs button").forEach((x) => x.classList.remove("on"));
      document.querySelectorAll(".rpane").forEach((x) => x.classList.remove("on"));
      b.classList.add("on");
      $(b.dataset.r).classList.add("on");
      if (b.dataset.r === "rHojas") pintarHojas();
      if (b.dataset.r === "rProy") calcularProyecto();      // #038
    });
  $("hdAbajo").onclick = () => {
    $("abajo").classList.toggle("min");
    $("flecha").textContent = $("abajo").classList.contains("min") ? "▸" : "▾";
    setTimeout(resize3D, 60);
  };

  $("pNombre").oninput = (e) => { S.proyecto.nombre = e.target.value; marcarSucio(); };
  $("pCliente").oninput = (e) => { S.proyecto.cliente = e.target.value; marcarSucio(); };
  $("bDeshacer").onclick = () => irAHistorial(-1);
  $("bRehacer").onclick = () => irAHistorial(+1);
  window.addEventListener("keydown", (e) => {
    if (!(e.ctrlKey || e.metaKey)) return;
    const k = e.key.toLowerCase();
    if (k === "z" && !e.shiftKey) { e.preventDefault(); irAHistorial(-1); }
    else if ((k === "z" && e.shiftKey) || k === "y") { e.preventDefault(); irAHistorial(+1); }
    else if (k === "s") { e.preventDefault(); guardar(); }
    else if (k === "i") { e.preventDefault(); mostrarInicio(); }     // #018
  });
  $("bConfig").onclick = abrirConfig;                       // #085
  $("bAyuda").onclick = () => menuAyuda();                  // #091
  $("aActualizar").onclick = async () => {
    menuAyuda(false);
    estado("Revisando…");
    await revisarActualizacion(true);
    const d = S.actualizacion || {};
    estado(d.hay ? T2("hay versión nueva: %s", d.version)
      : (d.error ? "no se pudo revisar (sin internet)" : "estás en la última"));
    if (d.hay) abrirConfig();
  };
  $("aAvisos").onclick = () => { menuAyuda(false); verAvisos(); };
  $("aLicencias").onclick = () => { menuAyuda(false); verLicencias(); };
  $("bAgregar").onclick = abrirTienda;                     // #025
  $("bGuardarModelo").onclick = guardarModelo;             // #026
  $("tCerrar").onclick = cerrarTienda;
  $("tBuscar").oninput = pintarCatalogo;
  $("tienda").onclick = (e) => { if (e.target.id === "tienda") cerrarTienda(); };
  $("bDuplicar").onclick = duplicar;
  $("bNuevaPestana").onclick = nuevo;                 // #036
  $("bProyecto").onclick = abrirProyecto;             // #038
  $("bLlaveGuardar").onclick = () => guardarLlave($("sLlave").value);   // #040
  $("bLlaveQuitar").onclick = () => guardarLlave("");
  $("sLlave").onkeydown = (e) => {
    if (e.key === "Enter") { e.preventDefault(); guardarLlave($("sLlave").value); }
  };
  $("iProyecto").onclick = abrirProyecto;
  $("bNuevo").onclick = nuevo;
  $("bGuardar").onclick = guardar;
  $("bAbrir").onclick = abrir;
  $("bExportar").onclick = exportar;
  $("bExportarProy").onclick = exportarProyecto;   // #071
  $("bAddMat").onclick = agregarMaterial;
  $("bAddPuerta").onclick = () => addFrente("puerta");
  $("bAddCajon").onclick = () => addFrente("cajon");
  $("bAddNicho").onclick = () => addFrente("abierto");        // #090
  $("mCancel").onclick = () => $("modal").classList.remove("on");

  // #018 — pantalla de inicio
  $("iNuevo").onclick = nuevo;
  $("iAbrir").onclick = abrir;
  $("iCerrar").onclick = ocultarInicio;
  $("bInicio").onclick = mostrarInicio;
  $("bTema").onclick = () => aplicarTema(S.tema === "claro" ? "oscuro" : "claro");
  $("iOlvidar").onclick = () => { escribirRecientes([]); pintarRecientes(); };
  window.addEventListener("keydown", (e) => {
    if (e.key === "Escape" && $("tienda").classList.contains("on")) { cerrarTienda(); return; }
    if (e.key === "Escape" && $("inicio").classList.contains("on")) ocultarInicio();
  });

  $("explo").oninput = (e) => {
    S.explosion = +e.target.value / 100;
    $("exploVal").textContent = e.target.value + "%";
    aplicarExplosion();
  };
  $("bVista").onclick = () => encuadrar();
  $("bMover").onclick = () => {
    S.mover = !S.mover;
    $("bMover").classList.toggle("act", S.mover);
    $("lienzo").style.cursor = "default";
  };
  $("bGirar").onclick = girarSeleccionado;
  $("bCotas").onclick = () => {
    S.cotas = !S.cotas;
    $("bCotas").classList.toggle("act", S.cotas);
    if (S.lineasCota) S.lineasCota.visible = S.cotas;
    pintarCotas();
  };
  $("bColor").onclick = () => {
    S.colorPor = S.colorPor === "material" ? "rol" : "material";
    $("bColor").textContent = S.colorPor === "material" ? T("Color: material")
                                                       : T("Color: rol");
    repintarColores();
  };
  $("gColgadoReset").onclick = () => {
    const gg = S.proyecto.gabinetes[S.sel];
    if (!gg) return;
    gg.alto_colgado = null;
    pintarGabinete(); recolocar3D(); pintarCotas(); recalcular();
  };
  $("bCantos").onclick = () => {
    S.aristas = !S.aristas;
    [grupo3D, grupoCub].forEach((gr) =>
      gr?.traverse((o) => { if (o.isLineSegments) o.visible = S.aristas; }));
  };

  // candados de alturas (#001)
  document.querySelectorAll(".alt .cand").forEach((b) =>
    b.onclick = () => ponerCandado(b.dataset.lock));
  $("gGolaReset").onclick = () => {                          // #030
    const gg = S.proyecto.gabinetes[S.sel];
    if (!gg) return;
    gg.gola = null; gg.alto_gola = null;
    pintarGabinete(); recalcular();
  };
  $("gVueloReset").onclick = () => {                         // #075
    const gg = S.proyecto.gabinetes[S.sel];
    if (!gg) return;
    gg.vuelo_cubierta = null;
    pintarGabinete(); recalcular();
  };
  $("gZocloReset").onclick = () => {
    const gg = S.proyecto.gabinetes[S.sel];
    gg.altura_zoclo = null;
    if (gg.alto_derivado === "zoclo") gg.alto_derivado = "cuerpo";
    leerAlturasDesdeEstandar(gg);
    pintarAlturas(); pintarLista(); recalcular();
  };

  // campos del gabinete
  const g = ["gNombre", "gTipo", "gCant", "gAncho", "gAlto", "gAltoCuerpo",
             "gAlturaZoclo", "gProf", "gEnt", "gEntFijos", "gTapa", "gZoclo",
             "gRespaldo",
             "gCubierta", "gGola", "gAltoGola", "gUnero", "gVuelo",
             "gMatCuerpo", "gMatFrente", "gMatRespaldo",
             "gPosX", "gPosZ", "gRot", "gColgado"];
  g.forEach((id) => {
    const el = $(id);
    el.addEventListener(el.type === "checkbox" || el.tagName === "SELECT" ? "change" : "input",
      leerGabinete);
  });
  // campos del estándar
  Object.keys(MAPA_STD).forEach((id) => {
    const el = $(id);
    el.addEventListener(el.type === "checkbox" || el.tagName === "SELECT" ? "change" : "input",
      leerEstandar);
  });
  ["sMatCuerpo", "sMatFrente", "sMatRespaldo", "sMatCajon", "sMatFondo",
   "sMatCubierta", "sMatManguete"].forEach((id) =>
    $(id).addEventListener("change", leerEstandar));

  window.addEventListener("resize", resize3D);

  // menú nativo de Electron
  window.despz?.onMenu?.((c) => ({ nuevo, abrir, guardar, exportar,
                                   inicio: mostrarInicio,          // #018
                                   deshacer: () => irAHistorial(-1),
                                   rehacer: () => irAHistorial(+1) }[c]?.()));
  // #015 — Electron pregunta antes de cerrar; #016 — abre el archivo del doble clic
  window.despz?.alCerrar?.(async () => {
    if (!S.sucio) return true;
    const r = await window.despz.preguntarGuardar(S.proyecto.nombre || "el proyecto", "Salir");
    if (r === "cancelar") return false;
    if (r === "guardar") { await guardar(); return !S.sucio; }
    limpiarRecuperacion();
    return true;
  });
  window.despz?.alAbrirArchivo?.(async (r) => {
    if (!r || !r.contenido) return;
    if (!await confirmarDescartar("Abrir el proyecto")) return;
    try { cargarProyecto(JSON.parse(r.contenido), r.ruta); estado("proyecto abierto"); }
    catch { estado("el archivo no se pudo leer", true); }
  });
  // Autoguardado antes de que se descargue la página. **Sin `preventDefault`**:
  // en Electron, un `beforeunload` que cancela deja la ventana imposible de
  // cerrar y sin diálogo que lo explique — la app se queda abierta y hay que
  // matarla desde el administrador de tareas. Ya pasó.
  //
  // Preguntar por el trabajo sin guardar es cosa del proceso principal, que
  // saca un diálogo de verdad con Guardar / Descartar / Cancelar (`alCerrar`,
  // arriba). Aquí sólo se deja el respaldo por si el cierre viene de fuera.
  window.addEventListener("beforeunload", () => {
    if (S.sucio) autoguardar();
  });

  // « Leer plano » - panel de IDENTIFICADOR. Empuja gabinetes a S.proyecto.gabinetes
  // igual que la biblioteca de modelos, y luego repinta.
  const leerPlano = montarLeerPlano({
    S, api, estado,
    refrescar: () => { pintarLista(); pintarGabinete(); recalcular(); },
  });
  const btnLeerPlano = document.getElementById("btnLeerPlano");
  if (btnLeerPlano) btnLeerPlano.onclick = () => leerPlano.abrir();
}

/* ============================================================ gabinetes */
async function agregarGabinete(pid) {
  const g = await api("/api/preset/" + pid);
  const base = g.nombre;
  let n = 1, nom = base;
  const usados = new Set(S.proyecto.gabinetes.map((x) => x.nombre));
  while (usados.has(nom)) nom = `${base} ${++n}`;
  g.nombre = nom;
  S.proyecto.gabinetes.push(g);
  S.sel = S.proyecto.gabinetes.length - 1;
  pintarLista(); pintarGabinete(); recalcular();
}

function duplicar() {
  if (S.sel < 0) return;
  const c = JSON.parse(JSON.stringify(S.proyecto.gabinetes[S.sel]));
  let n = 2, nom = c.nombre + " copia";
  const usados = new Set(S.proyecto.gabinetes.map((x) => x.nombre));
  while (usados.has(nom)) nom = c.nombre + " copia " + n++;
  c.nombre = nom;
  S.proyecto.gabinetes.splice(S.sel + 1, 0, c);
  S.sel++;
  pintarLista(); pintarGabinete(); recalcular();
}

function borrar(i) {
  S.proyecto.gabinetes.splice(i, 1);
  if (S.sel >= S.proyecto.gabinetes.length) S.sel = S.proyecto.gabinetes.length - 1;
  pintarLista(); pintarGabinete(); recalcular();
}

function pintarLista() {
  const c = $("listaGab");
  $("nGab").textContent = S.proyecto.gabinetes.length;
  if (!S.proyecto.gabinetes.length) {
    c.innerHTML = `<div class="vacio">Sin gabinetes.<br>Agrega uno abajo.</div>`;
    return;
  }
  c.innerHTML = S.proyecto.gabinetes.map((g, i) => {
    const np = g.frentes.filter((f) => f.tipo === "puerta").reduce((a, f) => a + f.n, 0);
    const nc = g.frentes.filter((f) => f.tipo === "cajon").length;
    const cfg = [np ? np + " " + T("pta") : "", nc ? nc + " " + T("caj") : "",
                 g.n_entrepanos ? g.n_entrepanos + " " + T("ent") : ""]
                .filter(Boolean).join(" · ");
    return `<div class="gab ${i === S.sel ? "sel" : ""}" data-i="${i}">
      <div class="nm">${esc(g.nombre)}${g.cantidad > 1 ? `<span class="badge">×${g.cantidad}</span>` : ""}
        <span class="badge">${T(g.tipo === "base" ? "bajo" : "aéreo")}</span></div>
      <div class="dm">${g.ancho}×${g.alto}×${g.prof}${cfg ? " · " + cfg : ""}</div>
      <div class="x" data-x="${i}">×</div></div>`;
  }).join("");
  c.querySelectorAll(".gab").forEach((el) =>
    el.onclick = (e) => {
      if (e.target.dataset.x !== undefined) { borrar(+e.target.dataset.x); return; }
      S.sel = +el.dataset.i; limpiarSub(false);
      pintarLista(); pintarGabinete(); resaltar3D(); pintarCotas();
    });
}

function pintarGabinete() {
  const hay = S.sel >= 0 && S.proyecto.gabinetes[S.sel];
  $("sinSel").style.display = hay ? "none" : "block";
  $("formGab").style.display = hay ? "block" : "none";
  if (!hay) return;
  const g = S.proyecto.gabinetes[S.sel];
  $("gNombre").value = g.nombre;
  $("gTipo").value = g.tipo;
  $("gCant").value = g.cantidad;
  $("gAncho").value = g.ancho;
  $("gProf").value = g.prof;
  $("gEnt").value = g.n_entrepanos;
  $("gEntFijos").checked = !!g.entrepanos_fijos;
  $("gTapa").checked = g.tapa_completa === null ? g.tipo === "aereo" : !!g.tapa_completa;
  // #065 — respaldo entero o dos travesaños; None = lo que diga el proyecto
  $("gRespaldo").checked = (g.respaldo_completo === null || g.respaldo_completo === undefined)
    ? (S.proyecto.estandar.respaldo_completo !== false) : !!g.respaldo_completo;
  $("gRespaldoOrigen").textContent =
    (g.respaldo_completo === null || g.respaldo_completo === undefined)
      ? "(del proyecto)" : "(propio)";
  $("gZoclo").checked = !!g.con_zoclo;
  // #028 — por omisión los bajos llevan cubierta y los aéreos no
  $("gCubierta").checked = g.con_cubierta === null || g.con_cubierta === undefined
    ? g.tipo === "base" : !!g.con_cubierta;
  // #030 — gola
  const hayGola = g.gola === null || g.gola === undefined
    ? !!S.proyecto.estandar.gola : !!g.gola;
  $("gGola").checked = hayGola;
  $("gGolaOrigen").textContent = (g.gola === null || g.gola === undefined)
    ? "(del proyecto)" : "(propia)";
  $("filaGola").style.display = hayGola ? "block" : "none";
  $("gAltoGola").value = Math.round(g.alto_gola != null
    ? g.alto_gola : S.proyecto.estandar.alto_gola);
  // #042 — uñero
  $("gUnero").checked = (g.unero === null || g.unero === undefined)
    ? !!S.proyecto.estandar.unero : !!g.unero;
  $("gUneroOrigen").textContent = (g.unero === null || g.unero === undefined)
    ? "(del proyecto)" : "(propia)";
  // #075 — vuelo de cubierta por mueble
  const propioVuelo = g.vuelo_cubierta !== null && g.vuelo_cubierta !== undefined;
  $("filaVuelo").style.display = $("gCubierta").checked ? "block" : "none";
  $("gVuelo").value = Math.round(propioVuelo ? g.vuelo_cubierta
                                             : S.proyecto.estandar.vuelo_cubierta);
  $("gVueloOrigen").textContent = propioVuelo ? "(propio)" : "(del proyecto)";
  opcionesMaterial("gMatCuerpo", g.mat_cuerpo);
  opcionesMaterial("gMatFrente", g.mat_frente);
  opcionesMaterial("gMatRespaldo", g.mat_respaldo);
  $("gPosX").value = Math.round(g.pos_x || 0);
  $("gPosZ").value = Math.round(g.pos_z || 0);
  $("gRot").value = String(((g.rot || 0) % 360 + 360) % 360);
  const aereo = g.tipo === "aereo";
  $("filaColgado").style.display = aereo ? "block" : "none";
  $("gColgado").value = Math.round(g.alto_colgado != null ? g.alto_colgado
                                   : S.proyecto.estandar.altura_colgado_aereo);
  $("gColgadoOrigen").textContent = g.alto_colgado != null ? "(propio)" : "(del proyecto)";
  pintarAlturas();
  pintarFrentes();
}

/* ---------- alturas con candado (#001) ----------
   Identidad: total = cuerpo + zoclo. El campo con candado se calcula. */
function llevaZoclo(g) { return g.tipo === "base" && !!g.con_zoclo; }
function zocloDe(g) {
  return g.altura_zoclo !== null && g.altura_zoclo !== undefined
    ? +g.altura_zoclo : +S.proyecto.estandar.altura_zoclo;
}

/* #059 — lo que se lleva la cubierta del alto declarado (espejo de
   `core.modelos.espesor_cubierta`). */
function espesorCubierta(g) {
  const std = S.proyecto.estandar || {};
  if (!llevaCubierta(g) || !std.mat_cubierta) return 0;
  return +(std.mat_cubierta.espesor || 0);
}

function resolverAlturas(g) {
  // #059 — `total` es lo que se TECLEA: la altura de trabajo, con cubierta.
  // `gabinete` es lo que se construye. La diferencia es la plancha, y hay que
  // llevar las dos: si se enseñara el cuerpo sin descontarla, la ficha diría
  // una medida y la lista de corte otra.
  const ec = espesorCubierta(g);
  const hay = llevaZoclo(g);
  const d = g.alto_derivado || "cuerpo";
  if (!hay) {
    const decl = d === "total" && g.alto_cuerpo ? +g.alto_cuerpo + ec : +g.alto;
    const cuerpo = decl - ec;
    return { total: decl, gabinete: cuerpo, cuerpo, zoclo: 0, derivado: d, cubierta: ec };
  }
  const hzRef = zocloDe(g);
  let decl, cuerpo, zoclo;
  if (d === "total") {                     // capturas cuerpo + zoclo
    cuerpo = g.alto_cuerpo != null ? +g.alto_cuerpo : +g.alto - ec - hzRef;
    zoclo = hzRef; decl = cuerpo + zoclo + ec;
  } else if (d === "zoclo") {              // capturas total + cuerpo
    decl = +g.alto;
    cuerpo = g.alto_cuerpo != null ? +g.alto_cuerpo : +g.alto - ec - hzRef;
    zoclo = decl - ec - cuerpo;
  } else {                                 // "cuerpo": capturas total + zoclo
    decl = +g.alto; zoclo = hzRef; cuerpo = decl - ec - zoclo;
  }
  return { total: decl, gabinete: cuerpo + zoclo, cuerpo, zoclo,
           derivado: d, cubierta: ec };
}

function pintarAlturas() {
  const g = S.proyecto.gabinetes[S.sel];
  const a = resolverAlturas(g);
  const hay = llevaZoclo(g);
  const d = a.derivado;

  $("gAlto").value = redondear(a.total);
  $("gAltoCuerpo").value = redondear(a.cuerpo);
  $("gAlturaZoclo").value = hay ? redondear(a.zoclo) : 0;

  document.querySelectorAll(".alt").forEach((el) => {
    const cual = el.dataset.a;
    const calc = cual === d && (hay || cual !== "zoclo");
    el.classList.toggle("calc", calc);
    el.classList.toggle("na", cual === "zoclo" && !hay);
    el.classList.toggle("override", cual === "zoclo" && g.altura_zoclo != null);
    el.querySelector("input").readOnly = calc;
    el.querySelector(".cand").textContent = calc ? "🔒" : "🔓";
  });
  $("gZocloOrigen").textContent = !hay ? "(sin zoclo)"
    : g.altura_zoclo != null ? "(propio)" : "(del proyecto)";

  const ef = S.proyecto.estandar.mat_frente.espesor;
  // #043 — con cubierta, el fondo tecleado es el de la plancha: el vuelo se va
  // por delante de la puerta y el cuerpo se corta con lo que queda.
  const vu = vueloDe(g);
  $("gNota").textContent =
    `Cuerpo ${redondear(a.cuerpo)} alto × ` +
    `${(g.prof - ef - vu - (+S.proyecto.estandar.holgura_frente_costado || 0)).toFixed(0)} prof` +
    (vu ? ` (fondo ${g.prof} de cubierta − ${vu} de vuelo)` : "") +
    (hay ? ` · zoclo ${redondear(a.zoclo)}` : " · sin zoclo") +
    (a.cubierta ? ` · gabinete ${redondear(a.gabinete)} + cubierta ${a.cubierta}` : "");

  const al = $("gAlertaAlturas");
  const min = 2 * S.proyecto.estandar.mat_cuerpo.espesor;   // piso + tapa/travesaño
  const mal = a.cuerpo <= min
      ? `El cuerpo queda en ${redondear(a.cuerpo)} mm y no caben ni el piso ni la tapa `
        + `(${min} mm mínimo). Baja el zoclo o sube el total.`
    : a.zoclo < 0
      ? `El zoclo queda en ${redondear(a.zoclo)} mm: el cuerpo no puede pasar del total.`
    : "";
  al.style.display = mal ? "block" : "none";
  al.textContent = mal;
}
const redondear = (v) => Math.round(v * 10) / 10;

/* #028 #043 — las mismas dos reglas que el motor (`core/modelos.py`), para poder
   rotular el fondo sin ir al servidor: un aéreo no lleva cubierta y un bajo sí,
   salvo que se diga lo contrario; y el vuelo sólo existe si hay cubierta. */
function llevaCubierta(g) {
  if (g.con_cubierta === null || g.con_cubierta === undefined) return g.tipo === "base";
  return !!g.con_cubierta;
}
function vueloDe(g) {
  const std = S.proyecto.estandar || {};
  if (!llevaCubierta(g) || !std.mat_cubierta) return 0;
  // #075 — el del mueble manda sobre el del proyecto
  if (g.vuelo_cubierta !== null && g.vuelo_cubierta !== undefined)
    return Math.max(0, +g.vuelo_cubierta);
  return Math.max(0, +(std.vuelo_cubierta || 0));
}

function leerAlturas() {
  const g = S.proyecto.gabinetes[S.sel];
  const hay = llevaZoclo(g);
  const d = g.alto_derivado || "cuerpo";
  const t = num($("gAlto").value, 0);
  const c = num($("gAltoCuerpo").value, 0);
  const z = num($("gAlturaZoclo").value, 0);

  if (!hay) { g.alto = d === "total" ? c : t; g.alto_cuerpo = g.alto; return; }
  if (d === "total") {            // capturas cuerpo + zoclo
    g.alto_cuerpo = c; g.altura_zoclo = z; g.alto = c + z;
  } else if (d === "zoclo") {     // capturas total + cuerpo
    g.alto = t; g.alto_cuerpo = c; g.altura_zoclo = t - c;
  } else {                        // "cuerpo": capturas total + zoclo
    g.alto = t; g.altura_zoclo = z; g.alto_cuerpo = t - z;
  }
}

function leerAlturasDesdeEstandar(g) {
  // tras quitar el override, recalcula respetando el campo derivado
  const a = resolverAlturas(g);
  g.alto = a.total;
  g.alto_cuerpo = a.cuerpo;
}

function ponerCandado(cual) {
  const g = S.proyecto.gabinetes[S.sel];
  if (cual === "zoclo" && !llevaZoclo(g)) return;
  // al mover el candado, congela los valores que hoy se ven
  const a = resolverAlturas(g);
  g.alto = a.total;
  g.alto_cuerpo = a.cuerpo;
  if (llevaZoclo(g)) g.altura_zoclo = a.zoclo;
  g.alto_derivado = cual;
  pintarAlturas(); recalcular();
}

/* #097 — Lo que va a salir si el campo se deja vacío: 80 % del alto del frente,
   redondeado al centímetro de arriba. Es la misma cuenta que hace el motor en
   alto_caja_de(); aquí sólo se enseña como sugerencia dentro del campo, para
   que no haya que calcular nada de cabeza. Si el alto del frente es automático
   todavía no se sabe, y se dice así. */
function altoCajaAuto(f, i) {
  // El alto de la hoja lo calcula el motor y ya viene en /api/solidos, que es
  // lo único que sabe repartir el sobrante entre los frentes sin altura fija.
  const alto = (S.solidos?.[S.sel]?.frentes || [])[i]?.alto ?? f.alto;
  if (!alto) return "auto";
  return String(Math.ceil(alto * 0.8 / 10) * 10);
}

/* #097 — El alto de la hoja lo calcula el motor, así que la sugerencia del
   campo «Caja» no se sabe hasta que contesta. Se actualiza sólo el placeholder,
   nunca se repinta el panel: repintarlo mientras alguien teclea le quitaría el
   foco a media medida. */
function refrescarSugerenciaCaja() {
  const g = S.proyecto.gabinetes[S.sel];
  if (!g) return;
  document.querySelectorAll("#listaFrentes [data-c=altoCaja]").forEach((inp) => {
    const i = +inp.closest(".frente").dataset.i;
    const f = g.frentes[i];
    if (f && f.tipo === "cajon") inp.placeholder = altoCajaAuto(f, i);
  });
}

function pintarFrentes() {
  const g = S.proyecto.gabinetes[S.sel];
  $("listaFrentes").innerHTML = g.frentes.map((f, i) => `
    <div class="frente" data-i="${i}">
      <div><div class="lbl">Tipo</div>
        <select data-c="tipo"><option value="puerta"${f.tipo === "puerta" ? " selected" : ""}>Puerta</option>
        <option value="cajon"${f.tipo === "cajon" ? " selected" : ""}>Cajón</option>
        <option value="abierto"${f.tipo === "abierto" ? " selected" : ""}>Abierto (nicho)</option></select></div>
      <div><div class="lbl">Alto (vacío = reparte)</div>
        <input type="number" data-c="alto" value="${f.alto ?? ""}" placeholder="auto"></div>
      <div><div class="lbl">Hojas</div>
        <input type="number" data-c="n" min="1" value="${f.n}" ${f.tipo !== "puerta" ? "disabled" : ""}></div>
      <div title="Alto de las paredes de la caja. Vacío = 80% del alto del frente, redondeado al cm de arriba."><div class="lbl">Caja</div>
        <input type="number" data-c="altoCaja" value="${f.alto_caja ?? ""}"
               placeholder="${f.tipo === "cajon" ? altoCajaAuto(f, i) : "—"}"
               ${f.tipo !== "cajon" ? "disabled" : ""}></div>
      <button class="del" data-d="${i}">×</button>
    </div>`).join("") || `<div style="color:var(--txt3);font-size:11.5px">Sin frentes (mueble abierto)</div>`;
  $("listaFrentes").querySelectorAll(".frente").forEach((el) => {
    const i = +el.dataset.i;
    el.querySelectorAll("[data-c]").forEach((inp) =>
      inp.addEventListener(inp.tagName === "SELECT" ? "change" : "input", () => {
        const c = inp.dataset.c;
        if (c === "alto") g.frentes[i].alto = inp.value === "" ? null : num(inp.value);
        else if (c === "altoCaja") {                                   // #097
          g.frentes[i].alto_caja = inp.value === "" ? null : num(inp.value);
        }
        else if (c === "n") g.frentes[i].n = Math.max(1, num(inp.value, 1));
        else { g.frentes[i].tipo = inp.value; if (inp.value !== "puerta") g.frentes[i].n = 1; pintarFrentes(); }
        recalcular();
      }));
    el.querySelector("[data-d]").onclick = () => { g.frentes.splice(i, 1); pintarFrentes(); recalcular(); };
  });
}

function addFrente(tipo) {
  const g = S.proyecto.gabinetes[S.sel];
  g.frentes.push({ tipo, alto: tipo === "cajon" ? 180 : null, n: 1,
                   alto_caja: null });                        // #090 #097
  pintarFrentes(); recalcular();
}

function leerGabinete() {
  if (S.sel < 0) return;
  const g = S.proyecto.gabinetes[S.sel];
  g.nombre = $("gNombre").value || g.nombre;
  g.tipo = $("gTipo").value;
  g.cantidad = Math.max(1, num($("gCant").value, 1));
  g.ancho = num($("gAncho").value, g.ancho);
  g.prof = num($("gProf").value, g.prof);
  g.n_entrepanos = Math.max(0, num($("gEnt").value, 0));
  g.entrepanos_fijos = $("gEntFijos").checked;
  g.tapa_completa = $("gTapa").checked;
  g.respaldo_completo = $("gRespaldo").checked;            // #065
  g.con_zoclo = $("gZoclo").checked;
  g.con_cubierta = $("gCubierta").checked;                 // #028
  g.gola = $("gGola").checked;                             // #030
  if ($("gGola").checked) g.alto_gola = num($("gAltoGola").value, S.proyecto.estandar.alto_gola);
  g.unero = $("gUnero").checked;                           // #042
  // #075 — sólo se guarda como propio si difiere del proyecto: así el mueble
  // sigue al proyecto mientras nadie lo toque, como el zoclo y la gola.
  if ($("gCubierta").checked) {
    const v = num($("gVuelo").value, S.proyecto.estandar.vuelo_cubierta);
    g.vuelo_cubierta = (Math.abs(v - S.proyecto.estandar.vuelo_cubierta) < 0.01)
      ? null : v;
    // el rótulo se actualiza aquí y no en pintarGabinete: repintar el panel
    // mientras se teclea le quitaría el cursor al campo.
    $("gVueloOrigen").textContent =
      g.vuelo_cubierta === null ? "(del proyecto)" : "(propio)";
  }
  g.mat_cuerpo = $("gMatCuerpo").value || null;
  g.mat_frente = $("gMatFrente").value || null;
  g.mat_respaldo = $("gMatRespaldo").value || null;
  g.pos_x = num($("gPosX").value, 0);
  g.pos_z = num($("gPosZ").value, 0);
  g.rot = num($("gRot").value, 0);
  if (g.tipo === "aereo") {
    const v = num($("gColgado").value, S.proyecto.estandar.altura_colgado_aereo);
    g.alto_colgado = v;
  }
  leerAlturas();
  pintarAlturas();
  pintarLista(); recalcular();
}

/* ============================================================ #025 · catálogo
   El menú de agregar deja de ser una lista desplegable y pasa a ser una parrilla
   con la imagen de cada mueble. Las miniaturas las dibuja el MISMO motor
   isométrico que hace los planos, así que no pueden desfasarse del modelo: si
   cambia el despiece, cambia la imagen.
   #026 · Debajo van los modelos que guarda el usuario, que viven en su perfil y
   no en el proyecto, para que estén en todas las cocinas. */

function abrirTienda() {
  $("tienda").classList.add("on");
  $("tBuscar").value = "";
  cargarModulos();
  setTimeout(() => $("tBuscar").focus(), 30);
}

function cerrarTienda() { $("tienda").classList.remove("on"); }

function tarjetaHTML({ img, nombre, dim, badge, quitar, nota, pid }) {
  // `data-pid` sigue puesto en los del programa: es como se pide uno por su
  // nombre, desde las pruebas y desde cualquier atajo futuro.
  return `<button class="tarjeta" ${pid ? `data-pid="${esc(pid)}"` : ""}
      ${quitar ? `data-borrar="1"` : ""}>
    <span class="im"><img loading="lazy" src="${esc(img)}" alt=""
      onerror="this.replaceWith(Object.assign(document.createElement('span'),
               {className:'cargando',textContent:'sin vista previa'}))"></span>
    <span class="nm">${esc(nombre)}</span>
    <span class="dm">${esc(dim)}</span>
    ${nota ? `<span class="nt">${esc(nota)}</span>` : ""}
    ${badge ? `<span class="badge">${esc(badge)}</span>` : ""}
    ${quitar ? `<span class="quitar" title="Quitar de la librería">×</span>` : ""}
  </button>`;
}

/* ---------------------------------------------------------------- #086
   La librería por categorías.

   Antes eran dos listas fijas —los de la app y los míos— una debajo de otra.
   Ahora cada categoría es una carpeta de módulos, y la barra de arriba escoge
   cuál se ve. Las dos primeras siguen existiendo: «Básicos» son los presets del
   programa y «Mis modelos» lo que ya estaba guardado con #026, que no se
   pierde. Después vienen las carpetas: las de fábrica y las del taller. */
const CAT_BASICOS = "__basicos__";
const CAT_MIOS = "__mios__";

async function cargarModulos() {
  if (!S.catSel) S.catSel = CAT_BASICOS;
  try { S.modulos = (await api("/api/modulos")).categorias || []; }
  catch { S.modulos = []; }
  try { S.biblioteca = (await api("/api/biblioteca")).modelos || []; }
  catch { S.biblioteca = []; }
  pintarCategorias();
  pintarCatalogo();
}

function categoriasVisibles() {
  return [
    { id: CAT_BASICOS, nombre: "Básicos", nota: "Los que trae el programa.", n: S.presets.length },
    ...S.modulos.map((c) => ({ ...c, n: c.modulos.length })),
    { id: CAT_MIOS, nombre: "Mis modelos", n: S.biblioteca.length,
      nota: "Los que guardaste sueltos, sin categoría." },
  ];
}

function pintarCategorias() {
  const cats = categoriasVisibles();
  if (!cats.some((c) => c.id === S.catSel)) S.catSel = CAT_BASICOS;
  $("tCats").innerHTML = cats.map((c) => `
    <button class="cat${c.id === S.catSel ? " act" : ""}" data-cat="${esc(c.id)}">
      ${esc(c.nombre)}<span class="n">${c.n}</span>
      ${c.propia ? `<span class="mia" title="Categoría tuya, no viene con la app">•</span>` : ""}
    </button>`).join("");
  $("tCats").querySelectorAll(".cat").forEach((b) => b.onclick = () => {
    S.catSel = b.dataset.cat;
    pintarCategorias();
    pintarCatalogo();
  });
}

/** Lo que se ve en la parrilla, ya sea preset, módulo de carpeta o modelo suelto.
    Los tres acaban en la misma forma para que la parrilla no sepa de dónde vino. */
function fichasDeCategoria() {
  if (S.catSel === CAT_BASICOS) {
    return S.presets.map((p) => ({
      clave: p.nombre + " " + p.ancho + p.alto + p.prof,
      img: `/api/miniatura/${p.id}.png?w=300`,
      nombre: p.nombre, dim: `${p.ancho} × ${p.alto} × ${p.prof} mm`,
      badge: /aereo|nicho$/.test(p.id) ? "aéreo" : "",
      pid: p.id,
      poner: () => agregarGabinete(p.id),
    }));
  }
  if (S.catSel === CAT_MIOS) {
    return S.biblioteca.map((m) => {
      const g = m.gabinete || {};
      return {
        clave: m.nombre,
        img: `/api/miniatura/biblioteca/${m.id}.png?w=300`,
        nombre: m.nombre, dim: `${g.ancho} × ${g.alto} × ${g.prof} mm`,
        badge: g.tipo === "aereo" ? "aéreo" : "",
        quitar: () => borrarModelo(m),
        poner: () => agregarDeLibreria(m.gabinete, m.nombre),
      };
    });
  }
  const cat = S.modulos.find((c) => c.id === S.catSel);
  return (cat ? cat.modulos : []).map((m) => {
    const g = m.gabinete || {};
    return {
      clave: m.nombre + " " + m.nota,
      img: `/api/miniatura/modulo/${m.id}.png?w=300`,
      nombre: m.nombre, dim: `${g.ancho} × ${g.alto} × ${g.prof} mm`,
      nota: m.nota, badge: g.tipo === "aereo" ? "aéreo" : "",
      // Lo de fábrica no se borra: viene con la app y volvería en la siguiente
      // actualización. Sólo lo del taller lleva la ×.
      quitar: m.propia ? () => borrarModulo(m) : null,
      poner: () => agregarDeLibreria(m.gabinete, m.nombre),
    };
  });
}

function pintarCatalogo() {
  const q = ($("tBuscar").value || "").toLowerCase().trim();
  const cat = categoriasVisibles().find((c) => c.id === S.catSel) || {};
  $("tNota").textContent = cat.nota || "";
  const lista = fichasDeCategoria().filter((f) => !f.clave || !q
    || f.clave.toLowerCase().includes(q));
  const rej = $("tModelos"), vac = $("tVacio");
  rej.innerHTML = lista.map(tarjetaHTML).join("");
  vac.hidden = lista.length > 0;
  if (!lista.length) {
    vac.innerHTML = q
      ? `Nada con «${esc(q)}» en esta categoría.`
      : (S.catSel === CAT_MIOS
        ? `Todavía no guardas ninguno.<br>Selecciona un gabinete y usa «Guardar como módulo».`
        : `Esta categoría está vacía.`);
  }
  rej.querySelectorAll(".tarjeta").forEach((el, i) => {
    el.onclick = (e) => {
      if (e.target.classList.contains("quitar")) {
        e.stopPropagation();
        lista[i].quitar?.();
        return;
      }
      cerrarTienda();
      lista[i].poner();
    };
  });
}

/** Mete en el proyecto una copia del módulo. (#026 · #086) */
function agregarDeLibreria(gabinete, nombre) {
  const g = JSON.parse(JSON.stringify(gabinete));
  let n = 1, nom = nombre;
  const usados = new Set(S.proyecto.gabinetes.map((x) => x.nombre));
  while (usados.has(nom)) nom = `${nombre} ${++n}`;
  g.nombre = nom;
  g.pos_x = g.pos_x || 0;
  g.pos_z = g.pos_z || 0;
  g.rot = 0;
  S.proyecto.gabinetes.push(g);
  S.sel = S.proyecto.gabinetes.length - 1;
  limpiarSub(false);
  pintarLista(); pintarGabinete(); recalcular();
  estado(T2("agregado desde la librería: %s", nom));
}

async function borrarModelo(m) {
  try {
    await api("/api/biblioteca/" + encodeURIComponent(m.id), { method: "DELETE" });
    cargarModulos();
    estado(T2("modelo quitado: %s", m.nombre));
  } catch (e) { estado(T2("no se pudo quitar: %s", e.message), true); }
}

async function borrarModulo(m) {
  try {
    await api("/api/modulos/" + m.id, { method: "DELETE" });
    cargarModulos();
    estado(T2("módulo quitado: %s", m.nombre));
  } catch (e) { estado(T2("no se pudo quitar: %s", e.message), true); }
}

/** #026 #086 — guarda el gabinete seleccionado como módulo reutilizable.
    Se pide la categoría: sin ella todo cae en un montón, que es de lo que
    este cambio venía a salir. La lista trae las que ya existen y deja escribir
    una nueva. */
function guardarModelo() {
  const g = S.proyecto.gabinetes[S.sel];
  if (!g) { estado("selecciona primero un gabinete", true); return; }
  const propias = (S.modulos || []).map((c) => c.nombre);
  modal("Guardar como módulo",
    `<div class="aviso">Queda en tu equipo, fuera del proyecto: lo vas a tener en
     todas las cocinas. Las actualizaciones no lo tocan.</div>
     <div class="fila"><label>Nombre del módulo</label>
       <input id="mNombreModelo" value="${esc(g.nombre)}"></div>
     <div class="fila"><label>Categoría</label>
       <input id="mCatModelo" list="mCats" placeholder="Mis módulos"
              value="${esc(propias[0] || "Mis módulos")}">
       <datalist id="mCats">${propias.map((c) => `<option value="${esc(c)}">`).join("")}</datalist>
     </div>
     <div class="fila"><label>Nota</label>
       <input id="mNotaModelo" placeholder="Para qué sirve y cuándo se usa"></div>
     <div style="font-size:11px;color:var(--txt3)">
       Se guarda la geometría, los frentes, los entrepaños y los materiales.
       La posición en la cocina no: eso es de cada proyecto. Los barrenos
       tampoco: los calcula el motor, y así no se desfasan.</div>`,
    async () => {
      const nombre = ($("mNombreModelo")?.value || g.nombre).trim();
      const categoria = ($("mCatModelo")?.value || "Mis módulos").trim();
      const nota = ($("mNotaModelo")?.value || "").trim();
      try {
        const r = await api("/api/modulos", {
          method: "POST", headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ categoria, nombre, nota, gabinete: g }),
        });
        estado(T2("guardado en «%s»: %s", r.categoria_nombre, r.nombre));
      } catch (e) { estado(T2("no se pudo guardar: %s", e.message), true); }
    }, "Guardar");
  setTimeout(() => $("mNombreModelo")?.select(), 40);
}

/* ============================================================ materiales */
function opcionesMaterial(id, valor, incluirVacio = true, textoVacio = "— del proyecto —") {
  const el = $(id);
  el.innerHTML = (incluirVacio ? `<option value="">${esc(textoVacio)}</option>` : "") +
    S.proyecto.catalogo.map((m) =>
      `<option value="${esc(m.nombre)}"${m.nombre === valor ? " selected" : ""}>${esc(m.nombre)}</option>`).join("");
  if (valor) el.value = valor;
}

function pintarMateriales() {
  $("tbMat").innerHTML = S.proyecto.catalogo.map((m, i) => `
    <tr data-i="${i}">
      <td><input class="col" type="color" data-c="color" value="${esc(m.color || "#D9D2C5")}"></td>
      <td><input data-c="nombre" value="${esc(m.nombre)}"></td>
      <td class="n"><input type="number" data-c="espesor" step="0.5" value="${m.espesor}" style="width:52px"></td>
      <td class="n"><input type="number" data-c="precio_hoja" step="10" value="${m.precio_hoja}" style="width:66px"></td>
      <td class="n"><input type="number" data-c="precio_canto_ml" step="1" value="${m.precio_canto_ml}" style="width:52px"></td>
      <td class="n"><input type="number" data-c="espesor_canto" step="0.5" min="0"
          value="${m.espesor_canto || 0}" style="width:46px"
          title="0 = usa el del estándar"></td>
      <td><input type="checkbox" data-c="veta"${m.veta ? " checked" : ""}></td>
      <td><button class="del" data-d="${i}" style="background:transparent;border:none;color:var(--txt3)">×</button></td>
    </tr>`).join("");
  $("tbMat").querySelectorAll("tr").forEach((tr) => {
    const i = +tr.dataset.i;
    tr.querySelectorAll("[data-c]").forEach((inp) =>
      inp.addEventListener(inp.type === "checkbox" ? "change" : "input", () => {
        const c = inp.dataset.c;
        const antes = S.proyecto.catalogo[i].nombre;
        S.proyecto.catalogo[i][c] = inp.type === "checkbox" ? inp.checked
          : (c === "nombre" || c === "color") ? inp.value : num(inp.value);
        if (c === "nombre") renombrarMaterial(antes, inp.value);
        if (c === "nombre" || c === "espesor") { pintarEstandar(); pintarGabinete(); pintarHojasMat(); }
        guardarTaller();                    // #037 — el catálogo es del taller
        recalcular();
      }));
    tr.querySelector("[data-d]").onclick = () => {
      S.proyecto.catalogo.splice(i, 1);
      guardarTaller();                      // #037
      pintarMateriales(); pintarEstandar(); pintarGabinete(); recalcular();
    };
  });
  pintarHojasMat();
}

function pintarHojasMat() {
  $("hojasMat").innerHTML = S.proyecto.catalogo.map((m, i) => `
    <div class="g2" style="margin-bottom:6px;align-items:center">
      <div style="font-size:11px;color:var(--txt2)">${esc(m.nombre)}</div>
      <div style="display:flex;gap:5px">
        <input type="number" data-h="${i}" data-k="largo_hoja" value="${m.largo_hoja}">
        <input type="number" data-h="${i}" data-k="ancho_hoja" value="${m.ancho_hoja}">
      </div></div>`).join("");
  $("hojasMat").querySelectorAll("[data-h]").forEach((inp) =>
    inp.oninput = () => {
      S.proyecto.catalogo[+inp.dataset.h][inp.dataset.k] = num(inp.value, 2440);
      guardarTaller();                      // #037
      recalcular();
    });
}

function renombrarMaterial(antes, ahora) {
  const e = S.proyecto.estandar;
  ["mat_cuerpo", "mat_frente", "mat_respaldo", "mat_cajon", "mat_fondo_cajon"].forEach((k) => {
    if (e[k] && e[k].nombre === antes) e[k] = { ...S.proyecto.catalogo.find((m) => m.nombre === ahora) };
  });
  S.proyecto.gabinetes.forEach((g) => {
    ["mat_cuerpo", "mat_frente", "mat_respaldo"].forEach((k) => { if (g[k] === antes) g[k] = ahora; });
  });
}

function agregarMaterial() {
  S.proyecto.catalogo.push({
    nombre: "Material nuevo", espesor: 18, largo_hoja: 2440, ancho_hoja: 1220,
    precio_hoja: 0, precio_canto_ml: 0, veta: false, familia: "Melamina", color: "#D9D2C5",
  });
  guardarTaller();                          // #037 — queda para todo el taller
  pintarMateriales(); pintarEstandar(); pintarGabinete();
}




/* ============================================================ #040 · la llave
   «Leer plano» viaja dentro de la app, pero la llave de API no: un instalador
   con la llave adentro es un instalador que la regala. Se teclea una vez y se
   queda en el perfil del equipo.

   No se vuelve a mostrar entera. Una llave en pantalla es una llave en la
   próxima captura que alguien mande por WhatsApp; con los últimos cuatro
   caracteres basta para saber CUÁL está puesta. */
async function pintarLlave() {
  try {
    const r = await api("/api/llave");
    $("llaveEstado").textContent = r.hay
      ? `puesta (${r.pista})` : "sin llave: «Leer plano» no va a poder leer";
    $("sLlave").value = "";
    $("sLlave").placeholder = r.hay ? "•••••••• (ya hay una)" : "sk-ant-…";
  } catch { /* backend caído: ya se avisa por otro lado */ }
}

async function guardarLlave(valor) {
  try {
    const r = await api("/api/llave", {
      method: "PUT", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ valor }),
    });
    estado(r.hay ? `llave guardada (${r.pista})` : "llave quitada");
    pintarLlave();
  } catch (e) { estado(T2("no se pudo guardar la llave: %s", e.message), true); }
}

/* ============================================================ #038 · proyecto
   Un proyecto es una CARPETA con los .t101x de sus muebles adentro, y un
   `proyecto.json` que dice de quién es el trabajo.

   Se eligió así, y no un archivo que contuviera todo, porque es como ya está
   organizado el trabajo en el taller: una carpeta por obra. Cada mueble se
   sigue mandando suelto por correo, nada se rompe si alguien mueve archivos, y
   abrir el proyecto es leer la carpeta — no hay índice que se desincronice. */
const PROY = { carpeta: null, nombre: "", cliente: "" };

async function abrirProyecto() {
  if (!window.despz?.abrirProyecto) {
    estado("abrir proyectos necesita la aplicación de escritorio", true);
    return;
  }
  const r = await window.despz.abrirProyecto();
  if (!r) return;
  if (r.error) { estado(r.error, true); return; }
  if (!r.muebles?.length) {
    estado(T2("«%s» no tiene muebles (.t101x) adentro", r.nombre), true);
    return;
  }
  PROY.carpeta = r.carpeta;
  PROY.nombre = r.nombre || "";
  PROY.cliente = r.cliente || "";

  for (const m of r.muebles) {
    try { cargarProyecto(JSON.parse(m.contenido), m.ruta); }
    catch { estado(T2("«%s» no se pudo leer", m.nombre), true); }
  }
  pintarProyecto();
  estado(T2("proyecto «%s»: %s mueble(s)", PROY.nombre, r.muebles.length));
}

function pintarProyecto() {
  const b = $("bProyecto");
  if (b) b.textContent = PROY.nombre ? PROY.nombre : "Proyecto…";
}

/** Despiece de TODOS los muebles abiertos, nesteados juntos. */
async function calcularProyecto() {
  guardarPestana();
  const muebles = P.docs
    .filter((d) => (d.proyecto?.gabinetes || []).length)
    .map((d) => d.proyecto);
  const cuerpo = $("proyCuerpo");
  if (!muebles.length) {
    cuerpo.innerHTML = `<div style="color:var(--txt3)">
      No hay muebles con gabinetes abiertos.</div>`;
    return;
  }
  cuerpo.innerHTML = `<div style="color:var(--txt3)">Calculando…</div>`;
  try {
    const r = await api("/api/proyecto/calcular", {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ nombre: PROY.nombre || "Proyecto",
                             cliente: PROY.cliente || "", muebles }),
    });
    pintarResumenProyecto(r);
  } catch (e) {
    cuerpo.innerHTML = `<div style="color:var(--warn)">${esc(e.message)}</div>`;
  }
}

function pintarResumenProyecto(r) {
  const a = r.ahorro || {};
  const dif = a.diferencia || 0;
  const costo = (r.costeo || []).reduce((s, c) => s + (c.costo_total || 0), 0);
  $("proyCuerpo").innerHTML = `
    <div style="display:flex;gap:26px;flex-wrap:wrap;margin-bottom:16px">
      ${[["Muebles", r.resumen.muebles], ["Piezas", r.resumen.piezas_totales],
         ["Hojas", r.resumen.hojas],
         ["Costo", "$" + costo.toLocaleString("es-MX", { maximumFractionDigits: 0 })]]
        .map(([k, v]) => `<div><div style="font-size:11px;color:var(--txt3);
          text-transform:uppercase;letter-spacing:.06em">${k}</div>
          <div style="font-size:21px">${v}</div></div>`).join("")}
    </div>
    ${dif > 0 ? `<div style="background:var(--aviso-bg);border-left:3px solid var(--acc);
        padding:9px 12px;margin-bottom:16px;font-size:12px">
        <b>Despiezando los muebles juntos salen ${a.hojas_juntas} hojas, y uno
        por uno serían ${a.hojas_sueltas}: ${dif} de menos.</b>
        Las piezas de un mueble caben en el retazo que deja el otro.</div>` : ""}
    <table style="width:100%;font-size:12px"><thead><tr>
      <th style="text-align:left;padding:5px 8px;color:var(--txt3)">Mueble</th>
      <th style="text-align:right;padding:5px 8px;color:var(--txt3)">Piezas</th>
      <th style="text-align:right;padding:5px 8px;color:var(--txt3)">Hojas por su cuenta</th>
    </tr></thead><tbody>
      ${(r.muebles || []).map((m) => `<tr>
        <td style="padding:5px 8px">${esc(m.mueble)}</td>
        <td style="padding:5px 8px;text-align:right">${m.piezas}</td>
        <td style="padding:5px 8px;text-align:right;color:var(--txt2)">${m.hojas}</td>
      </tr>`).join("")}
    </tbody></table>
    <div style="margin-top:16px;display:flex;align-items:center;gap:12px;flex-wrap:wrap">
      <button id="bExpProy">Exportar el proyecto completo</button>
      <span style="font-size:11.5px;color:var(--txt3)">
        Un juego con todo junto —planos de todos los muebles en un solo PDF— más
        una subcarpeta por mueble.</span>
    </div>`;
  $("bExpProy").onclick = exportarProyecto;
}

/** #071 — a disco: el juego conjunto y el de cada mueble.
 *
 *  El botón de siempre exporta SÓLO la pestaña de enfrente, y sus hojas de
 *  nesting son las de ese mueble solo. Aquí las hojas son las del proyecto
 *  entero, que son las que de verdad se van a cortar. */
async function exportarProyecto() {
  guardarPestana();
  const muebles = P.docs
    .filter((d) => (d.proyecto?.gabinetes || []).length)
    .map((d) => d.proyecto);
  if (!muebles.length) { estado("no hay muebles con gabinetes", true); return; }
  let carpeta = null;
  if (window.despz?.elegirCarpeta) {
    carpeta = await window.despz.elegirCarpeta();
    if (!carpeta) return;
  }
  const b = $("bExpProy");
  if (b) { b.disabled = true; b.textContent = "Exportando…"; }
  estado("exportando el proyecto…");
  try {
    const r = await api("/api/proyecto/exportar", {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ nombre: PROY.nombre || "Proyecto",
                             cliente: PROY.cliente || "", muebles, carpeta }),
    });
    modal("Proyecto exportado", `
      <div class="aviso">${r.resumen.muebles} muebles, ${r.resumen.piezas} piezas
        y ${r.resumen.hojas} hojas en:<br>
        <b style="color:var(--txt)" data-sin-traducir>${esc(r.carpeta)}</b></div>
      <p style="font-size:12px;color:var(--txt2);margin-bottom:6px">
        Lo de la carpeta principal es lo que se compra y se corta —el nesting está
        hecho con las piezas de todos los muebles juntas—. Las subcarpetas son
        para mandar un mueble suelto: no se suman, ya están adentro.</p>
      <ul style="margin-left:18px;font-size:12px;line-height:1.9">
        ${r.archivos.map((a) => `<li>${esc(a)}</li>`).join("")}
        ${(r.muebles || []).map((m) =>
          `<li style="color:var(--txt2)">${esc(m.carpeta)}/ — ${m.archivos.length} archivos</li>`
        ).join("")}</ul>`,
      window.despz?.abrirCarpeta ? () => window.despz.abrirCarpeta(r.carpeta) : null,
      window.despz?.abrirCarpeta ? "Abrir carpeta" : null);
    estado("proyecto exportado");
  } catch (e) {
    if (e.medidas) {
      problema(e.message);
      modal("No se puede exportar el proyecto",
        `<div class="aviso">${esc(e.message)}</div>
         <p style="font-size:12.5px;color:var(--txt2)">Se detuvo a propósito: es
         preferible corregir la medida a mandar piezas imposibles al corte.</p>`);
      estado("exportación detenida", true);
    } else {
      estado(T2("error al exportar: %s", e.message), true);
    }
  } finally {
    if (b) { b.disabled = false; b.textContent = "Exportar el proyecto completo"; }
  }
}

/* ============================================================ #037 · el taller
   Los materiales y el estándar constructivo son del TALLER, no de cada mueble.
   Un tablero cuesta lo que cuesta: si sube de precio, sube para todos los
   trabajos, no sólo para el que se abra después.

   Cada `.t101x` sigue guardando su catálogo —un mueble que se manda por correo
   tiene que abrirse completo en otra máquina— pero la base buena es la del
   taller, y al abrir un archivo lo que traiga y no esté se AGREGA a la base. */
let tGuardaTaller = null;

function guardarTaller() {
  clearTimeout(tGuardaTaller);
  tGuardaTaller = setTimeout(async () => {
    try {
      await api("/api/perfil", {
        method: "PUT", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ catalogo: S.proyecto.catalogo,
                               estandar: S.proyecto.estandar }),
      });
      DEF.catalogo = S.proyecto.catalogo;
      DEF.estandar = S.proyecto.estandar;
      repartirCatalogo();
    } catch { estado("no se pudo guardar el catálogo del taller", true); }
  }, 500);
}

/** El catálogo es uno solo: lo que se edita en un mueble vale para todos. */
function repartirCatalogo() {
  P.docs.forEach((d, i) => {
    if (i === P.activa || !d.proyecto) return;
    d.proyecto.catalogo = JSON.parse(JSON.stringify(DEF.catalogo));
  });
}

/** Al abrir un archivo, sus materiales desconocidos entran a la base del taller. */
async function fundirCatalogo(cat) {
  if (!cat || !cat.length) return;
  try {
    const r = await api("/api/perfil/fundir", {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ catalogo: cat }),
    });
    DEF.catalogo = r.perfil.catalogo;
    if (r.agregados?.length) {
      // se dice: un material que aparece solo en la lista de precios, sin
      // avisar, es peor que uno que falta
      estado(r.agregados.length === 1
        ? `«${r.agregados[0]}» se agregó al catálogo del taller`
        : `${r.agregados.length} materiales nuevos se agregaron al catálogo del taller`);
    }
  } catch { /* sin base del taller se sigue con lo que traiga el archivo */ }
}

/* ============================================================ estándar */
const MAPA_STD = {
  sEnsamble: "ensamble", sPaso: "paso_sistema", sOffset: "offset_linea_frente",
  sHp: "holgura_perimetral", sHef: "holgura_entre_frentes",
  sCorr: "holgura_corredera_lado", sHent: "holgura_entrepano",
  sRanurado: "respaldo_ranurado", sPranura: "prof_ranura", sOranura: "offset_ranura",
  sRespaldoCompleto: "respaldo_completo",                 // #065
  sAnchoTravRespaldo: "ancho_travesano_respaldo",
  sZoclo: "altura_zoclo", sRetZoclo: "retranqueo_zoclo",
  sKerf: "kerf", sSep: "separacion_piezas", sMargen: "margen_hoja",
  sAltoCaja: "alto_caja_cajon",
  sDescCanto: "descontar_canto",              // #006
  sRespInt: "respaldo_interior_desde",        // #003
  sColgado: "altura_colgado_aereo",           // #004
  sIman: "iman_distancia", sRejilla: "rejilla",
  // #028 #029 #030
  sHfc: "holgura_frente_costado",                        // #077
  sKerfSierra: "kerf_sierra",                            // #076
  sVuelo: "vuelo_cubierta", sVoladizo: "voladizo_lateral", sNariz: "alto_nariz",
  sJunta: "junta_cubierta", sPerfilNariz: "perfil_nariz",
  sGola: "gola", sAltoGola: "alto_gola",
  sUnero: "unero", sAltoManguete: "alto_manguete",      // #042
  sHolguraUnero: "holgura_unero",                      // #057
};
const MAPA_MAT = {
  sMatCuerpo: "mat_cuerpo", sMatFrente: "mat_frente", sMatRespaldo: "mat_respaldo",
  sMatCajon: "mat_cajon", sMatFondo: "mat_fondo_cajon",
  sMatCubierta: "mat_cubierta",       // #028
  sMatManguete: "mat_manguete",       // #067
};
// #067 — materiales que admiten «vacío». Vacío no es un error: significa que
// la pieza sigue al cuerpo, que es como se fabrica el manguete casi siempre.
const MAT_OPCIONAL = { sMatManguete: "— igual que el cuerpo —" };

function pintarEstandar() {
  const e = S.proyecto.estandar;
  Object.entries(MAPA_STD).forEach(([id, k]) => {
    const el = $(id);
    if (el.type === "checkbox") el.checked = !!e[k]; else el.value = e[k];
  });
  Object.entries(MAPA_MAT).forEach(([id, k]) =>
    opcionesMaterial(id, e[k] ? e[k].nombre : "",
                     id in MAT_OPCIONAL, MAT_OPCIONAL[id]));
}

function leerEstandar() {
  const e = S.proyecto.estandar;
  Object.entries(MAPA_STD).forEach(([id, k]) => {
    const el = $(id);
    e[k] = el.type === "checkbox" ? el.checked
      : el.tagName === "SELECT" ? el.value : num(el.value, e[k]);
  });
  Object.entries(MAPA_MAT).forEach(([id, k]) => {
    const v = $(id).value;
    if (!v && id in MAT_OPCIONAL) { e[k] = null; return; }   // #067
    const m = S.proyecto.catalogo.find((x) => x.nombre === v);
    if (m) e[k] = { ...m };
  });
  if ($("sOffset")) e.offset_linea_trasera = e.offset_linea_frente;
  // el zoclo del proyecto cambió: los gabinetes que lo heredan se recalculan (#001)
  S.proyecto.gabinetes.forEach((g) => {
    if (g.altura_zoclo == null) leerAlturasDesdeEstandar(g);
  });
  pintarGabinete(); pintarLista(); recalcular();
}

/* ============================================================ cálculo */
let tmr = null;
function recalcular(marcar = true) {
  if (marcar) marcarSucio();          // #015
  clearTimeout(tmr);
  tmr = setTimeout(hacerCalculo, 120);   // #088: antes 180
}
let turnoCalculo = 0;                     // #088: sólo cuenta la respuesta más nueva

async function hacerCalculo() {
  if (!S.proyecto.gabinetes.length) {
    S.ultimo = null; pintarResultados(null); construir3D([]); return;
  }
  estado("calculando…");
  const turno = ++turnoCalculo;
  try {
    const cuerpo = { method: "POST", headers: { "Content-Type": "application/json" },
                     body: JSON.stringify(S.proyecto) };
    // #088 — el 3D (rápido) se dibuja en cuanto llega, sin esperar la lista de
    // corte (lenta: acomoda piezas en hojas). Ambas se piden a la vez.
    const pCalc = api("/api/calcular", cuerpo);
    pCalc.catch(() => {});                  // su error se atiende abajo
    const s = await api("/api/solidos", cuerpo);
    if (turno !== turnoCalculo) return;     // ya hay un cálculo más nuevo en camino
    S.cubiertas3d = s.cubiertas || [];        // #028
    construir3D(s.gabinetes);
    const r = await pCalc;
    if (turno !== turnoCalculo) return;
    S.ultimo = r;
    pintarResultados(r);
    problema(null);
    estado("listo");
  } catch (e) {
    if (turno !== turnoCalculo) return;     // un error viejo no tapa un resultado nuevo
    if (e.medidas) {                     // #014
      problema(e.message);
      estado("medidas por corregir", true);
    } else {
      problema(null);
      estado(T2("error: %s", e.message.slice(0, 90)), true);
    }
  }
}

/* #014 — un problema de medidas se explica en grande, no en la barra de estado */
function problema(msg) {
  const el = $("problema");
  if (!el) return;
  el.style.display = msg ? "flex" : "none";
  if (msg) el.querySelector(".txt").textContent = msg;
}

function pintarResultados(r) {
  if (!r) {
    ["kPz", "kUn", "kHj", "kM2", "kAp"].forEach((k) => ($(k).textContent = "0"));
    $("kCosto").textContent = "$0";
    $("tbCorte").innerHTML = ""; $("tbCosteo").innerHTML = "";
    $("hojasCv").innerHTML = ""; $("tbCub").innerHTML = "";
    return;
  }
  const u = r.resumen;
  $("kPz").textContent = u.piezas_total;
  $("kUn").textContent = u.piezas_unicas;
  $("kHj").textContent = u.hojas;
  $("kM2").textContent = u.m2_hoja;
  $("kAp").textContent = u.m2_hoja ? ((u.m2_pieza / u.m2_hoja) * 100).toFixed(1) : "0";
  $("kCosto").textContent = money(u.costo_total);

  $("tbCorte").innerHTML = r.piezas.map((p) => `<tr>
    <td>${p.codigo}</td><td>${esc(p.mueble)}</td><td>${esc(p.nombre)}</td>
    <td>${esc(p.material)}</td><td class="n">${p.espesor}</td>
    <td class="n">${p.largo}</td><td class="n">${p.ancho}</td>
    <td class="n"><b>${p.cantidad}</b></td><td class="n">${p.canto_ml || ""}</td>
    <td style="color:var(--txt2)">${esc(p.nota || "")}</td></tr>`).join("");

  $("tbCosteo").innerHTML = r.costeo.map((c) => `<tr>
    <td>${esc(c.material)}</td><td class="n">${c.espesor}</td><td class="n">${c.hojas}</td>
    <td class="n">${money(c.precio_hoja)}</td><td class="n">${money(c.costo_material)}</td>
    <td class="n">${c.ml_canto}</td><td class="n">${money(c.costo_canto)}</td>
    <td class="n"><b>${money(c.costo_total)}</b></td></tr>`).join("");
  $("tbCub").innerHTML = (r.cubiertas || []).map((t, i) => `<tr>
    <td>C${i + 1}${t.partes > 1 ? ` <span class="badge">${t.parte}/${t.partes}</span>` : ""}</td>
    <td>${esc(t.material)}</td><td class="n">${t.espesor}</td>
    <td class="n">${t.largo}</td><td class="n">${t.fondo}</td><td class="n">${t.m2}</td>
    <td class="n">${t.alto_nariz}</td><td class="n">${t.ml_nariz}</td>
    <td class="n">${t.ml_doblado || ""}</td>
    <td style="color:var(--txt2)">${esc((t.muebles || []).join(", "))}</td>
    <td style="color:var(--txt2)">${esc(t.nota || "")}</td></tr>`).join("")
    || `<tr><td colspan="11" style="color:var(--txt3);padding:14px">
        Ningún mueble lleva cubierta todavía. Se marca por gabinete, en Configuración.
        </td></tr>`;
  if ($("rHojas").classList.contains("on")) pintarHojas();
}

function pintarHojas() {
  const r = S.ultimo;
  const c = $("hojasCv");
  if (!r || !r.hojas.length) { c.innerHTML = `<div class="vacio">Sin resultados</div>`; return; }
  c.innerHTML = r.hojas.map((h) => {
    const esc_ = 260 / h.ancho;
    const w = h.ancho * esc_, ht = h.alto * esc_;
    const piezas = h.piezas.map((p) => `
      <rect x="${p.x * esc_}" y="${(h.alto - p.y - p.h) * esc_}" width="${p.w * esc_}"
        height="${p.h * esc_}" fill="#0080C122" stroke="#0080C1" stroke-width="0.7"></rect>
      <text x="${(p.x + p.w / 2) * esc_}" y="${(h.alto - p.y - p.h / 2) * esc_}"
        fill="#e6e8ec" font-size="5" text-anchor="middle">${p.codigo}</text>`).join("");
    return `<div class="hojaBox">
      <div class="t"><b>Hoja ${h.idx}</b> ${esc(h.material)}
        <span style="margin-left:auto;color:var(--acc2)">${(h.aprov * 100).toFixed(1)}%</span></div>
      <svg width="${w}" height="${ht}" style="background:#12151b;border:1px solid #2a2f3a">
        ${piezas}</svg></div>`;
  }).join("");
}

/* ============================================================ 3D */
let escena, camara, render3, grupo3D, raf, controles, rejilla, grupoCub;
const GRUPOS_ES = {
  costado_izq: "Costados", costado_der: "Costados", piso: "Piso", tapa: "Tapa",
  travesano: "Travesaños", entrepano: "Entrepaños", respaldo: "Respaldo",
  frente: "Frentes", zoclo: "Zoclo", cajon: "Cajones",
  cajon_fondo: "Fondos de cajón",                    // #096
};

function init3D() {
  const cv = $("lienzo");
  render3 = new THREE.WebGLRenderer({ canvas: cv, antialias: true });
  render3.setPixelRatio(Math.min(devicePixelRatio, 2));
  escena = new THREE.Scene();
  escena.background = new THREE.Color((TEMAS[S.tema] || TEMAS.oscuro).lienzo);
  camara = new THREE.PerspectiveCamera(38, 1, 10, 40000);
  camara.position.set(1800, 1400, -2200);

  escena.add(new THREE.HemisphereLight(0xffffff, 0x2a2f3a, 1.5));
  const dl = new THREE.DirectionalLight(0xffffff, 1.6);
  dl.position.set(1600, 2600, 2000);
  escena.add(dl);
  const dl2 = new THREE.DirectionalLight(0xffffff, 0.55);
  dl2.position.set(-1800, 900, -1200);
  escena.add(dl2);

  const ct = TEMAS[S.tema] || TEMAS.oscuro;
  rejilla = new THREE.GridHelper(8000, 16, ct.rejilla1, ct.rejilla2);
  rejilla.position.y = -1;
  escena.add(rejilla);

  grupo3D = new THREE.Group();
  escena.add(grupo3D);
  controles = orbita(cv, camara, () => pedir3D());
  resize3D();
  cablear3D();
  vigilarCambios3D();
  // #088 — antes se dibujaba 60 veces por segundo aunque nada se moviera. Ahora
  // el bucle sólo pregunta «¿cambió algo?» (cuesta casi nada) y dibuja si sí:
  // se movió la cámara, o alguien pidió un cuadro con pedir3D().
  const camPos = new THREE.Vector3(NaN), camRot = new THREE.Quaternion(NaN), camProy = new THREE.Matrix4();
  (function loop() {
    raf = requestAnimationFrame(loop);
    const movio = !camara.position.equals(camPos) || !camara.quaternion.equals(camRot) ||
                  !camara.projectionMatrix.equals(camProy);
    if (!movio && pedidos3D <= 0) return;
    if (pedidos3D > 0) pedidos3D--;
    camPos.copy(camara.position); camRot.copy(camara.quaternion); camProy.copy(camara.projectionMatrix);
    actualizarEtiquetasCota();
    render3.render(escena, camara);
  })();
}

/* #088 — cuántos cuadros faltan por dibujar. Se piden unos cuantos (no uno)
   para cubrir cambios que terminan de aplicarse en el cuadro siguiente. */
let pedidos3D = 2;
function pedir3D(n = 2) { pedidos3D = Math.max(pedidos3D, n); }

/* Red de seguridad: casi todo lo que cambia la escena viene de algo que hizo
   la persona (clic, tecla, rueda, arrastre) o de un recálculo, que ya pide su
   cuadro. Así ningún cambio se queda sin dibujar aunque alguna función olvide
   pedirlo. Escuchar estos eventos no cuesta nada: sólo cambia un número. */
function vigilarCambios3D() {
  const unos = () => pedir3D(6);
  for (const ev of ["pointerdown", "pointerup", "click", "wheel", "keydown", "keyup", "input", "change"])
    document.addEventListener(ev, unos, { capture: true, passive: true });
  document.addEventListener("pointermove", (e) => { if (e.buttons) pedir3D(2); },
                            { capture: true, passive: true });
  addEventListener("focus", unos);
  document.addEventListener("visibilitychange", unos);
  // el tamaño del recuadro de cotas se guarda aquí: leerlo en cada cuadro
  // obligaba al navegador a recalcular toda la página a media tarea
  const cap = $("cotas3d");
  if (cap && typeof ResizeObserver !== "undefined") {
    new ResizeObserver(([e]) => { tamCotas.w = e.contentRect.width; tamCotas.h = e.contentRect.height; pedir3D(); })
      .observe(cap);
  }
}
const tamCotas = { w: 0, h: 0 };

function resize3D() {
  const c = $("centro");
  if (!c || !render3) return;
  const w = c.clientWidth, h = c.clientHeight;
  render3.setSize(w, h, false);
  camara.aspect = w / Math.max(h, 1);
  camara.updateProjectionMatrix();
  pedir3D();
}

/* offset que compensa el giro para que la huella quede en el cuadrante positivo (#004) */
function offsetGiro(rot, A, P) {
  return rot === 90 ? [P, 0] : rot === 180 ? [A, P] : rot === 270 ? [0, A] : [0, 0];
}

function colocarNodo(nodo, g, pos, bbox) {
  const rot = ((pos.rot || 0) % 360 + 360) % 360;
  const [ox, oz] = offsetGiro(rot, bbox[0], bbox[2]);
  nodo.rotation.y = -rot * Math.PI / 180;
  nodo.position.set((pos.x || 0) + ox, pos.base || 0, (pos.z || 0) + oz);
}

/* #058 — Una pieza con el canto cortado a 45°.
 *
 * En el taller la puerta se corta recta como todas y el chaflán se hace después
 * en la tupí. Pero si el 3D la enseña recta, nadie sabe cuál canto lo lleva, y
 * el uñero se ve como un hueco sin explicación. Así que aquí sí se dibuja.
 *
 * `chaflan: "sup"` = el canto de ARRIBA. #062, corregido por Mike: el corte
 * **mira hacia adentro del mueble**. Se quita el triángulo de atrás, no el de
 * adelante: la cara del frente conserva todo su alto y detrás queda el plano
 * inclinado. Así es como se jala — los dedos entran por el hueco y empujan
 * contra ese plano. Al revés, el filo quedaba adelante y no había de dónde
 * agarrar.
 *
 * `chaflan: "inf"` = lo mismo en el canto de abajo, que es lo que lleva el
 * manguete para mirar al de la puerta.
 *
 * Ejes de three: X = ancho, Y = alto, Z = profundidad (el frente en −Z local).
 */
function geoChaflan(p) {
  // #066 — se arma con `ExtrudeGeometry` en vez de a mano.
  //
  // La primera versión construía el BufferGeometry vértice por vértice, y las
  // caras salían con el giro cambiado: las normales apuntaban hacia adentro, así
  // que el frente se veía transparente y con una franja diagonal encima. Three
  // ya sabe hacer esto —tapas, contorno y normales— a partir de un perfil, y lo
  // hace bien. Menos código nuestro y una clase entera de error que desaparece.
  const c = Math.min(p.dy, p.dz);      // el chaflán es a 45°: cateto = espesor
  const A = p.dz / 2, F = p.dy / 2;    // medio alto y media profundidad
  // Perfil en el plano (profundidad, alto). El frente está en −profundidad.
  const forma = new THREE.Shape();
  if (p.chaflan === "inf") {
    // el del manguete abre hacia ATRÁS igual que el de la puerta: los dos
    // bisels se miran y forman la V por donde entran los dedos, angosta
    // adelante y abierta hacia adentro del mueble.
    forma.moveTo(-F, -A); forma.lineTo(F - c, -A);
    forma.lineTo(F, -A + c); forma.lineTo(F, A); forma.lineTo(-F, A);
  } else {
    forma.moveTo(-F, -A); forma.lineTo(F, -A);
    forma.lineTo(F, A - c); forma.lineTo(F - c, A); forma.lineTo(-F, A);
  }
  const geo = new THREE.ExtrudeGeometry(forma, { depth: p.dx, bevelEnabled: false });
  // El perfil se extruye a lo largo de +Z; aquí eso es el ANCHO de la pieza.
  // Se gira para dejarlo en X y se centra, que es como vienen todas las demás.
  geo.translate(0, 0, -p.dx / 2);
  geo.rotateY(-Math.PI / 2);
  geo.computeVertexNormals();
  return geo;
}

function construir3D(gabs) {
  while (grupo3D.children.length) {
    const o = grupo3D.children.pop();
    o.traverse?.((n) => { n.geometry?.dispose?.(); n.material?.dispose?.(); });
    grupo3D.remove(o);
  }
  S.solidos = gabs;
  refrescarSugerenciaCaja();          // #097
  const usados = new Set();
  gabs.forEach((g, gi) => {
    const nodo = new THREE.Group();
    nodo.userData.gi = gi;
    nodo.userData.bbox = g.bbox;
    g.piezas.forEach((p) => {
      usados.add(p.grupo);
      const geo = p.chaflan ? geoChaflan(p) : new THREE.BoxGeometry(p.dx, p.dz, p.dy);
      const c = S.colorPor === "rol" ? (p.color_rol || p.color) : p.color;
      const mat = new THREE.MeshLambertMaterial({ color: new THREE.Color(c[0], c[1], c[2]) });
      const m = new THREE.Mesh(geo, mat);
      // gabinete: X=ancho, Y=prof, Z=alto → three: X=ancho, Y=alto, Z=prof
      const base = new THREE.Vector3(p.x + p.dx / 2, p.z + p.dz / 2, p.y + p.dy / 2);
      m.position.copy(base);
      m.userData.base = base.clone();
      m.userData.exp = new THREE.Vector3(p.explosion[0], p.explosion[2], p.explosion[1]);
      m.userData.d = Math.max(g.bbox[0], g.bbox[1], g.bbox[2]) * 0.32;
      m.userData.gi = gi;
      m.userData.ref = p.ref || null;      // #023
      m.userData.grupo = p.grupo;
      m.userData.etiqueta = p.etiqueta;
      m.userData.colMat = p.color;
      m.userData.colRol = p.color_rol || p.color;
      nodo.add(m);
      const ln = new THREE.LineSegments(
        new THREE.EdgesGeometry(geo),
        new THREE.LineBasicMaterial({ color: (TEMAS[S.tema] || TEMAS.oscuro).arista }));
      ln.visible = S.aristas;
      m.add(ln);
    });
    colocarNodo(nodo, g, g.pos || {}, g.bbox);
    grupo3D.add(nodo);
  });
  dibujarCubiertas(S.cubiertas3d);      // #028
  aplicarExplosion();
  pintarLeyenda(usados);
  // sólo re-encuadra si cambió el conjunto de gabinetes, no en cada tecleo
  const firma = gabs.map((g) => g.nombre + g.bbox.join("x")).join("|");
  if (firma !== S.firma3D) { S.firma3D = firma; encuadrar(); }
  resaltar3D();
  pedir3D();
}

/* #028 — la cubierta no cuelga de ningún mueble: es un tramo de la cocina, así
   que va en su propio grupo. Tampoco se sub-selecciona: no se despieza por
   dentro, se pide por medida. */
function dibujarCubiertas(lista) {
  if (!grupoCub) {
    grupoCub = new THREE.Group();
    escena.add(grupoCub);
    // para que las pruebas puedan mirar dónde quedó la cubierta (#064)
    if (typeof window !== "undefined") window.__grupoCub = grupoCub;
  }
  while (grupoCub.children.length) {
    const o = grupoCub.children.pop();
    o.traverse?.((n) => { n.geometry?.dispose?.(); n.material?.dispose?.(); });
    grupoCub.remove(o);
  }
  S.cubCajas = 0;         // cuántas cajas se dibujaron (plancha + narices)
  (lista || []).forEach((t) => {
    const rot = ((t.rot || 0) % 360 + 360) % 360;
    const ejeX = rot % 180 === 0;
    const dx = ejeX ? t.largo : t.fondo;
    const dz = ejeX ? t.fondo : t.largo;
    const c = t.color || [0.56, 0.55, 0.52];
    const mat = new THREE.MeshLambertMaterial({ color: new THREE.Color(c[0], c[1], c[2]) });

    const caja = (ax, ay, az, bx, by, bz) => {
      const g = new THREE.BoxGeometry(bx - ax, by - ay, bz - az);
      const m = new THREE.Mesh(g, mat);
      m.position.set((ax + bx) / 2, (ay + by) / 2, (az + bz) / 2);
      m.userData.cubierta = t;
      m.userData.muebles = t.muebles || [];
      m.userData.pos0 = m.position.clone();   // de dónde partió, para el arrastre
      // #064 — la cubierta también se despega en el explosivo, y se va ARRIBA
      // DE TODO: es la última pieza que se pone. Vive en su propio grupo
      // (`grupoCub`) porque no es de ningún mueble sino del tramo, y por eso
      // se quedaba clavada mientras el resto se abría.
      m.userData.base = m.position.clone();
      m.userData.exp = new THREE.Vector3(0, 1.9, 0);
      m.userData.d = Math.max(bx - ax, by - ay, bz - az) * 0.32;
      grupoCub.add(m);
      S.cubCajas++;
      const ln = new THREE.LineSegments(
        new THREE.EdgesGeometry(g),
        new THREE.LineBasicMaterial({ color: (TEMAS[S.tema] || TEMAS.oscuro).arista }));
      ln.visible = S.aristas;
      m.add(ln);
      return m;
    };

    // La plancha se APOYA sobre el mueble: `t.alto` es su cara de abajo, que
    // coincide con donde termina el gabinete. El espesor va por encima.
    caja(t.x, t.alto, t.z, t.x + dx, t.alto + t.espesor, t.z + dz);

    // #029 — la nariz: la faja que cuelga del filo de adelante. Lo que se ve de
    // más allá del espesor de la plancha es material pegado por debajo, y hasta
    // ahora no se dibujaba en ningún lado: se ponía la nariz y no pasaba nada.
    const doblado = Math.max(0, (t.alto_nariz || 0) - t.espesor);
    if (doblado > 0.5) {
      const e = t.espesor;
      const y0 = t.alto - doblado, y1 = t.alto;
      // el frente es la cara de las puertas, y depende de cómo esté girado
      if (rot === 0)        caja(t.x, y0, t.z, t.x + dx, y1, t.z + e);
      else if (rot === 180) caja(t.x, y0, t.z + dz - e, t.x + dx, y1, t.z + dz);
      else if (rot === 90)  caja(t.x + dx - e, y0, t.z, t.x + dx, y1, t.z + dz);
      else                  caja(t.x, y0, t.z, t.x + e, y1, t.z + dz);
    }
  });
}

/* ---------- recolocar sin reconstruir, para que el arrastre sea fluido ---------- */
function recolocar3D() {
  grupo3D.children.forEach((n) => {
    const g = S.proyecto.gabinetes[n.userData.gi];
    if (!g) return;
    const base = g.tipo === "aereo"
      ? (g.alto_colgado != null ? g.alto_colgado : S.proyecto.estandar.altura_colgado_aereo)
      : 0;
    colocarNodo(n, g, { x: g.pos_x, z: g.pos_z, rot: g.rot, base }, n.userData.bbox);
  });
  arrastrarCubiertas();
}

/* La cubierta es parte del mueble, como una puerta: si el mueble se mueve, se
   mueve con él. Mientras dura el arrastre se corre el mismo trecho que el
   gabinete —sin ir al servidor, para que no se quede atrás— y al soltar,
   `recalcular()` vuelve a repartir los tramos de verdad: un mueble que se sale
   de la corrida la parte en dos, y eso sólo lo sabe el motor. */
function arrastrarCubiertas() {
  if (!grupoCub || !arrastreMueble) return;
  const g = S.proyecto.gabinetes[arrastreMueble.gi];
  if (!g) return;
  const dx = g.pos_x - arrastreMueble.x0;
  const dz = g.pos_z - arrastreMueble.z0;
  grupoCub.children.forEach((m) => {
    const suyos = m.userData.muebles || [];
    if (!suyos.includes(g.nombre)) return;
    const p = m.userData.pos0;
    if (!p) return;
    // el arrastre mueve el punto de partida; el explosivo se aplica encima
    m.userData.base.set(p.x + dx, p.y, p.z + dz);
    m.position.set(p.x + dx, p.y, p.z + dz);
  });
}

function repintarColores() {
  grupo3D.traverse((m) => {
    if (!m.isMesh || !m.userData.colMat) return;
    const c = S.colorPor === "rol" ? m.userData.colRol : m.userData.colMat;
    m.material.color.setRGB(c[0], c[1], c[2]);
  });
}

function aplicarExplosion() {
  const mover = (m) => {
    if (!m.isMesh || !m.userData.base) return;
    const u = m.userData;
    m.position.copy(u.base).addScaledVector(u.exp, u.d * S.explosion);
  };
  grupo3D.traverse(mover);
  if (grupoCub) grupoCub.traverse(mover);      // #064
  pedir3D();
}

function resaltar3D() {
  const varios = grupo3D.children.length > 1;
  grupo3D.children.forEach((n) => {
    const on = !varios || S.sel < 0 || n.userData.gi === S.sel;
    n.traverse((m) => {
      if (m.isMesh) { m.material.opacity = on ? 1 : 0.5; m.material.transparent = !on; }
      if (m.isLineSegments) m.material.opacity = on ? 1 : 0.25, m.material.transparent = !on;
    });
  });
  pintarCotas();
  const g = S.proyecto.gabinetes[S.sel];
  $("info3d").innerHTML = g
    ? `<div><b style="color:var(--txt)">${esc(g.nombre)}</b></div>
       <div>${g.ancho} × ${g.alto} × ${g.prof} mm</div>
       <div style="color:var(--txt3)">arrastra: girar · rueda: zoom · shift+arrastra: mover</div>`
    : "";
}

function pintarLeyenda(usados) {
  const vistos = new Map();
  usados.forEach((g) => {
    const n = GRUPOS_ES[g] || g;
    if (!vistos.has(n)) vistos.set(n, COLORES[g] || [0.8, 0.8, 0.8]);
  });
  $("leyenda").innerHTML = [...vistos.entries()].map(([n, c]) =>
    `<div class="it"><span class="sw" style="background:rgb(${c.map((v) => Math.round(v * 255)).join(",")})"></span>${n}</div>`
  ).join("");
}
const COLORES = {
  costado_izq: [0.86, 0.83, 0.78], costado_der: [0.86, 0.83, 0.78],
  piso: [0.86, 0.83, 0.78], tapa: [0.86, 0.83, 0.78], travesano: [0.86, 0.83, 0.78],
  entrepano: [0.90, 0.87, 0.82], respaldo: [0.72, 0.70, 0.66],
  frente: [0.70, 0.76, 0.82], zoclo: [0.55, 0.58, 0.62], cajon: [0.80, 0.84, 0.78],
};

function encuadrar() {
  const caja = new THREE.Box3().setFromObject(grupo3D);
  // #035 — sin muebles no hay nada que encuadrar, pero sí una rejilla que
  // mirar. Sin esto, un proyecto vacío deja la cámara donde la dejó el mueble
  // anterior y se ve un piso torcido saliéndose de la pantalla.
  if (caja.isEmpty()) {
    const c = new THREE.Vector3(600, 400, 300);
    camara.position.set(c.x + 1900, c.y + 1500, c.z - 2400);
    controles.objetivo.copy(c);
    camara.lookAt(c);
    return;
  }
  const c = caja.getCenter(new THREE.Vector3());
  const t = caja.getSize(new THREE.Vector3());
  // radio = semi-diagonal del envolvente, corregido por el aspecto del viewport
  const semi = Math.max(t.x / Math.max(camara.aspect, 0.6), t.y, t.z) / 2;
  const d = (semi / Math.tan((camara.fov * Math.PI) / 360)) * 1.45;
  // el frente del gabinete está en Z=0, así que la cámara va del lado -Z
  const dir = new THREE.Vector3(0.68, 0.48, -0.92).normalize().multiplyScalar(d);
  camara.position.copy(c).add(dir);
  controles.objetivo.copy(c);
  camara.lookAt(c);
}



/* ---------- arrastre y selección sobre el lienzo (#004 #012) ---------- */
let arrastreMueble = null;

function empezarArrastreMueble(e) {
  if (e.button !== 0 || e.shiftKey) return false;
  const hit = gabineteBajoCursor(e);
  if (!hit) return false;
  const g = S.proyecto.gabinetes[hit.gi];
  if (!g) return false;

  // seleccionar siempre; mover sólo si el modo está activo
  const eraSel = hit.gi === S.sel;
  if (!eraSel) {
    S.sel = hit.gi;
    limpiarSub(false);
    pintarLista(); pintarGabinete(); resaltar3D(); pintarCotas();
  }
  if (!S.mover) {
    // sin modo mover no hay arrastre, pero el clic sigue entrando a la pieza
    if (eraSel) subseleccionar(hit);
    return false;
  }

  const base = g.tipo === "aereo"
    ? (g.alto_colgado != null ? g.alto_colgado : S.proyecto.estandar.altura_colgado_aereo)
    : 0;
  const p0 = puntoEnPiso(e, base);
  if (!p0) return false;
  arrastreMueble = {
    gi: hit.gi, base, movido: false, eraSel,
    dx: (g.pos_x || 0) - p0.x, dz: (g.pos_z || 0) - p0.z,
    // de dónde salió el mueble: la cubierta se corre ese mismo trecho
    x0: g.pos_x || 0, z0: g.pos_z || 0,
  };
  $("lienzo").setPointerCapture(e.pointerId);
  $("lienzo").style.cursor = "grabbing";
  return true;
}

function cablear3D() {
  const el = $("lienzo");

  el.addEventListener("pointermove", (e) => {
    if (!arrastreMueble) {
      if (S.mover) el.style.cursor = gabineteBajoCursor(e) ? "grab" : "default";
      return;
    }
    const g = S.proyecto.gabinetes[arrastreMueble.gi];
    const p = puntoEnPiso(e, arrastreMueble.base);
    if (!g || !p) return;
    g.pos_x = p.x + arrastreMueble.dx;
    g.pos_z = p.z + arrastreMueble.dz;
    imantar(g);
    arrastreMueble.movido = true;
    recolocar3D(); pintarCotas();
    $("gPosX").value = Math.round(g.pos_x);
    $("gPosZ").value = Math.round(g.pos_z);
  });

  const soltar = (e) => {
    if (!arrastreMueble) return;
    const movido = arrastreMueble.movido;
    const eraSel = arrastreMueble.eraSel;
    arrastreMueble = null;
    el.style.cursor = "default";
    try { el.releasePointerCapture(e.pointerId); } catch {}
    if (movido) { pintarLista(); recalcular(); return; }
    if (eraSel) subseleccionar(gabineteBajoCursor(e));    // #023
  };
  el.addEventListener("pointerup", soltar);
  el.addEventListener("pointercancel", soltar);

  window.addEventListener("keydown", (e) => {
    if (/^(INPUT|SELECT|TEXTAREA)$/.test(document.activeElement?.tagName || "")) return;
    if (e.key === "r" || e.key === "R") girarSeleccionado();
    else if (e.key === "Escape" && S.sub) { limpiarSub(); estado("listo"); }
    // #036 — pestañas: Ctrl+T otro mueble, Ctrl+W cerrar, Ctrl+Tab siguiente
    else if (e.ctrlKey && !e.shiftKey && e.key.toLowerCase() === "t") { e.preventDefault(); nuevo(); }
    else if (e.ctrlKey && e.key.toLowerCase() === "w") { e.preventDefault(); cerrarPestana(P.activa); }
    else if (e.ctrlKey && e.key === "Tab" && P.docs.length > 1) {
      e.preventDefault();
      irAPestana((P.activa + (e.shiftKey ? -1 : 1) + P.docs.length) % P.docs.length);
    }
  });
}

/* ============================================================ interacción 3D */
/* #012 — clic sobre un mueble lo selecciona; #004 — arrastrarlo lo mueve */
const rayo = new THREE.Raycaster();
const raton = new THREE.Vector2();
const planoPiso = new THREE.Plane(new THREE.Vector3(0, 1, 0), 0);

function aNDC(e) {
  const r = $("lienzo").getBoundingClientRect();
  raton.set(((e.clientX - r.left) / r.width) * 2 - 1,
            -((e.clientY - r.top) / r.height) * 2 + 1);
  return raton;
}

function gabineteBajoCursor(e) {
  rayo.setFromCamera(aNDC(e), camara);
  const hit = rayo.intersectObjects(grupo3D.children, true)
                  .find((h) => h.object.isMesh);
  return hit ? { gi: hit.object.userData.gi, punto: hit.point, malla: hit.object } : null;
}

/* #023 — segundo clic sobre el mueble ya seleccionado: entra a la pieza.
   Es el gesto de siempre en un modelador: uno selecciona el grupo, otro entra. */
function subseleccionar(hit) {
  const ref = hit?.malla?.userData?.ref;
  if (!ref || hit.gi !== S.sel) { limpiarSub(); return false; }
  S.sub = { gi: hit.gi, tipo: ref.tipo, i: ref.i,
            etiqueta: hit.malla.userData.etiqueta || "" };
  resaltarSub();
  pintarCotas();
  estado(T2("editando %s — clic en la cota para cambiarla",
                S.sub.etiqueta || S.sub.tipo));
  return true;
}

function limpiarSub(repintar = true) {
  if (!S.sub) return;
  S.sub = null;
  resaltarSub();
  if (repintar) pintarCotas();
}

/** La pieza sub-seleccionada se marca; el resto del mueble se atenúa. */
function resaltarSub() {
  grupo3D.traverse((m) => {
    if (!m.isMesh || !m.userData.colMat) return;
    const c = S.colorPor === "rol" ? m.userData.colRol : m.userData.colMat;
    const r = m.userData.ref;
    const esta = S.sub && m.userData.gi === S.sub.gi
                 && r && r.tipo === S.sub.tipo && r.i === S.sub.i;
    if (S.sub && m.userData.gi === S.sub.gi) {
      if (esta) m.material.color.setRGB(
        Math.min(1, c[0] * 0.55 + 0.20), Math.min(1, c[1] * 0.75 + 0.32), Math.min(1, c[2] * 0.9 + 0.42));
      else m.material.color.setRGB(c[0], c[1], c[2]);
      m.material.opacity = esta ? 1 : 0.72;
      m.material.transparent = !esta;
    } else {
      m.material.color.setRGB(c[0], c[1], c[2]);
    }
  });
}

function puntoEnPiso(e, alturaY) {
  rayo.setFromCamera(aNDC(e), camara);
  planoPiso.constant = -(alturaY || 0);
  const p = new THREE.Vector3();
  return rayo.ray.intersectPlane(planoPiso, p) ? p : null;
}

/* huella en planta del gabinete, en coordenadas de cocina */
function huella(g) {
  const rot = ((g.rot || 0) % 360 + 360) % 360;
  const [a, p] = rot % 180 === 90 ? [g.prof, g.ancho] : [g.ancho, g.prof];
  return { x0: g.pos_x || 0, z0: g.pos_z || 0,
           x1: (g.pos_x || 0) + a, z1: (g.pos_z || 0) + p, a, p };
}

/* #004 — rejilla + imán contra los demás muebles */
function imantar(g) {
  const e = S.proyecto.estandar;
  const rej = Math.max(1, e.rejilla || 10);
  const tol = e.iman_distancia || 80;
  g.pos_x = Math.round(g.pos_x / rej) * rej;
  g.pos_z = Math.round(g.pos_z / rej) * rej;

  const h = huella(g);
  let mejorX = null, mejorZ = null;
  S.proyecto.gabinetes.forEach((o, i) => {
    if (i === S.sel || o === g) return;
    const q = huella(o);
    // se pegan de lado sólo si se traslapan en el otro eje
    const solapaZ = h.z0 < q.z1 + tol && q.z0 < h.z1 + tol;
    const solapaX = h.x0 < q.x1 + tol && q.x0 < h.x1 + tol;
    if (solapaZ) {
      for (const [borde, destino] of [[h.x0, q.x1], [h.x1, q.x0],
                                      [h.x0, q.x0], [h.x1, q.x1]]) {
        const d = destino - borde;
        if (Math.abs(d) <= tol && (mejorX === null || Math.abs(d) < Math.abs(mejorX)))
          mejorX = d;
      }
    }
    if (solapaX) {
      for (const [borde, destino] of [[h.z0, q.z1], [h.z1, q.z0],
                                      [h.z0, q.z0], [h.z1, q.z1]]) {
        const d = destino - borde;
        if (Math.abs(d) <= tol && (mejorZ === null || Math.abs(d) < Math.abs(mejorZ)))
          mejorZ = d;
      }
    }
  });
  if (mejorX !== null) g.pos_x += mejorX;
  if (mejorZ !== null) g.pos_z += mejorZ;
  return { x: mejorX !== null, z: mejorZ !== null };
}

function girarSeleccionado() {
  const g = S.proyecto.gabinetes[S.sel];
  if (!g) return;
  g.rot = (((g.rot || 0) + 90) % 360);
  recolocar3D(); pintarGabinete(); pintarCotas(); recalcular();
}

/* ============================================================ cotas
   #002 #013 — cotas del gabinete seleccionado.
   #022 — se pueden editar: al hacer clic en la cifra se vuelve un campo y lo
          que escribas cambia el modelo. Es la diferencia entre un visor y algo
          paramétrico.
   #023 — si hay una sub-pieza seleccionada (una puerta, un entrepaño), se
          muestran SUS cotas en vez de las del mueble. */

function nodoDe(gi) {
  return grupo3D.children.find((n) => n.userData.gi === gi);
}

/** Mallas del gabinete gi que apuntan a la misma parte del modelo. */
function mallasDe(gi, tipo, i) {
  const out = [];
  nodoDe(gi)?.traverse((m) => {
    const r = m.userData?.ref;
    if (m.isMesh && r && r.tipo === tipo && r.i === i) out.push(m);
  });
  return out;
}

function cajaMundo(mallas) {
  if (!mallas.length) return null;
  const caja = new THREE.Box3();
  mallas.forEach((m, k) => (k ? caja.expandByObject(m) : caja.setFromObject(m)));
  return caja;
}

/** Cotas de la sub-pieza seleccionada. Devuelve [] si no aplica. (#023) */
function cotasDeSub(g, datos) {
  const sub = S.sub;
  if (!sub || sub.gi !== S.sel) return [];
  const mallas = mallasDe(sub.gi, sub.tipo, sub.i);
  const caja = cajaMundo(mallas);
  if (!caja) return [];
  const sep = 90;
  const x = caja.max.x + sep;
  const z = caja.max.z + sep;

  if (sub.tipo === "frente") {
    const fr = (datos?.frentes || [])[sub.i];
    const alto = fr ? fr.alto : (caja.max.y - caja.min.y);
    return [{
      campo: "frente", i: sub.i, valor: alto, t: cm(alto),
      a: [x, caja.min.y, z], b: [x, caja.min.y + alto, z],
      ayuda: (fr && fr.tipo === "cajon" ? "alto del frente de cajón" : "alto de la puerta")
             + (fr && !fr.propio ? " · ahora lo reparte solo" : ""),
    }];
  }
  if (sub.tipo === "entrepano") {
    const ent = datos?.entrepanos || {};
    const h = (ent.alturas || [])[sub.i];
    if (h == null) return [];
    const pisoY = caja.min.y - h;              // el piso interior, deducido
    return [{
      campo: "entrepano", i: sub.i, valor: h, t: cm(h),
      a: [x, pisoY, z], b: [x, pisoY + h, z],
      ayuda: "altura libre bajo el entrepaño"
             + (ent.fijos ? "" : ` · regulable, se pega al paso de ${ent.paso} mm`),
    }];
  }
  return [];
}

function pintarCotas() {
  const cap = $("cotas3d");
  const g = S.proyecto.gabinetes[S.sel];
  const nodo = nodoDe(S.sel);
  if (!S.cotas || !g || !nodo) { cap.innerHTML = ""; S.cotasGeo = null; return; }

  const datos = S.solidos[S.sel];
  const sub = cotasDeSub(g, datos);
  if (sub.length) {
    S.cotasGeo = sub;
  } else {
    const h = huella(g);
    const base = g.tipo === "aereo"
      ? (g.alto_colgado != null ? g.alto_colgado : S.proyecto.estandar.altura_colgado_aereo)
      : 0;
    const alto = g.alto;
    const d = Math.max(80, Math.min(g.ancho, g.prof) * 0.18);
    // #060 — las cotas van DELANTE del mueble, no detrás.
    //
    // Estaban todas colgadas de `z1 + d`, que en un mueble sin girar es la
    // pared: el propio gabinete se pone encima de las líneas y no se entiende
    // qué se está midiendo. Aquí se pone cada una del lado del frente —el de
    // las puertas— según cómo esté girado, con la misma tabla que usa la
    // cubierta (#039): 0° mira a −z, 90° a +x, 180° a +z, 270° a −x.
    const rot = ((g.rot || 0) % 360 + 360) % 360;
    // ancho: recorre la cara del frente. prof: recorre el costado.
    // alto: sube por la esquina donde se cruzan las dos.
    const L = {
      0:   { an: [[h.x0, h.z0 - d], [h.x1, h.z0 - d]],
             pr: [[h.x1 + d, h.z0], [h.x1 + d, h.z1]], esq: [h.x1 + d, h.z0 - d] },
      180: { an: [[h.x0, h.z1 + d], [h.x1, h.z1 + d]],
             pr: [[h.x0 - d, h.z0], [h.x0 - d, h.z1]], esq: [h.x0 - d, h.z1 + d] },
      90:  { an: [[h.x1 + d, h.z0], [h.x1 + d, h.z1]],
             pr: [[h.x0, h.z1 + d], [h.x1, h.z1 + d]], esq: [h.x1 + d, h.z1 + d] },
      270: { an: [[h.x0 - d, h.z0], [h.x0 - d, h.z1]],
             pr: [[h.x0, h.z0 - d], [h.x1, h.z0 - d]], esq: [h.x0 - d, h.z0 - d] },
    }[rot] || null;
    const P = L || { an: [[h.x0, h.z0 - d], [h.x1, h.z0 - d]],
                     pr: [[h.x1 + d, h.z0], [h.x1 + d, h.z1]],
                     esq: [h.x1 + d, h.z0 - d] };
    S.cotasGeo = [
      { campo: "ancho", valor: g.ancho, t: cm(g.ancho), ayuda: "ancho del mueble",
        a: [P.an[0][0], base, P.an[0][1]], b: [P.an[1][0], base, P.an[1][1]] },
      { campo: "prof", valor: g.prof, t: cm(g.prof),
        ayuda: llevaCubierta(g) ? "fondo de la cubierta, del filo a la pared"
                                : "fondo al frente de la puerta",
        a: [P.pr[0][0], base, P.pr[0][1]], b: [P.pr[1][0], base, P.pr[1][1]] },
      { campo: "alto", valor: alto, t: cm(alto),
        ayuda: llevaCubierta(g) ? "altura total con cubierta, zoclo incluido"
                                : "altura total, con zoclo",
        a: [P.esq[0], base, P.esq[1]], b: [P.esq[0], base + alto, P.esq[1]] },
    ];
  }

  if (!S.lineasCota) {
    S.lineasCota = new THREE.Group();
    escena.add(S.lineasCota);
  }
  while (S.lineasCota.children.length) {
    const o = S.lineasCota.children.pop();
    o.geometry?.dispose?.(); o.material?.dispose?.();
    S.lineasCota.remove(o);
  }
  const matL = new THREE.LineBasicMaterial(
    { color: (TEMAS[S.tema] || TEMAS.oscuro).cota });
  S.cotasGeo.forEach((c) => {
    const geo = new THREE.BufferGeometry().setFromPoints(
      [new THREE.Vector3(...c.a), new THREE.Vector3(...c.b)]);
    S.lineasCota.add(new THREE.Line(geo, matL));
  });
  cap.innerHTML = S.cotasGeo.map((c, i) =>
    `<div class="cota editable" data-c="${i}" title="${esc(T2("%s — clic para editar", T(c.ayuda || "")))}"></div>`
  ).join("");
  cap.querySelectorAll(".cota").forEach((el) =>
    el.onclick = (e) => { e.stopPropagation(); editarCota(+el.dataset.c, el); });
  pedir3D();     // #088 — las etiquetas se colocan en el próximo cuadro, antes de verse
}
const cm = (mm) => (mm / 10).toFixed(1).replace(/\.0$/, "") + " cm";

/* ---------- #022 · editar la cota sobre el modelo ---------- */
function editarCota(idx, el) {
  const c = S.cotasGeo?.[idx];
  if (!c || el.querySelector("input")) return;
  const antes = (c.valor / 10);
  el.classList.add("editando");
  el.innerHTML = `<input type="number" step="0.1" value="${antes}"><span class="u">cm</span>`;
  const inp = el.querySelector("input");
  inp.focus();
  inp.select();

  let cerrado = false;
  const cerrar = (aplicar) => {
    if (cerrado) return;
    cerrado = true;
    const v = parseFloat(inp.value);
    el.classList.remove("editando");
    el.innerHTML = "";
    if (aplicar && isFinite(v) && v > 0 && Math.abs(v - antes) > 0.001) {
      aplicarCota(c, Math.round(v * 100) / 10);      // cm → mm, a una décima
    } else {
      actualizarEtiquetasCota();
    }
  };
  inp.onkeydown = (e) => {
    e.stopPropagation();
    if (e.key === "Enter") cerrar(true);
    else if (e.key === "Escape") cerrar(false);
  };
  inp.onblur = () => cerrar(true);
}

/** Escribe el valor en el modelo y deja que todo lo demás se reacomode. */
function aplicarCota(c, mm) {
  const g = S.proyecto.gabinetes[S.sel];
  if (!g) return;
  if (c.campo === "ancho") g.ancho = mm;
  else if (c.campo === "prof") g.prof = mm;
  else if (c.campo === "alto") {
    // se respeta el candado de alturas (#001): el campo derivado se recalcula
    g.alto = mm;
    const a = resolverAlturas(g);
    g.alto_cuerpo = a.cuerpo;
    if (llevaZoclo(g)) g.altura_zoclo = a.zoclo;
  } else if (c.campo === "frente") {
    const f = g.frentes[c.i];
    if (!f) return;
    f.alto = mm;                       // los demás frentes reparten el sobrante
  } else if (c.campo === "entrepano") {
    const ent = (S.solidos[S.sel] || {}).entrepanos || {};
    const lista = (g.alturas_entrepanos && g.alturas_entrepanos.length
      ? g.alturas_entrepanos.slice() : (ent.alturas || []).slice());
    while (lista.length < g.n_entrepanos) lista.push(0);
    lista[c.i] = mm;
    g.alturas_entrepanos = lista;
  }
  pintarGabinete();
  pintarLista();
  recalcular();
  estado(T2("cota aplicada: %s %s mm", c.campo, mm));
}


function actualizarEtiquetasCota() {
  if (!S.cotasGeo) return;
  const cap = $("cotas3d");
  // #088 — el tamaño viene del ResizeObserver; sólo si no hay, se mide
  if (!tamCotas.w) { tamCotas.w = cap.clientWidth; tamCotas.h = cap.clientHeight; }
  const w = tamCotas.w, hh = tamCotas.h;
  const etiquetas = cap.children;
  S.cotasGeo.forEach((c, i) => {
    const el = etiquetas[i];
    if (!el) return;
    const p = new THREE.Vector3((c.a[0] + c.b[0]) / 2, (c.a[1] + c.b[1]) / 2,
                                (c.a[2] + c.b[2]) / 2).project(camara);
    if (p.z > 1) { el.style.display = "none"; return; }
    el.style.display = "block";
    // #022 — mientras se edita NO se reescribe: borraría el campo en cuanto
    // aparece. #088: y sólo se escribe si el texto cambió.
    if (!el.classList.contains("editando") && el.textContent !== c.t) el.textContent = c.t;
    el.style.left = ((p.x * 0.5 + 0.5) * w) + "px";
    el.style.top = ((-p.y * 0.5 + 0.5) * hh) + "px";
  });
}

/* ---- órbita mínima (sin dependencias) ---- */
function orbita(el, cam, onCambio) {
  const objetivo = new THREE.Vector3();
  let arrastra = false, pan = false, px = 0, py = 0;
  const esf = { r: 4000, th: 0.9, fi: 1.0 };
  const sinc = () => {
    const v = new THREE.Vector3().subVectors(cam.position, objetivo);
    esf.r = v.length();
    esf.th = Math.atan2(v.x, v.z);
    esf.fi = Math.acos(Math.min(1, Math.max(-1, v.y / esf.r)));
  };
  const aplica = () => {
    const s = Math.sin(esf.fi);
    cam.position.set(objetivo.x + esf.r * s * Math.sin(esf.th),
                     objetivo.y + esf.r * Math.cos(esf.fi),
                     objetivo.z + esf.r * s * Math.cos(esf.th));
    cam.lookAt(objetivo);
    onCambio();
  };
  el.addEventListener("pointerdown", (e) => {
    if (empezarArrastreMueble(e)) return;      // #004: el mueble gana al orbitar
    sinc(); arrastra = true; pan = e.shiftKey || e.button === 1;
    px = e.clientX; py = e.clientY; el.setPointerCapture(e.pointerId);
  });
  el.addEventListener("pointerup", (e) => { arrastra = false; el.releasePointerCapture(e.pointerId); });
  el.addEventListener("pointermove", (e) => {
    if (!arrastra) return;
    const dx = e.clientX - px, dy = e.clientY - py;
    px = e.clientX; py = e.clientY;
    if (pan) {
      const k = esf.r * 0.0016;
      const der = new THREE.Vector3().setFromMatrixColumn(cam.matrix, 0);
      const arr = new THREE.Vector3().setFromMatrixColumn(cam.matrix, 1);
      objetivo.addScaledVector(der, -dx * k).addScaledVector(arr, dy * k);
    } else {
      esf.th -= dx * 0.006;
      esf.fi = Math.min(Math.PI - 0.05, Math.max(0.05, esf.fi - dy * 0.006));
    }
    aplica();
  });
  el.addEventListener("wheel", (e) => {
    e.preventDefault(); sinc();
    esf.r = Math.min(30000, Math.max(200, esf.r * (e.deltaY > 0 ? 1.12 : 0.89)));
    aplica();
  }, { passive: false });
  return { objetivo, aplica, sinc };
}


/* ============================================================ #015 · no perder el trabajo */
const MAX_HIST = 60;

/** Marca el proyecto como modificado y empuja un punto de retorno. */
function marcarSucio(guardarPunto = true) {
  if (S.aplicandoHistorial) return;
  S.sucio = true;
  pintarTitulo();
  if (guardarPunto) empujarHistorial();
  programarAutoguardado();
}

function pintarTitulo() {
  const n = S.proyecto.nombre || "Cocina sin nombre";
  document.title = (S.sucio ? "• " : "") + n + " — nest101";
  const p = $("puntoSucio");
  if (p) p.style.visibility = S.sucio ? "visible" : "hidden";
  // el nombre y el punto de «sin guardar» también se ven en la pestaña
  if (typeof refrescarPestana === "function") refrescarPestana();
}


/* ============================================================ #036 · pestañas
   Cada pestaña es un mueble: un archivo .t101x abierto, con su proyecto, su
   selección, su historial de deshacer y su marca de «sin guardar».

   Se eligió NO reescribir toda la app para que lea de una lista de documentos.
   En vez de eso, `S` sigue siendo el mueble en el que se está trabajando —las
   noventa y tantas líneas que dicen `S.proyecto` siguen igual de simples— y al
   cambiar de pestaña se guarda el estado en su cajón y se saca el de la otra.
   El riesgo de un cambio así es olvidarse de un campo: por eso la lista de qué
   se guarda está escrita una sola vez, aquí abajo, y no repartida por el código. */
const DE_LA_PESTANA = ["proyecto", "sel", "sub", "rutaActual", "sucio", "abierto",
                       "pila", "pilaPos", "solidos", "cubiertas3d"];

const P = { docs: [], activa: -1 };

function docVacio(nombre) {
  return {
    proyecto: { nombre: nombre || "Mueble sin nombre", cliente: "",
                catalogo: JSON.parse(JSON.stringify(DEF.catalogo || [])),
                estandar: JSON.parse(JSON.stringify(DEF.estandar || null)),
                gabinetes: [] },
    sel: -1, sub: null, rutaActual: null, sucio: false, abierto: true,
    pila: [], pilaPos: -1, solidos: [], cubiertas3d: [],
  };
}

function guardarPestana() {
  if (P.activa < 0 || !P.docs[P.activa]) return;
  const d = P.docs[P.activa];
  DE_LA_PESTANA.forEach((k) => { d[k] = S[k]; });
}

function ponerPestana(i) {
  const d = P.docs[i];
  if (!d) return;
  P.activa = i;
  DE_LA_PESTANA.forEach((k) => { S[k] = d[k]; });
  S.firma3D = null;                     // el 3D es de otro mueble: se rehace
  $("pNombre").value = S.proyecto.nombre || "";
  $("pCliente").value = S.proyecto.cliente || "";
  pintarMateriales(); pintarEstandar(); pintarLista(); pintarGabinete();
  pintarHistorialBotones();
  recalcular(false);
  pintarPestanas(); pintarTitulo();
}

function irAPestana(i) {
  if (i === P.activa || !P.docs[i]) return;
  guardarPestana();
  ponerPestana(i);
}

/** Abre un mueble en una pestaña nueva y se cambia a ella. */
function abrirEnPestana(proyecto, ruta) {
  guardarPestana();
  const d = docVacio(proyecto?.nombre);
  if (proyecto) d.proyecto = proyecto;
  d.rutaActual = ruta ?? null;
  d.sel = (d.proyecto.gabinetes || []).length ? 0 : -1;
  d.pila = [JSON.stringify(d.proyecto)];
  d.pilaPos = 0;
  P.docs.push(d);
  ponerPestana(P.docs.length - 1);
  return d;
}

/** Cierra una pestaña. Si tiene trabajo sin guardar, pregunta primero. */
async function cerrarPestana(i) {
  const d = P.docs[i];
  if (!d) return false;
  if (d.sucio) {
    if (i !== P.activa) irAPestana(i);
    const r = await window.despz?.preguntarGuardar?.(
      d.proyecto.nombre || "el mueble", "Cerrar");
    if (r === "cancelar") return false;
    if (r === "guardar") { await guardar(); if (S.sucio) return false; }
  }
  P.docs.splice(i, 1);
  if (!P.docs.length) {                 // no queda nada: a la pantalla de inicio
    P.activa = -1;
    S.abierto = false;
    S.proyecto = docVacio().proyecto;
    S.sel = -1;
    pintarLista(); pintarGabinete(); pintarPestanas();
    mostrarInicio();
    return true;
  }
  P.activa = -1;                        // se fuerza el repintado del que quede
  ponerPestana(Math.min(i, P.docs.length - 1));
  return true;
}

function pintarPestanas() {
  const barra = $("pestanas"), tiras = $("tiras");
  if (!barra || !tiras) return;
  // con un solo mueble la barra no aporta nada y quita alto al 3D
  barra.classList.toggle("uno", P.docs.length <= 1);
  tiras.innerHTML = P.docs.map((d, i) => {
    const n = d.proyecto?.nombre || "sin nombre";
    return `<button class="pest${i === P.activa ? " act" : ""}${d.sucio ? " sucia" : ""}"
              data-i="${i}" title="${esc(d.rutaActual || n)}">
              <span class="nom">${esc(n)}</span><span class="pt">•</span>
              <span class="x" data-x="${i}">×</span></button>`;
  }).join("");
  tiras.querySelectorAll(".pest").forEach((b) => {
    b.onclick = (e) => {
      const x = e.target.closest("[data-x]");
      if (x) { e.stopPropagation(); cerrarPestana(+x.dataset.x); return; }
      irAPestana(+b.dataset.i);
    };
  });
}

/** El estado de la pestaña activa cambió (nombre, sucio): sólo se repinta. */
function refrescarPestana() {
  if (P.activa < 0) return;
  guardarPestana();
  pintarPestanas();
}

/* ---------- historial ---------- */
let tHist = null;
function empujarHistorial() {
  clearTimeout(tHist);
  tHist = setTimeout(() => {
    const snap = JSON.stringify(S.proyecto);
    if (S.pila[S.pilaPos] === snap) return;
    S.pila = S.pila.slice(0, S.pilaPos + 1);
    S.pila.push(snap);
    if (S.pila.length > MAX_HIST) S.pila.shift();
    S.pilaPos = S.pila.length - 1;
    pintarHistorialBotones();
  }, 400);
}

function reiniciarHistorial() {
  S.pila = [JSON.stringify(S.proyecto)];
  S.pilaPos = 0;
  pintarHistorialBotones();
}

function pintarHistorialBotones() {
  const d = $("bDeshacer"), r = $("bRehacer");
  if (d) d.disabled = S.pilaPos <= 0;
  if (r) r.disabled = S.pilaPos >= S.pila.length - 1;
}

function irAHistorial(paso) {
  const destino = S.pilaPos + paso;
  if (destino < 0 || destino >= S.pila.length) return;
  S.pilaPos = destino;
  S.aplicandoHistorial = true;
  S.proyecto = JSON.parse(S.pila[destino]);
  if (S.sel >= S.proyecto.gabinetes.length) S.sel = S.proyecto.gabinetes.length - 1;
  $("pNombre").value = S.proyecto.nombre || "";
  $("pCliente").value = S.proyecto.cliente || "";
  pintarMateriales(); pintarEstandar(); pintarLista(); pintarGabinete();
  S.firma3D = null;                       // forzar reconstrucción del 3D
  recalcular();
  S.aplicandoHistorial = false;
  S.sucio = true;
  pintarTitulo(); pintarHistorialBotones();
  estado(paso < 0 ? "deshecho" : "rehecho");
}

/* ---------- autoguardado ---------- */
let tAuto = null;
function programarAutoguardado() {
  clearTimeout(tAuto);
  tAuto = setTimeout(autoguardar, 4000);
}

function autoguardar() {
  try {
    localStorage.setItem(CLAVE_REC, JSON.stringify({
      cuando: Date.now(),
      ruta: S.rutaActual,
      proyecto: S.proyecto,
    }));
  } catch { /* si no hay espacio, seguimos sin bloquear al usuario */ }
}

function limpiarRecuperacion() {
  try { localStorage.removeItem(CLAVE_REC); } catch {}
}

/** Al arrancar: si quedó trabajo sin guardar de una sesión anterior, ofrecerlo. */
function revisarRecuperacion() {
  let d = null;
  try { d = JSON.parse(localStorage.getItem(CLAVE_REC) || "null"); } catch {}
  if (!d || !d.proyecto || !(d.proyecto.gabinetes || []).length) return false;
  const cuando = new Date(d.cuando || Date.now());
  const hora = cuando.toLocaleString("es-MX",
    { day: "2-digit", month: "short", hour: "2-digit", minute: "2-digit" });
  modal("Trabajo sin guardar",
    `<div class="aviso">Se encontró un proyecto que no alcanzó a guardarse.</div>
     <p style="font-size:13px;line-height:1.7">
       <b>${esc(d.proyecto.nombre || "Sin nombre")}</b><br>
       ${(d.proyecto.gabinetes || []).length} gabinete(s) · ${esc(hora)}
       ${d.ruta ? `<br><span data-sin-traducir
           style="color:var(--txt3);font-size:11.5px">${esc(d.ruta)}</span>` : ""}
     </p>`,
    () => {
      S.proyecto = d.proyecto;
      S.rutaActual = d.ruta || null;
      S.sel = S.proyecto.gabinetes.length ? 0 : -1;
      $("pNombre").value = S.proyecto.nombre || "";
      $("pCliente").value = S.proyecto.cliente || "";
      pintarMateriales(); pintarEstandar(); pintarLista(); pintarGabinete();
      reiniciarHistorial(); recalcular();
      S.sucio = true; pintarTitulo();
      ocultarInicio();                          // #018
      estado("trabajo recuperado");
    }, "Recuperar", () => { limpiarRecuperacion(); mostrarInicio(); }, "Descartar");
  return true;
}

/* ---------- salida segura ---------- */
async function confirmarDescartar(accion = "continuar") {
  if (!S.sucio) return true;
  if (window.despz?.preguntarGuardar) {
    const r = await window.despz.preguntarGuardar(S.proyecto.nombre || "el proyecto", accion);
    if (r === "cancelar") return false;
    if (r === "guardar") { await guardar(); return !S.sucio; }
    return true;
  }
  return confirm(`«${S.proyecto.nombre}» tiene cambios sin guardar.\n\n¿${accion} de todos modos?`);
}

/* ============================================================ #018 · pantalla de inicio */
/* ¿Hay algo abierto a lo que volver?
   Antes esto se contestaba contando gabinetes, y funcionaba de casualidad porque
   un proyecto nuevo siempre traía uno. Con proyectos que arrancan vacíos, contar
   gabinetes decía «no hay nada» y la pantalla de inicio no se quitaba nunca. */
function hayProyecto() { return !!S.abierto; }

function mostrarInicio() {
  pintarRecientes();
  const el = $("inicio");
  el.classList.toggle("hayProyecto", hayProyecto());
  el.classList.add("on");
}

function ocultarInicio() {
  // sin nada abierto no hay a dónde volver: la pantalla se queda
  if (!hayProyecto()) return;
  $("inicio").classList.remove("on");
}

function leerRecientes() {
  try {
    const d = JSON.parse(localStorage.getItem(CLAVE_RECIENTES) || "[]");
    return Array.isArray(d) ? d.filter((r) => r && r.ruta) : [];
  } catch { return []; }
}

function escribirRecientes(lista) {
  try { localStorage.setItem(CLAVE_RECIENTES, JSON.stringify(lista.slice(0, MAX_RECIENTES))); }
  catch { /* sin espacio: la lista es una comodidad, no se bloquea nada */ }
}

/** Un proyecto que se abrió o se guardó sube al principio de la lista. */
function recordarReciente(ruta, proy) {
  if (!ruta) return;
  const lista = leerRecientes().filter((r) => r.ruta !== ruta);
  lista.unshift({
    ruta,
    nombre: (proy && proy.nombre) || "Sin nombre",
    cliente: (proy && proy.cliente) || "",
    n: ((proy && proy.gabinetes) || []).length,
    cuando: Date.now(),
  });
  escribirRecientes(lista);
}

function olvidarReciente(ruta) {
  escribirRecientes(leerRecientes().filter((r) => r.ruta !== ruta));
  pintarRecientes();
}

const FECHA_CORTA = (t) => new Date(t || Date.now()).toLocaleDateString("es-MX",
  { day: "2-digit", month: "short" });

function pintarRecientes() {
  const lista = leerRecientes();
  const c = $("iRecientes");
  $("iOlvidar").style.visibility = lista.length ? "visible" : "hidden";
  if (!lista.length) {
    c.innerHTML = `<div class="vacio">Todavía no hay proyectos.<br>
      Los que guardes aparecerán aquí.</div>`;
    return;
  }
  c.innerHTML = lista.map((r, i) => `
    <button class="rec" data-i="${i}" title="${esc(r.ruta)}">
      <div class="n1">${esc(r.nombre)}<span class="cuando">${
        r.n ? r.n + " gab · " : ""}${esc(FECHA_CORTA(r.cuando))}</span></div>
      <div class="n2">${esc(r.ruta)}</div>
    </button>`).join("");
  c.querySelectorAll(".rec").forEach((b) =>
    b.onclick = () => abrirReciente(lista[+b.dataset.i], b));
}

async function abrirReciente(r, boton) {
  if (!r) return;
  if (!await confirmarDescartar("Abrir «" + r.nombre + "»")) return;
  try {
    let d = null;
    if (window.despz?.leerArchivo) {
      const x = await window.despz.leerArchivo(r.ruta);
      if (!x || x.error) throw new Error(x ? x.error : "no se pudo leer");
      d = JSON.parse(x.contenido);
    } else {
      d = await api("/api/abrir?ruta=" + encodeURIComponent(r.ruta));
    }
    cargarProyecto(d, r.ruta);
    estado("proyecto abierto");
  } catch (e) {
    // el archivo se movió o se borró: se marca y se ofrece quitarlo de la lista
    boton?.classList.add("perdido");
    modal("No se encontró el proyecto",
      `<div class="aviso">${esc(r.ruta)}</div>
       <p style="font-size:12.5px;color:var(--txt2)">Puede que se haya movido, renombrado
       o borrado. ${esc(String(e.message).slice(0, 120))}</p>`,
      () => olvidarReciente(r.ruta), "Quitar de recientes");
  }
}

/* ============================================================ archivo */
/* #036 — «Nuevo» ya no tira lo que había: abre otra pestaña. Antes preguntaba
   si querías descartar tu trabajo porque no tenía dónde ponerlo; ahora sí. */
async function nuevo() {
  const d = abrirEnPestana(null, null);
  d.proyecto.nombre = "Mueble sin nombre";
  S.proyecto.nombre = d.proyecto.nombre;
  $("pNombre").value = S.proyecto.nombre;
  $("pCliente").value = "";
  limpiarRecuperacion();
  await arrancarVacio();
  estado("mueble nuevo");
}

/** Carga un proyecto ya parseado (de archivo, recuperación o doble clic). */
function cargarProyecto(d, ruta) {
  // #036 — cada mueble que se abre entra en su propia pestaña. Si el que está
  // abierto está vacío y sin tocar, se reusa: nadie quiere una pestaña en
  // blanco colgando al lado de la que sí tiene trabajo.
  const vacia = P.activa >= 0 && !S.sucio && !(S.proyecto.gabinetes || []).length;
  if (P.activa < 0 || !vacia) abrirEnPestana(null, null);
  S.proyecto = d;
  S.abierto = true;
  if (ruta !== undefined) S.rutaActual = ruta;
  $("pNombre").value = d.nombre || "";
  $("pCliente").value = d.cliente || "";
  S.sel = (d.gabinetes || []).length ? 0 : -1;
  S.firma3D = null;
  pintarMateriales(); pintarEstandar(); pintarLista(); pintarGabinete();
  recalcular(false);
  S.sucio = false;
  limpiarRecuperacion();
  reiniciarHistorial();
  pintarTitulo();
  recordarReciente(S.rutaActual, d);      // #018
  fundirCatalogo(d.catalogo);             // #037 — lo que traiga y no tengamos
  ocultarInicio();
}

async function guardar() {
  try {
    let ruta = null;
    if (window.despz?.guardarArchivo) {
      // #038 — con un proyecto abierto, el mueble nuevo se ofrece en SU carpeta
      const sugerido = (!S.rutaActual && PROY.carpeta)
        ? PROY.carpeta + "/" + S.proyecto.nombre + ".t101x"
        : S.proyecto.nombre + ".t101x";
      ruta = await window.despz.guardarArchivo(sugerido,
        JSON.stringify(S.proyecto, null, 2), S.rutaActual);
      if (!ruta) return;                       // el usuario canceló
    } else {
      const r = await api("/api/guardar", { method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ proyecto: S.proyecto }) });
      ruta = r.ruta;
    }
    S.rutaActual = ruta;
    S.sucio = false;                           // #015
    limpiarRecuperacion();
    recordarReciente(ruta, S.proyecto);        // #018
    pintarTitulo();
    estado(T2("guardado: %s", ruta));
  } catch (e) { estado(T2("error al guardar: %s", e.message), true); }
}

async function abrir() {
  if (!await confirmarDescartar("Abrir otro proyecto")) return;   // #015
  try {
    let d = null;
    if (window.despz?.abrirArchivo) {
      const r = await window.despz.abrirArchivo();
      if (!r) return;
      d = JSON.parse(r.contenido !== undefined ? r.contenido : r);
      S.rutaActual = r.ruta || null;
    } else {
      const ruta = prompt("Ruta del archivo .t101x:");
      if (!ruta) return;
      d = await api("/api/abrir?ruta=" + encodeURIComponent(ruta));
    }
    cargarProyecto(d);
    estado("proyecto abierto");
  } catch (e) { estado(T2("error al abrir: %s", e.message), true); }
}

async function exportar() {
  if (!S.proyecto.gabinetes.length) { estado("no hay gabinetes", true); return; }
  let carpeta = null;
  if (window.despz?.elegirCarpeta) {
    carpeta = await window.despz.elegirCarpeta();
    if (!carpeta) return;
  }
  estado("exportando…");
  try {
    const r = await api("/api/exportar", { method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ proyecto: S.proyecto, carpeta }) });
    modal("Exportación lista", `
      <div class="aviso">Archivos generados en:<br><b style="color:var(--txt)">${esc(r.carpeta)}</b></div>
      <ul style="margin-left:18px;font-size:12px;line-height:1.9">
        ${r.archivos.map((a) => `<li>${esc(a)}</li>`).join("")}</ul>`,
      window.despz?.abrirCarpeta ? () => window.despz.abrirCarpeta(r.carpeta) : null,
      window.despz?.abrirCarpeta ? "Abrir carpeta" : null);
    estado("exportado");
  } catch (e) {
    if (e.medidas) {
      problema(e.message);
      modal("No se puede exportar",
        `<div class="aviso">${esc(e.message)}</div>
         <p style="font-size:12.5px;color:var(--txt2)">Se detuvo la exportación a
         propósito: es preferible corregir la medida a mandar piezas imposibles
         al corte.</p>`);
      estado("exportación detenida", true);
    } else {
      estado(T2("error al exportar: %s", e.message), true);
    }
  }
}




/* ============================================================ #091 · Ayuda ▾
   Mike: «copia las funciones pertinentes para nest101 del menú de ayuda de
   draw101». Son tres, y ninguna es del mueble: actualizaciones, avisos de
   Taller 101 y licencias de terceros.

   El punto azul junto a «Ayuda» es lo único que interrumpe: un aviso que se
   abre solo en cada arranque deja de leerse a la tercera. */
function menuAyuda(abrir) {
  const d = $("dAyuda");
  d.hidden = abrir === undefined ? !d.hidden : !abrir;
  if (!d.hidden) {
    setTimeout(() => document.addEventListener("mousedown", (e) => {
      if (!$("mAyuda").contains(e.target)) d.hidden = true;
    }, { once: true }), 0);
  }
}

async function cargarAvisos(forzar = false) {
  try { S.avisos = await api("/api/avisos" + (forzar ? "?forzar=true" : "")); }
  catch { S.avisos = { avisos: [], sin_leer: 0, asoman: [] }; }
  const n = S.avisos.sin_leer || 0;
  $("pAvisos").hidden = !n;
  $("nAvisos").textContent = n ? String(n) : "";
  // Los importantes sin leer se abren solos, UNA vez. Los demás esperan.
  if ((S.avisos.asoman || []).length) verAvisos();
  return S.avisos;
}

function verAvisos() {
  const lista = (S.avisos && S.avisos.avisos) || [];
  const cuerpo = lista.length
    ? `<div class="avisos">${lista.map((a) => `
        <div class="aviso${a.leido ? "" : " nuevo"}">
          <div class="f" data-sin-traducir>${esc(a.fecha)}</div>
          <div class="t"><span data-sin-traducir>${esc(a.titulo)}</span>
            ${a.nivel === "importante" ? `<span class="imp">importante</span>` : ""}</div>
          <div class="x" data-sin-traducir>${esc(a.texto)}</div>
        </div>`).join("")}</div>`
    : `<div class="vacio">No hay avisos.</div>`;
  modal("Avisos", cuerpo, null, null, null, "Cerrar");
  // Se marcan leídos al VERLOS, no al cerrarlos: si alguien cierra con Esc,
  // igual los leyó, y volvérselos a enseñar mañana es ruido.
  const ids = lista.filter((a) => !a.leido).map((a) => a.id);
  if (ids.length) {
    api("/api/avisos/leidos", {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ ids }),
    }).then(() => { lista.forEach((a) => a.leido = true);
                    S.avisos.sin_leer = 0; S.avisos.asoman = [];
                    $("pAvisos").hidden = true; $("nAvisos").textContent = ""; })
      .catch(() => {});
  }
}

async function verLicencias() {
  let d = { componentes: [], total: 0 };
  try { d = await api("/api/licencias"); } catch {}
  const filas = d.componentes.map((c) => `
    <tr><td class="n">${esc(c.nombre)}</td>
        <td class="v">${esc(c.version)}</td>
        <td class="l">${esc(c.licencia)}
          ${c.texto ? `<details><summary>ver el texto</summary>
            <pre>${esc(c.texto.slice(0, 4000))}</pre></details>` : ""}</td></tr>`).join("");
  modal("Licencias de terceros",
    // El total va aparte, sin traducir. Si se interpola dentro de la frase, la
    // plantilla de números convierte también el «101» de nest101 y la frase
    // deja de existir en el diccionario: se quedaba en español.
    `<div style="font-size:11px;color:var(--txt3);margin-bottom:8px">
       <span data-sin-traducir>${d.total}</span>
       componentes ajenos viajan dentro de nest101. La lista se
       genera de lo que de verdad se empaqueta, no de una lista escrita a mano.
     </div>
     <div class="lic"><table>${filas}</table></div>`,
    null, null, null, "Cerrar");
}

/* ============================================================ #087 · actualizar
   Mike: «necesito que haya un link de actualización de aplicación… que se pueda
   descargar la última versión desde el programa».

   El programa **no se actualiza solo**: avisa y enseña el enlace. Un instalador
   de 180 MB bajándose sin permiso, con la máquina a media exportación, es una
   interrupción y no un servicio.

   Y si no hay internet no pasa nada: el taller trabaja sin red la mitad del
   tiempo, así que un fallo de red se queda callado. */
async function revisarActualizacion(forzar = false) {
  // #092 — Al arrancar se usa `/auto`, que respeta el interruptor y la versión
  // ignorada y no pregunta más de una vez al día. Cuando el usuario lo pide
  // desde Ayuda ▾ se usa la revisión directa: si te tomaste la molestia de
  // pedirlo, se pregunta aunque hayas revisado hace diez minutos.
  try {
    S.actualizacion = await api(forzar ? "/api/actualizacion?forzar=true"
                                       : "/api/actualizacion/auto");
  } catch { S.actualizacion = null; }
  pintarActualizacion();
}

function pintarActualizacion() {
  const a = S.actualizacion;
  const b = $("bActualizar");
  if (!b) return;
  b.hidden = !(a && a.hay);
  if (a && a.hay) {
    b.textContent = T2("Actualizar a %s", a.version);
    b.title = (a.notas || "") + (a.fecha ? `  ·  ${a.fecha}` : "");
    b.onclick = () => abrirConfig();
  }
}

/** #092 — El instalador ya está bajado y comprobado: se ofrece correrlo.
    Se pregunta SIEMPRE antes: correr un instalador cierra el programa, y
    hacerlo sin avisar a media exportación sería imperdonable. */
function instalarAhora(archivo, version) {
  modal(T2("Actualizar a %s", version),
    `<div class="aviso">El instalador ya está bajado y su huella cuadra.</div>
     <div style="font-size:12px;color:var(--txt2);line-height:1.6">
       Al instalar se cierra nest101. Se instala encima de la versión que
       tienes: tus proyectos, tu catálogo y tu carpeta de taller no se tocan.
     </div>
     <div style="font-size:11px;color:var(--txt3);margin-top:8px" data-sin-traducir>
       ${esc(archivo)}</div>`,
    () => {
      if (window.t101?.instalar) window.t101.instalar(archivo);
      else abrirEnlace("file:///" + archivo);
    }, "Instalar ahora", () => {}, "Ahora no");
}

/** Abre el enlace en el navegador del equipo, no dentro de la app. */
function abrirEnlace(url) {
  if (window.t101?.abrirEnlace) { window.t101.abrirEnlace(url); return; }
  window.open(url, "_blank", "noopener");     // en navegador, durante el desarrollo
}

/* ============================================================ #085 · configuración
   La caja de Configuración general del taller.

   Mike: «ya genera la caja de configuración general del taller usuario, a lo
   mejor arriba en el menú, que diga configuración general (ahí mismo hay que
   poner la opción de idioma)».

   Es lo del TALLER, no lo de esta cocina. Los parámetros de construcción
   —holguras, kerf, alturas— siguen en la pestaña Estándar, que es donde se
   editan mientras se dibuja. Aquí va lo que se toca una vez y vale para todos
   los proyectos: idioma, logotipo del papel y dónde vive todo. */
/** #092 — La línea de estado de las actualizaciones, en HTML.
    El número de versión va en su propio `<span data-sin-traducir>`: si se
    interpola dentro de la frase, la frase deja de existir en el diccionario
    —«Estás en la última (0.15.4)» no es ninguna clave— y se queda en español
    aunque el taller esté en inglés. Se separa el texto del número, y cada uno
    hace lo suyo. La misma función la usan el primer pintado y «Buscar ahora»,
    para que no se puedan desincronizar. */
function lineaAct(d) {
  d = d || {};
  if (d.hay) {
    return `<b style="color:var(--acc)">Hay versión nueva</b>` +
           ` <b style="color:var(--acc)" data-sin-traducir>${esc(d.version || "")}</b>`;
  }
  if (d.error) return "No se pudo revisar (sin internet)";
  const ver = d.instalada || "";
  return "Estás en la última" +
    (ver ? ` <span data-sin-traducir>(${esc(ver)})</span>` : "");
}

async function abrirConfig() {
  let idi = { activo: "es", disponibles: { es: "Español", en: "English" } };
  let logo = { propio: false, nombre: "", carpeta: "" };
  try { idi = await api("/api/idioma"); } catch {}
  try { logo = await api("/api/logo"); } catch {}
  const a = S.actualizacion || {};
  const ops = Object.entries(idi.disponibles || {}).map(([c, n]) =>
    `<option value="${esc(c)}"${c === idi.activo ? " selected" : ""}>${esc(n)}</option>`).join("");
  modal("Configuración general", `
    <div class="fila"><label>Idioma</label>
      <select id="cIdioma">${ops}</select></div>
    <div style="font-size:11px;color:var(--txt3);margin:-4px 0 12px">
      Alcanza la pantalla <b>y el papel</b>: planos, fichas de corte y Excel
      salen en el idioma que escojas. Es del taller, no del proyecto.</div>

    <div class="fila"><label>Logotipo del papel</label>
      <span id="cLogoNom" data-sin-traducir>${esc(logo.propio ? logo.nombre : "nest101")}</span></div>
    <div style="display:flex;gap:6px;margin:-4px 0 12px">
      <button class="gh" id="cLogoCambiar">Cambiar logo…</button>
      <button class="gh" id="cLogoQuitar"${logo.propio ? "" : " disabled"}>Quitar</button>
    </div>
    <div style="font-size:11px;color:var(--txt3);margin:-8px 0 12px">
      El que firma planos y fichas. También se cambia con clic derecho sobre el
      logotipo de la barra.</div>

    <div class="fila"><label>Actualizaciones</label>
      <span id="cActNota" style="font-size:11px;color:var(--txt2)">${lineaAct(a)}</span></div>
    <div style="display:flex;gap:6px;margin:-4px 0 8px;flex-wrap:wrap">
      <button class="gh" id="cActRevisar">Buscar ahora</button>
      <button class="${a.hay ? "pri" : "gh"}" id="cActBajar">Descargar la última versión</button>
      ${a.hay ? `<button class="gh" id="cActIgnorar">Ignorar esta versión</button>` : ""}
    </div>
    <label style="display:flex;gap:7px;align-items:center;font-size:12px;margin:0 0 8px">
      <input type="checkbox" id="cActAuto"${a.apagada ? "" : " checked"}>
      Revisar al arrancar y una vez al día</label>
    <div style="font-size:11px;color:var(--txt3);margin:-8px 0 12px">
      Se abre en tu navegador y se instala encima de la que tienes. Tus proyectos
      y tu carpeta de taller no se tocan.</div>
    ${a.hay && a.notas ? `<div style="font-size:11px;color:var(--txt2);margin:-6px 0 12px">
      <div style="color:var(--txt3);margin-bottom:3px">Qué trae</div>
      <div data-sin-traducir style="white-space:pre-wrap;max-height:120px;overflow:auto;
           border-left:2px solid var(--bor);padding-left:8px;line-height:1.5">${esc(
             String(a.notas).slice(0, 1200))}</div></div>` : ""}

    <div class="fila"><label>Carpeta del taller</label>
      <span style="font-size:11px;color:var(--txt2)" data-sin-traducir>${esc(logo.carpeta || "")}</span></div>
    <div style="font-size:11px;color:var(--txt3)">
      Ahí viven tu catálogo de materiales, tus módulos, tu logotipo y tu llave.
      Las actualizaciones no la tocan.</div>`,
    async () => {
      const cod = $("cIdioma")?.value;
      if (!cod || cod === idi.activo) return;
      try {
        await api("/api/perfil", {
          method: "PUT", headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ idioma: cod }),
        });
        await ponerIdioma(cod);
        // Volver al español no se puede hacer sustituyendo texto: el original
        // ya se perdió del DOM. Se recarga, que además es instantáneo porque
        // todo es local.
        if (cod === "es") location.reload();
        estado(T2("idioma: %s", idi.disponibles[cod] || cod));
      } catch (e) { estado(T2("no se pudo cambiar el idioma: %s", e.message), true); }
    }, "Guardar");
  setTimeout(() => {
    const b = $("cLogoCambiar"), q = $("cLogoQuitar");
    if (b) b.onclick = () => { $("modal").classList.remove("on"); elegirLogo(); };
    if (q) q.onclick = async () => { $("modal").classList.remove("on"); await quitarLogo(); };
    const bajar = $("cActBajar"), rev = $("cActRevisar");
    const auto = $("cActAuto"), ign = $("cActIgnorar");
    if (auto) auto.onchange = () => api("/api/actualizacion/auto", {
      method: "PUT", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ revisar: auto.checked }),
    }).then(() => estado(auto.checked ? "revisión automática encendida"
                                      : "revisión automática apagada"))
      .catch(() => estado("no se pudo guardar", true));
    if (ign) ign.onclick = async () => {
      await api("/api/actualizacion/auto", {
        method: "PUT", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ ignorada: a.version }),
      }).catch(() => {});
      $("modal").classList.remove("on");
      await revisarActualizacion();
      estado(T2("la %s deja de avisar; las siguientes sí", a.version));
    };
    // #092 — bajar, comprobar la huella y ofrecer instalar. El navegador sigue
    // siendo la salida si algo falla: nunca se queda sin manera de bajarlo.
    if (bajar) bajar.onclick = async () => {
      if (!a.hay) { abrirEnlace(a.url || ""); return; }
      const n = $("cActNota");
      if (n) n.textContent = "Bajando el instalador… (unos 180 MB)";
      bajar.disabled = true;
      try {
        const r = await api("/api/actualizacion/descargar", { method: "POST" });
        $("modal").classList.remove("on");
        instalarAhora(r.archivo, r.version);
      } catch (e) {
        if (n) n.textContent = "No se pudo bajar. Se abre en el navegador.";
        abrirEnlace(a.url || "");
      } finally { bajar.disabled = false; }
    };
    if (rev) rev.onclick = async () => {
      const n = $("cActNota");
      if (n) n.textContent = "Revisando…";
      await revisarActualizacion(true);
      const d = S.actualizacion || {};
      // innerHTML, no textContent: la versión viaja en su propio span sin
      // traducir. El observador de idioma vuelve a pasar por aquí solo.
      if (n) n.innerHTML = lineaAct(d);
    };
  }, 20);
}

function modal(titulo, html, onOk, okTxt, onAlt, altTxt) {
  $("mTit").textContent = titulo;
  $("mCuerpo").innerHTML = html;
  $("mOk").style.display = onOk ? "" : "none";
  $("mOk").textContent = okTxt || "Aceptar";
  $("mOk").onclick = () => { $("modal").classList.remove("on"); onOk?.(); };
  const alt = $("mCancel");
  alt.textContent = altTxt || "Cerrar";
  alt.onclick = () => { $("modal").classList.remove("on"); onAlt?.(); };
  $("modal").classList.add("on");
}

function esc(s) {
  return String(s ?? "").replace(/[&<>"]/g, (c) =>
    ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));
}
