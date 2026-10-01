"""Mete en `verificar.py` las comprobaciones de #101 y #102.

Va aparte del otro aplicador por una razón práctica: éste es el guardián —lo
que hace que los dos defectos no puedan volver— y se lee de corrido. Igual que
el otro, se ancla en texto que ya existe y se detiene si no lo encuentra.
"""

from __future__ import annotations

import pathlib
import sys

RAIZ = pathlib.Path(__file__).resolve().parent.parent

ANCLA_ALTURAS = '''chk(abs(c1 - c2) < 0.01 and t2 > t1,
    f"derivado=total: subir zoclo sube el total ({t1:.0f}→{t2:.0f}) y respeta el cuerpo ({c2:.0f})")
'''

BLOQUE_ALTURAS = '''
# ---------------- #102: la altura total no es la del cuerpo ----------------
# Mike, 30-sep: «en los cortes reinterpreta la altura total como la altura del
# gabinete, no le resta la altura del zoclo». Nacía en la pantalla del
# gabinete, que escribía `alto_cuerpo = alto` (el total declarado, plancha
# incluida); con el candado en «total», el motor tomaba ese número como cuerpo
# y el costado salía con la altura total. Lo de aquí mide las tres mitades:
# el archivo ya guardado se cura, la cuenta queda bien y recalcular no mueve el
# alto que tecleó el taller.
print("\\n== #102: el total no se confunde con el cuerpo ==")
from core.modelos import Gabinete as _Gb, espesor_cubierta as _ec_de
from core import iso as ISO

_sucio = _Gb(nombre="contaminado", tipo="base", ancho=600, alto=900.0, prof=600,
             alto_derivado="total", alto_cuerpo=900.0)
_t, _c, _z = alturas(_sucio, std)
chk(abs(_c - 900.0) < 0.01,
    f"el archivo viejo trae el defecto: sin curar el cuerpo sale {_c:.0f} (la altura total)")

_pr = Proyecto("t102"); _pr.estandar = std; _pr.gabinetes = [_sucio]
_pr.normalizar()
_t, _c, _z = alturas(_sucio, std)
_ec = _ec_de(_sucio, std)
_cos = [p for p in despiezar(_sucio, std, "1") if p.nombre == "Costado"][0]
chk(abs(_c - (900.0 - _ec - std.altura_zoclo)) < 0.01,
    f"curado: cuerpo {_c:.0f} = 900 − cubierta {_ec:.0f} − zoclo {std.altura_zoclo:.0f}")
chk(abs(_cos.largo - _c) < 0.01,
    f"el costado de la lista de corte mide el cuerpo: {_cos.largo:.0f}")
chk(abs(_sucio.alto - 900.0) < 0.01,
    f"curar no mueve el alto que tecleó el taller: {_sucio.alto:.0f}")

# y no se encoge: el defecto gemelo de #059 que seguía vivo en los muebles sin
# zoclo con el total derivado. Tres recálculos perdían un espesor de plancha
# cada uno.
_sin = _Gb(nombre="sin zoclo", tipo="base", ancho=600, alto=900.0, prof=600,
           con_zoclo=False, alto_derivado="total")
_pr2 = Proyecto("t102b"); _pr2.estandar = std; _pr2.gabinetes = [_sin]
for _ in range(3):
    _pr2.normalizar()
chk(abs(_sin.alto - 900.0) < 0.01,
    f"sin zoclo y total derivado: tras tres recálculos sigue en {_sin.alto:.0f} (no se encoge)")

# el barrido: 636 configuraciones de tipo, zoclo, cubierta, candado y overrides.
# Cada una tiene que cumplir las cuatro reglas a la vez.
_malos = []
import itertools as _it
for _tipo, _cz, _cc, _d, _ac, _hz in _it.product(
        ("base", "aereo"), (True, False), (True, False, None),
        ("cuerpo", "total", "zoclo"), (None, 780.0, 900.0), (None, 100.0, 150.0)):
    _g = _Gb(nombre="b", tipo=_tipo, ancho=600, alto=900.0, prof=600, con_zoclo=_cz,
             con_cubierta=_cc, alto_derivado=_d, alto_cuerpo=_ac, altura_zoclo=_hz)
    _etq = f"tipo={_tipo} zoclo={_cz} cub={_cc} candado={_d} cuerpo={_ac} hz={_hz}"
    try:
        _t, _c, _z = alturas(_g, std)
    except AlturaInvalida:
        continue                      # el juego no cierra y se rechaza: correcto
    if abs(_t - (_c + _z)) > 0.05:
        _malos.append(f"{_etq}: total {_t:.1f} ≠ cuerpo + zoclo")
    _cs = [p for p in despiezar(_g, std, "1") if p.nombre == "Costado"]
    if _cs and abs(_cs[0].largo - _c) > 0.05:
        _malos.append(f"{_etq}: costado {_cs[0].largo:.1f} ≠ cuerpo {_c:.1f}")
    _sol = ISO.solidos_gabinete(_g, std)
    if _sol and abs((max(s.z + s.dz for s in _sol) - min(s.z for s in _sol)) - _t) > 0.6:
        _malos.append(f"{_etq}: el 3D no mide el total {_t:.1f}")
    _p3 = Proyecto("bar"); _p3.estandar = std; _p3.gabinetes = [_g]
    _decl = float(_g.alto)
    _p3.normalizar(); _uno = (_g.alto, _g.alto_cuerpo, _g.altura_zoclo)
    _p3.normalizar()
    if _uno != (_g.alto, _g.alto_cuerpo, _g.altura_zoclo):
        _malos.append(f"{_etq}: recalcular dos veces mueve el mueble")
    if _d != "total" and abs(float(_g.alto) - _decl) > 0.05:
        _malos.append(f"{_etq}: el alto tecleado {_decl:.0f} quedó en {_g.alto:.0f}")
chk(not _malos,
    f"barrido de alturas: 636 configuraciones, {len(_malos)} incoherencias"
    + ("" if not _malos else "\\n         " + "\\n         ".join(_malos[:6])))
'''

ANCLA_PDF = "# ----------------------------------------------- #095 librerías del instalador"

BLOQUE_PDF = '''# ------------------------------------- #101 un isométrico por mueble, no el del primero
#
# Mike, 30-sep: «si exporto un proyecto completo, en el isométrico me coloca la
# misma imagen isométrica del primero en todos». reportlab guarda las imágenes
# **por nombre de archivo** y reutiliza la primera que vio: dos muebles con un
# gabinete del mismo nombre daban la misma ruta, y la página de conjunto tenía
# el nombre fijo para todos. Se mide por dentro del PDF: cada isométrico tiene
# que ser una imagen distinta.
print("\\n== #101: cada mueble con SU isométrico ==")
try:
    import hashlib as _hl, tempfile as _tf, os as _os              # noqa: E402
    import pypdfium2 as _fium                                      # noqa: E402
    from export import pdf as _PDF                                 # noqa: E402
    from core.proyecto import Proyecto as _Pr                      # noqa: E402

    _m1 = _Pr("Cocina"); _m1.estandar = std
    _m1.gabinetes = [_Gb(nombre="Gabinete 1", tipo="base", ancho=600, alto=900.0, prof=600)]
    _m2 = _Pr("Closet"); _m2.estandar = std
    _m2.gabinetes = [_Gb(nombre="Gabinete 1", tipo="aereo", ancho=1200, alto=700.0, prof=350)]
    _ruta = _os.path.join(_tf.mkdtemp(prefix="despz_v101_"), "proyecto.pdf")
    _PDF.exportar_proyecto([_m1, _m2], [], _ruta, proyecto="Prueba")

    # Se lee con pypdfium2 **a propósito**: es la librería que viaja dentro del
    # instalador, así que esta comprobación corre también en el armado, con el
    # mismo Python. Con una librería de sólo-pruebas se saltaría justo donde
    # importa.
    _isos = []
    _doc = _fium.PdfDocument(_ruta)
    for _i in range(len(_doc)):
        for _obj in _doc[_i].get_objects():
            if _obj.type != 3:                 # 3 = imagen
                continue
            _im = _obj.get_bitmap(render=False).to_pil()
            if _im.size[0] < 1000:             # el membrete, que sí va en todas
                continue
            _isos.append((_i + 1, _hl.sha256(_im.tobytes()).hexdigest()[:12]))
    chk(len(_isos) == 6, f"el PDF trae {len(_isos)} isométricos: conjunto, armado y despiece de cada mueble")
    _repes = [(a, b) for j, (a, hh) in enumerate(_isos) for (b, h2) in _isos[j + 1:] if hh == h2]
    chk(not _repes,
        "ningún isométrico se repite entre páginas"
        + ("" if not _repes else f" — repetidos en {_repes}"))
except ImportError as _e:                                          # noqa: BLE001
    print(f"  (sin pypdfium2 en esta máquina: la comprobación del PDF se salta — {_e})")

'''


def main() -> int:
    ruta = RAIZ / "verificar.py"
    texto = ruta.read_text(encoding="utf-8")
    if "#102: el total no se confunde con el cuerpo" in texto:
        print("  ya estaba  verificar.py")
        return 0
    for nombre, ancla in (("alturas", ANCLA_ALTURAS), ("PDF", ANCLA_PDF)):
        veces = texto.count(ancla)
        if veces != 1:
            print(f"  el ancla de {nombre} aparece {veces} veces, debía ser 1: no se tocó nada")
            return 1
    texto = texto.replace(ANCLA_ALTURAS, ANCLA_ALTURAS + BLOQUE_ALTURAS, 1)
    texto = texto.replace(ANCLA_PDF, BLOQUE_PDF + ANCLA_PDF, 1)
    ruta.write_text(texto, encoding="utf-8")
    print("  aplicado   verificar.py (las comprobaciones de #101 y #102)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
