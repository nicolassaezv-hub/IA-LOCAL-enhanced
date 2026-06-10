# astra_agent.py

"""
ASTRA Agent

Capa inteligente superior.

Flujo:

usuario
   ↓
intent_router
   ↓
tool_registry
   ↓
herramienta
   ↓
OpenAI fallback
"""

from tool_registry import (
    tool_exists,
    execute_tool
)

from intent_router import (
    analyze_request
)

from ai_models import ask_openai


# ==========================================
# AGENTE PRINCIPAL
# ==========================================

def process_request(user_input):

    try:

        analysis = analyze_request(user_input)

        intent = analysis["intent"]
        tool_name = analysis["tool"]

        print(f"[ASTRA] Intent detectado: {intent}")

        # ------------------------------------------------
        # NO SE ENCONTRÓ HERRAMIENTA
        # ------------------------------------------------

        if tool_name is None:

            return ask_openai(user_input)

        # ------------------------------------------------
        # HERRAMIENTA NO REGISTRADA
        # ------------------------------------------------

        if not tool_exists(tool_name):

            return ask_openai(user_input)

        # ------------------------------------------------
        # EJECUCIÓN SIMPLE
        # ------------------------------------------------

        result = execute_tool(tool_name)

        return result

    except Exception as e:

        return f"Error en ASTRA Agent: {e}"


# ==========================================
# DEBUG
# ==========================================

def debug_request(text):

    analysis = analyze_request(text)

    return {
        "input": text,
        "intent": analysis["intent"],
        "tool": analysis["tool"]
    }
