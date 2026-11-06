// Ejercicio del capítulo 9: la cinemática inversa de dos huesos.
//
// Completa `ik` y comprueba tu solución con:
//   node tools/test_cuerpo.js --ejercicio
//
// Recibe:
//   hombro    dónde está el hombro, [x, y, z] en metros
//   objetivo  dónde debe ir la muñeca, [x, y, z]
//   l1, l2    el largo del brazo y del antebrazo
//   polo      un punto hacia el que se dobla el codo, [x, y, z]
// Devuelve { codo, muneca }, dos arreglos [x, y, z].
//
// La idea, en palabras:
//   1. Mide d, la distancia del hombro al objetivo, y saca la dirección de largo 1 que va hacia él.
//   2. Si el objetivo está demasiado lejos o demasiado cerca, recorta d entre |l1 − l2| y l1 + l2: la muñeca llega
//      hasta donde puede, en esa misma dirección.
//   3. El hombro, el codo y la muñeca forman un triángulo de lados l1, l2 y d. La ley de los cosenos da cuánto avanza
//      el codo a lo largo de la dirección, x = (l1² − l2² + d²) / (2d), y Pitágoras cuánto se separa, h = √(l1² − x²).
//   4. Hacia qué lado se separa lo dice el polo: toma la flecha del hombro al polo, quítale la parte que va a lo
//      largo de la dirección y déjala de largo 1.
//
// Las pruebas tiran mil objetivos al azar y comprueban que el codo queda a l1 del hombro, que la muñeca queda a l2
// del codo, que llega al objetivo cuando está a su alcance y que da lo mismo que `build` de server/web/mocapmath.js.
'use strict';

function ik(hombro, objetivo, l1, l2, polo) {
  throw new Error('todavía no está hecho: escribe tu cinemática inversa en docs/curso/ejercicios/cap09.js');
}

module.exports = { ik };
