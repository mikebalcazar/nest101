"""Mete en `verificar.py` las comprobaciones de #103 y retira el archivo suelto.

`claude/comprobar_103.py` nació fuera del verificador porque el conector de
GitHub no puede reescribir un archivo de 46 KB, y fuera de él **no corre en el
armado**: una comprobación que no corre donde se publica es media comprobación.
Esto la pone dentro, en el mismo sitio donde vive el resto, y borra la copia
suelta para que no haya dos verdades.

Lo corre el mandadero, que después mide con `verificar.py` y sólo entonces hace
el commit.
"""

from __future__ import annotations

import pathlib
import sys

RAIZ = pathlib.Path(__file__).resolve().parent.parent
ANCLA = "# ----------------------------------------------- #095 librerías del instalador"
BLOQUE = '# ------------------------------------------ #103 el zoclo no se despieza\n#\n# Mike, 30-sep: «cuando se hagan los despieces y cortes no incluyas los zoclos.\n# Los zoclos sólo son para referencia para visualmente ver cómo queda el diseño,\n# pero esos no se hacen en este tipo de despiece».\n#\n# Se miden las dos mitades del asunto: que su pieza no aparezca en NINGUNA\n# salida —lista de corte, nesting, costeo— y que el zoclo siga existiendo donde\n# sí debe: restándole altura al cuerpo y dibujado en el 3D.\nprint("\\n== #103: el zoclo se ve, pero no se corta ==")\n_gz = _Gb(nombre="con zoclo", tipo="base", ancho=900, alto=900.0, prof=600,\n          con_zoclo=True, altura_zoclo=120.0, frentes=[_F("puerta", n=2)], n_entrepanos=1)\n_prz = Proyecto("t103"); _prz.estandar = std; _prz.gabinetes = [_gz]\n_pzz, _hjz, _solz = _prz.calcular()\n\nchk(not [x for x in _pzz if "zoclo" in x.nombre.lower()],\n    f"la lista de corte no trae zoclos ({len(_pzz)} piezas: "\n    + ", ".join(sorted({x.nombre for x in _pzz})) + ")")\nchk(not [c for h in _hjz for c in h.colocaciones if "zoclo" in c.pieza.nombre.lower()],\n    "ninguna hoja de nesting acomoda un zoclo")\nchk(not [x for x in _pzz if x.codigo.endswith("ZOC")],\n    "tampoco queda su código ZOC en ninguna pieza")\nchk(not [c for c in _prz.costeo(_pzz, _hjz) if "zoclo" in str(c.get("material", "")).lower()]\n    and all("zoclo" not in x.nombre.lower() for x in _pzz),\n    "el costeo tampoco lo cobra: sale de la misma lista")\n\n# y lo que NO debe cambiar\n_tz, _cz2, _hzz = alturas(_gz, std)\nchk(abs(_hzz - 120.0) < 0.01 and abs(_cz2 - (_tz - 120.0)) < 0.01,\n    f"el zoclo sigue restando: cuerpo {_cz2:.0f} = total {_tz:.0f} − zoclo {_hzz:.0f}")\n_cosz = next(x for x in _pzz if x.nombre == "Costado")\nchk(abs(_cosz.largo - _cz2) < 0.01,\n    f"el costado se corta al cuerpo, no al total: {_cosz.largo:.0f}")\nchk(any(s.grupo == "zoclo" for s in ISO.solidos_gabinete(_gz, std)),\n    "el 3D sí dibuja el zoclo: es para lo que sirve")\n\n# el control: un mueble que nunca tuvo zoclo no cambia en nada\n_gs = _Gb(nombre="sin zoclo", tipo="aereo", ancho=900, alto=700.0, prof=350,\n          frentes=[_F("puerta", n=2)])\n_prs = Proyecto("t103b"); _prs.estandar = std; _prs.gabinetes = [_gs]\nchk(len(_prs.calcular()[0]) == len([x for x in despiezar(_gs, std, "1")]),\n    "el aéreo entrega las mismas piezas que antes (control)")\n\n'


def main() -> int:
    v = RAIZ / "verificar.py"
    texto = v.read_text(encoding="utf-8")
    suelto = RAIZ / "claude" / "comprobar_103.py"
    if "#103: el zoclo se ve, pero no se corta" in texto:
        print("  ya estaba  verificar.py")
    else:
        if texto.count(ANCLA) != 1:
            print(f"  el ancla aparece {texto.count(ANCLA)} veces, debía ser 1: no se tocó nada")
            return 1
        v.write_text(texto.replace(ANCLA, BLOQUE + ANCLA, 1), encoding="utf-8")
        print("  aplicado   verificar.py (las comprobaciones de #103)")
    if suelto.exists():
        suelto.unlink()
        print("  retirado   claude/comprobar_103.py")
    return 0


if __name__ == "__main__":
    sys.exit(main())
