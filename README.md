# AR.Drone 2.0 Controller (Windows, MVP-00/01)

Aplicación **solo de diagnóstico y telemetría** para un PC Windows conectado
manualmente al punto de acceso Wi-Fi de un Parrot AR.Drone 2.0. Esta versión no
incluye ningún comando de vuelo, movimiento ni vídeo.

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

