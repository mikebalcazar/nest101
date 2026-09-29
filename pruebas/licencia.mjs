/* La puerta de licencia, medida sin abrir la app  ·  node pruebas/licencia.mjs
 *
 * Mide el núcleo: la huella del equipo, lo que se guarda entre arranques, la
 * regla de «sin internet abre mientras el token no venza», y qué hace el
 * latido con cada respuesta de la suite. La ventana de Electron no se puede
 * medir aquí, y por eso está en un archivo aparte que casi no tiene lógica.
 *
 * LO QUE DE VERDAD APORTA es la diferencia entre «la suite dice que no» y «no
 * hubo forma de llegar a la suite». Confundirlas es lo que dejaría a un taller
 * sin su programa porque el servidor tuvo un mal rato, y no se nota probando
 * a mano con internet bueno.
 */

import { mkdtempSync, writeFileSync, existsSync } from 'node:fs';
import { tmpdir } from 'node:os';
import path from 'node:path';
import { createRequire } from 'node:module';

const require = createRequire(import.meta.url);
const n = require('../electron/licencia-nucleo.js');

let fallas = 0, revisadas = 0;
const rev = (ok, texto, extra = '') => {
  revisadas++; if (!ok) fallas++;
  console.log(`  ${ok ? 'ok   ' : 'FALLA'} ${texto}${extra ? '  →  ' + extra : ''}`);
};
const dir = () => mkdtempSync(path.join(tmpdir(), 'nest101-lic-'));
const enDias = (d) => new Date(Date.now() + d * 86400000).toISOString();

console.log('\n· la huella del equipo');
{
  const a = dir();
  const h1 = n.huella(a);
  rev(/^[A-Za-z0-9_-]{16,128}$/.test(h1), 'tiene la forma que la suite acepta', `${h1.length} caracteres`);
  rev(n.huella(a) === h1, 'y es la misma en el siguiente arranque: no gasta un lugar nuevo cada vez');
  rev(n.huella(dir()) !== h1, 'otra instalación es otro equipo');
  rev(!h1.includes(process.env.HOSTNAME || 'nada-que-coincida'), 'no lleva dentro el nombre del equipo');
}
