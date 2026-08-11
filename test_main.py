# test_main.py
import types

import modules_extra
from modules_extra import calcular_integral

def test_sympy_integral():
    resultado = calcular_integral("sin(x)", "x", 0, 3.14159)
    assert "Integral" in resultado
    assert "pi" in resultado or "3.14159" in resultado

def test_redis_set_get(monkeypatch):
    """Exercise the Redis adapter without requiring a localhost server."""
    values = {}

    class FakeRedis:
        def __init__(self, *, host, port, db):
            assert (host, port, db) == ("localhost", 6379, 0)

        def set(self, key, value):
            values[key] = value.encode("utf-8")

        def get(self, key):
            return values.get(key)

    monkeypatch.setattr(modules_extra, "HAS_REDIS", True)
    monkeypatch.setattr(
        modules_extra,
        "redis_lib",
        types.SimpleNamespace(Redis=FakeRedis),
    )

    result = modules_extra.redis_set("pytest", "funciona")
    assert result == "Guardado en Redis: pytest -> funciona"
    assert modules_extra.redis_get("pytest") == "funciona"
