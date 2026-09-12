# Catálogo de simbología de carpintería en alzados

Cómo distinguir **CUERPO** (gabinete, lo que se fabrica) de **FRENTE** (puerta, cajón,
panel, lo que se ve). Esta es la pregunta central: el plano casi nunca la contesta con
palabras.

Cada regla trae su **peso**. Se aplican en orden: si una regla de peso alto decide, las
de peso bajo no la contradicen.

---

## A. Señales de CUERPO (frontera entre gabinetes)

| Peso | Señal | Cómo se ve |
|---|---|---|
| 0.95 | **Doble lateral** | Dos líneas verticales separadas ~2× el espesor de tablero (32–40 mm si el tablero es 16–19). Son los costados de dos gabinetes contiguos. **Sólo legible en PDF vectorial.** |
| 0.90 | **Lateral único** | Dos líneas separadas ~1× espesor (16–19 mm) en un extremo: costado del mueble. |
| 0.85 | **Línea más gruesa** | En planos con jerarquía de plumillas, el contorno del cuerpo se dibuja más grueso que las juntas de frentes. Ojo: muchos planos no la respetan. |
| 0.80 | **Cambio de tipo** | Entre un gabinete y un electrodoméstico, registro, torre o nicho siempre hay frontera de cuerpo. |
| 0.75 | **Cambio de altura o de profundidad** | Si el pano cambia de altura (faldón, escalón) hay cuerpo nuevo. |
| 0.70 | **Tick de cadena de cotas** | El arquitecto cota lo que le importa. Si la cadena marca 1.20 y no marca los 0.60 internos, ese 1.20 es un cuerpo. Si marca cada 0.60, es ambiguo (puede estar cotando puertas). |
| 0.95 | **Más de 2 puertas seguidas** | **Regla dura de Taller 101: un cuerpo lleva máximo 2 puertas.** Un pano con 3 puertas son 2 cuerpos; con 4 puertas, 2 cuerpos de 2. Corta donde el reparto quede parejo. |
| 0.60 | **Ancho > 1200 mm** | Un cuerpo de más de 1.20 m es raro por transporte y por pandeo del entrepaño. Un pano de 1.80 casi siempre son 2 o 3 cuerpos. |

## B. Señales de FRENTE

| Peso | Señal | Cómo se ve |
|---|---|---|
| 0.90 | **Línea vertical sola** entre dos panos del mismo alto, sin espesor dibujado | Junta entre dos puertas del mismo cuerpo. |
| 0.90 | **Línea horizontal + jaladera horizontal** | Frente de cajón. Varias apiladas = cajonera. |
| 0.85 | **Marca de jaladera** | Trazo corto (vertical para puerta, horizontal para cajón). Dos jaladeras encontradas hacia el centro = par de puertas del mismo cuerpo. |
| 0.85 | **Triángulo o V punteada** | Sentido de apertura. El **vértice apunta al lado de la bisagra**; la base al lado de la jaladera. |
| 0.80 | **Arco punteado** | Apertura abatible (más común en planta que en alzado). |
| 0.70 | **X completa sobre el pano** | Según contexto: electrodoméstico, hueco a integrar, o vidrio. Si trae clave (`SE-03`, `AS-10`) manda la clave. |
| 0.70 | **Rombo/diamante con clave** | Registro desmontable (eléctrico, plomería). No es puerta. |
| 0.60 | **Rayado o textura** | Sólo indica material (madera, mármol). No dice nada de la partición. |

## C. Regla de decisión

```
1. ¿Hay evidencia geométrica de doble lateral?   -> ahí corta cuerpo. FIN.
2. ¿Cambia el tipo (electro/registro/torre/nicho) o la altura? -> corta cuerpo.
3. ¿El pano lleva más de 2 puertas?              -> corta: máximo 2 por cuerpo.
4. ¿El pano mide más de 1200 mm?                 -> corta; reparte en cuerpos ≤1200.
5. ¿Las jaladeras van encontradas hacia el centro? -> es UN cuerpo de 2 puertas.
6. Si nada decide                                -> partición por default del taller
                                                    + PREGUNTA al usuario.
```

REGLA DURA DEL TALLER: **ningún cuerpo lleva más de 2 puertas.** Si tu lectura da 3 o más
puertas en un mismo módulo, la partición está mal: pártela antes de reportar.

REGLA DURA DEL TALLER: **el zoclo es parte del gabinete, no un elemento corrido.** Cada
cuerpo se apoya en su propio zoclo; el alto del gabinete lo incluye.

## D. Configuraciones típicas de gabinete

| Ancho del cuerpo | Lo más probable |
|---|---|
| ≤ 450 mm | 1 puerta |
| 450–700 mm | 1 puerta, o 2–4 cajones |
| 700–1000 mm | 2 puertas, o cajonera |
| 1000–1200 mm | 2 puertas (el máximo) |
| > 1200 mm | son varios cuerpos |

Los cajones no tienen ese tope: una cajonera puede llevar 3, 4 o 5 cajones en un cuerpo.

Un gabinete puede no tener frente: nicho abierto, entrepaños vistos, hueco de
electrodoméstico. `frentes: []` es una respuesta válida y frecuente.

## E. Lo que NO se debe inventar

- **Bisagra**: si no hay triángulo, arco ni jaladera, `bisagra: null`. No adivinar.
- **Profundidad**: el alzado no la trae. Va en la planta. `prof_mm: null`.
- **Espesor de tablero**: sólo si se mide en el vectorial o viene en nota.
- **Cajones**: no convertir "pano con líneas horizontales" en cajones si no hay jaladera
  ni cota; puede ser un entrepaño visto o una junta de veta.

## F. Aprendizaje

Cada corrección que el usuario hace en el diálogo se guarda en el perfil del despacho
(`perfiles/<despacho>.json`) como un ejemplo con su contexto, y se inyecta en este
prompt en las siguientes lecturas de planos del mismo despacho. Los despachos son
consistentes consigo mismos: lo que se aprende de una lámina sirve para las demás.
