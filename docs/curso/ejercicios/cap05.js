// Ejercicio del capítulo 5: el cuaternión de un giro.
//
// Completa `cuaternion` y comprueba tu solución con:
//   node tools/test_rotar.js --ejercicio
//
// Recibe:
//   eje     el eje del giro, un arreglo [x, y, z] (no tiene por qué medir 1)
//   angulo  cuánto girar alrededor de él, en radianes (positivo: contra el reloj mirando desde la punta del eje)
// Devuelve el cuaternión [w, x, y, z] de ese giro.
//
// La idea, en palabras: w es el coseno de la mitad del ángulo, y (x, y, z) es el eje, de largo 1, por el seno de
// la mitad del ángulo. Las pruebas comprueban que tu cuaternión gira igual que rot() (Rodrigues), que componer
// giros es multiplicar cuaterniones (qmul) y que sumar muchos giros chiquitos da el giro grande.
'use strict';

function cuaternion(eje, angulo) {
  throw new Error('todavía no está hecho: escribe tu cuaternión en docs/curso/ejercicios/cap05.js');
}

module.exports = { cuaternion };
