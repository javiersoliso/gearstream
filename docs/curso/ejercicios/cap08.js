// Ejercicio del capítulo 8: el filtro complementario.
//
// Completa `complementario` y comprueba tu solución con:
//   node tools/test_fusion.js --ejercicio
//
// Recibe:
//   giro    lo que dice el giroscopio en cada muestra, en °/s (un arreglo)
//   medido  lo que dice el acelerómetro en cada muestra, en grados (un arreglo del mismo largo)
//   hz      muestras por segundo (100: entre una y otra pasan 0.01 s)
//   k       la rigidez del resorte, por segundo
//   th0     el ángulo con que arranca la estimación, en grados
// Devuelve un arreglo con tu estimación del ángulo en cada muestra.
//
// La idea, en palabras: en cada muestra, avanza lo que dice el giroscopio y tira un poquito hacia lo
// que dice el acelerómetro, más fuerte cuanto más grande es k. Si te trabas, la página del capítulo
// (fusion.html) muestra la fórmula; trata de no mirar el código del curso hasta que pase.
'use strict';

function complementario(giro, medido, hz, k, th0) {
  throw new Error('todavía no está hecho: escribe tu filtro en docs/curso/ejercicios/cap08.js');
}

module.exports = { complementario };
