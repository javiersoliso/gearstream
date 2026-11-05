# Curso de GearStream · índice

Un curso de matemática desde lo más básico, al estilo de 3Blue1Brown, contado con lo que hace GearStream: un reloj que manda su acelerómetro, su giroscopio y su gravedad a 100 Hz a la laptop, y con eso mueve el cursor, dibuja en 1D, 2D y 3D, juega y anima un stickman. Cada idea aparece cuando hace falta, y su nombre llega después de la idea.

Cada capítulo tiene la misma forma:

1. **Una pregunta**, la guía, y las que salen de ahí: las que haría alguien curioso.
2. **Intuición visual**, interactiva: ver la idea antes de escribirla.
3. **La matemática mínima**: solo lo que hace falta para responder.
4. **El código**: una función real del repo, de 30 líneas o menos.
5. **Un experimento con datos reales**: con tu reloj o con una grabación de ejemplo.
6. **Un ejercicio que se comprueba**: con un número o una prueba que pasa o no pasa.

[mapa.md](mapa.md) dibuja qué necesita cada concepto, y [conceptos.json](conceptos.json) es su fuente: cada concepto con su definición, lo que necesita, las palabras que lo nombran y las funciones del código que lo usan. `python -I tools/check_curso.py` comprueba que cada concepto llegue después de lo que necesita, que ningún término del glosario aparezca en un capítulo anterior al que lo define, y que cada función con matemática del repo esté cubierta por algún concepto. La regla del glosario vale para todo lo que está dentro de un capítulo, preguntas incluidas: por eso el capítulo 1 dice "qué tan rápido gira" y no "velocidad angular", que se define en el 5.

Los capítulos ya escritos tienen su guion en [capitulos/](capitulos/) y su página en `server/web/`, marcada con `<meta name="curso-capitulo">`; `check_curso.py` también revisa su texto con la regla del glosario. Por ahora están escritos el 3, el 5, el 8 y el 11.

Los datos: `recordings/` es personal y no se sube. Para que los experimentos funcionen sin reloj hay que publicar a propósito una grabación de ejemplo, que todavía no existe.

## Contenido

- [0 · Un número que cambia](#capítulo-0--un-número-que-cambia)
- [1 · Qué es un sensor](#capítulo-1--qué-es-un-sensor)
- [2 · Vectores y marcos](#capítulo-2--vectores-y-marcos)
- [3 · Derivar e integrar con números](#capítulo-3--derivar-e-integrar-con-números)
- [4 · La gravedad dice dónde es arriba](#capítulo-4--la-gravedad-dice-dónde-es-arriba)
- [5 · Rotar](#capítulo-5--rotar)
- [6 · Del reloj al antebrazo: roll, yaw y pitch](#capítulo-6--del-reloj-al-antebrazo-roll-yaw-y-pitch)
- [7 · De 3D a 2D: el cursor](#capítulo-7--de-3d-a-2d-el-cursor)
- [8 · Fusión de sensores y por qué el rumbo se va](#capítulo-8--fusión-de-sensores-y-por-qué-el-rumbo-se-va)
- [9 · El cuerpo en 3D](#capítulo-9--el-cuerpo-en-3d)
- [10 · Gestos](#capítulo-10--gestos)
- [11 · Frecuencia](#capítulo-11--frecuencia)
- [12 · Aprender de datos](#capítulo-12--aprender-de-datos)
- [Apéndice · Supuestos, falencias y cosas por mejorar](#apéndice--supuestos-falencias-y-cosas-por-mejorar)

## Capítulo 0 · Un número que cambia

**Conceptos:** `senal` · `unidades` · `muestreo` · `marca_de_tiempo` · `interpolacion_lineal` · `cuantizar` · `lecturas_nuevas` · `resumir_ventana` · `latencia` · `alinear_relojes` · `agrupar_muestras`

**Pregunta guía.** ¿Cómo se guarda en una computadora algo que no para de cambiar, como el movimiento de tu muñeca?

**Preguntas que salen de ahí**

1. Si el reloj mide 100 veces por segundo, ¿qué pasó entre una medida y la siguiente? ¿Se puede adivinar?
2. ¿Por qué cada muestra trae la hora en que se midió? ¿No basta con saber que llegan 100 por segundo?
3. ¿Qué quiere decir "9.81 m/s²" o "300 °/s"? Si cambio de unidades, ¿cambia algo de verdad?
4. Si pido 200 muestras por segundo y llegan 200, ¿son 200 medidas distintas? (A 5 ms solo unas 115 son lecturas nuevas.)
5. El reloj y la laptop tienen cada uno su hora. ¿Cómo sé cuánto tardó una muestra en llegar, si ninguno de los dos relojes es "el de verdad"?
6. Si la red deja pasar un paquete por cada ida y vuelta, ¿cómo llegan 100 muestras por segundo por un Wi-Fi lento, y qué pierdo a cambio?
7. De mil números de una grabación, ¿con cuál me quedo para resumirla: el promedio, la mediana, el más grande? ¿Cuándo engaña cada uno?
8. Si un número solo puede caer en ciertos escalones, ¿cuánto detalle se pierde? ¿Se nota?

**Cómo sería el capítulo**

- *Intuición visual:* un punto que sube y baja con tu muñeca, en vivo; un control cambia cuántas veces por segundo se mide, y se ven los puntos sueltos, la recta que los une y lo que se pierde entre medio.
- *La matemática mínima:* `t_k = t₀ + k·Δt` y `f = 1/Δt`; entre dos muestras, `x(t) ≈ x_k + (t − t_k)/(t_k+1 − t_k)·(x_k+1 − x_k)`; el desfase entre relojes es el mínimo de (llegada − medida); el caudal es muestras por paquete sobre la ida y vuelta.
- *El código:* `Bridge.map_time` de `tools/sdb_bridge.py` (16 líneas): el desfase de cada sensor es el más chico visto, con una fuga lenta, y un salto de horas no lo mueve.
- *Experimento con datos reales:* en una grabación propia, contar muestras y lecturas nuevas por segundo de cada sensor, y graficar los Δt con la pantalla del reloj encendida y apagada.
- *Ejercicio que se comprueba:* escribir `interpolar(t, ts, xs)` y comprobar que coincide con `np.interp` en mil instantes al azar.

## Capítulo 1 · Qué es un sensor

**Conceptos:** `ejes_del_reloj` · `acelerometro` · `giroscopio` · `sensor_gravedad` · `ruido` · `tamano_tipico` · `sesgo` · `umbral` · `aprender_sesgo`

**Pregunta guía.** ¿Qué siente de verdad el reloj cuando mueves la mano?

**Preguntas que salen de ahí**

1. Con el reloj quieto sobre la mesa, ¿por qué el acelerómetro no marca cero?
2. Si el giroscopio marca 0.4 °/s con la mano quieta, ¿es la Tierra que gira o es el sensor? ¿Cómo lo distingo? (La Tierra da una vuelta al día: 0.004 °/s.)
3. ¿Por qué dos medidas seguidas, sin mover nada, no dan el mismo número?
4. ¿Cuánto ruido es "mucho"? ¿Con qué número lo mido?
5. Quieta, la mano nunca da cero. Entonces, ¿cómo sabe el programa que está quieta?
6. El reloj tiene un "sensor de gravedad", pero adentro no hay ningún sensor así. ¿De dónde sale ese número, y por qué deberíamos creerle?
7. ¿Hacia dónde apunta cada eje del reloj? ¿Qué cambia si me lo pongo en la otra mano?
8. Si el sesgo cambia con la temperatura, ¿cada cuánto hay que volver a medirlo?

**Cómo sería el capítulo**

- *Intuición visual:* las tres barras del giroscopio en vivo con el reloj sobre la mesa; un zoom hasta ver el temblor alrededor de un centro que no es cero, y una línea de "quieto" que se puede subir y bajar.
- *La matemática mínima:* medida = verdad + sesgo + ruido; `RMS = √(promedio de x²)`, y la desviación estándar es el RMS después de restar el promedio; el sesgo es la mediana de un segundo quieto.
- *El código:* `Motion._rest_window` de `tools/air_mouse.py` (26 líneas sin su comentario): decide si el último segundo fue reposo con el pico a pico, la mediana, el largo del acelerómetro y la gravedad.
- *Experimento con datos reales:* un minuto con el reloj en la mesa: el histograma del giroscopio por eje, su mediana (el sesgo) y su desviación estándar (el ruido); repetirlo después de diez minutos de uso, con el reloj tibio.
- *Ejercicio que se comprueba:* en una grabación con reposo y movimiento, encontrar el primer segundo quieto y su sesgo, y comprobar que coincide con el que toma `Motion._calibrate` repitiendo la misma grabación (`--replay`).

## Capítulo 2 · Vectores y marcos

**Conceptos:** `vector` · `norma` · `vector_unitario` · `trigonometria` · `envolver_angulos` · `producto_punto` · `producto_cruz` · `regla_mano_derecha` · `marco_de_referencia` · `coordenadas_en_una_base` · `cambio_de_marco`

**Pregunta guía.** El reloj dice "x, y, z". ¿x, y, z de quién?

**Preguntas que salen de ahí**

1. ¿Por qué tres números alcanzan para decir una dirección en el espacio? ¿Y cuántos hacen falta si solo me importa hacia dónde apunta, y no su largo?
2. Si el reloj dice que la gravedad es (0, 9.8, 0) y un rato después (0, 0, 9.8), ¿se movió la gravedad o se movió el reloj?
3. ¿Qué mide el producto punto, y por qué da cero cuando dos flechas forman ángulo recto?
4. ¿Cómo encuentro una flecha que forme ángulo recto con otras dos? ¿Hacia cuál de los dos lados apunta, y quién lo decide?
5. ¿Por qué 350° y −10° son el mismo ángulo, y qué sale si los promedio sin cuidado?
6. Si me pongo el reloj en la otra mano, ¿lo que cambia es un espejo o un giro?
7. Si dos ejes no forman ángulo recto, ¿cómo escribo una flecha como suma de ellos?
8. ¿Por qué atan2(y, x) y no simplemente el ángulo de y/x?

**Cómo sería el capítulo**

- *Intuición visual:* dos flechas que se arrastran con el ratón: la sombra de una sobre la otra es el producto punto, y el producto cruz sale del plano con el área del paralelogramo; al girar los ejes, la flecha queda quieta y sus tres números cambian.
- *La matemática mínima:* `|v| = √(x² + y² + z²)`; `a·b = Σ aᵢbᵢ = |a||b| cos θ`; `a × b`; en un marco de ejes unitarios en ángulo recto cada coordenada es un producto punto, y los nueve números juntos (una matriz) pasan del reloj al mundo.
- *El código:* `dot`, `cross`, `norm` y `forearmOf` de `server/web/wrist.js` (4 líneas) y `watchOf` de `server/web/mocapmath.js` (6 líneas).
- *Experimento con datos reales:* el reloj quieto en seis posturas, cada cara hacia arriba: los números de la gravedad cambian, pero su largo es siempre 9.8.
- *Ejercicio que se comprueba:* calcular el ángulo entre la gravedad de dos posturas con el producto punto y con atan2, y comprobar que da 90° entre caras vecinas y 180° entre opuestas.

## Capítulo 3 · Derivar e integrar con números

**Ya está escrito:** su [texto](capitulos/03-derivar.md), con una animación por concepto; las pruebas están en `tools/test_derivar.js` y el ejercicio, en `docs/curso/ejercicios/cap03.js`.

**Conceptos:** `derivada_discreta` · `segunda_derivada` · `integral_discreta` · `error_acumulado` · `doble_integral_zupt` · `suavizar` · `derivar_amplifica_ruido` · `paso_alto` · `curva_suave` · `onda_seno` · `integrar_un_seno`

**Pregunta guía.** Si el giroscopio solo dice qué tan rápido giras, ¿cómo sabes cuánto giraste?

**Preguntas que salen de ahí**

1. Si sumo "grados por segundo × segundos" muestra a muestra, ¿me dan los grados? ¿Y si se pierde una muestra?
2. Un sesgo de 0.3 °/s parece nada. ¿Cuánto es después de un minuto? ¿Y de una hora?
3. El ruido va para un lado y para el otro. ¿Por qué al integrarlo también crece? ¿Crece igual que el sesgo?
4. Para ir de la aceleración a la posición hay que integrar dos veces. ¿Por qué eso es mucho peor que una?
5. ¿Por qué derivar una señal con ruido da algo casi inservible, y cómo se arregla?
6. Si la muñeca va y viene muy rápido, ¿por qué el ángulo casi no cambia?
7. ¿Qué es suavizar, y qué se pierde al hacerlo?
8. ¿Para qué sirve saber que el dedo está quieto al apoyarlo y al levantarlo?

**Cómo sería el capítulo**

- *Intuición visual:* arriba la tasa del giroscopio, abajo el ángulo como el área que se va acumulando; un control de sesgo inclina la recta del error y uno de ruido la hace temblar como un paseo al azar.
- *La matemática mínima:* `(x[k+1] − x[k−1]) / 2Δt`; `θ ≈ Σ ω·Δt`; un sesgo b deja un error `b·t`, el ruido `σ·√(t·Δt)` y la doble integral `b·t²/2`; integrar `a·sen(2πft)` da amplitud `a/(2πf)`; suavizar es `y ← y + α(x − y)`.
- *El código:* `cursorTrack` de `server/web/mocapmath.js` (9 líneas) y `movavg` de `tools/analyze_dataset.py` (8 líneas).
- *Experimento con datos reales:* el reloj quieto 60 s: integrar el giroscopio con y sin restar el sesgo, e integrar dos veces el acelerómetro (menos su promedio) para ver cuánto "se mueve" algo que no se movió.
- *Ejercicio que se comprueba:* una tasa constante de 10 °/s durante 3 s tiene que dar 30°; después, predecir la deriva de un sesgo medido y compararla con la del experimento.

## Capítulo 4 · La gravedad dice dónde es arriba

**Conceptos:** `fuerza_especifica` · `arriba_desde_gravedad` · `inclinacion` · `aceleracion_lineal` · `rumbo`

**Pregunta guía.** Con la mano quieta, ¿cómo sabe el reloj hacia dónde está inclinado?

**Preguntas que salen de ahí**

1. Si el acelerómetro mide aceleración, ¿por qué quieto marca 9.81 hacia arriba y no hacia abajo?
2. ¿Se puede saber la inclinación del reloj sin integrar nada? ¿Por qué es tan buena noticia después del capítulo 3?
3. Si giro el reloj sobre la mesa, como la aguja de una brújula, ¿cambia lo que dice la gravedad?
4. Cuando muevo la mano, el acelerómetro mezcla la gravedad con lo que yo empujo. ¿Cómo los separo?
5. ¿Cuándo deja de servir el acelerómetro para saber dónde está arriba?
6. ¿Cómo reconoce el programa que el brazo está colgando?
7. ¿Qué es lo que la gravedad nunca va a poder decir?

**Cómo sería el capítulo**

- *Intuición visual:* un reloj 3D que se inclina con el tuyo y la flecha de la gravedad dentro de sus ejes; al girarlo sobre la mesa la flecha no se mueve: así se ve lo que la gravedad no ve, el rumbo.
- *La matemática mínima:* acelerómetro = aceleración − gravedad (la fuerza específica: 9.81 hacia arriba en reposo); `arriba = g/|g|`; la inclinación es `acos(ĝ·eje)` o atan2 de dos componentes; aceleración lineal = acelerómetro − gravedad.
- *El código:* `Motion.roll_from_gravity` de `tools/air_mouse.py` (9 líneas) y la primera línea de `onAccel` en `server/web/game.js`.
- *Experimento con datos reales:* girar el reloj despacio por las seis posturas y comparar acelerómetro y gravedad; después moverlo de golpe y ver dónde dejan de coincidir.
- *Ejercicio que se comprueba:* escribir `inclinacion(g, eje)` y comprobar con las seis posturas (0°, 90°, 180°), y que girar el reloj sobre la mesa no la cambia.

## Capítulo 5 · Rotar

**Ya está escrito:** su [texto](capitulos/05-rotar.md), con una animación por concepto; las pruebas están en `tools/test_rotar.js` y el ejercicio, en `docs/curso/ejercicios/cap05.js`.

**Conceptos:** `rotacion_2d` · `eje_y_angulo` · `matriz_de_rotacion` · `orden_no_conmuta` · `velocidad_angular` · `velocidad_de_un_punto_que_gira` · `angulos_de_euler` · `singularidad` · `cuaternion` · `integrar_orientacion`

**Pregunta guía.** ¿Cómo se describe un giro en 3D, y por qué los ángulos a veces se rompen?

**Preguntas que salen de ahí**

1. ¿Todo giro en 3D, por raro que sea, es girar alrededor de un solo eje? ¿Cómo encuentro ese eje?
2. Si giro 90° alrededor de x y luego 90° alrededor de y, ¿termino igual que si lo hago al revés?
3. ¿Qué es la velocidad angular? ¿Por qué es una flecha y no un número?
4. Si describo la orientación con tres ángulos, ¿por qué con el brazo colgando uno de ellos deja de existir?
5. ¿Por qué hacen falta cuatro números para algo que tiene tres grados de libertad?
6. Si sumo muchos giros chiquitos, ¿por qué la orientación se "deforma" y hay que normalizarla?
7. ¿Cómo se mueve un punto pegado a algo que gira? ¿Hacia dónde va?
8. Una matriz de rotación y un cuaternión guardan lo mismo. ¿Cuándo conviene cada uno?

**Cómo sería el capítulo**

- *Intuición visual:* un reloj 3D con tres anillos, uno por ángulo, que se traban cuando el antebrazo apunta al piso; al lado, el mismo giro como un eje y un ángulo, que nunca se traba.
- *La matemática mínima:* la rotación en el plano; Rodrigues, `v' = v cos θ + (k × v) sen θ + k (k·v)(1 − cos θ)`; `q = (cos θ/2, k sen θ/2)`; `q ← q ⊗ (cos(|ω|Δt/2), ω̂ sen(|ω|Δt/2))`; un punto que gira va a `ω × r`.
- *El código:* `rot`, `qmul` y `qcols` de `server/web/mocapmath.js` (12 líneas).
- *Experimento con datos reales:* integrar el giroscopio de una grabación propia con cuaterniones y con tres ángulos, y comparar justo cuando el brazo cuelga.
- *Ejercicio que se comprueba:* comprobar con `rot` que 90° en x y luego en y no da lo mismo que al revés, y que `qmul` da lo mismo que multiplicar las dos matrices.

## Capítulo 6 · Del reloj al antebrazo: roll, yaw y pitch

**Conceptos:** `antebrazo_eje_x` · `roll` · `pitch` · `yaw` · `giros_independientes`

**Pregunta guía.** El giroscopio gira con el reloj. ¿Cómo se convierte eso en "apunté a la izquierda" o "atornillé"?

**Preguntas que salen de ahí**

1. ¿Por qué el eje x del reloj es justo el antebrazo? ¿Qué pasa si me pongo el reloj girado?
2. En la muñeca derecha, si no aviso, ¿por qué arriba sale abajo y atornillar sale desatornillar?
3. El yaw es "girar alrededor de la vertical". Pero el reloj no sabe dónde es la vertical… ¿o sí?
4. ¿Por qué el yaw se divide por 1 − (g·f)², y qué pasa cuando el antebrazo apunta casi al piso?
5. Si atornillo sin mover la mano, ¿por qué el cursor no se mueve, sea cual sea la inclinación?
6. ¿Son el roll, el yaw y el pitch tres giros perpendiculares? ¿Importa si no lo son?
7. El ratón aéreo (Python), las páginas (wrist.js) y el avatar hacen esta cuenta cada uno por su lado, y no igual. ¿Qué haría falta para confiar en que dan lo mismo?

**Cómo sería el capítulo**

- *Intuición visual:* un antebrazo con tres flechas pegadas, roll a lo largo, pitch de costado y yaw en la vertical; giras la muñeca y se enciende la que corresponde, a cualquier inclinación.
- *La matemática mínima:* `roll = ω·f`; `pitch = ω·(f × g)/|f × g|`; `yaw = (ω·g − roll·(g·f)) / (1 − (g·f)²)`, el coeficiente de g al escribir ω en la base {g, f, f × g}; con f = −x en la muñeca derecha, pitch y roll cambian de signo.
- *El código:* `Wrist.rates` de `server/web/wrist.js` (13 líneas).
- *Experimento con datos reales:* con tu sesión del dataset de gestos, calcular los tres giros en los pasos de muñeca lenta y rápida y ver cuál de los tres manda en cada uno.
- *Ejercicio que se comprueba:* fabricar ω = a·g + b·f + c·p con a, b y c conocidos, pasarlo por `rates` y recuperar a (el yaw) y c (el pitch) exactos; ver que el roll no es b cuando g·f ≠ 0.

## Capítulo 7 · De 3D a 2D: el cursor

**Conceptos:** `arco_d_theta` · `rayo_tangente` · `coordenadas_esfericas` · `ganancia` · `recortar` · `subpixel` · `zona_muerta` · `curva_de_aceleracion` · `filtro_1euro` · `mapa_lineal_2x2` · `potencias_y_logaritmos` · `ley_de_fitts`

**Pregunta guía.** ¿Cuántos píxeles tiene que moverse el cursor cuando giras la muñeca un grado?

**Preguntas que salen de ahí**

1. Si apunto con un láser a una pared a 2.4 m y giro 10°, ¿cuánto se mueve el punto? ¿Y si giro 40°? (42 cm contra 2 m.)
2. ¿Por qué el ratón aéreo usa D·θ y no D·tan θ, si lo segundo es lo "correcto"?
3. ¿Por qué el cursor avanza más cuando giro rápido, aunque gire los mismos grados?
4. Si la mano me tiembla un poco, ¿cómo evito que tiemble el cursor sin que se vuelva lento?
5. ¿Qué es la zona muerta y por qué no puede ser grande? ¿Qué pasa justo en su borde?
6. ¿Por qué cuesta más mover el cursor en vertical que en horizontal? (Hace falta ×1.3, y los ejes se cruzan a 75°.)
7. ¿Cómo mido si un ajuste es mejor que otro, con un número y no con "se siente mejor"?
8. Si el cursor solo se mueve en píxeles enteros, ¿qué pasa con los movimientos de medio píxel?

**Cómo sería el capítulo**

- *Intuición visual:* un muñeco apunta a una pantalla; el rayo de verdad (D·tan θ) y el cursor (D·θ) se separan al alejarse del centro; controles de ganancia, zona muerta, curva de aceleración y suavizado, con el cursor respondiendo en vivo.
- *La matemática mínima:* el arco `D·θ` (θ en radianes; un grado son `D·π/180`); el rayo `D·tan θ ≈ D·θ` para ángulos pequeños; la ganancia en píxeles por grado; una curva suave entre `v_lo` y `v_hi`; el filtro 1€, `α = 1/(1 + 1/(2π f_c Δt))` con `f_c = f_min + β|ẋ|`; Fitts, `ID = log2(D/W + 1)`.
- *El código:* la clase `OneEuro` de `tools/air_mouse.py` (26 líneas).
- *Experimento con datos reales:* la prueba de objetivos de `calibrate.html` con dos ajustes distintos; comparar tiempos, sobrepasos y bits por segundo.
- *Ejercicio que se comprueba:* ¿a qué ángulo se separan 1 cm D·θ y D·tan θ con D = 2.4 m? Con `tan θ − θ ≈ θ³/3` salen unos 13°; comprobarlo con `cursorTrack`. (En 2D, en los íconos de las esquinas, la simulación llega a unos 3 cm.)

## Capítulo 8 · Fusión de sensores y por qué el rumbo se va

**Conceptos:** `fusion_de_sensores` · `filtro_complementario` · `triad` · `metodo_de_proyeccion` · `mahony` · `deriva_del_rumbo` · `recentrar`

**Pregunta guía.** El giroscopio es rápido pero se desvía; la gravedad no se desvía pero no lo ve todo. ¿Cómo se juntan los dos?

**Ya está escrito**, como piloto del curso: la página `server/web/fusion.html` (con el servidor andando, `/fusion.html`), su [guion](capitulos/08-fusion.md) con lo que dejó el piloto, la cuenta en `server/web/fusionmath.js`, las pruebas en `tools/test_fusion.js` y el ejercicio en `docs/curso/ejercicios/cap08.js`.

**Preguntas que salen de ahí**

1. Si confío 100 % en el giroscopio, ¿qué pasa en un minuto? ¿Y si confío 100 % en la gravedad?
2. ¿Qué significa "tirar suavemente" hacia la gravedad? ¿Qué tan fuerte hay que tirar, y qué pasa si tiro demasiado?
3. ¿Por qué la fusión corrige la inclinación pero nunca el rumbo?
4. ¿Por qué el método de las páginas (el rumbo integrado) se pierde al caminar y la fusión no? (16° de mediana contra menos de 1°.)
5. Si la gravedad del reloj ya es una cuenta de Samsung que junta sensores, ¿estoy fusionando una fusión?
6. ¿Qué haría falta para que el rumbo no se fuera nunca? (Un magnetómetro, que este reloj no tiene.)
7. ¿Cuándo conviene recentrar, y cómo se hace sin que el usuario lo note?
8. ¿Por qué un error de unas décimas de °/s se ve en el cursor como centímetros?

**Cómo sería el capítulo**

- *Intuición visual:* dos antebrazos, el de verdad y el reconstruido, y un control Kp: en cero se va todo; muy alto, tiembla con cada movimiento brusco; en el medio queda pegado, salvo el rumbo, que se va igual.
- *La matemática mínima:* el filtro complementario, `θ ← θ + ω·Δt + k·Δt·(θ_medido − θ)`, con un error que se queda en `b/k`; Mahony, `e = ĝ_medido × ĝ_predicho` y `q ← q ⊗ exp((ω + Kp·e)·Δt/2)`; TRIAD con arriba y el antebrazo; la deriva del rumbo es `∫ b_vertical dt`.
- *El código:* la rama de fusión de `reconstruct` en `server/web/mocapmath.js` (10 líneas).
- *Experimento con datos reales:* el reloj quieto 60 s en la mesa: la inclinación de la fusión no se mueve y el rumbo se va con el sesgo; medir cuánto y compararlo con sesgo × tiempo.
- *Ejercicio que se comprueba:* implementar el filtro complementario para el ángulo de roll y comprobar que con un sesgo constante b el error se queda en b/k en vez de crecer.

## Capítulo 9 · El cuerpo en 3D

**Conceptos:** `esqueleto` · `cinematica_directa` · `trayectorias` · `ley_de_cosenos` · `cinematica_inversa` · `ruido_gaussiano` · `sintetizar_imu` · `prueba_con_verdad` · `aceleracion_de_un_punto_que_gira` · `limites_articulares` · `verosimilitud` · `filtro_de_particulas` · `remuestreo_de_particulas`

**Pregunta guía.** Con un solo reloj en la muñeca, ¿se puede saber dónde está todo el brazo?

**Preguntas que salen de ahí**

1. Si sé los ángulos del hombro y del codo, ¿cómo calculo dónde está la mano?
2. Y al revés: si sé dónde quiero la mano, ¿de cuántas maneras se puede doblar el codo para llegar?
3. ¿Qué leería el reloj en la muñeca de un muñeco que camina? ¿Cómo se fabrica un giroscopio de mentira?
4. Si reconstruyo el antebrazo con lecturas sintetizadas y cae encima del de verdad, ¿probé que funciona en el mundo real?
5. El reloj ve el antebrazo. ¿Qué se puede deducir del brazo de arriba, y qué no?
6. ¿De qué sirve saber que el codo no se dobla hacia atrás?
7. ¿Por qué seguir 400 brazos posibles a la vez en vez de uno solo?
8. Con la muñeca quieta, ¿por qué el filtro no sabe nada del codo y vuelve a la postura de reposo?

**Cómo sería el capítulo**

- *Intuición visual:* el stickman con el antebrazo de verdad (cian) y el reconstruido (coral); al lado, una nube de codos posibles que se aprieta cuando mueves el brazo y se abre cuando lo dejas quieto.
- *La matemática mínima:* cinemática directa, `codo = hombro + L₁·u` y `muñeca = codo + L₂·f`; la inversa con la ley de los cosenos, `x = (L₁² − L₂² + d²)/(2d)`; la síntesis, ω del giro relativo entre muestras y `a = (p₊ − 2p + p₋)/Δt² + g`; las partículas pesadas por `exp(−r²/2σ²)`, con r el residuo de la aceleración centrípeta del codo.
- *El código:* `ik` de `server/web/mocapmath.js` (9 líneas).
- *Experimento con datos reales:* cortar tus sesiones en tomas (`python tools/export_mocap.py`) y ver tu antebrazo en el stickman; en el avatar con el filtro, mover el brazo y dejarlo quieto para ver cómo la nube de codos se aprieta y se abre.
- *Ejercicio que se comprueba:* implementar la cinemática inversa de dos huesos y comprobar, con mil objetivos al azar, que el codo queda a L₁ del hombro y la muñeca a L₂ del codo, y que llega al objetivo cuando está a su alcance.

## Capítulo 10 · Gestos

**Conceptos:** `deteccion_de_picos` · `histeresis` · `periodo_refractario` · `umbral_adaptativo` · `dominancia_de_eje` · `clic_de_tornillo` · `toque` · `empujon` · `sacudida` · `permanencia` · `scroll_por_roll` · `tempo` · `aciertos_y_falsas_alarmas` · `auc`

**Pregunta guía.** ¿Cómo distingue el reloj un clic a propósito de todo lo demás que hace tu mano?

**Preguntas que salen de ahí**

1. ¿Qué tiene un giro de muñeca para hacer clic que no tenga un movimiento normal al apuntar? (700 °/s contra 117 °/s.)
2. Si pongo el umbral muy bajo, ¿qué pasa? ¿Y muy alto? ¿Con qué criterio lo elijo?
3. ¿Por qué hay dos umbrales, uno para empezar y otro para terminar?
4. ¿Por qué el pellizco de los dedos no sirve como clic a 100 Hz (12 de 20) y el giro sí?
5. Si una persona gira más fuerte que otra, ¿cómo se adapta el detector sin calibrar?
6. ¿Cómo sé que fue la muñeca y no todo el brazo?
7. ¿Cómo se mide un ritmo con giros de muñeca? ¿Por qué con la mediana y no con el promedio?
8. ¿Por qué el toque en la esfera se decide 250 ms tarde, y qué cuesta esa espera?

**Cómo sería el capítulo**

- *Intuición visual:* ω_x en vivo con las dos líneas del umbral, la de entrar y la de salir, y cada giro marcado al detectarse; un control del umbral y un contador de aciertos y falsas alarmas.
- *La matemática mínima:* un pico va desde que cruza el umbral de entrada hasta que baja del de salida (la mitad); la dominancia, `|ω_x| > 1.3·máx(|ω_y|, |ω_z|)`; el umbral, `máx(70, 0.35·mediana de los picos)`; el tempo, `60000 / mediana de los intervalos`; el AUC, `P(positivo > negativo)`.
- *El código:* `FlickDetector.update` de `server/web/flick.js` (27 líneas).
- *Experimento con datos reales:* correr el detector sobre tu sesión del dataset de gestos (`node tools/test_flick.js`) y contar giros por paso; barrer el umbral del pellizco (`tools/analyze_dataset.py`) y graficar aciertos contra falsas alarmas por minuto.
- *Ejercicio que se comprueba:* escribir un detector de picos con histéresis y periodo refractario, y comprobar que en una señal con 10 picos conocidos y ruido cuenta exactamente 10.

## Capítulo 11 · Frecuencia

**Ya está escrito:** su [texto](capitulos/11-frecuencia.md), con una animación por concepto; la página es el Sismógrafo (`server/web/sismo.html`), la cuenta está en `server/web/sismomath.js` y el ejercicio, en `tools/test_sismo.js`.

**Conceptos:** `suma_de_senos` · `correlacion` · `retraso_por_correlacion` · `numeros_complejos` · `dft` · `fuga_y_ventana` · `frecuencia_dominante` · `nyquist` · `funcion_de_transferencia` · `retraso_puro` · `remanente` · `ritmo_y_armonia` · `octavas`

**Pregunta guía.** ¿Se puede medir tu tiempo de reacción solo con una línea que se mueve y tu muñeca?

**Preguntas que salen de ahí**

1. Una línea hecha de varias ondas parece al azar. ¿Cómo puede ser imprevisible y a la vez repetirse cada 20 s?
2. ¿Cómo saco de tu movimiento cuánto hay de cada onda, si están todas mezcladas?
3. ¿Por qué cada onda tiene que dar un número entero de vueltas en la ventana, y qué pasa si no?
4. Si llegas tarde τ segundos, ¿por qué el error es chico en las ondas lentas y grande en las rápidas?
5. ¿Qué es tu "ruido" en este juego, y por qué no está en ninguna onda de la línea?
6. ¿Cuál es la onda más rápida que se ve con 100 muestras por segundo? Las más rápidas, ¿desaparecen o se disfrazan?
7. ¿Por qué un polirritmo de 3 contra 2, tocado muy rápido, suena como un acorde?
8. ¿Por qué subir una octava es multiplicar por 2, y no sumar algo?

**Cómo sería el capítulo**

- *Intuición visual:* la línea del sismógrafo descompuesta en sus ondas; cada onda es una flecha que gira, y tu respuesta, otra flecha más corta y atrasada: el cociente de las dos dice cuánto seguiste y con cuánto atraso.
- *La matemática mínima:* `r(t) = Σ a_k sen(2πkt/T + φ_k)`; `X(f) = (2/N) Σ x_n e^(−2πi f t_n)`; `H = Y/R`, con `|H|`, `−∠H/(2πf)` y `|1 − H| = 2|sen(πfτ)|` si solo llegas tarde; la correlación para el retraso; Nyquist, `f_s/2`; la octava ×2 y el semitono ×2^(1/12).
- *El código:* la DFT y H dentro de `analyze` en `server/web/sismomath.js` (16 líneas).
- *Experimento con datos reales:* jugar el sismógrafo en los tres niveles, viendo la línea y a ciegas, y comparar tu retraso global con el de cada onda.
- *Ejercicio que se comprueba:* fabricar una aguja que sigue la línea con 0.25 s exactos de retraso y comprobar que `analyze` devuelve τ = 0.25 y |1 − H| = 2|sen(π f τ)| en cada onda.

## Capítulo 12 · Aprender de datos

**Conceptos:** `rasgos` · `segmentar` · `estandarizar` · `minimos_cuadrados` · `r_cuadrado` · `validacion_cruzada` · `ventana_de_retardos` · `ridge` · `predecir_velocidad` · `descenso_por_gradiente` · `red_neuronal` · `parecido_de_forma` · `vecinos_cercanos` · `matriz_de_confusion` · `anova_f`

**Pregunta guía.** ¿Puede el reloj aprender a redibujar una letra que nunca vio?

**Preguntas que salen de ahí**

1. Si el reloj está en la muñeca y escribo con el dedo, ¿qué parte de la letra puede ver y cuál no?
2. ¿Por qué aprender la velocidad del dedo funciona mejor que aprender su posición?
3. ¿Qué es una prueba justa, y cómo me engaño si no la hago?
4. ¿Por qué la regresión ridge le ganó a la red neuronal? ¿Le ganaría con diez veces más datos?
5. ¿Qué número dice si dos letras se parecen? ¿Por qué no basta con comparar punto a punto?
6. Con 53 letras de una sola sesión, ¿cuánto creo en una diferencia de 0.74 contra 0.70?
7. ¿Cómo sé qué medidas de un gesto sirven para distinguirlo de otro?
8. Si un modelo acierta el 95 % con mis datos, ¿por qué podría fallar con otra persona?

**Cómo sería el capítulo**

- *Intuición visual:* cada letra real (cian) junto a la redibujada (coral), con su parecido de forma; un control λ que va de "copia el ruido" a "una raya quieta".
- *La matemática mínima:* mínimos cuadrados, `min ‖XW − V‖²`; ridge, `(XᵀX + λI)W = XᵀV`; R²; el parecido de forma como correlación de las formas centradas; validación cruzada por grupos de trazos; k vecinos; la F, variación entre grupos sobre variación dentro de cada grupo.
- *El código:* la clase `Ridge` de `tools/reconstruct_drawing.py` (13 líneas).
- *Experimento con datos reales:* `python tools/reconstruct_drawing.py` con tu grabación de letras, y repetirlo con ventanas de ±80, ±160 y ±240 ms para ver si la diferencia es más que ruido.
- *Ejercicio que se comprueba:* resolver ridge a mano para dos rasgos y comprobar contra `Ridge.fit`; ver que con λ → 0 da mínimos cuadrados y con λ muy grande da solo el promedio.

## Apéndice · Supuestos, falencias y cosas por mejorar

Lo que damos por hecho, lo que ya medimos que falla y lo que falta, cada cosa con el capítulo donde está la matemática para entenderla. Sale de `docs/por-mejorar.md`, la lista de trabajo del proyecto; la segunda tabla son supuestos que aparecieron al leer el código y no estaban en esa lista.

### Supuestos

| # | Lo que damos por hecho | Dónde se explica |
|---|---|---|
| 1 | El reloj va puesto "normal", con la pantalla sobre el dorso de la muñeca: en la izquierda el antebrazo es +x y en la derecha −x. Puesto al revés o girado, arriba sale abajo. | [cap. 6](#capítulo-6--del-reloj-al-antebrazo-roll-yaw-y-pitch) · `antebrazo_eje_x` |
| 2 | El antebrazo es rígido y el reloj no se mueve sobre la piel: con la correa floja, el reloj gira distinto que el brazo y lo leemos como movimiento. | [cap. 9](#capítulo-9--el-cuerpo-en-3d) · `esqueleto` |
| 3 | Apuntas con el antebrazo, no con el dedo: el reloj no ve los dedos. | [cap. 6](#capítulo-6--del-reloj-al-antebrazo-roll-yaw-y-pitch) · `antebrazo_eje_x`; [cap. 12](#capítulo-12--aprender-de-datos) · `predecir_velocidad` |
| 4 | La gravedad del reloj es confiable, aunque sea una cuenta interna de Samsung que no controlamos ni podemos auditar. | [cap. 1](#capítulo-1--qué-es-un-sensor) · `sensor_gravedad`; [cap. 8](#capítulo-8--fusión-de-sensores-y-por-qué-el-rumbo-se-va) · `fusion_de_sensores` |
| 5 | El sesgo del giroscopio es casi constante y se aprende con la mano quieta (\|ω\| < 2 °/s). | [cap. 1](#capítulo-1--qué-es-un-sensor) · `aprender_sesgo` |
| 6 | El cursor es lineal en el ángulo (D·θ); el rayo real va como D·tan θ. A la distancia de un monitor la diferencia es chica: 3 cm a 13° y 2.4 m, en la simulación. | [cap. 7](#capítulo-7--de-3d-a-2d-el-cursor) · `rayo_tangente` |
| 7 | Los tiempos del reloj y de la laptop están alineados y el retraso de la red es estable. | [cap. 0](#capítulo-0--un-número-que-cambia) · `alinear_relojes`, `latencia` |
| 8 | El cuerpo tiene medidas fijas: brazo de 0.29 m y antebrazo de 0.27 m en el mocap, 0.30 y 0.25 m en el filtro del codo. En el mocap el codo no se mueve cuando reproducimos tus grabaciones. | [cap. 9](#capítulo-9--el-cuerpo-en-3d) · `esqueleto`, `filtro_de_particulas` |
| 9 | Una persona, un reloj y una laptop, en la misma red Wi-Fi. | [cap. 0](#capítulo-0--un-número-que-cambia) · `agrupar_muestras` |

### Supuestos que aparecieron en el código

| # | Lo que el código da por hecho sin decirlo | Dónde se explica |
|---|---|---|
| 10 | En las páginas (`wrist.js`), todo giro de menos de 2 °/s se aprende como sesgo: un giro lento y parejo hecho a propósito se va borrando. El ratón aéreo lo evita (pide pico a pico < 1 °/s y una mediana chica). | [cap. 1](#capítulo-1--qué-es-un-sensor) · `aprender_sesgo` |
| 11 | Con el antebrazo a menos de unos 17° de la vertical (\|g·f\| > 0.95: la mano muy arriba o el brazo colgando), las páginas apagan el pitch y achican el yaw. | [cap. 5](#capítulo-5--rotar) · `singularidad`; [cap. 6](#capítulo-6--del-reloj-al-antebrazo-roll-yaw-y-pitch) · `yaw`, `pitch` |
| 12 | La misma cuenta está tres veces y no igual: las páginas cortan el giro a cero bajo 0.6 °/s (con un salto), el ratón aéreo resta la zona muerta (sin salto) y el avatar toma el yaw como ω·arriba, sin quitarle la parte de roll. | [cap. 6](#capítulo-6--del-reloj-al-antebrazo-roll-yaw-y-pitch) · `yaw`; [cap. 7](#capítulo-7--de-3d-a-2d-el-cursor) · `zona_muerta` |
| 13 | En las páginas, un hueco de más de 100 ms entre muestras se integra como si fueran 10 ms: lo que giraste durante una pausa del Wi-Fi se pierde. | [cap. 0](#capítulo-0--un-número-que-cambia) · `marca_de_tiempo`; [cap. 3](#capítulo-3--derivar-e-integrar-con-números) · `integral_discreta` |
| 14 | `reconstruct_drawing.py` toma como sesgo la mediana del giroscopio de toda la grabación: supone que casi todo el tiempo la muñeca no gira, o gira parejo para los dos lados. | [cap. 1](#capítulo-1--qué-es-un-sensor) · `aprender_sesgo` |
| 15 | El filtro del codo supone el torso quieto y el hombro fijo en un punto. | [cap. 9](#capítulo-9--el-cuerpo-en-3d) · `filtro_de_particulas` |
| 16 | La distancia a la pantalla no se mide: la ganancia del ratón aéreo (de 12 a 30 px por grado) la supone. | [cap. 7](#capítulo-7--de-3d-a-2d-el-cursor) · `ganancia` |
| 17 | Los umbrales de los gestos salen de una persona y una sesión: el tornillo pide 200 °/s porque al apuntar los giros accidentales nunca pasaron de 117 °/s. | [cap. 10](#capítulo-10--gestos) · `clic_de_tornillo`, `umbral_adaptativo` |
| 18 | El juego toma la mira 120 ms antes del empujón: supone que empujar tarda eso en empezar a girar la muñeca. | [cap. 10](#capítulo-10--gestos) · `empujon` |

### Falencias conocidas

| # | Lo que ya medimos que falla | Dónde se explica |
|---|---|---|
| 1 | El rumbo se va: con el sesgo de un giroscopio real (unas décimas de °/s) el cursor se desvía unos 12 cm en 10 s a 2.4 m de la pantalla. | [cap. 3](#capítulo-3--derivar-e-integrar-con-números) · `error_acumulado`; [cap. 8](#capítulo-8--fusión-de-sensores-y-por-qué-el-rumbo-se-va) · `deriva_del_rumbo` |
| 2 | Con el brazo colgando, la proyección se rompe: ∫yaw se equivoca 16° de mediana y hasta 79° caminando. El mocap usa Mahony y queda bajo 1°; el ratón aéreo y Dibuja todavía usan la proyección. | [cap. 5](#capítulo-5--rotar) · `singularidad`; [cap. 8](#capítulo-8--fusión-de-sensores-y-por-qué-el-rumbo-se-va) · `metodo_de_proyeccion`, `mahony` |
| 3 | El pellizco no sirve como clic a 100 Hz: 12 de 20 en las pruebas. El clic de tornillo (~700 °/s) sí se distingue. | [cap. 10](#capítulo-10--gestos) · `aciertos_y_falsas_alarmas`, `clic_de_tornillo`; [cap. 11](#capítulo-11--frecuencia) · `nyquist` |
| 4 | El muestreo no es tan alto como parece: a 5 ms llegan ~200 muestras por segundo, pero solo ~115 son lecturas nuevas; con la pantalla apagada baja a ~45 Hz o llega en ráfagas. | [cap. 0](#capítulo-0--un-número-que-cambia) · `muestreo`, `lecturas_nuevas` |
| 5 | El servicio de sensores del reloj se traba si se corta mal ("Listener is already added") y hay que reiniciar el reloj. | Práctico, no matemático ([cap. 1](#capítulo-1--qué-es-un-sensor)). |
| 6 | Una sola conexión de depuración a la vez: el grabador y el puente no pueden correr juntos. | Práctico ([cap. 0](#capítulo-0--un-número-que-cambia)). |
| 7 | El botón de inicio es el de encendido: mantenerlo abre el asistente o reinicia el reloj. No se usa. | Práctico. |
| 8 | La calibración medida no está aplicada: la vertical necesita ×1.3 de ganancia y los ejes se cruzan a 75°, no a 90°. | [cap. 7](#capítulo-7--de-3d-a-2d-el-cursor) · `mapa_lineal_2x2`; [cap. 12](#capítulo-12--aprender-de-datos) · `minimos_cuadrados` |
| 9 | Las letras reconstruidas se parecen 0.74 en letras que el modelo nunca vio: el reloj ve la muñeca, no los dedos. | [cap. 12](#capítulo-12--aprender-de-datos) · `parecido_de_forma`, `predecir_velocidad` |
| 10 | Tus grabaciones en el mocap no tienen verdad contra la cual comparar, y su rumbo inicial lo suponemos hacia el frente. | [cap. 4](#capítulo-4--la-gravedad-dice-dónde-es-arriba) · `rumbo`; [cap. 9](#capítulo-9--el-cuerpo-en-3d) · `prueba_con_verdad` |
| 11 | Las pruebas del mocap usan datos sintéticos de nuestro propio modelo: comprueban la matemática, no el mundo real. | [cap. 9](#capítulo-9--el-cuerpo-en-3d) · `sintetizar_imu`, `prueba_con_verdad` |
| 12 | Dependemos de una puerta trasera: Samsung ya no da certificados para apps de reloj y leemos los sensores con `sensorctl` por la conexión de depuración. | Práctico. |
| 13 | Transmitir sin parar gasta la batería en un par de horas. | Práctico ([cap. 0](#capítulo-0--un-número-que-cambia): más muestras, más gasto). |

### Por mejorar: la parte de matemática y sensores

| Qué | Dónde se explica |
|---|---|
| Fusión en todas partes: llevar el filtro de Mahony del mocap al ratón aéreo y a Dibuja. | [cap. 8](#capítulo-8--fusión-de-sensores-y-por-qué-el-rumbo-se-va) · `mahony` |
| Aprender el sesgo mejor (un filtro de Kalman) y recentrar solo, suave, cuando la mano descansa. El filtro de Kalman todavía no está en el curso: sería el paso siguiente del capítulo 8. | [cap. 1](#capítulo-1--qué-es-un-sensor) · `aprender_sesgo`; [cap. 8](#capítulo-8--fusión-de-sensores-y-por-qué-el-rumbo-se-va) · `recentrar` |
| Aplicar la calibración (la matriz 2×2) y un asistente de "sigue el punto". | [cap. 7](#capítulo-7--de-3d-a-2d-el-cursor) · `mapa_lineal_2x2`; [cap. 12](#capítulo-12--aprender-de-datos) · `minimos_cuadrados` |
| Mapeo con tan θ, opcional, para pantallas grandes o proyectores. | [cap. 7](#capítulo-7--de-3d-a-2d-el-cursor) · `rayo_tangente` |
| Validar contra la realidad: video del teléfono con estimación de pose, o el ratón y el trackpad como maestros (ya los grabamos). | [cap. 9](#capítulo-9--el-cuerpo-en-3d) · `prueba_con_verdad`; [cap. 12](#capítulo-12--aprender-de-datos) · `validacion_cruzada` |
| Magnetómetro, si el reloj lo entrega, para frenar la deriva del rumbo. | [cap. 8](#capítulo-8--fusión-de-sensores-y-por-qué-el-rumbo-se-va) · `deriva_del_rumbo` |
| Posición, no solo orientación: integrar el acelerómetro con correcciones de velocidad cero. | [cap. 3](#capítulo-3--derivar-e-integrar-con-números) · `doble_integral_zupt` |
| Una sola extracción de roll, yaw y pitch para el ratón aéreo, las páginas y el avatar (hoy son tres: el supuesto 12). | [cap. 6](#capítulo-6--del-reloj-al-antebrazo-roll-yaw-y-pitch) · `yaw` |

El resto de la lista (publicar la app, partir `air_mouse.py`, comentarios en un solo idioma, la experiencia de las páginas) es trabajo de la app, no del curso.
