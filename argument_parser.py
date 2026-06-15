# argument_parser.py

"""
Extrae parámetros desde texto libre.

Ejemplos:

'lee pdf informe.pdf'
    -> ['informe.pdf']

'traduce hola mundo'
    -> ['hola mundo']

'analiza audio entrevista.mp3'
    -> ['entrevista.mp3']
"""

import re
import os


# ==========================================
# EXTENSIONES CONOCIDAS
# ==========================================

PDF_EXT = (".pdf",)
WORD_EXT = (".docx", ".doc")
EXCEL_EXT = (".xlsx", ".xls")
CSV_EXT = (".csv",)

AUDIO_EXT = (
    ".mp3",
    ".wav",
    ".ogg",
    ".m4a"
)

IMAGE_EXT = (
    ".png",
    ".jpg",
    ".jpeg",
    ".bmp",
    ".webp"
)
from forex.market_universe import find_market

# ==========================================
# BUSQUEDA DE ARCHIVOS
# ==========================================

def extract_market_symbol(text: str):

    text = text.upper()

    for token in text.split():

        market = find_market(token)

        if market:
            return market

    market = find_market(text)

    return market
    

def extract_filename(text):

    pattern = r'[\w\-.]+\.[a-zA-Z0-9]+'

    match = re.search(pattern, text)

    if match:
        return match.group(0)

    return None


# ==========================================
# PDF
# ==========================================

def extract_pdf(text):

    file = extract_filename(text)

    if file and file.lower().endswith(PDF_EXT):
        return [file]

    return []


# ==========================================
# WORD
# ==========================================

def extract_word(text):

    file = extract_filename(text)

    if file and file.lower().endswith(WORD_EXT):
        return [file]

    return []


# ==========================================
# EXCEL
# ==========================================

def extract_excel(text):

    file = extract_filename(text)

    if file and file.lower().endswith(EXCEL_EXT):
        return [file]

    return []


# ==========================================
# CSV
# ==========================================

def extract_csv(text):

    file = extract_filename(text)

    if file and file.lower().endswith(CSV_EXT):
        return [file]

    return []


# ==========================================
# AUDIO
# ==========================================

def extract_audio(text):

    file = extract_filename(text)

    if file and file.lower().endswith(AUDIO_EXT):
        return [file]

    return []


# ==========================================
# IMAGEN
# ==========================================

def extract_image(text):

    file = extract_filename(text)

    if file and file.lower().endswith(IMAGE_EXT):
        return [file]

    return []


# ==========================================
# TRADUCCION
# ==========================================

def extract_translation_text(text):

    keywords = [
        "traduce",
        "traducir",
        "translate"
    ]

    lower = text.lower()

    for k in keywords:

        if lower.startswith(k):

            return [
                text[len(k):].strip()
            ]

    return []


# ==========================================
# URL
# ==========================================

def extract_url(text):

    pattern = r'https?://\S+'

    match = re.search(pattern, text)

    if match:
        return [match.group(0)]

    return []


# ==========================================
# GENERAL
# ==========================================

def parse_arguments(intent, text):

    if intent == "document_read":

        pdf = extract_pdf(text)
        if pdf:
            return pdf

        word = extract_word(text)
        if word:
            return word

        excel = extract_excel(text)
        if excel:
            return excel

        csv = extract_csv(text)
        if csv:
            return csv

    elif intent == "translation":

        return extract_translation_text(text)

    elif intent == "forex_analysis":
        market = extract_market_symbol(text)
        if market:
            return [market]
        return []
        
    elif intent == "web_search":

        return extract_url(text)

    elif intent == "audio_analysis":

        return extract_audio(text)

    elif intent == "speech_to_text":

        return extract_audio(text)

    return []
