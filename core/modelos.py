"""Modelos paramétricos de gabinete. Todas las medidas en mm.

Convención de coordenadas locales de cada pieza (vista de la cara A, en plano):
  - COSTADOS:    X = altura desde el piso del cuerpo ; Y = profundidad desde el frente
  - HORIZONTALES (piso/tapa/travesaño/entrepaño): X = ancho del gabinete ; Y = profundidad
  - FRENTES/RESPALDOS: X = ancho ; Y = alto
"""
from dataclasses import dataclass, field
from typing import List, Dict, Optional
from .config import Estandar
from .pieza import Pieza, Barreno, Ranura

LARGOS_CORREDERA = [250, 300, 350, 400, 450, 500, 550, 600]


@dataclass
class Frente:
    """Elemento del frente del gabinete."""
    tipo: str            # "puerta" | "cajon" | "abierto"  (#090)
    alto: Optional[float] = None   # None = reparte el sobrante
    n: int = 1           # nº de hojas (solo puertas)
    # #097 — alto de las paredes de la caja, sólo para cajones.
    # None = se calcula solo: 80 % del alto del frente, redondeado al
    # centímetro cerrado de arriba. Un número aquí lo pisa, para el cajón de
    # cubiertos que va bajito o el de ollas que va alto.
    alto_caja: Optional[float] = None


@dataclass
class Gabinete:
    nombre: str
    tipo: str                     # "base" | "aereo"
    ancho: float
    alto: float                   # altura TOTAL (piso a tapa, incluye zoclo)
    prof: float                   # profundidad TOTAL (incluye frente)
    frentes: List[Frente] = field(default_factory=list)
    n_entrepanos: int = 1
    entrepanos_fijos: bool = False
    # #023 — altura libre de cada entrepaño, medida desde la cara superior del
    # piso interior hasta la CARA INFERIOR del entrepaño. None = repartidos a
    # distancias iguales, que es como se comportaba antes de la 0.5.0.
    alturas_entrepanos: Optional[List[float]] = None
    # #028 — este mueble lleva cubierta encima. None = lo decide el tipo:
    # los bajos sí, los aéreos no.
    con_cubierta: Optional[bool] = None
    # #030 — gola: el perfil se lleva altura del frente de arriba. None = usa la
    # del proyecto. El cuerpo NO cambia: la gola va atornillada al canto.
    gola: Optional[bool] = None
    alto_gola: Optional[float] = None
    # #042 — uñero: puerta con chaflán a 45° arriba y un manguete fijo encima.
    unero: Optional[bool] = None
    alto_manguete: Optional[float] = None
    tapa_completa: Optional[bool] = None   # None -> base=False, aereo=True
    # #065 — respaldo entero o dos travesaños. None = lo del proyecto.
    respaldo_completo: Optional[bool] = None
    # #075 — cuánto vuela la cubierta por delante de la puerta, de ESTE mueble.
    # None = lo del proyecto. Mike: una isla suele volar de los dos lados, y el
    # resto de la cocina no.
    vuelo_cubierta: Optional[float] = None
    con_zoclo: bool = True
    cantidad: int = 1
    # --- alturas (#001): total = cuerpo + zoclo. El campo derivado se recalcula.
    alto_cuerpo: Optional[float] = None     # None = se deriva de alto - zoclo
    altura_zoclo: Optional[float] = None    # None = usa la del proyecto
    alto_derivado: str = "cuerpo"           # "total" | "cuerpo" | "zoclo"
    # --- posición en la cocina (#004). mm, planta: X derecha, Z hacia el frente
    pos_x: float = 0.0
    pos_z: float = 0.0
    rot: int = 0                            # 0 / 90 / 180 / 270
    alto_colgado: Optional[float] = None    # aéreos: base sobre el piso. None = estándar
    # materiales por gabinete (nombre del catálogo). None = usa el del proyecto
    mat_cuerpo: Optional[str] = None
    mat_frente: Optional[str] = None
    mat_respaldo: Optional[str] = None


class GeometriaInvalida(ValueError):
    """El gabinete no se puede construir con las medidas dadas. (#014)"""


class AlturaInvalida(GeometriaInvalida):
    """El juego de alturas no cierra (cuerpo o zoclo <= 0)."""


def validar(g: Gabinete, std: Estandar):
    """Rechaza medidas que no producen un mueble construible. (#014)

    Corre ANTES de despiezar: más vale un mensaje claro que una lista de corte
    con piezas de medida negativa camino a la CNC.
    """
    e, ef = std.mat_cuerpo.espesor, std.mat_frente.espesor
    n = g.nombre or "el gabinete"

    if g.ancho is None or g.ancho <= 0:
        raise GeometriaInvalida(f"«{n}»: el ancho debe ser mayor que 0.")
    if g.prof is None or g.prof <= 0:
        raise GeometriaInvalida(f"«{n}»: la profundidad debe ser mayor que 0.")

    ancho_min = 2 * e + 50
    if g.ancho < ancho_min:
        raise GeometriaInvalida(
            f"«{n}»: {g.ancho:.0f} mm de ancho no alcanza. Con costados de {e:.0f} mm "
            f"el interior quedaría en {g.ancho - 2 * e:.0f} mm. "
            f"Mínimo {ancho_min:.0f} mm.")

    # #043 — con cubierta, el fondo tecleado es el de la plancha, así que el
    # vuelo también sale de ahí antes de que quede cuerpo.
    vu = vuelo_de(g, std)
    prof_min = ef + vu + holgura_frente(std) + 100
    if g.prof < prof_min:
        extra = f"el vuelo de la cubierta {vu:.0f} mm, " if vu else ""
        raise GeometriaInvalida(
            f"«{n}»: {g.prof:.0f} mm de profundidad no alcanza. {extra}"
            f"el frente se lleva {ef:.0f} mm y quedarían "
            f"{g.prof - ef - vu:.0f} mm de cuerpo. Mínimo {prof_min:.0f} mm.")

    alturas(g, std)          # valida el juego de alturas (#001)

    if g.n_entrepanos and g.n_entrepanos < 0:
        raise GeometriaInvalida(f"«{n}»: los entrepaños no pueden ser negativos.")
    for f in g.frentes:
        if f.tipo not in ("puerta", "cajon", "abierto"):       # #090
            raise GeometriaInvalida(
                f"«{n}»: «{f.tipo}» no es un tipo de frente. "
                "Sólo hay puerta, cajón y abierto.")
        if f.alto_caja is not None and float(f.alto_caja) <= 0:      # #097
            raise GeometriaInvalida(
                f"«{n}»: el alto de la caja del cajón debe ser mayor que 0.")
        if f.tipo == "puerta" and f.n < 1:
            raise GeometriaInvalida(f"«{n}»: una puerta necesita al menos una hoja.")


def _revisar_piezas(P: List[Pieza], g: Gabinete) -> List[Pieza]:
    """Red de seguridad: ninguna pieza sale con medida <= 0. (#014)

    `validar()` atrapa lo previsible; esto atrapa cualquier combinación rara que
    se nos escape, y lo hace antes de que la pieza llegue al nesting o al DXF.
    """
    malas = [p for p in P if p.largo <= 0 or p.ancho <= 0 or p.espesor <= 0]
    if malas:
        d = "; ".join(f"{p.nombre} {p.largo:.0f}×{p.ancho:.0f}" for p in malas[:3])
        raise GeometriaInvalida(
            f"«{g.nombre}»: el despiece produjo {len(malas)} pieza(s) con medida "
            f"imposible ({d}). Revisa las medidas generales del gabinete.")
    return P


def espesor_cubierta(g: Gabinete, std: Estandar) -> float:
    """#059 — Lo que se lleva la cubierta del alto declarado.

    Regla de Mike: **la altura que se teclea es la de trabajo, con cubierta y
    todo**. Si el mueble mide 1000 y lleva superficie sólida de 12, el gabinete
    —zoclo incluido— mide 988; la plancha pone los 12 que faltan.

    Es la misma idea del fondo (#043): lo que se captura es la medida del
    conjunto terminado, que es la que se mide en obra y la que sale en el plano.
    Antes la plancha se sumaba por encima y el mueble crecía 12 mm sobre lo
    pedido.
    """
    if not lleva_cubierta(g):
        return 0.0
    mat = getattr(std, "mat_cubierta", None)
    return float(mat.espesor) if mat is not None else 0.0


def alturas(g: Gabinete, std: Estandar):
    """Resuelve (total, cuerpo, zoclo) respetando el campo derivado.

    Identidad: total = cuerpo + zoclo.  Dos se capturan, el tercero se calcula.
    Un gabinete sin zoclo tiene zoclo = 0 y total == cuerpo.

    #059 — «total» aquí es el alto del GABINETE. Si lleva cubierta, el alto
    declarado incluye la plancha, así que se le descuenta antes de repartir.
    """
    lleva = bool(g.tipo == "base" and g.con_zoclo)
    hz_ref = g.altura_zoclo if g.altura_zoclo is not None else std.altura_zoclo
    d = (g.alto_derivado or "cuerpo").lower()
    ec = espesor_cubierta(g, std)

    if not lleva:
        total = float(g.alto_cuerpo if (d == "total" and g.alto_cuerpo) else g.alto)
        total -= ec
        if total <= 0:
            raise AlturaInvalida(f"«{g.nombre}»: la altura debe ser mayor que 0")
        return total, total, 0.0

    if d == "total":                       # capturas cuerpo + zoclo
        cuerpo = float(g.alto_cuerpo if g.alto_cuerpo is not None
                       else g.alto - ec - hz_ref)
        hz = float(hz_ref)
        total = cuerpo + hz
    elif d == "zoclo":                     # capturas total + cuerpo
        total = float(g.alto) - ec
        cuerpo = float(g.alto_cuerpo if g.alto_cuerpo is not None
                       else g.alto - ec - hz_ref)
        hz = total - cuerpo
    else:                                  # "cuerpo": capturas total + zoclo
        total = float(g.alto) - ec
        hz = float(hz_ref)
        cuerpo = total - hz

    # mínimo constructivo: al menos el piso y el travesaño/tapa
    minimo = 2 * std.mat_cuerpo.espesor
    if cuerpo <= minimo:
        raise AlturaInvalida(
            f"«{g.nombre}»: el cuerpo queda en {cuerpo:.0f} mm y no caben ni el piso "
            f"ni la tapa ({minimo:.0f} mm mínimo). "
            f"Baja el zoclo ({hz:.0f}) o sube el total ({total:.0f}).")
    if hz < 0:
        raise AlturaInvalida(
            f"«{g.nombre}»: el zoclo queda en {hz:.0f} mm. "
            f"El cuerpo ({cuerpo:.0f}) no puede pasar del total ({total:.0f}).")
    return total, cuerpo, hz


# ---------------------------------------------------------------- utilidades
def holgura_frente(std: Estandar) -> float:
    """#077 — el hueco entre el canto frontal del costado y la cara de atrás
    del frente.

    Mike: «hay que considerar el espacio entre el frente del costado y el frente
    (sea puerta o cajón), una holgura de 3 mm». Ahí viven la bisagra, el tope y
    el ajuste: una puerta pegada al canto no cierra.

    Sale del **fondo declarado**, igual que el vuelo (#043): lo que se teclea es
    el conjunto terminado y el cuerpo se corta de lo que queda. Se descuenta
    siempre, lleve frentes o no, para que en una corrida todos los cuerpos
    queden a la misma profundidad y el respaldo caiga en la misma línea.
    """
    return max(0.0, float(getattr(std, "holgura_frente_costado", 0.0) or 0.0))


def _materiales_de(std: Estandar) -> dict:
    """Los materiales que usa este estándar, por nombre."""
    d = {}
    for k in ("mat_cuerpo", "mat_frente", "mat_respaldo", "mat_cajon",
              "mat_fondo_cajon", "mat_cubierta", "mat_manguete"):
        m = getattr(std, k, None)
        if m is not None:
            d.setdefault(m.nombre, m)
    return d


def canto_de(std: Estandar, material, catalogo: dict = None) -> float:
    """#078 — el grosor del cubrecanto de ESE material.

    Una melamina de puerta se cantea con 2 mm y el interior del mueble con 1;
    con un solo grosor para todo el taller, la medida de corte (#006) sale mal
    en uno de los dos. El del material manda; en 0, el del estándar.
    """
    m = (catalogo or {}).get(material) if isinstance(material, str) else material
    esp = float(getattr(m, "espesor_canto", 0.0) or 0.0) if m is not None else 0.0
    return esp if esp > 0 else float(std.canto_visible)


def _canto_visible(std, *bordes):
    """Devuelve tupla de canto (inf, sup, izq, der) con espesor visible en los índices dados."""
    c = [0.0, 0.0, 0.0, 0.0]
    for b in bordes:
        c[b] = std.canto_visible
    return tuple(c)


def _linea32(std: Estandar, y_inicio: float, y_fin: float, x: float,
             dia: float, prof: float, nota: str) -> List[Barreno]:
    """Barrenos a paso 32 mm sobre el eje Y, en la coordenada X dada."""
    out, y = [], y_inicio
    while y <= y_fin + 0.01:
        out.append(Barreno(x=x, y=y, dia=dia, prof=prof, nota=nota))
        y += std.paso_sistema
    return out


def _n_conectores(prof: float) -> int:
    return 2 if prof < 400 else 3


def _pos_conectores(prof_util: float, std: Estandar, n: int) -> List[float]:
    """Posiciones en Y (profundidad) para conectores de ensamble."""
    a, b = std.offset_linea_frente, prof_util - std.offset_linea_trasera
    if n <= 2:
        return [a, b]
    paso = (b - a) / (n - 1)
    return [a + i * paso for i in range(n)]


def lleva_cubierta(g: Gabinete) -> bool:
    """#028 — un aéreo nunca lleva cubierta; un bajo, por omisión, sí."""
    if g.con_cubierta is None:
        return g.tipo == "base"
    return bool(g.con_cubierta)


def material_manguete(std: Estandar):
    """#067 — de qué sale el manguete del uñero.

    Mike: es una pieza APARTE de las puertas y va en el material del **cuerpo**.
    Tiene sentido: se atornilla entre costados, por detrás de la puerta, y de
    ella sólo se ve el canto de abajo con su chaflán. Cortarla del material de
    frentes —que suele ser el caro y el que lleva veta— era gastar de más.

    Se puede cambiar: hay muebles donde ese canto queda muy a la vista y se
    quiere que combine con los frentes.
    """
    return getattr(std, "mat_manguete", None) or std.mat_cuerpo


def respaldo_entero(g: Gabinete, std: Estandar) -> bool:
    """#065 — ¿el respaldo es un tablero, o son dos travesaños?

    Mike lo pidió para los muebles que van donde pasan las instalaciones
    hidráulicas: con dos travesaños —uno arriba y otro abajo, como en la tapa—
    el hueco de en medio deja libre el paso de tubos y registros, y el mueble
    conserva de qué escuadrarse.
    """
    if g.respaldo_completo is None:
        return bool(getattr(std, "respaldo_completo", True))
    return bool(g.respaldo_completo)


def gola_de(g: Gabinete, std: Estandar) -> float:
    """#030 — altura que la gola le quita al frente de arriba. 0 = sin gola.

    El cuerpo no cambia de tamaño: el perfil va atornillado al canto del costado
    y el hueco queda entre la cubierta y el frente. Por eso sólo se descuenta del
    reparto de frentes.
    """
    hay = std.gola if g.gola is None else bool(g.gola)
    if not hay:
        return 0.0
    alto = std.alto_gola if g.alto_gola is None else float(g.alto_gola)
    return max(0.0, float(alto))


def vuelo_de(g: Gabinete, std: Estandar) -> float:
    """#043 — Cuánto sobresale la cubierta POR DELANTE de la cara de la puerta.

    Regla de Mike, 30-ago:

      · Si el mueble **lleva cubierta**, la medida de fondo que se teclea es la
        de la **cubierta**: del filo de la plancha a la pared.
      · Si **no** lleva, la medida es del **frente de la puerta** a la pared.

    De ahí sale todo lo demás. Con vuelo 0 la plancha queda **a paño de las
    puertas**; con vuelo 20 sobresale 20 mm por delante de ellas. El cuerpo se
    corta lo que quede: `prof − vuelo − espesor del frente`.

    Antes esto se hacía al revés: la cubierta se dibujaba del fondo del mueble
    **más** el vuelo, así que el conjunto crecía en vez de que el mueble se
    ajustara, y con nariz el vuelo se anulaba y el cuerpo se encogía por su
    cuenta el espesor de la plancha. Dos reglas distintas para lo mismo, y por
    eso al quitar la nariz no regresaba a su medida.

    La nariz ya no encoge nada: cuelga del filo de la plancha, que va `vuelo`
    por delante de la puerta. Lo que la nariz baja de más se lo quita al frente
    de arriba (#041), que es donde estorba de verdad.
    """
    if not lleva_cubierta(g):
        return 0.0
    if getattr(std, "mat_cubierta", None) is None:
        return 0.0
    # #075 — el del mueble manda sobre el del proyecto. `estandar_de()` ya lo
    # deja puesto en `std`; esto es la red por si a alguien se le pasa.
    propio = getattr(g, "vuelo_cubierta", None)
    if propio is not None:
        return max(0.0, float(propio))
    return max(0.0, float(std.vuelo_cubierta or 0.0))


def doblado_nariz(g: Gabinete, std: Estandar) -> float:
    """#041 — Cuánto cuelga la nariz por DEBAJO de la cubierta.

    La nariz es el alto aparente del canto. Lo que pase del espesor de la
    plancha es una faja pegada por abajo, y esa faja queda justo delante del
    frente. Si la puerta no se acorta, se atraviesan: la puerta no abre.

    Nariz de 60 sobre piedra de 20 → 40 mm de faja → la puerta pierde 40.
    """
    if not lleva_cubierta(g):
        return 0.0
    mat = getattr(std, "mat_cubierta", None)
    if mat is None:
        return 0.0
    return max(0.0, float(std.alto_nariz or 0.0) - float(mat.espesor))


def unero_de(g: Gabinete, std: Estandar) -> float:
    """#042 — el manguete del uñero: la faja de arriba por donde se jala.

    El uñero es la otra manera de abrir sin tirador: la puerta se corta a 45° en
    su canto de arriba y arriba de ella queda un manguete fijo. Los dedos entran
    en el chaflán. Se lleva su alto del frente de arriba, como la gola.
    """
    hay = std.unero if g.unero is None else bool(g.unero)
    if not hay:
        return 0.0
    alto = std.alto_manguete if g.alto_manguete is None else float(g.alto_manguete)
    return max(0.0, float(alto))


def holgura_unero_de(g: Gabinete, std: Estandar) -> float:
    """#057 — Separación entre la base de la nariz y el canto alto de la puerta.

    Es el hueco por donde entran los dedos. 30 mm por omisión.
    """
    v = getattr(std, "holgura_unero", 30.0)
    return max(0.0, float(v if v is not None else 30.0))


def descuento_superior(g: Gabinete, std: Estandar):
    """Cuánto pierde de alto el frente de arriba, y quién se lo lleva.

    #057 #061 — **Todo cuelga de la base de la nariz**, no de la tapa del
    mueble. Uñero y gola son dos formas de abrir sin tirador, y las dos se miden
    desde el mismo sitio: el filo de abajo de la cubierta. Si la plancha lleva
    nariz, la nariz empuja el conjunto entero hacia abajo.

        base de la nariz   =  tapa del mueble − doblado
        uñero: manguete    =  50 mm a partir de ahí, hacia abajo
               canto puerta=  30 mm por debajo de la base
        gola:  canto puerta=  el alto del perfil por debajo de la base

    Antes los tres competían y mandaba el mayor, como si ocuparan la misma
    franja. No la ocupan: el doblado cuelga por delante y el canal de la gola va
    en el canto, así que la puerta tiene que librar los dos, uno tras otro.
    """
    dob = doblado_nariz(g, std)
    if unero_de(g, std) > 0:
        # los 30 son el hueco QUE SE VE, medido en el mueble armado. El frente
        # además se encoge su holgura perimetral dentro del módulo, así que esa
        # parte se descuenta aquí: si no, el hueco terminado salía de 31.5.
        hueco = holgura_unero_de(g, std) - std.holgura_perimetral
        return round(dob + max(0.0, hueco), 1), "uñero"
    gl = gola_de(g, std)
    if gl > 0:
        # el alto de la gola es el del PERFIL, que se monta entero bajo la
        # cubierta: aquí no se corrige por holgura como en el uñero, porque lo
        # que manda es la pieza que se compra, no el hueco que queda.
        return round(dob + gl, 1), "gola"
    return round(dob, 1), ("nariz" if dob > 0 else "")


def gola_o_similar(g: Gabinete, std: Estandar) -> float:
    """Lo que pierde el frente de arriba, sin decir por qué."""
    return descuento_superior(g, std)[0]


def _repartir_frentes(g: Gabinete, hc: float, std: Estandar) -> List[Dict]:
    """Calcula alto de cada frente. Devuelve lista con alto_frente y alto_hueco."""
    n = len(g.frentes)
    if n == 0:
        return []
    # #030 #041 #042 — la gola, el uñero y el doblado de la nariz se comen el
    # arranque, y se lo comen **sólo al de hasta arriba**. El hueco queda pegado
    # a la cubierta; los frentes de abajo no se enteran, ni los que traen medida
    # fija. El reparto se hace sobre el mueble completo y después el módulo de
    # arriba cede su parte alta.
    hg = gola_o_similar(g, std)
    fijos = sum(f.alto for f in g.frentes if f.alto)
    libres = [f for f in g.frentes if not f.alto]
    sobrante = hc - fijos
    h_libre = sobrante / len(libres) if libres else 0
    res, y = [], hg
    hp, hef = std.holgura_perimetral, std.holgura_entre_frentes
    for i, f in enumerate(g.frentes):
        h_mod = f.alto if f.alto else h_libre
        if i == 0 and hg:
            h_mod = max(0.0, h_mod - hg)
        # holgura: perimetral arriba/abajo del conjunto, entre frentes en juntas internas
        rec_inf = hp if i == len(g.frentes) - 1 else hef / 2   # frentes se listan de arriba a abajo
        rec_sup = hp if i == 0 else hef / 2
        res.append({
            "frente": f,
            "y_mod": y,               # borde superior del módulo, medido desde arriba
            "alto_mod": h_mod,
            "alto_frente": round(h_mod - rec_inf - rec_sup, 1),
        })
        y += h_mod
    return res


# ------------------------------------------------------------------ #023
PRIMER_BARRENO_32 = 96.0     # el sistema 32 arranca a 96 mm del piso del costado


def _pegar_a_32(h_bajo_entrepano: float, e: float, std: Estandar) -> float:
    """Un entrepaño regulable sólo puede apoyarse donde hay barreno.

    Se recibe la altura hasta la cara inferior y se devuelve la más cercana que
    caiga en la línea de sistema 32. Decir que un entrepaño regulable está a
    417 mm sería mentira: se apoya en el barreno de 416.
    """
    paso = std.paso_sistema or 32.0
    desde_piso_costado = h_bajo_entrepano + e
    k = round((desde_piso_costado - PRIMER_BARRENO_32) / paso)
    k = max(0, k)
    return PRIMER_BARRENO_32 + k * paso - e


def alturas_entrepanos(g: Gabinete, std: Estandar, hc: Optional[float] = None) -> List[float]:
    """Altura de la cara inferior de cada entrepaño, de abajo hacia arriba.

    Se mide desde la cara superior del piso interior, que es como se mide en el
    taller: lo que da esa cifra es la luz del hueco de abajo.
    """
    n = int(g.n_entrepanos or 0)
    if n <= 0:
        return []
    e = std.mat_cuerpo.espesor
    if hc is None:
        hc = alturas(g, std)[1]
    hueco = hc - 2 * e                       # luz entre piso y tapa
    propias = getattr(g, "alturas_entrepanos", None)
    if propias:
        hs = [float(v) for v in list(propias)[:n]]
        while len(hs) < n:                   # subieron la cantidad: se reparte el resto
            hs.append(hueco * (len(hs) + 1) / (n + 1))
    else:
        hs = [hueco * i / (n + 1) for i in range(1, n + 1)]
    if not g.entrepanos_fijos:
        hs = [_pegar_a_32(h, e, std) for h in hs]
    tope = hueco - e
    hs = sorted(min(max(h, 0.0), tope) for h in hs)

    # Dos entrepaños no pueden quedar a la misma altura, ni uno encima del otro.
    # Al pegar al sistema 32 dos alturas cercanas caen en el mismo barreno, así
    # que hay que separarlos: mínimo el espesor más un paso.
    paso = (std.paso_sistema or 32.0) if not g.entrepanos_fijos else 20.0
    minimo = e + paso
    for i in range(1, len(hs)):
        if hs[i] < hs[i - 1] + minimo:
            hs[i] = hs[i - 1] + minimo
    # si al separarlos se salieron por arriba, se empujan hacia abajo
    if hs and hs[-1] > tope:
        corrimiento = hs[-1] - tope
        hs = [h - corrimiento for h in hs]
        for i in range(len(hs) - 2, -1, -1):
            if hs[i] > hs[i + 1] - minimo:
                hs[i] = hs[i + 1] - minimo
        hs = [max(h, 0.0) for h in hs]
    return [round(h, 1) for h in hs]


def entrepanos_divisorios(g: Gabinete, std: Estandar,
                          hc: Optional[float] = None) -> List[Dict]:
    """#089 — Entrepaños que separan un cajón de una puerta.

    Petición de Mike (14-sep). Donde un módulo de cajón y uno de puerta quedan
    pegados, el hueco necesita un panel que los divida: sin él, el cajón abre
    contra el espacio de la puerta y no hay dónde fijar la corredera.

    Dos decisiones suyas, y las dos cambian dónde cae el panel:

    - **Fijo, ensamblado al costado.** No es regulable: va atornillado a su
      altura, como el piso, porque encima se apoya la corredera de un cajón y
      un entrepaño de clavijas se zafa.
    - **Siempre del lado de la puerta, tapado por ella.** El panel se mete
      DENTRO del alto de la puerta, nunca en la junta entre frentes, así que
      desde afuera no se ve: la puerta lo cubre. Con la puerta arriba, el panel
      cuelga hacia arriba desde la junta; con la puerta abajo, baja desde la
      junta. En los dos casos el borde que mira al cajón coincide con la junta.

    #090 — Los nichos abiertos también se cierran. Un módulo `abierto` pegado a
    un cajón o a una puerta lleva su panel, y así un nicho entre dos cajones
    queda con uno arriba y otro abajo, que es lo que lo vuelve utilizable. Ahí
    no hay puerta que tape nada, y la regla de Mike es que **el panel se mete
    en el módulo vecino, no en el nicho**: el hueco conserva el alto que se ve
    en pantalla en vez de perder un espesor por lado. Dos módulos abiertos
    seguidos son el mismo nicho y no llevan nada en medio.

    Devuelve, de abajo hacia arriba, un dict por panel:
      h    — altura de su cara inferior desde la cara superior del piso, que es
             como se mide en el taller y como ya se miden los otros entrepaños
      ent  — "i/j": entre qué dos módulos va, contados desde arriba
      modo — "puerta" si lo tapa una puerta, "nicho" si cierra un hueco abierto

    Se pone solo y no se puede apagar. Los muebles que sólo traen puertas, o
    sólo cajones, no llevan ninguno.
    """
    if len(g.frentes) < 2:
        return []
    e = std.mat_cuerpo.espesor
    if hc is None:
        hc = alturas(g, std)[1]
    mods = _repartir_frentes(g, hc, std)
    piso_arriba = hc - e            # cara superior del piso, medida desde arriba
    res = []
    for i in range(len(mods) - 1):
        arriba, abajo = mods[i]["frente"].tipo, mods[i + 1]["frente"].tipo
        par = {arriba, abajo}
        if "abierto" in par:
            if par == {"abierto"}:
                continue            # dos abiertos seguidos: es el mismo nicho
            # #090 — el panel se hunde en el vecino cerrado, no en el nicho
            anfitrion_arriba = abajo == "abierto"
            modo = "nicho"
        elif par == {"puerta", "cajon"}:
            anfitrion_arriba = arriba == "puerta"   # se hunde en la puerta
            modo = "puerta"
        else:
            continue                # puerta con puerta o cajón con cajón: nada
        y_junta = mods[i + 1]["y_mod"]          # la junta, medida desde arriba
        # si el anfitrión está abajo, el panel baja un espesor desde la junta
        y_cara_inf = y_junta if anfitrion_arriba else y_junta + e
        h = round(piso_arriba - y_cara_inf, 1)
        if 0 < h < piso_arriba - e:             # no pegado al piso ni a la tapa
            res.append({"h": h, "ent": f"{i + 1}/{i + 2}", "modo": modo})
    return sorted(res, key=lambda d: d["h"])


def fondo_divisorio(std: Estandar, prof_util: float, interior: bool) -> float:
    """#096 — Hasta dónde llega de fondo un entrepaño divisorio.

    Mike: «no deben llegar hasta el fondo, se les debe restar el espesor del
    panel de fondo». Tiene razón y el 3D lo enseñaba: el divisorio se dibujaba
    atravesando el respaldo, metido seis milímetros dentro de él.

    El respaldo se monta de tres formas y sólo una necesita cuenta aparte:

    - **Interior**, apoyado contra un rebaje: `prof_util` ya viene con su
      espesor descontado, así que no se resta dos veces.
    - **Ranurado**, metido en una ranura de los costados, o **sobrepuesto**,
      clavado por fuera: `prof_util` es el fondo completo del cuerpo, y hay que
      quitarle el espesor del respaldo para no llegar hasta él.

    Esta función existe para que el despiece y el 3D saquen el número **del
    mismo lugar**. Antes cada uno lo calculaba por su cuenta y no coincidían:
    la lista de corte decía 552 y el dibujo 559. Una pieza que se corta de un
    tamaño y se dibuja de otro es una pieza que un día no entra.
    """
    return round(prof_util - (0.0 if interior else std.mat_respaldo.espesor), 1)


def alto_caja_de(alto_frente: float, frente: "Frente" = None) -> float:
    """#097 — Cuánto miden las paredes de la caja de un cajón.

    Mike: «la altura de las paredes del cajón debe ser por default del 80 % de
    la altura del frente, redondeada al número cerrado (cm) más cercano hacia
    arriba».

    Antes era un número fijo del estándar —90 mm para todos—, y eso daba cajas
    iguales bajo frentes de 120 y de 300: el de ollas quedaba ridículo y el de
    cubiertos, hondísimo. Ahora la caja crece con su frente.

    El 80 % deja el 20 % de abajo para la corredera y el remate, y el redondeo
    va **hacia arriba** porque en el taller se compra y se corta en medidas
    cerradas: 144 se pide como 150, no como 140.

    Un valor puesto a mano en el frente manda sobre todo esto.
    """
    if frente is not None and frente.alto_caja:
        return round(float(frente.alto_caja), 1)
    import math as _m
    return float(_m.ceil(max(float(alto_frente), 0.0) * 0.8 / 10.0) * 10)


def respaldo_interior(std: Estandar) -> bool:
    """#003: los respaldos gruesos van encajonados, no ranurados."""
    return std.mat_respaldo.espesor >= std.respaldo_interior_desde


def _ancho_hojas(g: Gabinete, n: int, std: Estandar) -> float:
    hp, hef = std.holgura_perimetral, std.holgura_entre_frentes
    return round((g.ancho - 2 * hp - (n - 1) * hef) / n, 1)


# ---------------------------------------------------------------- generador
def despiezar(g: Gabinete, std: Estandar, pref: str = "1") -> List[Pieza]:
    validar(g, std)                       # #014
    e = std.mat_cuerpo.espesor
    ef = std.mat_frente.espesor
    er = std.mat_respaldo.espesor
    tapa = g.tapa_completa if g.tapa_completa is not None else (g.tipo == "aereo")
    _total, hc, hz = alturas(g, std)      # #001: total = cuerpo + zoclo
    # #043 — con cubierta, el fondo tecleado es el de la PLANCHA: el cuerpo se
    # corta lo que sobra después del vuelo y del frente.
    pc = round(g.prof - ef - vuelo_de(g, std) - holgura_frente(std), 1)
    ancho_int = round(g.ancho - 2 * e, 1)
    P: List[Pieza] = []
    mc, mf = std.mat_cuerpo.nombre, std.mat_frente.nombre

    interior = respaldo_interior(std)            # #003
    # #065 — sin tablero de respaldo no hay ranura que hacerle
    ranurado = std.respaldo_ranurado and not interior and respaldo_entero(g, std)
    prof_util = pc - er if interior else pc      # el respaldo grueso come fondo

    nconn = _n_conectores(pc)
    ys = _pos_conectores(pc, std, nconn)
    y_ran = pc - std.offset_ranura - er / 2      # eje de la ranura de respaldo

    # ---------------- COSTADOS ----------------
    cos = Pieza(f"{pref}-COS", "Costado", largo=hc, ancho=pc, espesor=e, material=mc,
                cantidad=2, canto=_canto_visible(std, 0), veta=True, mueble=g.nombre,
                nota="X=altura desde piso de cuerpo, Y=profundidad desde frente")
    # ensamble del piso (a e/2 del borde inferior en X)
    for y in ys:
        cos.barrenos.append(Barreno(e / 2, y, std.dia_minifix_costado, 12, nota="ens-piso"))
        if tapa:
            cos.barrenos.append(Barreno(hc - e / 2, y, std.dia_minifix_costado, 12, nota="ens-tapa"))
    if not tapa:   # travesaños
        for y in (std.offset_linea_frente, pc - std.offset_linea_trasera):
            cos.barrenos.append(Barreno(hc - e / 2, y, std.dia_minifix_costado, 12, nota="ens-trav"))
    # ranura de respaldo
    if ranurado:
        cos.ranuras.append(Ranura(0, y_ran, hc, y_ran, er + std.holgura_ranura,
                                  std.prof_ranura, "ranura respaldo"))
    if interior:   # ensamble del respaldo encajonado contra el costado
        for z in (e + 40, hc / 2, hc - e - 40):
            cos.barrenos.append(Barreno(z, pc - er / 2, std.dia_minifix_costado, 12,
                                        nota="ens-respaldo"))
    # #023 — entrepaños fijos: van atornillados a su altura, no en la línea 32
    if g.n_entrepanos and g.entrepanos_fijos:
        for i, h in enumerate(alturas_entrepanos(g, std, hc), start=1):
            for y in (std.offset_linea_frente, pc - std.offset_linea_trasera):
                cos.barrenos.append(Barreno(h + e / 2, y, std.dia_minifix_costado, 12,
                                            nota=f"ens-entrepano-{i}"))
    # #089 — los divisorios van ensamblados, como los entrepaños fijos
    for k, d in enumerate(entrepanos_divisorios(g, std, hc), start=1):
        for y in (std.offset_linea_frente, pc - std.offset_linea_trasera):
            cos.barrenos.append(Barreno(d["h"] + e / 2, y, std.dia_minifix_costado, 12,
                                        nota=f"ens-divisorio-{k}"))

    # línea 32 para entrepaños regulables
    if g.n_entrepanos and not g.entrepanos_fijos:
        x0 = 96.0
        x1 = hc - 96.0
        for y in (std.offset_linea_frente, pc - std.offset_linea_trasera):
            x = x0
            while x <= x1:
                cos.barrenos.append(Barreno(x, y, 5.0, 12, nota="sist32-entrepano"))
                x += std.paso_sistema
    P.append(cos)

    # ---------------- PISO ----------------
    piso = Pieza(f"{pref}-PIS", "Piso", largo=ancho_int, ancho=pc, espesor=e, material=mc,
                 cantidad=1, canto=_canto_visible(std, 0), mueble=g.nombre)
    for y in ys:
        piso.barrenos.append(Barreno(0, y, std.dia_minifix_canto, 25, cara="canto_L", nota="ens"))
        piso.barrenos.append(Barreno(ancho_int, y, std.dia_minifix_canto, 25, cara="canto_R", nota="ens"))
    if ranurado:
        piso.ranuras.append(Ranura(0, y_ran, ancho_int, y_ran, er + std.holgura_ranura,
                                   std.prof_ranura, "ranura respaldo"))
    P.append(piso)

    # ---------------- TAPA o TRAVESAÑOS ----------------
    if tapa:
        tp = Pieza(f"{pref}-TAP", "Tapa", largo=ancho_int, ancho=pc, espesor=e, material=mc,
                   cantidad=1, canto=_canto_visible(std, 0), mueble=g.nombre)
        for y in ys:
            tp.barrenos.append(Barreno(0, y, std.dia_minifix_canto, 25, cara="canto_L", nota="ens"))
            tp.barrenos.append(Barreno(ancho_int, y, std.dia_minifix_canto, 25, cara="canto_R", nota="ens"))
        if ranurado:
            tp.ranuras.append(Ranura(0, y_ran, ancho_int, y_ran, er + std.holgura_ranura,
                                     std.prof_ranura, "ranura respaldo"))
        P.append(tp)
    else:
        tr = Pieza(f"{pref}-TRV", "Travesaño superior", largo=ancho_int, ancho=100.0,
                   espesor=e, material=mc, cantidad=2, canto=_canto_visible(std, 0),
                   mueble=g.nombre, nota="1 frontal + 1 trasero")
        tr.barrenos.append(Barreno(0, 50, std.dia_minifix_canto, 25, cara="canto_L", nota="ens"))
        tr.barrenos.append(Barreno(ancho_int, 50, std.dia_minifix_canto, 25, cara="canto_R", nota="ens"))
        P.append(tr)

    # ---------------- RESPALDO ----------------
    # #065 — dos travesaños en vez de tablero entero, como la tapa. Es para los
    # muebles que caen donde pasan las instalaciones hidráulicas: el hueco de en
    # medio deja libre el paso de tubos y registros, y el mueble sigue teniendo
    # con qué escuadrarse. Se corta del material del CUERPO, no del de respaldo:
    # un MDF de 6 no aguanta el trabajo de un travesaño.
    if not respaldo_entero(g, std):
        atr = Pieza(f"{pref}-TRS", "Travesaño trasero", largo=ancho_int,
                    ancho=round(std.ancho_travesano_respaldo, 1), espesor=e,
                    material=mc, cantidad=2, canto=_canto_visible(std, 0),
                    mueble=g.nombre,
                    nota="respaldo de travesaños: 1 arriba + 1 abajo, "
                         "el hueco de en medio deja pasar instalaciones")
        med = round(std.ancho_travesano_respaldo / 2, 1)
        atr.barrenos.append(Barreno(0, med, std.dia_minifix_canto, 25,
                                    cara="canto_L", nota="ens"))
        atr.barrenos.append(Barreno(ancho_int, med, std.dia_minifix_canto, 25,
                                    cara="canto_R", nota="ens"))
        P.append(atr)
    elif interior:                     # #003: encajonado entre costados, piso y tapa
        # #070 — el respaldo encajonado no se ranura ni se chaflanea: entra a
        # tope entre las cuatro piezas del cuerpo, y por arriba tope es tope
        # **también cuando no hay tapa completa**. El travesaño trasero ocupa
        # ese mismo plano, así que también se lleva su espesor.
        #
        # Hasta la 0.10.3 sólo se descontaba con tapa: con travesaños el
        # respaldo subía hasta el canto alto del mueble y se cruzaba con el
        # travesaño trasero. En pantalla es una pieza montada sobre otra; en el
        # taller es un respaldo que no entra y hay que rebajar en la sierra.
        a_resp = ancho_int
        h_resp = round(hc - 2 * e, 1)
        nota_resp = ("interior, encajonado a ras del fondo · entre piso y "
                     + ("tapa" if tapa else "travesaño"))
    elif ranurado:
        a_resp = round(ancho_int + 2 * std.prof_ranura - 1.0, 1)
        h_resp = round((hc - 2 * e if tapa else hc - e) + (2 if tapa else 1) * std.prof_ranura - 1.0, 1)
        nota_resp = "ranurado"
    else:
        a_resp, h_resp = g.ancho, hc
        nota_resp = "sobrepuesto"
    if respaldo_entero(g, std):
        P.append(Pieza(f"{pref}-RES", "Respaldo", largo=a_resp, ancho=h_resp, espesor=er,
                       material=std.mat_respaldo.nombre, cantidad=1, mueble=g.nombre,
                       nota=nota_resp))

    # ---------------- ENTREPAÑOS ----------------
    if g.n_entrepanos:
        a_ent = round(ancho_int - std.holgura_entrepano, 1)
        p_ent = round(prof_util - std.retranqueo_entrepano - (er if ranurado else 0), 1)
        P.append(Pieza(f"{pref}-ENT", "Entrepaño", largo=a_ent, ancho=p_ent, espesor=e,
                       material=mc, cantidad=g.n_entrepanos,
                       canto=_canto_visible(std, 0), mueble=g.nombre,
                       nota=("regulable" if not g.entrepanos_fijos else "fijo")
                            + " · alturas " + ", ".join(
                                f"{h:.0f}" for h in alturas_entrepanos(g, std, hc))))

    # ---------------- ENTREPAÑOS DIVISORIOS ----------------  #089
    divs = entrepanos_divisorios(g, std, hc)
    if divs:
        p_div = fondo_divisorio(std, prof_util, interior)      # #096
        P.append(Pieza(f"{pref}-DIV", "Entrepaño divisorio", largo=ancho_int,
                       ancho=p_div, espesor=e, material=mc, cantidad=len(divs),
                       canto=_canto_visible(std, 0), mueble=g.nombre,
                       nota="fijo, ensamblado · el de puerta queda tapado por "
                            "ella; el de nicho se mete en el módulo vecino · "
                            "alturas "
                            + ", ".join(f"{d['h']:.0f} ({d['ent']}, {d['modo']})"
                                        for d in divs)))

    # ---------------- FRENTES ----------------
    # #042 #045 — el manguete del uñero: la faja fija de arriba contra la que se
    # jala. Es una pieza más, no un adorno: se corta, se cantea y hay que
    # comprarla.
    #
    # #045, corrección de Mike: **va por dentro**, entre costado y costado, no
    # montado sobre el canto de los costados. Queda detrás de la puerta, y en el
    # hueco que la puerta deja arriba se ve el chaflán. Por eso mide el interior
    # del mueble (`ancho − 2 espesores`) y no el ancho de los frentes.
    hman = unero_de(g, std)
    mman = material_manguete(std)               # #067
    if hman > 0:
        # #063 — se corta hasta arriba del gabinete: lo que la nariz tapa
        # también es material. Lo que se ve son los `hman` de abajo.
        alto_man = round(hman + doblado_nariz(g, std), 1)
        P.append(Pieza(
            f"{pref}-MAN", "Manguete (uñero)",
            largo=ancho_int,
            ancho=alto_man, espesor=mman.espesor, material=mman.nombre, cantidad=1,
            # sólo el canto de abajo se ve: es el que lleva el chaflán y el que
            # mira al hueco. Los otros tres quedan tapados entre costados.
            canto=(std.canto_visible, 0.0, 0.0, 0.0), veta=True, mueble=g.nombre,
            chaflan=(True, False, False, False),            # #058
            nota="uñero: va entre costados, por detrás de la puerta · "
                 "canto inferior a 45°, mira al chaflán de la puerta"))

    mods = _repartir_frentes(g, hc, std)
    ic = 0
    for i, m in enumerate(mods):
        f: Frente = m["frente"]
        if f.tipo == "abierto":       # #090 — nicho: no se corta ningún frente
            continue
        if f.tipo == "puerta":
            aw = _ancho_hojas(g, f.n, std)
            pz = Pieza(f"{pref}-PTA{i+1}", f"Puerta ({f.n} hoja{'s' if f.n>1 else ''})",
                       largo=aw, ancho=m["alto_frente"], espesor=ef, material=mf,
                       cantidad=f.n, canto=(std.canto_visible,) * 4, veta=True, mueble=g.nombre)
            # cazoletas de bisagra Ø35 a 22 mm del borde
            nb = 2 if m["alto_frente"] < 1200 else 3
            ypos = [100.0, m["alto_frente"] - 100.0]
            if nb == 3:
                ypos.insert(1, m["alto_frente"] / 2)
            for y in ypos:
                pz.barrenos.append(Barreno(22.0, y, 35.0, 12.5, nota="cazoleta bisagra"))
            # #042 — el uñero es un chaflán en el canto de ARRIBA del frente de
            # hasta arriba. No cambia la medida de corte: cambia cómo se canteA
            # y se pasa por la tupí, y eso tiene que llegar al taller escrito.
            if i == 0 and unero_de(g, std) > 0:
                pz.nota = ((pz.nota + " · ") if pz.nota else "") + \
                    "uñero: canto superior a 45°"
                pz.chaflan = (False, True, False, False)     # #058
                pz.canto = (pz.canto[0], std.canto_visible,
                            pz.canto[2], pz.canto[3])
            P.append(pz)
        else:  # cajón
            ic += 1
            aw = round(g.ancho - 2 * std.holgura_perimetral, 1)
            P.append(Pieza(f"{pref}-FCJ{ic}", f"Frente de cajón {ic}", largo=aw,
                           ancho=m["alto_frente"], espesor=ef, material=mf, cantidad=1,
                           canto=(std.canto_visible,) * 4, veta=True, mueble=g.nombre))
            P += _piezas_caja_cajon(g, std, prof_util, ancho_int, ic, pref,
                                    alto_caja_de(m["alto_frente"], m["frente"]))

    # ---------------- ZOCLO ----------------
    if hz:
        P.append(Pieza(f"{pref}-ZOC", "Zoclo frontal", largo=g.ancho, ancho=hz, espesor=ef,
                       material=mf, cantidad=1, canto=_canto_visible(std, 1),
                       veta=True, mueble=g.nombre,
                       nota="desmontable, clips" if std.zoclo_desmontable else "fijo"))

    return _numerar(_aplicar_canto(_revisar_piezas(P, g), std), pref)


def _aplicar_canto(P: List[Pieza], std: Estandar) -> List[Pieza]:
    """#006: la medida terminada incluye el cubrecanto, así que la de corte lo resta.

    `canto` = (largo_inf, largo_sup, ancho_izq, ancho_der). Los dos primeros
    corren a lo largo de la pieza, así que engordan el ANCHO; los otros dos
    corren a lo ancho y engordan el LARGO.
    """
    cat = _materiales_de(std)
    for p in P:
        # #078 — el grosor del cubrecanto lo pone el material de LA PIEZA, no el
        # taller. Se corrige aquí y no en cada llamada de `_canto_visible()`:
        # un solo punto, y ninguna pieza se queda con el grosor de otro.
        esp = canto_de(std, p.material, cat)
        if any(p.canto):
            p.canto = tuple(esp if c else 0.0 for c in p.canto)
        p.largo_final, p.ancho_final = p.largo, p.ancho
        if not std.descontar_canto:
            continue
        c = p.canto
        largo = round(p.largo - c[2] - c[3], 2)
        ancho = round(p.ancho - c[0] - c[1], 2)
        if largo > 0 and ancho > 0:
            p.largo, p.ancho = largo, ancho
    return P


def _numerar(P: List[Pieza], pref: str) -> List[Pieza]:
    """#011: códigos cortos mueble.correlativo → 1.01, 1.02, 2.01…"""
    n = "".join(ch for ch in str(pref) if ch.isdigit()) or "1"
    for i, p in enumerate(P, start=1):
        p.codigo = f"{int(n)}.{i:02d}"
    return P


def _piezas_caja_cajon(g, std, pc, ancho_int, idx, pref, h=None) -> List[Pieza]:
    ec = std.mat_cajon.espesor
    ancho_caja = round(ancho_int - 2 * std.holgura_corredera_lado, 1)
    util = pc - std.retranqueo_fondo_cajon
    largo_corr = max([l for l in LARGOS_CORREDERA if l <= util], default=LARGOS_CORREDERA[0])
    # #097 — el alto lo manda el frente, no el estándar. El valor del estándar
    # queda sólo como red por si alguien llama a esta función sin pasarlo.
    h = float(h) if h else std.alto_caja_cajon
    a_int = round(ancho_caja - 2 * ec, 1)
    mcj, mfc = std.mat_cajon.nombre, std.mat_fondo_cajon.nombre
    return [
        Pieza(f"{pref}-CJL{idx}", f"Lateral caja cajón {idx}", largo=float(largo_corr), ancho=h,
              espesor=ec, material=mcj, cantidad=2, canto=_canto_visible(std, 1), mueble=g.nombre,
              nota=f"corredera {largo_corr} mm"),
        Pieza(f"{pref}-CJF{idx}", f"Frente/trasera caja cajón {idx}", largo=a_int, ancho=h,
              espesor=ec, material=mcj, cantidad=2, canto=_canto_visible(std, 1), mueble=g.nombre),
        Pieza(f"{pref}-CJB{idx}", f"Fondo caja cajón {idx}", largo=ancho_caja,
              ancho=float(largo_corr), espesor=std.mat_fondo_cajon.espesor, material=mfc,
              cantidad=1, mueble=g.nombre, nota="sobrepuesto/atornillado"),
    ]


# ---------------------------------------------------------------- presets
def preset_base(nombre="Base", ancho=900.0, alto=880.0, prof=600.0,
                puertas=2, cajones=0, entrepanos=1, cantidad=1) -> Gabinete:
    fr = []
    if cajones:
        for _ in range(cajones):
            fr.append(Frente("cajon", alto=180.0))
    if puertas:
        fr.append(Frente("puerta", alto=None, n=puertas))
    return Gabinete(nombre, "base", ancho, alto, prof, fr, entrepanos, cantidad=cantidad)


def preset_aereo(nombre="Aéreo", ancho=900.0, alto=700.0, prof=350.0,
                 puertas=2, entrepanos=1, cantidad=1) -> Gabinete:
    return Gabinete(nombre, "aereo", ancho, alto, prof,
                    [Frente("puerta", alto=None, n=puertas)], entrepanos,
                    tapa_completa=True, con_zoclo=False, cantidad=cantidad)


def preset_gaveteros(nombre="Cajonera", ancho=600.0, alto=880.0, prof=600.0,
                     cajones=4, cantidad=1) -> Gabinete:
    return Gabinete(nombre, "base", ancho, alto, prof,
                    [Frente("cajon") for _ in range(cajones)], 0, cantidad=cantidad)


# ---------------------------------------------------------------- #068
# El orden en que se arma e instala, que NO es el orden en que se capturó.
#
# Mike: «En el PDF de planos que se exporta, siempre cambia de orden el acomodo
# de los gabinetes del mueble, y es un problema grave porque en instalación lo
# van a armar mal.»
#
# No era que el orden cambiara entre exportaciones —eso es estable—: era que el
# orden de las páginas es el orden de la LISTA, o sea el orden en que se fueron
# agregando, y ése no tiene nada que ver con cómo quedan parados en la pared.
# En su HOLCIM CAR-02 la lista dice Base, Base copia, Cajonera y en la cocina
# están, de izquierda a derecha, Cajonera, Base, Base copia. El instalador lee
# «gabinete 1» y agarra el que no es.
#
# Lo que manda es la posición: se recorre el frente del mueble de izquierda a
# derecha. «Izquierda» es la del que está PARADO ENFRENTE, así que depende del
# giro: un mueble en la pared de enfrente (180°) se recorre al revés en x.
#
#   giro   frente mira a   el eje local +x (izq→der visto de frente) cae en
#    0°      −z                (+1,  0)
#   90°      +x                ( 0, +1)
#  180°      +z                (−1,  0)
#  270°      −x                ( 0, −1)
#
# Se agrupa por giro —cada pared es un tramo— y dentro de cada pared se ordena
# a lo largo de ese eje. Empatados, primero el de abajo: el bajo se instala
# antes que el aéreo que va encima.
_EJE_LOCAL = {0: (1.0, 0.0), 90: (0.0, 1.0), 180: (-1.0, 0.0), 270: (0.0, -1.0)}


def orden_instalacion(gabinetes: List[Gabinete]) -> List[int]:
    """Los índices de `gabinetes`, en el orden en que se arman en obra."""
    def clave(i):
        g = gabinetes[i]
        ex, ez = _EJE_LOCAL.get(int(getattr(g, "rot", 0) or 0) % 360, (1.0, 0.0))
        return (int(getattr(g, "rot", 0) or 0) % 360,
                (g.pos_x or 0.0) * ex + (g.pos_z or 0.0) * ez,
                1 if g.tipo == "aereo" else 0,
                i)
    return sorted(range(len(gabinetes)), key=clave)


def ordenados_para_instalar(gabinetes: List[Gabinete]):
    """Pares (n, gabinete) con n = 1..N en orden de instalación."""
    return [(n, gabinetes[i])
            for n, i in enumerate(orden_instalacion(gabinetes), start=1)]
