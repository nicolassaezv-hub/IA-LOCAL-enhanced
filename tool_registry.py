# tool_registry.py
"""
Registro centralizado de herramientas ASTRA.

Objetivos:
- Centralizar acceso a funciones.
- Evitar imports dispersos.
- Facilitar agentes futuros.
- Mantener compatibilidad con el esqueleto actual.
"""

# ==========================================
# IO FILES
# ==========================================

from io_files import (
    leer_pdf,
    leer_word,
    leer_excel,
    leer_csv,
    escribe_pdf,
    escribe_word,
    escribe_excel,
    escribe_csv,
    crea_py
)

# ==========================================
# AI MODELS
# ==========================================

from ai_models import (
    ask_openai,
    system_status,
    torch_demo,
    tensorflow_demo,
    keras_demo,
    sklearn_demo,
    calcular_integral,
    entrenar_modelo_sklearn
)

# ==========================================
# WEB TOOLS
# ==========================================

from web_tools import (
    extrae_web,
    traducir,
    descargar_youtube,
    httpx_demo,
    aiohttp_demo,
    socketio_demo,
    fastapi_demo,
    flask_demo,
    subir_archivo_azure,
    consumir_api_grpc
)

# ==========================================
# AUDIO VIDEO
# ==========================================

from audio_video import (
    voz_a_texto,
    texto_a_voz,
    analiza_audio,
    reproducir_audio,
    convertir_audio,
    descargar_audio_youtube
)

from forex_analytics import (
    market_history,
    compare_market_history
)

from forex.forex_memory import (
    list_saved_markets
)

# ==========================================
# VISUALIZATION
# ==========================================

from visualization import (
    grafica_csv,
    mostrar_tabla,
    mostrar_rich,
    crear_pdf,
    procesar_imagen_skimage,
    mostrar_gui_pyqt
)

# ==========================================
# SECURITY
# ==========================================

from security import (
    cifra_archivo,
    hash_password,
    verify_password,
    passlib_hash,
    passlib_verify,
    crear_jwt,
    verificar_jwt,
    paramiko_demo
)

# ==========================================
# UTILS
# ==========================================

from utils import (
    system_status as utils_status,
    barra_progreso,
    tarea_programada,
    simular_tecla,
    simular_click,
    bloquear_archivo,
    iniciar_monitor,
    obtener_fecha_arrow,
    serializar_orjson
)

# ==========================================
# MODULES EXTRA
# ==========================================

from modules_extra import (
    FaissMemory,
    LlamaMemory,
    redis_set,
    redis_get,
    guardar_usuario
)

# ==========================================
# REGISTRO CENTRAL
# ==========================================

TOOLS = {

    # ---------- IO ----------
    "leer_pdf": leer_pdf,
    "leer_word": leer_word,
    "leer_excel": leer_excel,
    "leer_csv": leer_csv,
    "forex_analyze": analyze_market_file,
    "escribe_pdf": escribe_pdf,
    "escribe_word": escribe_word,
    "escribe_excel": escribe_excel,
    "escribe_csv": escribe_csv,

    "crea_py": crea_py,

    # ---------- WEB ----------
    "extrae_web": extrae_web,
    "traducir": traducir,
    "descargar_youtube": descargar_youtube,

    "httpx_demo": httpx_demo,
    "aiohttp_demo": aiohttp_demo,
    "socketio_demo": socketio_demo,
    "fastapi_demo": fastapi_demo,
    "flask_demo": flask_demo,

    "azure": subir_archivo_azure,
    "grpc": consumir_api_grpc,

    # ---------- AUDIO ----------
    "voz_a_texto": voz_a_texto,
    "texto_a_voz": texto_a_voz,
    "analiza_audio": analiza_audio,
    "reproducir_audio": reproducir_audio,
    "convertir_audio": convertir_audio,
    "descargar_audio_youtube": descargar_audio_youtube,

    # ---------- VISUAL ----------
    "grafica_csv": grafica_csv,
    "mostrar_tabla": mostrar_tabla,
    "mostrar_rich": mostrar_rich,
    "crear_pdf": crear_pdf,
    "procesar_imagen": procesar_imagen_skimage,
    "mostrar_gui": mostrar_gui_pyqt,

    # ---------- SECURITY ----------
    "cifra_archivo": cifra_archivo,
    "hash_password": hash_password,
    "verify_password": verify_password,

    "passlib_hash": passlib_hash,
    "passlib_verify": passlib_verify,

    "crear_jwt": crear_jwt,
    "verificar_jwt": verificar_jwt,

    "paramiko_demo": paramiko_demo,

    # ---------- UTILS ----------
    "estado_pc": utils_status,
    "barra_progreso": barra_progreso,
    "tarea_programada": tarea_programada,

    "simular_tecla": simular_tecla,
    "simular_click": simular_click,

    "bloquear_archivo": bloquear_archivo,
    "iniciar_monitor": iniciar_monitor,

    "fecha": obtener_fecha_arrow,
    "json": serializar_orjson,

    # ---------- IA ----------
    "ask_openai": ask_openai,
    "torch_demo": torch_demo,
    "tensorflow_demo": tensorflow_demo,
    "keras_demo": keras_demo,
    "sklearn_demo": sklearn_demo,

    "integral": calcular_integral,
    "entrenar_modelo": entrenar_modelo_sklearn,

    # ---------- MEMORIA ----------
    "faiss_memory": FaissMemory,
    "llama_memory": LlamaMemory,

    "redis_set": redis_set,
    "redis_get": redis_get,

    # ---------- SQL ----------
    "guardar_usuario": guardar_usuario,
}

# ==========================================
# HELPERS
# ==========================================

def get_tool(name):
    """
    Obtiene una herramienta por nombre.
    """
    return TOOLS.get(name)


def tool_exists(name):
    """
    Verifica si existe una herramienta.
    """
    return name in TOOLS


def list_tools():
    """
    Lista todas las herramientas registradas.
    """
    return sorted(TOOLS.keys())


def execute_tool(name, *args, **kwargs):
    """
    Ejecuta una herramienta de forma segura.
    """

    tool = get_tool(name)

    if tool is None:
        return f"Herramienta no encontrada: {name}"

    try:
        return tool(*args, **kwargs)

    except Exception as e:
        return f"Error ejecutando {name}: {e}"

TOOLS["forex_analyze"] = analyze_forex_file

def registry_stats():
    """
    Estadísticas del registro.
    """

    return {
        "total_tools": len(TOOLS),
        "tools": list_tools()
    }
