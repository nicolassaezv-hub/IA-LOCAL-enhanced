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
from memory_router import (
    save_chat,
    get_context
)

from argument_parser import parse_arguments

from tool_registry import (
    tool_exists
)

from tool_executor import execute

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
        args = parse_arguments(
           intent,
           user_input
        )   
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

        result = execute(
           tool_name,
           *args
        )
        save_chat(
           user_input,
           str(result)
        )
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
