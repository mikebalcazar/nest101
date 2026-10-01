# #101 y #102 · lo aplicado y lo que falta

*30-sep-2026. Lo escribe el chat que arregló los dos defectos que reportó Mike.*

## Por qué este archivo existe

La sesión que hizo el arreglo **no tiene empuje directo a este repositorio**: el
proxy contesta *«mikebalcazar/nest101 is not in this session's authorized
repository set»*. Lo que sí tiene es el conector de GitHub, que escribe archivos
completos pero **no puede escribir dentro de `.github/workflows/`** (403:
*resource not accessible by integration*), así que tampoco se pudo dejar un
flujo que aplicara el cambio en el corredor.

De ahí el reparto: lo que cabía se subió como archivo completo y verificado por
hash; lo que no cabía viaja como aplicador.

## Lo que ya está aplicado y medido

| Archivo | Qué trae |
| --- | --- |
| `export/pdf.py` | **#101** · cada isométrico con su propio nombre de archivo |
| `core/proyecto.py` | **#102** · se cura al recalcular el `alto_cuerpo` que quedó valiendo el total declarado |

Medido en esta rama, con el árbol tal como está:

- `verificar.py` (las 180 comprobaciones que ya existían): **TODO OK**.
- El zoclo: un mueble de 900 con zoclo de 100 y el candado en «total» da
  **costado de 780** en la lista de corte, y el alto declarado **sigue en 900**.
  Antes daba 900 de costado: era el reporte de Mike.
- El isométrico: el PDF de un proyecto de dos muebles trae **6 isométricos y los
  6 son distintos**. Antes tres pares de páginas compartían la misma imagen.

## Lo que falta, en orden de importancia

Los tres cambios están escritos y probados; sólo faltaba subirlos. Viajan dentro
de los dos aplicadores de esta misma carpeta.

1. **`verificar.py` · las comprobaciones nuevas.** Sin ellas los dos defectos
   pueden volver sin que nada se queje. Las trae
   `claude/aplicar_101_102_pruebas.py`: el caso del archivo contaminado, la
   prueba de que el mueble no se encoge, un barrido de 636 configuraciones de
   tipo, zoclo, cubierta, candado y overrides, y la lectura del PDF por dentro.
2. **`core/modelos.py` · que el mueble no se encoja.** Defecto gemelo de #059,
   vivo en la rama sin zoclo: con el total derivado, `alturas()` le quita la
   plancha a un número que ya era el cuerpo, así que cada recálculo se come un
   espesor (medido: 900 → 880 → 860 con piedra de 20). Lo trae
   `claude/aplicar_101_102.py`.
3. **`ui/app.js` · la captura.** Es donde nace #102: la pantalla del gabinete
   escribe `alto_cuerpo = alto` y no descuenta la plancha. El saneo de
   `core/proyecto.py` ya corrige el resultado, así que el taller no ve el
   defecto; esto es para que la pantalla deje de generar el dato malo. Lo trae
   `claude/aplicar_101_102.py` (son 140 KB de archivo y un cambio de 12
   líneas: por eso viaja como aplicador y no como archivo completo).

**Los dos aplicadores se corren juntos**, en este orden, y después `verificar.py`:

```bash
python claude/aplicar_101_102.py
python claude/aplicar_101_102_pruebas.py
python verificar.py          # tiene que decir TODO OK
git rm claude/aplicar_101_102.py claude/aplicar_101_102_pruebas.py claude/101-102-pendiente.md
```

No se aplican por separado: las comprobaciones del punto 1 miden el arreglo del
punto 2, así que solas fallarían. Cada aplicador se ancla en el texto que va a
cambiar y **se detiene sin tocar nada** si no lo encuentra exactamente una vez;
los dos son idempotentes (si el cambio ya está, lo dicen y no hacen nada).

## Lo que nadie ha hecho todavía

**Publicar una versión.** `apps.yml` sólo arranca a mano (`workflow_dispatch`) y
el conector de esta sesión no puede dispararlo. Mientras no se publique, el
taller sigue con la 0.18.2 y estos arreglos viven sólo en el repositorio.

## Dónde está el parche completo

Los dos commits están también como parche en el proyecto de Claude de Mike:
`claude/nest101-101-102-iso-y-alturas.patch` (y el de licencias, #100, en
`claude/nest101-100-licencia-robusta.patch`, que sigue sin subir por lo mismo).
