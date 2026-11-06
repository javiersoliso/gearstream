// Ejercicio del capítulo 2: el ángulo entre dos lecturas de la gravedad.
//
// Completa `anguloPunto` y `anguloAtan2` y comprueba tu solución con:
//   node tools/test_marcos.js --ejercicio
//
// Las dos reciben:
//   a, b  dos lecturas de la gravedad, arreglos [x, y, z] en m/s² (no miden exactamente 9.81 y traen ruido)
// y devuelven el ángulo entre ellas, en grados, entre 0 y 180.
//
// La idea, en palabras:
//   anguloPunto: a·b = |a||b| cos θ, así que el coseno es a·b dividido por los dos largos, y acos lo vuelve ángulo.
//                Cuidado: por redondeo ese cociente puede dar 1.0000000000000002, y acos de eso no es un número.
//   anguloAtan2: |a × b| es |a||b| sen θ y a·b es |a||b| cos θ. El par (a·b, |a × b|) señala el ángulo, y atan2
//                lo saca sin dividir por nada.
//
// Las pruebas comprueban que las dos dan 90° entre caras vecinas y 180° entre caras opuestas, también con lecturas
// con ruido, y que dan lo mismo en cualquier par de flechas.
'use strict';

function anguloPunto(a, b) {
  throw new Error('todavía no está hecho: escribe tu ángulo en docs/curso/ejercicios/cap02.js');
}

function anguloAtan2(a, b) {
  throw new Error('todavía no está hecho: escribe tu ángulo en docs/curso/ejercicios/cap02.js');
}

module.exports = { anguloPunto, anguloAtan2 };
