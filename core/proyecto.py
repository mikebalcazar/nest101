"""Proyecto = catálogo de materiales + estándar constructivo + lista de gabinetes."""
import copy, json, os
from dataclasses import dataclass, field, asdict
from typing import List, Dict, Optional
from .config import Estandar, Material, CATALOGO_DEFAULT
from .modelos import (Gabinete, Frente, despiezar, alturas, AlturaInvalida,
                      espesor_cubierta)
from .pieza import agrupar, Pieza
from .nesting import nestear, Hoja


@dataclass
class Proyecto:
    nombre: str = "Proyecto sin nombre"
    cliente: str = ""
    catalogo: List[Material] = field(default_factory=lambda: [copy.copy(m) for m in CATALOGO_DEFAULT])
    estandar: Estandar = field(default_factory=Estandar)
    gabinetes: List[Gabinete] = field(default_factory=list)

    # ---------------- materiales ----------------
    def material(self, nombre: Optional[str]) -> Optional[Material]:
        if not nombre:
            return None
        for m in self.catalogo:
            if m.nombre == nombre:
                return m
        return None

    ROLES_MAT = ("mat_cuerpo", "mat_frente", "mat_respaldo", "mat_cajon",
                 "mat_fondo_cajon", "mat_cubierta", "mat_manguete")

    def estandar_de(self, g: Gabinete) -> Estandar:
        """Estándar del proyecto con lo que sobreescribe el gabinete."""
        std = copy.deepcopy(self.estandar)
        # #078 — los materiales se refrescan del CATÁLOGO por nombre. El
        # estándar guarda una copia de cada uno, y esa copia se queda vieja en
        # cuanto se edita el catálogo: se cambiaba el grosor del cubrecanto de
        # la melamina y las puertas seguían cortándose con el grosor anterior,
        # sin decir nada. El catálogo es la base del taller (#037), así que es
        # el que manda.
        for attr in self.ROLES_MAT:
            actual = getattr(std, attr, None)
            if actual is None:
                continue
            m = self.material(actual.nombre)
            if m:
                setattr(std, attr, copy.copy(m))
        for attr, nom in (("mat_cuerpo", g.mat_cuerpo),
                          ("mat_frente", g.mat_frente),
                          ("mat_respaldo", g.mat_respaldo)):
            m = self.material(nom)
            if m:
                setattr(std, attr, copy.copy(m))
        if g.altura_zoclo is not None:          # #001: override de zoclo
            std.altura_zoclo = float(g.altura_zoclo)
        if getattr(g, "vuelo_cubierta", None) is not None:      # #075
            std.vuelo_cubierta = float(g.vuelo_cubierta)
        return std

    def normalizar(self):
        """Deja coherentes las tres alturas de cada gabinete (#001).

        Escribe de vuelta total, cuerpo y zoclo, de modo que `alto` siempre sea
        la altura total real sin importar cuál campo esté derivado.

        #059 — `alturas()` devuelve el alto del GABINETE, y `g.alto` es el
        DECLARADO, que incluye la cubierta. Hay que volver a sumarla al
        guardar: sin eso, cada vez que se normaliza —o sea, en cada recálculo—
        el mueble se encoge otro espesor de plancha. Con piedra de 20, tres
        recálculos y el mueble perdió 6 cm sin que nadie tocara nada.
        """
        for g in self.gabinetes:
            std_g = self.estandar_de(g)
            try:
                total, cuerpo, hz = alturas(g, std_g)
            except AlturaInvalida:
                continue                        # se reporta al calcular
            g.alto = round(total + espesor_cubierta(g, std_g), 1)
            g.alto_cuerpo = round(cuerpo, 1)
            if g.tipo == "base" and g.con_zoclo and g.altura_zoclo is not None:
                g.altura_zoclo = round(hz, 1)
        return self

    def hojas_por_material(self) -> Dict[str, tuple]:
        d = {}
        for m in self.catalogo:
            d[m.nombre] = (m.largo_hoja, m.ancho_hoja)
        for std in [self.estandar] + [self.estandar_de(g) for g in self.gabinetes]:
            for m in (std.mat_cuerpo, std.mat_frente, std.mat_respaldo, std.mat_cubierta,
                      std.mat_cajon, std.mat_fondo_cajon,
                      getattr(std, "mat_manguete", None)):     # #067
                if m is None:
                    continue
                d.setdefault(m.nombre, (m.largo_hoja, m.ancho_hoja))
        return d

    def precios(self) -> Dict[str, Material]:
        d = {m.nombre: m for m in self.catalogo}
        for std in [self.estandar] + [self.estandar_de(g) for g in self.gabinetes]:
            for m in (std.mat_cuerpo, std.mat_frente, std.mat_respaldo, std.mat_cubierta,
                      std.mat_cajon, std.mat_fondo_cajon,
                      getattr(std, "mat_manguete", None)):     # #067
                if m is None:
                    continue
                d.setdefault(m.nombre, m)
        return d

    # ---------------- cálculo ----------------
    def cubiertas(self):
        """#028 — tramos de cubierta de toda la cocina, no de cada mueble."""
        from . import cubierta as CUB
        mat = self.material(self.estandar.mat_cubierta.nombre) or self.estandar.mat_cubierta
        return CUB.tramos(self.gabinetes, self.estandar, mat)

    def calcular(self):
        """Devuelve (piezas_agrupadas, hojas, solidos_por_gabinete)."""
        from . import iso as ISO
        todas: List[Pieza] = []
        solidos = {}
        for i, g in enumerate(self.gabinetes, start=1):
            std = self.estandar_de(g)
            pref = str(i)
            pz = despiezar(g, std, pref)
            for p in pz:
                p.cantidad *= max(1, g.cantidad)
            todas += pz
            solidos[g.nombre] = ISO.solidos_gabinete(g, std)
        # #028 — la cubierta de tablero se corta con el resto; la piedra y la
        # superficie sólida se piden por medida y no pasan por aquí.
        from .config import va_a_nesting
        from .pieza import Pieza as _P
        mat_cub = self.material(self.estandar.mat_cubierta.nombre) or self.estandar.mat_cubierta
        if mat_cub and va_a_nesting(mat_cub):
            for j, t in enumerate(self.cubiertas(), start=1):
                todas.append(_P(
                    codigo=f"C{j}", nombre="Cubierta", largo=t.largo, ancho=t.fondo,
                    espesor=t.espesor, material=t.material, cantidad=1,
                    canto=(self.estandar.canto_visible, 0, 0, 0),   # nariz al frente
                    mueble="Cubierta", veta=bool(mat_cub.veta),
                    nota=("sobre " + ", ".join(t.muebles))[:60]
                         + (f" · {t.nota}" if t.nota else "")))

        todas = agrupar(todas)
        # la veta la manda el catálogo: si el material la tiene, la pieza no rota
        pr = self.precios()
        for p in todas:
            m = pr.get(p.material)
            p.veta = bool(m and m.veta)
        std = copy.deepcopy(self.estandar)
        std.veta_respetada = True
        hojas = nestear(todas, std, self.hojas_por_material()) if todas else []
        return todas, hojas, solidos

    def costeo(self, piezas: List[Pieza], hojas: List[Hoja]) -> List[Dict]:
        pr = self.precios()
        agg: Dict[tuple, Dict] = {}
        for h in hojas:
            k = (h.material, h.espesor)
            a = agg.setdefault(k, {"material": h.material, "espesor": h.espesor,
                                   "hojas": 0, "m2_pieza": 0.0, "ml_canto": 0.0})
            a["hojas"] += 1
        for p in piezas:
            k = (p.material, p.espesor)
            a = agg.setdefault(k, {"material": p.material, "espesor": p.espesor,
                                   "hojas": 0, "m2_pieza": 0.0, "ml_canto": 0.0})
            a["m2_pieza"] += p.area_m2 * p.cantidad
            a["ml_canto"] += p.ml_canto * p.cantidad
        out = []
        for k, a in agg.items():
            m = pr.get(a["material"])
            ph = m.precio_hoja if m else 0.0
            pc = m.precio_canto_ml if m else 0.0
            a["precio_hoja"] = ph
            a["precio_canto_ml"] = pc
            a["costo_material"] = round(a["hojas"] * ph, 2)
            a["costo_canto"] = round(a["ml_canto"] * pc, 2)
            a["costo_total"] = round(a["costo_material"] + a["costo_canto"], 2)
            a["m2_pieza"] = round(a["m2_pieza"], 3)
            a["ml_canto"] = round(a["ml_canto"], 2)
            out.append(a)
        out.sort(key=lambda x: -x["costo_total"])
        return out

    # ---------------- persistencia ----------------
    def to_dict(self):
        return {
            "nombre": self.nombre,
            "cliente": self.cliente,
            "catalogo": [asdict(m) for m in self.catalogo],
            "estandar": asdict(self.estandar),
            "gabinetes": [_gab_dict(g) for g in self.gabinetes],
        }

    @staticmethod
    def from_dict(d) -> "Proyecto":
        p = Proyecto(nombre=d.get("nombre", "Proyecto"), cliente=d.get("cliente", ""))
        if "catalogo" in d:
            # #069 #078 — igual que el estándar: un catálogo guardado por otra
            # versión no puede tumbar la apertura por traer una llave de más ni
            # perder las nuevas por no traerlas.
            campos = set(Material.__dataclass_fields__)
            p.catalogo = [Material(**{k: v for k, v in m.items() if k in campos})
                          for m in d["catalogo"]]
        if "estandar" in d:
            # #069 — un archivo guardado con otra versión no puede apagar
            # opciones que esa versión no conocía: lo suyo se monta encima de
            # lo de fábrica y lo que falta se queda en su valor por omisión.
            p.estandar = Estandar.desde(d["estandar"])
        p.gabinetes = [_gab_obj(g) for g in d.get("gabinetes", [])]
        p.normalizar()
        return p

    def guardar(self, path):
        with open(path, "w", encoding="utf-8") as f:
            json.dump(self.to_dict(), f, indent=2, ensure_ascii=False)
        return path

    @staticmethod
    def abrir(path) -> "Proyecto":
        with open(path, encoding="utf-8") as f:
            return Proyecto.from_dict(json.load(f))


def _gab_dict(g: Gabinete):
    d = asdict(g)
    d["frentes"] = [asdict(f) for f in g.frentes]
    return d


def _gab_obj(d) -> Gabinete:
    d = dict(d)
    d["frentes"] = [Frente(**f) for f in d.get("frentes", [])]
    campos = {f for f in Gabinete.__dataclass_fields__}
    return Gabinete(**{k: v for k, v in d.items() if k in campos})
