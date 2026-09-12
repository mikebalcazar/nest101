"""#028 — Cubiertas.

Una cocina no lleva un pedazo de cubierta por mueble: lleva **tramos corridos**
sobre los muebles que están pegados. Este módulo agrupa los gabinetes bajos que
llevan cubierta en tramos, y parte cada tramo si no cabe en una placa del
material, dejando la junta anotada.

Qué NO hace, a propósito:
  · No manda la piedra ni la superficie sólida al nesting de tableros. Esas se
    piden por medida al proveedor (`config.va_a_nesting`). La cubierta de
    melamina sí, porque sale de un tablero como cualquier otra pieza.
  · No inventa recortes de tarja ni de parrilla: eso va en la nota del tramo,
    porque depende del modelo que compre el cliente.

#029 — la nariz es el **alto aparente del canto frontal**. Si es mayor que el
espesor del material, se pega un doblado por debajo, y ese doblado es material
extra que hay que pedir: se contabiliza en metros lineales.
"""
from dataclasses import dataclass, field
from typing import Dict, List, Optional

from .config import Estandar, Material, va_a_nesting
from .modelos import Gabinete, alturas, lleva_cubierta
from . import iso as ISO

TOLERANCIA = 3.0        # mm de separación entre muebles que aún cuenta como pegado


@dataclass
class Tramo:
    """Un pedazo de cubierta que se fabrica de una sola pieza."""
    material: str
    espesor: float
    largo: float                  # a lo largo del tramo
    fondo: float                  # de pared a nariz
    # La cubierta se APOYA sobre el mueble: `alto` es la cara de ABAJO, que es
    # donde termina el gabinete. El espesor suma. Un bajo de 880 con piedra de
    # 20 deja la superficie de trabajo a 900, que es como se mide en obra.
    alto: float
    x: float = 0.0                # esquina de la huella, en coordenadas de cocina
    z: float = 0.0
    rot: int = 0
    muebles: List[str] = field(default_factory=list)
    alto_nariz: float = 0.0
    ml_nariz: float = 0.0         # metros lineales de nariz (el frente del tramo)
    ml_doblado: float = 0.0       # material extra pegado bajo la nariz
    parte: int = 1                # de un tramo partido: 1 de 2, 2 de 2…
    partes: int = 1
    nota: str = ""

    @property
    def alto_lomo(self) -> float:
        """La cara de arriba: la altura de trabajo de la cocina."""
        return round(self.alto + self.espesor, 1)

    @property
    def area_m2(self) -> float:
        return self.largo * self.fondo / 1_000_000

    @property
    def eje_x(self) -> bool:
        return int(self.rot) % 180 != 90


# Hacia dónde da el frente —la cara de las puertas— según cómo esté girado el
# mueble. Sale de cómo `iso.colocar` gira las piezas: la puerta vive en y=0, y
# ese y=0 termina en un lado distinto del mundo según el giro.
#
#     0°   → el frente da a −z        180° → +z
#     90°  → +x                       270° → −x
#
# Esto es lo que la 0.8.0 no sabía: el vuelo de la cubierta se iba para atrás,
# contra la pared, en vez de volar por delante de las puertas.
#
# Desde #043 el vuelo ya no se suma aquí —viene dentro del fondo declarado— así
# que esta tabla queda para el resto del programa: es la que dice de qué lado
# está la cara de las puertas.
FRENTE = {0: (0, -1), 90: (1, 0), 180: (0, 1), 270: (-1, 0)}


def _clave_tramo(g: Gabinete, std: Estandar):
    """Dos muebles van en el mismo tramo si comparten línea, giro y altura.

    El giro se compara COMPLETO, no módulo 180: dos muebles espalda con espalda
    están en la misma línea pero miran a lados opuestos, y una sola plancha no
    puede volar hacia los dos frentes a la vez.
    """
    rot = int(g.rot) % 360
    x0, z0, x1, z1 = ISO.huella(g)
    total = alturas(g, std)[0]
    # la coordenada perpendicular al tramo, redondeada al milímetro
    perp = round(z0 if rot % 180 == 0 else x0, 1)
    return (rot, perp, round(total, 1))


def _largo_max(m: Material) -> float:
    """El lado mayor de la placa: es como se pide un tramo corrido."""
    return max(m.largo_hoja, m.ancho_hoja)


def tramos(gabinetes: List[Gabinete], std: Estandar,
           material: Optional[Material] = None) -> List[Tramo]:
    """Agrupa en tramos corridos los muebles que llevan cubierta. (#028)"""
    mat = material or std.mat_cubierta
    if mat is None:
        return []
    conjuntos: Dict[tuple, List[Gabinete]] = {}
    for g in gabinetes:
        if not lleva_cubierta(g):
            continue
        conjuntos.setdefault(_clave_tramo(g, std), []).append(g)

    salida: List[Tramo] = []
    for (rot, perp, total), grupo in sorted(conjuntos.items()):
        eje_x = rot % 180 == 0
        # se ordenan a lo largo del tramo y se van pegando los contiguos
        grupo.sort(key=lambda g: ISO.huella(g)[0] if eje_x else ISO.huella(g)[1])
        corridas: List[List[Gabinete]] = []
        for g in grupo:
            x0, z0, x1, z1 = ISO.huella(g)
            ini = x0 if eje_x else z0
            if corridas:
                px0, pz0, px1, pz1 = ISO.huella(corridas[-1][-1])
                fin_ant = px1 if eje_x else pz1
                if ini - fin_ant <= TOLERANCIA:
                    corridas[-1].append(g)
                    continue
            corridas.append([g])

        for corrida in corridas:
            salida.extend(_tramo_de(corrida, mat, std, eje_x, total, rot))
    return salida


def _tramo_de(corrida: List[Gabinete], mat: Material, std: Estandar,
              eje_x: bool, total: float, rot: int = 0) -> List[Tramo]:
    """Convierte una corrida de muebles en uno o más pedazos fabricables."""
    huellas = [ISO.huella(g) for g in corrida]
    x0 = min(h[0] for h in huellas)
    z0 = min(h[1] for h in huellas)
    x1 = max(h[2] for h in huellas)
    z1 = max(h[3] for h in huellas)

    nariz = max(float(std.alto_nariz or 0.0), 0.0)
    vl = float(std.voladizo_lateral or 0.0)

    # #043 — el vuelo YA ESTÁ dentro del fondo declarado del mueble: con
    # cubierta, esa medida es la de la plancha, y el cuerpo se cortó lo que
    # sobraba (`modelos.vuelo_de`). Así que la plancha ocupa la huella tal cual:
    # su filo cae donde empieza el mueble y su respaldo en la pared.
    #
    # Hasta la 0.9.0 se sumaba el vuelo AQUÍ, encima de la huella: el conjunto
    # crecía en vez de que el mueble se ajustara. Y con nariz se anulaba el
    # vuelo y el cuerpo se encogía por otro lado — dos reglas para lo mismo, que
    # es lo que hacía que al quitar la nariz nada regresara a su sitio.
    #
    # #039 sigue vigente para el voladizo lateral y para saber cuál cara es el
    # frente: 0° mira a −z, 90° a +x, 180° a +z, 270° a −x.
    if eje_x:
        largo = (x1 - x0) + 2 * vl
        fondo = (z1 - z0)
        px = x0 - vl
        pz = z0
    else:
        largo = (z1 - z0) + 2 * vl
        fondo = (x1 - x0)
        pz = z0 - vl
        px = x0

    doblado = max(0.0, nariz - mat.espesor)
    maximo = _largo_max(mat)
    n = max(1, int(-(-largo // maximo)))          # techo de la división
    if n == 1:
        largos = [largo]
    else:
        util = largo - (n - 1) * std.junta_cubierta
        largos = [round(util / n, 1)] * n

    nombres = [g.nombre for g in corrida]
    piezas: List[Tramo] = []
    avance = 0.0
    for i, L in enumerate(largos, start=1):
        nota = []
        if n > 1:
            nota.append(f"tramo partido: no cabe en una placa de {maximo:.0f} mm")
        if doblado > 0:
            nota.append(f"doblado de {doblado:.0f} mm bajo la nariz")
        if not va_a_nesting(mat):
            nota.append("se pide por medida, no entra al nesting")
        piezas.append(Tramo(
            material=mat.nombre, espesor=mat.espesor,
            largo=round(L, 1), fondo=round(fondo, 1), alto=round(total, 1),
            x=round(px + (avance if eje_x else 0.0), 1),
            z=round(pz + (0.0 if eje_x else avance), 1),
            rot=int(rot) % 360,
            muebles=nombres,
            alto_nariz=round(nariz or mat.espesor, 1),
            ml_nariz=round(L / 1000.0, 3),
            ml_doblado=round(L / 1000.0 if doblado > 0 else 0.0, 3),
            parte=i, partes=n, nota=" · ".join(nota),
        ))
        avance += L + std.junta_cubierta
    return piezas


def resumen(ts: List[Tramo]) -> List[dict]:
    """Totales por material, que es como se cotiza con el proveedor."""
    por: Dict[str, dict] = {}
    for t in ts:
        d = por.setdefault(t.material, {
            "material": t.material, "espesor": t.espesor, "tramos": 0,
            "m2": 0.0, "ml_nariz": 0.0, "ml_doblado": 0.0, "largo_total": 0.0,
        })
        d["tramos"] += 1
        d["m2"] += t.area_m2
        d["ml_nariz"] += t.ml_nariz
        d["ml_doblado"] += t.ml_doblado
        d["largo_total"] += t.largo
    for d in por.values():
        d["m2"] = round(d["m2"], 3)
        d["ml_nariz"] = round(d["ml_nariz"], 3)
        d["ml_doblado"] = round(d["ml_doblado"], 3)
        d["largo_total"] = round(d["largo_total"], 1)
    return list(por.values())
