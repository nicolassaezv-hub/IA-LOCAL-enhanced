# intent_router.py

import re

# ==========================================
# PALABRAS CLAVE
# ==========================================

INTENT_PATTERNS = {

    "document_read": [
        "lee pdf",
        "leer pdf",
        "lee word",
        "leer word",
        "lee excel",
        "leer excel",
        "lee csv",
        "leer csv",
        "abrir documento",
        "leer documento",
    ],

    "document_summary": [
        "resume pdf",
        "resume documento",
        "resumen pdf",
        "analiza pdf",
        "explica pdf",
    ],

    "translation": [
        "traduce",
        "traducir",
        "translate",
    ],

    "web_search": [
        "extrae web",
        "buscar web",
        "consulta web",
        "investiga",
        "busca informacion",
    ],
    
    "business_analysis": [
        "analiza negocio",
        "analizar negocio",
        "analiza empresa",
        "analizar empresa",
        "analiza ventas",
        "analizar ventas",
        "kpi",
        "kpis",
        "business analysis",
        "analyze business",
        "analyse business",
        "business intelligence",
        "análisis financiero",
        "analisis financiero",
        "reporte negocio",
        "health score",
    ],

    "business_consult": [
        "consulta negocio",
        "consultar negocio",
        "consulta empresa",
        "consultar empresa",
        "consulta pyme",
        "diagnóstico negocio",
        "diagnostico negocio",
        "diagnóstico empresa",
        "consult business",
        "diagnose business",
        "pyme consult",
        "full analysis",
        "análisis completo",
        "analisis completo",
    ],

    "business_train": [
        "entrena negocio",
        "entrenar negocio",
        "entrena pyme",
        "train business",
        "bi train",
    ],

    "forex_analysis": [
        "forex",
        "analyze forex",
        "analyse forex",
        "eurusd",
        "eur/usd",
        "gbpusd",
        "usdjpy",
        "market analysis",
        "analyze pair",
        "analiza forex",
    ],
    
    "forex_history": [
        "history",
        "show history",
        "market history",
        "analysis history",
    ],

    "forex_compare": [
        "compare analyses",
        "compare reports",
        "compare history",
    ],

    "forex_markets": [
        "list markets",
        "saved markets",
        "analyzed markets",
    ],
    # ── Fase 2: Active Engine ──────────────────────────────
    "schedule_forex": [
        "schedule forex",
        "programar forex",
        "schedule stop",
        "schedule status",
        "schedule run",
        "programar señal",
    ],

    "watch_forex": [
        "watch forex",
        "watch stop",
        "watch status",
        "watch check",
        "monitorear forex",
        "monitor forex",
        "watcher",
    ],

    # ── Fase 2: Signal Tracker ────────────────────────────
    "signal_history": [
        "signals",
        "señales",
        "historial señales",
        "signal history",
        "últimas señales",
        "ultimas señales",
        "ver señales",
    ],

    "signal_stats": [
        "stats señales",
        "estadísticas señales",
        "estadisticas señales",
        "signal stats",
    ],

    # ── Fase 2: Project Memory ────────────────────────────
    "list_models_memory": [
        "models memory",
        "modelos guardados",
        "list models",
        "ver modelos",
        "mis modelos",
        "models status",
    ],

    "list_projects": [
        "projects",
        "proyectos",
        "list projects",
        "ver proyectos",
        "mis proyectos",
    ],

    # ── Fase 4: News Intelligence ─────────────────────────
    "news_forex": [
        "news",
        "noticias",
        "noticias forex",
        "news forex",
        "noticias eurusd",
        "noticias xauusd",
    ],

    "news_predict": [
        "news predict",
        "predict news",
        "noticias prediccion",
        "prediccion noticias",
        "señal con noticias",
        "combined signal",
    ],

    # ── Fase 5: Prediction Lab ─────────────────────────────
    "lab_analiza": [
        "lab analiza",
        "analiza mi idea",
        "prediction lab",
        "lab dataset",
        "lab viabilidad",
        "lab planea",
        "lab genera",
        "lab valida",
        "lab modelos",
        "lab generar",
        "lab entrenar",
        "lab comparar",
        "lab reporte",
        "lab proyectos",
    ],

    # ── Roadmap IV, Seccion 7: Cognitive Center ────────────
    "cognitive_center": [
        "memoria explorar",
        "memoria buscar",
        "cognitive center",
        "explorar memoria",
        "busca en mi memoria",
        "que sabes de mi",
        "knowledge graph",
        "linea de tiempo",
        "timeline memoria",
    ],


    
    "audio_analysis": [
        "analiza audio",
        "analizar audio",
    ],

    "speech_to_text": [
        "voz a texto",
        "transcribir audio",
    ],

    "text_to_speech": [
        "texto a voz",
        "leer texto",
    ],

    "symbolic_math": [
        "integral",
        "derivada",
        "calculo simbolico",
        "resolver integral",
    ],

    "machine_learning": [
        "entrena modelo",
        "entrenar modelo",
        "machine learning",
        "sklearn",
    ],

    "security": [
        "hash",
        "jwt",
        "cifrar",
        "encriptar",
        "password",
        "contraseña",
    ],

    "system": [
        "estado pc",
        "cpu",
        "ram",
        "estado sistema",
    ],

    "memory": [
        "recuerda",
        "memoria",
        "guardar memoria",
        "buscar memoria",
        "redis",
        "faiss",
        "llamaindex",
    ],

    "sme_diagnostic": [
        "diagnóstico pyme",
        "diagnostico pyme",
        "diagnostico empresa",
        "diagnóstico empresa",
        "scorecard negocio",
        "scorecard empresa",
        "puntuacion empresa",
        "puntuación empresa",
        "evaluación empresa",
        "evaluacion empresa",
        "dimensiones negocio",
        "diagnostic pyme",
        "business scorecard",
        "health scorecard",
    ],

    "sme_forecast": [
        "proyección negocio",
        "proyeccion negocio",
        "proyectar ventas",
        "proyecta negocio",
        "forecast negocio",
        "forecast ventas",
        "predecir ingresos",
        "próximos meses",
        "proximos meses",
        "proyectar ingresos",
        "business forecast",
        "revenue forecast",
    ],

    "sme_recommend": [
        "recomienda para",
        "recomendaciones para",
        "plan de accion",
        "plan de acción",
        "estrategia negocio",
        "estrategia empresa",
        "acciones para mejorar",
        "qué hago con",
        "que hago con",
        "plan estrategico",
        "plan estratégico",
        "strategic plan",
        "action plan",
    ],

    "sme_simulate": [
        "simula",
        "simulacion",
        "simulación",
        "que pasa si",
        "qué pasa si",
        "si reduzco",
        "si aumento",
        "si bajo",
        "si subo",
        "escenario hipotetico",
        "escenario hipotético",
        "what if",
        "simulate",
    ],

    "self_analysis": [
        "self analysis",
        "self-analysis",
        "analiza astra",
        "analizar astra",
        "reporte sistema",
        "reporte astra",
        "estado astra",
        "diagnostico astra",
        "diagnóstico astra",
        "astra report",
        "system report",
        "genera reporte",
        "generar reporte",
    ],

    # ── Roadmap VI — Autonomía & Data Intelligence ─────────────────
    "self_test": [
        "self-test",
        "selftest",
        "check sistema",
        "check system",
        "diagnostico sistema",
        "diagnóstico sistema",
        "verificar sistema",
    ],

    "scheduler_control": [
        "scheduler start",
        "scheduler stop",
        "scheduler info",
        "scheduler status",
        "iniciar scheduler",
        "detener scheduler",
        "estado scheduler",
    ],

    "circuit_control": [
        "circuit status",
        "circuit reset",
        "circuit breaker status",
        "circuit breaker reset",
        "estado circuit",
    ],

    "hparam_cache_cmd": [
        "hparam cache",
        "hparam invalidar",
        "hparam status",
        "hyperparameter cache",
        "cache hiperparametros",
        "caché hiperparámetros",
    ],

    "model_cache_cmd": [
        "model cache",
        "model cache status",
        "cache modelos",
        "caché modelos",
    ],

    "rolling_dataset_cmd": [
        "rolling info",
        "rolling dataset",
        "dataset rolling",
        "estado dataset rolling",
    ],

    "opportunity_ranking_cmd": [
        "opportunity ranking",
        "oportunidades ranking",
        "top señales",
        "top signals",
        "mejores señales",
        "ranking señales",
    ],

    "candlestick_cmd": [
        "candlestick",
        "patrones vela",
        "velas japonesas",
        "patrones japoneses",
    ],

    "csv_scanner_cmd": [
        "escanear csvs",
        "csvs activos",
        "escanear datos",
        "indice csvs",
        "índice csvs",
    ],

    "auto_update_cmd": [
        "auto update",
        "actualizar csvs",
        "actualizar todos",
        "update csvs",
    ],

    "adaptive_budget_cmd": [
        "adaptive budget",
        "budget adaptativo",
        "presupuesto adaptativo",
    ],

    "quality_history_cmd": [
        "quality history",
        "historial calidad",
        "historial precisión",
        "historial precision",
    ],

    "forex_generate_csvs_cmd": [
        "generar csvs forex",
        "generar todos los csvs forex",
        "generate forex csvs",
        "crear csvs forex",
        "descargar csvs forex",
    ],

    "chat": []
}

# ==========================================
# DETECCION
# ==========================================

def classify_intent(text):

    text = text.lower().strip()

    # Los comandos deben ir al INICIO del mensaje (una sola línea, formato comando).
    # Esto evita que texto conversacional que solo *contiene* una palabra parecida
    # a un comando (ej. "ramificaciones" contiene "ram") dispare una herramienta
    # real por error. Si el usuario quiere hablar, debe poder hacerlo sin que
    # ASTRA interprete su mensaje como un comando de sistema.
    for intent, patterns in INTENT_PATTERNS.items():

        for pattern in patterns:

            if text == pattern or text.startswith(pattern + " "):
                return intent

    return "chat"

# ==========================================
# MAPEO INTENCION -> TOOL
# ==========================================

INTENT_TO_TOOL = {

    "business_analysis": "bi_analyze",
    "business_consult":  "bi_consult",
    "business_train":    "bi_train",

    "forex_analysis": "forex_analyze",

    "forex_history": "forex_history",

    "forex_compare": "forex_compare",

    "forex_markets": "forex_markets",
    
    "document_read": "leer_pdf",

    "document_summary": "leer_pdf",

    "translation": "traducir",

    "web_search": "extrae_web",

    "audio_analysis": "analiza_audio",

    "speech_to_text": "voz_a_texto",

    "text_to_speech": "texto_a_voz",

    "symbolic_math": "integral",

    "machine_learning": "entrenar_modelo",

    "system": "estado_pc",

    "sme_diagnostic": "sme_diagnostic",
    "sme_forecast":   "sme_forecast",
    "sme_recommend":  "sme_recommend",
    "sme_simulate":   "sme_simulate",

    "self_analysis": "self_analysis",

    # ── Roadmap VI ────────────────────────────────────────────────
    "self_test":              "self_test",
    "scheduler_control":      "scheduler_control",
    "circuit_control":        "circuit_control",
    "hparam_cache_cmd":       "hparam_cache_cmd",
    "model_cache_cmd":        "model_cache_cmd",
    "rolling_dataset_cmd":    "rolling_dataset_cmd",
    "opportunity_ranking_cmd": "opportunity_ranking_cmd",
    "candlestick_cmd":        "candlestick_cmd",
    "csv_scanner_cmd":        "csv_scanner_cmd",
    "auto_update_cmd":        "auto_update_cmd",
    "adaptive_budget_cmd":    "adaptive_budget_cmd",
    "quality_history_cmd":    "quality_history_cmd",
    "forex_generate_csvs_cmd": "forex_generate_csvs_cmd",
}

# ==========================================
# HELPERS
# ==========================================

def get_tool_for_intent(intent):

    return INTENT_TO_TOOL.get(intent)

def analyze_request(text):

    intent = classify_intent(text)

    return {
        "intent": intent,
        "tool": get_tool_for_intent(intent)
    }
