"""Verificación: cierre dimensional, integridad de nesting y conteos."""
import sys

# #091 — En Windows la consola no habla UTF-8: sale en cp1252 o en la página de
# códigos que tenga el equipo, y ahí no existen ni «→» ni «ñ». Los mensajes de
# abajo están llenos de las dos cosas, así que el primer `print` reventaba con
# UnicodeEncodeError y las 93 comprobaciones morían antes de decir si pasaban.
# En Linux nunca se notó, porque ahí la consola sí es UTF-8: por eso el «93 de
# 93» de todos los chats anteriores estaba medido sólo en Linux, y la primera
# corrida de apps.yml en Windows falló en este paso.
#
# `errors="replace"` es a propósito: si alguna consola rara tampoco puede con
# un carácter, se ve un signo de interrogación, pero la verificación termina y
# dice si pasó. Nunca se muere por un acento.
for _flujo in (sys.stdout, sys.stderr):
    try:
        _flujo.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

from core.config import Estandar
from core.modelos import (despiezar, _repartir_frentes, vuelo_de, holgura_frente,
                          espesor_cubierta)
from core.pieza import agrupar, expandir
from core.nesting import nestear
from cli import proyecto_demo

FALLAS = []


def chk(cond, msg):
    print(("  OK   " if cond else "  FALLA") + " " + msg)
    if not cond:
        FALLAS.append(msg)


std = Estandar()
gabs = proyecto_demo()
e = std.mat_cuerpo.espesor

for i, g in enumerate(gabs, 1):
    print(f"\n== {g.nombre} ({g.ancho}x{g.alto}x{g.prof}) ==")
    pz = despiezar(g, std, f"M{i:02d}")
    d = {p.nombre.split(" (")[0]: p for p in pz}

    # 1. cierre en ancho
    piso = next(p for p in pz if p.nombre == "Piso")
    chk(abs(piso.terminado[0] + 2 * e - g.ancho) < 0.01,
        f"ancho: piso {piso.terminado[0]} + 2x{e} = {piso.terminado[0] + 2*e} vs {g.ancho}")

    # 2. cierre en alto
    hz = std.altura_zoclo if (g.tipo == "base" and g.con_zoclo) else 0
    hc = g.alto - hz
    cos = next(p for p in pz if p.nombre == "Costado")
    # #059 — el alto tecleado es el del CONJUNTO: la plancha va por dentro.
    ec = espesor_cubierta(g, std)
    chk(abs(cos.terminado[0] + hz + ec - g.alto) < 0.01,
        f"alto: costado {cos.terminado[0]} + zoclo {hz} + cubierta {ec:.0f} = "
        f"{cos.terminado[0] + hz + ec} vs {g.alto}")

    # 3. cierre en profundidad — sobre la medida TERMINADA (el corte lleva menos canto, #006)
    # #043 el vuelo y #077 la holgura del frente salen del fondo declarado
    cos_prof = cos.terminado[1]
    vu_, hf_ = vuelo_de(g, std), holgura_frente(std)
    chk(abs(cos_prof + std.mat_frente.espesor + vu_ + hf_ - g.prof) < 0.01,
        f"prof: cuerpo {cos_prof} + frente {std.mat_frente.espesor} + vuelo {vu_:.0f}"
        f" + holgura {hf_:.0f} vs {g.prof}")

    # 4. frentes: suma de módulos = hc
    mods = _repartir_frentes(g, hc, std)
    if mods:
        chk(abs(sum(m["alto_mod"] for m in mods) - hc) < 0.01,
            f"frentes: suma módulos {sum(m['alto_mod'] for m in mods):.1f} vs cuerpo {hc}")
        # alto de frente < alto de módulo (siempre hay holgura)
        chk(all(m["alto_frente"] < m["alto_mod"] for m in mods), "holgura vertical en frentes > 0")

    # 5. puertas: n*ancho + holguras = ancho gabinete
    for m in mods:
        f = m["frente"]
        if f.tipo == "puerta":
            p = next(x for x in pz if x.nombre.startswith("Puerta"))
            pw = p.terminado[0]        # con el canto pegado (#006)
            total = pw * f.n + 2 * std.holgura_perimetral + (f.n - 1) * std.holgura_entre_frentes
            chk(abs(total - g.ancho) < 0.15,
                f"puertas: {f.n}x{pw} + holguras = {total:.1f} vs {g.ancho}")

    # 6. entrepaño cabe dentro
    if g.n_entrepanos:
        ent = next(p for p in pz if p.nombre == "Entrepaño")
        chk(ent.largo < piso.largo, f"entrepaño {ent.largo} < interior {piso.largo}")
        chk(ent.ancho < cos.ancho, f"entrepaño prof {ent.ancho} < cuerpo {cos.ancho}")

    # 7. cajón cabe
    lat = [p for p in pz if p.nombre.startswith("Lateral caja")]
    if lat:
        fondo = next(p for p in pz if p.nombre.startswith("Fondo caja"))
        chk(fondo.largo <= piso.largo - 2 * std.holgura_corredera_lado + 0.01,
            f"caja cajón {fondo.largo} + correderas <= interior {piso.largo}")
        chk(lat[0].largo <= cos.ancho, f"corredera {lat[0].largo} <= prof cuerpo {cos.ancho}")

    # 8. barrenos dentro de la pieza
    for p in pz:
        for b in p.barrenos:
            if b.cara == "A":
                ok = -0.01 <= b.x <= p.largo + 0.01 and -0.01 <= b.y <= p.ancho + 0.01
                if not ok:
                    chk(False, f"barreno fuera de {p.codigo}: ({b.x},{b.y}) en {p.largo}x{p.ancho}")

# ---------------- alturas (#001) ----------------
print("\n== ALTURAS: total = cuerpo + zoclo (#001) ==")
from core.modelos import alturas, AlturaInvalida
from core.proyecto import Proyecto
import copy as _copy

for derivado in ("cuerpo", "total", "zoclo"):
    g = _copy.deepcopy(gabs[0])
    g.alto_derivado = derivado
    g.alto, g.alto_cuerpo, g.altura_zoclo = 880.0, 760.0, 120.0
    t, c, z = alturas(g, std)
    chk(abs(t - (c + z)) < 0.01,
        f"derivado={derivado}: {t:.0f} = {c:.0f} + {z:.0f}")

# el override por gabinete gana sobre el estándar del proyecto
g = _copy.deepcopy(gabs[0]); g.altura_zoclo = 150.0
p = Proyecto("t"); p.gabinetes = [g]
_t, _c, z = alturas(g, p.estandar_de(g))
chk(abs(z - 150.0) < 0.01, f"override de zoclo por gabinete: {z:.0f} (proyecto: {std.altura_zoclo:.0f})")

g2 = _copy.deepcopy(gabs[0]); g2.altura_zoclo = None
_t, _c, z2 = alturas(g2, p.estandar_de(g2))
chk(abs(z2 - std.altura_zoclo) < 0.01, f"sin override hereda del proyecto: {z2:.0f}")

# subir el zoclo con el cuerpo derivado NO debe mover el cuerpo si se deriva el total
ga = _copy.deepcopy(gabs[0]); ga.alto_derivado = "total"; ga.alto_cuerpo = 780.0
t1, c1, _z = alturas(ga, std)
ga.altura_zoclo = 160.0
t2, c2, _z = alturas(ga, std)
chk(abs(c1 - c2) < 0.01 and t2 > t1,
    f"derivado=total: subir zoclo sube el total ({t1:.0f}→{t2:.0f}) y respeta el cuerpo ({c2:.0f})")

# con el cuerpo derivado, el total manda y el cuerpo absorbe
gb = _copy.deepcopy(gabs[0]); gb.alto_derivado = "cuerpo"; gb.alto = 880.0
t3, c3, _z = alturas(gb, std)
gb.altura_zoclo = 160.0
t4, c4, _z = alturas(gb, std)
chk(abs(t3 - t4) < 0.01 and c4 < c3,
    f"derivado=cuerpo: subir zoclo mantiene el total ({t4:.0f}) y baja el cuerpo ({c3:.0f}→{c4:.0f})")

# geometría: el despiece usa las alturas resueltas
gc = _copy.deepcopy(gabs[0]); gc.alto_derivado = "total"; gc.alto_cuerpo = 800.0; gc.altura_zoclo = 120.0
pz = despiezar(gc, p.estandar_de(gc), "MX")
cos = next(x for x in pz if x.nombre == "Costado")
zoc = next(x for x in pz if x.nombre.startswith("Zoclo"))
chk(abs(cos.largo - 800.0) < 0.01, f"costado usa el cuerpo capturado: {cos.largo:.0f}")
chk(abs(zoc.terminado[1] - 120.0) < 0.01,
    f"zoclo usa su altura propia: {zoc.terminado[1]:.0f} terminado ({zoc.ancho:.0f} de corte)")

# rechazo de combinaciones imposibles
gd = _copy.deepcopy(gabs[0]); gd.altura_zoclo = 900.0
try:
    alturas(gd, std)
    chk(False, "zoclo mayor que el total debe rechazarse")
except AlturaInvalida:
    chk(True, "zoclo mayor que el total se rechaza con mensaje claro")

# normalizar() deja alto = total real
gn = _copy.deepcopy(gabs[0]); gn.alto_derivado = "total"; gn.alto_cuerpo = 780.0; gn.altura_zoclo = 150.0
gn.alto = 1.0                       # valor sucio a propósito
pn = Proyecto("t"); pn.gabinetes = [gn]; pn.normalizar()
_esp = 930.0 + espesor_cubierta(gn, pn.estandar_de(gn))     # #059: la plancha cuenta
chk(abs(gn.alto - _esp) < 0.01,
    f"normalizar() corrige el total sucio: {gn.alto:.0f} (esperado {_esp:.0f})")

# ---------------- nesting ----------------
print("\n== NESTING ==")
todas = []
for i, g in enumerate(gabs, 1):
    pz = despiezar(g, std, f"M{i:02d}")
    for p in pz:
        p.cantidad *= g.cantidad
    todas += pz
todas = agrupar(todas)
hojas_mat = {m.nombre: (m.largo_hoja, m.ancho_hoja) for m in
             (std.mat_cuerpo, std.mat_frente, std.mat_respaldo, std.mat_cajon, std.mat_fondo_cajon)}
hojas = nestear(todas, std, hojas_mat)

n_esperado = sum(p.cantidad for p in todas)
n_colocado = sum(len(h.colocaciones) for h in hojas)
chk(n_esperado == n_colocado, f"piezas colocadas {n_colocado} = esperadas {n_esperado}")

for h in hojas:
    for c in h.colocaciones:
        chk(c.x >= std.margen_hoja - 0.01 and c.y >= std.margen_hoja - 0.01 and
            c.x + c.w <= h.ancho - std.margen_hoja + 0.01 and
            c.y + c.h <= h.alto - std.margen_hoja + 0.01,
            f"hoja {h.idx}: pieza {c.pieza.codigo} dentro de márgenes") if False else None
    # traslapes
    cs = h.colocaciones
    for i in range(len(cs)):
        for j in range(i + 1, len(cs)):
            a, b = cs[i], cs[j]
            solapa = not (a.x + a.w <= b.x + 0.01 or b.x + b.w <= a.x + 0.01 or
                          a.y + a.h <= b.y + 0.01 or b.y + b.h <= a.y + 0.01)
            if solapa:
                chk(False, f"hoja {h.idx}: traslape {a.pieza.codigo} / {b.pieza.codigo}")
    dentro = all(c.x >= std.margen_hoja - 0.01 and c.y >= std.margen_hoja - 0.01 and
                 c.x + c.w <= h.ancho - std.margen_hoja + 0.01 and
                 c.y + c.h <= h.alto - std.margen_hoja + 0.01 for c in cs)
    chk(dentro, f"hoja {h.idx}: todas las piezas dentro de márgenes")
    mismo_mat = all(c.pieza.material == h.material and c.pieza.espesor == h.espesor for c in cs)
    chk(mismo_mat, f"hoja {h.idx}: material homogéneo")

area_pz = sum(p.area_m2 * p.cantidad for p in todas)
area_hj = sum(h.ancho * h.alto for h in hojas) / 1e6
print(f"\n  Área piezas: {area_pz:.2f} m² | Área hojas: {area_hj:.2f} m² | "
      f"aprovechamiento global {area_pz/area_hj*100:.1f}%")
# ---------------- cambios #002-#013 ----------------
print("\n== #003 RESPALDO INTERIOR ==")
from core.modelos import respaldo_interior
import copy as _c
s6 = _c.deepcopy(std); s6.mat_respaldo.espesor = 6.0
s18 = _c.deepcopy(std); s18.mat_respaldo.espesor = 18.0
chk(not respaldo_interior(s6), "6 mm sigue ranurado")
chk(respaldo_interior(s18), f"18 mm va por dentro (umbral {std.respaldo_interior_desde:.0f})")
p6 = despiezar(gabs[0], s6, "1"); p18 = despiezar(gabs[0], s18, "1")
r6 = next(x for x in p6 if x.nombre == "Respaldo")
r18 = next(x for x in p18 if x.nombre == "Respaldo")
c18 = next(x for x in p18 if x.nombre == "Costado")
e6 = next(x for x in p6 if x.nombre == "Entrepaño")
e18 = next(x for x in p18 if x.nombre == "Entrepaño")
piso = next(x for x in p18 if x.nombre == "Piso")
chk(abs(r18.largo - (gabs[0].ancho - 2 * s18.mat_cuerpo.espesor)) < 0.1,
    f"respaldo interior encaja entre costados: {r18.largo:.0f}")
chk(len(c18.ranuras) == 0, "sin ranura en el costado")
chk(len(next(x for x in p6 if x.nombre == 'Costado').ranuras) == 1, "el de 6 mm sí lleva ranura")
chk(e18.ancho < e6.ancho, f"el entrepaño se acorta: {e6.ancho:.0f} → {e18.ancho:.0f}")
# en ambos casos el fondo se reparte: entrepaño + retranqueo + espesor de respaldo = cuerpo
pc_ref = (gabs[0].prof - std.mat_frente.espesor
          - vuelo_de(gabs[0], std) - holgura_frente(std))
for nom, ent, esp in (("6 mm ranurado", e6, 6.0), ("18 mm interior", e18, 18.0)):
    suma = ent.terminado[1] + std.retranqueo_entrepano + esp
    chk(abs(suma - pc_ref) < 0.1,
        f"{nom}: entrepaño {ent.terminado[1]:.0f} + retranqueo {std.retranqueo_entrepano:.0f}"
        f" + respaldo {esp:.0f} = {suma:.0f} (cuerpo {pc_ref:.0f})")
chk(sum(1 for b in c18.barrenos if b.nota == "ens-respaldo") >= 2,
    "el respaldo interior lleva ensamble")

print("\n== #006 CUBRECANTO DESCONTADO ==")
sc = _c.deepcopy(std); sc.descontar_canto = True
sn = _c.deepcopy(std); sn.descontar_canto = False
pc_, pn_ = despiezar(gabs[0], sc, "1"), despiezar(gabs[0], sn, "1")
pta_c = next(x for x in pc_ if x.nombre.startswith("Puerta"))
pta_n = next(x for x in pn_ if x.nombre.startswith("Puerta"))
cv = std.canto_visible
chk(abs((pta_n.largo - pta_c.largo) - 2 * cv) < 0.01,
    f"puerta con canto en 4 lados: corte {pta_c.largo} vs nominal {pta_n.largo}")
lf, af = pta_c.terminado
chk(abs(lf - pta_n.largo) < 0.01 and abs(af - pta_n.ancho) < 0.01,
    f"la medida terminada conserva la nominal: {lf} × {af}")
res_c = next(x for x in pc_ if x.nombre == "Respaldo")
chk(res_c.largo == res_c.terminado[0], "una pieza sin canto no cambia de medida")
cos_c = next(x for x in pc_ if x.nombre == "Costado")
chk(abs(cos_c.ancho - (cos_c.terminado[1] - cv)) < 0.01,
    f"el canto de un solo borde descuenta una vez: {cos_c.ancho} (nominal {cos_c.terminado[1]})")

print("\n== #011 NOMENCLATURA ==")
import re as _re
todos = []
for i, g in enumerate(gabs, 1):
    todos += despiezar(g, std, str(i))
chk(all(_re.fullmatch(r"\d+\.\d{2}", p.codigo) for p in todos),
    f"todos con formato mueble.correlativo (ej. {todos[0].codigo}, {todos[-1].codigo})")
chk(len({p.codigo for p in todos}) == len(todos), "sin códigos repetidos entre muebles")
chk(max(len(p.codigo) for p in todos) <= 6,
    f"códigos cortos: máximo {max(len(p.codigo) for p in todos)} caracteres")

print("\n== #005 LAS 6 CARAS ==")
from core import iso as ISO2
s_ = ISO2.solidos_gabinete(gabs[0], std)[0]
chk(len(ISO2.caras(s_)) == 6, "cada tablero aporta 6 caras al render")
chk(len(ISO2.caras_visibles(s_)) == 3, "el dibujo vectorial sigue usando 3")
norm = {round(sum(p[0] for p in c) / 4, 3) for c, _k in ISO2.caras(s_)}
chk(len(norm) >= 2, "las caras cubren ambos extremos en X")

print("\n== #009 COLOR POR MATERIAL ==")
sm = _c.deepcopy(std)
sm.mat_frente = _c.deepcopy(std.mat_frente)
sm.mat_frente.nombre = "Melamina madera 18mm"
sm.mat_frente.color = "#B98A52"
sol = ISO2.solidos_gabinete(gabs[0], sm)
fr = next(x for x in sol if x.grupo == "frente")
co = next(x for x in sol if x.grupo == "costado_izq")
chk(fr.material == "Melamina madera 18mm", f"el frente sabe su material: {fr.material}")
chk(fr.color != co.color, "frente y cuerpo se pintan distinto")
chk(ISO2.hex_a_rgb("#B98A52") is not None and ISO2.hex_a_rgb("xx") is None,
    "el color inválido no rompe el render")

print("\n== #004 POSICIÓN Y GIRO ==")
gp = _c.deepcopy(gabs[0]); gp.pos_x, gp.pos_z, gp.rot = 1000, 500, 0
h0 = ISO2.huella(gp)
chk(h0 == (1000, 500, 1000 + gp.ancho, 500 + gp.prof), f"huella sin girar: {h0}")
gp.rot = 90
h9 = ISO2.huella(gp)
chk(h9 == (1000, 500, 1000 + gp.prof, 500 + gp.ancho), f"al girar 90° se intercambian: {h9}")
for r in (0, 90, 180, 270):
    gp.rot = r
    sc_ = ISO2.colocar(ISO2.solidos_gabinete(gp, std), gp, std)
    xs = [q.x for q in sc_] + [q.x + q.dx for q in sc_]
    ys = [q.y for q in sc_] + [q.y + q.dy for q in sc_]
    hh = ISO2.huella(gp)
    # #043 — la huella es la del CONJUNTO: por delante la ocupa la plancha, y
    # el mueble empieza `vuelo` más atrás. Lo que se comprueba es que nada se
    # salga y que el respaldo caiga justo en la pared, no que el mueble llene
    # la huella por los cuatro lados.
    ok = (min(xs) >= hh[0] - 0.1 and min(ys) >= hh[1] - 0.1
          and max(xs) <= hh[2] + 0.1 and max(ys) <= hh[3] + 0.1)
    chk(ok, f"giro {r}°: los sólidos caen dentro de la huella  "
            f"[{min(xs):.0f},{min(ys):.0f} → {max(xs):.0f},{max(ys):.0f}] en {hh}")
    pegado = (abs(min(xs) - hh[0]) < 0.1 or abs(min(ys) - hh[1]) < 0.1
              or abs(max(xs) - hh[2]) < 0.1 or abs(max(ys) - hh[3]) < 0.1)
    chk(pegado, f"giro {r}°: y el mueble toca la pared de su huella")
ga_ = _c.deepcopy(gabs[1])
chk(ISO2.base_z(ga_, std) == std.altura_colgado_aereo,
    f"el aéreo se cuelga a {std.altura_colgado_aereo:.0f}")
ga_.alto_colgado = 1600
chk(ISO2.base_z(ga_, std) == 1600, "el colgado propio gana al del proyecto")

# ---------------- #014 VALIDACIÓN DE MEDIDAS ----------------
print("\n== #014 VALIDACIÓN DE MEDIDAS ==")
from core.modelos import GeometriaInvalida, validar, Gabinete as _G, Frente as _F
from core.nesting import nestear as _nest

def _gab(**kw):
    base = dict(nombre="Prueba", tipo="base", ancho=900, alto=880, prof=600,
                frentes=[_F("puerta", n=2)], n_entrepanos=1)
    base.update(kw)
    return _G(**base)

for nom, kw in [("ancho 30 mm", dict(ancho=30)), ("prof 10 mm", dict(prof=10)),
                ("ancho negativo", dict(ancho=-500)), ("prof 0", dict(prof=0)),
                ("ancho 0", dict(ancho=0))]:
    try:
        despiezar(_gab(**kw), std, "1")
        chk(False, f"{nom}: debía rechazarse y pasó")
    except GeometriaInvalida as ex:
        chk("mm" in str(ex) or "0" in str(ex), f"{nom} rechazado — «{str(ex)[:64]}…»")

pz_ok = despiezar(_gab(), std, "1")
chk(all(p.largo > 0 and p.ancho > 0 for p in pz_ok),
    f"un gabinete normal pasa con {len(pz_ok)} piezas sanas")
chk(min(min(p.largo, p.ancho) for p in pz_ok) > 0,
    f"pieza más chica: {min(min(p.largo, p.ancho) for p in pz_ok):.0f} mm")

# el mínimo es constructivo, no arbitrario
e_ = std.mat_cuerpo.espesor
try:
    despiezar(_gab(ancho=2 * e_ + 50), std, "1")
    chk(True, f"el mínimo de ancho ({2*e_+50:.0f} mm) sí se acepta")
except GeometriaInvalida:
    chk(False, "el mínimo de ancho se rechaza a sí mismo")

# pieza que no cabe en la hoja → mensaje accionable, no traceback
try:
    g_gr = _gab(nombre="Enorme", ancho=2600)
    _nest(despiezar(g_gr, std, "1"), std,
          {std.mat_cuerpo.nombre: (2440, 1220), std.mat_frente.nombre: (2440, 1220),
           std.mat_respaldo.nombre: (2440, 1220), std.mat_cajon.nombre: (2440, 1220)})
    chk(False, "una pieza más larga que la hoja debía rechazarse")
except GeometriaInvalida as ex:
    chk("no cabe" in str(ex) and "hoja" in str(ex),
        f"pieza mayor que la hoja: «{str(ex)[:70]}…»")

# la red de seguridad atrapa cualquier pieza <= 0 aunque validar() no la vea
from core.modelos import _revisar_piezas
from core.pieza import Pieza as _P
try:
    _revisar_piezas([_P("1.01", "Costado", 100, -5, 18, "M")], _gab())
    chk(False, "la red de seguridad dejó pasar una pieza negativa")
except GeometriaInvalida as ex:
    chk("imposible" in str(ex), "la red de seguridad atrapa piezas con medida <= 0")


# ------------------------------------------------------- #094 nombre bajado
#
# El nombre del instalador lo publica el flujo en el JSON. Si la app lo guarda
# con un nombre y lo busca con otro, se vuelve a bajar 120 MB en cada arranque
# sin que nadie entienda por qué. Y como ese nombre viene de un archivo de
# fuera, tampoco puede servir para escribir donde no debe.
print("\n== #094 NOMBRE DEL INSTALADOR ==")
from core import actualizar as _ACT                                # noqa: E402

def _nom(archivo=None, url="", version="1.0.0"):
    win = {}
    if archivo is not None:
        win["archivo"] = archivo
    if url:
        win["url"] = url
    return _ACT.leer_estado({"nest101": {"version": version, "windows": win}})["archivo"]

chk(_nom("nest101-0.16.0-setup.exe") == "nest101-0.16.0-setup.exe",
    "se usa el nombre que publica el flujo")
chk(_nom(None, "https://x/y/nest101-9.9.9-setup.exe", "9.9.9") == "nest101-9.9.9-setup.exe",
    "si no viene, se saca del final de la URL")
chk(_nom(None) == "nest101-1.0.0-setup.exe",
    "sin nombre ni URL, se arma por convención")
for feo, qué in [("../../../evil.exe", "«..» para salirse de la carpeta"),
                 ("C:\\Windows\\System32\\mal.exe", "ruta absoluta de Windows"),
                 ("/etc/passwd", "ruta absoluta de Linux"),
                 ("otroprograma-setup.exe", "instalador de otro programa"),
                 ("Diagnostico.bat", "algo que no es instalador")]:
    chk(_nom(feo) == "nest101-1.0.0-setup.exe", f"se rechaza: {qué}")

_ruta = _ACT.destino_de("0.16.0", "nest101-0.16.0-setup.exe")
chk(_ruta.endswith("nest101-0.16.0-setup.exe"), "el archivo se guarda con ese nombre")
chk("descargas" in _ruta, "y dentro de la carpeta de descargas del taller")
chk(_ACT.destino_de("0.16.0", "../fuera.exe") == _ACT.destino_de("0.16.0"),
    "un nombre torcido cae en el de siempre, nunca fuera de la carpeta")

# --------------------------------------- #096 el divisorio no llega al respaldo
#
# Mike: «no deben llegar hasta el fondo, se les debe restar el espesor del
# panel de fondo». El 3D lo enseñaba: el divisorio atravesaba el respaldo. Y de
# paso se vio que el despiece y el dibujo sacaban el fondo de fórmulas
# distintas. Ahora los dos llaman a fondo_divisorio().
print("\n== #096 FONDO DEL ENTREPAÑO DIVISORIO ==")
import dataclasses as _dc                                         # noqa: E402
from core.modelos import (fondo_divisorio as _fd,                 # noqa: E402
                          Gabinete as _Gab, Frente as _Fre)
from core.iso import solidos_gabinete as _sg                      # noqa: E402

def _torre(std):
    return _Gab(nombre="Torre", ancho=600, prof=600, alto=2100, tipo="base",
                frentes=[_Fre(tipo=t, alto=(180.0 if t == "cajon" else None))
                         for t in ("cajon", "abierto", "cajon")])

_e6 = Estandar()
_e18 = _dc.replace(_e6, mat_respaldo=_dc.replace(_e6.mat_respaldo, espesor=18.0))
for _nom, _std in [("ranurado", _e6),
                   ("sobrepuesto", _dc.replace(_e6, respaldo_ranurado=False)),
                   ("interior 18mm", _e18)]:
    _g = _torre(_std)
    _div = [p for p in despiezar(_g, _std) if p.nombre == "Entrepaño divisorio"]
    chk(bool(_div), f"{_nom}: el nicho genera divisorios")
    _S = _sg(_g, _std)
    _d3 = [s for s in _S if s.codigo == "DIV"]
    _r3 = [s for s in _S if s.grupo == "respaldo"]
    if _div and _d3 and _r3:
        _fin, _resp = _d3[0].y + _d3[0].dy, _r3[0].y
        chk(_fin <= _resp + 0.01,
            f"{_nom}: el divisorio no se mete en el respaldo ({_fin:.0f} <= {_resp:.0f})")
        chk(_div[0].ancho < _d3[0].dy + 1.01,
            f"{_nom}: corte y 3D salen del mismo cálculo ({_div[0].ancho:.0f} vs {_d3[0].dy:.0f})")
    # el descuento se hace una sola vez: si el respaldo va por dentro, prof_util
    # ya lo traía restado y volver a restarlo comería fondo de más
    chk(_fd(_std, 500.0, True) == 500.0, f"{_nom}: respaldo interior no se resta dos veces")
    chk(_fd(_std, 500.0, False) == 500.0 - _std.mat_respaldo.espesor,
        f"{_nom}: respaldo ranurado o sobrepuesto sí se resta")

# ------------------------------------------------- #098 textos sin traducir
#
# La interfaz arranca en inglés por omisión, y el diccionario se busca por el
# texto en español. Un texto nuevo sin entrada no truena: sale en español en
# media pantalla en inglés, y nadie se entera hasta que un cliente lo ve. Pasó
# con «Cajones» y «Fondos de cajón» en la leyenda del 3D.
print("\n== #098 TEXTOS TRADUCIDOS ==")
import json as _json                                              # noqa: E402
from pathlib import Path as _Path                                 # noqa: E402

_dic = _json.loads((_Path(__file__).parent / "assets" / "idioma" / "en.json")
                   .read_text(encoding="utf-8"))
from core.modelos import Frente as _Fr, Gabinete as _Gb            # noqa: E402
for _txt in ["Entrepaño divisorio", "Abierto (nicho)", "+ Nicho", "Cajones",
             "Fondos de cajón", "Caja", "Ver adentro",
             "Lateral izq caja cajón #", "Frente caja cajón #",
             "Trasera caja cajón #", "Fondo caja cajón #",
             "Lateral caja cajón #", "Frente/trasera caja cajón #"]:
    chk(bool(_dic.get(_txt)), f"«{_txt}» tiene traducción — {_dic.get(_txt, 'FALTA')}")

# Los nombres que inventa el motor llevan número, y el diccionario los guarda
# con «#» en su lugar. Si alguien cambia el nombre de una pieza y no toca el
# diccionario, esto lo caza.
_g98 = _Gb(nombre="V", tipo="base", ancho=600.0, alto=880.0, prof=600.0,
           frentes=[_Fr("cajon", alto=180.0), _Fr("puerta")])
import re as _re                                                  # noqa: E402
for _pz in despiezar(_g98, std):
    if "cajón" in _pz.nombre or "divisorio" in _pz.nombre:
        _clave = _re.sub(r"\d+", "#", _pz.nombre).strip()
        chk(bool(_dic.get(_clave)) or bool(_dic.get(_pz.nombre)),
            f"la pieza «{_pz.nombre}» se puede traducir")

# ------------------------------------- #097 alto de las paredes de la caja
#
# Mike: «la altura de las paredes del cajón debe ser por default del 80 % de la
# altura del frente, redondeada al número cerrado (cm) más cercano hacia
# arriba. Aparte, una opción de editarla por cajón».
#
# Antes era un número fijo del estándar —90 mm para todos—, y daba la misma
# caja bajo un frente de 120 y bajo uno de 300.
print("\n== #097 ALTO DE LA CAJA DEL CAJÓN ==")
from core.iso import solidos_gabinete as _sol                      # noqa: E402
from core.modelos import alto_caja_de as _aca                      # noqa: E402

for _frente, _esperado, _porque in [
        (120.0, 100.0, "96 sube a 100"),
        (150.0, 120.0, "120 ya es cerrado, no sube"),
        (180.0, 150.0, "144 sube a 150"),
        (200.0, 160.0, "160 ya es cerrado"),
        (300.0, 240.0, "240 ya es cerrado"),
        (89.0, 80.0, "71.2 sube a 80")]:
    chk(_aca(_frente) == _esperado,
        f"frente {_frente:.0f} → caja {_aca(_frente):.0f} mm ({_porque})")

chk(_aca(180.0) == _aca(180.0, _Fr("cajon", alto=180.0)),
    "sin valor a mano, el frente no cambia la cuenta")
chk(_aca(180.0, _Fr("cajon", alto=180.0, alto_caja=120.0)) == 120.0,
    "un valor puesto a mano manda sobre el 80 %")
chk(_aca(180.0, _Fr("cajon", alto=180.0, alto_caja=None)) == 150.0,
    "dejarlo vacío vuelve al automático")

# Y lo que importa de verdad: que ese alto llegue igual a las dos salidas.
_g97 = _Gb(nombre="V", tipo="base", ancho=600.0, alto=880.0, prof=600.0,
           frentes=[_Fr("cajon", alto=180.0), _Fr("cajon", alto=300.0),
                    _Fr("cajon", alto=180.0, alto_caja=120.0)])
_P97 = [q for q in despiezar(_g97, std) if "Lateral caja" in q.nombre]
_S97 = [x for x in _sol(_g97, std) if x.grupo == "cajon" and "Lateral izq" in x.etiqueta]
chk([q.ancho_final for q in _P97] == [150.0, 240.0, 120.0],
    f"corte: los tres cajones salen 150/240/120 → {[q.ancho_final for q in _P97]}")
chk([round(x.dz, 1) for x in _S97] == [150.0, 240.0, 120.0],
    f"3D: los tres cajones salen 150/240/120 → {[round(x.dz, 1) for x in _S97]}")

# Un alto de caja imposible se rechaza con mensaje, no con traceback.
try:
    despiezar(_Gb(nombre="V", tipo="base", ancho=600.0, alto=880.0, prof=600.0,
                  frentes=[_Fr("cajon", alto=180.0, alto_caja=-5.0)]), std)
    _ok97, _m97 = False, "no se rechazó"
except GeometriaInvalida as _e:
    _ok97, _m97 = True, str(_e)[:60]
chk(_ok97, f"un alto de caja negativo se rechaza — «{_m97}…»")

# ------------------------------------------- #096 el 3D contra la lista de corte
#
# Mike: «necesito que el 3D dibuje los cajones como se están computando, no un
# cubo representativo, y confirmar que sea fiel a lo que se manda a corte».
#
# La caja del cajón ya no es un bloque: son sus cinco piezas. Esta comprobación
# es la otra mitad de la petición, y vale más que mirar una captura: cada
# sólido del 3D tiene que existir en la lista de corte con LAS MISMAS medidas.
#
# Se compara contra la medida TERMINADA, no contra la de corte. No es un
# detalle: la lista dice 89 mm porque es lo que se corta, y la pieza mide 90 ya
# con su canto de 1 mm pegado. El 3D enseña el mueble armado, así que le toca
# la terminada. Comparar contra la de corte daría un error de un milímetro por
# cada canto y sería la comprobación la que está mal.
print("\n== #096 EL 3D CONTRA LA LISTA DE CORTE ==")
def _terminada(pz):
    """Las tres medidas de la pieza ya armada, ordenadas para poder compararlas
    sin depender de cómo se orientó en el mueble."""
    largo = pz.largo_final if pz.largo_final is not None else pz.largo
    ancho = pz.ancho_final if pz.ancho_final is not None else pz.ancho
    return tuple(sorted((round(largo, 1), round(ancho, 1), round(pz.espesor, 1))))

for _nom, _fr in [("3 cajones", [_Fr("cajon", alto=180.0) for _ in range(3)]),
                  ("cajón y puerta", [_Fr("cajon", alto=180.0), _Fr("puerta")]),
                  ("cajón, nicho, cajón", [_Fr("cajon", alto=180.0), _Fr("abierto"),
                                           _Fr("cajon", alto=180.0)])]:
    _g = _Gb(nombre="V", tipo="base", ancho=600.0, alto=880.0, prof=600.0, frentes=_fr)
    _P = despiezar(_g, std)
    _S = [x for x in _sol(_g, std) if x.grupo in ("cajon", "cajon_fondo")]

    # cuántas piezas de caja de cajón hay en corte, contando las de cantidad 2
    _de_caja = [q for q in _P if "caja cajón" in q.nombre]
    _n_corte = sum(int(q.cantidad) for q in _de_caja)
    chk(len(_S) == _n_corte,
        f"{_nom}: el 3D dibuja {len(_S)} piezas de caja y la lista manda cortar {_n_corte}")

    # y cada sólido tiene que existir en la lista con las mismas tres medidas
    _medidas = {}
    for q in _de_caja:
        _medidas.setdefault(_terminada(q), []).append(q.nombre)
    _malas = []
    for _s in _S:
        _tres = tuple(sorted((round(_s.dx, 1), round(_s.dy, 1), round(_s.dz, 1))))
        if _tres not in _medidas:
            _malas.append(f"{_s.etiqueta} {_tres}")
    chk(not _malas,
        f"{_nom}: cada pieza del 3D cuadra con una de corte"
        + (f" — NO cuadran: {'; '.join(_malas)}" if _malas else ""))

    # el material dibujado también tiene que ser el que se va a cortar
    _mats3d = {x.material for x in _S}
    _matsco = {q.material for q in _de_caja}
    chk(_mats3d == _matsco,
        f"{_nom}: mismos materiales en 3D y en corte ({', '.join(sorted(_mats3d))})")

# Un mueble sin cajones no dibuja ninguna caja.
_sin = _Gb(nombre="V", tipo="base", ancho=600.0, alto=880.0, prof=600.0,
           frentes=[_Fr("puerta")])
chk(not [x for x in _sol(_sin, std) if x.grupo in ("cajon", "cajon_fondo")],
    "un mueble de pura puerta no dibuja cajas de cajón")

# ----------------------------------------------- #095 librerías del instalador
#
# Las 0.16.0 y 0.16.1 se publicaron sin cuatro librerías: la receta del flujo
# instalaba siete paquetes y el código importa once. Todo salió verde —las
# comprobaciones de aquí sólo tocan el motor de cálculo, que no las usa— y el
# instalador se publicó roto: al arrancar, server.py reventaba al importar y la
# app se quedaba clavada en la pantalla de arranque, sin decir por qué.
#
# Esto corre con el MISMO Python que viaja dentro del instalador, así que si
# falta una, la compilación se pone roja antes de publicar nada.
print("\n== #095 LIBRERÍAS QUE NECESITA LA APP ==")
import importlib as _il                                           # noqa: E402

for _lib, _para in [
        ("fastapi", "el servidor"), ("uvicorn", "el servidor"),
        ("pydantic", "validar lo que llega"), ("multipart", "recibir archivos subidos"),
        ("numpy", "cálculo"), ("PIL", "imágenes"),
        ("ezdxf", "exportar DXF"), ("openpyxl", "exportar Excel"),
        ("reportlab", "exportar PDF"), ("cv2", "leer planos"),
        ("pypdfium2", "abrir planos en PDF"), ("anthropic", "identificar piezas")]:
    try:
        _il.import_module(_lib)
        _ok, _detalle = True, ""
    except Exception as _e:                                       # noqa: BLE001
        _ok, _detalle = False, f" — {type(_e).__name__}: {_e}"
    chk(_ok, f"{_lib} carga ({_para}){_detalle}")

# multipart no se importa en el código, pero FastAPI lo exige en cuanto una ruta
# recibe un archivo. Sin él la app no truena al compilar: truena al arrancar.
try:
    from fastapi import FastAPI as _FA, File as _File, UploadFile as _UF
    _app = _FA()

    @_app.post("/x")
    async def _subir(f: _UF = _File(...)):                        # noqa: ANN202
        return {}
    _ok2, _d2 = True, ""
except Exception as _e:                                           # noqa: BLE001
    _ok2, _d2 = False, f" — {_e}"
chk(_ok2, f"una ruta que recibe archivos se puede declarar{_d2}")

# El veredicto va AL FINAL y con código de salida.
#
# Estaba a la mitad del archivo y sin `sys.exit`: contaba sólo lo que había
# corrido hasta ahí, y la tubería de compilación lo daba por bueno aunque
# fallara. Once comprobaciones llevaban rotas desde #043/#059 —seguían
# esperando `cuerpo + frente = fondo` y `costado + zoclo = alto`, que dejó de
# ser cierto cuando el vuelo y la plancha empezaron a salir de la medida
# declarada— y nadie se enteró, porque al leer el final del archivo salían
# líneas OK. Un veredicto que no se ve al final no es un veredicto.
import sys as _sys                                                # noqa: E402
print(f"\n{'TODO OK' if not FALLAS else str(len(FALLAS)) + ' FALLAS'}")
_sys.exit(1 if FALLAS else 0)
