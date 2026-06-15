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
    
    "forex_analysis": "forex_analyze",
    
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
