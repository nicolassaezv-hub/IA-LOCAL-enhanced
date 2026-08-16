"""Offline regressions for the Groq model-id migration."""
from __future__ import annotations

import inspect
import json
import sys
from types import ModuleType

import ai_models


def test_groq_key_selects_gpt_oss_120b(monkeypatch):
    monkeypatch.setenv("GROQ_API_KEY", "unit-test-placeholder")

    assert ai_models._active_model() == "openai/gpt-oss-120b"
    assert ai_models._GROQ_MODEL == "openai/gpt-oss-120b"
    assert ai_models._GROQ_BASE_URL == "https://api.groq.com/openai/v1"


def test_groq_client_keeps_existing_credential_and_endpoint_without_network(
    monkeypatch
):
    captured = {}
    fake_openai = ModuleType("openai")

    class FakeOpenAI:
        def __init__(self, **kwargs):
            captured.update(kwargs)

    fake_openai.OpenAI = FakeOpenAI
    credential = "unit-test-placeholder"
    monkeypatch.setenv("GROQ_API_KEY", credential)
    monkeypatch.setitem(sys.modules, "openai", fake_openai)
    monkeypatch.setattr(ai_models, "_groq_client", None)

    ai_models._get_client()

    assert captured == {
        "api_key": credential,
        "base_url": "https://api.groq.com/openai/v1",
    }


def test_runtime_configuration_has_no_retired_model_or_hardcoded_groq_secret():
    source = inspect.getsource(ai_models)

    assert "llama-3.3-70b-versatile" not in source
    assert 'os.environ.get("GROQ_API_KEY")' in source
    assert "gsk_" not in source


def test_workspace_status_reports_gpt_oss_when_groq_is_configured(monkeypatch):
    monkeypatch.setenv("GROQ_API_KEY", "unit-test-placeholder")
    from workspace import server

    payload = json.loads(server.get_status().body)

    assert payload["model"] == "openai/gpt-oss-120b"
    assert payload["model_configured"] == "openai/gpt-oss-120b"
