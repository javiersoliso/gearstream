// Ejercicio del capítulo 3: integrar con números.
//
// Completa `integrar` y comprueba tu solución con:
//   node tools/test_derivar.js --ejercicio
//
// Recibe:
//   t     el tiempo de cada muestra, en segundos (un arreglo; no vienen parejas, y a veces se pierde alguna)
//   tasa  lo que dice el sensor en cada muestra, por ejemplo °/s (un arreglo del mismo largo)
// Devuelve un arreglo del mismo largo con cuánto se acumuló hasta cada muestra, empezando en 0.
//
// La idea, en palabras: entre una muestra y la siguiente pasó un tiempo Δt, que se saca de `t`, no se supone. En
// ese rato se acumuló tasa × Δt. Da igual si usas la tasa de la muestra de antes o la de después.
//
// Las pruebas comprueban que 10 °/s durante 3 s dan 30°, también si se pierden muestras, y que tu integral predice
// lo que dice el capítulo: b·t con un sesgo, σ√(t·Δt) con ruido, b·t²/2 integrando dos veces y a/(2πf) con una onda.
'use strict';

function integrar(t, tasa) {
  throw new Error('todavía no está hecho: escribe tu integral en docs/curso/ejercicios/cap03.js');
}

module.exports = { integrar };
