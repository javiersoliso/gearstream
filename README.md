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
phone/start.sh      arranque en Termux (servidor + puente en el teléfono)
```
