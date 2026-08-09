# ASTRA — Oracle Cloud VM

## 1. Información general

Servidor principal utilizado para ejecutar ASTRA de forma autónoma 24/7.

Fecha de creación:
- 08-08-2026

Proveedor:
- Oracle Cloud Infrastructure (OCI)

Región:
- Chile West / Valparaíso
- `sa-valparaiso-1`

Nombre de instancia:
- `astra-server`

Hostname observado mediante SSH:
- `astra-vnic`

Estado inicial:
- En ejecución


## 2. Hardware

Shape:
- `VM.Standard.A1.Flex`

Arquitectura:
- ARM64 / aarch64
- Oracle Ampere A1

OCPU:
- 2

RAM:
- 12 GB

Dominio de disponibilidad:
- AD-1

Dominio de errores:
- FD-1


## 3. Sistema operativo

Distribución:
- Ubuntu 24.04.4 LTS

Codename:
- `noble`

Arquitectura:
- `aarch64`

Kernel original:
- `6.17.0-1018-oracle`

Kernel instalado durante actualización inicial:
- `6.17.0-1019-oracle`

Imagen OCI:
- Canonical Ubuntu 24.04 Minimal aarch64

Build de imagen utilizado:
- `2026.07.17-0`


## 4. Red

IP pública inicial:
- `147.224.238.55`

IP privada:
- `10.0.0.171`

VCN:
- `astra-vcn`

La instancia utiliza:
- IPv4 privada automática
- IPv4 pública
- Sin IPv6

Acceso administrativo:
- SSH


## 5. Acceso SSH

Usuario:
- `ubuntu`

Comando utilizado desde Windows PowerShell:

```powershell
ssh -i ".\ssh-key-2026-08-08 (2).key" ubuntu@147.224.238.55