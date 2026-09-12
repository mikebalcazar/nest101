"""Motor de ambiguedades: lo que el plano no dice y el despiece si necesita.

En vez de inventar, IDENTIFICADOR junta lo que no pudo resolver y lo convierte en
PREGUNTAS tipadas. El plugin del DESPIEZADOR las pinta como cuadro de dialogo, el
usuario contesta, y `aplicar()` mete las respuestas al modelo. Cada respuesta puede
guardarse en el perfil del despacho para no volver a preguntar lo mismo.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field, asdict
from typing import Any, Dict, List, Literal, Optional

from .schema import Alzado, Documento, Modulo, TipoFrente, TipoModulo
from .validate import MAX_PUERTAS_POR_CUERPO

UMBRAL_PARTICION = 0.75
UMBRAL_MODULO = 0.6

# defaults del taller: se precargan en el dialogo, el usuario solo confirma
PROF_DEFAULT_MM = {
    TipoModulo.BASE: 600.0, TipoModulo.AEREO: 320.0, TipoModulo.TORRE: 600.0,
    TipoModulo.CUBIERTA: 620.0, TipoModulo.ZOCLO: 550.0, TipoModulo.PANEL: 19.0,
}
ESPESOR_DEFAULT_MM = 19.0


@dataclass
class Opcion:
    id: str
    label: str
    detalle: str = ""
    valor: Any = None
    recomendada: bool = False


@dataclass
class Pregunta:
    id: str
    tipo: Literal["particion", "medida", "material", "frente"]
    titulo: str
    detalle: str
    ref: Optional[str] = None                  # clave del modulo al que aplica
    alzado: Optional[str] = None
    formato: Literal["opcion", "numero", "texto"] = "opcion"
    unidad: Optional[str] = None
    opciones: List[Opcion] = field(default_factory=list)
    valor_default: Any = None
    evidencia: Optional[str] = None
    impacto: Optional[str] = None
    obligatoria: bool = True
    aprendible: bool = False                   # ¿tiene sentido guardarla en el perfil?

    def dict(self) -> dict:
        d = asdict(self)
        d["opciones"] = [asdict(o) for o in self.opciones]
        return d


# --------------------------------------------------------------- generacion
def _cuerpos_minimos(ancho: float, n_puertas: int) -> int:
    """Cuantos cuerpos hacen falta como minimo: manda la regla de 2 puertas."""
    por_puertas = -(-n_puertas // MAX_PUERTAS_POR_CUERPO) if n_puertas else 1
    por_ancho = 1 if ancho <= 1200 else 2
    return max(1, por_puertas, por_ancho)


def _particiones_alternas(ancho: float, n_puertas: int = 0) -> List[Opcion]:
    """Formas razonables de partir un pano de `ancho` mm.
    Nunca ofrece una que deje mas de 2 puertas en un cuerpo."""
    minimo = _cuerpos_minimos(ancho, n_puertas)
    ops = []
    for n in (1, 2, 3, 4):
        if ancho / n < 300:
            break
        if n_puertas and n_puertas / n > MAX_PUERTAS_POR_CUERPO:
            continue                      # dejaria un cuerpo con 3+ puertas
        p = f", {n_puertas // n} puerta(s) cada uno" if n_puertas and n_puertas % n == 0 else ""
        ops.append(Opcion(
            id=str(n),
            label=(f"1 cuerpo de {ancho:.0f} mm" if n == 1
                   else f"{n} cuerpos de {ancho/n:.0f} mm"),
            detalle=("Un solo gabinete; las juntas que se ven son puertas." + p if n == 1
                     else f"El pano son {n} gabinetes iguales pegados{p}."),
            valor={"cuerpos": n}, recomendada=(n == minimo)))
    return ops


def _preguntas_particion(a: Alzado) -> List[Pregunta]:
    out = []
    for i, m in enumerate(a.modulos):
        if m.tipo in (TipoModulo.CUBIERTA, TipoModulo.ZOCLO, TipoModulo.ELECTRO):
            continue
        conf = m.confianza_particion if m.confianza_particion is not None else m.confianza
        ancho = m.ancho_mm or 0
        excede = m.n_puertas > MAX_PUERTAS_POR_CUERPO
        if conf >= UMBRAL_PARTICION and ancho <= 1200 and not excede:
            continue
        ref = m.clave or f"{a.id}#{i+1}"
        nf = len(m.frentes) or (m.puertas or 0) + (m.cajones or 0)
        out.append(Pregunta(
            id=f"part::{a.id}::{ref}", tipo="particion", ref=ref, alzado=a.id,
            titulo=f"{ref}: ¿es un cuerpo de {ancho:.0f} mm o son varios?",
            detalle=((f"El pano mide {ancho:.0f} mm y trae {nf} frente(s). "
                      "De esto depende cuantos laterales y fondos salen al despiece.")
                     + (f" Trae {m.n_puertas} puertas y el taller usa maximo "
                        f"{MAX_PUERTAS_POR_CUERPO} por cuerpo: hay que partirlo."
                        if excede else "")),
            opciones=_particiones_alternas(ancho, m.n_puertas),
            valor_default={"cuerpos": _cuerpos_minimos(ancho, m.n_puertas)},
            evidencia=(m.fuente_particion or "sin evidencia geometrica")
                      + f" (confianza {conf:.2f})",
            impacto="Cambia el numero de laterales, fondos y entrepanos del despiece.",
            aprendible=True))
    return out


NOMBRE_TIPO = {TipoModulo.BASE: "gabinetes bajos", TipoModulo.AEREO: "aereos",
               TipoModulo.TORRE: "torres", TipoModulo.CUBIERTA: "la cubierta",
               TipoModulo.ZOCLO: "el zoclo", TipoModulo.PANEL: "los paneles"}


def _preguntas_medida(a: Alzado) -> List[Pregunta]:
    out = []
    # la profundidad se pregunta UNA vez por tipo, no modulo por modulo:
    # en la practica todos los bajos de un mueble llevan la misma.
    sin_prof: Dict[TipoModulo, List[str]] = {}
    for i, m in enumerate(a.modulos):
        ref = m.clave or f"{a.id}#{i+1}"
        if m.prof_mm is None and m.tipo in PROF_DEFAULT_MM:
            sin_prof.setdefault(m.tipo, []).append(ref)
    for tipo, refs in sin_prof.items():
        d = PROF_DEFAULT_MM[tipo]
        out.append(Pregunta(
            id=f"prof::{a.id}::tipo::{tipo.value}", tipo="medida",
            ref=", ".join(refs), alzado=a.id,
            titulo=f"Profundidad de {NOMBRE_TIPO.get(tipo, tipo.value)}"
                   + (f" ({len(refs)} elementos)" if len(refs) > 1 else ""),
            detalle="El alzado no cota la profundidad; va en la planta o en el corte. "
                    f"Aplica a: {', '.join(refs)}.",
            formato="numero", unidad="mm", valor_default=d,
            evidencia="default del catalogo Taller 101",
            impacto="Define el ancho de laterales, fondo y entrepanos.",
            aprendible=True))

    for i, m in enumerate(a.modulos):
        ref = m.clave or f"{a.id}#{i+1}"
        if m.alto_mm is None and m.tipo not in (TipoModulo.ELECTRO,):
            out.append(Pregunta(
                id=f"alto::{a.id}::{ref}", tipo="medida", ref=ref, alzado=a.id,
                titulo=f"{ref}: altura",
                detalle="No se pudo leer del alzado.",
                formato="numero", unidad="mm", valor_default=None,
                impacto="Sin altura no se puede despiezar el cuerpo."))
        if m.ancho_mm is None:
            out.append(Pregunta(
                id=f"ancho::{a.id}::{ref}", tipo="medida", ref=ref, alzado=a.id,
                titulo=f"{ref}: ancho",
                detalle="No se pudo leer del alzado.",
                formato="numero", unidad="mm", valor_default=None,
                impacto="Sin ancho no se puede despiezar el cuerpo."))
    return out


# clave de acabado del plano: WD01, SS01, SE-03, PF-04, AS-10...
RE_CLAVE = re.compile(r"^[A-Z]{1,3}[-_ ]?\d{1,3}$")


# el plano tambien deja materiales abiertos: "MDF o triplay de 18 mm", "color a definir"
RE_ABIERTO = re.compile(r"\ba definir\b|\bpor definir\b|\bo similar\b|\s+o\s+|/", re.I)


def es_clave_sin_resolver(valor: str) -> bool:
    """'WD01' es una clave del plano y 'MDF o triplay de 18 mm' es una decision que el
    plano dejo abierta: las dos hay que amarrarlas al catalogo antes de despiezar.
    'MDF chapa nogal' ya es un material cerrado."""
    v = valor.strip()
    return bool(RE_CLAVE.match(v) or RE_ABIERTO.search(v))


def _preguntas_material(a: Alzado, catalogo: Optional[Dict[str, str]] = None) -> List[Pregunta]:
    """Las claves del plano (WD01, SS01) hay que amarrarlas al catalogo del taller."""
    catalogo = catalogo or {}
    claves: Dict[str, List[str]] = {}
    for i, m in enumerate(a.modulos):
        ref = m.clave or f"{a.id}#{i+1}"
        for valor in [m.material] + [f.material for f in m.frentes]:
            if valor and valor not in catalogo and es_clave_sin_resolver(valor):
                refs = claves.setdefault(valor, [])
                if ref not in refs:
                    refs.append(ref)
    out = []
    for clave, refs in sorted(claves.items()):
        out.append(Pregunta(
            id=f"mat::{a.id}::{clave}", tipo="material", ref=clave, alzado=a.id,
            titulo=f"Clave «{clave}»: ¿que material es?",
            detalle=(f"Aparece en {len(refs)} elemento(s): {', '.join(refs[:6])}"
                     + ("..." if len(refs) > 6 else "")
                     + ". La tabla de acabados normalmente va en otra lamina."),
            formato="texto",
            valor_default=None,
            opciones=[Opcion(id="mel19", label="Melamina 19 mm", valor={"material": "Melamina", "espesor_mm": 19}),
                      Opcion(id="mel16", label="Melamina 16 mm", valor={"material": "Melamina", "espesor_mm": 16}),
                      Opcion(id="mdf19", label="MDF 19 mm lacado", valor={"material": "MDF lacado", "espesor_mm": 19}),
                      Opcion(id="chapa19", label="MDF 19 mm chapa de madera", valor={"material": "MDF chapa", "espesor_mm": 19}),
                      Opcion(id="otro", label="Otro / escribirlo", valor=None)],
            evidencia="clave leida del plano",
            impacto="Define espesor de tablero, canto y costo.",
            aprendible=True))
    return out


def _preguntas_frente(a: Alzado) -> List[Pregunta]:
    out = []
    for i, m in enumerate(a.modulos):
        ref = m.clave or f"{a.id}#{i+1}"
        for j, f in enumerate(m.frentes):
            if f.tipo == TipoFrente.PUERTA and f.bisagra is None:
                out.append(Pregunta(
                    id=f"bis::{a.id}::{ref}::{j}", tipo="frente", ref=ref, alzado=a.id,
                    titulo=f"{ref}, frente {j+1}: lado de bisagra",
                    detalle="El alzado no dibuja el sentido de apertura.",
                    opciones=[Opcion(id="izq", label="Bisagra a la izquierda", valor="izq"),
                              Opcion(id="der", label="Bisagra a la derecha", valor="der"),
                              Opcion(id="pend", label="Lo defino en taller", valor=None,
                                     recomendada=True)],
                    valor_default=None, obligatoria=False,
                    impacto="Solo afecta el barrenado, no el corte."))
    return out


def generar(doc: Documento, catalogo_materiales: Optional[Dict[str, str]] = None,
            incluir_opcionales: bool = True) -> List[Pregunta]:
    """Todas las preguntas que hay que resolver antes de mandar a DESPIEZADOR."""
    preguntas: List[Pregunta] = []
    for a in doc.alzados:
        preguntas += _preguntas_particion(a)
        preguntas += _preguntas_medida(a)
        preguntas += _preguntas_material(a, catalogo_materiales)
        if incluir_opcionales:
            preguntas += _preguntas_frente(a)
    orden = {"particion": 0, "medida": 1, "material": 2, "frente": 3}
    preguntas.sort(key=lambda p: (orden[p.tipo], not p.obligatoria, p.id))
    return preguntas


# ---------------------------------------------------------------- aplicacion
def _partir(m: Modulo, n: int) -> List[Modulo]:
    if n <= 1 or not m.ancho_mm:
        return [m]
    ancho = m.ancho_mm / n
    frentes = m.frentes
    salida = []
    for k in range(n):
        nuevo = m.model_copy(deep=True)
        nuevo.clave = f"{m.clave or 'M'}-{k+1}"
        nuevo.ancho_mm = round(ancho, 1)
        nuevo.x_mm = None if m.x_mm is None else round(m.x_mm + k * ancho, 1)
        nuevo.fuente_particion = "usuario"
        nuevo.confianza_particion = 1.0
        x0, x1 = k * ancho, (k + 1) * ancho
        nuevo.frentes = [f for f in frentes
                         if f.x_rel_mm is None or x0 - 1 <= f.x_rel_mm < x1 - 1]
        for f in nuevo.frentes:
            if f.x_rel_mm is not None:
                f.x_rel_mm = round(f.x_rel_mm - x0, 1)
        salida.append(nuevo)
    return salida


def _unir(modulos: List[Modulo]) -> Modulo:
    base = modulos[0].model_copy(deep=True)
    base.ancho_mm = sum(m.ancho_mm or 0 for m in modulos)
    base.frentes = [f for m in modulos for f in m.frentes]
    base.fuente_particion = "usuario"
    base.confianza_particion = 1.0
    return base


def aplicar(doc: Documento, respuestas: Dict[str, Any],
            catalogo_materiales: Optional[Dict[str, dict]] = None) -> Documento:
    """Mete las respuestas del dialogo al modelo. `respuestas` = {id_pregunta: valor}."""
    catalogo_materiales = catalogo_materiales or {}
    for a in doc.alzados:
        nuevos: List[Modulo] = []
        for i, m in enumerate(a.modulos):
            ref = m.clave or f"{a.id}#{i+1}"
            r = respuestas.get(f"part::{a.id}::{ref}")
            piezas = [m]
            if isinstance(r, dict) and r.get("cuerpos"):
                piezas = _partir(m, int(r["cuerpos"]))
            for p in piezas:
                v = respuestas.get(f"prof::{a.id}::tipo::{p.tipo.value}")
                if v is None:
                    v = respuestas.get(f"prof::{a.id}::{ref}")
                if v is not None:
                    p.prof_mm = float(v)
                v = respuestas.get(f"alto::{a.id}::{ref}")
                if v is not None:
                    p.alto_mm = float(v)
                v = respuestas.get(f"ancho::{a.id}::{ref}")
                if v is not None and len(piezas) == 1:
                    p.ancho_mm = float(v)
                if p.material:
                    mat = respuestas.get(f"mat::{a.id}::{p.material}")
                    if isinstance(mat, dict):
                        p.material = mat.get("material", p.material)
                    elif isinstance(mat, str) and mat:
                        p.material = mat
                for j, f in enumerate(p.frentes):
                    b = respuestas.get(f"bis::{a.id}::{ref}::{j}")
                    if b:
                        f.bisagra = b
                    if f.material:
                        mat = respuestas.get(f"mat::{a.id}::{f.material}")
                        if isinstance(mat, dict):
                            f.material = mat.get("material", f.material)
                        elif isinstance(mat, str) and mat:
                            f.material = mat
            nuevos += piezas
        a.modulos = nuevos
    return doc


def para_perfil(preguntas: List[Pregunta], respuestas: Dict[str, Any]) -> List[dict]:
    """Convierte las respuestas en ejemplos para el perfil del despacho."""
    out = []
    idx = {p.id: p for p in preguntas}
    for pid, val in respuestas.items():
        p = idx.get(pid)
        if not p or not p.aprendible:
            continue
        out.append({"tipo": p.tipo, "contexto": p.titulo,
                    "correccion": str(val), "evidencia": p.evidencia})
    return out
