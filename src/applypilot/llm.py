"""
Unified LLM client for ApplyPilot.

Supports Gemini, OpenAI, and local OpenAI-compatible endpoints.
"""

import logging
import os
import time

import httpx

log = logging.getLogger(__name__)

# Provider constants
_PROVIDER_GEMINI = "gemini"
_PROVIDER_OPENAI = "openai"
_PROVIDER_ANTHROPIC = "anthropic"
_PROVIDER_LOCAL = "local"
_VALID_PROVIDERS = {_PROVIDER_GEMINI, _PROVIDER_OPENAI, _PROVIDER_ANTHROPIC, _PROVIDER_LOCAL}

_DEFAULT_MODELS = {
    _PROVIDER_GEMINI: "gemini-2.0-flash",
    _PROVIDER_OPENAI: "gpt-4o-mini",
    _PROVIDER_ANTHROPIC: "claude-haiku-4-5-20251001",
    _PROVIDER_LOCAL: "local-model",
}


def _detect_provider() -> tuple[str, str, str, str]:
    """Return (provider, base_url, model, api_key) from environment."""
    model_override = os.environ.get("LLM_MODEL", "").strip()
    provider_override = os.environ.get("LLM_PROVIDER", "").strip().lower()
    gemini_key = os.environ.get("GEMINI_API_KEY", "").strip()
    openai_key = os.environ.get("OPENAI_API_KEY", "").strip()
    anthropic_key = os.environ.get("ANTHROPIC_API_KEY", "").strip()
    local_url = os.environ.get("LLM_URL", "").strip().rstrip("/")
    local_key = os.environ.get("LLM_API_KEY", "").strip() or openai_key

    def resolve_model(provider: str) -> str:
        if not model_override:
            return _DEFAULT_MODELS[provider]

        if provider != _PROVIDER_LOCAL:
            return model_override

        # Avoid accidentally reusing cloud defaults (often loaded from .env) for local endpoints.
        remote_defaults = {
            _DEFAULT_MODELS[_PROVIDER_OPENAI],
            _DEFAULT_MODELS[_PROVIDER_GEMINI],
        }
        if provider_override != _PROVIDER_LOCAL and model_override in remote_defaults:
            return _DEFAULT_MODELS[_PROVIDER_LOCAL]

        return model_override

    def resolve(provider: str) -> tuple[str, str, str, str]:
        if provider == _PROVIDER_LOCAL:
            if not local_url:
                raise RuntimeError("LLM_PROVIDER=local requires LLM_URL.")
            return (
                _PROVIDER_LOCAL,
                local_url,
                resolve_model(_PROVIDER_LOCAL),
                local_key,
            )

        if provider == _PROVIDER_GEMINI:
            if not gemini_key:
                raise RuntimeError("LLM_PROVIDER=gemini requires GEMINI_API_KEY.")
            return (
                _PROVIDER_GEMINI,
                "https://generativelanguage.googleapis.com/v1beta/openai",
                resolve_model(_PROVIDER_GEMINI),
                gemini_key,
            )

        if provider == _PROVIDER_OPENAI:
            if not openai_key:
                raise RuntimeError("LLM_PROVIDER=openai requires OPENAI_API_KEY.")
            return (
                _PROVIDER_OPENAI,
                "https://api.openai.com/v1",
                resolve_model(_PROVIDER_OPENAI),
                openai_key,
            )

        if provider == _PROVIDER_ANTHROPIC:
            if not anthropic_key:
                raise RuntimeError("LLM_PROVIDER=anthropic requires ANTHROPIC_API_KEY.")
            return (
                _PROVIDER_ANTHROPIC,
                "https://api.anthropic.com/v1",
                resolve_model(_PROVIDER_ANTHROPIC),
                anthropic_key,
            )

        raise RuntimeError(f"Unsupported LLM provider: {provider}")

    if provider_override:
        if provider_override not in _VALID_PROVIDERS:
            valid = ", ".join(sorted(_VALID_PROVIDERS))
            raise RuntimeError(f"Invalid LLM_PROVIDER '{provider_override}'. Valid values: {valid}.")
        return resolve(provider_override)

    # Auto-detect precedence:
    # 1) local endpoint (explicit LLM_URL)
    # 2) Anthropic
    # 3) Gemini
    # 4) OpenAI
    if local_url:
        return resolve(_PROVIDER_LOCAL)
    if anthropic_key:
        return resolve(_PROVIDER_ANTHROPIC)
    if gemini_key:
        return resolve(_PROVIDER_GEMINI)
    if openai_key:
        return resolve(_PROVIDER_OPENAI)

    raise RuntimeError(
        "No LLM provider configured. Set ANTHROPIC_API_KEY, GEMINI_API_KEY, OPENAI_API_KEY, or LLM_URL."
    )


# ---------------------------------------------------------------------------
# Client
# ---------------------------------------------------------------------------

_MAX_RETRIES = int(os.environ.get("LLM_MAX_RETRIES", "3"))
_TIMEOUT = float(os.environ.get("LLM_TIMEOUT", "30"))  # seconds
_RETRY_BASE_WAIT = float(os.environ.get("LLM_RETRY_BASE_WAIT", "2"))  # seconds


class LLMClient:
    """OpenAI-compatible LLM client."""

    def __init__(self, provider: str, base_url: str, model: str, api_key: str) -> None:
        self.provider = provider
        self.base_url = base_url
        self.model = model
        self.api_key = api_key
        timeout = httpx.Timeout(_TIMEOUT, connect=min(10.0, _TIMEOUT))
        self._client = httpx.Client(timeout=timeout)

    # -- public API ---------------------------------------------------------

    def chat(
        self,
        messages: list[dict],
        temperature: float = 0.0,
        max_tokens: int = 4096,
    ) -> str:
        """Send a chat completion request and return the assistant message text."""
        if self.provider == _PROVIDER_ANTHROPIC:
            return self._chat_anthropic(messages, temperature, max_tokens)
        return self._chat_openai(messages, temperature, max_tokens)

    def ask(self, prompt: str, **kwargs) -> str:
        """Convenience: single user prompt -> assistant response."""
        return self.chat([{"role": "user", "content": prompt}], **kwargs)

    def close(self) -> None:
        self._client.close()

    # -- Anthropic API ------------------------------------------------------

    def _chat_anthropic(
        self,
        messages: list[dict],
        temperature: float,
        max_tokens: int,
    ) -> str:
        """Call Anthropic Messages API."""
        headers = {
            "Content-Type": "application/json",
            "x-api-key": self.api_key,
            "anthropic-version": "2023-06-01",
        }

        # Extract system message if present
        system_text = None
        api_messages = []
        for msg in messages:
            if msg["role"] == "system":
                system_text = msg["content"]
            else:
                api_messages.append({"role": msg["role"], "content": msg["content"]})

        payload: dict = {
            "model": self.model,
            "messages": api_messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
        }
        if system_text:
            payload["system"] = system_text

        url = f"{self.base_url}/messages"
        return self._request_with_retry(url, payload, headers, parser=self._parse_anthropic)

    @staticmethod
    def _parse_anthropic(data: dict) -> str:
        """Extract text from Anthropic Messages API response."""
        return data["content"][0]["text"]

    # -- OpenAI API ---------------------------------------------------------

    def _chat_openai(
        self,
        messages: list[dict],
        temperature: float,
        max_tokens: int,
    ) -> str:
        """Call OpenAI-compatible chat/completions endpoint."""
        # Qwen3 optimization: prepend /no_think to skip chain-of-thought
        if "qwen" in self.model.lower() and messages:
            first = messages[0]
            if first.get("role") == "user" and not first["content"].startswith("/no_think"):
                messages = [{"role": first["role"], "content": f"/no_think\n{first['content']}"}] + messages[1:]

        headers: dict[str, str] = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"

        payload = {
            "model": self.model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
        }

        url = f"{self.base_url}/chat/completions"
        return self._request_with_retry(url, payload, headers, parser=self._parse_openai)

    @staticmethod
    def _parse_openai(data: dict) -> str:
        """Extract text from OpenAI-compatible API response."""
        return data["choices"][0]["message"]["content"]

    # -- Shared retry logic -------------------------------------------------

    def _request_with_retry(
        self,
        url: str,
        payload: dict,
        headers: dict[str, str],
        parser: callable,
    ) -> str:
        """POST with exponential backoff retry on 429/503/timeout."""
        for attempt in range(_MAX_RETRIES):
            try:
                resp = self._client.post(url, json=payload, headers=headers)

                if resp.status_code in (429, 503) and attempt < _MAX_RETRIES - 1:
                    wait = _RETRY_BASE_WAIT * (attempt + 1)
                    log.warning(
                        "LLM returned %s, retrying in %ds (attempt %d/%d)",
                        resp.status_code, wait, attempt + 1, _MAX_RETRIES,
                    )
                    time.sleep(wait)
                    continue

                resp.raise_for_status()
                return parser(resp.json())

            except (httpx.TimeoutException, httpx.RequestError) as e:
                if attempt < _MAX_RETRIES - 1:
                    wait = _RETRY_BASE_WAIT * (attempt + 1)
                    log.warning(
                        "LLM request failed (%s), retrying in %ss (attempt %d/%d)",
                        e.__class__.__name__, wait, attempt + 1, _MAX_RETRIES,
                    )
                    time.sleep(wait)
                    continue
                raise

        raise RuntimeError("LLM request failed after all retries")


# ---------------------------------------------------------------------------
# Singleton
# ---------------------------------------------------------------------------

_instance: LLMClient | None = None


def get_client() -> LLMClient:
    """Return (or create) the module-level LLMClient singleton."""
    global _instance
    if _instance is None:
        provider, base_url, model, api_key = _detect_provider()
        log.info("LLM provider: %s  base: %s  model: %s", provider, base_url, model)
        _instance = LLMClient(provider, base_url, model, api_key)
    return _instance
