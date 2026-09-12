"""#031 — La lectura del plano, en un solo lugar y detrás de una frontera.

Este archivo existe para poder partir «Leer plano» en dos mitades:

    mitad pesada    abrir el PDF, enderezar la foto, recortar las vistas,
                    medir la geometría y preguntarle al modelo de visión.
                    Necesita pdfium, opencv y la llave de API.

    mitad ligera    validar, preguntar lo ambiguo, armar el contrato y
                    traducir a gabinetes. Sólo necesita pydantic.

La frontera es el `Documento`. Todo lo que sale de aquí es JSON: se puede
producir en esta misma máquina o en el servidor de Taller 101, y lo de arriba no
se entera.

Por qué importa: la llave de API **no puede viajar dentro del instalador** —
cualquiera la saca del .exe. Y las librerías pesadas suman ~130 MB al programa.
Con este corte, la app instalada no lleva ni una cosa ni la otra: sube el plano
y recibe el resultado.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Callable, Dict, List, Optional

from .motor import ambiguedad, validate
from .motor.schema import Alzado, Documento

FORMATOS = (".pdf", ".png", ".jpg", ".jpeg", ".tif", ".tiff", ".bmp")

Avisar = Callable[[str, str], None]


def _nada(titulo: str, detalle: str = ""):
    pass


def _guardar_crudo(salida: Path, png: Path, crudo: dict) -> None:
    """#055 — deja en disco lo que contesto el modelo para esta vista."""
    try:
        d = dict(crudo)
        texto = d.pop("_crudo", "")
        (salida / f"{png.stem}.respuesta.json").write_text(
            json.dumps(d, ensure_ascii=False, indent=1), encoding="utf-8")
        if texto:
            (salida / f"{png.stem}.crudo.txt").write_text(texto, encoding="utf-8")
    except Exception:                                           # noqa: BLE001
        pass          # el diagnostico nunca puede tumbar la lectura


def leer(archivo: Path, salida: Path, despacho: Optional[str] = None,
         backend: str = "anthropic", avisar: Optional[Avisar] = None,
         perfil: Optional[dict] = None) -> dict:
    """Lee un plano y devuelve el resultado crudo, listo para serializar.

    Las importaciones pesadas están **adentro** a propósito: el escritorio
    importa este archivo aunque no tenga pdfium ni opencv, siempre que use el
    servicio en vez de leer en local.
    """
    try:
        from .motor import foto, geometria, imaging, sheet, vision
    except ImportError as e:
        # En la app instalada esto es lo esperado: la mitad pesada no viaja.
        raise RuntimeError(
            "Este equipo no puede leer planos por su cuenta: la lectura corre en "
            "el servicio de Taller 101 y no está configurado (T101_PLANOS_URL)."
        ) from e


    av = avisar or _nada
    salida.mkdir(parents=True, exist_ok=True)
    alzados: List[Alzado] = []
    vistas: List[dict] = []
    bbox: Dict[str, dict] = {}

    es_pdf = archivo.suffix.lower() == ".pdf"
    vectorial = False
    if es_pdf:
        doc = sheet.abrir(archivo)
        vectorial = sheet.es_vectorial(doc[0])
        doc.close()

    # ---------------------------------------------------- lámina vectorial
    if vectorial:
        tipo_origen = "vectorial"
        av("Abriendo el PDF", "PDF vectorial de CAD")
        doc = sheet.abrir(archivo)
        for _npag, page in enumerate(doc, start=1):
            vs = sheet.detectar_vistas(page)
            if vs:
                av("Buscando vistas", f"{len(vs)} vista(s) rotuladas")
            else:
                # #049 — sin rótulos NO se entrega una hoja vacía: se lee
                # completa. Cero módulos en silencio parece un plano malo, y
                # casi siempre es que el despacho rotula distinto al que
                # esperábamos.
                vs = [sheet.hoja_completa(page)]
                av("Buscando vistas",
                   "sin rótulos que reconozca; se lee la hoja completa")
            for v in vs:
                info = {"numero": v.numero, "tipo": v.tipo, "titulo": v.titulo,
                        "escala": f"1:{v.escala}" if v.escala else None,
                        "procesada": False}
                if v.tipo in ("elevacion", "corte"):
                    png = sheet.recortar(page, v, salida, px_objetivo=2000)
                    geo = geometria.analizar(page, v.rect, v.mm_por_pt) if v.mm_por_pt else None
                    ctx = (f"Vista: {v.titulo} (tipo {v.tipo}, escala 1:{v.escala}).\n"
                           "Texto NATIVO del PDF (exacto, úsalo para cotas y claves):\n"
                           + json.dumps(sheet.texto_de_vista(v), ensure_ascii=False))
                    if geo:
                        ctx += "\n\n" + geometria.como_evidencia(geo)
                        info["geometria"] = geo.resumen()
                        av("Midiendo la geometría", geo.resumen())
                    crudo = vision.extraer(png, backend=backend, contexto=ctx,
                                           despacho=despacho, perfil=perfil)
                    # #055 — lo que contesto el modelo se guarda junto al recorte.
                    # Sin esto, un «no reconoci ningun mueble» no se puede
                    # diagnosticar sin volver a pagar la lectura, y no hay forma
                    # de saber si fallo el recorte, el modelo o lo que sigue.
                    _guardar_crudo(salida, png, crudo)
                    n_mod = 0
                    for a in crudo.get("alzados", []):
                        al = Alzado(**{**a, "vista_numero": v.numero, "tipo_vista": v.tipo,
                                       "escala_den": v.escala, "titulo": v.titulo,
                                       "mm_por_px": sheet.mm_por_px(v)})
                        alzados.append(al)
                        n_mod += len(al.modulos)
                        bbox[al.id] = {m.clave: m.bbox_px for m in al.modulos if m.bbox_px}
                    info.update(procesada=True, imagen=png.name,
                                alzados=len(crudo.get("alzados", [])), modulos=n_mod)
                    av(f"Vista leída: {v.titulo}",
                       f"{n_mod} módulo(s)" if n_mod else
                       "el modelo no encontró módulos en esta vista")
                vistas.append(info)
        doc.close()

    # ---------------------------------------------------- foto o escaneo
    else:
        tipo_origen = "foto"
        av("Abriendo la imagen", "")
        pngs = imaging.cargar_entrada(archivo, dpi=300) if es_pdf else [archivo]
        derecha, corregida = foto.enderezar(pngs[0], salida / "derecha.png")
        limpia = foto.limpiar(derecha, salida / "limpia.png")
        av("Enderezando la hoja",
           "perspectiva corregida" if corregida else "no se halló el borde de la hoja")
        vs = foto.detectar_vistas(limpia)
        av("Buscando vistas",
           ", ".join(v.titulo for v in vs) if vs else "sin rótulos; hoja completa")
        objetivos = [(v.titulo, v.tipo, foto.recortar(limpia, v, salida)) for v in vs
                     if v.tipo in ("elevacion", "corte")] or [("HOJA", "elevacion", limpia)]
        for titulo, tipo, png in objetivos:
            ctx = (f"Vista: {titulo} ({tipo}). Viene de una FOTO o escaneo.\n"
                   "La escala del papel NO es confiable: usa ÚNICAMENTE las cotas escritas. "
                   "Si una cota no se lee, deja el valor en null y baja la confianza.")
            crudo = vision.extraer(png, backend=backend, contexto=ctx,
                                   despacho=despacho, imagenes_extra=[limpia],
                                   perfil=perfil)
            for a in crudo.get("alzados", []):
                al = Alzado(**{**a, "tipo_vista": tipo, "titulo": titulo})
                alzados.append(al)
                bbox[al.id] = {m.clave: m.bbox_px for m in al.modulos if m.bbox_px}
            vistas.append({"numero": None, "tipo": tipo, "titulo": titulo,
                           "escala": None, "procesada": True, "imagen": png.name})

    av("Leyendo cotas y claves", "")
    doc = Documento(archivo=archivo.name, modelo_vision=backend, alzados=alzados)
    validate.validar(doc)
    preguntas = ambiguedad.generar(doc)
    av("Validando",
       f"{sum(1 for a in doc.avisos if a.nivel == 'error')} error(es), "
       f"{sum(1 for a in doc.avisos if a.nivel == 'warn')} aviso(s)")

    return {"documento": doc, "vistas": vistas, "bbox": bbox,
            "preguntas": preguntas, "tipo_origen": tipo_origen}


def a_json(resultado: dict, salida: Path, con_imagenes: bool = True) -> dict:
    """Empaqueta el resultado para mandarlo por la red.

    Las imágenes de las vistas viajan en base64: son los recortes que el panel le
    enseña al usuario para que revise lo que se leyó, y sin ellas el diálogo
    pierde la mitad de su utilidad. Pesan poco comparadas con el plano original.
    """
    import base64

    doc: Documento = resultado["documento"]
    imgs: Dict[str, str] = {}
    if con_imagenes:
        for v in resultado["vistas"]:
            n = v.get("imagen")
            if not n:
                continue
            p = salida / n
            if p.exists():
                imgs[n] = base64.b64encode(p.read_bytes()).decode()
    return {
        "documento": doc.dict(),
        "vistas": resultado["vistas"],
        "bbox": resultado["bbox"],
        "tipo_origen": resultado["tipo_origen"],
        "imagenes": imgs,
    }


def de_json(d: dict, salida: Path) -> dict:
    """Reconstruye el resultado del otro lado de la red."""
    import base64

    salida.mkdir(parents=True, exist_ok=True)
    for nombre, b64 in (d.get("imagenes") or {}).items():
        # nunca se confía en un nombre que venga de fuera para escribir en disco
        seguro = Path(nombre).name
        (salida / seguro).write_bytes(base64.b64decode(b64))
    doc = Documento(**d["documento"])
    return {"documento": doc, "vistas": d.get("vistas", []),
            "bbox": d.get("bbox", {}), "preguntas": ambiguedad.generar(doc),
            "tipo_origen": d.get("tipo_origen", "vectorial")}
