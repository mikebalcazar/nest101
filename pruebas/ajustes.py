"""#105 — el menú de Ajustes, medido en un navegador de verdad.

La otra mitad de #105 se mide en `verificar.py`, que corre en cada armado. Esto
no puede correr ahí: necesita playwright y un Chromium, y ninguno de los dos
viaja en el instalador. Se corre a mano cuando se toca el menú:

    pip install playwright && playwright install chromium
    python pruebas/ajustes.py              # sale 0 si todo está bien

Levanta el backend con un perfil de taller nuevo —nunca el del usuario—, abre
la app en el navegador y comprueba: que el engrane abra el cuadro; que estén
las siete secciones; que la llave se pueda pegar, probar y quitar sin verse
entera; que las unidades cambien lo que se LEE y no lo que se corta; y que en
inglés no se quede ni un rótulo en español.
"""
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
import urllib.request

from playwright.sync_api import sync_playwright

AQUI = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PUERTO = int(os.environ.get("T101_PUERTO_PRUEBA", "8761"))
URL = f"http://127.0.0.1:{PUERTO}/"
# El Chromium de playwright no siempre está en el mismo lugar; si la variable
# no está puesta, playwright lo busca solo.
CHROMIUM = os.environ.get("T101_CHROMIUM", "")
FALLAS = []


def chk(cond, msg):
    print(("  OK   " if cond else "  FALLA") + " " + msg)
    if not cond:
        FALLAS.append(msg)


def esperar(segundos=25):
    hasta = time.time() + segundos
    while time.time() < hasta:
        try:
            urllib.request.urlopen(URL + "api/salud", timeout=1)
            return True
        except Exception:                                       # noqa: BLE001
            time.sleep(0.4)
    return False


perfil = tempfile.mkdtemp(prefix="t105-perfil-")
entorno = dict(os.environ, T101_PERFIL_DIR=perfil)
entorno.pop("ANTHROPIC_API_KEY", None)
servidor = subprocess.Popen(
    [sys.executable, os.path.join(AQUI, "server.py"), "--port", str(PUERTO)],
    cwd=AQUI, env=entorno, stdout=subprocess.DEVNULL, stderr=subprocess.STDOUT)
if not esperar():
    servidor.kill()
    print("  FALLA el backend no levantó")
    sys.exit(1)

try:
    with sync_playwright() as pw:
        nav = pw.chromium.launch(**({"executable_path": CHROMIUM} if CHROMIUM else {}))
        pag = nav.new_page()
        errores = []
        pag.on("pageerror", lambda e: errores.append(str(e)))
        # Los errores de consola sin URL no dicen qué falló; se anota la respuesta.
        fallidas = []
        pag.on("response", lambda r: fallidas.append(f"{r.status} {r.url}") if r.status >= 400 else None)
        pag.on("console", lambda m: errores.append(m.text)
               if m.type == "error" and "Failed to load resource" not in m.text else None)
        pag.goto(URL, wait_until="networkidle")
        pag.wait_for_timeout(1200)
        # el taller nace en inglés (#085); se mide en español y al final se cambia
        pag.evaluate("""fetch('/api/perfil', {method:'PUT',
            headers:{'Content-Type':'application/json'},
            body: JSON.stringify({idioma:'es'})})""")
        pag.wait_for_timeout(500)
        pag.reload(wait_until="networkidle")
        pag.wait_for_timeout(1200)
        # la pantalla de inicio tapa la barra: se empieza un proyecto nuevo
        pag.click("#iNuevo")
        pag.wait_for_timeout(800)

        print("\n== abre el menú ==")
        pag.click("#bConfig")
        pag.wait_for_timeout(600)
        chk(pag.is_visible("#modal.on"), "el engrane abre el cuadro")
        chk(pag.inner_text("#mTit").strip() == "Ajustes", f"se llama Ajustes: «{pag.inner_text('#mTit').strip()}»")
        cuerpo = pag.inner_text("#mCuerpo")
        for sec in ["LICENCIA DE ESTE EQUIPO", "LLAVE DE CLAUDE", "IDIOMA Y UNIDADES",
                    "LOGOTIPO DEL PAPEL", "ACTUALIZACIONES", "DÓNDE VIVE TODO"]:
            chk(sec in cuerpo.upper(), f"está la sección «{sec.lower()}»")
        for cid in ["cLlave", "cLlaveProbar", "cLlaveGuardar", "cLlaveQuitar",
                    "cIdioma", "cUnidades", "cLogoCambiar", "cActRevisar"]:
            chk(pag.query_selector("#" + cid) is not None, f"está el control #{cid}")

        print("\n== la llave: pegar, ver y quitar ==")
        chk("sin llave" in cuerpo, "sin llave puesta lo dice")
        pag.fill("#cLlave", "no-es-una-llave")
        pag.click("#cLlaveGuardar")
        pag.wait_for_timeout(300)
        msg = pag.inner_text("#cLlaveMsg")
        chk("sk-ant-" in msg, f"una llave mal formada no se guarda: «{msg}»")
        pag.fill("#cLlave", "sk-ant-api03-" + "x" * 20 + "ABCD")
        pag.click("#cLlaveGuardar")
        pag.wait_for_timeout(900)
        cuerpo = pag.inner_text("#mCuerpo")
        chk("puesta" in cuerpo and "ABCD" in cuerpo,
            f"guardada, se ve CUÁL quedó sin verla entera: {[l for l in cuerpo.split(chr(10)) if 'puesta' in l]}")
        chk("sk-ant-api03" not in cuerpo, "la llave no se vuelve a mostrar entera")
        pag.click("#cLlaveQuitar")
        pag.wait_for_timeout(900)
        chk("sin llave" in pag.inner_text("#mCuerpo"), "se puede quitar")

        print("\n== probar la llave le pregunta a Anthropic ==")
        pag.fill("#cLlave", "sk-ant-api03-llave-inventada")
        pag.click("#cLlaveProbar")
        pag.wait_for_timeout(9000)
        msg = pag.inner_text("#cLlaveMsg")
        chk("Anthropic no aceptó la llave" in msg or "no se pudo probar" in msg,
            f"una llave inventada se reporta en castellano: «{msg}»")
        chk("sin llave" in pag.inner_text("#mCuerpo"),
            "probar NO guarda: la que no sirve no se queda puesta")

        print("\n== unidades: cambian lo que se lee, no lo que se guarda ==")
        pag.click("#mCancel")
        pag.wait_for_timeout(300)

        def medidas_de_la_parrilla():
            pag.click("#bAgregar")
            pag.wait_for_timeout(800)
            t = pag.inner_text(".tienda")
            pag.click("#tCerrar")
            pag.wait_for_timeout(300)
            return t

        chk("900 × 880 × 600 mm" in medidas_de_la_parrilla(),
            "la parrilla nace en milímetros")

        for uni, debe, nodebe in [
                ("cm", "90 × 88 × 60 cm", "880 mm"),
                ("pulg", '35 7/16" × 34 5/8" × 23 5/8"', "88 cm"),
                ("mm", "900 × 880 × 600 mm", '34 5/8"')]:
            pag.click("#bConfig")
            pag.wait_for_timeout(500)
            pag.select_option("#cUnidades", uni)
            pag.click("#mOk")
            pag.wait_for_timeout(900)
            t = medidas_de_la_parrilla()
            chk(debe in t, f"en {uni} el gabinete bajo se lee «{debe}»")
            chk(nodebe not in t, f"en {uni} ya no se lee «{nodebe}»")
            guardado = pag.evaluate("fetch('/api/perfil').then(r=>r.json()).then(d=>d.unidades)")
            chk(guardado == uni, f"queda guardado en el perfil: {guardado}")

        print("\n== el proyecto sigue en milímetros ==")
        # las piezas del cálculo NO cambian con la unidad de pantalla
        r = pag.evaluate("""fetch('/api/calcular', {method:'POST',
            headers:{'Content-Type':'application/json'},
            body: JSON.stringify({gabinetes:[{nombre:'G',tipo:'base',ancho:900,alto:880,prof:600,
              frentes:[{tipo:'puerta',n:2}]}]})}).then(r=>r.json())""")
        largos = sorted({p["largo"] for p in r["piezas"]})
        chk(max(largos) > 100, f"el motor sigue en milímetros: largos {largos[:4]}…")

        print("\n== en inglés no se queda nada en español ==")
        pag.click("#bConfig")
        pag.wait_for_timeout(500)
        pag.select_option("#cIdioma", "en")
        pag.click("#mOk")
        pag.wait_for_timeout(1500)
        pag.click("#bConfig")
        pag.wait_for_timeout(900)
        txt = pag.inner_text("#mCuerpo")
        sospechosas = [p for p in ["Licencia", "Llave", "Unidades", "Estado", "Probar",
                                   "Guardar", "Quitar", "Versión", "Idioma", "Milímetros",
                                   "Pulgadas", "Logotipo", "Dónde", "Pegar", "Ajustes"]
                       if re.search(r"\b" + p, txt)]
        chk(not sospechosas, f"ni un rótulo en español: {sospechosas}")
        chk("Settings" in pag.inner_text("#mTit") or "Settings" in txt,
            f"el cuadro se llama Settings: «{pag.inner_text('#mTit')}»")
        pag.select_option("#cIdioma", "es")
        pag.click("#mOk")
        pag.wait_for_timeout(1500)

        print("\n== sin errores en la consola ==")
        chk(not errores, f"la consola está limpia: {errores[:3]}")
        # Una miniatura que todavía no se ha generado es normal; cualquier otra no.
        rotas = [f for f in fallidas if "favicon" not in f and "miniatura" not in f]
        chk(not rotas, f"ninguna petición rota: {rotas[:3]}")
        if fallidas:
            print("     (peticiones 4xx, para constancia:", fallidas[:4], ")")
        pag.screenshot(path=os.path.join(perfil, "ajustes.png"), full_page=True)
        nav.close()

finally:
    servidor.terminate()
    try:
        servidor.wait(timeout=10)
    except Exception:                                           # noqa: BLE001
        servidor.kill()
    shutil.rmtree(perfil, ignore_errors=True)

print(f"\n{'TODO OK' if not FALLAS else str(len(FALLAS)) + ' FALLAS'}")
sys.exit(1 if FALLAS else 0)
