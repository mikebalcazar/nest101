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

console.log('\n· lo que se guarda entre arranques');
{
  const a = dir();
  rev(n.guardada(a) === null, 'recién instalada no hay nada guardado');
  n.guardar(a, { token: 'v1.abc.def', hasta: enDias(3) });
  rev(n.guardada(a)?.token === 'v1.abc.def', 'lo guardado se vuelve a leer');
  writeFileSync(n.archivoLicencia(a), '{ esto no es json');
  rev(n.guardada(a) === null, 'un archivo roto se lee como «no hay licencia», no truena');
  n.guardar(a, { token: 'v1.abc.def', hasta: enDias(3) });
  n.olvidar(a);
  rev(!existsSync(n.archivoLicencia(a)) && n.guardada(a) === null, 'olvidar la borra de verdad');
}

console.log('\n· sin internet: abre mientras el token no venza');
rev(n.alCorriente({ hasta: enDias(5) }) === true, 'con el token vigente, abre sin preguntarle a nadie');
rev(n.alCorriente({ hasta: enDias(-1) }) === false, 'vencido ayer, ya no');
rev(n.alCorriente({}) === false, 'y sin fecha tampoco: no se supone nada');

console.log('\n· el latido, según lo que conteste la suite');
{
  const comun = (d = { token: 'v1.viejo', hasta: enDias(-1) }) => ({ api: 'https://sin.red', carpeta: dir(), nombre: 'nest101', d });

  const bien = { ...comun(), traer: async () => ({ ok: true, status: 200, json: async () => ({ ok: true, data: { token: 'v1.nuevo', hasta: enDias(14), licencia: { programa: 'nest101' } } }) }) };
  const r1 = await n.latido(bien);
  rev(r1.ok === true, 'token nuevo: sigue');
  rev(n.guardada(bien.carpeta)?.token === 'v1.nuevo', 'y el token nuevo queda guardado, no el viejo');

  const sinPago = { ...comun(), traer: async () => ({ ok: false, status: 402, json: async () => ({ ok: false, error: 'sin_pago' }) }) };
  const r2 = await n.latido(sinPago);
  rev(r2.vencida === true && /no está al corriente/.test(r2.porque), 'la suite dice que no está al corriente, y se dice con palabras', r2.porque);

  /* Éstas son las dos que importan: un servidor caído o sin señal NO es una
   * licencia mala. Si se confundieran, un mal rato del servidor dejaría a un
   * taller sin su programa. */
  const caido = { ...comun(), traer: async () => ({ ok: false, status: 503, json: async () => ({ ok: false, error: 'ups' }) }) };
  rev((await n.latido(caido)).sinRed === true, 'un 503 es «no se pudo llegar», no «licencia mala»');
  const nada = { ...comun(), traer: async () => { throw new Error('getaddrinfo ENOTFOUND'); } };
  rev((await n.latido(nada)).sinRed === true, 'y no tener señal, tampoco');

  const caido2 = { ...comun(), traer: async () => ({ ok: false, status: 503, json: async () => ({ ok: false }) }) };
  n.guardar(caido2.carpeta, caido2.d);
  await n.latido(caido2);
  rev(n.guardada(caido2.carpeta)?.token === 'v1.viejo', 'y por un servidor caído no se borra la licencia guardada');
}

console.log('\n· la pantalla que se abre');
{
  const u = new URL(n.direccionDeLaPantalla({ api: 'https://api.ejemplo', programa: 'nest101', nombre: 'nest101', huella: 'equipo-0123456789abcdef', version: '10.0.2' }));
  rev(u.pathname === '/licencias/entrar', 'es la pantalla de la suite, no una propia');
  rev(u.searchParams.get('programa') === 'nest101' && u.searchParams.get('huella') === 'equipo-0123456789abcdef', 'y le dice qué programa y qué equipo');
  rev(!u.toString().includes('token'), 'la dirección no lleva ningún token: una dirección se copia y se queda en registros');
  rev(u.searchParams.get('equipo') === n.nombreDelEquipo(), 'y cómo se llama este equipo, para la lista de equipos de la suite');
  rev(['windows', 'mac', 'linux'].includes(u.searchParams.get('sistema')), 'y en qué sistema va, que es el ícono de esa lista', u.searchParams.get('sistema'));
}

/* El nombre del equipo  ·  28-sep-2026. Mike pidió la lista estilo Adobe para
 * dar de baja un equipo, «que ponga el nombre del equipo como lo tiene en su
 * windows». La lista la sirve suite101-api y es la misma para toda la suite:
 * si nest101 no manda su nombre, sus equipos salen ahí sin nombre.
 *
 * La línea que no se puede cruzar: el nombre va APARTE, como etiqueta. La
 * huella sigue siendo el azar guardado y de ella no se saca el nombre de
 * nadie. Si algún día alguien vuelve a meter el hostname en la huella, esta
 * prueba lo caza. */
console.log('\n· cómo se llama este equipo');
{
  const nombre = n.nombreDelEquipo();
  rev(typeof nombre === 'string' && nombre.length > 0 && nombre.length <= 60, 'la app sabe cómo se llama esta computadora', nombre);
  rev(!nombre.includes('.'), 'sin el sufijo de red, que alarga y no distingue');
  rev(['windows', 'mac', 'linux'].includes(n.sistemaDelEquipo()), 'y en qué sistema va');

  const carpeta = dir();
  const h = n.huella(carpeta);
  rev(!h.includes(nombre), 'la HUELLA no lleva el nombre dentro: sigue sin identificar a nadie');
  rev(n.huella(carpeta) === h, 'y es la misma en el siguiente arranque, como siempre');

  /* Que la huella NO salga del hostname ya lo mide el primer bloque: si
   * saliera, dos instalaciones del mismo equipo darian la misma y «otra
   * instalacion es otro equipo» fallaria. Aqui no se repite. */

  const mandado = [];
  const espia = { api: 'https://x', carpeta, nombre: 'nest101', d: { token: 'v1.x', hasta: enDias(5) },
    traer: async (_u, o) => { mandado.push(JSON.parse(o.body)); return { ok: true, status: 200, json: async () => ({ ok: true, data: { token: 'v1.y', hasta: enDias(20), licencia: {} } }) }; } };
  await n.latido(espia);
  rev(mandado[0].nombre === nombre, 'el latido diario lo manda, así que la lista se llena sola sin reactivar nada');
  rev(mandado[0].huella === h, 'junto a la huella de siempre');
}

console.log(`\n${fallas ? `${fallas} FALLA${fallas > 1 ? 'S' : ''}` : 'todo bien'} · ${revisadas - fallas} de ${revisadas} pasaron\n`);
process.exit(fallas ? 1 : 0);
