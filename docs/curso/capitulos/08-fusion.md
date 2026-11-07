# Capítulo 8 · Fusión de sensores, y por qué el rumbo se va

El capítulo es una página: [`server/web/fusion.html`](../../../server/web/fusion.html), en `http://localhost:8765/fusion.html` con el servidor de GearStream andando. Este archivo es su guion: lo que cuenta cada escena, la frase que tiene que quedar y cómo se comprueba. Es el piloto del curso: el primer capítulo hecho entero, para saber cuánto cuesta uno.

**Pregunta guía.** El giroscopio es rápido pero se desvía; la gravedad no se desvía pero no lo ve todo. ¿Cómo se juntan los dos?

## Las escenas

Cada escena tiene una frase que, una vez vista la figura, tiene que parecer obvia.

| # | Escena | La frase | La figura | Se comprueba en |
|---|---|---|---|---|
| 1 | Dos testigos que mienten | El giroscopio es bueno en lo rápido y malo en lo lento; el acelerómetro, al revés. | Un minuto de una muñeca inventada: la verdad, el giroscopio sumado (se va b·t) y el acelerómetro (salta con cada sacudida). Controles: sesgo y sacudidas. | `test_fusion.js`: 29.7° a los 60 s con b = 0.5 °/s; el acelerómetro promedia 0.01° pero salta 36°. |
| 2 | Un resorte | El error no crece: se queda quieto en b/k. | Los antebrazos de costado, el filtro atado al acelerómetro por un resorte que engorda con k; abajo, el error contra la punteada b/k. | Con la mano quieta, el error a los 30 s y a los 60 s es b/k (cuatro pares de b y k). |
| 3 | El valle | No hay un k bueno para todo: depende de cuánto miente cada testigo. | El error rms para k de 0.01 a 50 por segundo; la punteada b/k es el lado izquierdo, donde en un minuto hay tiempo de llegar a ella (k de 0.2/s para arriba). | El fondo está cerca de k = 1/s (0.70°); sin sacudidas se corre a 11.5/s. |
| 4 | Lo que la gravedad no ve | Una flecha no cambia si giras alrededor de ella: la gravedad no ve el rumbo. | El antebrazo con el reloj, tres controles (inclinar, atornillar, rumbo) y las tres cifras que lee el reloj. Con el reloj de verdad, las cifras en vivo. | Para varias poses, cambiar el rumbo no cambia ninguna cifra. |
| 5 | En 3D: Mahony | El mismo resorte en 3D endereza la inclinación y deja el rumbo irse casi exactamente ∫ b·ĝ dt. | Un minuto de la animación de apuntar del mocap, con ruido y sesgo: error de inclinación, error de rumbo y la punteada ∫ b·ĝ dt. Control Kp y animación. | Kp = 0: la inclinación se va 26°. Kp = 2: 0.19° de inclinación y 23.2° de rumbo, contra 22.9° predichos. |
| 6 | Con tu reloj | Lo mismo, con tu muñeca. | Los últimos 20 s: la gravedad del reloj (ya fusionada por Samsung), el acelerómetro crudo, el giroscopio sumado y el filtro. Un control suma sesgo, porque el reloj ya resta casi todo el suyo. Y la prueba de la mesa: 10 s para medir el sesgo vertical, 50 s para ver si el rumbo se va sesgo × 50 s. | A mano, con el reloj. Con `tools/fake_watch.py` se comprobó que los datos llegan y se dibujan. |

## Las animaciones

Una por concepto, para ver la idea antes de mover los controles de la página. Salen de
[`animaciones/cap08.py`](../animaciones/cap08.py) (Manim), con los números de `fusionmath.js` y `mocapmath.js`:
[`animaciones/datos_cap08.js`](../animaciones/datos_cap08.js) los calcula con la misma cuenta que la página y las pruebas.
Debajo de cada una va la teoría que cuenta la página.

**Fusión de sensores.** El giroscopio sumado se va b·t (30° en un minuto); el acelerómetro no se va, pero salta con
cada sacudida. Juntos, ni se va ni salta.

![La mano de verdad, el giroscopio sumado que se va 30° en un minuto, el acelerómetro que salta y el filtro que sigue a la mano](../media/cap08/DosTestigos.gif)

**El filtro complementario.** La estimación está atada a la medida con un resorte de rigidez k; el sesgo la corre y
el resorte tira más cuanto más se aleja, hasta que los dos se igualan en e = b/k.

![La estimación atada a la medida con un resorte; el error sube y se queda quieto en b/k, más bajo cuanto más rígido el resorte](../media/cap08/Resorte.gif)

En cada muestra la estimación avanza lo que dice el giroscopio, y el resorte la tira un poquito hacia la medida. El
error es $e = \theta - \theta_{\text{verdad}}$, y cambia por dos razones: el sesgo lo corre $b$ grados por segundo, y el
resorte lo devuelve $k\,e$ grados por segundo. Mientras $b$ sea más grande que $k\,e$, el error crece; se queda quieto
cuando los dos tirones se empatan:

$$e' = b - k\,e \quad\Rightarrow\quad e \to b/k$$

No llega de golpe: $e(t) = (b/k)\,(1 - \exp(-kt))$, la exponencial del capítulo 3 con constante de tiempo $1/k$, así que
tarda unos $3/k$ segundos; con $k$ = 0.01/s no llega en un minuto. Por eso $k$ va en "por segundo": **en $1/k$
segundos el resorte cierra casi dos tercios de la diferencia** (el 63 % del capítulo 3). Un sesgo de 0.5 °/s con
$k$ = 1/s deja medio grado de error, para siempre, y el sesgo solo no deja más que eso.

Se llama **complementario** porque de cada testigo toma lo que al otro le falta: lo rápido del giroscopio y lo lento
del acelerómetro. Juntar dos medidas así, para que cada una tape el defecto de la otra, es la fusión de sensores.

**Qué tan fuerte tirar.** A la izquierda del valle manda el giroscopio y el error va hacia b/k, y llega si hay tiempo;
a la derecha manda el acelerómetro y salta con él. Sin sacudidas, el fondo se corre a la derecha, porque si el
acelerómetro no miente conviene creerle más. Con más sesgo también se corre a la derecha: hay más deriva que frenar.
No hay un k bueno para todo; depende de cuánto miente cada testigo.

![El error rms contra k en escala logarítmica: un valle con el fondo cerca de k = 1/s, que sin sacudidas se corre a k ≈ 12/s](../media/cap08/Valle.gif)

**Lo que la gravedad no ve.** Inclinar y atornillar cambian lo que lee el reloj; girar alrededor de arriba, no. La
gravedad es una sola flecha, y una flecha no cambia si giras alrededor de ella. Así que el resorte del rumbo no tiene de
dónde agarrarse: la inclinación queda atada a la gravedad, y el rumbo queda suelto, con un error que crece b·t.

![El antebrazo con los ejes del reloj y las tres cifras que lee de la gravedad: cambian al inclinar y al atornillar, y no al girar el rumbo](../media/cap08/GravedadNoVeRumbo.gif)

**TRIAD.** Arriba y el antebrazo, conocidos en el reloj y en el mundo, arman la orientación entera, con un rumbo
supuesto porque arriba no dice hacia qué lado apunta el antebrazo. Con el trío $a, b, c$ escrito como columnas en los
dos marcos, $R = [a\ b\ c]_{\text{mundo}}\,[a\ b\ c]_{\text{reloj}}^{\mathsf T}$: de derecha a izquierda, la transpuesta
pasa del reloj al trío y la otra matriz, del trío al mundo (capítulo 5, sección 2).

![Arriba y el antebrazo, el círculo de antebrazos posibles, un rumbo supuesto y las dos flechas que completan el trío](../media/cap08/Triad.gif)

**El método de proyección.** El rumbo es hacia dónde apunta la sombra del antebrazo en el piso; con el brazo
colgando la sombra es un punto, y caminando el método se pierde: 16° de mediana contra menos de 1° de la fusión.

![De costado, el antebrazo baja hasta colgar y su sombra se encoge; caminando, el error de la proyección salta cuando el brazo cuelga y el de la fusión no](../media/cap08/MetodoDeProyeccion.gif)

**Mahony.** El mismo resorte en 3D: e = arriba medido × arriba predicho es el eje del giro que le falta al reloj, y girar
el reloj alrededor de él Kp·|e| por segundo junta las dos flechas. Desde el reloj, la flecha predicha va al revés: $-\omega \times v$. Sin resorte la inclinación se va 26° en un minuto; con
Kp = 2 no pasa de unas décimas.

![Dos flechas, arriba medido y arriba predicho, que se juntan girando alrededor de su producto cruz; luego el error de inclinación con Kp = 0 y con Kp = 2](../media/cap08/Mahony.gif)

El mocap guarda la orientación del reloj en un cuaternión (capítulo 5) y en cada muestra la gira lo que dice el
giroscopio más esa corrección: $q \leftarrow q \otimes \exp((\omega + K_p e)\,\Delta t/2)$. El $\exp$ de una flecha $u$ es
$(\cos|u|,\ \hat u\,\sin|u|)$, el cuaternión del capítulo 5: girar $|\omega + K_p e|\,\Delta t$ alrededor de
$\omega + K_p e$. Las dos flechas "arriba" son casi verticales, así que su producto cruz $e$ es casi horizontal: **la
corrección inclina, pero no agrega ni quita giro alrededor de la vertical**, así que no puede frenar
la deriva del rumbo. Y como Mahony guarda la orientación entera, no necesita el rumbo del
antebrazo en cada muestra: no tiene el hueco de la proyección cuando el brazo cuelga.

**Por qué el rumbo se va.** Con Kp = 2 el rumbo se va igual, y casi exactamente ∫ b·ĝ dt (el ruido suma un paseo de unas décimas de grado): la parte del sesgo que gira
alrededor de la vertical. En la animación esa parte es de unos 0.38 °/s: en 10 s son 3.8°, unos 16 cm de cursor con la pantalla a 2.4 m,
porque ahí un grado son 2.4 m × π/180 ≈ 4.2 cm (capítulo 7).

![El error de rumbo de la fusión encima de la curva predicha ∫ b·ĝ dt, y el rayo a la pantalla que se corre unos 16 cm en 10 s](../media/cap08/DerivaDelRumbo.gif)

**Ningún Kp arregla la deriva**: Kp solo tira de la inclinación. Desde Kp = 0.5 la inclinación queda entre unas
décimas y un par de grados, y el rumbo sigue la punteada casi exacto. Ojo: en la animación el arriba medido no miente,
porque es la gravedad de la animación; con el acelerómetro crudo vuelve el valle, y un Kp alto tiembla. ¿Qué arreglaría
el rumbo? Otra flecha fija en el mundo que no sea vertical: el norte de un magnetómetro, que este reloj no entrega, o
algo que se vea, como la pantalla o una cámara.

**Fusionar una fusión.** El sensor de gravedad del reloj ya es una cuenta de Samsung que junta el acelerómetro y el
giroscopio: por eso tiembla tan poco, y la página lo usa de referencia en vivo. Mahony con esa gravedad es fusionar una
fusión. Debería andar bien, porque casi no tiembla, pero no está medido, y no se sabe qué rigidez eligió Samsung. El
testigo que tiembla de verdad es el acelerómetro crudo.

**Recentrar.** El rumbo es relativo: se fija un frente y se vuelve a él, con un botón o de a poco. De a poco no hace
falta botón, pero también se come los giros que dejas puestos mucho rato.

![El rumbo de tu mano, el de la fusión que se va, el recentrado con un botón y el recentrado de a poco con τ = 12 s](../media/cap08/Recentrar.gif)

Lo ideal es recentrar cuando la mano descansa: si está quieta, nadie nota que el frente se mueve un poco. Pero
`autoCenterStep` de `server/web/avatar.js` no espera al reposo. Con "auto-centrar rumbo" prendido (viene prendido),
en cada cuadro tira del rumbo del antebrazo hacia el frente una fracción $\Delta t/\tau$ de lo que falta, con
$\tau$ = 12 s (con 90° fuera, unos 7.5 °/s), y gira lo mismo el filtro del brazo (`ArmFilter.rotateY`). Por eso se come
también los giros que dejas puestos. La otra forma es el botón, o la tecla R.

## La matemática

- El filtro complementario: `θ ← θ + ω·Δt + k·Δt·(θ_acel − θ)`.
- Por qué b/k: `e′ = b − k·e`, que deja de crecer cuando `e = b/k`; llega como `e(t) = (b/k)(1 − exp(−kt))`, en unos 3/k segundos.
- El acelerómetro se inclina con cada tirón: una muñeca a r del codo que acelera su giro a α empuja de costado con r·α (la aceleración de un punto que gira se ve en el capítulo 9, sección 10). Con el brazo colgando, el acelerómetro cree que arriba se inclinó `atan(r·α / g)`; con el brazo horizontal ese tirón no inclina la elevación, y en medio el efecto cambia. La simulación usa esa fórmula en toda postura: es un modelo inventado, para tener sacudidas de un tamaño creíble, no la física de cada postura. Con la física completa el valle sigue ahí.
- Mahony: `e = ĝ_medido × ĝ_predicho` y `q ← q ⊗ exp((ω + Kp·e)·Δt/2)`.
- La deriva del rumbo: `∫ b·ĝ dt`, la parte del sesgo que gira alrededor de la vertical.
- En el ¡hola! del índice no hay fusión: Dibuja suma el giroscopio solo, así que sus ángulos se van con el sesgo que
  quede, y la tecla R los vuelve a poner en cero (`recenter` de `server/web/dibuja.js`).

## El código

- `paso`, `complementario`, `inclinacion`, `valle`, `gravedadLeida` y `derivaPredicha` en `server/web/fusionmath.js`: la cuenta de la página, sin nada de dibujo.
- La rama de fusión de `reconstruct` en `server/web/mocapmath.js`. La página muestra los dos trozos leyendo los archivos de verdad, así que no se desactualizan.
- Las figuras y la conexión al reloj, en `server/web/fusion.js`.

## El ejercicio

Escribir el filtro en `docs/curso/ejercicios/cap08.js` y correr `node tools/test_fusion.js --ejercicio`. Corre las mismas pruebas que el filtro del curso: con k = 0 integra; con sesgo b el error se queda en b/k; con k grande sigue a la medida; con la muñeca inventada le gana por 5× a cada testigo solo. Da igual si el arreglo guarda la estimación antes o después de usar cada muestra.

## Lo que dejó el piloto

- **Lo que más rindió:** empezar por números que se comprueban (b/k, el valle, ∫ b·ĝ dt) antes de dibujar nada. Las frases de las escenas salieron de las pruebas, no al revés.
- **Lo que costó:** la figura 3D a mano, sin bibliotecas. Para los capítulos 5 y 9 conviene usar three.js como el mocap.
- **Lo que no se pudo comprobar sin el reloj:** que en vivo las curvas tengan el signo correcto con una muñeca de verdad. La cuenta de signos está probada contra `wrist.js`, pero falta mirarlo con el reloj puesto.
- **Para los otros capítulos:** la misma forma (una página, su cuenta en un archivo aparte con pruebas, este guion) y la marca `<meta name="curso-capitulo">` para que `check_curso.py` revise su texto con el glosario.
