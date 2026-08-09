# ASTRA v7.0 — Workspace Edition
**Sistema AI Modular · Consultor PYME · Forex Intelligence**

Este archivo es la copia del `replit.md` raíz dentro del proyecto ASTRA.
La versión canónica está en `../../replit.md` (raíz del monorepo).

---

## Arranque rápido (Replit)

Dos workflows se inician automáticamente:

1. **"ASTRA AI"** — CLI de terminal: `cd artifacts/astra && python main.py`
2. **"artifacts/api-server: ASTRA Workspace"** — Workspace web en el panel Preview (FastAPI en puerto 8080)

La API key `GROQ_API_KEY` ya está configurada en Replit Secrets.

## Arranque rápido (Windows local)

```cmd
:: CLI
cd artifacts\astra
python main.py

:: Workspace web
cd artifacts\astra
pip install fastapi uvicorn python-multipart
python workspace\server.py
:: → http://localhost:8000
```

## Diagnóstico
```bash
cd artifacts/astra
python check_startup.py     # rápido
python astra_doctor.py      # completo (10 categorías)
```

## Documentación completa
- `MANUAL.md` — Manual completo de usuario (v7.0)
- `docs/ORACLE_CLOUD.md` — Despliegue en Oracle Cloud
- `FOREX_USER_GUIDE.md` — Guía específica de Forex
- `docs/GUIA_CSV.md` — Formato de CSVs aceptados

## Workspace — Paneles disponibles
Chat · Forex Lab · Prediction Lab · Business Lab · Cognitive Core · Evolution Engine · Activity Center · Dashboard Activo · Configuración

## Stack
- Python 3.11 · FastAPI + uvicorn · Groq (Llama-3.3-70B)
- ML: XGBoost + LightGBM + scikit-learn + Optuna
- Memoria: SQLite (memoria.db + especializados) · Redis/FAISS opcionales
