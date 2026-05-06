"""LLM provider abstraction with Ollama, OpenAI, and Anthropic backends."""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass

import httpx

from kb.core.config import LLMConfig


@dataclass(frozen=True)
class LLMResponse:
    text: str
    tokens_used: int
    model: str


class LLMProvider(ABC):
    """Abstract interface for LLM text generation."""

    @abstractmethod
    def generate(self, prompt: str, *, system_prompt: str = "") -> LLMResponse: ...

    @abstractmethod
    def generate_stream(self, prompt: str, *, system_prompt: str = ""):
        """Yield LLMResponse chunks as they arrive."""
        ...

    @property
    @abstractmethod
    def model_name(self) -> str: ...


class OllamaLLMProvider(LLMProvider):
    """Ollama local LLM backend (e.g., qwen2.5, llama3)."""

    def __init__(self, model: str = "qwen2.5:7b", base_url: str = "http://localhost:11434") -> None:
        self._model = model
        self._base_url = base_url

    def generate(self, prompt: str, *, system_prompt: str = "") -> LLMResponse:
        messages: list[dict] = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        with httpx.Client(timeout=120) as client:
            resp = client.post(
                f"{self._base_url}/api/chat",
                json={"model": self._model, "messages": messages, "stream": False},
            )
            resp.raise_for_status()
            data = resp.json()

        return LLMResponse(
            text=data["message"]["content"],
            tokens_used=data.get("eval_count", 0),
            model=self._model,
        )

    def generate_stream(self, prompt: str, *, system_prompt: str = ""):
        import json as _json

        messages: list[dict] = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        with httpx.Client(timeout=120) as client:
            with client.stream(
                "POST",
                f"{self._base_url}/api/chat",
                json={"model": self._model, "messages": messages, "stream": True},
            ) as resp:
                resp.raise_for_status()
                for line in resp.iter_lines():
                    if not line:
                        continue
                    data = _json.loads(line)
                    if data.get("done"):
                        break
                    yield LLMResponse(
                        text=data["message"].get("content", ""),
                        tokens_used=0,
                        model=self._model,
                    )

    @property
    def model_name(self) -> str:
        return self._model


class OpenAILLMProvider(LLMProvider):
    """OpenAI Chat Completions API backend."""

    def __init__(self, api_key: str, model: str = "gpt-4o-mini") -> None:
        self._api_key = api_key
        self._model = model

    def generate(self, prompt: str, *, system_prompt: str = "") -> LLMResponse:
        messages: list[dict] = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        with httpx.Client(timeout=60) as client:
            resp = client.post(
                "https://api.openai.com/v1/chat/completions",
                headers={
                    "Authorization": f"Bearer {self._api_key}",
                    "Content-Type": "application/json",
                },
                json={"model": self._model, "messages": messages},
            )
            resp.raise_for_status()
            data = resp.json()

        choice = data["choices"][0]
        return LLMResponse(
            text=choice["message"]["content"],
            tokens_used=data.get("usage", {}).get("total_tokens", 0),
            model=self._model,
        )

    def generate_stream(self, prompt: str, *, system_prompt: str = ""):
        import json as _json

        messages: list[dict] = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        with httpx.Client(timeout=60) as client:
            with client.stream(
                "POST",
                "https://api.openai.com/v1/chat/completions",
                headers={
                    "Authorization": f"Bearer {self._api_key}",
                    "Content-Type": "application/json",
                },
                json={"model": self._model, "messages": messages, "stream": True},
            ) as resp:
                resp.raise_for_status()
                for line in resp.iter_lines():
                    if not line or line.startswith(": "):
                        continue
                    if line == "data: [DONE]":
                        break
                    if line.startswith("data: "):
                        data = _json.loads(line[6:])
                        delta = data["choices"][0].get("delta", {})
                        if "content" in delta:
                            yield LLMResponse(
                                text=delta["content"],
                                tokens_used=0,
                                model=self._model,
                            )

    @property
    def model_name(self) -> str:
        return self._model


class AnthropicLLMProvider(LLMProvider):
    """Anthropic Messages API backend."""

    def __init__(self, api_key: str, model: str = "claude-haiku-4-5-20251001") -> None:
        self._api_key = api_key
        self._model = model

    def generate(self, prompt: str, *, system_prompt: str = "") -> LLMResponse:
        body: dict = {
            "model": self._model,
            "max_tokens": 1024,
            "messages": [{"role": "user", "content": prompt}],
        }
        if system_prompt:
            body["system"] = system_prompt

        with httpx.Client(timeout=60) as client:
            resp = client.post(
                "https://api.anthropic.com/v1/messages",
                headers={
                    "x-api-key": self._api_key,
                    "anthropic-version": "2023-06-01",
                    "Content-Type": "application/json",
                },
                json=body,
            )
            resp.raise_for_status()
            data = resp.json()

        text = "".join(b["text"] for b in data["content"] if b["type"] == "text")
        return LLMResponse(
            text=text,
            tokens_used=data.get("usage", {}).get("input_tokens", 0)
                      + data.get("usage", {}).get("output_tokens", 0),
            model=self._model,
        )

    def generate_stream(self, prompt: str, *, system_prompt: str = ""):
        import json as _json

        body: dict = {
            "model": self._model,
            "max_tokens": 1024,
            "messages": [{"role": "user", "content": prompt}],
            "stream": True,
        }
        if system_prompt:
            body["system"] = system_prompt

        with httpx.Client(timeout=60) as client:
            with client.stream(
                "POST",
                "https://api.anthropic.com/v1/messages",
                headers={
                    "x-api-key": self._api_key,
                    "anthropic-version": "2023-06-01",
                    "Content-Type": "application/json",
                },
                json=body,
            ) as resp:
                resp.raise_for_status()
                for line in resp.iter_lines():
                    if not line:
                        continue
                    if ": " in line:
                        event_type, data_str = line.split(": ", 1)
                        if event_type == "data":
                            data = _json.loads(data_str)
                            if data["type"] == "content_block_delta":
                                yield LLMResponse(
                                    text=data["delta"].get("text", ""),
                                    tokens_used=0,
                                    model=self._model,
                                )

    @property
    def model_name(self) -> str:
        return self._model


def create_llm_provider(config: LLMConfig) -> LLMProvider:
    """Factory: build LLM provider from config."""
    import os as _os

    if config.provider == "ollama":
        return OllamaLLMProvider(model=config.model)

    if config.provider == "openai":
        key = _os.environ.get(config.api_key_env or "OPENAI_API_KEY", "")
        if not key:
            raise ValueError(
                f"OpenAI API key not found in env var {config.api_key_env or 'OPENAI_API_KEY'}"
            )
        return OpenAILLMProvider(api_key=key, model=config.model)

    if config.provider == "anthropic":
        key = _os.environ.get(config.api_key_env or "ANTHROPIC_API_KEY", "")
        if not key:
            raise ValueError(
                f"Anthropic API key not found in env var {config.api_key_env or 'ANTHROPIC_API_KEY'}"
            )
        return AnthropicLLMProvider(api_key=key, model=config.model)

    raise ValueError(f"Unknown LLM provider: {config.provider}")
