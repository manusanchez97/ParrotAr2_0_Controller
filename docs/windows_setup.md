# Preparación de Windows 10/11

## 1. Requisitos y entorno Python

Instale Python 3.12 (o la versión estable indicada por `pyproject.toml`) y abra
PowerShell o Windows Terminal en la raíz del repositorio:

```powershell
py -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

Si la política de ejecución impide activar el entorno, puede usar directamente
`.\.venv\Scripts\python.exe`; no es necesario reducir permanentemente la política
de seguridad. Referencia: [entornos virtuales de Python](https://docs.python.org/3/library/venv.html).

## 2. Conexión manual al dron

1. Retire las hélices durante las primeras pruebas de red o sitúe el dron en un
   área segura, con batería suficiente.
2. Encienda el AR.Drone 2.0 y espere su inicialización.
3. Desde el panel Wi-Fi de Windows, conéctese manualmente al SSID creado por el
   dron (habitualmente comienza por `ardrone2_`). El MVP no cambia adaptadores ni
   credenciales.
4. Acepte que esta red no proporciona Internet. Evite que Windows cambie a otro
   punto de acceso durante la prueba.

La dirección predeterminada documentada del dron es `192.168.1.1`; normalmente
su DHCP asigna al PC una dirección `192.168.1.x`. No configure una IP estática
salvo que el diagnóstico DHCP lo justifique.

## 3. Inspección de adaptadores, dirección y ruta

Ejecute, sin necesidad de privilegios elevados:

```powershell
ipconfig
Get-NetAdapter
Get-NetIPConfiguration
route print
```

Compruebe que el adaptador Wi-Fi está `Up`, tiene una IPv4 compatible y que una
ruta hacia `192.168.1.1` usa ese adaptador. Para una vista más precisa:

```powershell
Get-NetRoute -AddressFamily IPv4 |
  Sort-Object DestinationPrefix, RouteMetric |
  Format-Table DestinationPrefix, NextHop, InterfaceAlias, RouteMetric
```

`ping` es sólo una pista opcional:

```powershell
ping 192.168.1.1
```

Un timeout ICMP no demuestra que UDP falle. Asimismo, crear o “conectar” un
socket UDP no completa ningún handshake y no demuestra que el dron responda.
MVP-00 envía la activación de NavData y exige recibir un paquete NavData válido:

```powershell
python -m cli.ping
```

Después, el monitor no motriz se ejecuta con:

```powershell
python -m cli.monitor
```

Detenga ambos con `Ctrl+C`; deben cerrar sus sockets limpiamente.

## 4. VPN, rutas y adaptadores virtuales

Si la interfaz local mostrada por la aplicación no es la Wi-Fi del dron:

- desconecte temporalmente VPN que capture redes privadas;
- examine adaptadores de Hyper-V, WSL, Docker y software de virtualización;
- busque otra LAN que también use `192.168.1.0/24`;
- compare métricas con `Get-NetRoute` y confirme la ruta efectiva con
  `route print 192.168.1.1`.

No añada rutas permanentes a ciegas. Primero elimine el conflicto o ajuste la
configuración de la VPN siguiendo la política del equipo.

## 5. Windows Defender Firewall

Windows Defender Firewall conserva estado para UDP, pero una política, el
perfil de red o una regla corporativa puede impedir la recepción de NavData. Es
un indicio típico que:

- la ruta y dirección local sean correctas;
- el socket de comandos se cree y la activación se envíe;
- no llegue ningún NavData, o Wireshark lo vea entrar por Wi-Fi pero Python no;
- el programa funcione sólo al desactivar temporalmente el firewall.

Consulte perfil y reglas **sin modificarlas**:

```powershell
Get-NetConnectionProfile
Get-NetFirewallProfile
Get-NetFirewallRule -PolicyStore ActiveStore |
  Where-Object DisplayName -Match 'Python' |
  Format-Table DisplayName, Enabled, Direction, Action, Profile
```

También puede abrir `wf.msc` y revisar “Reglas de entrada”. La documentación de
Microsoft explica la [configuración de Windows Firewall](https://learn.microsoft.com/windows/security/operating-system-security/network-security/windows-firewall/configure) y recomienda mantenerlo habilitado.

**La aplicación nunca desactiva el firewall ni crea reglas automáticamente.**
Si una captura confirma que éste es el bloqueo, solicite al usuario/administrador
una excepción de entrada restringida al ejecutable del entorno virtual, UDP,
perfil y red local necesarios. Una regla amplia “permitir Python en cualquier
red” o desactivar todos los perfiles no es una solución aceptable. En equipos
gestionados, siga la política corporativa.

## 6. Conflictos de puerto y observación de sockets

No ejecute `cli.ping` y `cli.monitor` simultáneamente. Compruebe endpoints UDP:

```powershell
Get-NetUDPEndpoint | Sort-Object LocalPort
netstat -ano -p udp
```

Si aparece un PID ocupando el puerto local requerido:

```powershell
Get-Process -Id <PID>
```

No finalice procesos desconocidos. Cierre primero monitores anteriores y vuelva
a probar. Winsock puede devolver `WSAEADDRINUSE` si otro proceso conserva el
bind; el programa debe mostrar ese error, no reinterpretarlo como dron ausente.

## 7. Matriz de diagnóstico rápido

| Síntoma | Causa probable | Comprobación segura |
|---|---|---|
| IP local no es `192.168.1.x` | No conectado al SSID o DHCP incompleto | `ipconfig`, reconectar y esperar |
| Interfaz elegida es VPN/virtual | Ruta más específica o métrica menor | `Get-NetRoute`, `route print` |
| Socket abre pero NavData expira | UDP no confirma peer; firewall, ruta o dron | Wireshark + perfil firewall |
| `Address already in use` | Otro monitor ligado al puerto | `Get-NetUDPEndpoint`, `netstat -ano -p udp` |
| Datos llegan y el parser rechaza | Paquete truncado, cabecera/opciones/checksum | Guardar captura, no relajar validación |
| Funciona sólo con firewall apagado | Regla de entrada ausente/bloqueo por política | Reactivar firewall y crear excepción mínima manual |

## 8. Límites de validación

Las pruebas automatizadas pueden verificar formato y timeouts en cualquier SO,
pero la aceptación de MVP-00/MVP-01 requiere una sesión física en Windows
10/11, Python sobre Winsock y un AR.Drone 2.0. Debe registrarse versión de
Windows, versión de Python, perfil de firewall, interfaz local, firmware del
dron, duración y pérdidas observadas. Una ejecución en Linux o con paquetes
sintéticos no sustituye esa validación.

