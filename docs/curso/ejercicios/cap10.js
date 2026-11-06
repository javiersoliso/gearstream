// Ejercicio del capítulo 10: un detector de picos con dos umbrales y un periodo refractario.
//
// Completa `detectar` y comprueba tu solución con:
//   node tools/test_gestos.js --ejercicio
//
// Recibe:
//   t     el instante de cada muestra, en ms (un arreglo)
//   x     la señal en cada muestra, por ejemplo ω_x en °/s (un arreglo del mismo largo). Va para los dos lados.
//   opc   { entrar, salir, refractario }: los dos umbrales, en las unidades de x, y la espera en ms
// Devuelve un arreglo de picos, cada uno { t, signo, tam }: el instante del máximo, +1 o −1, y el tamaño de |x| ahí.
//
// La idea, en palabras. Tienes dos estados:
//   - Afuera: si |x| pasa de `entrar`, y ya pasó más de `refractario` desde el máximo del último pico, empieza uno.
//     Guarda su signo.
//   - Adentro: mientras x siga del mismo signo, guarda el mayor |x| y su instante. El pico se cierra cuando |x| baja
//     de `salir` o cuando x cambia de signo.
// Si te trabas, el capítulo cuenta cómo lo hace `FlickDetector.update`, en server/web/flick.js. Trata de no mirar el
// código hasta que pase.
//
// Las pruebas comprueban que en una señal con 10 picos conocidos y ruido cuentas exactamente 10, con su instante,
// signo y tamaño; que un temblor en el borde del umbral no cuenta dos veces; y que un rebote no cuenta como otro pico.
'use strict';

function detectar(t, x, opc) {
  throw new Error('todavía no está hecho: escribe tu detector en docs/curso/ejercicios/cap10.js');
}

module.exports = { detectar };
