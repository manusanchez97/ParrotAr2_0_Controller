# Roadmap

El orden es obligatorio. Cada MVP comienza solo cuando el anterior supera sus
pruebas automáticas y, cuando corresponda, la validación con hardware real en
Windows. Añadir esqueletos de interfaces futuras no autoriza implementar ni
activar funciones de etapas posteriores.

## MVP-00 — Diagnóstico de red Windows

**Entrega:** `python -m cli.ping` descubre la interfaz local elegida por la ruta,
comprueba que se pueden abrir los sockets UDP y solicita una respuesta real del
protocolo. ICMP puede mostrarse como información auxiliar, nunca como prueba
única. No modifica Wi-Fi ni firewall.

**Puerta de salida:** diagnósticos claros para éxito, timeout, ruta equivocada,
bind fallido y socket cerrado; cierre limpio; pruebas con sockets simulados y
loopback; ejecución verificada en Windows/Winsock y comunicación confirmada por
un datagrama NavData válido del dron.

## MVP-01 — NavData

**Entrega:** inicio del flujo NavData, parser defensivo y
`python -m cli.monitor` con conexión, batería, estado de vuelo, actitud, altitud,
velocidades y salud/edad de telemetría, actualizado sin inundar la consola.

**Puerta de salida:** fixtures cubren paquete válido, opciones desconocidas,
truncamiento, tamaños inválidos, checksum, bits y unidades; se detecta pérdida y
recuperación; `Ctrl+C` cierra en Windows; telemetría real permanece estable. No
se envía ningún comando capaz de mover motores.

> **La entrega actual termina aquí.** No se avanza hasta validar networking y
> NavData con un AR.Drone 2.0 real.

## MVP-02 — Generador de comandos AT + tests

**Entrega futura:** codificación pura de comandos AT, contador de secuencia,
representación de floats, límites, terminadores, configuración y watchdog, sin
acoplarse a input ni Windows.

**Puerta de salida:** vectores conocidos y tests de secuencia, wrap/error,
float, límites y formato; captura de tráfico comparada con documentación/SDK;
ningún vuelo en esta etapa.

## MVP-03 — Takeoff / Hover / Land

**Entrega futura:** máquina de estados y bucle periódico con acciones explícitas
de despegue, hover y aterrizaje, además de emergencia inequívoca.

**Puerta de salida:** pruebas iniciales sin hélices; NavData reciente obligatoria;
prioridades EMERGENCY/LAND verificadas; watchdogs y pérdida de enlace ensayados;
primer vuelo en área controlada con operador preparado para desconectar batería.

## MVP-04 — Control por teclado

**Entrega futura:** `KeyboardController` compatible con Windows, eventos key-down
y key-up, teclas simultáneas y estado neutral al soltar o perder input. Los
eventos solo actualizan intención; el bucle fijo envía comandos.

**Puerta de salida:** mapeo, simultaneidad, pérdida de foco/input, deadband,
normalización y salida comprobados; LAND y EMERGENCY conservan prioridad.

## MVP-05 — Gamepad

**Entrega futura:** `GamepadController` tras la abstracción común
`ControllerInput`, con Xbox/XInput y HID compatibles mediante una biblioteca
Windows evaluada.

**Puerta de salida:** conexión/desconexión en caliente, ejes, deadband, inversión,
normalización y botones probados; desconexión neutraliza la intención.

## MVP-06 — Interfaz de telemetría

**Entrega futura:** presentación más rica sin acoplarla al parser ni perjudicar
la cadencia de control.

**Puerta de salida:** UI lenta o cerrada no bloquea red/control; distingue dato
actual, obsoleto y desconocido; consumo de recursos medido en Windows.

## MVP-07 — Vídeo

**Entrega futura:** recepción y decodificación de vídeo aisladas de NavData y del
bucle de control.

**Puerta de salida:** pérdidas o carga del vídeo no afectan watchdogs ni control;
dependencias y compatibilidad Windows documentadas.

## MVP-08 — Port a ESP32

**Entrega futura:** portar transporte y control reutilizando especificación,
vectores binarios y contratos; adaptar concurrencia y tiempo al entorno embebido.

**Puerta de salida:** paridad de codificación/parsing con Python, presupuestos de
memoria/tiempo medidos y todos los failsafes revalidados en la nueva plataforma.

## Evidencia por etapa

Cada puerta conserva: versión de firmware/hardware, versión de Windows y Python,
comando de prueba, resultado, captura Wireshark cuando sea pertinente y riesgos
pendientes. Los fallos no se “resuelven” relajando validación o suponiendo un
estado seguro. Una regresión de seguridad bloquea todas las etapas posteriores.
