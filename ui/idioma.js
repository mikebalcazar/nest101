/* #085 — Idioma de la interfaz.

   Mike: «ahí mismo hay que poner la opción de idioma. Necesito que la
   aplicación por default arranque en inglés.»

   La decisión de fondo: **la clave es el texto en español**. No hay `data-i18n`
   ni claves inventadas tipo `boton.guardar`. El diccionario es
   `assets/idioma/en.json` y se ve así:

       { "Lista de corte": "Cut list", "Ancho": "Width", … }

   Por qué así y no con etiquetas:

   · Hay 212 textos repartidos en `index.html` y otros tantos que `app.js`
     pinta con plantillas. Etiquetarlos uno por uno son 400 lugares donde
     equivocarse, y cada texto nuevo que alguien escriba mañana nace sin
     etiqueta y sin que nadie lo note.
   · Con el español de clave, el archivo en español **no existe**: es el
     código. Un texto sin traducir sale en español, que es entendible, en vez
     de salir como `boton.guardar`, que no es nada.
   · Y se puede comprobar de verdad: `t020` compara las cadenas que hay en el
     HTML contra las llaves del diccionario y falla si aparece una nueva sin
     traducir. Una etiqueta olvidada no se puede detectar así.

   El recorrido va por nodos de texto y por los atributos que se leen
   (`title`, `placeholder`, `alt`). Y se queda escuchando con un
   `MutationObserver`, porque casi toda la interfaz se repinta con
   `innerHTML`: sin el observador, la lista de piezas volvería al español en
   cuanto se recalcula.

   Lo que NO se toca: lo que escribió el usuario. Los `value` de los campos,
   los nombres de sus muebles y de sus materiales pasan tal cual — sólo se
   traduce lo que está literalmente en el diccionario, así que un mueble que
   se llame «Ancho» sigue llamándose «Ancho». */

export const IDIOMAS = { es: "Español", en: "English" };

let DIC = {};              // español → idioma activo
let ACTIVO = "es";
let observando = null;

export function idioma() { return ACTIVO; }

// `*` y no `?`: «0.15.3» tiene que ser UN número, no «0.15» y «3».
const NUM = /\d+(?:[.,]\d+)*/g;

/** Traduce una cadena suelta. Sin entrada en el diccionario, sale igual.

    Además de la búsqueda exacta hay **una** regla, la misma que en
    `core/idioma.py`: los números se sacan y se vuelven a meter. «Frente de
    cajón 3» busca «Frente de cajón #» y devuelve «Drawer front 3». Sin ella,
    el diccionario tendría que traer una línea por cada número posible. */
export function T(t) {
  if (t == null) return t;
  // Los saltos de línea y la sangría del HTML se aplastan a un espacio antes de
  // buscar. Sin esto, un párrafo escrito en tres renglones —que en el archivo es
  // un solo nodo de texto con saltos adentro— nunca encuentra su entrada, y el
  // diccionario parece incompleto cuando lo que falla es la búsqueda. Fue justo
  // lo que pasó: la prueba normalizaba y el programa no, así que t020 pasaba en
  // verde con media caja de configuración en español.
  const s = String(t).replace(/\s+/g, " ").trim();
  if (DIC[s]) return DIC[s];
  const nums = s.match(NUM);
  if (!nums) return String(t);
  const tr = DIC[s.replace(NUM, "#")];
  if (!tr) return String(t);
  let i = 0;
  return tr.replace(/#/g, () => (i < nums.length ? nums[i++] : "#"));
}

/** Traduce un texto que lleva un número u otro dato pegado.
    `T2("Hoja %s", 3)` con "Hoja %s" en el diccionario da "Sheet 3". */
export function T2(plantilla, ...args) {
  let s = T(plantilla);
  for (const a of args) s = s.replace("%s", a);
  return s;
}

const ATRIBUTOS = ["title", "placeholder", "alt", "aria-label"];
// Dentro de estas etiquetas no hay texto que enseñar.
const SALTAR = new Set(["SCRIPT", "STYLE", "CANVAS", "TEXTAREA"]);

function traducirNodo(n) {
  if (n.nodeType === 3) {                       // nodo de texto
    const bruto = n.nodeValue;
    const s = bruto.trim();
    if (!s) return;
    const tr = T(s);
    // Se conservan los espacios de los extremos: son los que separan este trozo
    // del <b> que va al lado. Sin ellos, «…la pantalla <b>y el papel</b>» se
    // pega y sale «screenand the paper».
    if (tr !== s) {
      const izq = bruto.match(/^\s*/)[0], der = bruto.match(/\s*$/)[0];
      n.nodeValue = izq + tr + der;
    }
    return;
  }
  if (n.nodeType !== 1 || SALTAR.has(n.tagName)) return;
  if (n.closest && n.closest("[data-sin-traducir]")) return;
  for (const a of ATRIBUTOS) {
    const v = n.getAttribute && n.getAttribute(a);
    if (v) { const tr = T(v); if (tr !== v.trim()) n.setAttribute(a, tr); }
  }
  // `option` guarda su texto aparte; sin esto los desplegables no cambian
  if (n.tagName === "OPTION") {
    const tr = T(n.textContent);
    if (tr !== n.textContent.trim()) n.textContent = tr;
  }
  for (const h of n.childNodes) traducirNodo(h);
}

export function traducirTodo(raiz = document.body) {
  if (ACTIVO === "es") return;
  traducirNodo(raiz);
}

function observar() {
  if (observando || ACTIVO === "es") return;
  observando = new MutationObserver((muts) => {
    // Se apaga mientras se traduce: si no, cada cambio que hace el observador
    // dispara al observador otra vez y se queda dando vueltas.
    observando.disconnect();
    for (const m of muts) {
      for (const n of m.addedNodes) traducirNodo(n);
      if (m.type === "attributes" && m.target) traducirNodo(m.target);
      if (m.type === "characterData") traducirNodo(m.target);
    }
    prender();
  });
  prender();
}

function prender() {
  observando.observe(document.body, {
    childList: true, subtree: true, characterData: true,
    attributes: true, attributeFilter: ATRIBUTOS,
  });
}

/** Carga el diccionario y traduce lo que ya esté pintado. */
export async function ponerIdioma(codigo) {
  ACTIVO = IDIOMAS[codigo] ? codigo : "es";
  document.documentElement.lang = ACTIVO;
  if (ACTIVO === "es") {
    DIC = {};
    // Volver al español pide repintar: el texto original ya se perdió del DOM.
    // Es un cambio de idioma, pasa dos veces en la vida de la app.
    if (observando) { observando.disconnect(); observando = null; }
    return DIC;
  }
  try {
    const r = await fetch(`/api/idioma/${ACTIVO}.json`);
    DIC = r.ok ? await r.json() : {};
  } catch { DIC = {}; }
  traducirTodo();
  observar();
  return DIC;
}
