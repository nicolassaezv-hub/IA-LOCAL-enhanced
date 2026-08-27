# ASTRA

# Peticiones Personales

- Actualiza constantemente

- Sigue avanzando con la rama forex, consigue como minimo:

  - Integrar informe automatico en primera iteracion entre la rama forex y el servidor de flujo automatizado

- Configura el servidor VM  de Oracle Cloud a usar, aplica tests end-to-end para verificar viabilidad y finalizar la consolidacion del proyecto (Version Final)

- Usa herramientas para avanzar

   - ### Base44 (Integracion y testeo)
   - ### Replit (Integracion y planificacion)
   - ### Bolt.new (solo para crear borrador)
   - ### Lovable (Integracion y Planificacion)
   - ### Github Copilot (Diagnostico y Planificacion)
   - ### Claude (solo de diagnostico)
   - ### Codex CLI/Chatgpt (Integracion y testeo)

- Para comprobaciones de calidad de usuario (UX) o estetica consulta con Base44, asegurate de mencionar que la estetica es propia del Workspace en servidor (modificar HTML constantemente)
  
[Ir a integrar las nuevas implemetaciones listadas](Implementaciones%20futuras.md) una vez completado los test End-to-End de produccion

- Las actualizaciones ya NO SON por Roadmaps, se ingresan al listado de registro de integraciones

## Informacion General

Este Workspace IA esta hecha a partir de aportes estructurales de Nicolas Saez Valenzuela, Replit, Copilot, Chatgpt entre otros servicios digitales con tal de brindar una experiencia mas completa y complementada por modulos extensos con tal de concentrar una learning AI con fijacion en procesamiento de archivos y analisis intensivo de datasets del area del mercado FOREX (+ 40 Divisas,Cripto y Materias Primas).

Todo, en base a un sistema local PC de las siguientes especificaciones

PROCESADOR:

- Intel(R) Core (TM) I5-10300H CPU @2.5GHz

RAM:

- 16GB RAM

Se le asigna un máximo de 10GB de RAM a la IA

GPU:

- NVIDIA 1650ti 8GB VRAM

Asignacion maxima de 6GB VRAM

# API

## Actualmente el funcionamiento de esta IA es gracias a la conexion por GroqCloud

-  name: NICO'S LOCAL AI

-  ID: "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"

-  model= "openai/gpt-oss-120"

 # Configuracion VM
   
Para automatizar la rama FOREX de forma activa y crear la base del display grafico se logro migrar el Workspace a una VM (Virtual Machine) para optimizar tiempos de ejecucion del Pipeline

  - Imagen: Ubuntu 24.04
  
  - Sistema Operativo: Canonical Ubuntu
  
  - Memoria: 12GB RAM
  
  - Almacenamiento: 57 GB

En la comparativa practica se demostro que la "prediccion completa" de un solo simbolo tomaba entre 7-15 minutos, hubo una rebaja a 9 minutos usando una implementacion caché.

Sin embargo no es una optimizacion acertada al sistema completo si tomamos en cuenta que en hay mas de 50 Simbolos (Divisa,Commodities y Cripto)

### *HASTA EL MOMENTO SOLO HAY TESTS. NINGUNA ACTIVIDAD 24/7 HASTA COMPROBAR LA FIABILIDAD PRODUCTIVA*

### *(Scheduler,Rolling Dataset y Watcher desactivados)*

# Estructura

Esta IA Local se compone de mas de 200 codigos Python para asegurar eficiencia y rapidez en la ejecucion.
El programa puente (astra.py) viene siendo la central de los comandos ingresados para ser rediregido a funciones/herramientas de utilidad.
Las ramas actuales son las siguientes:

## CORE

- Cognitive Core

- Evolution Engine

- Customization Bar

## FOREX

- Principal Prediction Pipeline
--CSV builder
--MTF Fuser (H1/H4/D1)
--TUNER
--TRAINER
--DOUBLE ACTION VERIFIER

- Scheduler

- Watcher

- Activity Center

## PREDICTION LAB

- Prompt Analyzer

- Check-in design bar

- Status deployer

- Feedback-to-form Engine

## BUSINESS

- Prompt Analyzer


# Diagnostico Integro del sistema

Se incluyen 3 códigos adicionales para verificar la integridad de los módulos presentes en cada codigo Python.

- check_startup

- check_skeleton

- check_pipeline

El Proyecto ejecutado tanto en CLI como server tambien tiene implementado un comando de autoanalisis

- astra doctor

# Requisitos Obligatorios

Para correr el sistema Workspace ASTRA se debe OBLIGATORIAMENTE seguir estos pasos

## 0. Instalar Python y Pip

'''bash
pip install
'''

## 1.Instalar localmente el proyecto:

Descargas el proyecto y una vez dentro de la carpeta, haz click derecho y entras a la terminal.

```bash
cd C:/.../IA-LOCAL-enhanced
```

## 2.Instalar y activar entorno virtual:

Instalacion es por

```bash
python -m venv venv
```
Una vez completado procede a activarlo

'''bash
venv/venv activate.bat
'''

## 3.Descargar dependencias:

```bash
pip install -r requirements.txt
```

# Inicialización

Una vez cumplido los requisitos obligatorios se puede correr el workspace las veces que se quiera. Aqui las dos maneras

## a. Inicializar astra.py (CLI)

'''bash
python astra.py
'''

## b. Inicializar server (HTML)

'''bash
python workspace/server.py
'''

A continuacion se dan las caracteristicas y detalles del programa principal mas los anexos.

# Comandos y Programa Puente (astra.py + .env)

### Comandos

El nucleo del esqueleto organiza las entradas del usuario y repone todo en una funcion general, en esta funcion principal estan seccionados los comandos

### COMANDOS FOREX ESTAN DESHABILITADOS HASTA IMPLEMENTAR SWITCH DE EJECUCION DE LA RAMA (Ref. Implementaciones Futuras)

<details>
<summary>Ver comandos</summary>
  
### Sistema y diagnóstico

| Comando | Qué hace |
|---|---|
| `ayuda` | Referencia de comandos dentro del CLI |
| `astra doctor` | Diagnóstico completo (10 categorías) + informe en `reports/` |
| `self-test` | Diagnóstico semáforo rápido (VI.2) |
| `analiza astra` | Reporte completo de autoanálisis del sistema |
| `estado pc` | CPU, RAM, disco y uptime |
| `fecha` | Fecha y hora actual del sistema |
| `json` | Demo de serialización JSON |
| `gui` | Lanza la mini GUI local |
| `imagen` | Demo de detección de bordes (scikit-image) |
| `barra progreso` | Demo de barra de progreso |
| `tabla <datos>` / `rich <texto>` | Salida formateada en tabla / Rich |
| `simular click` / `simular tecla <k>` | Automatización de escritorio |
| `monitor archivos <ruta>` | Vigila cambios en archivos |
| `monitor historial` | Historial de snapshots de rendimiento |
| `dev log` | Últimas entradas del historial de desarrollo |
| `dev log add [tipo] título \| detalle` | Añade entrada (`feature`, `bugfix`, `optimization`, `refactor`, `docs`, `release`) |
| `dev log release <versión>` | Release notes de una versión |
| `api start` / `api stop` / `api status` | API REST interna legada (`http://localhost:8766`) |

### Forex Lab — flujo principal

| Comando (alias español) | Qué hace |
|---|---|
| `train forex <csv>` (`entrenar forex`) | Entrena el ensemble XGB + LGBM + RF |
| `tune forex <csv>` (`afinar forex`) | Búsqueda de hiperparámetros con Optuna (5-15 min) y entrena |
| `predict forex <csv>[,<csv2>...]` (`predecir forex`) | Señal BUY/SELL/HOLD; con varios CSV guarda un `.txt` por par en `reports/` |
| `multi forex <csv>` (`multihorizonte forex`) | Consenso a 3 horizontes (5/10/20 velas) |
| `backtest forex <csv>` | Backtest sobre datos retenidos |
| `full forex <csv>` (`completo forex`) | Train + Predict + Backtest en una pasada |
| `scan forex <carpeta\|csvs>` (`escanear forex`) | Escanea CSVs y rankea señales por fuerza |
| `analiza forex <csv> <símbolo>` | Informe técnico completo (RSI/MACD/EMA/ATR…) |
| `generar csvs forex [tf] [n]` | Genera CSVs en lote (Yahoo real → sintético como respaldo). Alias: `generate forex csvs`, `generar todos los csvs forex` |
| `lista mercados` | Pares y materias primas soportados |
| `mercados analizados` | Mercados analizados alguna vez |
| `historial forex <símbolo>` (`forex history`) | Historial de análisis guardados |
| `compara forex <símbolo>` | Compara los últimos 5 análisis del par |
| `mis modelos` / `info modelo <par>` | Modelos entrenados y detalle de uno |
| `schedule forex <csv> [min]` / `schedule run <par>` / `schedule stop [par]` | Análisis recurrente programado |

### Watcher y señales

| Comando | Qué hace |
|---|---|
| `watch forex <par> <csv> [seg]` | Monitoreo continuo del par en background |
| `watch check <par>` | Fuerza una evaluación inmediata |
| `watch status` | Pares en monitoreo |
| `watch stop <par>` / `watch stop all` | Detiene uno o todos los watchers |
| `señales [par]` (`signals`) | Historial de señales BUY/SELL/HOLD |
| `stats señales [par]` | Ratio y estadísticas de señales |

### Motor de decisión avanzado

Todos estos módulos se ejecutan **también de forma automática** dentro de
`predict forex` / `full forex`: el pipeline construye el contexto (volatilidad,
régimen, coherencia MTF, circuit breaker, noticias, histórico real) y el
Decision Engine puede **vetar** la señal del modelo. Los comandos siguientes
permiten inspeccionar cada pieza por separado.

| Comando | Fase | Qué hace |
|---|---|---|
| `quality <csv> [par] [tf]` | V.5 | Gate de calidad del dataset |
| `regime <csv> [par] [tf]` | V.4 | Detección de régimen de mercado |
| `mtf <d1.csv> <h4.csv> <h1.csv>` | V.3 | Coherencia multi-timeframe D1→H4→H1 |
| `reliability <conf> [signal]` | V.8 | Reliability Score (7 factores, 0-100) |
| `decision <signal> <conf>` | V.1 | Motor de decisión final (BUY/SELL/HOLD/NO_OPERAR) |
| `risk <BUY\|SELL> <entry> <atr>` | V.2 | SL/TP + position sizing (Kelly) |
| `backtest <modelo> <csv> [par]` | V.9 | Backtesting con 20+ métricas y Walk-Forward |
| `feature_importance <modelo> <csv>` | V.6 | Importancia de features (SHAP) |
| `dataset_update <par> [tf]` | V.11 | Actualización incremental del CSV |
| `scheduler_status` | V.12 | Estado del scheduler inteligente |
| `retrain_check <par>` / `retrain_history` | V.13 | Reentrenamiento adaptativo |
| `sentinel_status` / `sentinel_signals [par] [n]` | V.10 | Market Sentinel y su historial |
| `outcome_stats [par]` / `outcome_history` | V.14 | Resultados reales de las predicciones |
| `notify_test <par> <signal> <r>` / `notify_log` | V.15 | Notificaciones multi-canal |
| `portfolio_ranking [signal] [min]` / `portfolio_export` | V.18 | Ranking multi-activo y exportación |
| `news <par>` / `noticias <par>` / `noticias predice <par>` | V.16 | Sentimiento de noticias financieras |

### Data intelligence y Autonomía

| Comando | Qué hace |
|---|---|
| `descargar datos <par> [tf] [n]` | Descarga Forex/Cripto (Yahoo / Binance / MT5) |
| `migrar csv <ruta> [par] [tf]` | Migra un CSV al formato rolling |
| `escanear csvs` / `csvs activos` | Escanea e indexa los CSVs de `CSVs/` |
| `rolling info <par> [tf]` | Estado del RollingDataset |
| `candlestick <csv>` | Patrones de vela japonesa |
| `hparam cache` / `hparam invalidar <par>` | Caché de hiperparámetros |
| `model cache` | Estado del Model Cache Manager |
| `adaptive budget <par>` | Historial de budgets adaptativos |
| `quality history` | Precisión verificada por modelo |
| `opportunity ranking [n]` | Top N BUY/SELL por Opportunity Score |
| `scheduler start` / `scheduler stop` / `scheduler info` | Scheduler autónomo |
| `auto update` | Actualiza ahora todos los CSVs activos |

### Gestión de riesgo

| Comando | Qué hace |
|---|---|
| `circuit status` / `circuit reset` | Circuit breaker (pérdida diaria/semanal/drawdown) |
| `position size <par> [balance]` (`sizing`) | Tamaño de posición con criterio Kelly |

### Business Intelligence (PYME)

| Comando | Qué hace |
|---|---|
| `consulta negocio <csv>` (`consultar negocio`) | Consultoría completa: KPIs + forecast + recomendaciones |
| `analiza negocio <csv>` (`analizar negocio`) | KPIs + health score + alertas (sin ML) |
| `predice negocio <csv>` (`predecir negocio`) | Forecast ML: ¿crece o cae el próximo periodo? |
| `entrena negocio <csv>` (`entrenar negocio`) | Entrena modelo sobre tu dataset de negocio |
| `forecast negocio <csv> [meses]` | Proyección optimista / esperada / conservadora |
| `diagnóstico pyme <csv>` | Scorecard financiero + crecimiento + riesgo |
| `plan de accion <csv>` | 5 recomendaciones priorizadas (Llama) |
| `que pasa si <escenario> <csv>` | Simulación what-if con tabla antes/después |
| `si aumento ventas <csv> 20%` / `si reduzco costos <csv> 15%` | Simulaciones rápidas |

### Prediction Lab 

| Comando | Qué hace |
|---|---|
| `lab analiza "<idea>"` | Extrae el ProblemSpec de una idea en lenguaje natural |
| `lab dataset <csv> [target]` | Calidad, señal y VIF del dataset |
| `lab viabilidad <csv> "<idea>"` | Índice de viabilidad 0-100 |
| `lab planea <csv> "<idea>"` | Plan de modelo: algoritmos, features, validación |
| `lab genera <csv> "<idea>"` | Genera el `Pipeline` sklearn ejecutable |
| `lab valida <csv> "<idea>"` | Entrena y valida (holdout / k-fold / WFV) |
| `lab reporte <csv> "<idea>"` | Corre 5.1→5.6 y guarda el informe |
| `lab info proyecto <nombre>` | Detalle de un proyecto del lab |

### Proyectos y tareas

| Comando | Qué hace |
|---|---|
| `mis proyectos` | Lista los proyectos registrados |
| `nuevo proyecto <nombre> <desc>` | Crea un proyecto |
| `cerrar proyecto <nombre>` / `pausar proyecto <nombre>` | Cambia el estado |
| `tareas [proyecto]` | Tareas pendientes |
| `nueva tarea <proyecto> \| <desc>` | Crea una tarea |
| `completar tarea <id>` | Marca la tarea como completada |

### Evolution Engine, Constitution y feedback

| Comando | Qué hace |
|---|---|
| `reglas ver` | Reglas constitucionales activas |
| `evolucionar` / `evolucionar ciclo` / `evolucionar ciclo auto` | Genera y ejecuta ciclos evolutivos |
| `evolucion historial` | Historial de ciclos |
| `propuestas ver` | Propuestas pendientes |
| `propuesta validar\|aprobar\|rechazar\|aplicar <id>` | Flujo de aprobación manual |
| `audit ver` | Auditoría de cambios |
| `rollback ver` / `rollback aplicar <id>` | Puntos de rollback |
| `salud sistema` / `mejoras detectar` / `monitor snapshot` | Salud y oportunidades de mejora |
| `feedback ver <id>` / `feedback votar <id> <voto>` | Feedback sobre resultados |
| `feedback analisis` / `feedback dashboard` | Análisis y dashboard de feedback |
| `thresholds ver` / `contextual memoria` | Umbrales adaptativos y memoria contextual |

### Despliegue y robustez

| Comando | Qué hace |
|---|---|
| `deploy check` | Pipeline + Deployment + Readiness en un paso |
| `deploy readiness` (`deploy readiness check`) | Solo Production Readiness Report |
| `deploy verify` / `deploy history` / `deploy reports` | Verificación, historial y listado de informes |
| `robustness check` (`robustez check`) | Dependencias Python / paquetes / sistema |
| `robustness data` | Integridad de CSVs (filas, huecos, duplicados) |
| `robustness models` | Carga, features y antigüedad de los modelos |
| `robustness recovery` | Historial de eventos de recuperación |
| `robustness provider` | Proveedor cloud detectado |
| `robustness benchmark` | Rendimiento del pipeline |
| `robustness wizard` | Asistente de primera ejecución |
| `robustness all` | Todos los checks |

> Todos los comandos `robustness *` tienen alias en español `robustez *`.

### Documentos, web, audio y utilidades

| Comando | Qué hace |
|---|---|
| `lee pdf\|word\|excel\|csv <ruta>` | Lectura de documentos |
| `analiza csv <ruta>` | Estadísticas completas de un CSV |
| `escribe pdf\|word\|excel\|csv <ruta> <contenido>` | Creación de documentos |
| `crear pdf <ruta> <texto>` | PDF vía ReportLab |
| `grafica csv <ruta>` | Gráfico a partir de un CSV |
| `extrae web <url>` | Scraping de texto |
| `traducir <texto>` | Traducción al inglés |
| `youtube <url>` / `descargar audio youtube <url>` | Descarga de vídeo / audio |
| `httpx demo`, `aiohttp demo`, `socketio demo`, `fastapi demo`, `flask demo` | Demos de red |
| `voz a texto` / `texto a voz <texto>` | STT / TTS |
| `analiza audio <ruta>` / `reproducir audio <ruta>` / `convertir audio <ruta>` | Audio |
| `crea py <ruta>` / `analiza codigo [archivo…]` | Generación y análisis de código |
| `torch demo`, `tensorflow demo`, `keras demo`, `sklearn demo`, `integral` | Demos ML / simbólico |
| `memoria buscar <texto>` / `que hice con <tema>` / `historial <tema>` | Memoria y trazabilidad |
| `redis set\|get`, `sqlalchemy usuario`, `faiss add\|search`, `llama add\|query` | Demos de memoria/DB |
| `hash pass`, `verify pass`, `passlib hash\|verify`, `crear jwt`, `verificar jwt`, `cifra archivo`, `bloquear archivo`, `paramiko demo` | Seguridad |

---
</details>

## CSVs Disponibles para Analisis y Prediccion Forex

 (UPDATED 23/06/2026) https://drive.google.com/drive/folders/16K6FPgHz6k_FQ6SBYFvOv-7XwaQXsRLm?usp=sharing
 
## Modulos (Instalados y/o Integrados)

Aqui el archivo con el listado de modulos Instalados e Integrados
 https://docs.google.com/spreadsheets/d/1I2JpcZ6_V_WUdXkkYkP7MZ1fgQcPW6y73xBbtZjOfHI/edit?usp=sharing

## Actualizacion de Modulos (Semanal)

## Ejemplos de Grafica Dataset de Prediction Lab

## Ejemplo de Ejecucion con Dataset de Forex



