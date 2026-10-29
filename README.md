# GearStream

Streaming en tiempo real de **todos los sensores** de un Samsung Galaxy Watch (1ª gen, 46 mm, Tizen) a la laptop, con dashboard en vivo y grabación a CSV.

```
Galaxy Watch (app Tizen web)  --WebSocket/Wi-Fi-->  laptop: server/server.py  --->  dashboard en el navegador
  watch-app/                    ws://IP:8765/watch     graba recordings/<sesión>/*.csv    http://localhost:8765
```

## Qué se transmite

La app del reloj **no tiene una lista fija**: al arrancar pregunta a Tizen qué sensores existen (`tizen.sensorservice.getAvailableSensors()`) y los abre todos a 100 Hz (lo máximo que permite Tizen). Además:

| Fuente | API | Notas |
|---|---|---|
| ACCELERATION, GYROSCOPE, GRAVITY, LINEAR_ACCELERATION, GYROSCOPE_ROTATION_VECTOR, *_UNCALIBRATED, MAGNETIC… | `tizen.sensorservice` | lo que el reloj reporte como disponible |
| HRM_RAW | `tizen.sensorservice` | señal PPG cruda (LED verde) |
| PRESSURE, LIGHT | `tizen.sensorservice` | barómetro y luz ambiental, 10 Hz |
| HRM, PEDOMETER, WRIST_UP, SLEEP_MONITOR, SLEEP_DETECTOR, STRESS_MONITOR | `tizen.humanactivitymonitor` | pulso (lpm + intervalo RR), pasos, gestos… |
| GPS | `navigator.geolocation` | necesita cielo abierto |
| ORIENTATION | `deviceorientation` | alpha/beta/gamma ya fusionados |
| BATTERY | `tizen.systeminfo` | |
| BEZEL | evento `rotarydetent` | giros del bisel |

Las fuentes que el reloj no soporte aparecen en el dashboard en "No disponibles", con el error que devolvió Tizen.

## 1. Probarlo sin el reloj (2 minutos)

```bash
pip install -r requirements.txt
```
```bash
python server/server.py
```
En otra terminal:
```bash
python tools/fake_watch.py
```
Abre http://localhost:8765. El simulador manda datos con el mismo protocolo que el reloj.

## Modo sin app (lo que funciona hoy)

Samsung ya no emite certificados para relojes Tizen: su servidor solo da certificados de TV (VD), y el reloj los rechaza con *"Invalid certificate chain"*. Mientras tanto, `tools/sdb_bridge.py` lee los sensores con `sensorctl`, una herramienta interna del reloj, por la conexión de depuración, sin instalar nada:

```bash
python tools/sdb_bridge.py
```
Sin `--device` busca el reloj en la red local (puerto 26101); con `--device <ip>` va directo.

| Sí (100 Hz) | Sí (10 Hz) | No |
|---|---|---|
| acelerómetro, giroscopio, gravedad, aceleración lineal | barómetro (+ altitud y temperatura), luz | pulso y PPG (permiso denegado al shell), magnetómetro (no existe) |

Requisitos: depuración activada y Bluetooth del teléfono apagado. El puente habla el protocolo sdb directo desde Python ([tools/sdb_client.py](tools/sdb_client.py)), así que no necesita `sdb.exe`. Usa la llave `~/.tizen/sdbkey` si existe (ya autorizada por el reloj); si no, genera una propia y el reloj pide permiso una vez. El pulso se lee del log de Samsung Health mientras mide (~1 Hz).

### En el teléfono, sin laptop (Termux)

1. Instala Termux desde F-Droid y en Termux corre: `pkg install -y python unzip` y luego `pip install websockets`.
2. En la laptop genera el paquete una vez (`python tools/build_phone_zip.py`) y, con el servidor corriendo y el teléfono en la misma Wi-Fi, descárgalo en Termux: `curl -O http://<IP-laptop>:8765/gearstream-phone.zip && unzip -o gearstream-phone.zip`.
3. Arranca: `bash gearstream/phone/start.sh` (busca el reloj solo; o `bash gearstream/phone/start.sh <IP-del-reloj>`) y abre `http://localhost:8765` en el navegador del teléfono.

Sin router: prende el punto de acceso del teléfono (banda 2.4 GHz, WPA2: el SM-R800 no ve 5 GHz ni WPA3) y conecta el reloj a esa red. Ojo: el hotspot de un teléfono **aísla a sus clientes**, así que ahí solo el propio teléfono puede leer el reloj; una laptop conectada al mismo hotspot no lo ve. Para medir la red: `python tools/batch_test.py --device <ip-del-reloj>` compara los modos de agrupamiento.

### Medir el retraso

Tres puntos del camino reportan cuánto tarda la muestra más reciente en llegar (tiempo desde que el reloj la generó; el reloj de cada sensor se ancla a la entrega más rápida vista, así que el número es relativo al mejor caso):
- **Puente** (`retraso N ms · ida y vuelta A-B ms, C muestras/paquete`): reloj → Wi-Fi → sdb → Python. El protocolo sdb manda **un paquete por sensor y espera nuestro acuse antes del siguiente**, y el reloj no junta muestras por su cuenta (medido: 0.8 muestras/paquete, y `sensorctl --batch_latency` no cambia nada). Por eso la velocidad máxima es 1 muestra por ida y vuelta: ~10 ms en casa alcanza para 100 Hz; en el hotspot de un teléfono (~60 ms) solo pasan ~17/s y el resto se acumula en el reloj (ese es el "lag" del teléfono). La solución es `--batch 10`: el reloj agrupa 10 muestras por paquete con `awk` (medido: 100 Hz, 10 muestras/paquete, hasta 100 ms más de retraso). `phone/start.sh` ya lo usa. Menos sensores = menos paquetes: `--sensors accelerometer,gyroscope`.
- **Servidor** (`retraso N ms (puente→servidor M ms)`): lo anterior + el lote del puente (`--flush-ms`, 20 ms por defecto; 10 para menos retraso). El segundo número es solo el tramo puente → servidor, medido con el mismo reloj.
- **Dashboard** (cabecera): `retraso` = todo el camino; `desde el puente` = solo puente → servidor → navegador (exacto cuando el navegador corre en el mismo equipo que el puente: laptop o teléfono); `ráfaga máx` = la mayor pausa entre lotes en el último segundo y el lote más grande (ráfagas grandes = la red o el navegador se atoran a ratos).

Lo que más pesa en un teléfono es dibujar las gráficas (rasterizar los trazos), no Python: por eso el dashboard limita la densidad a 1.5×, dibuja solo las tarjetas visibles y solo cuando llegan datos (≤30 veces/s).

## 2. Preparar el reloj

1. **Misma red Wi-Fi** que la laptop. En el reloj: *Ajustes → Conexiones → Wi-Fi* → conéctate a tu red.
2. **Modo desarrollador**: *Ajustes → Acerca del reloj → Software* → toca **Versión de software** 5 veces. Luego activa *Ajustes → Acerca del reloj → Depuración*.
3. Anota la **IP del reloj** (*Wi-Fi → tu red → detalles*).
4. En Windows, cuando arranques `server.py` por primera vez, **permite Python en el firewall** para redes privadas (y que tu red esté marcada como *Privada*).

> **Ojo con Bluetooth:** si el reloj está enlazado al teléfono, Tizen manda el tráfico por el Bluetooth del teléfono y puede no llegar a tu laptop. Si no conecta, pon el Wi-Fi del reloj en *Siempre activo* o apaga el Bluetooth del teléfono mientras transmites.

## 3. Instalar la app en el reloj

Necesitas **Tizen Studio** (basta con la versión CLI) y, en su *Package Manager*, las extensiones **Samsung Certificate Extension** y **Wearable Extension**.

1. **Certificado Samsung** (obligatorio en relojes comerciales): *Tools → Certificate Manager → + → Samsung → Mobile/Wearable*, inicia sesión con tu cuenta Samsung y deja que añada el DUID del reloj (el reloj tiene que estar conectado por `sdb` en ese momento). Llámalo, por ejemplo, `gearstream`.
   > Samsung ha ido retirando partes de este flujo y hay reportes de errores en sus foros. Si falla aquí, avísame y buscamos alternativa.
2. **Conectar el reloj**:
   ```bash
   sdb connect 192.168.0.XX
   ```
   Acepta la clave RSA que aparece en el reloj y comprueba con `sdb devices`.
3. **IP del servidor**: edita `SERVER_URL` en [watch-app/js/config.js](watch-app/js/config.js) (`server.py` imprime la URL correcta al arrancar). También se puede cambiar después tocando la URL en la pantalla del reloj.
4. **Empaquetar e instalar**:
   ```bash
   tizen package -t wgt -s gearstream -- watch-app
   ```
   ```bash
   tizen install -n GearStream.wgt -- watch-app
   ```
   (Otra opción: en Tizen Studio, *File → Import → Tizen → Tizen Project*, elige `watch-app` y *Run As → Tizen Web Application*.)
5. Abre **GearStream** en el reloj, toca **Iniciar** y acepta los permisos (sensores de salud y ubicación).

En el reloj:
- El punto verde indica conexión con la laptop; la lista muestra cada fuente (verde = datos, ámbar = esperando, rojo = error).
- El **bisel** desplaza la lista.
- **Atrás** mientras transmite solo oculta la app (el stream sigue). Para parar, toca **Detener**.
- Por defecto mantiene la **pantalla encendida** (`KEEP_SCREEN_ON`), porque con la pantalla apagada Tizen puede pausar sensores. Pantalla + 100 Hz + Wi-Fi gastan mucha batería; mejor transmite con el reloj cargado o en sesiones cortas.

## Datos grabados

Cada sesión crea `recordings/AAAAMMDD-HHMMSS/`:
- `ACCELERATION.csv`, `HRM_RAW.csv`, …: una fila por muestra. `t_watch_ms` es el reloj del Galaxy Watch y `t_recv_ms` el de la laptop, ambos en ms Unix.
- `meta.jsonl`: info del dispositivo, sensores disponibles, estado de cada fuente y specs del hardware (rango, resolución, intervalo mínimo).

Usa `--no-record` para no grabar y `--out <carpeta>` para grabar en otra parte.

### Privacidad

Las grabaciones son datos personales (pulso, movimiento) y **nunca salen de tu máquina**: `recordings/` está en `.gitignore`. Las llaves tampoco viven en el repositorio: la llave sdb está en `~/.tizen/sdbkey` o `~/.gearstream/sdbkey.json`, y el perfil del ratón aéreo en `~/.gearstream/airmouse.json`. Si quieres compartir una grabación de ejemplo, cópiala a otra carpeta a propósito.

## Lanzador (sin comandos)

```bash
python tools/launcher.py
```

Una ventana que muestra tu Wi-Fi y la IP de la laptop, busca el reloj en la red (o escribes su IP: en el hotspot del teléfono la búsqueda a veces no lo ve), arranca el servidor y el puente, y abre con un botón el juego, el avatar, el dashboard, la calibración o el ratón aéreo. Mide la red con ping y agrupa muestras solo si hace falta. Para el puente y el ratón con Ctrl+Break, para que limpien el reloj al salir.

## Sismógrafo: sigue la línea

`http://localhost:8765/sismo.html` (o el botón Sismógrafo del lanzador). Una línea amarilla viene corriendo por el papel y tu muñeca mueve la aguja: mantenla encima durante 20 segundos. Botón atrás del reloj (o Espacio) para empezar, el bisel cambia el nivel (tranquilo, normal, sismo), E el giro que mueve la aguja (inclinar, girar o atornillar) y V si ves venir la línea o vas a ciegas.

Es una tarea de seguimiento como las que McRuer usaba en los años 60 para medir pilotos. La línea es una suma de senos r(t) = Σ a_k sin(2π k t / T + φ_k) con fases al azar: parece imprevisible, pero cada seno da un número entero de vueltas en T = 20 s, así que al final la transformada de Fourier separa tu respuesta onda por onda. Para cada frecuencia, H = Y/R dice cuánto de esa onda seguiste (|H|), con cuánto retraso (−∠H / 2πf) y cuánto error te quedó (|1 − H|). Si solo te fallara el tiempo de reacción τ, ese error sería 2·|sin(π f τ)|, y la tarjeta del final dibuja esa curva junto a tus barras. También da tu retraso global (la correlación de tu aguja con la línea desplazada) y tu "ruido": lo que moviste que no estaba en ninguna onda. Matemática en `server/web/sismomath.js`, probada en `tools/test_sismo.js`.

## Muñeca izquierda o derecha

En la muñeca izquierda el antebrazo es el +x del reloj; en la derecha, con el reloj puesto igual (botones hacia el codo), es −x, y sin avisar arriba sale abajo y atornillar sale desatornillar. Dibuja y el Sismógrafo tienen un botón (o la tecla M) para elegir la muñeca; la elección se guarda en el navegador y la usan también los globos, el tornillo y el avatar (`server/web/wrist.js`). Para el ratón aéreo: `--forearm -x`.

## Dibuja en 1D, 2D y 3D

`http://localhost:8765/dibuja.html`. Mantén el botón atrás del reloj para bajar el lápiz y gira el bisel para cambiar de color. **2D**: apuntas con la muñeca y dibujas en un lienzo (la "sombra" de un puntero: lo que mejor reconstruye tus trazos en los datos). **3D**: la muñeca da la dirección y girar el antebrazo como atornillando da la profundidad (horario aleja); con O orbitas el dibujo. **Modo creativo** (F): vuelas libre como en Minecraft creativo (WASD, E/Q sube y baja, ratón para mirar) y el lápiz va delante de ti. I invierte el sentido de la profundidad. **1D**: un sismógrafo, la muñeca mueve la aguja y el papel corre solo; E elige el giro (inclinar, girar o atornillar). M: muñeca izquierda o derecha. R recentra, Z deshace, S guarda la imagen.

## Juego: Revienta globos

`http://localhost:8765/game.html` (o el botón Juego del lanzador). Apuntas con la muñeca y **empujas la mano hacia la pantalla** para lanzar un dardo: la fuerza del empujón es la profundidad, suave llega a los globos cercanos y fuerte a los lejanos, que valen el triple. El empujón es la aceleración a lo largo del antebrazo (eje x del reloj, sin gravedad); la escala se adapta a tu fuerza. Botón atrás del reloj: empezar y recentrar la mira. Sin reloj se juega con el ratón y las teclas 1, 2 y 3. Apaga el ratón aéreo mientras juegas.

## Tornillo y tempo

`http://localhost:8765/tempo.html`. Gira la muñeca como con un destornillador: el antebrazo es el eje x del reloj, así que el giro es ω_x del giroscopio, y su signo es el sentido (mirando del codo a los dedos, horario = atornillar). Un giro fuerte, de más de 200 °/s, avanza o saca el tornillo una vuelta entera: apuntando con el ratón, los giros accidentales del dataset nunca pasaron de 117 °/s. Un ritmo constante de giros da el tempo en giros por minuto; con el botón atrás o Espacio se fija y suena un metrónomo. Detector en `server/web/flick.js`, probado con el dataset en `tools/test_flick.js`.

## Dibujar con el trackpad (el dedo como esfero)

```bash
python tools/draw_recorder.py --device <IP-del-reloj>
```

Lee el trackpad de precisión de Windows directo por Raw Input (`tools/touchpad.py`: cada dedo con su posición en milímetros, si toca o no y el Scan Time del propio trackpad) y el reloj directo por sdb a su máxima resolución (acelerómetro y giroscopio a 200 muestras/s, unas 120 lecturas nuevas; gravedad a 200). Escribes qué vas a dibujar, dibujas con el índice de la mano del reloj y queda todo en `recordings/dibujo-*/` con un reloj de tiempo común: el trackpad es la verdad del trazo para entrenar al reloj a reconstruirlo. Cierra el puente antes: el reloj acepta una sola conexión.

## Lo que el reloj ve de tu escritura

![Cada letra: el dedo en el trackpad (cian) y lo que reconstruye el reloj (coral)](docs/media/letras-forma.gif)

Dos abecedarios escritos con el índice en el trackpad mientras el reloj grababa a 200 muestras/s. Cian es el trazo real (el trackpad, a 143 lecturas/s y 0.03 mm); coral es lo que reconstruye el reloj con **una sola calibración lineal** para toda la sesión: los ángulos de muñeca integrados (la "sombra" de un puntero) más la aceleración integrada dos veces con velocidad cero al apoyar y al levantar. Cada trazo coral arranca donde arranca el real (el reloj ve la forma, no dónde se apoya el dedo) y en este GIF cada letra se escala con un solo número para comparar la forma; la versión sin retoques es [letras-global.gif](docs/media/letras-global.gif). El número junto a cada letra es el parecido de forma (correlación; 1 = idéntica).

- Parecido de forma mediano **0.69**; las mejores, S 0.96, v 0.90, j 0.89, x 0.87, G 0.86. Las peores salen giradas: U, N, W.
- Lo que decide la calidad no es la velocidad ni la aceleración del dedo (correlación −0.04 y +0.01) sino **cuánto gira la muñeca** (+0.22), que crece con el tamaño del trazo. Las letras pequeñas se escriben con los dedos y el reloj, en la muñeca, casi no las ve; un círculo grande sí.
- Apoyar y levantar el dedo casi no deja huella en el reloj (AUC 0.56 y 0.58): el "lápiz abajo" lo da el trackpad.
- Calibración del giro en postura de escritura: 5.3 mm de trazo por grado de yaw y 6.9 por grado de pitch, con los ejes cruzados (75° entre sí): la muñeca necesita 1.3 veces más ganancia en vertical.

### Redibujar con el reloj, letras que el modelo nunca vio

![Letras redibujadas por un modelo entrenado con el otro abecedario](docs/media/letras-forma-aprendido.gif)

En vez de una sola calibración, un modelo aprende a traducir lo que siente el reloj en cada instante (giros de muñeca, giro crudo, aceleración lineal y postura, en una ventana de ±240 ms) a la **velocidad** del dedo, y la integra para redibujar el trazo. Prueba justa: las mayúsculas las redibuja un modelo entrenado sin mayúsculas, y las minúsculas uno entrenado sin minúsculas. Se le da cuándo apoya y levanta el dedo (el reloj no lo ve) y dónde empieza cada trazo; la forma la pone el reloj.

| método (letras nunca vistas) | parecido de forma mediano | letras por encima de 0.8 | largo reconstruido / real |
|---|---|---|---|
| una calibración lineal de posición | 0.60 | 12 / 53 | 0.36 |
| regresión ridge sobre la velocidad | **0.74** | **19 / 53** | 0.58 |
| red neuronal pequeña (numpy) | 0.60 | 14 / 53 | 0.70 |

Todo con numpy: la regresión es un sistema lineal, (XᵀX + λI)·W = XᵀV, y la red es una capa oculta tanh entrenada con Adam a mano. Variantes probadas (±80 / ±160 / ±240 ms, ridge sola o junto a la red) quedan entre 0.67 y 0.75: con 53 letras de una sola sesión, esas diferencias son ruido. Para avanzar de verdad hacen falta más datos, no un modelo más grande. `tools/reconstruct_drawing.py` entrena y evalúa; `render_letters_gif.py --fuente aprendido` dibuja el GIF.

Herramientas: `tools/draw_recorder.py` (grabar), `tools/analyze_drawing.py` (números), `tools/render_letters_gif.py` (este GIF, con `letters.json` diciendo qué trazos forman cada letra).

## Gestos nuevos

`tools/dataset_capture.py` (consola) o `http://localhost:8765/dataset.html` graban un dataset guiado de 13 gestos con etiquetas; `tools/analyze_dataset.py recordings/<sesión>` dice cuáles se distinguen. `tools/guided_capture.py` graba un gesto guiado por pitidos y luego movimiento normal; `tools/analyze_gesture.py` dice si el gesto se distingue. Con `--device IP` lee el acelerómetro directo a 200 Hz (con la pantalla del reloj encendida: apagada, el reloj baja los sensores a unas 45 muestras por segundo).

## Ratón aéreo (el reloj como cursor)

`tools/air_mouse.py` mueve el cursor de Windows con el giroscopio (apuntas con la muñeca), con clic y scroll desde el propio reloj:

```bash
python tools/sdb_bridge.py --flush-ms 10 --sensors accelerometer,gyroscope,gravity
python tools/air_mouse.py
```

- Arranca con el brazo relajado unos segundos (calibra el reposo) y luego levanta la mano y apunta.
- **Clic:** botón *atrás* del reloj (mantenerlo arrastra). Alternativa: un toque seco en la esfera (`--click tap`).
- **Scroll:** el bisel, muesca a muesca (`--scroll roll` usa el giro del antebrazo si el puente no manda el bisel).
- **Seguridad:** mover el ratón físico pausa el aéreo; la tecla Pausa lo pausa/reanuda; dejar el cursor 1.5 s en la esquina superior izquierda lo apaga.
- **Calibración:** abre `http://localhost:8765/calibrate.html` con el ratón corriendo. Ajusta sensibilidad (incluida la vertical, `gain_y`), zona muerta y suavizado en vivo, haz la prueba de objetivos (sugiere el ajuste por eje), la de clic y la de scroll (verifica el sentido del bisel), y graba gestos de 3 s. El perfil se guarda en `~/.gearstream/airmouse.json`.
- Pruebas: `python -I tools/test_air_mouse.py` y `python -I tools/test_sdb_bridge.py`. `--replay recordings/<sesión>` repite una grabación sin tocar el cursor (`--dry-run`).


## Protocolo (por si haces otro cliente)

JSON por WebSocket, del reloj al servidor (y reenviado tal cual al dashboard por `/ui`):

```json
{"type":"hello","app":"1.0.0","device":{"model_name":"SM-R800",...},"available":["ACCELERATION",...]}
{"type":"status","source":"HRM_RAW","state":"on|waiting|error|unsupported","detail":"...","hw":{...}}
{"type":"data","samples":[["ACCELERATION",1729800000123,{"x":0.1,"y":9.8,"z":0.3}], ...]}
```
El reloj manda un lote cada 50 ms. Si se cae la conexión, guarda hasta 20 000 muestras y reconecta solo.

## Siguiente paso: el teléfono

- **Ya funciona hoy:** abre `http://<IP-laptop>:8765` en el navegador del teléfono; el dashboard se adapta a pantalla chica.
- **Teléfono como receptor (sin laptop):** una app Android que levante un servidor WebSocket en `:8765/watch` con este mismo protocolo. El reloj no cambia: basta con apuntar `SERVER_URL` a la IP del teléfono (misma Wi-Fi o hotspot del teléfono).
- **Solo Bluetooth (sin Wi-Fi):** requiere Samsung Accessory SDK (SAP) en ambos lados. Es más trabajo y el SDK ya no recibe mantenimiento.

## Estructura

```
watch-app/          app Tizen web (config.xml, index.html, js/main.js, js/config.js)
server/server.py    servidor WebSocket + HTTP + grabación (solo depende de `websockets`)
server/web/         dashboard (JS puro + canvas, sin dependencias)
tools/fake_watch.py reloj simulado
tools/sdb_client.py cliente sdb (protocolo de depuración de Tizen) en Python puro
tools/sdb_bridge.py puente: sensores, pulso, bisel y botones del reloj → servidor
tools/air_mouse.py  ratón aéreo (cursor de Windows con el reloj) + canal de ajuste en vivo
tools/batch_test.py mide la red entre el puente y el reloj
server/web/calibrate.html  página de calibración del ratón aéreo
server/web/avatar.html     avatar 3D del brazo (orbital, POV y plano del brazo) a partir de gravedad + giroscopio
server/web/armfilter.js    filtro de partículas del codo: aceleración del reloj + límites del brazo (prueba: node tools/test_armfilter.js)
phone/start.sh      arranque en Termux (servidor + puente en el teléfono)
tools/launcher.py   ventana para conectar el reloj y abrir cada modo
server/web/game.html  juego Revienta globos (apuntar con la muñeca, empujar hacia la pantalla)
```
