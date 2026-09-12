"""#095 — Las cifras del papel, en Fira Sans.

Norma de la suite (`claude/tipografia-cifras-suite101.md`): toda medida,
cantidad, precio, fecha u hora se compone en **Fira Sans**, cifras alineadas.
El texto sigue en Raleway y la marca en Sansation.

## Por qué

Raleway trae cifras «old style». Medido sobre el propio archivo: el 3, 4, 5, 7
y 9 caen hasta 154 unidades por debajo de la línea base y el 6 y el 8 suben 140
por encima. En un rótulo eso se ve elegante; en una cota de corte **no se lee de
un golpe**, y un número que no se lee de un golpe es una pieza mal cortada.

## Cómo, y en qué se aparta de draw101

En la interfaz esto lo resuelve el `unicode-range` del CSS: la familia «Cifras»
sólo contiene los dígitos, va primero en la pila y el navegador reparte solo,
carácter por carácter.

reportlab no tiene `unicode-range`. draw101 usa una regla por CADENA —si toda la
cadena es una medida, va en Fira; si no, en Raleway—:

    _ES_MEDIDA = re.compile(r"^[\\s\\d.,+\\-±×°%Øø]+(mm|cm|m)?$")

Aquí se hace **por tramos**, no por cadena, porque los textos de nest101 mezclan
las dos cosas en el mismo renglón y son la mayoría:

    "Costado 600 × 880"      draw101: todo Raleway (lleva letras)
                             aquí:    "Costado " Raleway · "600 × 880" Fira
    "regulable · alturas 366"
    "Cuerpo 760 alto × 559 prof"

Con la regla por cadena, las cifras de la lista de corte —que es justo lo que se
lleva a la sierra— se quedarían en Raleway. Partir por tramos da el mismo
resultado que el `unicode-range` de la pantalla, que es lo que dice la norma.

## Dónde se aplica

En **un solo sitio**: el lienzo envuelto de `core/idioma.py`, por donde ya pasa
todo el texto de todos los PDF. Ni `export/pdf.py` ni `export/fichas.py` saben
que esto existe, y el `drawString` que alguien escriba mañana tampoco tiene que
enterarse.

**La marca no se toca.** Cuando el lienzo está escribiendo en Sansation —el
logotipo, el título de la página— las cifras se quedan en Sansation: mezclar dos
tipografías dentro del nombre del programa se ve como un error de imprenta, y
ahí no hay ninguna medida que leer.
"""
from __future__ import annotations

import re
from typing import List, Tuple

# Lo que se compone en Fira: los dígitos y los signos que sólo aparecen pegados
# a un número. El punto, la coma y el guion **no** entran aunque separen cifras:
# saltar de fuente en mitad de «1,250» se nota más que la cifra vieja, y son
# caracteres cuyo dibujo apenas cambia entre las dos familias.
_TRAMO = re.compile(r"[0-9]+(?:[.,][0-9]+)*[°±×%]?|[°±×%]+")

# Las familias que llevan cifras propias. Sansation queda fuera a propósito.
_CON_CIFRAS = ("Raleway", "Helvetica", "Times")


def _quiere_cifras(fuente: str) -> bool:
    return any(fuente.startswith(f) for f in _CON_CIFRAS)


def _negrita(fuente: str) -> bool:
    f = fuente.lower()
    return "bold" in f or "semi" in f


def partir(texto: str) -> List[Tuple[str, bool]]:
    """Parte el texto en tramos `(fragmento, es_cifra)`, en orden.

    >>> partir("Costado 600 × 880")
    [('Costado ', False), ('600 ', False), ...]

    Los tramos vacíos no salen, y volver a juntarlos da el texto original —eso
    lo comprueba `t025`, porque un partidor que pierde un carácter escribe una
    medida equivocada en una ficha de corte.
    """
    out: List[Tuple[str, bool]] = []
    i = 0
    for m in _TRAMO.finditer(texto):
        if m.start() > i:
            out.append((texto[i:m.start()], False))
        out.append((m.group(), True))
        i = m.end()
    if i < len(texto):
        out.append((texto[i:], False))
    return out


def fuente_cifra(fuente: str) -> str:
    """La Fira que le toca a la fuente de texto que esté puesta."""
    from . import marca as M
    return M.CIF_B if _negrita(fuente) else M.CIF


def ancho(c, texto: str, fuente: str, tam: float) -> float:
    """Lo que va a medir el texto ya repartido entre las dos fuentes.

    Hay que medirlo así y no con `stringWidth` a secas: Fira y Raleway no tienen
    los mismos anchos, y si se centra o se alinea a la derecha con la medida
    equivocada el número se sale de su columna.
    """
    if not _quiere_cifras(fuente):
        return c.stringWidth(texto, fuente, tam)
    cif = fuente_cifra(fuente)
    return sum(c.stringWidth(f, cif if es else fuente, tam)
               for f, es in partir(texto))


def escribir(c, x: float, y: float, texto: str, fuente: str, tam: float,
             ancla: str = "izq") -> float:
    """Escribe `texto` repartiendo las cifras, y deja la fuente como estaba.

    `ancla`: «izq», «centro» o «der», los tres anclajes que usa reportlab.
    Devuelve el ancho escrito.
    """
    if not _quiere_cifras(fuente) or not any(ch.isdigit() for ch in texto):
        # Sin dígitos no hay nada que repartir: se escribe de una vez, que es
        # además el camino de la inmensa mayoría de las llamadas.
        w = c.stringWidth(texto, fuente, tam)
        x0 = x if ancla == "izq" else (x - w / 2 if ancla == "centro" else x - w)
        c.drawString(x0, y, texto)
        return w

    w = ancho(c, texto, fuente, tam)
    x0 = x if ancla == "izq" else (x - w / 2 if ancla == "centro" else x - w)
    cif = fuente_cifra(fuente)
    for frag, es in partir(texto):
        f = cif if es else fuente
        c.setFont(f, tam)
        c.drawString(x0, y, frag)
        x0 += c.stringWidth(frag, f, tam)
    c.setFont(fuente, tam)          # se devuelve como estaba: nadie lo pidió
    return w
