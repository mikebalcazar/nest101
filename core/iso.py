"""Generación de sólidos 3D del gabinete y proyección isométrica.

Sistema de coordenadas del gabinete (mm):
  X = ancho   (0 = costado izq)
  Y = profund.(0 = plano del frente, crece hacia atrás)
  Z = altura  (0 = piso del local)
"""
import math
from dataclasses import dataclass
from typing import List, Tuple
from .config import Estandar
from .modelos import (Gabinete, _repartir_frentes, _ancho_hojas, LARGOS_CORREDERA,
                      alturas, alturas_entrepanos, doblado_nariz,
                      entrepanos_divisorios, respaldo_interior, fondo_divisorio,
                      holgura_frente, respaldo_entero, respaldo_interior,
                      unero_de, vuelo_de)

C30 = math.cos(math.radians(30))
S30 = math.sin(math.radians(30))

# vector de explosión por grupo (dirección · magnitud relativa)
EXPLOSION = {
    "costado_izq": (-1.15, 0, 0),
    "costado_der": (1.15, 0, 0),
    "piso":        (0, 0, -1.0),
    "tapa":        (0, 0, 1.15),
    "travesano":   (0, 0, 0.95),
    "respaldo":    (0, 1.5, 0),
    "entrepano":   (0, -0.35, -0.45),
    "frente":      (0, -1.5, 0),
    "zoclo":       (0, -2.2, -0.2),
    "cajon":       (0, -0.85, 0),
    "manguete":    (0, -1.2, 0.25),                  # #067
}

# color base por grupo (r,g,b 0-1)
COLOR = {
    "costado_izq": (0.86, 0.83, 0.78),
    "costado_der": (0.86, 0.83, 0.78),
    "piso":        (0.86, 0.83, 0.78),
    "tapa":        (0.86, 0.83, 0.78),
    "travesano":   (0.86, 0.83, 0.78),
    "entrepano":   (0.90, 0.87, 0.82),
    "respaldo":    (0.72, 0.70, 0.66),
    "frente":      (0.70, 0.76, 0.82),
    "zoclo":       (0.55, 0.58, 0.62),
    "cajon":       (0.80, 0.84, 0.78),
    "manguete":    (0.84, 0.81, 0.75),               # #067: es pieza de cuerpo
}


@dataclass
class Solido:
    x: float; y: float; z: float
    dx: float; dy: float; dz: float
    codigo: str
    grupo: str
    etiqueta: str = ""
    material: str = ""                      # #009
    color: Tuple[float, float, float] = None
    # #023 — a qué parte del modelo apunta: ("frente", i) o ("entrepano", i).
    # Sin esto, el 3D sabe dibujar la pieza pero no qué campo edita al tocarla.
    ref_tipo: str = ""
    ref_i: int = -1
    # #058 — cantos cortados a 45°. En el taller la pieza se corta recta como
    # todas y el chaflán se hace después, pero si el 3D la enseña recta nadie
    # sabe cuál canto lleva el corte. Se marca aquí y se dibuja.
    #   "sup" = el canto de arriba, mirando al frente (el del uñero)
    chaflan: str = ""

    @property
    def centro(self):
        return (self.x + self.dx / 2, self.y + self.dy / 2, self.z + self.dz / 2)


def proyectar(x, y, z) -> Tuple[float, float]:
    """Isométrico: vista desde arriba-frente-**izquierda**.

    (Hasta la 0.15.2 este comentario decía «derecha», y estaba mal. Se ve
    fácil: el eje +X sube hacia la derecha de la pantalla y el +Y sube hacia
    la izquierda, así que la esquina más baja del dibujo —la más cercana— es
    la de x=0, y=0: la de la IZQUIERDA. El dibujo siempre fue éste; lo que
    estaba equivocado era el nombre, y de ahí salió el error de abajo.)
    """
    return ((x - y) * C30, (x + y) * S30 + z)


def profundidad(x, y, z) -> float:
    """Mayor = más cerca del observador.

    #080 — Corregido. Antes devolvía `x - y + z`, que **no es** la
    profundidad de esta proyección: dos puntos que caen en el mismo píxel
    tienen que dar la misma profundidad, y con la fórmula vieja no la daban.

    La comprobación es de una línea. El eje de la vista —la dirección en la
    que dos puntos se pisan en pantalla— sale de `proyectar`: es (1, 1, −1),
    porque (1−1)=0 en horizontal y (1+1)·½+(−1)=0 en vertical. La
    profundidad tiene que ser constante sobre ese eje, o sea perpendicular a
    él. `x − y + z` da (1,−1,1)·(1,1,−1) = −1 ≠ 0: no lo era. `z − x − y` da
    (−1,−1,1)·(1,1,−1) = −3, paralelo, que es lo correcto (el signo hace que
    «mayor» sea «más cerca», que es lo que espera el z-buffer).

    Qué se veía mal: en el isométrico de los planos el z-buffer premiaba a
    veces la cara equivocada, y por eso aparecían piezas atravesadas y el
    interior del mueble visible con el mueble cerrado.
    """
    return z - x - y


# --------------------------------------------------------------- construcción
ROL_MATERIAL = {
    "costado_izq": "mat_cuerpo", "costado_der": "mat_cuerpo", "piso": "mat_cuerpo",
    "tapa": "mat_cuerpo", "travesano": "mat_cuerpo", "entrepano": "mat_cuerpo",
    "respaldo": "mat_respaldo", "frente": "mat_frente", "zoclo": "mat_frente",
    "manguete": "mat_manguete",                      # #067

    "cajon": "mat_cajon",
}


def hex_a_rgb(h: str):
    h = (h or "").lstrip("#")
    if len(h) != 6:
        return None
    try:
        return tuple(int(h[i:i + 2], 16) / 255 for i in (0, 2, 4))
    except ValueError:
        return None


def pintar_por_material(sol: List[Solido], std: Estandar) -> List[Solido]:
    """Asigna material y color de catálogo a cada sólido. (#009)"""
    for s in sol:
        m = getattr(std, ROL_MATERIAL.get(s.grupo, "mat_cuerpo"), None)
        if m is None:                      # #067: mat_manguete vacío = el del cuerpo
            m = std.mat_cuerpo
        if m is not None:
            s.material = m.nombre
            s.color = hex_a_rgb(getattr(m, "color", "")) or COLOR.get(s.grupo)
    return sol


def solidos_gabinete(g: Gabinete, std: Estandar) -> List[Solido]:
    e = std.mat_cuerpo.espesor
    ef = std.mat_frente.espesor
    er = std.mat_respaldo.espesor
    ec = std.mat_cajon.espesor
    tapa = g.tapa_completa if g.tapa_completa is not None else (g.tipo == "aereo")
    _total, hc, hz = alturas(g, std)      # #001
    A, P = g.ancho, g.prof
    # #043 #044 — con cubierta, el fondo declarado es el de la PLANCHA. El vuelo
    # se descuenta por delante: primero la puerta, luego el cuerpo. Y la puerta
    # se recorre con él, en vez de quedarse flotando en y=0 como hasta la 0.9.0.
    vu = vuelo_de(g, std)
    # #077 — entre el canto frontal del costado y la cara de atrás del frente va
    # un hueco: ahí viven la bisagra y el tope. El cuerpo se recorre hacia atrás.
    hf = holgura_frente(std)
    yf = vu                    # cara frontal de la PUERTA
    y0 = vu + ef + hf          # cara frontal del cuerpo
    Pc = P - ef - vu - hf
    z0 = hz                    # base del cuerpo
    S: List[Solido] = []

    # zoclo
    if hz:
        # el retranqueo del zoclo se mide desde la cara de la PUERTA, no desde el
        # filo de la cubierta: si no, con vuelo el zoclo se adelantaba solo.
        S.append(Solido(0, yf + std.retranqueo_zoclo, 0, A, ef, hz,
                        "ZOC", "zoclo", "Zoclo"))

    # costados
    S.append(Solido(0, y0, z0, e, Pc, hc, "COS", "costado_izq", "Costado izq."))
    S.append(Solido(A - e, y0, z0, e, Pc, hc, "COS", "costado_der", "Costado der."))

    # piso
    S.append(Solido(e, y0, z0, A - 2 * e, Pc, e, "PIS", "piso", "Piso"))

    # tapa o travesaños
    if tapa:
        S.append(Solido(e, y0, z0 + hc - e, A - 2 * e, Pc, e, "TAP", "tapa", "Tapa"))
    else:
        S.append(Solido(e, y0, z0 + hc - e, A - 2 * e, 100, e, "TRV", "travesano", "Travesaño front."))
        S.append(Solido(e, y0 + Pc - 100, z0 + hc - e, A - 2 * e, 100, e, "TRV", "travesano", "Travesaño tras."))

    # respaldo
    # #070 — el encajonado (#003) **no se ranura**: entra a tope entre las
    # cuatro piezas del cuerpo, y arriba topa con la tapa o con el travesaño
    # trasero, que ocupan el mismo plano. Hasta la 0.10.3 el 3D le metía la
    # profundidad de ranura por los cuatro lados aunque no hubiera ranura, y
    # además lo dejaba subir hasta el canto alto cuando no había tapa: se veía
    # atravesando el travesaño y los costados.
    interior = respaldo_interior(std)
    ranurado = std.respaldo_ranurado and not interior
    zr0 = z0 + e                      # cara de arriba del piso
    ztope = z0 + hc - e               # cara de abajo de la tapa o del travesaño
    if respaldo_entero(g, std):
        if ranurado:
            pr = std.prof_ranura
            zr1 = ztope + pr if tapa else z0 + hc
            S.append(Solido(e - pr, y0 + Pc - er, zr0 - pr,
                            A - 2 * e + 2 * pr, er, zr1 - (zr0 - pr),
                            "RES", "respaldo", "Respaldo"))
        elif interior:
            S.append(Solido(e, y0 + Pc - er, zr0, A - 2 * e, er, ztope - zr0,
                            "RES", "respaldo", "Respaldo"))
        else:                     # sobrepuesto: va POR FUERA, tapando todo
            S.append(Solido(0, y0 + Pc, z0, A, er, hc,
                            "RES", "respaldo", "Respaldo"))
    else:
        # #065 — dos travesaños atrás, uno arriba y otro abajo, y el hueco de en
        # medio libre para que pasen las instalaciones. El de arriba topa con la
        # tapa o con el travesaño superior trasero, no con el canto del mueble.
        at = float(std.ancho_travesano_respaldo)
        S.append(Solido(e, y0 + Pc - e, ztope - at, A - 2 * e, e, at,
                        "TRS", "travesano", "Travesaño trasero sup."))
        S.append(Solido(e, y0 + Pc - e, zr0, A - 2 * e, e, at,
                        "TRS", "travesano", "Travesaño trasero inf."))

    # entrepaños
    if g.n_entrepanos:
        p_ent = Pc - std.retranqueo_entrepano - er
        for i, h in enumerate(alturas_entrepanos(g, std, hc), start=1):   # #023
            zz = z0 + e + h
            S.append(Solido(e + 1, y0, zz, A - 2 * e - 2, p_ent, e,
                            "ENT", "entrepano", f"Entrepaño {i}",
                            ref_tipo="entrepano", ref_i=i - 1))

    # #089 — entrepaños divisorios: van ensamblados entre costado y costado, así
    # que miden el interior completo, no el ancho holgado del entrepaño suelto.
    for i, d in enumerate(entrepanos_divisorios(g, std, hc), start=1):
        # #096 — el fondo sale de la MISMA función que usa el despiece: antes
        # cada uno lo calculaba aparte y el dibujo no cuadraba con el corte.
        S.append(Solido(e, y0, z0 + e + d["h"], A - 2 * e,
                        fondo_divisorio(std, Pc - (er if interior else 0), interior), e,
                        "DIV", "entrepano", f"Entrepaño divisorio {i}"))

    # frentes (se listan de arriba hacia abajo)
    hp, hef = std.holgura_perimetral, std.holgura_entre_frentes

    # #042 #045 #057 — el manguete del uñero va **entre costados y detrás de la
    # puerta** (por eso arranca en `y0`, la cara del cuerpo, y mide el interior),
    # y cuelga de la BASE DE LA NARIZ, no de la tapa: si la cubierta trae nariz,
    # el conjunto entero baja con ella.
    hman = unero_de(g, std)
    if hman > 0:
        # #063 — el manguete llega HASTA ARRIBA del gabinete, aunque la nariz le
        # tape la parte de encima. Lo que se ve son sus `hman` de abajo, del
        # filo de la nariz para abajo; lo de arriba es material que sí se corta
        # y sí se compra, y tiene que estar ahí para tener de dónde atornillarlo.
        z_nariz = z0 + hc - doblado_nariz(g, std)     # base de la nariz
        z_pie = z_nariz - hman
        S.append(Solido(e, y0, z_pie,
                        A - 2 * e, ef, (z0 + hc) - z_pie,
                        "MAN", "manguete", "Manguete (uñero)", chaflan="inf"))
    ic = 0
    for i, m in enumerate(_repartir_frentes(g, hc, std)):
        f = m["frente"]
        z_top = z0 + hc - m["y_mod"]
        z_bot = z_top - m["alto_mod"]
        h_f = m["alto_frente"]
        zf = z_bot + (m["alto_mod"] - h_f) / 2
        # #058 — el chaflán del uñero sólo lo lleva el frente de hasta arriba
        chaf = "sup" if (i == 0 and hman > 0) else ""
        if f.tipo == "abierto":       # #090 — nicho: no se dibuja ningún frente
            continue
        if f.tipo == "puerta":
            aw = _ancho_hojas(g, f.n, std)
            for k in range(f.n):
                xf = hp + k * (aw + hef)
                S.append(Solido(xf, yf, zf, aw, ef, h_f, f"PTA{i+1}", "frente",
                                f"Puerta {i+1}.{k+1}",
                                ref_tipo="frente", ref_i=i, chaflan=chaf))
        else:
            ic += 1
            S.append(Solido(hp, yf, zf, A - 2 * hp, ef, h_f, f"FCJ{ic}", "frente",
                            f"Frente cajón {ic}", ref_tipo="frente", ref_i=i,
                            chaflan=chaf))
            # caja del cajón (bloque simplificado)
            ancho_caja = A - 2 * e - 2 * std.holgura_corredera_lado
            util = Pc - std.retranqueo_fondo_cajon
            lc = max([l for l in LARGOS_CORREDERA if l <= util], default=LARGOS_CORREDERA[0])
            S.append(Solido(e + std.holgura_corredera_lado, y0 + 15,
                            zf + 8, ancho_caja, lc, std.alto_caja_cajon,
                            f"CJ{ic}", "cajon", f"Caja cajón {ic}"))
    return pintar_por_material(S, std)


# --------------------------------------------------------------- explosión
def explotar(sol: List[Solido], factor: float, g: Gabinete) -> List[Solido]:
    if factor <= 0:
        return sol
    import copy
    d = max(g.ancho, g.alto, g.prof) * factor
    out = []
    for s in sol:
        v = EXPLOSION.get(s.grupo, (0, 0, 0))
        q = copy.copy(s)
        q.x += v[0] * d
        q.y += v[1] * d
        q.z += v[2] * d
        out.append(q)
    return out


def caras_visibles(s: Solido):
    """Las 3 caras que mira el observador: top (+Z), frente (−Y) e izq (−X).

    #080 — Antes devolvía la cara +X (la «derecha»), que en esta proyección
    está de espaldas. Se comprueba con el eje de la vista (1, 1, −1): la
    normal (−1,0,0) apunta hacia quien mira y la (1,0,0) al revés.

    Sirve para dibujo vectorial sin z-buffer. Para el render usa caras(), que
    devuelve las 6: un gabinete se mira POR DENTRO y las caras interiores hacen
    falta (#005).
    """
    x, y, z, dx, dy, dz = s.x, s.y, s.z, s.dx, s.dy, s.dz
    top = [(x, y, z + dz), (x + dx, y, z + dz), (x + dx, y + dy, z + dz), (x, y + dy, z + dz)]
    frente = [(x, y, z), (x + dx, y, z), (x + dx, y, z + dz), (x, y, z + dz)]
    izq = [(x, y, z), (x, y + dy, z), (x, y + dy, z + dz), (x, y, z + dz)]
    return top, frente, izq


# Factor de sombreado por cara: exteriores claras, interiores más apagadas.
# #080 — «izq» y «der» iban al revés: la cara que se ve de fuera es la −X, y
# era la que llevaba el tono de cara interior.
SOMBRA = {"top": 1.0, "frente": 0.84, "izq": 0.66,
          "fondo": 0.45, "trasera": 0.62, "der": 0.74}


def caras(s: Solido):
    """Las 6 caras del tablero con su factor de luz. (#005)"""
    x, y, z, dx, dy, dz = s.x, s.y, s.z, s.dx, s.dy, s.dz
    X, Y, Z = x + dx, y + dy, z + dz
    return [
        ([(x, y, Z), (X, y, Z), (X, Y, Z), (x, Y, Z)], SOMBRA["top"]),      # +Z
        ([(x, y, z), (X, y, z), (X, Y, z), (x, Y, z)], SOMBRA["fondo"]),    # -Z
        ([(x, y, z), (X, y, z), (X, y, Z), (x, y, Z)], SOMBRA["frente"]),   # -Y
        ([(x, Y, z), (X, Y, z), (X, Y, Z), (x, Y, Z)], SOMBRA["trasera"]),  # +Y
        ([(X, y, z), (X, Y, z), (X, Y, Z), (X, y, Z)], SOMBRA["der"]),      # +X
        ([(x, y, z), (x, Y, z), (x, Y, Z), (x, y, Z)], SOMBRA["izq"]),      # -X
    ]


def bbox_proyectado(sol: List[Solido]):
    pts = []
    for s in sol:
        for cx in (s.x, s.x + s.dx):
            for cy in (s.y, s.y + s.dy):
                for cz in (s.z, s.z + s.dz):
                    pts.append(proyectar(cx, cy, cz))
    xs = [p[0] for p in pts]; ys = [p[1] for p in pts]
    return min(xs), min(ys), max(xs), max(ys)


# --------------------------------------------------------------- colocación (#004)
def base_z(g: Gabinete, std: Estandar) -> float:
    """Altura a la que arranca el gabinete sobre el piso del local."""
    if g.tipo == "aereo":
        return float(g.alto_colgado if g.alto_colgado is not None
                     else std.altura_colgado_aereo)
    return 0.0


def colocar(sol: List[Solido], g: Gabinete, std: Estandar) -> List[Solido]:
    """Lleva los sólidos del gabinete a coordenadas de la cocina.

    El giro sólo admite múltiplos de 90°, así que las cajas siguen alineadas a
    los ejes y el z-buffer las sigue tratando como AABB.
    """
    import copy
    rot = int(g.rot) % 360
    A, P = g.ancho, g.prof
    dz = base_z(g, std)
    out = []
    for s in sol:
        q = copy.copy(s)
        x, y, dx, dy = s.x, s.y, s.dx, s.dy
        if rot == 90:
            q.x, q.y, q.dx, q.dy = P - y - dy, x, dy, dx
        elif rot == 180:
            q.x, q.y = A - x - dx, P - y - dy
        elif rot == 270:
            q.x, q.y, q.dx, q.dy = y, A - x - dx, dy, dx
        q.x += g.pos_x
        q.y += g.pos_z
        q.z += dz
        out.append(q)
    return out


def huella(g: Gabinete):
    """Rectángulo en planta (x0, z0, x1, z1) que ocupa el gabinete."""
    a, p = (g.prof, g.ancho) if int(g.rot) % 180 == 90 else (g.ancho, g.prof)
    return (g.pos_x, g.pos_z, g.pos_x + a, g.pos_z + p)
