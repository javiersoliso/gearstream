// Ejercicio del capítulo 6: fabricar un giro y recuperar sus partes.
//
// Completa `fabricar` y `rollQueSale` y comprueba tu solución con:
//   node tools/test_antebrazo.js --ejercicio
//
// fabricar(a, b, c, g, f) devuelve el arreglo [x, y, z] de ω = a·g + b·f + c·p, en °/s, donde:
//   g  es arriba en los ejes del reloj, de largo 1
//   f  es el antebrazo en los ejes del reloj, de largo 1 ([1, 0, 0] en la izquierda, [−1, 0, 0] en la derecha)
//   p  es f × g dividido por su largo (tienes que calcularlo)
//
// rollQueSale(a, b, g, f) devuelve lo que va a decir `rates` en su roll para ese ω. Ojo: no es b.
//
// La idea, en palabras: g y f no forman ángulo recto salvo con el antebrazo horizontal, así que ω·f se lleva b y
// también la parte de a que cae sobre f. p sí forma ángulo recto con los dos, por eso c no molesta a nadie.
//
// Las pruebas pasan tu ω por `Wrist.rates` de server/web/wrist.js con el antebrazo a muchas alturas, en las dos manos,
// y comprueban que el yaw es a y el pitch es c, exactos, y que el roll es el que dijiste.
'use strict';

function fabricar(a, b, c, g, f) {
  throw new Error('todavía no está hecho: escribe tu ω en docs/curso/ejercicios/cap06.js');
}

function rollQueSale(a, b, g, f) {
  throw new Error('todavía no está hecho: escribe tu roll en docs/curso/ejercicios/cap06.js');
}

module.exports = { fabricar, rollQueSale };
