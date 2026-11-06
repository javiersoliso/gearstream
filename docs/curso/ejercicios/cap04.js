// Ejercicio del capítulo 4: la inclinación.
//
// Completa `inclinacion` y comprueba tu solución con:
//   node tools/test_gravedad.js --ejercicio
//
// Recibe:
//   g    la gravedad que lee el reloj, un arreglo [x, y, z] en m/s² (apunta hacia arriba; no tiene por qué medir 9.81)
//   eje  un eje del reloj, un arreglo [x, y, z] (por ejemplo [0, 0, 1], y tampoco tiene por qué medir 1)
// Devuelve el ángulo entre ese eje y la vertical, en grados, de 0 a 180.
//
// La idea, en palabras: divide los dos por su largo, haz el producto punto y saca el arccos. Cuidado: por el redondeo
// el producto punto puede dar 1.0000000002, y el arccos de eso no existe.
//
// Las pruebas comprueban las seis posturas (0°, 90° y 180°), que da igual el largo de g y que girar el reloj sobre
// la mesa no cambia la inclinación.
'use strict';

function inclinacion(g, eje) {
  throw new Error('todavía no está hecho: escribe tu inclinación en docs/curso/ejercicios/cap04.js');
}

module.exports = { inclinacion };
