# Librería de módulos — dónde se agregan

Un **módulo** es un archivo JSON con un gabinete adentro.
Una **categoría** es una carpeta con módulos.

No hay base de datos: se copia una carpeta y se copió la librería completa.

```
assets/modulos/                       ← de fábrica, viaja con la app
    taller-101/                       ← una categoría
        categoria.json                ← nombre, nota y orden
        base-900-2-puertas.json       ← un módulo
        cajonera-600-4.json
    ikeda/                            ← así se agrega otra
        categoria.json
        base-600-3-charolas.json
```

Y del lado del taller, las que hace el usuario desde la app:

```
~/Taller 101/modulos/<categoria>/
```

**Las dos se leen juntas y las del taller mandan.** Si el taller hace un módulo
con el mismo nombre de archivo que uno de fábrica, gana el suyo: así puede
corregir uno de fábrica sin que la siguiente actualización se lo deshaga,
porque una actualización sólo reescribe la carpeta de instalación.

Por eso mismo **nunca se escribe aquí desde la app**. Lo que el taller guarda va
siempre a su carpeta: escribir en `assets/` sería escribir en un lugar que la
próxima versión borra.

## categoria.json

```json
{
  "nombre": "Gabinetes para IKEDA",
  "nota": "Medidas para recibir entrepaños, cajones y charolas IKEDA.",
  "orden": 20
}
```

`orden` decide el lugar en la barra de categorías; a igual orden, alfabético.

## Un módulo

```json
{
  "nombre": "Base 600 · 3 charolas",
  "nota": "Para qué sirve y cuándo se usa. Sale debajo del nombre.",
  "gabinete": { … }
}
```

El bloque `gabinete` es **el mismo que guarda un `.t101x`**, sin `pos_x`,
`pos_z`, `rot` ni `alto_colgado` — el lugar en la cocina es de cada proyecto, no
del módulo. La manera menos trabajosa de escribir uno: armarlo en la app y usar
**Guardar como módulo**, que lo deja ya con esta forma en la carpeta del taller;
de ahí se copia para acá si va a viajar con la instalación.

Los barrenos **no se guardan**: los calcula el motor a partir del gabinete y del
estándar del taller (sistema 32). Un barreno escrito a mano se desfasaría el día
que cambie una medida; uno calculado, no.

## Categorías de una marca

`taller-101/` está hecha con las medidas del taller, que son reales. Una
categoría de marca —IKEDA u otra— necesita las medidas de la ficha técnica de
esa marca: separación de barrenos, largo de corredera, espesor de charola. Esas
**no se inventan**: un módulo con medidas plausibles es un módulo que se corta
mal. Se agrega la carpeta cuando estén los datos.
