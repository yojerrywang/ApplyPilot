"""
Unified LLM client for ApplyPilot.

Auto-detects provider from environment:
  GEMINI_API_KEY  -> Google Gemini via native API (default: gemini-2.0-flash)
  OPENAI_API_KEY  -> OpenAI (default: gpt-4o-mini)
  LLM_URL         -> Local llama.cpp / Ollama compatible endpoint

LLM_MODEL env var overrides the model name for any provider.

NOTE: Gemini now uses the native generateContent API instead of the OpenAI-
compatible translation layer, which is more reliable (avoids 403/429 issues
with the /v1beta/openai/* endpoint). See GitHub issue #1.
"""

import logging
import os
import time

import httpx

log = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Provider detection
# ---------------------------------------------------------------------------

# Provider constants
_PROVIDER_GEMINI = "gemini"
_PROVIDER_OPENAI = "openai"
_PROVIDER_LOCAL = "local"


def _detect_provider() -> tuple[str, str, str, str]:
    """Return (provider, base_url, model, api_key) based on environment variables."""
    gemini_key = os.environ.get("GEMINI_API_KEY", "")
    openai_key = os.environ.get("OPENAI_API_KEY", "")
    local_url = os.environ.get("LLM_URL", "")
    model_override = os.environ.get("LLM_MODEL", "")

    if gemini_key and not local_url:
        return (
            _PROVIDER_GEMINI,
            "https://generativelanguage.googleapis.com/v1beta",
            model_override or "gemini-2.0-flash",
            gemini_key,
        )

    if openai_key and not local_url:
        return (
            _PROVIDER_OPENAI,
            "https://api.openai.com/v1",
            model_override or "gpt-4o-mini",
            openai_key,
        )

    if local_url:
        return (
            _PROVIDER_LOCAL,
            local_url.rstrip("/"),
            model_override or "local-model",
            os.environ.get("LLM_API_KEY", ""),
        )

    raise RuntimeError(
        "No LLM provider configured. "
        "Set GEMINI_API_KEY, OPENAI_API_KEY, or LLM_URL in your environment."
    )

# ---------------------------------------------------------------------------
# Client
# ---------------------------------------------------------------------------

_MAX_RETRIES = 6
_TIMEOUT = 300  # seconds (bumped for free OpenRouter queues)
_RETRY_BASE_WAIT = 5  # seconds — longer base wait for Gemini free tier


class LLMClient:
    """Multi-provider LLM client. Uses native APIs where possible."""

    def __init__(self, provider: str, base_url: str, model: str, api_key: str) -> None:
        self.provider = provider
        self.base_url = base_url
        self.model = model
        self.api_key = api_key
        self._client = httpx.Client(timeout=_TIMEOUT)

    # -- public API ---------------------------------------------------------

    def chat(
        self,
        messages: list[dict],
        temperature: float = 0.0,
        max_tokens: int = 4096,
    ) -> str:
        """Send a chat completion request and return the assistant message text."""
        if self.provider == _PROVIDER_GEMINI:
            return self._chat_gemini(messages, temperature, max_tokens)
        return self._chat_openai(messages, temperature, max_tokens)

    def ask(self, prompt: str, **kwargs) -> str:
        """Convenience: single user prompt -> assistant response."""
        return self.chat([{"role": "user", "content": prompt}], **kwargs)

    def close(self) -> None:
        self._client.close()

    # -- Gemini native API --------------------------------------------------

    def _chat_gemini(
        self,
        messages: list[dict],
        temperature: float,
        max_tokens: int,
    ) -> str:
        """Call Gemini's native generateContent endpoint."""
        # Convert OpenAI-style messages to Gemini format
        system_text = None
        contents = []
        for msg in messages:
            role = msg.get("role", "user")
            text = msg.get("content", "")
            if role == "system":
                system_text = text
            else:
                # Gemini uses "user" and "model" (not "assistant")
                gemini_role = "model" if role == "assistant" else "user"
                contents.append({
                    "role": gemini_role,
                    "parts": [{"text": text}],
                })

        payload: dict = {
            "contents": contents,
            "generationConfig": {
                "temperature": temperature,
                "maxOutputTokens": max_tokens,
            },
        }
        if system_text:
            payload["system_instruction"] = {
                "parts": [{"text": system_text}],
            }

        url = f"{self.base_url}/models/{self.model}:generateContent"
        headers = {
            "Content-Type": "application/json",
            "x-goog-api-key": self.api_key,
        }

        return self._request_with_retry(url, payload, headers, parser=self._parse_gemini)

    @staticmethod
    def _parse_gemini(data: dict) -> str:
        """Extract text from Gemini native API response."""
        try:
            return data["candidates"][0]["content"]["parts"][0]["text"]
        except (KeyError, IndexError) as e:
            raise RuntimeError(f"Unexpected Gemini response format: {e}\n{data}") from e

    # -- OpenAI-compatible API (OpenAI, local) ------------------------------

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

            except httpx.TimeoutException:
                if attempt < _MAX_RETRIES - 1:
                    wait = _RETRY_BASE_WAIT * (attempt + 1)
                    log.warning(
                        "LLM request timed out, retrying in %ds (attempt %d/%d)",
                        wait, attempt + 1, _MAX_RETRIES,
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
