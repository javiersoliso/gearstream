// Ejercicio del capítulo 7: ¿a qué ángulo se separan el cursor y el rayo?
//
// Completa `anguloDeSeparacion` y comprueba tu solución con:
//   node tools/test_cursor.js --ejercicio
//
// Recibe:
//   D    la distancia a la pantalla, en metros
//   sep  la separación que quieres entre el rayo y el cursor, en metros (por ejemplo 0.01, un centímetro)
// Devuelve el ángulo, en grados, al que el rayo (D·tan θ) y el cursor (D·θ) quedan separados `sep`.
//
// La idea, en palabras: la separación es D·(tan θ − θ), y para ángulos pequeños tan θ − θ ≈ θ³/3. Despeja θ, que
// sale en radianes, y pásalo a grados.
//
// Las pruebas giran un cursor de verdad, con `cursorTrack` de server/web/mocapmath.js, hasta que se separa `sep` del
// rayo, y comparan ese ángulo con el tuyo. Con D = 2.4 m y 1 cm tienen que salir unos 13°.
'use strict';

function anguloDeSeparacion(D, sep) {
  throw new Error('todavía no está hecho: escribe tu cuenta en docs/curso/ejercicios/cap07.js');
}

module.exports = { anguloDeSeparacion };
