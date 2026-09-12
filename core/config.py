"""Configuración paramétrica del estándar constructivo — DESPIEZADOR v0.1"""
from dataclasses import dataclass, field, asdict
from typing import Literal
import json

TipoEnsamble = Literal["minifix", "confirmat", "tarugo", "ranura"]


@dataclass
class Material:
    nombre: str
    espesor: float
    largo_hoja: float = 2440.0
    ancho_hoja: float = 1220.0
    precio_hoja: float = 0.0          # MXN por hoja
    precio_canto_ml: float = 0.0      # MXN por metro lineal de canto
    veta: bool = False                # True = material con veta direccional
    familia: str = "Melamina"         # Melamina / MDF / Triplay / Otro
    color: str = "#D9D2C5"            # #009: color en el 3D
    # #078 — el grosor del cubrecanto es de ESTE material, no del taller: una
    # melamina de puerta se cantea con 2 mm y el interior con 1. Y el grosor
    # cambia la medida de corte (#006), así que no es un dato decorativo.
    # 0 = el del estándar.
    espesor_canto: float = 0.0

    @property
    def m2_hoja(self) -> float:
        return self.largo_hoja * self.ancho_hoja / 1_000_000

    @property
    def precio_m2(self) -> float:
        return self.precio_hoja / self.m2_hoja if self.m2_hoja else 0.0


CATALOGO_DEFAULT = [
    Material("Melamina blanca 18mm", 18.0, 2440, 1220, 1150.0, 12.0, False, "Melamina", "#EDE9E1"),
    Material("Melamina color 18mm", 18.0, 2440, 1220, 1390.0, 16.0, False, "Melamina", "#7E8B99"),
    Material("Melamina madera 18mm", 18.0, 2440, 1220, 1620.0, 22.0, True, "Melamina", "#B98A52"),
    Material("Melamina blanca 15mm", 15.0, 2440, 1220, 980.0, 11.0, False, "Melamina", "#E6E2DA"),
    Material("MDF 6mm", 6.0, 2440, 1220, 420.0, 0.0, False, "MDF", "#B8A489"),
    Material("MDF 3mm", 3.0, 2440, 1220, 260.0, 0.0, False, "MDF", "#C2AF95"),
    Material("MDF 18mm (para laca)", 18.0, 2440, 1220, 1280.0, 0.0, False, "MDF", "#AE9A80"),
    Material("Triplay pino 18mm", 18.0, 2440, 1220, 1050.0, 18.0, True, "Triplay", "#D8B487"),
    # #028 — cubiertas. La «hoja» de piedra y de superficie sólida es el tamaño
    # de placa que vende el proveedor, no un tablero: no se acomodan en nesting,
    # se piden por medida. Los precios son de referencia y se editan en la app.
    Material("Piedra 20mm", 20.0, 3000, 1400, 0.0, 0.0, True, "Cubierta piedra", "#8E8B86"),
    Material("Superficie sólida 12mm", 12.0, 3680, 760, 0.0, 0.0, False,
             "Cubierta sólida", "#E8E4DC"),
    Material("Cubierta melamina 19mm", 19.0, 2440, 1220, 1490.0, 24.0, True,
             "Melamina", "#C9B79A"),
]

# #028 — qué familias NO se acomodan en hoja: se le piden al marmolista por
# medida. La melamina de cubierta sí entra al nesting, porque sale de un tablero.
FAMILIAS_SIN_NESTING = ("Cubierta piedra", "Cubierta sólida")


def va_a_nesting(m: Material) -> bool:
    return (m.familia or "") not in FAMILIAS_SIN_NESTING


@dataclass
class Estandar:
    # --- materiales ---
    mat_cuerpo: Material = field(default_factory=lambda: Material("Melamina blanca 18mm", 18.0, precio_hoja=1150.0, precio_canto_ml=12.0))
    mat_frente: Material = field(default_factory=lambda: Material("Melamina blanca 18mm", 18.0, precio_hoja=1150.0, precio_canto_ml=12.0))
    mat_respaldo: Material = field(default_factory=lambda: Material("MDF 6mm", 6.0, precio_hoja=420.0))
    mat_cajon: Material = field(default_factory=lambda: Material("Melamina blanca 15mm", 15.0, precio_hoja=980.0, precio_canto_ml=11.0))
    mat_fondo_cajon: Material = field(default_factory=lambda: Material("MDF 6mm", 6.0, precio_hoja=420.0))
    # #067 — el manguete del uñero es pieza de CUERPO, no de frente: va
    # atornillado entre costados y no se ve más que su canto. None = el del
    # cuerpo; se puede poner otro cuando el canto queda a la vista y se quiere
    # que combine con los frentes.
    mat_manguete: Material = None
    # #028 — cubierta
    mat_cubierta: Material = field(default_factory=lambda: Material(
        "Piedra 20mm", 20.0, 3000, 1400, 0.0, 0.0, True, "Cubierta piedra", "#8E8B86"))

    # --- ensamble ---
    ensamble: TipoEnsamble = "minifix"
    paso_sistema: float = 32.0          # sistema 32 mm
    offset_linea_frente: float = 37.0   # eje 1a linea de barrenos desde frente
    offset_linea_trasera: float = 37.0
    dia_minifix_costado: float = 8.0    # barreno tarugo/perno en costado
    dia_minifix_canto: float = 8.0
    dia_confirmat_pasado: float = 7.0
    dia_confirmat_canto: float = 5.0

    # --- respaldo ---
    respaldo_ranurado: bool = True
    # #065 — respaldo de DOS TRAVESAÑOS en vez de tablero entero, como la tapa.
    # Es para los muebles que caen donde pasan las instalaciones hidráulicas:
    # el hueco de en medio deja libre el paso de tubos y registros.
    respaldo_completo: bool = True
    ancho_travesano_respaldo: float = 100.0
    respaldo_interior_desde: float = 12.0   # #003: de este espesor en adelante va por dentro
    prof_ranura: float = 8.0
    offset_ranura: float = 12.0         # desde borde trasero al inicio de la ranura
    holgura_ranura: float = 0.5         # respaldo entra con juego

    # --- frentes ---
    holgura_perimetral: float = 1.5     # entre frente y borde de cuerpo
    holgura_entre_frentes: float = 3.0
    # #077 — el hueco entre el CANTO FRONTAL DEL COSTADO y la cara de atrás del
    # frente. Ahí viven la bisagra, el tope y el ajuste: pegado no cierra.
    # Sale del fondo declarado, igual que el vuelo (#043).
    holgura_frente_costado: float = 3.0
    frentes_sobrepuestos: bool = True

    # --- zoclo / patas ---
    altura_zoclo: float = 100.0
    retranqueo_zoclo: float = 55.0
    zoclo_desmontable: bool = True      # patas niveladoras + zoclo clipeado

    # --- colocación en la cocina (#004) ---
    altura_colgado_aereo: float = 1450.0    # base del aéreo sobre el piso
    iman_distancia: float = 80.0            # a esta distancia los muebles se pegan
    rejilla: float = 10.0                   # el arrastre cae a múltiplos de esto

    # --- entrepaños ---
    holgura_entrepano: float = 2.0      # total en ancho (1 mm por lado)
    retranqueo_entrepano: float = 20.0  # respecto a profundidad de cuerpo

    # --- cajones (corredera oculta / telescópica) ---
    holgura_corredera_lado: float = 12.7
    alto_caja_cajon: float = 90.0
    retranqueo_fondo_cajon: float = 12.0

    # --- fabricación CNC ---
    kerf: float = 3.2                   # diámetro de fresa
    # #076 — el disco de la seccionadora es más grueso que la fresa, y ese mm de
    # más, multiplicado por todos los cortes de una hoja, mueve el acomodo.
    # #084 — **3 mm de fábrica**, que es el disco del taller. Antes salía en 0
    # («usa el mismo que la fresa»), y ese default era una trampa: nadie va a
    # ajustes a corregir un número que la app ya llenó, así que todos los cortes
    # de sierra se calculaban con el kerf de la fresa —3.2— sin que nadie lo
    # hubiera escogido. Se puede cambiar; 0 sigue significando «el de la fresa».
    kerf_sierra: float = 3.0
    margen_hoja: float = 10.0
    separacion_piezas: float = 6.0
    veta_respetada: bool = False        # True = no rotar piezas

    # --- canto ---
    # --- cubierta (#028) y nariz (#029) ---
    vuelo_cubierta: float = 20.0        # cuánto sobresale por delante del frente
    voladizo_lateral: float = 0.0       # sobresale a los lados del tramo
    alto_nariz: float = 0.0             # 0 = el canto se ve del espesor del material
    perfil_nariz: str = "recta"         # recta | boleada | chaflán | doblada
    junta_cubierta: float = 3.0         # separación entre tramos que no caben en una placa

    # --- gola (#030) ---
    gola: bool = False
    # #042 — uñero: en vez de tirador, la puerta se corta a 45° arriba y encima
    # queda un manguete fijo. Los dedos entran en el chaflán.
    unero: bool = False
    alto_manguete: float = 50.0                  # el proyecto entero, se puede cambiar por mueble
    # #057 — el hueco entre la BASE DE LA NARIZ y el canto alto de la puerta.
    # Por ahí entran los dedos; el manguete se mide desde ese mismo punto.
    holgura_unero: float = 30.0
    alto_gola: float = 45.0             # el hueco que se le quita al frente de arriba

    canto_visible: float = 1.0
    canto_interior: float = 0.45
    descontar_canto: bool = True        # #006: la pieza se corta menos el canto

    def dump(self, path):
        with open(path, "w", encoding="utf-8") as f:
            json.dump(asdict(self), f, indent=2, ensure_ascii=False)

    @staticmethod
    def desde(d: dict) -> "Estandar":
        """#069 — un estándar guardado por CUALQUIER versión.

        Lo que trae el archivo se monta encima de lo de fábrica: las llaves que
        esa versión no conocía se quedan con su valor por omisión, y las que ya
        no existen se ignoran en vez de tronar. Un `None` tampoco pisa: llegaba
        de campos nuevos que la interfaz vieja mandaba en blanco, y `None` es
        falso — así se apagaba solo el respaldo completo al actualizar.
        """
        base = asdict(Estandar())
        if isinstance(d, dict):
            base.update({k: v for k, v in d.items() if k in base and v is not None})
        for k in ("mat_cuerpo", "mat_frente", "mat_respaldo", "mat_cajon",
                  "mat_fondo_cajon", "mat_cubierta", "mat_manguete"):
            if isinstance(base.get(k), dict):
                base[k] = Material(**{c: v for c, v in base[k].items()
                                      if c in Material.__dataclass_fields__})
        return Estandar(**base)

    @staticmethod
    def load(path) -> "Estandar":
        with open(path, encoding="utf-8") as f:
            d = json.load(f)
        for k in ("mat_cuerpo", "mat_frente", "mat_respaldo", "mat_cajon",
                  "mat_fondo_cajon", "mat_cubierta", "mat_manguete"):
            if isinstance(d.get(k), dict):
                d[k] = Material(**d[k])
        return Estandar(**d)
