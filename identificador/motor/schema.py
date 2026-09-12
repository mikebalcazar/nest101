"""Esquema de datos IDENTIFICADOR -> DESPIEZADOR t101.

Todas las medidas internas se guardan en MILIMETROS (mm) como entero/float.
Las coordenadas de pixel (bbox_px) son [x0, y0, x1, y1] sobre la imagen
rasterizada que se le mando al modelo de vision.
"""

from __future__ import annotations

from enum import Enum
from typing import List, Optional, Literal

from pydantic import BaseModel, Field


class TipoModulo(str, Enum):
    BASE = "base"            # gabinete bajo, apoyado en piso
    AEREO = "aereo"          # gabinete alto de muro
    TORRE = "torre"          # columna / alacena de piso a techo
    PANEL = "panel"          # panel ciego, remate, costado vista
    CUBIERTA = "cubierta"    # cubierta / barra
    ELECTRO = "electrodomestico"
    ZOCLO = "zoclo"
    OTRO = "otro"


class Unidad(str, Enum):
    MM = "mm"
    CM = "cm"
    M = "m"
    IN = "in"


FACTOR_MM = {Unidad.MM: 1.0, Unidad.CM: 10.0, Unidad.M: 1000.0, Unidad.IN: 25.4}


class Cota(BaseModel):
    """Una cota leida del plano."""
    texto: str = Field(description="Texto tal cual aparece en el plano, ej '0.60' o '600'")
    valor_mm: Optional[float] = Field(default=None, description="Valor normalizado a mm")
    orientacion: Literal["h", "v"] = "h"
    cadena: Optional[str] = Field(default=None, description="Id de la linea de cotas a la que pertenece")
    bbox_px: Optional[List[float]] = None
    confianza: float = 0.5


class Anotacion(BaseModel):
    texto: str
    tipo: Literal["clave_modulo", "acabado", "herraje", "nota", "titulo", "escala", "tabla", "otro"] = "otro"
    bbox_px: Optional[List[float]] = None
    confianza: float = 0.5


class TipoFrente(str, Enum):
    PUERTA = "puerta"
    CAJON = "cajon"
    PANEL_CIEGO = "panel_ciego"       # frente fijo, sin apertura
    ABIERTO = "abierto"               # nicho sin frente
    REGISTRO = "registro"             # tapa desmontable (electrico, plomeria)
    VIDRIO = "vidrio"
    PERSIANA = "persiana"


class Frente(BaseModel):
    """Lo que se ve por fuera del gabinete: puerta, cajon, panel, nicho.
    Un gabinete tiene 0, 1 o varios. Es la unidad que el plano dibuja."""
    tipo: TipoFrente = TipoFrente.PUERTA
    ancho_mm: Optional[float] = None
    alto_mm: Optional[float] = None
    x_rel_mm: Optional[float] = Field(default=None, description="Desde el costado izq del gabinete")
    z_rel_mm: Optional[float] = Field(default=None, description="Desde el piso del gabinete")
    bisagra: Optional[Literal["izq", "der", "sup", "inf"]] = Field(
        default=None, description="Lado de giro; null si no se puede leer del dibujo")
    jaladera: Optional[str] = Field(default=None, description="Tipo o posicion de jaladera si se ve")
    material: Optional[str] = None
    confianza: float = 0.5
    evidencia: Optional[str] = Field(default=None, description="Que se vio en el dibujo para decidirlo")


class Modulo(BaseModel):
    """CUERPO fabricable (gabinete). Sus frentes van en `frentes`."""
    clave: Optional[str] = Field(default=None, description="Clave/etiqueta del modulo en el plano, ej 'B-01'")
    tipo: TipoModulo = TipoModulo.OTRO
    ancho_mm: Optional[float] = None
    alto_mm: Optional[float] = None
    prof_mm: Optional[float] = None
    x_mm: Optional[float] = Field(default=None, description="Distancia desde el extremo izquierdo del alzado")
    z_mm: Optional[float] = Field(default=None, description="Altura del borde inferior sobre el piso terminado")
    frentes: List[Frente] = Field(default_factory=list)
    puertas: Optional[int] = None
    cajones: Optional[int] = None
    entrepanos: Optional[int] = None
    material: Optional[str] = None
    notas: Optional[str] = None
    bbox_px: Optional[List[float]] = None
    confianza: float = 0.5
    confianza_particion: Optional[float] = Field(
        default=None, description="Que tan seguro esta el engine de que ESTE es un cuerpo y no dos")
    fuente_particion: Optional[str] = Field(
        default=None, description="geometria | simbologia | heuristica | usuario")
    fuente_cotas: List[str] = Field(default_factory=list, description="Textos de cota usados para deducir medidas")

    @property
    def n_puertas(self) -> int:
        n = sum(1 for f in self.frentes if f.tipo == TipoFrente.PUERTA)
        return n or (self.puertas or 0)

    @property
    def n_cajones(self) -> int:
        n = sum(1 for f in self.frentes if f.tipo == TipoFrente.CAJON)
        return n or (self.cajones or 0)


class Alzado(BaseModel):
    id: str
    titulo: Optional[str] = None
    escala_texto: Optional[str] = None
    # --- solo cuando viene de una lamina vectorial (Revit/AutoCAD) ---
    vista_numero: Optional[str] = None
    tipo_vista: Optional[str] = None
    escala_den: Optional[int] = Field(default=None, description="Denominador: 25 => 1:25")
    mm_por_px: Optional[float] = Field(
        default=None, description="mm reales por pixel del recorte; permite medir la geometria")
    unidad_plano: Unidad = Unidad.MM
    altura_libre_mm: Optional[float] = Field(
        default=None, description="Altura libre del local (piso a plafon), si el plano la cota")
    ancho_total_mm: Optional[float] = None
    alto_total_mm: Optional[float] = Field(
        default=None, description="Alto total del mueble segun la cota general del alzado")
    modulos: List[Modulo] = Field(default_factory=list)
    cotas: List[Cota] = Field(default_factory=list)
    anotaciones: List[Anotacion] = Field(default_factory=list)
    bbox_px: Optional[List[float]] = None


class Aviso(BaseModel):
    nivel: Literal["info", "warn", "error"] = "warn"
    codigo: str
    mensaje: str
    ref: Optional[str] = None


class Documento(BaseModel):
    archivo: str
    pagina: int = 1
    dpi: int = 300
    modelo_vision: Optional[str] = None
    alzados: List[Alzado] = Field(default_factory=list)
    avisos: List[Aviso] = Field(default_factory=list)

    @property
    def requiere_revision(self) -> bool:
        return any(a.nivel in ("warn", "error") for a in self.avisos)


def json_schema_para_vision() -> dict:
    """Schema recortado que se le pasa al modelo como tool input."""
    return {
        "type": "object",
        "properties": {
            "alzados": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "id": {"type": "string"},
                        "titulo": {"type": "string"},
                        "escala_texto": {"type": "string"},
                        "unidad_plano": {"type": "string", "enum": ["mm", "cm", "m", "in"]},
                        "ancho_total_mm": {"type": "number"},
                        "alto_total_mm": {"type": "number"},
                        "altura_libre_mm": {"type": "number"},
                        "modulos": {
                            "type": "array",
                            "items": {
                                "type": "object",
                                "properties": {
                                    "clave": {"type": "string"},
                                    "tipo": {"type": "string", "enum": [t.value for t in TipoModulo]},
                                    "ancho_mm": {"type": "number"},
                                    "alto_mm": {"type": "number"},
                                    "prof_mm": {"type": "number"},
                                    "x_mm": {"type": "number"},
                                    "z_mm": {"type": "number"},
                                    "puertas": {"type": "integer"},
                                    "cajones": {"type": "integer"},
                                    "entrepanos": {"type": "integer"},
                                    "material": {"type": "string"},
                                    "notas": {"type": "string"},
                                    "bbox_px": {"type": "array", "items": {"type": "number"}},
                                    "confianza": {"type": "number"},
                                    "confianza_particion": {"type": "number"},
                                    "fuente_particion": {"type": "string",
                                        "enum": ["geometria", "simbologia", "heuristica", "usuario"]},
                                    "fuente_cotas": {"type": "array", "items": {"type": "string"}},
                                    "frentes": {
                                        "type": "array",
                                        "items": {
                                            "type": "object",
                                            "properties": {
                                                "tipo": {"type": "string",
                                                         "enum": [t.value for t in TipoFrente]},
                                                "ancho_mm": {"type": "number"},
                                                "alto_mm": {"type": "number"},
                                                "x_rel_mm": {"type": "number"},
                                                "z_rel_mm": {"type": "number"},
                                                "bisagra": {"type": "string",
                                                            "enum": ["izq", "der", "sup", "inf"]},
                                                "jaladera": {"type": "string"},
                                                "material": {"type": "string"},
                                                "confianza": {"type": "number"},
                                                "evidencia": {"type": "string"},
                                            },
                                            "required": ["tipo", "confianza"],
                                        },
                                    },
                                },
                                "required": ["tipo", "confianza"],
                            },
                        },
                        "cotas": {
                            "type": "array",
                            "items": {
                                "type": "object",
                                "properties": {
                                    "texto": {"type": "string"},
                                    "valor_mm": {"type": "number"},
                                    "orientacion": {"type": "string", "enum": ["h", "v"]},
                                    "cadena": {"type": "string"},
                                    "bbox_px": {"type": "array", "items": {"type": "number"}},
                                    "confianza": {"type": "number"},
                                },
                                "required": ["texto"],
                            },
                        },
                        "anotaciones": {
                            "type": "array",
                            "items": {
                                "type": "object",
                                "properties": {
                                    "texto": {"type": "string"},
                                    "tipo": {"type": "string", "enum": ["clave_modulo", "acabado", "herraje", "nota", "titulo", "escala", "tabla", "otro"]},
                                    "bbox_px": {"type": "array", "items": {"type": "number"}},
                                    "confianza": {"type": "number"},
                                },
                                "required": ["texto", "tipo"],
                            },
                        },
                    },
                    "required": ["id", "modulos"],
                },
            }
        },
        "required": ["alzados"],
    }
