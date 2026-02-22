import pytest

from applypilot import llm


def test_detect_provider_gemini_default(monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "g-key")
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("LLM_URL", raising=False)
    monkeypatch.delenv("LLM_MODEL", raising=False)

    provider, base_url, model, api_key = llm._detect_provider()

    assert provider == "gemini"
    assert "generativelanguage.googleapis.com" in base_url
    assert model == "gemini-2.0-flash"
    assert api_key == "g-key"


def test_detect_provider_openai_default(monkeypatch):
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    monkeypatch.setenv("OPENAI_API_KEY", "o-key")
    monkeypatch.delenv("LLM_URL", raising=False)
    monkeypatch.delenv("LLM_MODEL", raising=False)

    provider, base_url, model, api_key = llm._detect_provider()

    assert provider == "openai"
    assert base_url == "https://api.openai.com/v1"
    assert model == "gpt-4o-mini"
    assert api_key == "o-key"


def test_detect_provider_local_has_precedence(monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "g-key")
    monkeypatch.setenv("OPENAI_API_KEY", "o-key")
    monkeypatch.setenv("LLM_URL", "http://localhost:8080/v1")
    monkeypatch.setenv("LLM_API_KEY", "local-key")

    provider, base_url, model, api_key = llm._detect_provider()

    assert provider == "local"
    assert base_url == "http://localhost:8080/v1"
    assert model == "local-model"
    assert api_key == "local-key"


def test_detect_provider_model_override(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "o-key")
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    monkeypatch.delenv("LLM_URL", raising=False)
    monkeypatch.setenv("LLM_MODEL", "gpt-5-mini")

    _, _, model, _ = llm._detect_provider()

    assert model == "gpt-5-mini"


def test_detect_provider_raises_without_configuration(monkeypatch):
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("LLM_URL", raising=False)
    monkeypatch.delenv("LLM_MODEL", raising=False)

    with pytest.raises(RuntimeError):
        llm._detect_provider()
