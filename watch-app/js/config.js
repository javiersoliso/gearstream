// Configuración de GearStream en el reloj.
// SERVER_URL: pon la IP de tu laptop (server.py la imprime al arrancar).
// También se puede cambiar desde el reloj tocando la URL en pantalla.
window.GEARSTREAM_CONFIG = {
  SERVER_URL: 'ws://192.168.0.XX:8765/watch',

  // Intervalo de muestreo de tizen.sensorservice (10 ms = 100 Hz, el mínimo que admite Tizen).
  SENSOR_INTERVAL_MS: 10,
  INTERVAL_OVERRIDES: { LIGHT: 100, PRESSURE: 100, PROXIMITY: 100, ULTRAVIOLET: 100 },

  // Monitores de actividad (tizen.humanactivitymonitor). Los que el reloj no soporte se reportan como "unsupported".
  HAM_TYPES: ['HRM', 'PEDOMETER', 'WRIST_UP', 'SLEEP_MONITOR', 'SLEEP_DETECTOR', 'STRESS_MONITOR'],

  GPS: true,               // navigator.geolocation (gasta batería; en interiores casi nunca tiene fix)
  W3C_ORIENTATION: true,   // evento deviceorientation (alpha/beta/gamma ya fusionados)

  FLUSH_MS: 50,                 // cada cuánto se envía un lote por WebSocket
  MAX_BUFFER: 20000,            // muestras guardadas mientras no hay conexión
  MAX_WS_BUFFERED: 512 * 1024,  // si el socket va atrasado, se espera antes de mandar más
  KEEP_SCREEN_ON: true,         // con la pantalla apagada Tizen puede pausar los sensores
  AUTO_START: false
};
