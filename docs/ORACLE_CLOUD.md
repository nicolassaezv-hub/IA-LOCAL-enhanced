# ASTRA en Oracle Cloud Always Free — Guía de Despliegue

> Estado actual: **Preparado** — los módulos están listos para Oracle Cloud.
> El despliegue en sí es un paso manual del usuario.

---

## Arquitectura para Oracle Cloud

```
┌─────────────────────────────────────────────┐
│         Oracle Cloud VM (Always Free)        │
│  Ubuntu 22.04 LTS | 4 OCPUs | 24 GB RAM     │
│                                              │
│  ┌──────────────────────┐                   │
│  │  ASTRA Core          │ ← Python 3.11     │
│  │  (main.py / CLI)     │                   │
│  └──────────┬───────────┘                   │
│             │                               │
│  ┌──────────▼───────────┐                   │
│  │  AutonomousScheduler │ ← systemd service  │
│  │  H1/H4/D1 cycles     │                   │
│  └──────────┬───────────┘                   │
│             │                               │
│  ┌──────────▼───────────┐                   │
│  │  ASTRA API Server    │ ← puerto 8766     │
│  │  (astra_api.py)      │                   │
│  └──────────┬───────────┘                   │
│             │                               │
│  ┌──────────▼───────────┐                   │
│  │  Nginx Reverse Proxy │ ← puerto 443/80   │
│  │  + SSL (Let's Encrypt)│                  │
│  └──────────────────────┘                   │
└─────────────────────────────────────────────┘
              │
              ▼ HTTPS API
┌─────────────────────────────┐
│  Workplace (Replit / Local) │
│  Consulta predicciones,     │
│  rankings, estado del sistema│
└─────────────────────────────┘
```

---

## Pasos de despliegue en Oracle Cloud

### 1. Crear la VM (Oracle Cloud Console)

1. Iniciar sesión en https://cloud.oracle.com
2. **Compute → Instances → Create Instance**
3. Configuración:
   - Shape: `VM.Standard.A1.Flex` (ARM) — **Always Free**: 4 OCPUs, 24 GB RAM
   - OS: Ubuntu 22.04 LTS (ARM)
   - Storage: 50 GB (Always Free)
4. Añadir tu clave SSH pública
5. Guardar la IP pública de la VM

### 2. Instalar Python y dependencias

```bash
ssh -i ~/.ssh/id_rsa ubuntu@<IP_PUBLICA>

# Actualizar sistema
sudo apt update && sudo apt upgrade -y
sudo apt install -y python3.11 python3.11-venv python3-pip git libgomp1 nginx

# Crear directorio de trabajo
mkdir -p /opt/astra && cd /opt/astra

# Clonar/transferir el proyecto
# Opción A: scp desde tu máquina local
scp -r ./artifacts/astra ubuntu@<IP>:/opt/astra/

# Crear entorno virtual
python3.11 -m venv venv
source venv/bin/activate

# Instalar dependencias
pip install pandas numpy scikit-learn xgboost lightgbm optuna openai requests
pip install colorama rich orjson filelock psutil yfinance
pip install matplotlib seaborn openpyxl PyPDF2 python-docx pdfplumber
pip install faiss-cpu arrow tabulate watchdog schedule reportlab
pip install cryptography bcrypt PyJWT
```

### 3. Configurar variables de entorno

```bash
# Crear archivo de entorno
sudo nano /etc/environment
# Añadir:
GROQ_API_KEY="gsk_tu_key_aqui"
ASTRA_API_PORT="8766"

# O en el archivo .env dentro de /opt/astra/
echo "GROQ_API_KEY=gsk_tu_key_aqui" > /opt/astra/.env
echo "ASTRA_API_PORT=8766" >> /opt/astra/.env
```

### 4. Crear servicio systemd para el Scheduler

```bash
sudo nano /etc/systemd/system/astra-scheduler.service
```

```ini
[Unit]
Description=ASTRA Autonomous Scheduler
After=network.target
StartLimitIntervalSec=0

[Service]
Type=simple
User=ubuntu
WorkingDirectory=/opt/astra
Environment=LD_LIBRARY_PATH=/usr/lib/aarch64-linux-gnu:/usr/local/lib
Environment=PYTHONPATH=/opt/astra
EnvironmentFile=/opt/astra/.env
ExecStart=/opt/astra/venv/bin/python /opt/astra/scheduler_service.py
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

```bash
sudo systemctl daemon-reload
sudo systemctl enable astra-scheduler
sudo systemctl start astra-scheduler
sudo systemctl status astra-scheduler
```

### 5. Crear servicio systemd para la API

```bash
sudo nano /etc/systemd/system/astra-api.service
```

```ini
[Unit]
Description=ASTRA Internal REST API
After=network.target astra-scheduler.service

[Service]
Type=simple
User=ubuntu
WorkingDirectory=/opt/astra
Environment=PYTHONPATH=/opt/astra
Environment=ASTRA_API_PORT=8766
EnvironmentFile=/opt/astra/.env
ExecStart=/opt/astra/venv/bin/python /opt/astra/astra_api.py
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
```

```bash
sudo systemctl enable astra-api
sudo systemctl start astra-api
```

### 6. Configurar Nginx como proxy HTTPS

```bash
sudo nano /etc/nginx/sites-available/astra
```

```nginx
server {
    listen 80;
    server_name <IP_PUBLICA>;

    location /api/astra/ {
        proxy_pass http://127.0.0.1:8766;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        add_header 'Access-Control-Allow-Origin' '*' always;
    }
}
```

```bash
sudo ln -s /etc/nginx/sites-available/astra /etc/nginx/sites-enabled/
sudo nginx -t && sudo systemctl reload nginx
```

### 7. Verificar funcionamiento

```bash
# Health check
curl http://<IP>:8766/api/astra/health

# Estado del sistema
curl http://<IP>:8766/api/astra/status

# Ranking de oportunidades
curl http://<IP>:8766/api/astra/ranking
```

---

## Archivo `scheduler_service.py` (para el servicio systemd)

```python
"""Punto de entrada para el Scheduler como servicio independiente."""
import sys, os, time, logging
sys.path.insert(0, os.path.dirname(__file__))
logging.basicConfig(level=logging.INFO)

from forex.scheduler.autonomous_scheduler import get_scheduler
from forex.scheduler.auto_updater import get_auto_updater

if __name__ == "__main__":
    scheduler = get_scheduler()
    updater = get_auto_updater()

    # Registrar tarea de actualización de datasets (cada hora)
    scheduler.add_job_seconds(
        "update_h1_datasets",
        interval_s=3600,
        fn=lambda: updater.update_all(bars_fetch=10)
    )

    # Registrar tarea de actualización H4 (cada 4 horas)
    scheduler.add_job_seconds(
        "update_h4_datasets",
        interval_s=14400,
        fn=lambda: updater.update_all(bars_fetch=5)
    )

    print("Scheduler iniciado. Ctrl+C para detener.")
    scheduler.start(daemon=False)  # blocking

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        scheduler.stop()
        print("Scheduler detenido.")
```

---

## Endpoints de la API disponibles

| Endpoint | Método | Descripción |
|----------|--------|-------------|
| `/api/astra/health` | GET | Health check básico |
| `/api/astra/status` | GET | Estado completo del sistema (CPU, RAM, scheduler) |
| `/api/astra/predictions` | GET | Predicciones recientes (param: `pair`, `limit`) |
| `/api/astra/ranking` | GET | Top BUY/SELL por OpScore (param: `top_n`) |
| `/api/astra/outcomes` | GET | Estadísticas de outcomes (param: `pair`) |
| `/api/astra/history` | GET | Historial de calidad de modelos (param: `limit`) |
| `/api/astra/datasets` | GET | Lista de datasets activos |
| `/api/astra/scheduler` | GET | Estado del scheduler autónomo |
| `/api/astra/doctor` | GET | Diagnóstico completo del sistema |
| `/api/astra/signal` | POST | Enviar señales activas para el ranking |
| `/api/astra/state` | POST | Actualizar estado del sistema |

---

## Sincronización Workplace ↔ Oracle Cloud

El Workplace (Replit) puede consultar la API de Oracle Cloud directamente:

```javascript
// En el frontend del Workplace
const ORACLE_API = "http://<IP_ORACLE>:8766"

async function getRanking() {
    const res = await fetch(`${ORACLE_API}/api/astra/ranking`)
    return res.json()
}

async function getStatus() {
    const res = await fetch(`${ORACLE_API}/api/astra/status`)
    return res.json()
}
```

O a través del proxy del api-server de Replit (recomendado para CORS):
```
GET /api/astra/ranking  → proxy a Oracle Cloud
GET /api/astra/status   → proxy a Oracle Cloud
```
