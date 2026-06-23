"""Абстракція провайдера LLM (ТЗ §9): OpenAI-сумісний API (локальний Ollama/vLLM
або хмара). Вимкнено, поки AI_ENABLED=false або не задано AI_BASE_URL.
Жодних мережевих викликів, поки провайдер вимкнено."""

import hashlib
import logging

import httpx

from app.config import get_settings

logger = logging.getLogger(__name__)


class AIProvider:
    def __init__(self) -> None:
        s = get_settings()
        self.base_url = s.ai_base_url.rstrip("/")
        self.api_key = s.ai_api_key
        self.model = s.ai_model
        self.embed_model = s.ai_embed_model
        self.enabled = bool(s.ai_enabled and self.base_url)

    def _headers(self) -> dict:
        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        return headers

    def _require(self) -> None:
        if not self.enabled:
            raise RuntimeError("AI вимкнено (AI_ENABLED=false або не задано AI_BASE_URL)")

    def embed(self, texts: list[str]) -> list[list[float]]:
        self._require()
        resp = httpx.post(
            f"{self.base_url}/embeddings",
            json={"model": self.embed_model, "input": texts},
            headers=self._headers(),
            timeout=60,
        )
        resp.raise_for_status()
        return [item["embedding"] for item in resp.json()["data"]]

    def chat(self, messages: list[dict], temperature: float = 0.2) -> str:
        self._require()
        resp = httpx.post(
            f"{self.base_url}/chat/completions",
            json={"model": self.model, "messages": messages, "temperature": temperature},
            headers=self._headers(),
            timeout=120,
        )
        resp.raise_for_status()
        return resp.json()["choices"][0]["message"]["content"]


def get_provider() -> AIProvider:
    return AIProvider()


def prompt_hash(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()
