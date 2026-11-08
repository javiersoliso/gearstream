# Supuestos, falencias y cosas por mejorar

Lo que damos por hecho, lo que sabemos que falla (con números cuando los tenemos) y lo que falta. Es la lista
honesta del proyecto: sirve de apéndice al curso y de lista de trabajo para la app.

## Supuestos: lo que damos por hecho

1. **El reloj va puesto "normal"**: pantalla sobre el dorso de la muñeca. En la izquierda el antebrazo es el +x
   del reloj; en la derecha, con el reloj igual, es −x (`server/web/wrist.js`). Si te pones el reloj al revés o
   girado, arriba sale abajo.
2. **El antebrazo es rígido y el reloj no se mueve sobre la piel.** Si la correa está floja, el reloj gira
   distinto que el brazo y lo leemos como movimiento.
3. **Apuntas con el antebrazo, no con el dedo.** El reloj no ve los dedos: el cursor sigue al antebrazo.
4. **La gravedad del reloj es confiable.** Es una fusión interna de Samsung que no controlamos ni podemos auditar.
5. **El sesgo del giroscopio es casi constante** y se puede aprender cuando la mano está quieta (|ω| < 2 °/s).
6. **El cursor es lineal en el ángulo** (D·θ). El rayo real va como D·tan θ; a la distancia de un monitor la
   diferencia es chica (3 cm a 13° y 2.4 m, en la simulación).
7. **Los tiempos del reloj y de la laptop están alineados** y el retraso de la red es estable.
8. **El cuerpo tiene medidas fijas**: brazo 0.29 m, antebrazo 0.27 m (mocap) y 0.30/0.25 m (filtro del codo).
   En el mocap el codo no se mueve cuando reproducimos tus grabaciones.
9. **Una persona, un reloj, una laptop**, en la misma red Wi-Fi.

## Falencias conocidas: lo que ya medimos que falla

1. **El rumbo se va.** El giro alrededor de la vertical no lo corrige la gravedad. Con el sesgo de un
   giroscopio real (unas décimas de °/s) el cursor se desvía unos 12 cm en 10 s a 2.4 m de la pantalla.
2. **Con el brazo colgando, la proyección se rompe.** El rumbo de un antebrazo casi vertical no existe: el
   método de las páginas (∫yaw) se equivoca 16° de mediana y hasta 79° caminando. El mocap usa fusión
   (Mahony) y queda bajo 1°; el ratón aéreo y Dibuja todavía usan la proyección.
3. **El pellizco no sirve como clic** a 100 Hz: 12 de 20 en las pruebas. El clic con giro de muñeca
   (tornillo, ~700 °/s) sí se distingue.
4. **El muestreo no es tan alto como parece.** A 5 ms llegan ~200 muestras por segundo pero solo ~115 son
   lecturas nuevas. Con la pantalla apagada baja a ~45 Hz o llega en ráfagas y la página se congela.
5. **El servicio de sensores del reloj se traba** si se corta mal ("Listener is already added"): hay que
   reiniciar el reloj.
6. **Una sola conexión de depuración a la vez**: el grabador y el puente no pueden correr juntos.
7. **El botón de inicio es el de encendido**: mantenerlo abre el asistente o reinicia el reloj. No se usa.
8. **La calibración medida no está aplicada**: la vertical necesita ×1.3 de ganancia y los ejes se cruzan a
   75°, no a 90°.
9. **Las letras reconstruidas se parecen 0.74** en letras que el modelo nunca vio: el reloj ve la muñeca, no
   los dedos.
10. **Tus grabaciones en el mocap no tienen verdad** contra la cual comparar, y su rumbo inicial lo suponemos
    hacia el frente.
11. **Las pruebas del mocap usan datos sintéticos de nuestro propio modelo**: comprueban la matemática, no el
    mundo real.
12. **Dependemos de una puerta trasera**: Samsung ya no da certificados para apps de reloj; leemos los sensores
    con `sensorctl` por la conexión de depuración.
13. **La batería**: transmitir sin parar la gasta en un par de horas.

## Por mejorar

### Para publicar (primero)

- **App instalable**: la v0.1 ya existe (`GearStream.exe` en un .zip, con asistente, ajustes y bandeja). Falta un
  instalador, firmarla (para que Windows no avise) y **probarla con el reloj de verdad**: solo se probó con el
  reloj simulado porque el reloj estaba sin batería.
- ~~Quitar las IPs de tu red~~: hecho, ahora son ejemplos (`192.168.0.XX`) y el ratón aéreo busca el reloj solo.
  Siguen en el historial de git, pero son IPs de red local: desde afuera no llevan a nada.
- ~~three.js sin internet~~: hecho, va en `server/web/vendor/`. El visor exportado sigue con el CDN porque viaja solo.
- **Pruebas automáticas en GitHub Actions**: escrito en `.github/workflows/app.yml` (pruebas + armar y probar el
  .exe); falta verlo correr en GitHub.
- **Guía para contribuir** y una captura o GIF por página.

### Matemática y sensores

- **Fusión en todas partes**: llevar el filtro de Mahony del mocap al ratón aéreo y a Dibuja.
- **Aprender el sesgo mejor** (un filtro de Kalman) y recentrar solo, suave, cuando la mano descansa.
- **Aplicar la calibración** (la matriz 2×2) y un asistente de "sigue el punto".
- **Mapeo con tan θ** opcional para pantallas grandes o proyectores.
- **Validar contra la realidad**: video del teléfono con estimación de pose, o el ratón y el trackpad como
  maestros (ya los grabamos).
- **Magnetómetro**, si el reloj lo entrega, para frenar la deriva del rumbo.
- **Posición, no solo orientación**: integrar el acelerómetro con correcciones de velocidad cero.

### Código

- `tools/air_mouse.py` pesa 146 KB: partirlo en módulos.
- **Una sola extracción**: el ratón aéreo (Python) y las páginas (`wrist.js`) calculan roll/yaw/pitch por
  separado.
- **Comentarios en un solo idioma**: los archivos viejos (`sdb_bridge.py`, `sdb_client.py`, `server.py`) mezclan
  inglés y español.
- **Un módulo común para las páginas**: conexión al servidor, frecuencia, muñeca y botones se repiten.
- **Ventanas angostas**: la barra de herramientas de varias páginas se amontona.

### Experiencia

- El plano de caminar del modo comercial se ve de canto.
- El navegador exige un clic antes de dejar sonar la música.
- Mensajes más claros cuando el reloj no responde (qué hacer, no solo qué pasó).
