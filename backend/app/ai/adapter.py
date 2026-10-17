"""Single LLM adapter. Swap the provider by implementing `LLMProvider.complete_json`."""
import json
import re
from typing import Protocol

from ..config import settings


class LLMProvider(Protocol):
    name: str

    def complete_json(self, system: str, user: str, schema: dict) -> dict: ...


class OpenAIProvider:
    name = "openai"

    def __init__(self):
        from openai import OpenAI
        self.client = OpenAI(api_key=settings.openai_api_key, timeout=15)

    def complete_json(self, system: str, user: str, schema: dict) -> dict:
        r = self.client.chat.completions.create(
            model=settings.openai_model,
            messages=[{"role": "system", "content": system}, {"role": "user", "content": user}],
            response_format={"type": "json_schema", "json_schema": {"name": "result", "strict": True, "schema": schema}},
            temperature=0.1,
        )
        return json.loads(r.choices[0].message.content)


class OfflineProvider:
    """Keyword-based fallback used when no API key is configured, so the product still runs."""
    name = "offline"

    def complete_json(self, system: str, user: str, schema: dict) -> dict:
        raise NotImplementedError


_provider = None


def get_provider():
    global _provider
    if _provider is None:
        _provider = OpenAIProvider() if settings.openai_api_key else OfflineProvider()
    return _provider


def validate(data: dict, schema: dict) -> bool:
    """Minimal structural validation against our flat object schemas."""
    if not isinstance(data, dict):
        return False
    for k in schema.get("required", []):
        if k not in data:
            return False
    for k, spec in schema.get("properties", {}).items():
        if k not in data:
            continue
        v, t = data[k], spec.get("type")
        if t == "string" and not isinstance(v, str):
            return False
        if t == "number" and not isinstance(v, (int, float)):
            return False
        if t == "array" and not isinstance(v, list):
            return False
        if "enum" in spec and v not in spec["enum"]:
            return False
    return True


AR = re.compile(r"[؀-ۿ]")


def is_arabic(text: str) -> bool:
    return len(AR.findall(text)) > max(2, len(text) * 0.3)
