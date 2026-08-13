# ASTRA — perfil de la VM Oracle

Este documento registra únicamente los hechos estables que condicionan el
target productivo. Las IPs, OCIDs, hostnames, nombres de instancia, usuarios
administrativos y nombres/rutas de llaves SSH son metadata operacional: se
mantienen en el inventario privado del operador y no en el repositorio.

No es evidencia de que ASTRA esté desplegado o production-ready. La autoridad
del procedimiento y de sus resultados es
[`DEPLOYMENT.md`](DEPLOYMENT.md); readiness se calcula desde evidencia real en
cada ejecución.

## Perfil productivo actual

- Proveedor: Oracle Cloud Infrastructure (OCI).
- Shape: `VM.Standard.A1.Flex` (Oracle Ampere A1).
- Arquitectura: ARM64 / `aarch64`.
- Recursos asignados: 2 OCPU y 12 GB RAM.
- Sistema operativo: Ubuntu 24.04 LTS.
- Python: 3.12.
- Directorio de instalación por defecto: `/opt/astra`.
- Usuario de servicio: `astra` no-root, administrado por systemd.
- EnvironmentFile: `/etc/astra/astra.env`, protegido y fuera del repositorio.
- Bind HTTP por defecto: `127.0.0.1:8000`.
- Backup root dedicado: `/var/backups/astra`.

El instalador también admite `x86_64`, pero ARM64/aarch64 es el target primario.
El tamaño de esta VM describe la instancia objetivo; no es un requisito
universal para todo entorno de desarrollo.

## Red y acceso

ASTRA no publica `:8000` por defecto. Cualquier acceso desde Internet requiere
que el operador configure por separado reverse proxy HTTPS, DNS e ingress; el
repositorio no afirma que esos componentes estén implementados.

Ejemplo deliberadamente no operacional:

```bash
ssh -i <private-key-path> <admin-user>@<server-ip>
```

Nunca deben copiarse llaves privadas, credenciales o valores del EnvironmentFile
a este documento.
