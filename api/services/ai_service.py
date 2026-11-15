import os
import json
import logging
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

import httpx


logger = logging.getLogger(__name__)


class AIProviderError(Exception):
    """
    Base error for AI provider failures.
    """


class AIProviderUnavailableError(AIProviderError):
    """
    Raised when the AI provider is disabled, unreachable, or misconfigured.
    """


class AIService:
    def __init__(self):
        self.provider = os.getenv("AI_PROVIDER", "disabled").lower()

        # Timeouts
        self.timeout = float(os.getenv("AI_TIMEOUT_SECONDS", "300"))
        self.connect_timeout = float(os.getenv("AI_CONNECT_TIMEOUT_SECONDS", "5"))

        # Generation settings
        self.temperature = float(os.getenv("AI_TEMPERATURE", "0.2"))
        self.max_tokens = int(os.getenv("AI_MAX_TOKENS", "600"))

        # Context safety settings
        self.max_context_items = int(os.getenv("AI_MAX_CONTEXT_ITEMS", "10"))
        self.max_string_chars = int(os.getenv("AI_MAX_STRING_CHARS", "500"))
        self.max_prompt_chars = int(os.getenv("AI_MAX_PROMPT_CHARS", "12000"))

        # Audit logging settings
        self.audit_enabled = os.getenv("AI_AUDIT_LOG", "true").lower() in {
            "1",
            "true",
            "yes",
            "on",
        }
        self.audit_path = Path(os.getenv("AI_AUDIT_LOG_PATH", "logs/ai_audit.jsonl"))

        # Sensitive key patterns that should never be sent to the model.
        self.sensitive_key_patterns = (
            "password",
            "passwd",
            "secret",
            "api_key",
            "apikey",
            "token",
            "authorization",
            "private_key",
            "access_key",
            "credential",
        )

        # Ollama
        self.ollama_base_url = os.getenv(
            "OLLAMA_BASE_URL",
            "http://localhost:11434"
        ).rstrip("/")
        self.ollama_model = os.getenv("OLLAMA_MODEL", "llama3.1")

        # OpenAI
        self.openai_api_key = os.getenv("OPENAI_API_KEY", "")
        self.openai_model = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
        self.openai_base_url = os.getenv(
            "OPENAI_BASE_URL",
            "https://api.openai.com/v1"
        ).rstrip("/")

        # Anthropic
        self.anthropic_api_key = os.getenv("ANTHROPIC_API_KEY", "")
        self.anthropic_model = os.getenv(
            "ANTHROPIC_MODEL",
            "claude-3-5-sonnet-latest"
        )

        # llama.cpp
        llamacpp_base = os.getenv(
            "LLAMACPP_BASE_URL",
            "http://127.0.0.1:8080"
        ).rstrip("/")

        if llamacpp_base.endswith("/v1"):
            self.llamacpp_api_base = llamacpp_base
        else:
            self.llamacpp_api_base = f"{llamacpp_base}/v1"

        self.llamacpp_model = os.getenv("LLAMACPP_MODEL", "")

        #
        # Important for your llama.cpp build.
        # This avoids the:
        # "Error: gzip is not supported by this browser"
        # issue.
        #
        self.llamacpp_headers = {
            "Accept": "application/json",
            "Accept-Encoding": "identity",
        }

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _timeout(self) -> httpx.Timeout:
        return httpx.Timeout(
            self.timeout,
            connect=self.connect_timeout,
        )

    def _short_timeout(self) -> httpx.Timeout:
        return httpx.Timeout(
            5.0,
            connect=2.0,
        )

    def _system_prompt(self) -> str:
        return (
            "You are a professional Bitcoin AML analyst. "
            "Answer using only the provided JSON context. "
            "Do not hallucinate facts. "
            "Do not write Cypher. "
            "Do not suggest destructive database operations. "
            "Explain the alert or address risk in clear plain English. "
            "Keep the answer concise, structured, and suitable for a compliance dashboard."
        )

    def _is_sensitive_key(self, key: Any) -> bool:
        """
        Return True if a dictionary key looks like a secret or credential.
        """
        key_str = str(key).lower()

        return any(
            pattern in key_str
            for pattern in self.sensitive_key_patterns
        )

    def _redact_sensitive(self, value: Any) -> Any:
        """
        Recursively redact values whose keys look sensitive.

        This prevents accidental leakage of secrets into model prompts.
        """
        if isinstance(value, dict):
            redacted = {}

            for key, item in value.items():
                if self._is_sensitive_key(key):
                    redacted[key] = "[REDACTED]"
                else:
                    redacted[key] = self._redact_sensitive(item)

            return redacted

        if isinstance(value, list):
            return [self._redact_sensitive(item) for item in value]

        return value

    def _sanitize_value(self, value: Any) -> Any:
        """
        Prevent extremely large strings or nested structures from being sent
        to the local model.
        """
        if isinstance(value, str):
            if len(value) > self.max_string_chars:
                return value[: self.max_string_chars] + "...[truncated]"
            return value

        if isinstance(value, dict):
            return self._truncate_context(value)

        if isinstance(value, list):
            sanitized = []
            for item in value[: self.max_context_items]:
                sanitized.append(self._sanitize_value(item))
            return sanitized

        return value

    def _truncate_context(self, data: dict[str, Any]) -> dict[str, Any]:
        """
        Reduce large API payloads before sending them to the LLM.
        """
        if not isinstance(data, dict):
            return {}

        safe: dict[str, Any] = {}

        for key, value in data.items():
            safe[key] = self._sanitize_value(value)

        return safe

    def _prepare_context(self, data: dict[str, Any]) -> dict[str, Any]:
        """
        Prepare structured data safely for the model.

        This:
        - redacts sensitive keys
        - truncates large lists
        - truncates long strings
        - removes large graph payloads
        """
        if not isinstance(data, dict):
            return {}

        safe_data = self._redact_sensitive(data)
        safe_data = self._truncate_context(safe_data)

        # Graph payloads are usually too large and not useful
        # for plain-English explanations or summaries.
        safe_data.pop("graph", None)

        return safe_data

    def _limit_prompt(self, prompt: str) -> str:
        """
        Cap the final prompt size before sending it to the model.
        """
        if len(prompt) <= self.max_prompt_chars:
            return prompt

        return (
            prompt[: self.max_prompt_chars]
            + "\n\n[context truncated for model limit]"
        )

    def _json_dumps(self, data: Any) -> str:
        return json.dumps(
            data,
            indent=2,
            default=str,
            ensure_ascii=False,
        )

    def _write_audit_log(
        self,
        endpoint: str,
        status: str,
        started_at: float,
        prompt_chars: Optional[int] = None,
        output_chars: Optional[int] = None,
        error: Optional[str] = None,
    ) -> None:
        """
        Write a single JSON line to the AI audit log.

        Example:
            logs/ai_audit.jsonl
        """
        if not self.audit_enabled:
            return

        record = {
            "endpoint": endpoint,
            "provider": self.provider,
            "model": self.current_model(),
            "status": status,
            "latency_ms": int((time.perf_counter() - started_at) * 1000),
            "created_at": datetime.now(timezone.utc).isoformat(),
        }

        if prompt_chars is not None:
            record["prompt_chars"] = prompt_chars

        if output_chars is not None:
            record["output_chars"] = output_chars

        if error:
            record["error"] = str(error)[:500]

        try:
            self.audit_path.parent.mkdir(parents=True, exist_ok=True)

            with self.audit_path.open("a", encoding="utf-8") as file:
                file.write(json.dumps(record, default=str) + "\n")

        except Exception:
            logger.exception("Failed to write AI audit log")

    def _extract_openai_content(self, data: dict[str, Any]) -> str:
        """
        Extract content from an OpenAI-compatible response.
        Used by llama.cpp and OpenAI.
        """
        try:
            content = data["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError) as exc:
            raise AIProviderError(
                "Unexpected OpenAI-compatible response format"
            ) from exc

        if content is None:
            raise AIProviderError("AI provider returned empty content")

        content = str(content).strip()

        if not content:
            raise AIProviderError("AI provider returned empty content")

        return content

    # ------------------------------------------------------------------
    # llama.cpp helpers
    # ------------------------------------------------------------------

    def _list_llamacpp_models(self) -> list[str]:
        """
        List models from llama.cpp's OpenAI-compatible /v1/models endpoint.

        Your current server returns both:
          - data[]
          - models[]

        This helper prefers data[], then falls back to models[].
        """
        url = f"{self.llamacpp_api_base}/models"

        with httpx.Client(
            timeout=self._short_timeout(),
            headers=self.llamacpp_headers,
        ) as client:
            response = client.get(url)
            response.raise_for_status()
            payload = response.json()

        items = payload.get("data") or payload.get("models") or []

        models: list[str] = []

        for item in items:
            if not isinstance(item, dict):
                continue

            model_id = item.get("id") or item.get("name")

            if model_id:
                models.append(str(model_id))

        return models

    def _resolve_llamacpp_model(self) -> Optional[str]:
        """
        Return the configured llama.cpp model.

        If no model is configured, fall back to the first available model.
        """
        if self.llamacpp_model:
            return self.llamacpp_model

        try:
            models = self._list_llamacpp_models()
        except Exception:
            return None

        if models:
            return models[0]

        return None

    def _call_llamacpp(self, user_prompt: str) -> str:
        model = self._resolve_llamacpp_model()

        if not model:
            raise AIProviderUnavailableError(
                "No llama.cpp model is available. "
                "Check LLAMACPP_MODEL and the running llama.cpp server."
            )

        url = f"{self.llamacpp_api_base}/chat/completions"

        payload = {
            "model": model,
            "stream": False,
            "temperature": self.temperature,
            "max_tokens": self.max_tokens,
            "messages": [
                {
                    "role": "system",
                    "content": self._system_prompt(),
                },
                {
                    "role": "user",
                    "content": user_prompt,
                },
            ],
        }

        try:
            with httpx.Client(
                timeout=self._timeout(),
                headers=self.llamacpp_headers,
            ) as client:
                response = client.post(url, json=payload)
                response.raise_for_status()
                data = response.json()
        except httpx.TimeoutException as exc:
            raise AIProviderError(
                "llama.cpp request timed out"
            ) from exc
        except httpx.HTTPStatusError as exc:
            raise AIProviderError(
                f"llama.cpp returned HTTP {exc.response.status_code}"
            ) from exc
        except httpx.HTTPError as exc:
            raise AIProviderError(
                f"llama.cpp request failed: {exc}"
            ) from exc

        return self._extract_openai_content(data)

    # ------------------------------------------------------------------
    # Ollama helper
    # ------------------------------------------------------------------

    def _call_ollama(self, user_prompt: str) -> str:
        url = f"{self.ollama_base_url}/api/chat"

        payload = {
            "model": self.ollama_model,
            "stream": False,
            "messages": [
                {
                    "role": "system",
                    "content": self._system_prompt(),
                },
                {
                    "role": "user",
                    "content": user_prompt,
                },
            ],
        }

        try:
            with httpx.Client(timeout=self._timeout()) as client:
                response = client.post(url, json=payload)
                response.raise_for_status()
                data = response.json()
        except httpx.TimeoutException as exc:
            raise AIProviderError("Ollama request timed out") from exc
        except httpx.HTTPError as exc:
            raise AIProviderError(f"Ollama request failed: {exc}") from exc

        try:
            content = data["message"]["content"]
        except (KeyError, TypeError) as exc:
            raise AIProviderError(
                "Unexpected Ollama response format"
            ) from exc

        if not content:
            raise AIProviderError("Ollama returned empty content")

        return str(content).strip()

    # ------------------------------------------------------------------
    # OpenAI helper
    # ------------------------------------------------------------------

    def _call_openai(self, user_prompt: str) -> str:
        if not self.openai_api_key:
            raise AIProviderUnavailableError(
                "OpenAI API key is not configured"
            )

        url = f"{self.openai_base_url}/chat/completions"

        headers = {
            "Authorization": f"Bearer {self.openai_api_key}",
            "Content-Type": "application/json",
        }

        payload = {
            "model": self.openai_model,
            "stream": False,
            "temperature": self.temperature,
            "max_tokens": self.max_tokens,
            "messages": [
                {
                    "role": "system",
                    "content": self._system_prompt(),
                },
                {
                    "role": "user",
                    "content": user_prompt,
                },
            ],
        }

        try:
            with httpx.Client(timeout=self._timeout()) as client:
                response = client.post(
                    url,
                    headers=headers,
                    json=payload,
                )
                response.raise_for_status()
                data = response.json()
        except httpx.TimeoutException as exc:
            raise AIProviderError("OpenAI request timed out") from exc
        except httpx.HTTPError as exc:
            raise AIProviderError(f"OpenAI request failed: {exc}") from exc

        return self._extract_openai_content(data)

    # ------------------------------------------------------------------
    # Anthropic helper
    # ------------------------------------------------------------------

    def _call_anthropic(self, user_prompt: str) -> str:
        if not self.anthropic_api_key:
            raise AIProviderUnavailableError(
                "Anthropic API key is not configured"
            )

        url = "https://api.anthropic.com/v1/messages"

        headers = {
            "x-api-key": self.anthropic_api_key,
            "anthropic-version": "2023-06-01",
            "Content-Type": "application/json",
        }

        payload = {
            "model": self.anthropic_model,
            "max_tokens": self.max_tokens,
            "temperature": self.temperature,
            "system": self._system_prompt(),
            "messages": [
                {
                    "role": "user",
                    "content": user_prompt,
                }
            ],
        }

        try:
            with httpx.Client(timeout=self._timeout()) as client:
                response = client.post(
                    url,
                    headers=headers,
                    json=payload,
                )
                response.raise_for_status()
                data = response.json()
        except httpx.TimeoutException as exc:
            raise AIProviderError("Anthropic request timed out") from exc
        except httpx.HTTPError as exc:
            raise AIProviderError(f"Anthropic request failed: {exc}") from exc

        try:
            content = data["content"][0]["text"]
        except (KeyError, IndexError, TypeError) as exc:
            raise AIProviderError(
                "Unexpected Anthropic response format"
            ) from exc

        if not content:
            raise AIProviderError("Anthropic returned empty content")

        return str(content).strip()

    # ------------------------------------------------------------------
    # Public API used by FastAPI routes
    # ------------------------------------------------------------------

    def is_available(self) -> bool:
        if self.provider == "disabled":
            return False

        if self.provider == "llamacpp":
            try:
                models = self._list_llamacpp_models()

                if not models:
                    return False

                if self.llamacpp_model:
                    return self.llamacpp_model in models

                return True

            except Exception as exc:
                logger.warning(
                    "llama.cpp availability check failed: %s",
                    exc,
                )
                return False

        if self.provider == "ollama":
            try:
                with httpx.Client(timeout=self._short_timeout()) as client:
                    response = client.get(
                        f"{self.ollama_base_url}/api/tags"
                    )
                    return response.status_code == 200
            except Exception as exc:
                logger.warning(
                    "Ollama availability check failed: %s",
                    exc,
                )
                return False

        if self.provider == "openai":
            return bool(self.openai_api_key)

        if self.provider == "anthropic":
            return bool(self.anthropic_api_key)

        logger.warning(
            "Unsupported AI provider configured: %s",
            self.provider,
        )

        return False

    def current_model(self) -> Optional[str]:
        if self.provider == "llamacpp":
            if self.llamacpp_model:
                return self.llamacpp_model

            try:
                models = self._list_llamacpp_models()
                return models[0] if models else None
            except Exception:
                return None

        if self.provider == "ollama":
            return self.ollama_model

        if self.provider == "openai":
            return self.openai_model

        if self.provider == "anthropic":
            return self.anthropic_model

        return None

    def generate(self, user_prompt: str) -> str:
        if self.provider == "disabled":
            raise AIProviderUnavailableError(
                "AI provider is disabled"
            )

        if self.provider == "llamacpp":
            return self._call_llamacpp(user_prompt)

        if self.provider == "ollama":
            return self._call_ollama(user_prompt)

        if self.provider == "openai":
            return self._call_openai(user_prompt)

        if self.provider == "anthropic":
            return self._call_anthropic(user_prompt)

        raise AIProviderUnavailableError(
            f"Unsupported AI provider: {self.provider}"
        )

    def explain_alert(self, alert: dict[str, Any]) -> str:
        started_at = time.perf_counter()
        prompt_chars: Optional[int] = None

        try:
            safe_alert = self._prepare_context(alert)

            prompt = (
                "/no_think\n"
                "Explain this Bitcoin AML alert in plain English.\n\n"
                "Alert JSON:\n"
                f"{self._json_dumps(safe_alert)}\n\n"
                "Explain:\n"
                "1. What the alert means.\n"
                "2. Why it is relevant for AML/compliance review.\n"
                "3. What evidence an analyst should inspect next.\n"
                "Keep the answer concise and professional."
            )

            prompt = self._limit_prompt(prompt)
            prompt_chars = len(prompt)

            explanation = self.generate(prompt)

            if not explanation:
                raise AIProviderError("AI provider returned empty content")

            self._write_audit_log(
                endpoint="explain-alert",
                status="success",
                started_at=started_at,
                prompt_chars=prompt_chars,
                output_chars=len(explanation),
            )

            return explanation

        except AIProviderUnavailableError:
            self._write_audit_log(
                endpoint="explain-alert",
                status="unavailable",
                started_at=started_at,
                prompt_chars=prompt_chars,
                error="AI provider unavailable",
            )
            raise

        except AIProviderError:
            self._write_audit_log(
                endpoint="explain-alert",
                status="provider_error",
                started_at=started_at,
                prompt_chars=prompt_chars,
                error="AI provider error",
            )
            raise

        except Exception as exc:
            self._write_audit_log(
                endpoint="explain-alert",
                status="error",
                started_at=started_at,
                prompt_chars=prompt_chars,
                error=exc,
            )
            raise AIProviderError("AI provider request failed") from exc

    def summarize_address(self, address_report: dict[str, Any]) -> str:
        started_at = time.perf_counter()
        prompt_chars: Optional[int] = None

        try:
            safe_report = self._prepare_context(address_report)

            prompt = (
                "/no_think\n"
                "Summarize the risk profile of this Bitcoin address in plain English.\n\n"
                "Address report JSON:\n"
                f"{self._json_dumps(safe_report)}\n\n"
                "Explain:\n"
                "1. Overall risk level.\n"
                "2. Key red flags.\n"
                "3. OFAC exposure, if present.\n"
                "4. Entity membership, if present.\n"
                "5. What an analyst should review next.\n"
                "Keep the answer concise and professional."
            )

            prompt = self._limit_prompt(prompt)
            prompt_chars = len(prompt)

            summary = self.generate(prompt)

            if not summary:
                raise AIProviderError("AI provider returned empty content")

            self._write_audit_log(
                endpoint="summarize-address",
                status="success",
                started_at=started_at,
                prompt_chars=prompt_chars,
                output_chars=len(summary),
            )

            return summary

        except AIProviderUnavailableError:
            self._write_audit_log(
                endpoint="summarize-address",
                status="unavailable",
                started_at=started_at,
                prompt_chars=prompt_chars,
                error="AI provider unavailable",
            )
            raise

        except AIProviderError:
            self._write_audit_log(
                endpoint="summarize-address",
                status="provider_error",
                started_at=started_at,
                prompt_chars=prompt_chars,
                error="AI provider error",
            )
            raise

        except Exception as exc:
            self._write_audit_log(
                endpoint="summarize-address",
                status="error",
                started_at=started_at,
                prompt_chars=prompt_chars,
                error=exc,
            )
            raise AIProviderError("AI provider request failed") from exc


ai_service = AIService()
