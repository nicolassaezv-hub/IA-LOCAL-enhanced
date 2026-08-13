# Despliegue de ASTRA en Ubuntu 24.04 ARM64

Este documento describe el contrato operativo de `infra/deploy.sh`. El target
primario es Ubuntu 24.04, `aarch64`, Python 3.12 y systemd. El mismo instalador
acepta `x86_64`, pero no contiene rutas, wheels ni paquetes exclusivos de esa
arquitectura.

## Flujo y resultados

```text
infra/deploy.sh
  PRECHECK
    -> DEPENDENCIES
    -> FILESYSTEM
    -> CONFIGURATION
    -> PYTHON_DEPENDENCIES
    -> SYSTEMD
    -> START
    -> READINESS
```

Cada fase crítica debe terminar `PASS`. `START` exige que la unit esté activa y
que `GET /health` responda HTTP 200 con el JSON canónico `{"status":"ok"}`.
Eso demuestra salud del proceso, no readiness productiva.

- `SUCCESS` (exit 0): todas las fases y el readiness A08 pasaron.
- `DEPLOYED_NOT_READY` (exit 2): infraestructura y health pasaron, pero falta
  evidencia productiva real (por ejemplo datasets, modelos o provider probe).
- `FAILED` (exit 1): falló una fase crítica.

Readiness no crea datasets/modelos sintéticos. El probe de providers sólo se
ejecuta al usar `--probe-providers`.

## Primera instalación

El instalador no instala paquetes OS sin autorización explícita:

```bash
sudo -v
./infra/deploy.sh --install-system-packages
```

En la primera ejecución se crea `/etc/astra/astra.env`, sin secretos y con modo
`0640`, propietario `root:astra`. La fase `CONFIGURATION` falla hasta que un
operador establezca `ASTRA_API_KEY` en ese archivo. El valor no debe mostrarse
en consola, copiarse al repositorio ni incluirse en backups. Después se vuelve
a ejecutar el mismo comando. El env existente nunca se resetea.

El deploy acepta `ASTRA_HOME` sólo como directorio dedicado bajo `/opt/` o
`/srv/`; no acepta esos roots por sí mismos ni paths de sistema o de homes. El
`ASTRA_ENV_FILE` productivo debe ser un archivo bajo `/etc/astra/`. Ambas rutas
se validan, incluyendo traversal y escapes por symlink existentes, antes de
cualquier instalación o cambio recursivo de permisos.

La API queda en `127.0.0.1:8000`. `--allow-public-http` sólo habilita una
configuración de bind público que el operador ya haya escrito; no abre firewall,
OCI ingress, DNS ni TLS. Para Internet todavía se requiere un reverse proxy HTTPS
y una política de ingress administrados por separado.

## Identidad y filesystem

```text
astra:astra (nologin, sin sudo)
  -> código y venv: root:root, sin escritura del servicio
  -> runtime escribible:
       memory_db/
       models/
       CSVs/
       workspace/uploads/
       reports/ y prediction/reports/
       logs/
       data/
       lab_reports/
       /var/log/astra/
       /var/backups/astra/
```

Los DB/índices históricos que en desarrollo viven en la raíz se redirigen en
producción mediante `ASTRA_MEMORY_DB_PATH`, `ASTRA_HPARAM_DB_PATH` y
`ASTRA_CSV_INDEX_PATH`. El estado del Circuit Breaker se redirige mediante
`ASTRA_CIRCUIT_BREAKER_STATE_PATH`. Los defaults locales previos se preservan.

`forex/data/` contiene código fuente de providers y gestión de datasets; no es
un root de estado y permanece read-only. Los writers auditados persisten los
datasets en `CSVs/` o `data/forex/`, ambos roots runtime dedicados y escribibles.

Las units usan `ProtectSystem=strict`, `ProtectHome=true`, `PrivateTmp=true`,
`NoNewPrivileges=true`, `UMask=0027` y `ReadWritePaths` limitado. systemd es la
única autoridad de restart; `infra/monitor/supervisor.py` es diagnóstico.

## Backup y logging

`astra-backup.timer` ejecuta como `astra`. El backup:

1. crea staging privado dentro de `ASTRA_BACKUP_ROOT`;
2. obtiene snapshots con SQLite Backup API;
3. copia sólo estado explícito sin seguir symlinks;
4. genera manifest completo y SHA-256 por archivo;
5. verifica el archive;
6. lo publica por rename atómico;
7. aplica retención sólo a archives top-level del backup root.

`ASTRA_BACKUP_ROOT` debe ser absoluto, estar fuera del proyecto y ser un
directorio dedicado. Roots de filesystem/sistema como `/`, `/var`, `/opt`,
`/srv` o `/mnt` se rechazan antes de crear o modificar el directorio. El backup
incluye los datasets runtime de `CSVs/` y `data/forex/`, no el código fuente de
`forex/data/`.

Los env/secrets, venv, caches y código no se incluyen. No existe actualmente un
restore productivo canónico; cualquier restore debe validar manifest y archive
antes de sustituir estado y queda fuera de B3.

Los file logs de las units rotan con `create 0640 astra astra`; el monitor no
duplica handlers. `copytruncate` se conserva porque systemd mantiene abiertos
los destinos `StandardOutput=append`.

## Dependencias

- `requirements-core.txt`: servicio y utilidades obligatorias.
- `requirements-ml.txt`: Forex/ML productivo y ruta Yahoo para Linux.
- `requirements-optional.txt`: cloud clients, FAISS y otras features opt-in.
- `requirements-dev.txt`: tests/desarrollo.
- `constraints-py312.txt`: versiones directas observadas con Python 3.12.6.

El deploy usa requirements core+ML y constraints. No instala MetaTrader5 en
Linux. Torch, TensorFlow y FAISS no bloquean el arranque core.
