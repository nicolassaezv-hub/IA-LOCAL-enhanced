# ASTRA v7.0.2-prod — Reporte de Auditoría Completa

> **Registro histórico de v7.0.2-prod.** No define la versión actual ni prueba
> readiness/deployment del checkout actual; la versión canónica está en
> `astra_version.py` y readiness se recalcula desde evidencia real.
**Fecha:** 2026-08-04  
**Auditor:** Análisis automatizado con 7 sub-agentes en paralelo  
**Cobertura:** 338 archivos totales, 175 módulos Python activos, 46,387 líneas de código

---

## 1. RESUMEN EJECUTIVO

El proyecto ASTRA v7.0.2-prod está **casi completo**. Se analizaron los 338 archivos del ZIP, leyendo cada línea de cada archivo Python activo. Se identificaron y corrigieron problemas en `MANUAL.md` y `requirements.txt`.

---

## 2. CORRECCIONES APLICADAS A requirements.txt

### Paquetes añadidos (faltaban, importados en código activo):
| Paquete | Import | Ubicación | Razón |
|---|---|---|---|
| `PyYAML>=6.0` | `yaml` | `astra.py:302` | Importado en try/except, pero crítico para config |
| `imbalanced-learn>=1.2` | `imblearn` | `forex/xgb_trainer.py:47`, `forex/prediction/xgb_trainer.py:47`, `prediction_lab/validation_engine.py:218` | SMOTE en entrenamiento ML |
| `shap>=0.44` | `shap` | `forex/prediction/feature_importance.py:42` | Feature importance explicabilidad |
| `nltk>=3.8` | `nltk` | `nlp_tools.py` (8 ocurrencias) | Tokenización, sentimiento, POS tagging |
| `regex>=2024.0` | `regex` | `nlp_tools.py:22` | Regex avanzado para NLP |

### Paquetes movidos a sección opcional (comentados):
| Paquete | Razón |
|---|---|
| `aiofiles` | Nunca importado en código activo |
| `pytube` | Importado en try/except (web_tools, audio_video) |
| `websockets` | Importado en try/except (web_tools) |
| `websocket-client` | Importado en try/except (astra.py) |
| `pytest` | Solo usado en test_main.py |
| `torchvision`, `torchaudio`, `keras`, `h5py`, `imageio` | Faltaban en sección opcional |
| Cloud SDKs: `azure-storage-blob`, `azure-identity`, `google-cloud-storage`, `boto3` | Solo en try/except en cloud_tools.py |
| Windows-only: `MetaTrader5`, `PyQt5`, `dearpygui`, `kivy`, `pyautogui`, etc. | Documentados como excluidos para Linux |

### Paquetes que se mantienen (justificación):
| Paquete | Razón de mantener |
|---|---|
| `groq>=0.11.0` | Aunque se usa via OpenAI SDK, es el paquete recomendado para Groq |
| `python-multipart` | Dependencia implícita de FastAPI para UploadFile |
| `lxml>=4.9` | Backend opcional de beautifulsoup4 |
| `python-dotenv` | Útil para cargar .env aunque no se use actualmente |
| `lazy-loader` | Eliminado — conflicto con astra_lazy_loader.py local. **Nota: se mantuvo al final como dev utility para compatibilidad** |

---

## 3. CORRECCIONES APLICADAS A MANUAL.md

### Cambios de versión:
- `v6.0.1-prod` → `v7.0.2-prod` (alineado con CHANGELOG.md y VERIFICACION_COMPLETA.md)
- Fecha actualizada a 2026-08-04

### Correcciones de rutas:
- Eliminada referencia a `artifacts/astra/main.py` → `main.py` está en raíz
- Eliminada referencia a `artifacts/astra/` → no existe ese directorio
- `cd artifacts\astra` → removido (ejecutar desde raíz del proyecto)

### Correcciones de base de datos:
- `memory_db/astra_memory.db` (21 tablas) → `memory_db/astra_autonomous.db` (8 tablas)
- Tablas reales: predictions, scheduler_runs, supported_symbols, dataset_registry, model_quality, outcomes, config, sqlite_sequence
- Añadidas otras BDs: memoria.db, dev_log.db, analytics_memory.db, astra_hparam_cache.db

### Correcciones de estructura:
- "48 módulos" → "175 módulos Python"
- Estructura de archivos (PARTE 10) completamente reescrita con todos los directorios reales
- Añadidos: constitution/, evolution/, feedback/, prediction_lab/, notifications/, scheduler/, legacy/, CSVs/, forex_backup/, future_phases_draft/

### Contenido añadido:
- **PARTE 2 expandida**: +20 comandos Forex CLI (train, predict, scan, backtest, full, quality, regime, mtf, sentinel, portfolio_ranking, etc.)
- **PARTE 6 nueva**: Subsistemas internos (Constitution, Evolution, Feedback, Prediction Lab, Market Intelligence, SME)
- **PARTE 9 expandida**: Solución de problemas con módulos faltantes (PyYAML, imblearn, shap, nltk)
- Eliminada duplicación: PARTE 5 y PARTE 10 (viejo) eran idénticas → fusionadas en PARTE 5

### Correcciones de comandos:
- Añadidos comandos de Evolution Engine (evolucionar, reglas ver, rollback ver, mejoras detectar)
- Añadidos comandos de Feedback (feedback analisis, thresholds ver, contextual memoria)
- Añadidos comandos de Roadmap V (quality, regime, mtf, retrain_check, sentinel_status)
- Añadidos comandos de Roadmap VI (quality history, opportunity)

---

## 4. PROBLEMAS ENCONTRADOS EN EL CÓDIGO (no corregidos — requieren atención del desarrollador)

### CRÍTICO — Archivos mal nombrados en forex/ raíz:
Los archivos de business en `forex/` raíz tienen un "shift" de contenido:
- `forex/business_dataset_builder.py` contiene código de `business_csv_adapter.py`
- `forex/business_feature_engineering.py` contiene código de `business_dataset_builder.py`
- `forex/business_pipeline.py` contiene código de `business_feature_engineering.py`
- `forex/business_predictor.py` contiene código de `business_pipeline.py`
- `forex/kpi_engine.py` contiene código de `business_predictor.py`

**Nota:** Las versiones correctas existen en `forex/business/` subdirectorio. Los archivos en raíz de `forex/` son redundantes y tienen contenido desplazado.

### CRÍTICO — forex_backup/ contiene archivos corruptos:
- 3 archivos son bytecode `.pyc` guardados como `.py` (fatal syntax error)
- 10 archivos tienen contenido rotado/mal nombrado
- **Recomendación:** Eliminar todo el directorio `forex_backup/`

### CRÍTICO — future_phases_draft/ es obsoleto:
- 4 archivos son duplicados exactos de producción
- 21 archivos son drafts con bugs ya corregidos
- **Recomendación:** Eliminar todo el directorio `future_phases_draft/`

### BUGS MENORES en código activo:
- `main.py`: imports no usados (subprocess, project_memory functions, etc.)
- `astra.py`: import `csv` no usado
- `forex/indicators.py`: posible división por cero en `compute_mfi()`
- `forex/__init__.py`: mapeo de lazy import roto (apunta a `forex.prediction.*` en vez de `forex.*`)
- `astra_api.py`: HTTPServer single-threaded bloquea requests concurrentes
- `active_engine.py`: SQLite cross-thread puede causar `ProgrammingError`
- `argument_parser.py`: regex `[A-Z]{6}` puede confundir palabras españolas con pares Forex

### DEPENDENCIAS OPCIONALES documentadas:
28 paquetes adicionales se importan en try/except y no están en requirements.txt activo. Se documentaron en la sección "Optional" con instrucciones de instalación manual.

---

## 5. VEREDICTO

| Archivo | ¿Actualizado? | Cambios |
|---|---|---|
| **requirements.txt** | ✅ Sí | +5 paquetes activos, +20 paquetes opcionales documentados, reorganización |
| **MANUAL.md** | ✅ Sí | Versión, rutas, DB, estructura, comandos, subsistemas, troubleshooting |

### Lo que falta para "todo listo":
1. **Eliminar `forex_backup/`** (archivos corruptos y obsoletos)
2. **Eliminar `future_phases_draft/`** (subsistemas ya en producción)
3. **Corregir archivos mal nombrados en `forex/` raíz** (business_*.py con contenido desplazado)
4. **Arreglar `forex/__init__.py`** (mapeo de lazy import roto)
5. Opcional: limpiar imports no usados en main.py y astra.py

---

*Auditoría completada: 338 archivos analizados, 175 módulos Python verificados línea por línea*
