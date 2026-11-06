// Ejercicio del capítulo 12: resolver ridge a mano, para dos rasgos.
//
// Completa `ridge` y comprueba tu solución con:
//   node tools/test_aprender.js --ejercicio
//
// Recibe:
//   X    un arreglo de filas [x1, x2]: los dos rasgos de cada muestra
//   y    un arreglo con lo que se quiere predecir en cada muestra
//   lam  el castigo λ
// Devuelve [w1, w2, b]: los dos coeficientes sobre los rasgos ESTANDARIZADOS y el término constante, en el mismo
// orden que `Ridge.W` de tools/reconstruct_drawing.py.
//
// La idea, en palabras. Estandariza cada rasgo: réstale su promedio y divídelo por su desviación estándar (la que
// divide por n, no por n − 1). Llama z1 y z2 a lo que queda. Como z1 y z2 tienen promedio cero, el término constante
// se separa solo: b es el promedio de y, y no se castiga. Para w1 y w2 queda un sistema de 2 × 2:
//
//   (S11 + λ) w1 +  S12      w2 = T1          con S11 = Σ z1², S12 = Σ z1·z2, S22 = Σ z2²,
//    S12      w1 + (S22 + λ) w2 = T2              T1 = Σ z1·y,  T2 = Σ z2·y
//
// Eso es (XᵀX + λI)W = XᵀV escrito a mano. Resuélvelo con la regla de Cramer o despejando.
//
// Las pruebas comparan tu resultado con lo que da `Ridge.fit` de verdad y comprueban que con λ → 0 sale mínimos
// cuadrados, que con λ enorme queda solo el promedio y que el tamaño de W baja cuando λ sube.
'use strict';

function ridge(X, y, lam) {
  throw new Error('todavía no está hecho: escribe tu solución en docs/curso/ejercicios/cap12.js');
}

module.exports = { ridge };
