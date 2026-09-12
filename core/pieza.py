"""Piezas y operaciones de maquinado."""
from dataclasses import dataclass, field
from typing import List, Literal, Tuple

Cara = Literal["A", "B", "canto_L", "canto_R", "canto_sup", "canto_inf"]


@dataclass
class Barreno:
    x: float
    y: float
    dia: float
    prof: float
    cara: Cara = "A"
    nota: str = ""


@dataclass
class Ranura:
    """Ranura recta definida por dos puntos en el plano de la pieza."""
    x1: float
    y1: float
    x2: float
    y2: float
    ancho: float
    prof: float
    nota: str = ""


@dataclass
class Pieza:
    codigo: str            # ej. 1.01 (#011)
    nombre: str
    largo: float           # eje X en el despiece — MEDIDA DE CORTE (#006)
    ancho: float           # eje Y — medida de corte
    espesor: float
    material: str
    cantidad: int = 1
    # canto: (largo_inf, largo_sup, ancho_izq, ancho_der) espesor de canto en mm, 0 = sin canto
    canto: Tuple[float, float, float, float] = (0, 0, 0, 0)
    veta: bool = False     # True = respetar dirección de veta (largo = veta)
    barrenos: List[Barreno] = field(default_factory=list)
    ranuras: List[Ranura] = field(default_factory=list)
    mueble: str = ""
    nota: str = ""
    # #058 — cantos que van cortados a 45° despues del corte recto, con los
    # mismos indices que `canto`: (inf, sup, izq, der). Se corta como cualquier
    # panel y el chaflan se hace en la tupi, pero tiene que llegar escrito y
    # dibujado, o en el taller sale una puerta recta.
    chaflan: Tuple[bool, bool, bool, bool] = (False, False, False, False)
    # #006: medida terminada (con el cubrecanto pegado). None = igual al corte
    largo_final: float = None
    ancho_final: float = None

    @property
    def area_m2(self) -> float:
        return self.largo * self.ancho / 1_000_000

    @property
    def ml_canto(self) -> float:
        c = self.canto
        ml = 0.0
        if c[0]: ml += self.largo
        if c[1]: ml += self.largo
        if c[2]: ml += self.ancho
        if c[3]: ml += self.ancho
        return ml / 1000

    @property
    def terminado(self):
        return (self.largo_final if self.largo_final is not None else self.largo,
                self.ancho_final if self.ancho_final is not None else self.ancho)

    def clave_agrupacion(self):
        return (self.codigo, self.nombre, round(self.largo, 1), round(self.ancho, 1),
                self.espesor, self.material, self.canto)


def agrupar(piezas: List[Pieza]) -> List[Pieza]:
    """Consolida piezas idénticas sumando cantidades."""
    out = {}
    for p in piezas:
        k = p.clave_agrupacion()
        if k in out:
            out[k].cantidad += p.cantidad
        else:
            import copy
            out[k] = copy.deepcopy(p)
    return list(out.values())


def expandir(piezas: List[Pieza]) -> List[Pieza]:
    """Una instancia por unidad (para nesting)."""
    import copy
    out = []
    for p in piezas:
        for i in range(p.cantidad):
            q = copy.deepcopy(p)
            q.cantidad = 1
            q.nota = p.nota
            out.append(q)
    return out
