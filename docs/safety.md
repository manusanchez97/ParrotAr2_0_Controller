# Seguridad operacional

## Advertencia y alcance

Un AR.Drone puede causar lesiones y daños. El software no sustituye el manual,
la inspección previa ni el juicio del piloto. Los MVP-00 y MVP-01 son de
diagnóstico/telemetría y **no deben mover motores**. Si durante estas pruebas los
motores reaccionan, desconecte la batería e investigue antes de continuar.

## Preparación para MVP-00/01

- Retire las hélices para pruebas de banco cuando sea razonable y mantenga a
  personas, animales, cabello y objetos sueltos lejos de ellas.
- Use batería en buen estado, carcasa adecuada al entorno y una zona ventilada,
  despejada y legal.
- Conecte el PC manualmente solo a la red del dron esperado. Confirme el IP de
  origen de la telemetría; no acepte datagramas arbitrarios como prueba del dron.
- No ejecute simultáneamente otra aplicación de pilotaje: puede competir por la
  sesión, los puertos o la secuencia de comandos.
- No cree automáticamente excepciones de firewall ni cambie rutas/adaptadores.
  Cualquier excepción debe ser consciente, limitada al ejecutable/red privada y
  revertida después de la prueba.
- Tenga acceso físico a la batería. La pérdida del programa o de Wi-Fi no
  garantiza por sí sola un estado seguro.

## Invariantes obligatorios para etapas de vuelo futuras

1. Nunca despegar automáticamente ni durante inicialización/reconexión.
2. Un despegue exige una acción humana explícita y telemetría válida reciente.
3. `EMERGENCY` tiene prioridad máxima; `LAND` tiene prioridad sobre movimiento.
4. La pérdida o antigüedad excesiva de input pone todos los ejes a cero.
5. La pérdida de NavData o Wi-Fi se detecta por plazos monotónicos.
6. Nunca se mantiene indefinidamente el último `PCMD`.
7. No se permite despegar sin NavData válida y estado compatible confirmado.
8. Nunca se infiere `LANDED` por silencio, timeout, arranque o reconexión.
9. Los ejes se limitan y validan; NaN, infinito o valores fuera de contrato se
   rechazan antes de codificar.
10. Una reconexión vuelve a un estado no armado: jamás reanuda automáticamente
    una intención de despegue o movimiento anterior.

## Máquina de estados prevista

```text
DISCONNECTED → CONNECTED → INITIALIZING → READY
                                         │
                                         ▼
                              TAKING_OFF → FLYING
                                              │
                                              ▼
                                         LANDING → READY

Desde cualquier estado aplicable: LINK_LOST, NAVDATA_LOST, ERROR, EMERGENCY
```

Los estados describen conocimiento confirmado, no deseos. En esta entrega solo
son observables conexión, recepción y pérdida de NavData; no se implementan las
transiciones de vuelo.

### Prioridades de arbitraje futuras

```text
EMERGENCY > LAND > neutralización por failsafe > movimiento > TAKEOFF
```

La acción de emergencia no es un “aterrizaje rápido”: el bit del protocolo puede
detener motores y provocar una caída. Debe exponerse claramente, requerir una
acción inequívoca y no reutilizarse como botón normal de parada. El borrado de
emergencia será una operación distinta y confirmada por telemetría.

## Pérdidas y datos inválidos

- Un paquete válido actualiza la instantánea y su marca monotónica.
- Un paquete truncado, con longitudes imposibles, checksum incorrecto o emisor
  inesperado se descarta y cuenta; no refresca el watchdog.
- Un timeout muestra `NavData LOST/WAITING`, conserva la última muestra solo para
  diagnóstico y la marca explícitamente como obsoleta.
- Un retorno del flujo no autoriza vuelo: requiere reinicialización segura y
  confirmación nueva de los estados pertinentes.
- Errores repetidos deben producir mensajes accionables sin bucles de reintento
  agresivos que inunden la red o consola.

Los umbrales concretos de vuelo se fijarán y probarán antes de MVP-03 a partir de
la documentación oficial y ensayos controlados. No se inventan valores en esta
fase.

## Watchdogs futuros

Habrá watchdogs independientes para input, recepción NavData, envío de comandos
y salud del bucle. Cada uno usará reloj monotónico, tendrá dueño y transición de
fallo explícitos, y será probado con reloj inyectable. El watchdog del dron no
reemplaza los failsafes locales. Un hilo bloqueado, suspensión de Windows o salto
de planificación no debe dejar una orden persistente.

## Lista de autorización antes del primer vuelo

- MVP-00 y MVP-01 validados repetidamente con hardware en Windows.
- Parser probado con paquetes normales, desconocidos, corruptos y truncados.
- Estado de batería, emergencia y vuelo interpretado y visible.
- Frecuencia, secuencia y watchdog AT verificados primero sin hélices.
- Botones de LAND y EMERGENCY ensayados y siempre accesibles.
- Pérdida de input, NavData, proceso y Wi-Fi ensayada de forma controlada.
- Área de vuelo despejada, observador si procede y plan de desconexión física.

No se avanza porque “parece funcionar”: cada puerta del roadmap requiere
evidencia y una forma de volver a un estado seguro.
