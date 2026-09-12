"""DESPIEZADOR v0.1 — CLI de prueba.
Uso:  python cli.py [proyecto.json] [carpeta_salida]
Sin argumentos corre un proyecto demo (base + aéreo + cajonera).
"""
import sys, os, json
from core.config import Estandar
from core.modelos import Gabinete, Frente, despiezar, preset_base, preset_aereo, preset_gaveteros
from core.pieza import agrupar
from core.nesting import nestear
from export import dxf, xlsx, pdf, fichas


def proyecto_demo():
    return [
        preset_base("BAJO-90", ancho=900, alto=880, prof=600, puertas=2, cajones=1, entrepanos=1),
        preset_aereo("ALTO-90", ancho=900, alto=700, prof=350, puertas=2, entrepanos=1),
        preset_gaveteros("CAJONERA-60", ancho=600, alto=880, prof=600, cajones=4),
    ]


def correr(gabinetes, std, outdir, proyecto="Cocina demo"):
    from core.proyecto import Proyecto
    os.makedirs(outdir, exist_ok=True)
    pr = Proyecto(proyecto)
    pr.estandar = std
    pr.gabinetes = list(gabinetes)
    todas, hojas, _ = pr.calcular()
    costeo = pr.costeo(todas, hojas)

    p1 = dxf.exportar_nesting(hojas, os.path.join(outdir, "despiece_nesting.dxf"))
    p2 = dxf.exportar_piezas_detalle(todas, os.path.join(outdir, "piezas_detalle.dxf"))
    # #072 — sin DXF de isométricos: la vista isométrica del PDF ya cumple, y un
    # DXF de isométricos no se corta ni se arma.
    p4 = xlsx.exportar(todas, hojas, os.path.join(outdir, "lista_corte.xlsx"), proyecto, costeo)
    p5 = pdf.exportar(gabinetes, hojas, std, os.path.join(outdir, "planos.pdf"), proyecto, pr)
    p6 = fichas.exportar(todas, os.path.join(outdir, "fichas_de_corte.pdf"), proyecto)
    return todas, hojas, [p1, p2, p4, p5, p6]


if __name__ == "__main__":
    std = Estandar()
    outdir = sys.argv[2] if len(sys.argv) > 2 else "out"
    gab = proyecto_demo()
    # #004: posiciones para que la página de cocina tenga sentido
    x = 0.0
    for g in gab:
        g.pos_x = x
        x += g.ancho + 0
        if g.tipo == "aereo":
            g.pos_z = 0.0
    piezas, hojas, archivos = correr(gab, std, outdir)
    print(f"Piezas únicas: {len(piezas)} | Total unidades: {sum(p.cantidad for p in piezas)}")
    print(f"Hojas: {len(hojas)}")
    for h in hojas:
        print(f"  Hoja {h.idx}: {h.material} {h.espesor}mm  {len(h.colocaciones)} pz  "
              f"aprov {h.aprovechamiento*100:.1f}%")
    for a in archivos:
        print("  ->", a)
