# astra_agent.py
"""
ASTRA Agent — capa inteligente superior.

Flujo:
  usuario
     ↓
  intent_router  (clasifica intención)
     ↓
  tool_registry  (busca herramienta)
     ↓
  herramienta    (ejecuta)
     ↓ (si es herramienta BI/consultor)
  ask_llama_with_context  (narra resultado)
     ↓ (si no hay herramienta)
  ask_openai     (chat general con sesión)
"""

from memory_router import save_chat, get_context
from argument_parser import parse_arguments
from tool_registry import tool_exists
from tool_executor import execute
from intent_router import analyze_request
from ai_models import ask_openai, ask_llama_with_context

# ==========================================
# HERRAMIENTAS QUE RECIBEN NARRACIÓN AI
# ==========================================
# Estas herramientas producen datos estructurados que se benefician
# de que Llama los interprete como consultor antes de mostrarlos.

_NARRATE_TOOLS = {
    "bi_analyze",
    "bi_consult",
    "bi_kpis",
    "bi_train",
    "self_analysis",
    "sme_diagnostic",
    "sme_forecast",
    "sme_simulate",
}

# ==========================================
# AGENTE PRINCIPAL
# ==========================================

def process_request(user_input: str) -> str:

    try:
        analysis  = analyze_request(user_input)
        intent    = analysis["intent"]
        tool_name = analysis["tool"]
        args      = parse_arguments(intent, user_input)

        print(f"[ASTRA] Intent: {intent} | Tool: {tool_name or 'chat'}")

        # ── Sin herramienta → chat general con Llama ──
        if tool_name is None or not tool_exists(tool_name):
            return ask_openai(user_input)

        # ── Ejecutar herramienta ──
        result = execute(tool_name, *args)
        save_chat(user_input, str(result))

        # ── Narración AI para herramientas BI / consultor ──
        if tool_name in _NARRATE_TOOLS:
            narration = ask_llama_with_context(user_input, str(result))
            return (
                f"{result}\n\n"
                f"{'─' * 52}\n"
                f"💬  Análisis ASTRA (Groq: openai/gpt-oss-120b)\n"
                f"{'─' * 52}\n"
                f"{narration}"
            )

        return result

    except Exception as e:
        return f"Error en ASTRA Agent: {e}"


# ==========================================
# DEBUG
# ==========================================

def debug_request(text: str) -> dict:
    analysis = analyze_request(text)
    return {
        "input":  text,
        "intent": analysis["intent"],
        "tool":   analysis["tool"],
    }
