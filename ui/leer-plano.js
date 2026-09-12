/* Leer plano — panel de IDENTIFICADOR dentro de Taller 101.
 *
 * Se monta desde app.js con una línea:
 *     import { montarLeerPlano } from "./leer-plano.js";
 *     montarLeerPlano({ S, api, refrescar, estado });
 *
 * Usa las clases de la app (.tienda, .caja, .cab, .scroll, .pri, .gh) para verse
 * nativo, y sólo agrega las suyas con prefijo lp-.
 */

const H = (s) => String(s ?? "").replace(/[&<>"']/g,
  (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));

const ESTILOS = `
.lp-paso{display:flex;gap:6px;margin-left:auto;font-size:11px;color:var(--txt3)}
.lp-paso i{font-style:normal;padding:2px 8px;border-radius:99px;background:var(--panel2)}
.lp-paso i.on{background:var(--acc);color:#fff}
.lp-soltar{border:2px dashed var(--linea3);border-radius:10px;padding:40px 22px;text-align:center;
  background:var(--panel2)}
.lp-soltar.encima{border-color:var(--acc);background:var(--acc-sombra)}
.lp-soltar h3{margin:0 0 6px;font-size:16px}
.lp-soltar p{margin:0 auto 16px;color:var(--txt2);max-width:52ch;font-size:12.5px}
.lp-tareas{max-width:560px;margin:0 auto}
.lp-t{display:flex;gap:10px;padding:6px 0;color:var(--txt2);opacity:.45}
.lp-t.on,.lp-t.ok{opacity:1}
.lp-t.ok{color:var(--txt)}
.lp-t b{width:15px;height:15px;border-radius:50%;border:2px solid var(--linea3);flex:none;
  margin-top:3px;display:grid;place-items:center;font-size:9px;font-weight:400}
.lp-t.on b{border-color:var(--acc);border-right-color:transparent;animation:lpgiro .8s linear infinite}
.lp-t.ok b{border-color:var(--ok);background:var(--ok);color:#fff}
.lp-t small{display:block;color:var(--txt3);font-size:11.5px}
@keyframes lpgiro{to{transform:rotate(360deg)}}
.lp-cols{display:grid;grid-template-columns:minmax(0,1.02fr) minmax(0,.98fr);gap:14px;align-items:start}
@media(max-width:900px){.lp-cols{grid-template-columns:1fr}}
.lp-caja{background:var(--panel2);border:1px solid var(--linea);border-radius:var(--r);overflow:hidden}
.lp-caja>h4{margin:0;padding:8px 11px;font-size:12px;border-bottom:1px solid var(--linea);
  display:flex;gap:8px;align-items:center}
.lp-chip{font-size:10px;padding:1px 7px;border-radius:99px;background:var(--panel3);color:var(--txt2)}
.lp-chip.geo{background:var(--acc-sombra);color:var(--acc2)}
.lp-chip.ojo{background:var(--peligro-bg);color:var(--peligro)}
.lp-tabs{display:flex;gap:2px;padding:6px 8px 0;background:var(--panel3);flex-wrap:wrap}
.lp-tabs button{background:none;border:1px solid transparent;border-bottom:none;font-size:11.5px;
  padding:4px 9px;border-radius:var(--r) var(--r) 0 0;color:var(--txt2);cursor:pointer}
.lp-tabs button[aria-selected=true]{background:var(--panel2);color:var(--txt);border-color:var(--linea)}
.lp-lienzo{position:relative;background:#fff;line-height:0}
.lp-lienzo img{width:100%;display:block}
.lp-lienzo svg{position:absolute;inset:0;width:100%;height:100%}
.lp-lienzo rect{fill:transparent;stroke-width:2.5;cursor:pointer}
.lp-lienzo rect:hover{fill:rgba(0,128,193,.16)}
.lp-lienzo rect.sel{fill:rgba(0,128,193,.28);stroke-width:3.5}
/* #095 — El rótulo sobre el plano lleva número («M1», «M2»), así que va con la
   pila de cifras y no con la de marca: Sansation es del logotipo, no de
   etiquetar medidas sobre un dibujo. */
.lp-lienzo text{font:600 11px "Cifras","Raleway",system-ui,sans-serif;fill:#111;
  paint-order:stroke;stroke:#fff;stroke-width:3.5px;pointer-events:none}
.lp-tabla{width:100%;border-collapse:collapse;font-size:12px}
.lp-tabla th{text-align:left;font-size:9.5px;text-transform:uppercase;letter-spacing:.07em;
  color:var(--txt3);font-weight:400;padding:5px 7px;border-bottom:1px solid var(--linea)}
.lp-tabla td{padding:6px 7px;border-bottom:1px solid var(--linea2);vertical-align:top}
.lp-tabla tbody tr{cursor:pointer}
.lp-tabla tbody tr:hover{background:var(--hoverfila)}
.lp-tabla tbody tr.sel{background:var(--sel)}
.lp-tabla td.n{text-align:right;font-variant-numeric:tabular-nums}
.lp-fr{font-size:10.5px;border:1px solid var(--linea3);border-radius:3px;padding:0 5px;
  color:var(--txt2);margin-right:3px;white-space:nowrap}
.lp-preg{border-bottom:1px solid var(--linea2);padding:10px 11px}
.lp-preg.ok{background:color-mix(in srgb,var(--ok) 10%,transparent)}
.lp-preg h5{margin:0 0 3px;font-size:12.5px}
.lp-preg p{margin:0 0 8px;font-size:11.5px;color:var(--txt2)}
.lp-ops{display:flex;flex-direction:column;gap:4px}
.lp-op{display:flex;gap:7px;align-items:flex-start;border:1px solid var(--linea);border-radius:var(--r);
  padding:6px 8px;cursor:pointer;font-size:12px;background:var(--campo)}
.lp-op.sel{border-color:var(--acc);background:var(--acc-sombra)}
.lp-op small{display:block;color:var(--txt3);font-size:11px}
.lp-ev{font-size:10.5px;color:var(--txt3);margin-top:7px;padding-top:6px;
  border-top:1px dashed var(--linea2);display:flex;gap:12px;flex-wrap:wrap}
.lp-mats{padding:9px 11px;display:grid;grid-template-columns:1fr 1fr;gap:7px 10px;align-items:center;
  font-size:12px}
.lp-vacio{padding:18px;text-align:center;color:var(--txt3);font-size:12.5px}
.lp-pie{display:flex;align-items:center;gap:12px;padding:11px 16px;border-top:1px solid var(--linea)}
.lp-riel{flex:1;height:4px;background:var(--panel3);border-radius:2px;overflow:hidden}
.lp-riel i{display:block;height:100%;background:var(--acc);transition:width .25s}
.lp-aviso{background:var(--aviso-bg);border-left:3px solid var(--warn);padding:8px 11px;
  font-size:11.5px;margin:9px 0;border-radius:0 var(--r) var(--r) 0}
.lp-ayuda{max-width:640px;margin:14px auto 0;text-align:left;background:var(--panel2);
  border:1px solid var(--linea);border-radius:var(--r);padding:16px 20px;font-size:12.5px;
  line-height:1.7;color:var(--txt2)}
.lp-ayuda h4{margin:0 0 4px;font-size:13.5px;color:var(--txt)}
.lp-ayuda ol{margin:0;padding-left:0;list-style:none;counter-reset:paso}
.lp-ayuda ol>li{counter-increment:paso;position:relative;padding:0 0 14px 34px}
.lp-ayuda ol>li::before{content:counter(paso);position:absolute;left:0;top:1px;width:22px;
  height:22px;border-radius:50%;background:var(--acc);color:#fff;display:grid;
  place-items:center;font-size:11px}
.lp-ayuda b{color:var(--txt)}
.lp-ayuda code{background:var(--panel3);padding:1px 5px;border-radius:4px;font-size:11.5px}
.lp-ayuda .ojo{background:var(--aviso-bg);border-left:3px solid var(--warn);
  padding:8px 11px;margin:4px 0 0;border-radius:0 var(--r) var(--r) 0;font-size:11.5px}
.lp-ayuda table{width:100%;border-collapse:collapse;margin-top:6px;font-size:11.5px}
.lp-ayuda td{padding:4px 8px 4px 0;border-bottom:1px solid var(--linea2);vertical-align:top}
`;

/* #050 — La ayuda para sacar la llave, DENTRO del programa.
 *
 * Va aquí y no en un PDF aparte por una razón práctica: el momento en que hace
 * falta es el momento en que el cuadro pide la llave, y quien instala el
 * programa en una máquina del taller no va a tener a la mano un archivo que
 * alguien le mandó por correo. Viaja con el instalador y no se puede perder.
 */
const AYUDA_LLAVE = `
<div class="lp-ayuda">
  <h4>Cómo sacar tu llave de Anthropic</h4>
  <p style="margin:0 0 12px">Se hace una sola vez por taller. Toma unos diez
     minutos, y necesitas una tarjeta para cargarle saldo.</p>
  <ol>
    <li><b>Entra a <code>platform.claude.com</code></b><br>
        Sirve la misma cuenta de claude.ai. Si no tienes, créala ahí mismo.
        <div class="ojo">Ojo: ya no es <code>console.anthropic.com</code>. Ese
          redirige, pero el bueno es platform.claude.com.</div></li>
    <li><b>Carga saldo primero</b> — <code>Settings → Billing → Buy credits</code><br>
        La API se paga por adelantado. Sin saldo la llave existe pero cada plano
        falla. Con 20 USD alcanza para unos 65 planos de seis vistas.
        Ahí mismo puedes prender <b>auto-reload</b> para que se recargue sola.</li>
    <li><b>Crea la llave</b> — <code>Settings → API keys → Create key</code>
        <table>
          <tr><td style="width:96px">Name</td><td><code>Taller 101</code></td></tr>
          <tr><td>Expiration</td><td><b>Never</b></td></tr>
          <tr><td>Linked account</td><td>tú mismo</td></tr>
          <tr><td>Workspace</td><td>déjalo como viene</td></tr>
        </table>
        <div class="ojo"><b>«Expiration» es la trampa.</b> El menú ofrece 3
          horas, 1 día, 7 días, 30 días… Si escoges cualquiera de ésas, «Leer
          plano» sirve hoy y <b>deja de servir sola</b> el día que venza.
          Escoge <b>Never</b>.</div></li>
    <li><b>Cópiala completa</b><br>
        Empieza con <code>sk-ant-api</code> y <b>sólo se enseña una vez</b>.
        Cópiala antes de cerrar esa ventana. Si se pierde no se recupera: se
        borra esa y se hace otra.</li>
    <li><b>Pégala aquí arriba</b> y dale Guardar.<br>
        Se guarda en tu carpeta <code>Taller 101</code>, en este equipo.
        <b>Nunca va dentro del programa</b>, así que el instalador se puede
        compartir sin regalar tu llave — pero también quiere decir que en cada
        computadora del taller hay que pegarla otra vez.</li>
  </ol>
  <h4 style="margin-top:6px">Si algo sale mal</h4>
  <table>
    <tr><td style="width:44%">«Anthropic no aceptó la llave»</td>
        <td>mal copiada, revocada, o la creaste con vencimiento y ya venció</td></tr>
    <tr><td>«revisa el saldo de la cuenta»</td><td>falta el paso 2</td></tr>
    <tr><td>Lee, pero salen 0 módulos</td>
        <td>el plano no trae rótulos que el programa reconozca; no es la llave</td></tr>
  </table>
  <p style="margin:12px 0 0;color:var(--txt3);font-size:11.5px">
     Cuida tu llave como una tarjeta: quien la tenga puede gastar de tu saldo.
     No la mandes por correo ni por chat. Si se te salió, bórrala en
     <code>Settings → API keys</code> y haz otra.</p>
</div>`;

const HTML = `
<div class="caja">
  <div class="cab">
    <b>Leer plano</b>
    <span id="lpArchivo" style="font-size:11.5px;color:var(--txt3)"></span>
    <span class="lp-paso" id="lpPasos">
      <i data-p="cargar">1 Cargar</i><i data-p="leyendo">2 Leer</i>
      <i data-p="revisar">3 Revisar</i><i data-p="importar">4 Importar</i>
    </span>
    <button class="gh ic" id="lpCerrar" title="Cerrar (Esc)">×</button>
  </div>
  <div class="scroll" id="lpCuerpo"></div>
  <div class="lp-pie" id="lpPie" hidden>
    <span id="lpAvance" style="font-size:12px;color:var(--txt2)"></span>
    <span class="lp-riel"><i id="lpRiel"></i></span>
    <button class="gh" id="lpDefaults">Aceptar defaults</button>
    <button class="pri" id="lpImportar">Agregar al proyecto</button>
  </div>
</div>`;

export function montarLeerPlano({ S, api, refrescar, estado }) {
  const est = { paso: "cargar", tid: null, datos: null, resp: {}, mats: {},
                vista: 0, sel: null, poll: null };

  const style = document.createElement("style");
  style.textContent = ESTILOS;
  document.head.appendChild(style);

  const caja = document.createElement("div");
  caja.className = "tienda";
  caja.id = "lp";
  caja.innerHTML = HTML;
  document.body.appendChild(caja);

  const $ = (id) => document.getElementById(id);
  const cuerpo = $("lpCuerpo");

  const abrir = () => { caja.classList.add("on"); if (!est.datos) irA("cargar"); };
  const cerrar = () => {
    caja.classList.remove("on");
    if (est.poll) { clearInterval(est.poll); est.poll = null; }
  };
  $("lpCerrar").onclick = cerrar;
  document.addEventListener("keydown", (e) => {
    if (e.key === "Escape" && caja.classList.contains("on")) cerrar();
  });

  function irA(paso) {
    est.paso = paso;
    [...$("lpPasos").children].forEach((i) => i.classList.toggle("on", i.dataset.p === paso));
    $("lpPie").hidden = paso !== "revisar";
    if (paso === "cargar") pintarCargar();
  }

  // #049 — «1 Cargar» siempre es clicable. Mike se quedó atorado en una pantalla
  // sin botón de regreso: la única salida era cerrar el panel. Volver al primer
  // paso es la salida que ya existía, sólo que no se podía tocar.
  $("lpPasos").querySelector("[data-p='cargar']").style.cursor = "pointer";
  $("lpPasos").querySelector("[data-p='cargar']").title = "Volver a empezar con otro plano";
  $("lpPasos").querySelector("[data-p='cargar']").onclick = () => {
    if (est.paso === "cargar") return;
    if (est.poll) { clearInterval(est.poll); est.poll = null; }
    if (est.tid) {                       // se le avisa al servidor que ya no se usa
      api(`/api/plano/${est.tid}`, { method: "DELETE" }).catch(() => {});
      est.tid = null;
    }
    est.datos = null; est.resp = {}; est.mats = {}; est.sel = null; est.vista = 0;
    $("lpArchivo").textContent = "";
    irA("cargar");
  };

  /* ---------------------------------------------------------- la llave
   *
   * #046 — La llave se pide AQUÍ, en el momento en que hace falta. Antes el
   * panel decía «no está disponible» y el campo vivía en otra pestaña, así que
   * el usuario se quedaba con un error y sin la cosa que lo arregla a la vista.
   */
  function pintarPideLlave(motivo) {
    cuerpo.innerHTML = `
      <div class="lp-soltar" style="border-style:solid">
        <h3>Falta la llave para leer planos</h3>
        <p>${H(motivo || "")} La lectura la hace un modelo de Anthropic y se
           cobra a tu cuenta. Se teclea una vez: queda en este equipo, en tu
           carpeta de Taller 101, nunca dentro del programa.</p>
        <div style="display:flex;gap:6px;max-width:460px;margin:0 auto 10px">
          <input id="lpLlave" type="password" placeholder="sk-ant-…"
                 style="flex:1;min-width:0" autocomplete="off">
          <button class="pri" id="lpLlaveOk">Guardar</button>
        </div>
        <p id="lpLlaveMsg" style="min-height:16px;margin:0 0 4px"></p>
        <button class="gh" id="lpAyudaLlave">¿Cómo saco mi llave? →</button>
      </div>
      <div id="lpAyuda" hidden>${AYUDA_LLAVE}</div>`;
    const msg = $("lpLlaveMsg");
    $("lpAyudaLlave").onclick = () => {
      const a = $("lpAyuda");
      a.hidden = !a.hidden;
      $("lpAyudaLlave").textContent = a.hidden
        ? "¿Cómo saco mi llave? →" : "Ocultar los pasos";
      if (!a.hidden) a.scrollIntoView({ behavior: "smooth", block: "start" });
    };
    $("lpLlave").onkeydown = (e) => { if (e.key === "Enter") $("lpLlaveOk").click(); };
    $("lpLlaveOk").onclick = async () => {
      const v = $("lpLlave").value.trim();
      if (!v) { msg.textContent = "Pega la llave primero."; return; }
      // Se revisa la forma antes de guardarla: pegar la mitad de la llave, o el
      // nombre que se le puso en la consola, es un error de dedo que si no se
      // atrapa aquí reaparece tres minutos después como un 401 en inglés.
      if (!/^sk-ant-/.test(v)) {
        msg.textContent = "Eso no parece una llave: las de Anthropic empiezan "
          + "con sk-ant-";
        return;
      }
      msg.textContent = "Guardando…";
      try {
        await api("/api/llave", {
          method: "PUT", headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ valor: v }),
        });
      } catch (e) { msg.textContent = "No se pudo guardar: " + e.message; return; }
      pintarCargar();
    };
    $("lpLlave").focus();
  }

  /* ---------------------------------------------------------- paso 1 */
  async function pintarCargar() {
    // Se pregunta ANTES de que elija archivo: hacerlo esperar a que suba un
    // plano para decirle que falta la llave es hacerle perder el viaje dos veces.
    let sal = null;
    try { sal = await api("/api/plano/salud"); } catch (e) { sal = null; }
    if (sal && !sal.ok && sal.falta === "llave") return pintarPideLlave(sal.motivo);

    const aviso = sal && !sal.ok
      ? `<div class="lp-aviso" style="margin-bottom:12px">${H(sal.motivo || "")}</div>` : "";
    cuerpo.innerHTML = aviso + `
      <div class="lp-soltar" id="lpSoltar">
        <h3>Arrastra el plano aquí</h3>
        <p>PDF de CAD, PDF escaneado o una foto del plano impreso. Se buscan las
           elevaciones, se leen las cotas y salen los módulos.</p>
        <button class="pri" id="lpElegir">Elegir archivo…</button>
        <input type="file" id="lpFile" accept=".pdf,.png,.jpg,.jpeg,.tif,.tiff" hidden>
      </div>`;
    const zona = $("lpSoltar"), file = $("lpFile");
    $("lpElegir").onclick = () => file.click();
    file.onchange = () => file.files[0] && subir(file.files[0]);
    ["dragenter", "dragover"].forEach((e) => zona.addEventListener(e, (ev) => {
      ev.preventDefault(); zona.classList.add("encima");
    }));
    ["dragleave", "drop"].forEach((e) => zona.addEventListener(e, (ev) => {
      ev.preventDefault(); zona.classList.remove("encima");
    }));
    zona.addEventListener("drop", (ev) => ev.dataTransfer.files[0] && subir(ev.dataTransfer.files[0]));
  }

  /* ---------------------------------------------------------- paso 2 */
  async function subir(archivo) {
    est.resp = {}; est.mats = {}; est.sel = null; est.vista = 0; est.datos = null;
    $("lpArchivo").textContent = archivo.name;
    irA("leyendo");
    cuerpo.innerHTML = `<div class="lp-tareas" id="lpTareas"></div>`;

    const fd = new FormData();
    fd.append("archivo", archivo);
    if (S.proyecto?.nombre) fd.append("proyecto", S.proyecto.nombre);
    let r;
    try {
      r = await api("/api/plano/analizar", { method: "POST", body: fd });
    } catch (e) { return falla(e.message); }
    est.tid = r.trabajo_id;

    let vistos = 0;
    est.poll = setInterval(async () => {
      let t;
      try { t = await api("/api/plano/" + est.tid); } catch (e) { return falla(e.message); }
      (t.progreso || []).slice(vistos).forEach((p) => { vistos++; tarea(p.titulo, p.detalle); });
      if (t.estado === "error") return falla(t.error);
      if (t.estado === "listo") {
        clearInterval(est.poll); est.poll = null;
        cerrarTareas();
        est.datos = t;
        (t.materiales_del_plano || []).forEach((m) => (est.mats[m] = null));
        irA("revisar"); pintarRevisar();
      }
    }, 900);
  }

  function tarea(titulo, detalle) {
    const c = $("lpTareas"); if (!c) return;
    const previa = c.querySelector(".lp-t.on");
    if (previa) { previa.className = "lp-t ok"; previa.querySelector("b").textContent = "✓"; }
    c.insertAdjacentHTML("beforeend",
      `<div class="lp-t on"><b></b><span>${H(titulo)}<small>${H(detalle || "")}</small></span></div>`);
  }
  function cerrarTareas() {
    document.querySelectorAll("#lpTareas .lp-t.on").forEach((t) => {
      t.className = "lp-t ok"; t.querySelector("b").textContent = "✓";
    });
  }
  async function falla(msg) {
    if (est.poll) { clearInterval(est.poll); est.poll = null; }
    // #046 — si lo que falta es la llave, se pide AQUÍ. Decirle a alguien que
    // le falta la llave y dejarlo en una pantalla donde no puede escribirla es
    // dejarlo igual de atorado que antes, sólo que con mejor ortografía.
    const t = String(msg || "");
    // Una llave mal copiada o sin saldo vuelve como un 401 de la API, con su
    // JSON en inglés adentro. Eso no es un mensaje para el taller, y además
    // tiene arreglo: se vuelve a pedir la llave, dicho en castellano.
    if (/401|authentication_error|invalid x-api-key|API key/i.test(t)) {
      return pintarPideLlave(
        "Anthropic no aceptó la llave: puede estar mal copiada, revocada, "
        + "o la cuenta sin saldo.");
    }
    if (/402|credit balance|quota|rate_limit|529|overloaded/i.test(t)) {
      return pintarPideLlave(
        "Anthropic no dejó leer el plano: revisa el saldo de la cuenta. "
        + "Si prefieres, cambia la llave.");
    }
    try {
      const s = await api("/api/plano/salud");
      if (!s.ok && s.falta === "llave") return pintarPideLlave(s.motivo);
    } catch (e) { /* si ni eso contesta, se enseña el error tal cual */ }
    cuerpo.innerHTML = `<div class="lp-aviso"><b>No se pudo leer el plano.</b><br>${H(msg)}</div>
      <div style="text-align:center"><button class="gh" id="lpVolver">Probar con otro</button></div>`;
    $("lpVolver").onclick = () => irA("cargar");
  }

  /* ---------------------------------------------------------- paso 3 */
  const mm = (v) => (v == null ? "?" : Math.round(v));

  function pintarRevisar() {
    const d = est.datos, pay = d.resultado;
    const vistas = (d.vistas || []).filter((v) => v.procesada && v.imagen);
    const v = vistas[est.vista];
    const mueble = pay.muebles[est.vista] || pay.muebles[0] || { gabinetes: [], corridos: [] };

    // #049 — Cero módulos NO se enseña como una pantalla de revisión vacía. Eso
    // fue exactamente lo que le pasó a Mike con CAR-06: el panel se veía
    // «terminado», con su barra de avance llena y su botón azul, y por dentro no
    // había nada que agregar. Se dice lo que pasó y se ofrece la salida.
    const total = (pay.muebles || []).reduce(
      (n, m) => n + (m.gabinetes || []).length, 0);
    if (!total) {
      $("lpPie").hidden = true;
      // #055 — se enseña QUÉ pasó en cada vista. Un «no reconocí nada» a secas
      // manda a buscar el problema al plano; casi siempre está en otro lado, y
      // sin estas cifras no hay forma de saber en cuál.
      const vs = d.vistas || [];
      const leidas = vs.filter((v) => v.procesada);
      const filas = vs.map((v) => `
        <tr><td>${H(v.titulo || "—")}</td><td>${H(v.tipo || "")}</td>
            <td>${v.procesada ? "se leyó" : "no se manda al modelo"}</td>
            <td class="n">${v.procesada ? (v.modulos ?? 0) : "—"}</td></tr>`).join("");
      cuerpo.innerHTML = `
        <div class="lp-aviso"><b>No reconocí ningún mueble en este plano.</b><br>
          Se abrió bien (${H(pay.origen.tipo)}) y encontré ${vs.length} vista(s),
          de las que ${leidas.length} se mandaron al modelo — pero no salió ni un
          módulo, así que no hay nada que agregar al proyecto.</div>
        <div class="lp-caja" style="margin:12px 0">
          <h4>Qué encontré en la lámina</h4>
          <table class="lp-tabla">
            <thead><tr><th>Vista</th><th>Tipo</th><th>Estado</th>
              <th class="n">Módulos</th></tr></thead>
            <tbody>${filas || '<tr><td colspan="4">ninguna</td></tr>'}</tbody>
          </table>
        </div>
        <div class="lp-caja" style="margin:12px 0;padding:12px 14px">
          <div style="font-size:12px;color:var(--txt2);line-height:1.65">
            Sólo se leen <b>elevaciones y cortes</b>: es donde se ven los frentes.
            Las plantas y los detalles se detectan pero no dan módulos.
            <ul style="margin:8px 0 0;padding-left:18px">
              <li>Si arriba dice <b>0 módulos</b> en una elevación, el recorte
                  llegó al modelo pero no sacó nada de él.</li>
              <li>Si no aparece ninguna elevación, la lámina es de plantas o
                  detalles, o rotula distinto a lo que reconozco.</li>
            </ul>
          </div>
        </div>
        <div style="text-align:center;display:flex;gap:8px;justify-content:center">
          <button class="pri" id="lpVolver">Probar con otro plano</button>
          <button class="gh" id="lpDiag">Guardar diagnóstico</button>
        </div>
        <p id="lpDiagMsg" style="text-align:center;font-size:11.5px;
           color:var(--txt3);margin:10px 0 0"></p>`;
      $("lpVolver").onclick = () => irA("cargar");
      $("lpDiag").onclick = async () => {
        const m = $("lpDiagMsg");
        m.textContent = "Guardando…";
        try {
          const r = await api(`/api/plano/${est.tid}/diagnostico`, { method: "POST" });
          m.innerHTML = `Guardado en <b>${H(r.carpeta)}</b> (${r.archivos} archivos).
            Ahí están los recortes que se le mandaron al modelo y lo que contestó.`;
        } catch (e) { m.textContent = "No se pudo guardar: " + e.message; }
      };
      return;
    }

    cuerpo.innerHTML = `
      <div class="lp-cols">
        <div class="lp-caja">
          <h4>Plano
            <span class="lp-chip">${H(pay.origen.tipo)}</span>
            <span class="lp-chip ${pay.origen.geometria_confiable ? "geo" : "ojo"}">
              ${pay.origen.geometria_confiable ? "geometría medible" : "sólo cotas escritas"}</span>
          </h4>
          <div class="lp-tabs">${vistas.map((x, i) =>
            `<button aria-selected="${i === est.vista}" data-v="${i}">${H(x.titulo)}</button>`).join("")}</div>
          <div class="lp-lienzo" id="lpLienzo"></div>
        </div>
        <div>
          <div class="lp-caja" style="margin-bottom:12px">
            <h4>Módulos <span class="lp-chip">${pay.muebles.reduce((a, m) => a + m.gabinetes.length, 0)}</span></h4>
            <div id="lpModulos"></div>
          </div>
          <div class="lp-caja" style="margin-bottom:12px">
            <h4>Materiales del plano</h4>
            <div class="lp-mats" id="lpMats"></div>
          </div>
          <div class="lp-caja">
            <h4>Falta definir</h4>
            <div id="lpPreg"></div>
          </div>
        </div>
      </div>`;

    cuerpo.querySelectorAll("[data-v]").forEach((b) =>
      b.onclick = () => { est.vista = +b.dataset.v; est.sel = null; pintarRevisar(); });

    pintarLienzo(v, mueble);
    pintarModulos(pay);
    pintarMats();
    pintarPreguntas();
    pintarPie();
  }

  function pintarLienzo(v, mueble) {
    const cont = $("lpLienzo");
    if (!v) { cont.innerHTML = ""; return; }
    const bb = (est.datos.bbox || {})[mueble.id] || {};
    cont.innerHTML = `<img id="lpImg" src="/api/plano/${est.tid}/vista/${encodeURIComponent(v.imagen)}">
                      <svg id="lpSvg" preserveAspectRatio="none"></svg>`;
    const img = $("lpImg");
    const dibuja = () => {
      const svg = $("lpSvg");
      svg.setAttribute("viewBox", `0 0 ${img.naturalWidth} ${img.naturalHeight}`);
      svg.innerHTML = mueble.gabinetes.map((g) => {
        const b = bb[g.id]; if (!b) return "";
        const c = g.confianza?.global < 0.7 ? "#c9694a" : "#4ea36b";
        return `<rect data-id="${H(g.id)}" class="${est.sel === g.id ? "sel" : ""}"
            x="${b[0]}" y="${b[1]}" width="${b[2] - b[0]}" height="${b[3] - b[1]}" stroke="${c}"/>
          <text x="${b[0] + 6}" y="${b[1] + 16}">${H(g.id.replace(/^.*?-/, ""))}</text>`;
      }).join("");
      svg.querySelectorAll("rect").forEach((r) => r.onclick = () => elegir(r.dataset.id));
    };
    if (img.complete) dibuja(); else img.onload = dibuja;
  }

  function elegir(id) {
    est.sel = est.sel === id ? null : id;
    pintarRevisar();
    const tr = document.querySelector(`.lp-tabla tr[data-id="${CSS.escape(id)}"]`);
    if (tr) tr.scrollIntoView({ block: "nearest" });
  }

  function pintarModulos(pay) {
    $("lpModulos").innerHTML = pay.muebles.map((m) => `
      <div style="padding:7px 11px;font-size:11.5px;color:var(--txt2);background:var(--panel3)">
        ${H(m.nombre || m.id)} · ${mm(m.medidas_totales_mm?.ancho)} ×
        ${mm(m.medidas_totales_mm?.alto)} × ${mm(m.medidas_totales_mm?.prof)} mm</div>
      <table class="lp-tabla"><thead><tr><th>Módulo</th><th style="text-align:right">Ancho</th>
        <th style="text-align:right">Alto</th><th style="text-align:right">Prof</th><th>Frentes</th></tr></thead>
      <tbody>${m.gabinetes.map((g) => {
        const e = g.medidas_exteriores_mm || {};
        const fr = (g.frentes || []).map((f) =>
          `<span class="lp-fr">${H(f.tipo)} ${mm(f.medidas_mm?.ancho)}×${mm(f.medidas_mm?.alto)}</span>`
        ).join("") || `<span class="lp-fr">sin frentes</span>`;
        return `<tr data-id="${H(g.id)}" class="${est.sel === g.id ? "sel" : ""}">
          <td>${H(g.id)}<br><span style="font-size:10px;color:var(--txt3)">${H(g.plantilla_sugerida || "")}</span></td>
          <td class="n">${mm(e.ancho)}</td><td class="n">${mm(e.alto)}</td><td class="n">${mm(e.prof)}</td>
          <td>${fr}</td></tr>`;
      }).join("")}</tbody></table>`).join("");
    $("lpModulos").querySelectorAll("tr[data-id]").forEach((tr) =>
      tr.onclick = () => elegir(tr.dataset.id));
  }

  function pintarMats() {
    const cat = (S.proyecto.catalogo || []).map((m) => m.nombre);
    const claves = Object.keys(est.mats);
    $("lpMats").innerHTML = claves.length
      ? claves.map((k) => `
          <span style="color:var(--txt2)">${H(k)}</span>
          <select data-mat="${H(k)}">
            <option value="">— usar el del proyecto —</option>
            ${cat.map((n) => `<option ${est.mats[k] === n ? "selected" : ""}>${H(n)}</option>`).join("")}
          </select>`).join("")
      : `<span style="color:var(--txt3);grid-column:1/-1">El plano no trae claves de material.</span>`;
    $("lpMats").querySelectorAll("[data-mat]").forEach((s) =>
      s.onchange = () => { est.mats[s.dataset.mat] = s.value || null; });
  }

  function pintarPreguntas() {
    const qs = est.datos.preguntas || [];
    if (!qs.length) { $("lpPreg").innerHTML = `<div class="lp-vacio">Nada pendiente.</div>`; return; }
    const orden = { particion: 0, medida: 1, material: 2, frente: 3 };
    $("lpPreg").innerHTML = [...qs]
      .sort((a, b) => (orden[a.tipo] - orden[b.tipo]) || (b.obligatoria - a.obligatoria))
      .map((q) => {
        const val = est.resp[q.id], hecho = val !== undefined && val !== null;
        const ctrl = q.formato === "numero"
          ? `<div style="display:flex;gap:7px;align-items:center">
               <input type="number" data-q="${H(q.id)}" value="${val ?? ""}"
                 placeholder="${q.valor_default ?? "—"}" style="width:110px">
               <span style="font-size:11px;color:var(--txt3)">${H(q.unidad || "")}</span>
               ${q.valor_default != null ? `<button class="gh" data-def="${H(q.id)}"
                  data-val="${q.valor_default}" style="font-size:11px;padding:3px 8px">usar ${q.valor_default}</button>` : ""}
             </div>`
          : `<div class="lp-ops">${(q.opciones || []).map((o) => `
              <label class="lp-op ${JSON.stringify(val) === JSON.stringify(o.valor) ? "sel" : ""}">
                <input type="radio" name="${H(q.id)}" data-q="${H(q.id)}" data-json="1"
                  value='${H(JSON.stringify(o.valor))}'
                  ${JSON.stringify(val) === JSON.stringify(o.valor) ? "checked" : ""}>
                <span>${H(o.label)}${o.recomendada ? " · sugerido" : ""}
                ${o.detalle ? `<small>${H(o.detalle)}</small>` : ""}</span></label>`).join("")}</div>`;
        return `<div class="lp-preg ${hecho ? "ok" : ""}">
          <h5>${H(q.titulo)}</h5><p>${H(q.detalle)}</p>${ctrl}
          <div class="lp-ev">${q.evidencia ? `<span>evidencia · ${H(q.evidencia)}</span>` : ""}
          ${q.impacto ? `<span>impacto · ${H(q.impacto)}</span>` : ""}
          ${!q.obligatoria ? "<span>opcional</span>" : ""}</div></div>`;
      }).join("");

    $("lpPreg").querySelectorAll("[data-q]").forEach((el) => el.onchange = () => {
      let v = el.type === "number" ? (el.value === "" ? null : +el.value) : el.value;
      if (el.dataset.json) v = JSON.parse(el.value);
      est.resp[el.dataset.q] = v; pintarPreguntas(); pintarPie();
    });
    $("lpPreg").querySelectorAll("[data-def]").forEach((b) => b.onclick = () => {
      est.resp[b.dataset.def] = +b.dataset.val; pintarPreguntas(); pintarPie();
    });
  }

  function faltan() {
    return (est.datos.preguntas || []).filter(
      (q) => q.obligatoria && (est.resp[q.id] === undefined || est.resp[q.id] === null));
  }
  function pintarPie() {
    const obl = (est.datos.preguntas || []).filter((q) => q.obligatoria).length;
    const falta = faltan().length;
    $("lpAvance").textContent = falta ? `Faltan ${falta} de ${obl}` : "Listo para agregar";
    $("lpRiel").style.width = (obl ? (100 * (obl - falta)) / obl : 100) + "%";
    $("lpImportar").disabled = falta > 0;
  }

  $("lpDefaults").onclick = () => {
    for (const q of est.datos.preguntas || []) {
      if (est.resp[q.id] !== undefined) continue;
      if (q.valor_default != null) est.resp[q.id] = q.valor_default;
      else { const r = (q.opciones || []).find((o) => o.recomendada); if (r) est.resp[q.id] = r.valor; }
    }
    pintarPreguntas(); pintarPie();
  };

  /* ---------------------------------------------------------- paso 4 */
  $("lpImportar").onclick = async () => {
    let r;
    try {
      r = await api(`/api/plano/${est.tid}/importar`, {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ respuestas: est.resp, materiales: est.mats }),
      });
    } catch (e) { return falla(e.message); }

    const usados = new Set(S.proyecto.gabinetes.map((x) => x.nombre));
    for (const g of r.gabinetes) {
      let nom = g.nombre, n = 1;
      while (usados.has(nom)) nom = `${g.nombre} ${++n}`;
      usados.add(nom);
      S.proyecto.gabinetes.push({ ...g, nombre: nom });
    }
    S.sel = S.proyecto.gabinetes.length - 1;
    irA("importar");
    cerrar();
    refrescar();
    estado(`leídos del plano: ${r.resumen.gabinetes} módulos, ` +
           `${r.resumen.puertas} puertas, ${r.resumen.cajones} cajones`);
    if (r.avisos?.length) console.warn("[leer plano]", r.avisos);
  };

  return { abrir, cerrar };
}
