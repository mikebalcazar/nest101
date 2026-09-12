"""Nesting de piezas en hojas — MaxRects (Best Short Side Fit) con rotación opcional."""
from dataclasses import dataclass, field
from typing import List, Dict, Tuple
from .pieza import Pieza, expandir
from .config import Estandar
from .modelos import GeometriaInvalida


@dataclass
class Colocacion:
    pieza: Pieza
    x: float
    y: float
    w: float
    h: float
    rotada: bool


@dataclass
class Hoja:
    idx: int
    material: str
    espesor: float
    ancho: float          # X
    alto: float           # Y
    colocaciones: List[Colocacion]
    # #076 — sólo los llena el acomodo de sierra lineal. En el de fresa quedan
    # vacíos: una fresa no corta por tiras, entra donde sea.
    tiras: List = field(default_factory=list)
    cortes: List = field(default_factory=list)

    @property
    def area_usada(self):
        return sum(c.w * c.h for c in self.colocaciones)

    @property
    def aprovechamiento(self):
        return self.area_usada / (self.ancho * self.alto)


class _MaxRects:
    def __init__(self, w, h):
        self.libres: List[Tuple[float, float, float, float]] = [(0.0, 0.0, w, h)]

    def insertar(self, w, h, permitir_rot):
        best = None
        for (fx, fy, fw, fh) in self.libres:
            for rot in ((False, w, h), (True, h, w)) if permitir_rot else ((False, w, h),):
                r, ww, hh = rot
                if ww <= fw + 1e-6 and hh <= fh + 1e-6:
                    ss = min(fw - ww, fh - hh)
                    ls = max(fw - ww, fh - hh)
                    key = (ss, ls)
                    if best is None or key < best[0]:
                        best = (key, fx, fy, ww, hh, r)
        if best is None:
            return None
        _, x, y, ww, hh, r = best
        self._partir(x, y, ww, hh)
        return x, y, ww, hh, r

    def _partir(self, x, y, w, h):
        nuevos = []
        for (fx, fy, fw, fh) in self.libres:
            if x >= fx + fw or x + w <= fx or y >= fy + fh or y + h <= fy:
                nuevos.append((fx, fy, fw, fh))
                continue
            if x > fx:
                nuevos.append((fx, fy, x - fx, fh))
            if x + w < fx + fw:
                nuevos.append((x + w, fy, fx + fw - (x + w), fh))
            if y > fy:
                nuevos.append((fx, fy, fw, y - fy))
            if y + h < fy + fh:
                nuevos.append((fx, y + h, fw, fy + fh - (y + h)))
        # eliminar contenidos
        out = []
        for i, a in enumerate(nuevos):
            if not any(i != j and _contiene(b, a) for j, b in enumerate(nuevos)):
                out.append(a)
        self.libres = [r for r in out if r[2] > 1 and r[3] > 1]


def _contiene(a, b):
    return (a[0] <= b[0] + 1e-6 and a[1] <= b[1] + 1e-6 and
            a[0] + a[2] >= b[0] + b[2] - 1e-6 and a[1] + a[3] >= b[1] + b[3] - 1e-6)


def nestear(piezas: List[Pieza], std: Estandar,
            hojas_por_material: Dict[str, Tuple[float, float]] = None) -> List[Hoja]:
    hojas_por_material = hojas_por_material or {}
    sep = std.separacion_piezas + std.kerf
    m = std.margen_hoja
    unid = expandir(piezas)
    grupos: Dict[Tuple[str, float], List[Pieza]] = {}
    for p in unid:
        grupos.setdefault((p.material, p.espesor), []).append(p)

    resultado, n = [], 0
    for (mat, esp), lote in grupos.items():
        W, H = hojas_por_material.get(mat, (std.mat_cuerpo.largo_hoja, std.mat_cuerpo.ancho_hoja))
        Wu, Hu = W - 2 * m, H - 2 * m
        lote.sort(key=lambda p: -(max(p.largo, p.ancho)))
        pend = list(lote)
        while pend:
            n += 1
            mr = _MaxRects(Wu, Hu)
            hoja = Hoja(n, mat, esp, W, H, [])
            resto = []
            for p in pend:
                w, h = p.largo + sep, p.ancho + sep
                rot_ok = not (std.veta_respetada and p.veta)
                r = mr.insertar(w, h, rot_ok)
                if r is None:
                    resto.append(p)
                    continue
                x, y, ww, hh, rotada = r
                hoja.colocaciones.append(
                    Colocacion(p, x + m, y + m, ww - sep, hh - sep, rotada))
            if not hoja.colocaciones:
                sob = pend[0]
                util_w, util_h = W - 2 * m, H - 2 * m
                raise GeometriaInvalida(          # #014: mensaje accionable
                    f"La pieza {sob.codigo} «{sob.nombre}» de {sob.mueble} mide "
                    f"{sob.largo:.0f}×{sob.ancho:.0f} mm y no cabe en una hoja de "
                    f"{mat} ({W:.0f}×{H:.0f}, útil {util_w:.0f}×{util_h:.0f} tras "
                    f"márgenes). Reduce el gabinete o usa una hoja más grande.")
            resultado.append(hoja)
            pend = resto
    return resultado


# =====================================================================
# #076 — Corte en SIERRA LINEAL (seccionadora), que no es el mismo corte
# =====================================================================
#
# Mike: «hay que agregar en los archivos de exportación corte en CNC de sierra
# lineal, para optimizar a ese tipo de despiece».
#
# El acomodo de arriba —MaxRects— es para **router/fresa**: la fresa entra donde
# sea y recorta el contorno de cada pieza, así que las piezas pueden quedar
# encajadas como un rompecabezas.
#
# Una **sierra lineal no puede hacer eso**. Cada corte atraviesa el tablero de
# lado a lado: no hay forma de parar a la mitad. A eso se le llama corte
# «guillotina», y obliga a un acomodo distinto:
#
#     1) el tablero se corta en TIRAS, a lo largo, de lado a lado
#     2) cada tira se trocea en piezas, con cortes de lado a lado de la tira
#     3) si a una pieza le sobra alto dentro de su tira, un corte más se lo quita
#
# Mandarle a la sierra el acomodo de la fresa es mandarle algo que **no se puede
# cortar**. Por eso son dos archivos y no uno con dos nombres.
#
# El precio de la restricción es real: la guillotina desperdicia un poco más que
# el rompecabezas. `nestear()` y `nestear_guillotina()` devuelven las mismas
# `Hoja`, así que las dos se pueden calcular y comparar hoja por hoja — y eso es
# lo que se enseña en pantalla, para que la decisión de en qué máquina cortar sea
# con el número enfrente y no de oído.


@dataclass
class Corte:
    """Un corte de lado a lado. `pos` se mide desde el borde de referencia."""
    n: int
    eje: str              # "y" = corta a lo largo (saca tiras) · "x" = trocea
    pos: float            # dónde cae el corte, en mm desde el borde
    desde: float          # de dónde a dónde llega el corte
    hasta: float
    etapa: int            # 1 = tiras · 2 = trozar la tira · 3 = despuntar la pieza
    nota: str = ""


@dataclass
class Tira:
    """Una tira: una banda del tablero, del ancho completo."""
    y: float
    alto: float
    piezas: List[Colocacion]


def _acomodo_tiras(lote, Wu, Hu, sep, veta_respetada, sep_min):
    """Acomoda un lote en tiras (guillotina de 2 niveles + despunte).

    Por alto decreciente, y cada pieza a la tira que le quede **más justa**, no
    a la primera donde quepa. La diferencia no es cosmética: con «la primera que
    quepa», una pieza de 99 se mete en una tira de 758 y deja 659 mm de despunte
    —basura— teniendo al lado una tira de 99 hecha a su medida.

    Devuelve (tiras, sobrantes). Nada de heurísticas de más: en un taller lo que
    importa es que la lista de cortes se pueda seguir sin pensarle.
    """
    tiras: List[Tira] = []
    usado_y = 0.0
    sobra = []
    for p in lote:
        w, h = p.largo + sep, p.ancho + sep
        rot_ok = not (veta_respetada and p.veta)
        mejor = None
        for t in tiras:
            for rot, ww, hh in ((False, w, h), (True, h, w)) if rot_ok else ((False, w, h),):
                if hh > t.alto + 1e-6 or ww > Wu + 1e-6:
                    continue
                x = sum(c.w + sep for c in t.piezas)
                if x + ww > Wu + 1e-6:
                    continue
                # lo que sobraría de alto: mientras menos, mejor
                sobra_alto = t.alto - hh
                if mejor is None or sobra_alto < mejor[0]:
                    mejor = (sobra_alto, t, x, ww, hh, rot)
        # ...pero meterla en una tira demasiado alta es peor que abrir una tira
        # nueva a su medida. Ordenadas por alto decreciente, cuando llega la
        # primera pieza baja **sólo existen tiras altas**: si se acepta la mejor
        # de ésas sin más, la tira de su medida no se abre nunca y cada pieza
        # baja se paga con su despunte. Se acepta la tira existente sólo si lo
        # que sobra es poco; si no, se abre una nueva mientras quede tablero.
        if mejor is not None:
            _s, t, x, ww, hh, rot = mejor
            cabe_nueva = usado_y + min(h, w if rot_ok else h) <= Hu + 1e-6
            if _s <= 0.12 * t.alto + 8 or not cabe_nueva:
                t.piezas.append(Colocacion(p, x, t.y, ww - sep, hh - sep, rot))
                continue
        # tira nueva: se elige la orientación que deje la tira más baja
        opciones = [(h, w, False)]
        if rot_ok:
            opciones.append((w, h, True))
        opciones = [(hh, ww, r) for hh, ww, r in opciones if ww <= Wu + 1e-6]
        if not opciones:
            sobra.append(p)
            continue
        hh, ww, r = min(opciones, key=lambda o: o[0])
        if usado_y + hh > Hu + 1e-6:
            sobra.append(p)
            continue
        t = Tira(usado_y, hh, [Colocacion(p, 0.0, usado_y, ww - sep, hh - sep, r)])
        tiras.append(t)
        usado_y += hh
    return tiras, sobra


def _cortes_de(tiras: List[Tira], Wu, Hu, m, sep) -> List[Corte]:
    """La secuencia de cortes, en el orden en que se hacen en la máquina."""
    cortes, n = [], 0
    for i, t in enumerate(tiras, start=1):
        n += 1
        cortes.append(Corte(n, "y", round(m + t.y + t.alto - sep, 1), m, m + Wu,
                            1, f"tira {i} · {t.alto - sep:.0f} mm de ancho"))
    for i, t in enumerate(tiras, start=1):
        x = 0.0
        for j, c in enumerate(t.piezas, start=1):
            x += c.w
            n += 1
            cortes.append(Corte(n, "x", round(m + x, 1), round(m + t.y, 1),
                                round(m + t.y + t.alto - sep, 1), 2,
                                f"tira {i} · pieza {c.pieza.codigo}"))
            x += sep
        # despunte: lo que le sobra de alto a cada pieza dentro de su tira
        for c in t.piezas:
            if t.alto - sep - c.h > 1.0:
                n += 1
                cortes.append(Corte(n, "y", round(m + c.y + c.h, 1),
                                    round(m + c.x, 1), round(m + c.x + c.w, 1), 3,
                                    f"despunte de {c.pieza.codigo} "
                                    f"({t.alto - sep - c.h:.0f} mm)"))
    return cortes


def nestear_guillotina(piezas: List[Pieza], std: Estandar,
                       hojas_por_material: Dict[str, Tuple[float, float]] = None
                       ) -> List[Hoja]:
    """Acomodo cortable en sierra lineal: sólo cortes de lado a lado."""
    hojas_por_material = hojas_por_material or {}
    kerf = float(getattr(std, "kerf_sierra", 0) or std.kerf)
    sep = std.separacion_piezas + kerf
    m = std.margen_hoja
    unid = expandir(piezas)
    grupos: Dict[Tuple[str, float], List[Pieza]] = {}
    for p in unid:
        grupos.setdefault((p.material, p.espesor), []).append(p)

    resultado, n = [], 0
    for (mat, esp), lote in grupos.items():
        W, H = hojas_por_material.get(mat, (std.mat_cuerpo.largo_hoja, std.mat_cuerpo.ancho_hoja))
        Wu, Hu = W - 2 * m, H - 2 * m
        # por alto decreciente: es lo que hace que las tiras salgan parejas
        lote.sort(key=lambda p: (-(p.ancho), -(p.largo)))
        pend = list(lote)
        while pend:
            tiras, sobra = _acomodo_tiras(pend, Wu, Hu, sep,
                                          std.veta_respetada, std.separacion_piezas)
            if not tiras:
                sob = pend[0]
                raise GeometriaInvalida(
                    f"La pieza {sob.codigo} «{sob.nombre}» de {sob.mueble} mide "
                    f"{sob.largo:.0f}×{sob.ancho:.0f} mm y no cabe en una hoja de "
                    f"{mat} ({W:.0f}×{H:.0f}) cortada en sierra lineal. "
                    f"Reduce el gabinete o usa una hoja más grande.")
            n += 1
            hoja = Hoja(n, mat, esp, W, H, [])
            for t in tiras:
                for c in t.piezas:
                    c.x += m
                    c.y += m
                    hoja.colocaciones.append(c)
            hoja.tiras = tiras
            hoja.cortes = _cortes_de(tiras, Wu, Hu, m, sep)
            resultado.append(hoja)
            pend = sobra
    return resultado
