// Los números de referencia de las animaciones del capítulo 0, de la misma cuenta que usan las páginas:
// wave y makeTarget (server/web/sismomath.js), el intervalo de FlickDetector.tempo (server/web/flick.js) y las
// franjas del 1 al 8 de server/web/musica.js. cap00.py lo corre y compara su propia cuenta con esta.
//   node docs/curso/animaciones/datos_cap00.js
'use strict';
const fs = require('fs');
const path = require('path');
const WEB = path.join(__dirname, '..', '..', '..', 'server', 'web');
const S = require(path.join(WEB, 'sismomath.js'));
const { FlickDetector } = require(path.join(WEB, 'flick.js'));

// musica.js se cuelga de `self`, como en el navegador
const raiz = {};
new Function('self', fs.readFileSync(path.join(WEB, 'musica.js'), 'utf8'))(raiz);

let estado = 2027;                                     // números al azar repetibles
const azar = () => { estado = (estado * 16807) % 2147483647; return estado / 2147483647; };
const comps = S.makeTarget(1, azar);                   // nivel "normal" del Sismógrafo
const ts = Array.from({ length: 121 }, (_, i) => i / 10);

const f = new FlickDetector();
f.beats = [0, 500, 1000, 1500];                        // un giro cada 500 ms

process.stdout.write(JSON.stringify({
  comps,
  ts,
  ys: ts.map((t) => S.wave(comps, t)),
  giros_por_minuto: f.tempo(),
  franjas: [0, 0.1, 0.13, 0.26, 0.5, 0.74, 0.9, 0.9999].map((u) => [u, raiz.ratiosOf(1, [0, (1 - u) * 100], [100, 100])[0]]),
}));
