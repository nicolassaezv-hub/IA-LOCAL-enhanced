# ai_models.py
"""
Motor de IA de ASTRA — Groq (openai/gpt-oss-120b) con memoria de sesión,
historial persistente estructurado, y narración de herramientas.
"""

import os
import psutil
import numpy as np
from sklearn.model_selection import train_test_split
from sklearn.linear_model import LogisticRegression

from memory import guardar_memoria, cargar_turnos

# ==========================================
# OPTIONAL HEAVY IMPORTS
# ==========================================

try:
    import torch
    HAS_TORCH = True
except ImportError:
    torch = None
    HAS_TORCH = False

try:
    import tensorflow as tf
    HAS_TF = True
except ImportError:
    tf = None
    HAS_TF = False

try:
    import keras
    HAS_KERAS = True
except ImportError:
    keras = None
    HAS_KERAS = False

try:
    import sympy as sp
    HAS_SYMPY = True
except ImportError:
    sp = None
    HAS_SYMPY = False

try:
    import torchvision.models as tv_models
    HAS_TORCHVISION = True
except ImportError:
    tv_models = None
    HAS_TORCHVISION = False

try:
    import torchaudio
    HAS_TORCHAUDIO = True
except ImportError:
    torchaudio = None
    HAS_TORCHAUDIO = False

# ==========================================
# CLIENT CONFIG
# ==========================================

_groq_client    = None
_GROQ_MODEL     = "openai/gpt-oss-120b"
_GROQ_BASE_URL  = "https://api.groq.com/openai/v1"
_TEMPERATURE    = 0.4          # analytical but not robotic
_MAX_TOKENS     = 1024         # enough for consultant-grade answers
_MAX_SESSION    = 20           # max turn-items kept in session buffer (10 exchanges)
_DB_TURNS_LOAD  = 6            # how many past exchanges to pull from DB on cold start

# ==========================================
# SESSION BUFFER  (lives for one Python process run)
# ==========================================

_session_history: list[dict] = []


def _push_session(role: str, content: str) -> None:
    """Añade un turno al buffer de sesión y recorta si excede el límite."""
    _session_history.append({"role": role, "content": content})
    if len(_session_history) > _MAX_SESSION:
        _session_history.pop(0)


def clear_session() -> str:
    """Limpia el historial de sesión en memoria (no borra SQLite)."""
    _session_history.clear()
    return "Sesión reiniciada. El historial de conversación en memoria ha sido limpiado."


def get_session_length() -> int:
    """Devuelve cuántos turnos hay en el buffer de sesión."""
    return len(_session_history)


# ==========================================
# GROQ CLIENT
# ==========================================

def _get_client():
    global _groq_client
    if _groq_client is None:
        from openai import OpenAI
        api_key = os.environ.get("GROQ_API_KEY") or os.environ.get("OPENAI_API_KEY")
        if not api_key:
            raise RuntimeError(
                "No AI API key found. Set GROQ_API_KEY (recommended) "
                "or OPENAI_API_KEY as an environment variable."
            )
        base_url = _GROQ_BASE_URL if os.environ.get("GROQ_API_KEY") else None
        _groq_client = OpenAI(api_key=api_key, base_url=base_url)
    return _groq_client


def _active_model() -> str:
    return _GROQ_MODEL if os.environ.get("GROQ_API_KEY") else "gpt-3.5-turbo"


# ==========================================
# SYSTEM PROMPT
# ==========================================

_SYSTEM_PROMPT = """\
Eres ASTRA, un asistente de inteligencia artificial modular diseñado como \
consultor experto para PyMEs y pequeñas empresas. \
Operas en español por defecto; si el usuario escribe en inglés, responde en inglés.

## Identidad y especialización
- Consultor financiero y de negocio para pequeñas y medianas empresas (PyMEs)
- Analista de Business Intelligence: KPIs, salud financiera, tendencias, alertas
- Analista Forex: pares de divisas, análisis técnico (RSI, MACD, EMA, Bollinger), predicción ML
- Procesador de documentos: PDF, Word, Excel, CSV
- Consultor PYME: diagnóstico empresarial, proyecciones, recomendaciones accionables, simulaciones

## Capacidades activas
- Análisis de negocio: KPIs, health score 0-100, alertas críticas, consulta completa, entrenamiento ML
- Análisis Forex: técnico completo, historial de análisis, comparativa de reportes
- Documentos: lectura y extracción de PDF, Word, Excel, CSV
- Web: extracción de contenido, traducción de texto
- Seguridad: cifrado AES, JWT, hashing bcrypt
- Sistema: estado del PC, auto-análisis con reporte fechado

## Estilo de respuesta
- Sé directo, analítico y profesional. Omite frases de relleno.
- Para datos: primero el número, luego la interpretación, luego la acción concreta.
- Para recomendaciones: usa numeración (1. 2. 3.) con acción específica + impacto esperado.
- Máximo 4 párrafos salvo que el usuario pida más detalle.
- Si el usuario menciona un archivo o empresa que analizaste antes, recuérdalo y referéncialo.

## Reglas críticas
- Nunca inventes cifras o datos financieros que no estén en el contexto.
- Si los datos son insuficientes para una recomendación sólida, indícalo claramente.
- Las proyecciones son estimaciones basadas en tendencias — menciona siempre esa limitación.
- No digas "No puedo hacer eso" para tareas dentro de tu alcance. Intenta siempre.
"""


# ==========================================
# MESSAGE BUILDER
# ==========================================

def _build_messages(user_message: str, extra_context: str | None = None) -> list[dict]:
    """
    Construye la lista de mensajes para la API con esta prioridad:
      1. System prompt (siempre)
      2. Historial de sesión actual (si hay turnos en memoria)
         ó historial de DB (si es inicio de sesión)
      3. Mensaje del usuario actual

    Si se proporciona extra_context (resultado de una herramienta),
    se inyecta en el mensaje del usuario.
    """
    messages: list[dict] = [{"role": "system", "content": _SYSTEM_PROMPT}]

    if _session_history:
        messages.extend(_session_history)
    else:
        db_turns = cargar_turnos(limit=_DB_TURNS_LOAD)
        if db_turns:
            messages.extend(db_turns)

    if extra_context:
        user_content = (
            f"{user_message}\n\n"
            f"--- Resultado de herramienta ASTRA ---\n"
            f"{extra_context}\n"
            f"--- Fin del resultado ---\n\n"
            f"Proporciona un análisis narrativo conciso de estos resultados "
            f"como consultor experto: interpreta los datos clave, señala alertas "
            f"y termina con 2-3 recomendaciones accionables numeradas."
        )
    else:
        user_content = user_message

    messages.append({"role": "user", "content": user_content})
    return messages


# ==========================================
# SYSTEM STATUS
# ==========================================

def system_status():
    cpu = psutil.cpu_percent(interval=1)
    ram = psutil.virtual_memory().percent
    return f"CPU: {cpu}% | RAM: {ram}%"


# ==========================================
# CORE AI CALL
# ==========================================

def ask_openai(user_message: str) -> str:
    """
    Llamada principal al modelo. Mantiene sesión en memoria y
    persiste en SQLite para memoria a largo plazo.
    """
    try:
        client   = _get_client()
        messages = _build_messages(user_message)

        response = client.chat.completions.create(
            model       = _active_model(),
            messages    = messages,
            temperature = _TEMPERATURE,
            max_tokens  = _MAX_TOKENS,
        )
        reply = response.choices[0].message.content

        _push_session("user",      user_message)
        _push_session("assistant", reply)
        guardar_memoria(user_message, reply)

        return reply

    except Exception as e:
        return f"Error al consultar AI: {e}"


def ask_llama_with_context(user_message: str, tool_output: str) -> str:
    """
    Narración de resultados de herramientas.

    Recibe la consulta original del usuario y el output crudo de una herramienta
    (BI report, Forex analysis, etc.) y pide a Llama que lo interprete
    como un consultor — narrativa concisa + recomendaciones.

    Usado por astra_agent.py para enriquecer respuestas de herramientas clave.
    """
    try:
        client   = _get_client()
        messages = _build_messages(user_message, extra_context=tool_output)

        response = client.chat.completions.create(
            model       = _active_model(),
            messages    = messages,
            temperature = _TEMPERATURE,
            max_tokens  = _MAX_TOKENS,
        )
        reply = response.choices[0].message.content

        _push_session("user",      user_message)
        _push_session("assistant", reply)
        guardar_memoria(user_message, reply)

        return reply

    except Exception as e:
        return f"[Narración no disponible: {e}]"


# ==========================================
# ML / FRAMEWORK DEMOS
# ==========================================

def torch_demo():
    if not HAS_TORCH:
        return "PyTorch no disponible en este sistema."
    try:
        a = torch.tensor([1, 2, 3])
        b = torch.tensor([4, 5, 6])
        return f"Torch demo: {a * b}"
    except Exception as e:
        return f"Error en Torch demo: {e}"


def tensorflow_demo():
    if not HAS_TF:
        return "TensorFlow no disponible en este sistema."
    try:
        a = tf.constant([1, 2, 3])
        b = tf.constant([4, 5, 6])
        return f"TensorFlow demo: {tf.add(a, b).numpy()}"
    except Exception as e:
        return f"Error en TensorFlow demo: {e}"


def calcular_integral(expr, var, a, b):
    if not HAS_SYMPY:
        return "sympy no disponible en este sistema."
    x = sp.Symbol(var)
    integral = sp.integrate(sp.sympify(expr), (x, a, b))
    return f"Integral de {expr} entre {a} y {b}: {integral}"


def entrenar_modelo_sklearn():
    X = np.array([[0, 0], [1, 1], [2, 2], [3, 3]])
    y = np.array([0, 1, 1, 1])
    X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.25)
    model = LogisticRegression().fit(X_train, y_train)
    pred  = model.predict(X_test)
    score = model.score(X_test, y_test)
    return f"Predicciones: {pred}, Score: {score}"


def demo_torchvision():
    if not HAS_TORCHVISION:
        return "torchvision no disponible en este sistema."
    try:
        resnet = tv_models.resnet18()
        return f"ResNet18 cargado, parámetros: {sum(p.numel() for p in resnet.parameters())}"
    except Exception as e:
        return f"Error en torchvision demo: {e}"


def demo_torchaudio():
    if not HAS_TORCHAUDIO:
        return "torchaudio no disponible en este sistema."
    return f"Torchaudio versión: {torchaudio.__version__}"


def keras_demo():
    if not HAS_KERAS:
        return "Keras no disponible en este sistema."
    try:
        model = keras.Sequential([
            keras.layers.Dense(10, activation="relu", input_shape=(5,)),
            keras.layers.Dense(1,  activation="sigmoid"),
        ])
        return "Modelo Keras creado correctamente."
    except Exception as e:
        return f"Error en Keras demo: {e}"


def sklearn_demo():
    try:
        X = np.arange(10).reshape(-1, 1)
        y = np.arange(10)
        X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2)
        return f"Train size: {len(X_train)}, Test size: {len(X_test)}"
    except Exception as e:
        return f"Error en Scikit-learn demo: {e}"
