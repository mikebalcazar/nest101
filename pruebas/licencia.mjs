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
}

/* #100 — Un mal rato del camino NO le quita la licencia a nadie.
 *
 * Esto es lo que más caro cuesta si se hace distinto, y es justo lo que no se
 * nota probando a mano con buen internet. Antes se preguntaba al revés —todo
 * lo que no fuera un 5xx contaba como «la suite dice que no»— y estas cinco
 * situaciones normales borraban la licencia del equipo. Se midieron una por
 * una antes de cambiarlo.
 */
console.log('\n· ruido del camino: la licencia guardada no se toca');
{
  const respuesta = (status, cuerpo, esJson = true) => async () => ({
    ok: status >= 200 && status < 300, status,
    json: async () => { if (!esJson) throw new Error('vino HTML, no JSON'); return cuerpo; },
  });
  const caso = async (texto, traer) => {
    const a = dir();
    n.guardar(a, { token: 'viejo', hasta: enDias(30), licencia: 'L-1' });
    const r = await n.latido({ api: 'https://x', carpeta: a, nombre: 'nest101', d: n.guardada(a), version: '1', traer });
    // Las dos mitades: que se llame «no se pudo llegar», y que el archivo siga
    // ahí. Es el llamador quien borra al oír «vencida», así que las dos cosas
    // tienen que cumplirse para que el taller conserve su programa.
    rev(!!r.sinRed && n.guardada(a)?.token === 'viejo', texto);
  };
  await caso('429: tres equipos del taller abriendo a la vez', respuesta(429, { error: 'rate_limited' }));
  await caso('408: se agotó el tiempo', respuesta(408, null));
  await caso('401 del proxy de la empresa, que no es la suite', respuesta(401, null));
  await caso('404 el día que cambie una dirección', respuesta(404, null));
  await caso('200 con la página de «acceso bloqueado» de un proxy', respuesta(200, null, false));
  await caso('un motivo que la suite invente mañana', respuesta(403, { error: 'algo_que_no_conozco' }));
}

console.log('\n· y un «no» de verdad sí cierra, con sus palabras');
{
  for (const motivo of ['sin_pago', 'suspendida', 'maquina_desconocida', 'licencia_desconocida', 'token_invalido']) {
    const a = dir();
    n.guardar(a, { token: 'viejo', hasta: enDias(30) });
    const traer = async () => ({ ok: false, status: 403, json: async () => ({ error: motivo }) });
    const r = await n.latido({ api: 'https://x', carpeta: a, nombre: 'nest101', d: n.guardada(a), version: '1', traer });
    rev(!!r.vencida && typeof r.porque === 'string' && r.porque.length > 10, motivo, r.porque);
  }
}

/* #100 — «¿Con qué cuenta estoy?», que antes no se podía contestar sin ir a
 * buscar un archivo dentro de AppData. */
console.log('\n· lo que enseña el menú Licencia');
{
  const ahora = Date.parse('2026-09-19T12:00:00Z');
  const ver = (d) => n.resumen(d, { nombre: 'nest101', huella: 'abcdefgh1234567890', ahora });

  const viva = ver({ token: 't', correo: 'mike@forespot.com', licencia: 'L-77', hasta: '2026-10-29T12:00:00Z' });
  rev(viva.activa, 'con licencia vigente dice que está activado');
  rev(viva.lineas.some((l) => l.includes('mike@forespot.com')), 'y con qué cuenta');
  rev(viva.lineas.some((l) => l.includes('faltan 40 días')), 'y cuántos días le quedan', viva.lineas[2]);

  const manana = ver({ token: 't', hasta: '2026-09-20T12:00:00Z' });
  rev(manana.lineas.some((l) => l.includes('falta 1 día')), 'un solo día se dice en singular', manana.lineas[2]);

  const muerta = ver({ token: 't', correo: 'x@y.z', licencia: 'L-9', hasta: '2026-09-01T12:00:00Z' });
  rev(!muerta.activa && muerta.titulo.includes('venció'), 'vencida lo dice, y no ofrece cambiar de cuenta');

  const nada = ver(null);
  rev(!nada.activa && nada.titulo.includes('no está activado'), 'sin activar también se puede abrir el menú');

  const todo = [viva, manana, muerta, nada].flatMap((r) => [r.titulo, ...r.lineas]).join(' ');
  rev(!todo.includes('abcdefgh1234567890'), 'la huella sale cortada, no entera');
  rev(!/token|t\b'/.test(todo.replace(/nest101/g, '')), 'y el token no se enseña en ninguna parte');
}

console.log(`\n${fallas ? `${fallas} FALLA${fallas > 1 ? 'S' : ''}` : 'todo bien'} · ${revisadas - fallas} de ${revisadas} pasaron\n`);
process.exit(fallas ? 1 : 0);
