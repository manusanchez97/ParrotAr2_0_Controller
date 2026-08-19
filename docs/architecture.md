# Arquitectura

## Alcance de esta entrega

Esta primera entrega implementa exclusivamente **MVP-00 (diagnóstico de red)** y
**MVP-01 (recepción y visualización de NavData)**. Es deliberadamente de solo
lectura desde el punto de vista del vuelo: no contiene despegue, aterrizaje,
`AT*PCMD`, movimiento, teclado, gamepad ni vídeo. El único datagrama enviado al
puerto de NavData es el disparador que solicita el flujo de telemetría.

La aplicación se ejecuta en Windows 10/11 con Python, después de que el usuario
se conecte manualmente al punto de acceso Wi-Fi del dron. No cambia interfaces,
rutas ni reglas de firewall.

## Principios

1. **Protocolo puro y portable.** Constantes, validación binaria y parser no
   conocen Winsock, PowerShell ni la interfaz de usuario.
2. **Efectos de red encapsulados.** Creación, configuración y cierre de sockets
   están en la capa de transporte.
3. **Estado explícito e inmutable para el consumidor.** Cada paquete válido
   produce una instantánea de telemetría; un paquete incompleto o corrupto no
   sobrescribe la última instantánea válida.
4. **Tiempo monotónico.** Los plazos y la edad de NavData se calculan con
   `time.monotonic()` o `time.perf_counter()`, nunca con la hora civil.
5. **Cierre determinista.** Los sockets se poseen mediante context managers y
   se cierran tanto en salida normal como ante `Ctrl+C` o error.
6. **Seguridad por defecto.** La ausencia de telemetría es desconocimiento, no
   confirmación de que el dron está aterrizado.

## Capas del MVP

```text
cli.ping / cli.monitor              presentación y ciclo de aplicación
             │
             ▼
ardrone.client                     orquestación de sesión NavData
             │
       ┌─────┴────────┐
       ▼              ▼
ardrone.transport  ardrone.navdata transporte UDP / parser binario puro
       │              │
       └──────┬───────┘
              ▼
         ardrone.state              instantánea de telemetría
```

`ardrone.protocol` centraliza dirección, puertos, cabeceras, etiquetas, bits de
estado y límites de protocolo. No deben repetirse literales de red en los CLI.

### Flujo de entrada (MVP-01)

```text
AR.Drone → UDP 5554 → transporte → parser NavData → DroneState
                                                → monitor / diagnóstico
```

El parser recibe únicamente `bytes` y devuelve tipos Python o un error de
protocolo. Así puede probarse con fixtures sin red ni dron.

### Flujo de control futuro (no implementado)

```text
ControllerInput → DesiredControlState → bucle de control de frecuencia fija
                → codificador AT → transporte UDP → Wi-Fi → AR.Drone
```

La futura entrada de teclado o gamepad escribirá intención, pero nunca enviará
comandos directamente. El bucle será el único propietario de la cadencia y del
número de secuencia. El diseño separará una interfaz `ControllerInput` de sus
adaptadores Windows para que protocolo y control permanezcan portables.

## Responsabilidades por módulo

| Módulo | Responsabilidad actual o prevista |
|---|---|
| `ardrone.protocol` | Constantes y primitivas independientes del SO. |
| `ardrone.navdata` | Verificación de cabecera, opciones, longitudes y checksum; decodificación de demo/state. |
| `ardrone.state` | Modelos y significado observable del estado del dron. |
| `ardrone.transport` | Sockets UDP, timeout, dirección local elegida por la tabla de rutas y cierre. |
| `ardrone.client` | Inicio/reintento del flujo, recepción y detección de pérdida. |
| `cli.ping` | Diagnóstico mediante protocolo, sin depender de ICMP. |
| `cli.monitor` | Render limitado en frecuencia y cierre limpio con `Ctrl+C`. |
| `controller.*` | Futuro: adaptadores de entrada; no forman parte de MVP-00/01. |
| `safety.*` | Futuro: watchdog y máquina de estados; las reglas ya están definidas en `safety.md`. |

## Ciclo de vida y concurrencia

El MVP puede operar con un único hilo bloqueado en `recvfrom` con timeout corto:

1. crear socket UDP y enlazar el extremo local;
2. enviar el disparador NavData al dron;
3. recibir, validar y publicar instantáneas;
4. al vencer el timeout, marcar NavData como perdida y reintentar de forma
   acotada el disparador sin bloquear indefinidamente la interfaz;
5. al recibir `KeyboardInterrupt`, cerrar el socket en un bloque `finally`.

Un timeout es un evento esperado, no un motivo para reutilizar bytes antiguos.
Los errores irrecuperables de socket terminan con un diagnóstico y código de
salida distinto de cero. En Windows se evita depender de señales POSIX,
`curses`, `epoll` o descriptores de dispositivos.

Cuando exista control de vuelo habrá separación entre recepción, entrada y
bucle de control. El estado compartido se protegerá con una primitiva pequeña
(`Lock`, cola o intercambio de snapshots); no se mantendrá el lock durante E/S.
La parada se coordinará con `threading.Event`. El bucle utilizará
`perf_counter()`, espera interrumpible y corrección de deriva, sin busy-wait.

## Recuperación y observabilidad

Se distinguen cuatro resultados que no deben colapsarse en un simple “ping”:

- existe una dirección local/ruta candidata;
- se pudo crear el socket de comandos;
- se pudo crear y enlazar el socket de NavData;
- llegó un paquete NavData válido del IP y puerto esperados.

Enviar un datagrama UDP con éxito no demuestra que el dron lo recibió. Solo una
respuesta válida constituye comunicación confirmada. El cliente conserva la
edad del último paquete, contadores de paquetes inválidos/timeouts y el último
error para que el CLI diferencie pérdida, datos corruptos y configuración local.
Tras una interrupción puede volver a solicitar el flujo; nunca sintetiza estado
de vuelo durante el hueco.

## Límites de portabilidad

- La capa de protocolo usa enteros de tamaño explícito, endianness declarada y
  no depende de la representación de estructuras de C del host.
- El transporte se expresa detrás de una interfaz mínima de enviar, recibir,
  timeout y cerrar. Una futura implementación C/C++, ESP32 o Raspberry Pi puede
  sustituirla sin cambiar fixtures ni semántica del parser.
- El adaptador Windows se limita a `socket`/Winsock y presentación de consola.
- Ningún módulo de dominio ejecuta `ipconfig`, `ping` ni PowerShell.

## Estrategia de pruebas

Las pruebas unitarias inyectan datagramas binarios conocidos para verificar
cabecera, opciones desconocidas, truncamiento, unidades, bits de estado y
checksum. Sockets falsos validan timeout, reintento, cierre y selección del
remitente sin hardware. Las pruebas de integración locales usan UDP loopback y
son multiplataforma. La validación física en Windows debe comprobar finalmente
Winsock, firewall, interfaz Wi-Fi y telemetría estable; se registra por separado
porque no es reproducible en CI.

No se habilitará MVP-02 mientras los criterios de salida de MVP-00 y MVP-01 del
roadmap no se hayan validado con el dron real.
