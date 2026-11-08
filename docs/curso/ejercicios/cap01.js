// Ejercicio del capítulo 1: encontrar el primer segundo quieto y su sesgo.
//
// Completa `primerReposo` y comprueba tu solución con:
//   node tools/test_sensor.js --ejercicio
//
// Recibe tres listas de muestras {t, x, y, z}, con t en ms, a unas 100 muestras por segundo:
//   giro  el giroscopio, en °/s
//   acel  el acelerómetro, en m/s²
//   grav  el sensor de gravedad, en m/s² (usa su dirección: divídelo por su largo)
// Devuelve {t, sesgo: [x, y, z]}: el instante en que termina el primer segundo quieto y la mediana del giroscopio
// en ese segundo, eje por eje. Si nunca hay un segundo quieto, devuelve null.
//
// La idea, en palabras: cada 10 muestras del giroscopio mira el último segundo (al menos 80 muestras) y
// pregúntale lo mismo que Motion._rest_window. Quieto quiere decir que, en ese segundo:
//   1. el pico a pico del giroscopio es menor que 2.5 °/s en cada eje;
//   2. la mediana del giroscopio es menor que 1.5 °/s en valor absoluto en cada eje;
//   3. el largo del acelerómetro no se aleja más de 1 m/s² de 9.807;
//   4. entre dos muestras seguidas del acelerómetro, la distancia entre (x, y, z) y el siguiente (x, y, z)
//      es menor que 0.6 m/s²;
//   5. la dirección de la gravedad, componente por componente, tiene un pico a pico menor que 0.05.
//
// La grabación de prueba tiene una trampa para cada condición. Las pruebas comprueban que caes en el mismo segundo
// que Motion._calibrate, con el mismo sesgo, y, si hay python, que repitiendo la grabación con
// `python tools/air_mouse.py --replay` el programa toma ese mismo sesgo.
'use strict';

function primerReposo(giro, acel, grav) {
  throw new Error('todavía no está hecho: escribe tu búsqueda en docs/curso/ejercicios/cap01.js');
}

module.exports = { primerReposo };
