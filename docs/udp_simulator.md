# Simulador UDP del AR.Drone 2.0

El simulador local permite desarrollar el cliente de red sin conectar un dron.
Escucha solo en `127.0.0.1`, usando los puertos UDP habituales `5554` (NavData)
y `5556` (AT), y genera paquetes compatibles con el parser del proyecto.

## Arranque

En una terminal:

```powershell
python -m simulator.udp_drone
```

En otra terminal, el diagnóstico de red existente puede apuntar al loopback:

```powershell
python -m cli.ping --ip 127.0.0.1
```

El monitor completa la configuración demo automáticamente y muestra la
telemetría sintética:

```powershell
python -m cli.monitor --ip 127.0.0.1
```

Para conducir el gemelo desde la consola de Windows, abre otra terminal y
ejecuta:

```powershell
python -m cli.controller --simulator
```

Pulsa `T` para despegar, `L` para aterrizar y `Esc` para aterrizar y salir.
Mantén el foco en esa consola. Los ejes son `W/S` avance/retroceso, `A/D`
izquierda/derecha, `R/F` subir/bajar y `Q/E` giro. Con ninguna tecla de eje
pulsada, el controlador envía ejes neutrales.

Los comandos de inclinación se aplican en los ejes del dron: al cambiar el yaw,
`W/S` también cambia la dirección de avance respecto al mapa. La vista 3D queda
fija y la flecha del dron gira con el rumbo.
Takeoff y land se reenvían brevemente hasta que NavData confirma el cambio de
estado.

El controlador muestra batería, estado, actitud, altitud, velocidades y edad de
NavData en la consola, y abre una ventana con cuadrícula isométrica, posición y
trayectoria 3D estimadas. X/Y se integran desde VX/VY y Z usa altitud; es un
recorrido local relativo, sin GPS ni posición absoluta. Puedes cerrar la ventana
del mapa sin detener el control. El monitor independiente sigue disponible si
quieres abrir la telemetría en otra terminal. Usa `--no-map` para desactivar la
ventana.

El cliente recibirá primero un paquete NavData válido sin opción demo. Para
completar el modo demo, un cliente debe enviar `AT*CONFIG` solicitando
`general:navdata_demo=TRUE`, esperar `COMMAND_MASK`, y reconocerlo con
`AT*CTRL=...,5,0`. El simulador entonces incluye el bloque demo en su flujo.
`AT*CONFIG_IDS` se acepta y registra si se envía, pero no es obligatorio para
este perfil del simulador.

El monitor y el controlador pueden permanecer abiertos a la vez en terminales
distintas. El simulador envía cada paquete NavData a todos los clientes locales
activos; cerrar uno no interrumpe el flujo del otro.

La telemetría demo empieza en tierra con batería 87 % y se publica a 15 Hz; los
paquetes llevan secuencia creciente y checksum válido. El simulador entiende el
trigger NavData, `CONFIG_IDS`, la configuración `navdata_demo`, el ACK `CTRL`,
`AT*REF` y `AT*PCMD`. `REF` solicita despegue/aterrizaje y `PCMD` cambia actitud,
velocidad y altitud mediante un modelo cinemático sencillo. El toggle de
emergencia produce un descenso simulado. `AT*PCMD_MAG` no se modela.

Este modelo no reproduce aerodinámica, sensores, batería variable, límites del
firmware ni latencias reales. Es útil para comprobar que el software emite y
consume el protocolo y para observar respuestas aproximadas, no para validar
parámetros de vuelo reales.

Los ejes progresivos vuelven a cero si no llega otro `PCMD` durante 0,5 s. Si
no llega ningún comando AT durante 2 s mientras está volando, el gemelo neutraliza
los ejes e inicia un aterrizaje simulado.

El emulador es una herramienta de desarrollo de protocolo, no certifica
compatibilidad con firmware, no reemplaza pruebas físicas de red, y sus datos no
deben confundirse con telemetría real. Detén el proceso con `Ctrl+C`.
