# tool_executor.py

"""
Ejecutor inteligente de herramientas ASTRA
"""

import inspect

from tool_registry import (
    get_tool,
    tool_exists
)


def get_signature(tool_name):

    tool = get_tool(tool_name)

    if tool is None:
        return None

    try:
        return inspect.signature(tool)

    except Exception:
        return None


def validate_arguments(tool_name, args):

    tool = get_tool(tool_name)

    if tool is None:
        return False, "Herramienta no encontrada"

    try:

        sig = inspect.signature(tool)

        sig.bind(*args)

        return True, None

    except TypeError as e:

        return False, str(e)


def execute(tool_name, *args, **kwargs):

    if not tool_exists(tool_name):

        return f"Herramienta '{tool_name}' no existe"

    tool = get_tool(tool_name)

    try:

        valid, error = validate_arguments(
            tool_name,
            args
        )

        if not valid:

            return (
                f"Argumentos inválidos para "
                f"{tool_name}: {error}"
            )

        result = tool(*args, **kwargs)

        return result

    except Exception as e:

        return (
            f"Error ejecutando "
            f"{tool_name}: {e}"
        )


def describe_tool(tool_name):

    tool = get_tool(tool_name)

    if tool is None:

        return {
            "exists": False
        }

    try:

        sig = inspect.signature(tool)

        return {
            "exists": True,
            "name": tool_name,
            "signature": str(sig),
            "doc": inspect.getdoc(tool)
        }

    except Exception:

        return {
            "exists": True,
            "name": tool_name,
            "signature": "unknown",
            "doc": None
        }
