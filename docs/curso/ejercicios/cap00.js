// Ejercicio del capítulo 0: interpolar.
//
// Completa `interpolar` y comprueba tu solución con:
//   node tools/test_muestreo.js --ejercicio
//
// Recibe:
//   t   el instante en que quieres saber el valor (un número)
//   ts  el tiempo de cada muestra, de menor a mayor (un arreglo; no vienen parejas)
//   xs  el valor de cada muestra (un arreglo del mismo largo)
// Devuelve el valor de la recta que une las dos muestras que rodean a `t`. Si `t` cae antes de la primera
// muestra devuelve la primera, y si cae después de la última, la última: lo mismo que hace `np.interp`.
//
// La idea, en palabras: busca la muestra k que cae justo antes de `t`. Saca qué parte del camino llevas hasta la
// siguiente, u = (t − ts[k]) / (ts[k+1] − ts[k]), y avanza esa parte de lo que cambia x entre las dos.
//
// Las pruebas comprueban que caes justo en cada muestra, que respetas los extremos, y que coincides con la cuenta
// de `np.interp` en mil instantes al azar (con numpy de verdad si tu máquina tiene python con numpy).
'use strict';

function interpolar(t, ts, xs) {
  throw new Error('todavía no está hecho: escribe tu interpolación en docs/curso/ejercicios/cap00.js');
}

module.exports = { interpolar };
