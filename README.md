# AR.Drone 2.0 Controller (Windows, MVP-00/01)

Conectada al AR.Drone 2.0 real, la aplicación se limita a **diagnóstico y
telemetría**: no envía comandos de vuelo ni movimiento. El control por teclado
está disponible solo para el simulador local en loopback.

## Instalación (PowerShell)

```powershell
py -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
```

Encienda el dron, conéctese a su Wi-Fi y ejecute primero:

```powershell
python -m cli.ping
```

El resultado `Drone communication: OK` significa que se recibió y validó un
datagrama NavData; la mera creación de un socket UDP no se presenta como prueba
de que el dron esté accesible. Después inicie el monitor de solo lectura:

```powershell
python -m cli.monitor
```

Deténgalo con **Ctrl+C**. Consulte [la preparación de Windows](docs/windows_setup.md),
[el protocolo](docs/ardrone_protocol.md) y [las reglas de seguridad](docs/safety.md)
antes de probar con hardware.

## Pruebas offline

```powershell
python -m pytest
```

## Simulador local de protocolo

Se puede iniciar un emulador UDP en loopback para desarrollar la comunicación
sin un dron conectado:

Terminal 1:

```powershell
python -m simulator.udp_drone
```

Terminal 2:

```powershell
python -m cli.controller --simulator
```

El emulador produce NavData sintética, reconoce el handshake demo y modela la
respuesta cinemática a `REF`/`PCMD` recibidos en loopback. Consulte [su
funcionamiento y límites](docs/udp_simulator.md).

El controlador incluye el panel de telemetría y abre una vista 3D isométrica de
la trayectoria estimada. Si prefieres el monitor independiente, puedes
ejecutarlo en otra terminal:

```powershell
python -m cli.monitor --ip 127.0.0.1
```

