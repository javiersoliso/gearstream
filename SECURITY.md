# Seguridad

Qué abre GearStream en tu computadora y en tu red, qué no hace, y cómo comprobar que lo que instalas es este código.

## Lo que abre

| Qué | Dónde | Quién puede hablarle |
|---|---|---|
| Servidor de las páginas y los datos | puerto 8765 | Solo esta laptop (`127.0.0.1`). En Ajustes → Red puedes abrirlo a tu Wi-Fi, para la app del teléfono o del reloj: entonces quien esté en esa red puede ver tus sensores y mandar datos. Hazlo solo en redes de confianza. |
| Canal de control del ratón aéreo | `127.0.0.1:8766` | Solo esta laptop, y solo la página de Calibración servida por GearStream. |
| Una sola app abierta | `127.0.0.1:47615` | Solo esta laptop: si abres GearStream otra vez, trae al frente la que ya estaba. |
| Depuración del reloj | puerto 26101 del reloj | Para leer los sensores sin instalar nada en el reloj, GearStream usa su modo de depuración, que escucha en tu Wi-Fi. La primera vez el reloj te pregunta si aceptas esta computadora; su llave queda en `~/.gearstream/sdbkey.json`. |

Además, el servidor rechaza:

- los pedidos dirigidos a otro nombre que no sea esta laptop (o tu red, si la abriste), que es como una página haciéndose pasar por `localhost` intentaría entrar (*DNS rebinding*);
- las conexiones de páginas de otros sitios: sin esto, cualquier página abierta en tu navegador podría leer tus sensores, porque los navegadores dejan abrir WebSockets hacia otros sitios.

`python -I tools/test_server_seguridad.py` comprueba las dos cosas contra el servidor de verdad.

## Lo que no hace

- No se conecta a internet: no hay cuentas, ni telemetría, ni actualizaciones automáticas. Las páginas traen three.js adentro; solo la página exportada de un dibujo (el visor) lo carga de cdnjs, para verse en cualquier lado.
- Tus datos (grabaciones, dibujos, tomas) se quedan en tu carpeta de datos, por defecto `Documentos/GearStream`. No se suben a ningún lado.
- No cambia nada de tu red ni de tu router. "Buscar en la red" prueba el puerto 26101 en tu subred para encontrar el reloj: en una red de empresa eso puede verse como un escaneo.

## Lo que te toca a ti

- **Apaga la depuración del reloj al terminar** (Ajustes del reloj → Acerca del reloj → Depuración). Mientras está encendida, el reloj escucha en tu Wi-Fi.
- **No aceptes en el reloj un aviso de conexión que no esperabas.** Aceptarlo le da a esa computadora acceso de depuración al reloj.
- Usa la depuración del reloj y "Abrir a la red" solo en redes de confianza, no en la Wi-Fi de un café.

## Cómo comprobar lo que instalas

- El código es este repositorio, y puedes armar el `.exe` tú: `python tools/build_app.py` (al final corre una prueba de punta a punta).
- Los `.zip` de Releases los arma GitHub Actions (`.github/workflows/app.yml`) desde una etiqueta `v*`. Cada uno trae su suma SHA-256 (`.zip.sha256`), y, con el repositorio público, una atestación de compilación que firma de qué commit y de qué ejecución salió:

  ```bash
  gh attestation verify GearStream-0.1.0-windows.zip -R <dueño>/<repo>
  ```

- El `.exe` no está firmado con un certificado de código, así que Windows muestra el aviso de SmartScreen la primera vez.

## Si encuentras un problema

Abre un issue en este repositorio. Si es algo que no conviene contar en público, usa el aviso privado de vulnerabilidades de GitHub (pestaña Security), si está activado.
