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

    "chat": []
}

# ==========================================
# DETECCION
# ==========================================

def classify_intent(text):

    text = text.lower().strip()

    for intent, patterns in INTENT_PATTERNS.items():

        for pattern in patterns:

            if pattern in text:
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
