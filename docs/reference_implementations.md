# Implementaciones de referencia del AR.Drone 2.0

## Criterio de investigación

Para implementar el protocolo se considera normativa la documentación y el
código del SDK de Parrot. Los proyectos de terceros son evidencia útil sobre
interoperabilidad, pero **no sustituyen** al SDK: algunos contienen constantes
sin explicar, omiten opciones de NavData o fueron escritos para Python 2.

Fuentes primarias:

- [AR.Drone Developer Guide 2.0.1 (Parrot, copia archivada por la comunidad)](https://jpchanson.github.io/ARdrone/ParrotDevGuide.pdf).
- [AR.Drone SDK 2.0, espejo del código publicado por Parrot](https://github.com/Parrot-Developers/ardrone-sdk).

El sitio y las descargas originales son antiguos y pueden no estar disponibles
de forma continua. Por eso se indica expresamente cuándo un enlace es un espejo
o archivo, y los valores de protocolo deben contrastarse con el *Developer
Guide* y las cabeceras del SDK.

## Proyectos examinados

### AR.Drone SDK de Parrot

El SDK incluye la implementación de referencia en C: apertura de canales,
generación de órdenes AT, negociación de configuración, análisis de NavData y
watchdogs. Su arquitectura mezcla partes portables con la abstracción de hilos,
sockets y la aplicación de ejemplo. Es la referencia para:

- orden y formato exacto de `AT*CONFIG`, `AT*CTRL`, `AT*PCMD`, `AT*REF` y
  `AT*COMWDG`;
- contador de secuencia compartido por la sesión AT;
- cabecera, opciones y checksum de NavData;
- bits de `ardrone_state` y el diálogo de configuración.

El SDK histórico incluía soporte para Windows en su API de plataforma, pero no
conviene incorporar su sistema de compilación ni su UI al MVP Python. El
protocolo UDP funciona con Winsock; nuestro diseño reproduce sólo el mínimo
documentado y conserva capturas para comparar el comportamiento real.

### node-ar-drone

[node-ar-drone](https://github.com/felixge/node-ar-drone) es una implementación
JavaScript muy conocida. Separa un cliente de alto nivel, el flujo de NavData,
la generación de órdenes y el transporte mediante `dgram`. Mantiene el envío
periódico de órdenes y ofrece una API de movimiento. Es especialmente útil para
estudiar cómo una biblioteca ligera desacopla eventos de entrada del tráfico AT.

El módulo UDP de Node es multiplataforma, por lo que la parte de control puede
ejecutarse en Windows. Sin embargo, eso no demuestra que cada utilidad opcional
(vídeo, scripts o dependencias antiguas) funcione hoy en Windows 10/11. El
repositorio está orientado a versiones antiguas de Node y no debe copiarse sin
validar secuencias, temporización y seguridad.

### libardrone

[robotika/libardrone](https://github.com/robotika/libardrone) implementa en
Python el protocolo de control/NavData con pocos componentes. Es valioso para
comparar desempaquetado binario, conversión de los argumentos `float` de PCMD a
enteros de 32 bits y ciclos de watchdog. Parte de su historia corresponde a
Python 2 y sus ejemplos no constituyen soporte formal de Python 3.12 ni de
Windows actual. Se toma como lectura, no como dependencia.

### pyardrone

[pyardrone](https://github.com/afdaniele/pyardrone) ofrece una API Python para
AR.Drone y organiza comandos, estado y navegación. Sirve como segunda
implementación independiente para contrastar opciones de NavData y órdenes AT.
Su mera utilización de `socket` no garantiza compatibilidad completa con
Winsock, firewall, cierre o recuperación: esas rutas se prueban aquí de manera
explícita y sin requerir el paquete.

### AR.Drone-Control-.NET

[AR.Drone-Control-.NET](https://github.com/shtejv/AR.Drone-Control-.NET) es una
biblioteca C#/.NET orientada al AR.Drone 2.0. Es la referencia de terceros más
relevante para Windows: muestra que el control, NavData y vídeo pueden separarse
en trabajadores gestionados y sockets .NET. También ilustra eventos de estado y
una API de cliente. No se reutiliza su código y el vídeo queda deliberadamente
fuera de MVP-00/MVP-01.

### ardrone_autonomy (ROS)

[AutonomyLab/ardrone_autonomy](https://github.com/AutonomyLab/ardrone_autonomy)
es un controlador ROS maduro basado en el SDK. Aporta experiencia sobre
reconexión, publicación de telemetría y calibraciones. ROS y su cadena histórica
son principalmente Linux: no es una base apropiada para una aplicación nativa
de PowerShell/Windows ni prueba de compatibilidad Winsock.

## Patrones comunes y decisiones propias

| Área | Patrón observado | Decisión del proyecto |
|---|---|---|
| Transporte | UDP independiente para AT y NavData | `socket` estándar, encapsulado detrás de una clase cerrable |
| Inicialización NavData | Datagrama de activación al puerto 5554 y espera de cabecera válida | La recepción válida, no ICMP, demuestra comunicación |
| Comandos | Contador creciente y `\r` final | Se implementará y probará en MVP-02; no se envía PCMD en MVP-01 |
| Configuración | `CONFIG` y acuse mediante estado/`CTRL` | Máquina explícita con timeout; nunca una ráfaga “mágica” |
| Watchdog | Envío periódico independiente de la entrada | Futuro bucle fijo; un evento de teclado nunca impulsa la cadencia |
| NavData | Opciones TLV con DEMO como resumen | Parser acotado, ignora opciones desconocidas y valida checksum |
| Recuperación | Reabrir sesión tras silencio/error | Cierre idempotente, backoff acotado y estado `NAVDATA_LOST` |

## Particularidades de Windows encontradas

- Python usa Winsock bajo `socket`; no se emplean `epoll`, señales POSIX,
  `/dev/input` ni `curses`.
- Un `connect()` sobre UDP selecciona ruta/interfaz, pero **no prueba** que haya
  un receptor. Sólo un NavData válido recibido tras el datagrama de activación
  confirma al dron.
- Windows Defender Firewall puede permitir el envío y bloquear la respuesta
  UDP. La prueba debe distinguir “socket creado” de “telemetría recibida”.
- Dos procesos que intenten recibir el mismo puerto local pueden interferir. No
  se depende de semánticas ambiguas de `SO_REUSEADDR` entre POSIX y Winsock.
- VPN, Hyper-V/WSL y adaptadores virtuales pueden instalar rutas que compiten
  con `192.168.1.0/24`. Se informa la dirección local elegida y se diagnostica
  con `route print`/`Get-NetRoute`.

## Qué no se adopta de las referencias

- No se copia código ni se heredan sus licencias accidentalmente.
- No se considera “Windows compatible” sólo porque una biblioteca sea Python o
  JavaScript.
- No se envía takeoff, `AT*REF` de vuelo ni PCMD durante diagnóstico/monitor.
- No se mantiene indefinidamente una última orden ante pérdida de entrada o
  NavData.
- No se usa la recepción de cualquier datagrama como válida: debe superar la
  validación estructural y, cuando esté presente, de checksum.

