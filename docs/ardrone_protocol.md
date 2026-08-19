# Protocolo del Parrot AR.Drone 2.0

> **Alcance.** Este documento describe el protocolo legado del **AR.Drone 2.0** (AR.Drone SDK 2.0), no el protocolo ARSDK de productos Parrot posteriores. El MVP descrito aquí únicamente abre la sesión de NavData y recibe telemetría: no arma ni mueve motores.

## Fuentes y criterio de verificación

La fuente normativa utilizada es la guía original *AR.Drone Developer Guide*, revisión 2.0, en particular los capítulos 6 («Communication services»), 7 («AT commands») y 8 («Navdata»), junto con los encabezados y ejemplos distribuidos en el SDK oficial. Como el sitio histórico de Parrot ya no conserva de forma estable todas las descargas, se enlazan también copias conservadas y el árbol del SDK:

1. Parrot, [*AR.Drone Developer Guide 2.0* (copia conservada)](https://jpchanson.github.io/ARdrone/ParrotDevGuide.pdf), capítulos 6–8.
2. Parrot Developers, [AR.Drone SDK 2.0](https://github.com/Parrot-Developers/ARDrone_SDK_2_0): `ARDroneLib/Soft/Common/navdata_common.h`, `ardrone_api.h` y el cliente de ejemplo.
3. Código fuente histórico de Parrot, [proyecto AR.Drone en GitHub](https://github.com/Parrot-Developers), para contrastar estructuras, constantes y la negociación de configuración.

Los números de puerto, cabeceras, unidades y bits indicados abajo proceden de la guía/SDK, no de inferencias de capturas. Algunos detalles cambian entre revisiones de firmware (especialmente multi-configuración); se señalan expresamente. Antes de habilitar vuelo se debe contrastar el comportamiento con el firmware del aparato mediante NavData y una captura de Wireshark.

## Topología y servicios de red

En la configuración de fábrica, el dron crea un punto de acceso Wi-Fi sin infraestructura y usa:

```text
Dron:               192.168.1.1
AT commands:        UDP destino 5556
NavData:            UDP destino 5554 (flujo de vuelta al cliente)
Vídeo:              TCP 5555 (fuera de este MVP)
Control/config:     TCP 5559 (servicio del SDK; no necesario para el MVP)
```

Los puertos 5554 y 5556 están verificados en las tablas de servicios de la guía, y en las constantes del SDK. Que un socket UDP pueda hacer `connect()` **no demuestra** que el dron exista: UDP no realiza handshake. La evidencia de comunicación para MVP-00 es recibir un datagrama NavData válido después del disparador de cuatro bytes.

El flujo AT es unidireccional PC → dron. NavData es UDP dron → PC. No existe confirmación por paquete AT; el estado y el bit `command_mask` de NavData son el mecanismo observable para determinadas órdenes de configuración. Los puertos de vídeo/control se documentan solo para situar la arquitectura y no se abren en MVP-00/01.

## Canal de comandos AT (UDP 5556)

Cada comando es ASCII y termina en retorno de carro (`\r`, byte `0x0d`):

```text
AT*<NOMBRE>=<sequence>[,<argumento>...]\r
```

Se pueden concatenar varios comandos en un datagrama, respetando el límite de 1024 bytes indicado por la guía. El contador `sequence`:

- es decimal, positivo y estrictamente creciente dentro de una sesión;
- comienza en `1` al iniciar el cliente;
- es común a todos los comandos AT;
- no debe reutilizarse ni retroceder; el dron descarta comandos con secuencia antigua.

La documentación recomienda tráfico AT periódico (habitualmente un ciclo de control cercano a 30 ms en el SDK), pero la obligación de protocolo es no dejar vencer el watchdog de comunicaciones. La cadencia exacta de un futuro control loop debe medirse, no derivarse de la precisión de `sleep()`.

### `AT*REF`

```text
AT*REF=<seq>,<flags>\r
```

Gestiona la entrada global de despegue/aterrizaje y emergencia. El argumento conserva un patrón de bits requerido por el firmware. Los valores canónicos del SDK son:

| Acción solicitada | Decimal | Hexadecimal |
|---|---:|---:|
| aterrizar (`start=0`, emergencia=0) | 290717696 | `0x11540000` |
| despegar (`start=1`, emergencia=0) | 290718208 | `0x11540200` |

El bit 9 es `start` (0 aterrizaje, 1 despegue). El bit 8 es una entrada **toggle** de emergencia, no una orden idempotente «poner emergencia»: un flanco puede entrar en emergencia y otro salir/resetearla. Por ello nunca se debe retransmitir ciegamente una variante de emergencia y se debe confirmar el bit 31 de estado por NavData. El MVP no genera `AT*REF`.

### `AT*PCMD`

```text
AT*PCMD=<seq>,<progressive>,<roll_i32>,<pitch_i32>,<gaz_i32>,<yaw_i32>\r
```

`progressive=0` solicita hover; `progressive=1` habilita los ejes progresivos. Roll, pitch, gaz y yaw son valores nominales `float32` en `[-1.0, +1.0]`, pero se transmiten como el **entero decimal con signo que contiene el mismo patrón IEEE-754 binario de 32 bits**, no como texto flotante. Ejemplo conceptual: `1.0f` tiene bits `0x3f800000` y se escribe `1065353216`; `-1.0f` tiene bits `0xbf800000` y, interpretado como `int32`, se escribe `-1082130432`. La guía define pitch negativo como avance y positivo como retroceso; los demás signos deben conservar la convención documentada y validarse con el aparato antes del vuelo.

Este comando está fuera de MVP-00/01.

### `AT*COMWDG`

```text
AT*COMWDG=<seq>\r
```

Reinicia el watchdog de comunicaciones cuando NavData informa `com_watchdog` (bit 30). La guía establece un timeout del watchdog de comandos de aproximadamente **2 segundos** sin comandos AT. No se debe confundir `COMWDG` con un keepalive suficiente para controlar vuelo: un cliente seguro envía su estado deseado a cadencia fija y, ante pérdida de input/telemetría, pasa a ejes cero y a su política de aterrizaje. `COMWDG` no confirma recepción ni restablece Wi-Fi.

### `AT*CONFIG` y `AT*CONFIG_IDS`

```text
AT*CONFIG=<seq>,"<sección:clave>","<valor>"\r
AT*CONFIG_IDS=<seq>,"<session_id>","<user_id>","<application_id>"\r
```

Para NavData demo se solicita:

```text
AT*CONFIG=<seq>,"general:navdata_demo","TRUE"\r
```

En firmware con multi-configuración, la guía SDK 2.0 exige enviar primero `AT*CONFIG_IDS` con identificadores registrados/válidos y asociarlo al `CONFIG`; clientes antiguos a veces funcionan sin ello. Esto es una diferencia de firmware que debe registrarse durante pruebas reales, no ocultarse con reintentos infinitos. `general:navdata_options` es una máscara que selecciona opciones adicionales; el MVP no presupone que estén presentes.

### `AT*CTRL`

```text
AT*CTRL=<seq>,<mode>,<arg>\r
```

Para la negociación de configuración, `mode=5, arg=0` (`ACK_CONTROL_MODE`) reconoce/borra el evento de comando después de observar `command_mask` en NavData. La secuencia segura es: enviar `CONFIG` (con `CONFIG_IDS` si corresponde), esperar a que se active el bit 6, enviar `CTRL ... 5,0`, y esperar a que se borre. No se debe asumir éxito solo porque `sendto()` terminó sin error.

Otros modos de `CTRL` permiten pedir configuración; no son necesarios para MVP-01 y no deben mezclarse con el reconocimiento sin implementar su máquina de estados.

## NavData (UDP 5554)

### Apertura de la sesión

El cliente abre un socket UDP, con timeout y ligado a una interfaz local alcanzable, y envía al puerto 5554 del dron el entero little-endian de 32 bits `1`:

```text
01 00 00 00
```

El dron empieza entonces a enviar NavData al endpoint que originó el disparador. En Windows hay que mantener abierto **ese mismo socket** para recibir la respuesta. Algunos ejemplos históricos ligan explícitamente el puerto local 5554; otros dejan que Winsock asigne un puerto efímero. La implementación debe favorecer el mismo socket y tolerar/reintentar la negociación, evitando dos consumidores simultáneos del puerto.

Al iniciar, `navdata_bootstrap` suele estar activo. El cliente solicita `general:navdata_demo=TRUE`, completa el handshake `command_mask`/`CTRL`, y sigue recibiendo. El modo demo ofrece el subconjunto estable que necesita el monitor y reduce ancho de banda. La guía indica aproximadamente 15 Hz en demo y hasta aproximadamente 200 Hz en modo completo; son tasas nominales, no una garantía de entrega UDP.

### Cabecera del datagrama

Todos los enteros son little-endian en el AR.Drone 2.0:

| Offset | Tipo | Campo |
|---:|---|---|
| 0 | `uint32` | `header = 0x55667788` |
| 4 | `uint32` | máscara `ardrone_state` |
| 8 | `uint32` | secuencia NavData |
| 12 | `uint32` | `vision_defined` |
| 16… | opciones TLV | opciones concatenadas |

Se deben rechazar datagramas truncados, con cabecera distinta, opciones de tamaño menor que 4, tamaños que excedan el datagrama o secuencias obsoletas (teniendo en cuenta el wrap de `uint32`). UDP puede perder, duplicar o reordenar paquetes; un salto de secuencia es una métrica de pérdida, no necesariamente un error de parsing.

### Opciones TLV y bloque demo

Cada opción comienza con:

```c
uint16_t tag;
uint16_t size;  // incluye los cuatro bytes de tag y size
```

El tag `0` (`NAVDATA_DEMO_TAG`) contiene, tras la cabecera TLV:

- `ctrl_state` (`uint32`): estado de control, cuyo valor alto identifica el estado principal;
- `vbat_flying_percentage` (`uint32`): batería en porcentaje;
- `theta`, `phi`, `psi` (`float32`): pitch, roll y yaw en miligrados (dividir por 1000 para grados);
- `altitude` (`int32`): milímetros (dividir por 1000 para metros);
- `vx`, `vy`, `vz` (`float32`): milímetros por segundo en el marco definido por el SDK (dividir por 1000 para m/s);
- `num_frames` y campos posteriores definidos en la estructura de la revisión de SDK.

El parser debe usar el `size` real y aceptar opciones desconocidas, saltándolas. No debe desempaquetar una estructura C completa sin considerar padding/tamaño ni exigir campos opcionales que una versión de firmware no envía.

### Checksum

La última opción normal es `NAVDATA_CKS_TAG = 0xffff`; contiene un `uint32` con la suma, módulo `2^32`, de **cada byte anterior a la opción checksum**. Debe comprobarse antes de publicar telemetría. Un paquete sin checksum, truncado o con checksum incorrecto no es NavData válida y no renueva el freshness watchdog de la aplicación.

### Máscara `ardrone_state`

Los bits definidos por `ardrone_api.h`/la guía son:

| Bit | Nombre SDK | Interpretación cuando vale 1 |
|---:|---|---|
| 0 | `FLY_MASK` | volando (0 = aterrizado) |
| 1 | `VIDEO_MASK` | vídeo habilitado |
| 2 | `VISION_MASK` | visión habilitada |
| 3 | `CONTROL_MASK` | algoritmo de control alternativo/velocidad angular |
| 4 | `ALTITUDE_MASK` | control de altitud activo |
| 5 | `USER_FEEDBACK_START` | entrada start del usuario |
| 6 | `COMMAND_MASK` | comando/configuración pendiente de ACK |
| 7 | `CAMERA_MASK` | cámara preparada |
| 8 | `TRAVELLING_MASK` | travelling activo |
| 9 | `USB_MASK` | USB preparado |
| 10 | `NAVDATA_DEMO_MASK` | solo NavData demo |
| 11 | `NAVDATA_BOOTSTRAP` | NavData en bootstrap |
| 12 | `MOTORS_MASK` | problema/motores parados |
| 13 | `COM_LOST_MASK` | comunicación de red perdida |
| 14 | `SOFTWARE_FAULT` | fallo de software |
| 15 | `VBAT_LOW` | batería baja |
| 16 | `USER_EL` | emergencia solicitada por usuario |
| 17 | `TIMER_ELAPSED` | temporizador agotado |
| 18 | `MAGNETO_NEEDS_CALIB` | magnetómetro requiere calibración |
| 19 | `ANGLES_OUT_OF_RANGE` | ángulos fuera de rango |
| 20 | `WIND_MASK` | demasiado viento |
| 21 | `ULTRASOUND_MASK` | ultrasonidos sin recepción |
| 22 | `CUTOUT_MASK` | cutout detectado |
| 23 | `PIC_VERSION_MASK` | número de versión PIC OK |
| 24 | `ATCODEC_THREAD_ON` | hilo AT codec activo |
| 25 | `NAVDATA_THREAD_ON` | hilo NavData activo |
| 26 | `VIDEO_THREAD_ON` | hilo vídeo activo |
| 27 | `ACQ_THREAD_ON` | hilo adquisición activo |
| 28 | `CTRL_WATCHDOG_MASK` | watchdog de control |
| 29 | `ADC_WATCHDOG_MASK` | watchdog ADC |
| 30 | `COM_WATCHDOG_MASK` | watchdog de comandos AT |
| 31 | `EMERGENCY_MASK` | estado de emergencia |

`LANDED` solo puede inferirse de bit 0=0 cuando el paquete es reciente y válido, y conviene cruzarlo con `ctrl_state`; una ausencia de telemetría jamás equivale a aterrizado. Algunos nombres son diagnósticos del firmware y no instrucciones de recuperación: la aplicación debe mostrar el bit bruto además de mapear un estado amigable.

## Secuencia de inicialización del MVP-01

1. El usuario conecta Windows manualmente al SSID del AR.Drone.
2. Se crea el socket de comandos UDP hacia `192.168.1.1:5556`, sin enviar ninguna orden de vuelo.
3. Se crea **un** socket NavData con timeout; se conserva para trigger y recepción.
4. Se envía `uint32_le(1)` a `192.168.1.1:5554`.
5. Se espera un paquete con cabecera, estructura y checksum válidos. Un timeout provoca reintento limitado del trigger y estado `NAVDATA_LOST`, no despegue ni una falsa indicación `LANDED`.
6. Si llega bootstrap, se negocia `general:navdata_demo=TRUE` mediante `CONFIG` y el ACK con `CTRL`; en firmware que lo exija se usan `CONFIG_IDS`.
7. Se publica el demo más reciente de forma atómica y se calcula su antigüedad con reloj monotónico (`time.perf_counter()`). La UI puede refrescar más lentamente que NavData.
8. Durante la sesión se atiende `COM_WATCHDOG_MASK` con `AT*COMWDG`, usando la secuencia AT única. Esto no autoriza comandos de vuelo.
9. Al recibir Ctrl+C se cierran sockets e hilos; no se usan señales POSIX exclusivas.

## Timeouts, pérdida y recuperación

- **Watchdog del dron:** aproximadamente 2 s sin AT, señalado por bit 30; se responde con `COMWDG` y se verifica en NavData.
- **Timeout de socket:** es una política local para despertar el receptor; no prueba por sí solo pérdida permanente.
- **NavData stale:** el umbral es una decisión de seguridad de la aplicación. Debe configurarse y probarse; no se presenta como una constante del protocolo. Al vencer, la telemetría queda inválida y la máquina pasa a `NAVDATA_LOST`.
- **Recuperación:** recrear/renegociar el socket NavData con backoff acotado y volver a bootstrap/configuración. Nunca conservar el último estado como actual ni ejecutar takeoff durante recuperación.
- **UDP/Winsock:** `sendto()` exitoso solo confirma entrega al stack local. Errores como `WSAECONNRESET` pueden aparecer en una recepción UDP tras un ICMP «port unreachable»; el receptor debe tratarlos como pérdida recuperable, cerrar y recrear limpiamente el socket.

## Límites de esta verificación

Este documento verifica el formato contra la guía y las cabeceras del SDK, pero no sustituye una prueba con el firmware concreto. Antes de MVP-02 se deben guardar: versión de firmware, primer paquete bootstrap, negociación de `command_mask`, frecuencia y pérdidas, estado/checksum, comportamiento al desconectar Wi-Fi y efecto del firewall de Windows. En particular, no se debe ensayar `REF`, `PCMD` ni el toggle de emergencia hasta disponer de telemetría estable, zona despejada y procedimiento físico de contención.
