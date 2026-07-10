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

def ask_openai_tool(*args, **kwargs):
    from ai_models import ask_openai
    return ask_openai(*args, **kwargs)

from forex_analytics import (
    analyze_market_file,
    market_history,
    compare_market_history
)

from bi_analytics import (
    bi_analyze,
    bi_consult,
    bi_kpis,
    bi_train,
)

from self_analysis import generate_self_analysis

from sme_consultant import (
    sme_diagnostic,
    sme_forecast,
    sme_recommend,
    sme_simulate,
)

from forex.forex_memory import (
    list_saved_markets
)

def registry_stats():
    """
    Estadísticas del registro.
    """

    return {
        "total_tools": len(TOOLS),
        "tools": list_tools()
    }

_FOREX_PIPELINE = None

def run_forex_analysis(
    filepath: str,
    mode: str = "full"
):
    global _FOREX_PIPELINE
    if _FOREX_PIPELINE is None:
        from forex.prediction.integrated_pipeline import ForexIntegratedPipeline
        _FOREX_PIPELINE = ForexIntegratedPipeline()
    return _FOREX_PIPELINE.run(
        filepath=filepath,
        mode=mode
    )


# =======================================
# REGISTRO CENTRAL
# ==========================================


# ==========================================
# COGNITIVE CORE — Fase 1 & 2
# ==========================================

from project_memory import (
    register_model,
    get_model,
    list_models,
    save_project,
    list_projects,
    session_summary,
    auto_register_forex_model,
)

from signal_tracker import (
    save_signal,
    get_signals,
    get_last_signal,
    signal_stats,
    cmd_signal_history,
    cmd_signal_stats,
)

from active_engine import get_engine as get_active_engine

from news_intelligence import (
    fetch_news,
    analyze_sentiment,
    cmd_news,
    cmd_news_predict,
)

from prediction_lab.prompt_analyzer import analyze_prompt, cmd_lab_analiza
from prediction_lab.dataset_analyzer import analyze_dataset, cmd_lab_dataset
from prediction_lab.feasibility_engine import assess_feasibility, cmd_lab_viabilidad
from prediction_lab.model_planner import plan_model, cmd_lab_planea
from prediction_lab.pipeline_generator import generate_pipeline, cmd_lab_genera
from prediction_lab.validation_engine import validate_pipeline, cmd_lab_valida

from cognitive_center import (
    get_conversations,
    get_projects_overview,
    get_tools_usage,
    get_learned_preferences,
    get_timeline,
    build_knowledge_graph,
    search_memory,
    cmd_memoria_explorar,
    cmd_memoria_buscar,
)

TOOLS = {
    # ---------- SELF ANALYSIS --------- #
    "self_analysis": generate_self_analysis,

    # ---------- BRANCH 4 — SME CONSULTANT --------- #
    "sme_diagnostic": sme_diagnostic,
    "sme_forecast":   sme_forecast,
    "sme_recommend":  sme_recommend,
    "sme_simulate":   sme_simulate,

    # ---------- BUSINESS INTELLIGENCE --------- #
    "bi_analyze":  bi_analyze,
    "bi_consult":  bi_consult,
    "bi_kpis":     bi_kpis,
    "bi_train":    bi_train,

    # ---------- FOREX --------- #
    "ask_openai": ask_openai_tool,
    "forex_history" : market_history,
    "forex_compare" : compare_market_history,
    "forex_markets" : list_saved_markets,
    "forex_analyze": analyze_market_file,
    "run_forex_analysis" : run_forex_analysis,
    "registry_stats": registry_stats,
    # ---------- IO ----------
    "leer_pdf": leer_pdf,
    "leer_word": leer_word,
    "leer_excel": leer_excel,
    "leer_csv": leer_csv,
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

    # ── Cognitive Core ─────────────────────────────────
    "register_model":          register_model,
    "get_model":               get_model,
    "list_models":             list_models,
    "save_project":            save_project,
    "list_projects":           list_projects,
    "session_summary":         session_summary,
    "auto_register_model":     auto_register_forex_model,

    # ── Signal Tracker ──────────────────────────────────
    "save_signal":             save_signal,
    "get_signals":             get_signals,
    "get_last_signal":         get_last_signal,
    "signal_stats":            signal_stats,
    "signal_history":          cmd_signal_history,
    "signal_stats_cmd":        cmd_signal_stats,

    # ── Active Engine ───────────────────────────────────
    "get_engine":              get_active_engine,

    # ── News Intelligence ───────────────────────────────
    "fetch_news":              fetch_news,
    "analyze_sentiment":       analyze_sentiment,
    "news_cmd":                cmd_news,
    "news_predict_cmd":        cmd_news_predict,

    # ── Prediction Lab (Fase 5) ─────────────────────────
    "lab_analyze_prompt":      analyze_prompt,
    "lab_analiza_cmd":         cmd_lab_analiza,
    "lab_analyze_dataset":     analyze_dataset,
    "lab_dataset_cmd":         cmd_lab_dataset,
    "lab_assess_feasibility":  assess_feasibility,
    "lab_viabilidad_cmd":      cmd_lab_viabilidad,
    "lab_plan_model":          plan_model,
    "lab_planea_cmd":          cmd_lab_planea,
    "lab_generate_pipeline":   generate_pipeline,
    "lab_genera_cmd":          cmd_lab_genera,
    "lab_validate_pipeline":   validate_pipeline,
    "lab_valida_cmd":          cmd_lab_valida,

    # ── Cognitive Center (Roadmap IV, Seccion 7) ────────
    "cognitive_conversations":   get_conversations,
    "cognitive_projects":        get_projects_overview,
    "cognitive_tools_usage":     get_tools_usage,
    "cognitive_preferences":     get_learned_preferences,
    "cognitive_timeline":        get_timeline,
    "cognitive_knowledge_graph": build_knowledge_graph,
    "cognitive_search":          search_memory,
    "memoria_explorar_cmd":      cmd_memoria_explorar,
    "memoria_buscar_cmd":        cmd_memoria_buscar,

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
        raise RuntimeError(
            f"Error ejecutando {name}: {e}"
        )

