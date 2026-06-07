# test_main.py
import pytest
from modules_extra import calcular_integral, redis_set, redis_get

def test_sympy_integral():
    resultado = calcular_integral("sin(x)", "x", 0, 3.14159)
    assert "Integral" in resultado
    assert "pi" in resultado or "3.14159" in resultado

def test_redis_set_get():
    redis_set("pytest", "funciona")
    valor = redis_get("pytest")
    assert valor == "funciona"