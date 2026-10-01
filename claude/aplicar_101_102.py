"""Aplica los arreglos #101 y #102 sobre el árbol del repositorio.

Existe porque el chat que los hizo no tiene empuje directo a este repositorio:
el proxy de su sesión no autoriza `nest101`, y el conector de GitHub sólo sabe
escribir archivos completos —`ui/app.js` son 140 KB y volver a teclearlo a mano
es justo la clase de cosa que mete un error que nadie buscaría—. Así que lo que
viaja es el cambio, no el archivo: cada reemplazo lleva su ancla, y si una ancla
no aparece **exactamente una vez** esto se detiene sin tocar nada.

Cada cambio lleva además una **firma**: un trozo corto que, si ya está en el
archivo, significa que el cambio está puesto. La primera versión preguntaba si
el texto nuevo completo estaba, y eso se rompió solo: `core/proyecto.py` recibió
después el filtro del zoclo (#103) y ni el texto nuevo ni el ancla volvieron a
coincidir palabra por palabra, así que el aplicador se detuvo con «el ancla
aparece 0 veces» sobre un cambio que ya estaba hecho. Una firma corta sobrevive
a que el vecindario cambie; un bloque de treinta líneas no.

Lo corre el mandadero (ver `claude/ultimo-mandado.md`), que después mide con
`verificar.py` y sólo entonces hace el commit.
"""

from __future__ import annotations

import pathlib
import sys

RAIZ = pathlib.Path(__file__).resolve().parent.parent

CAMBIOS: list[tuple[str, str, str, str]] = []


def cambio(archivo: str, viejo: str, nuevo: str, firma: str) -> None:
    CAMBIOS.append((archivo, viejo, nuevo, firma))


# ------------------------------------------------------------------ #102 motor
cambio(
    "core/modelos.py",
    """    if not lleva:
        total = float(g.alto_cuerpo if (d == "total" and g.alto_cuerpo) else g.alto)
        total -= ec
""",
    """    if not lleva:
        # #102 — con el total derivado, `alto_cuerpo` YA es el cuerpo: quitarle
        # la plancha otra vez encogía el mueble un espesor en cada recálculo
        # (20 mm por vez con piedra de 20). Es el mismo defecto de #059, que se
        # arregló en la rama con zoclo y se quedó vivo en ésta.
        if d == "total" and g.alto_cuerpo:
            total = float(g.alto_cuerpo)
        else:
            total = float(g.alto) - ec
""",
    'if d == "total" and g.alto_cuerpo:')

# --------------------------------------------------------------- #102 el saneo
#
# Los dos cambios de `core/proyecto.py` ya están en `main` (llegaron por el
# conector, que sí puede con un archivo de 12 KB). Se quedan aquí con su firma
# para que el aplicador lo diga en voz alta en vez de callar, y para que siga
# sirviendo sobre un árbol viejo.
cambio(
    "core/proyecto.py",
    """from .nesting import nestear, Hoja


@dataclass
class Proyecto:""",
    '''from .nesting import nestear, Hoja


def _sanear_alto_cuerpo(g: Gabinete, std: Estandar) -> bool:
    """#102 — cura el `alto_cuerpo` que quedó valiendo la altura TOTAL.

    Hasta la 0.18.2 la pantalla del gabinete escribía `alto_cuerpo = alto` en
    los muebles sin zoclo y no descontaba la plancha en los demás. Con el
    candado en «total» ese número se vuelve el cuerpo, y entonces el costado de
    la lista de corte sale con la altura total: nadie le resta el zoclo. Mike lo
    vio en los PDF de corte.

    El arreglo de la captura no repara los archivos ya guardados, y esos son los
    que están en el taller. Aquí se detecta el dato imposible —un cuerpo que no
    deja lugar al zoclo dentro del total declarado— y se vuelve a derivar.
    Idempotente: una vez curado no vuelve a entrar.
    """
    if not (g.tipo == "base" and g.con_zoclo):
        return False
    if (g.alto_derivado or "cuerpo").lower() != "total" or g.alto_cuerpo is None:
        return False
    hz = float(g.altura_zoclo if g.altura_zoclo is not None else std.altura_zoclo)
    if hz <= 0:
        return False
    # **Sólo la firma exacta del defecto**: `alto_cuerpo` idéntico al alto
    # declarado, que es lo que escribía `g.alto_cuerpo = g.alto`. Un cuerpo
    # grande capturado a mano es legítimo —con este candado el total se deriva
    # de cuerpo + zoclo y sube— y no se toca. La primera versión de este saneo
    # curaba por «no cabe en el total» y se llevaba esos casos buenos: lo cazó
    # la comprobación de que normalizar corrige el total sucio a 950.
    if abs(float(g.alto_cuerpo) - float(g.alto)) > 0.05:
        return False
    g.alto_cuerpo = round(float(g.alto) - espesor_cubierta(g, std) - hz, 1)
    return True


@dataclass
class Proyecto:''',
    "def _sanear_alto_cuerpo(")

cambio(
    "core/proyecto.py",
    """        for g in self.gabinetes:
            std_g = self.estandar_de(g)
            try:
                total, cuerpo, hz = alturas(g, std_g)""",
    """        for g in self.gabinetes:
            std_g = self.estandar_de(g)
            _sanear_alto_cuerpo(g, std_g)
            try:
                total, cuerpo, hz = alturas(g, std_g)""",
    "            _sanear_alto_cuerpo(g, std_g)")

# ------------------------------------------------------- #101 el PDF de planos
cambio(
    "export/pdf.py",
    """def _iso_en_pagina(c, solidos, x_pt, y_pt, w_pt, h_pt, tmpdir, nombre,
                   etiquetas=False, ancho_px=2400):""",
    """import itertools

# Un número de serie por isométrico renderizado. Ver #101 dentro de
# `_iso_en_pagina`: dos imágenes distintas no pueden compartir nombre de
# archivo, o reportlab pone la primera en las dos páginas.
_SERIE = itertools.count(1)


def _iso_en_pagina(c, solidos, x_pt, y_pt, w_pt, h_pt, tmpdir, nombre,
                   etiquetas=False, ancho_px=2400):""",
    "_SERIE = itertools.count(1)")

cambio(
    "export/pdf.py",
    """    ruta = os.path.join(tmpdir, nombre)
    im.save(ruta, "PNG")""",
    """    # #101 — el archivo lleva un número de serie propio. reportlab guarda las
    # imágenes **por nombre de archivo** y reutiliza la primera: al exportar el
    # proyecto entero, dos muebles con un gabinete del mismo nombre daban la
    # misma ruta (`iso_Gabinete_1_arm.png`) y el segundo salía con el
    # isométrico del primero. La página de conjunto era peor: su nombre
    # (`iso_cocina.png`) era fijo para todos los muebles. Lo reportó Mike:
    # «me coloca la misma imagen isométrica del primero en todos».
    ruta = os.path.join(tmpdir, f"{next(_SERIE):04d}_{nombre}")
    im.save(ruta, "PNG")""",
    'f"{next(_SERIE):04d}_{nombre}"')

# ---------------------------------------------------------- #102 la captura
cambio(
    "ui/app.js",
    """  if (!hay) { g.alto = d === "total" ? c : t; g.alto_cuerpo = g.alto; return; }
  if (d === "total") {            // capturas cuerpo + zoclo
    g.alto_cuerpo = c; g.altura_zoclo = z; g.alto = c + z;
  } else if (d === "zoclo") {     // capturas total + cuerpo
    g.alto = t; g.alto_cuerpo = c; g.altura_zoclo = t - c;
  } else {                        // "cuerpo": capturas total + zoclo
    g.alto = t; g.altura_zoclo = z; g.alto_cuerpo = t - z;
  }""",
    """  // #102 — la plancha entra en todas las cuentas. `g.alto` es el DECLARADO (con
  // cubierta) y `g.alto_cuerpo` es el cuerpo construido (sin ella): confundirlos
  // dejaba `alto_cuerpo` valiendo el total, y con el candado en «total» el motor
  // tomaba ese número como cuerpo y la lista de corte salía con la altura total,
  // sin restar el zoclo. Lo reportó Mike: «en los cortes reinterpreta la altura
  // total como la altura del gabinete, no le resta la altura del zoclo».
  const ec = espesorCubierta(g);
  if (!hay) {
    const decl = d === "total" ? c + ec : t;
    g.alto = decl; g.alto_cuerpo = decl - ec; return;
  }
  if (d === "total") {            // capturas cuerpo + zoclo
    g.alto_cuerpo = c; g.altura_zoclo = z; g.alto = c + z + ec;
  } else if (d === "zoclo") {     // capturas total + cuerpo
    g.alto = t; g.alto_cuerpo = c; g.altura_zoclo = t - ec - c;
  } else {                        // "cuerpo": capturas total + zoclo
    g.alto = t; g.altura_zoclo = z; g.alto_cuerpo = t - ec - z;
  }""",
    "  const ec = espesorCubierta(g);\n  if (!hay) {")


def main() -> int:
    errores = []
    for archivo, viejo, nuevo, firma in CAMBIOS:
        ruta = RAIZ / archivo
        if not ruta.exists():
            errores.append(f"{archivo}: no existe")
            continue
        texto = ruta.read_text(encoding="utf-8")
        if firma in texto:
            print(f"  ya estaba  {archivo}  ({firma.strip()[:40]})")
            continue
        veces = texto.count(viejo)
        if veces != 1:
            errores.append(f"{archivo}: el ancla aparece {veces} veces, debía ser 1")
            continue
        ruta.write_text(texto.replace(viejo, nuevo, 1), encoding="utf-8")
        print(f"  aplicado   {archivo}")
    if errores:
        print("\nNo se aplicó nada de lo que falta:")
        for e in errores:
            print(f"  - {e}")
        return 1
    print("\nTodos los cambios de #101 y #102 están puestos.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
