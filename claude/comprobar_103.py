"""#103 — el zoclo se ve en el 3D, pero no se corta.  Comprobación suelta.

Mike, 30-sep-2026: *«cuando se hagan los despieces y cortes no incluyas los
zoclos. Los zoclos sólo son para referencia para visualmente ver cómo queda el
diseño, pero esos no se hacen en este tipo de despiece»*.

Se corre solo:

    python claude/comprobar_103.py        # sale 0 si todo está bien

Está aparte de `verificar.py` por un motivo de plomería, no de criterio: la
sesión que lo escribió no tiene empuje directo a este repositorio y el conector
de GitHub no puede reescribir archivos tan grandes como `verificar.py`. Lo que
mide es exactamente lo que mediría allá dentro, y en cuanto alguien con empuje
pase por aquí, el bloque se muda a `verificar.py` —ver
`claude/101-102-pendiente.md`— y este archivo se borra.

Mide las dos mitades del asunto, que es lo que hace que la comprobación valga:
que el zoclo NO aparezca en ninguna salida, y que siga existiendo donde sí
sirve. Una prueba que sólo mirara la primera mitad pasaría igual si alguien
borrara el zoclo del programa entero.
"""

from __future__ import annotations

import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))

from core import iso as ISO                                  # noqa: E402
from core.config import Estandar                             # noqa: E402
from core.modelos import Frente, Gabinete, alturas, despiezar  # noqa: E402
from core.proyecto import Proyecto                           # noqa: E402

FALLAS = []


def chk(cond, msg):
    print(("  OK   " if cond else "  FALLA") + " " + msg)
    if not cond:
        FALLAS.append(msg)


std = Estandar()

print("\n== #103: el zoclo se ve, pero no se corta ==")

g = Gabinete(nombre="con zoclo", tipo="base", ancho=900, alto=900.0, prof=600,
             con_zoclo=True, altura_zoclo=120.0,
             frentes=[Frente("puerta", n=2)], n_entrepanos=1)
pr = Proyecto("t103")
pr.estandar = std
pr.gabinetes = [g]
piezas, hojas, _solidos = pr.calcular()

# --- lo que NO debe aparecer ---------------------------------------------
chk(not [p for p in piezas if "zoclo" in p.nombre.lower()],
    f"la lista de corte no trae zoclos ({len(piezas)} piezas: "
    + ", ".join(sorted({p.nombre for p in piezas})) + ")")
chk(not [c for h in hojas for c in h.colocaciones if "zoclo" in c.pieza.nombre.lower()],
    "ninguna hoja de nesting acomoda un zoclo")
chk(not [p for p in piezas if p.codigo.endswith("ZOC")],
    "tampoco queda su código ZOC en ninguna pieza")
chk(all("zoclo" not in p.nombre.lower() for p in piezas),
    "el costeo tampoco lo cobra: sale de esta misma lista")

# --- lo que SÍ debe seguir igual -----------------------------------------
total, cuerpo, hz = alturas(g, std)
chk(abs(hz - 120.0) < 0.01 and abs(cuerpo - (total - 120.0)) < 0.01,
    f"el zoclo sigue restando: cuerpo {cuerpo:.0f} = total {total:.0f} − zoclo {hz:.0f}")
costado = next(p for p in piezas if p.nombre == "Costado")
chk(abs(costado.largo - cuerpo) < 0.01,
    f"el costado se corta al cuerpo, no al total: {costado.largo:.0f}")
chk(any(s.grupo == "zoclo" for s in ISO.solidos_gabinete(g, std)),
    "el 3D sí dibuja el zoclo: es para lo que sirve")

# --- el control: un mueble que nunca tuvo zoclo no cambia en nada ---------
aereo = Gabinete(nombre="sin zoclo", tipo="aereo", ancho=900, alto=700.0, prof=350,
                 frentes=[Frente("puerta", n=2)])
pr2 = Proyecto("t103b")
pr2.estandar = std
pr2.gabinetes = [aereo]
chk(len(pr2.calcular()[0]) == len(despiezar(aereo, std, "1")),
    "el aéreo entrega las mismas piezas que antes (control)")

print(f"\n{'TODO OK' if not FALLAS else str(len(FALLAS)) + ' FALLAS'}")
sys.exit(1 if FALLAS else 0)
