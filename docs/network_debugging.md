# Diagnóstico de red en Windows

Este MVP no depende de ICMP ni modifica el firewall. `python -m cli.ping` abre
los sockets UDP, envía el *trigger* NavData y solo declara comunicación correcta
tras recibir un paquete válido del dron.

## Wireshark

Capture en el adaptador Wi-Fi conectado al dron. Filtros de visualización útiles:

```text
ip.addr == 192.168.1.1
udp
udp.port == 5554
udp.port == 5556
ip.src == 192.168.1.1 && udp.srcport == 5554
```

Para MVP-01 debe verse primero un datagrama UDP de cuatro bytes (`01 00 00 00`)
hacia `192.168.1.1:5554`, seguido por datagramas desde el dron al puerto efímero
del PC. No capture tráfico de terceros y evite publicar capturas con datos de
otras redes.

## Herramientas incluidas en Windows

```powershell
Get-NetUDPEndpoint | Sort-Object LocalPort
netstat -ano -p udp
Get-NetRoute -AddressFamily IPv4 | Sort-Object RouteMetric
Test-NetConnection 192.168.1.1 -InformationLevel Detailed
```

`Test-NetConnection` ayuda a observar ruta/interfaz, pero una prueba TCP o ICMP
fallida no demuestra por sí sola que NavData UDP esté roto. La evidencia decisiva
es el intercambio UDP del protocolo.

## Árbol de diagnóstico

1. Sin trigger saliente: confirme conexión Wi-Fi, ruta, VPN y dirección objetivo.
2. Trigger visible, sin respuesta: cierre otros clientes del dron, reinícielo y
   revise que la captura esté en el adaptador correcto.
3. Respuesta visible en Wireshark, pero la aplicación expira: sospeche del perfil
   de red o Windows Defender Firewall; siga el procedimiento manual descrito en
   `windows_setup.md`. La aplicación nunca crea excepciones automáticamente.
4. Paquetes recibidos pero rechazados: conserve una captura y use los mensajes
   de checksum/longitud del parser para distinguir corrupción de formato nuevo.
5. Flujo que se detiene: busque cambio de red, ahorro de energía del adaptador,
   otro cliente y pérdida de señal. El cliente reenvía el trigger tras un timeout.

## Referencias

- [Wireshark: filtros de visualización](https://www.wireshark.org/docs/wsug_html_chunked/ChWorkBuildDisplayFilterSection.html)
- [Microsoft: Get-NetUDPEndpoint](https://learn.microsoft.com/powershell/module/nettcpip/get-netudpendpoint)
- [Microsoft: solución de problemas de Windows Firewall](https://learn.microsoft.com/troubleshoot/windows-client/networking/windows-firewall-troubleshooting)

