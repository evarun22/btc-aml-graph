import json
import time
from pathlib import Path

import pytest

from api.services.ai_service import AIService


@pytest.fixture
def governed_service(tmp_path, monkeypatch):
    monkeypatch.setenv("AI_PROVIDER", "disabled")
    monkeypatch.setenv("AI_AUDIT_LOG", "true")
    monkeypatch.setenv("AI_AUDIT_LOG_PATH", str(tmp_path / "ai_audit.jsonl"))
    monkeypatch.setenv("AI_MAX_PROMPT_CHARS", "50")
    monkeypatch.setenv("AI_MAX_CONTEXT_ITEMS", "5")
    monkeypatch.setenv("AI_MAX_STRING_CHARS", "20")

    return AIService()


def test_disabled_provider_is_unavailable(governed_service):
    assert governed_service.is_available() is False


def test_redact_sensitive_keys(governed_service):
    data = {
        "password": "secret-password",
        "api_key": "secret-key",
        "authorization": "Bearer token",
        "nested": {
            "token": "abc123",
            "safe_field": "visible",
        },
        "list": [
            {"private_key": "should-hide"},
            {"normal": "ok"},
        ],
    }

    redacted = governed_service._redact_sensitive(data)

    assert redacted["password"] == "[REDACTED]"
    assert redacted["api_key"] == "[REDACTED]"
    assert redacted["authorization"] == "[REDACTED]"
    assert redacted["nested"]["token"] == "[REDACTED]"
    assert redacted["nested"]["safe_field"] == "visible"
    assert redacted["list"][0]["private_key"] == "[REDACTED]"
    assert redacted["list"][1]["normal"] == "ok"


def test_prepare_context_removes_graph(governed_service):
    data = {
        "address": "bc1qexample",
        "risk_score": 80,
        "graph": {
            "nodes": [{"id": "1"}],
            "edges": [{"source": "1", "target": "2"}],
        },
    }

    prepared = governed_service._prepare_context(data)

    assert "graph" not in prepared
    assert prepared["address"] == "bc1qexample"
    assert prepared["risk_score"] == 80


def test_limit_prompt_truncates_large_prompt(governed_service):
    prompt = "x" * 200

    limited = governed_service._limit_prompt(prompt)

    assert len(limited) < 200
    assert "truncated" in limited.lower()


def test_write_audit_log_creates_jsonl(governed_service):
    audit_path = governed_service.audit_path

    governed_service._write_audit_log(
        endpoint="explain-alert",
        status="success",
        started_at=time.perf_counter(),
        prompt_chars=100,
        output_chars=50,
    )

    assert audit_path.exists()

    lines = audit_path.read_text().strip().splitlines()
    assert len(lines) == 1

    record = json.loads(lines[0])

    assert record["endpoint"] == "explain-alert"
    assert record["provider"] == "disabled"
    assert record["status"] == "success"
    assert record["prompt_chars"] == 100
    assert record["output_chars"] == 50
    assert "latency_ms" in record
    assert "created_at" in record
