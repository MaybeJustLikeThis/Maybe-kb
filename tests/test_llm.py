"""Tests for LLM provider abstraction."""
import pytest
from kb.core.config import LLMConfig


def test_llm_response_fields():
    """LLMResponse stores text, tokens, and model."""
    from kb.data.llm import LLMResponse
    r = LLMResponse(text="hello", tokens_used=5, model="test")
    assert r.text == "hello"
    assert r.tokens_used == 5
    assert r.model == "test"


def test_create_provider_ollama():
    """Factory returns OllamaLLMProvider when config says 'ollama'."""
    from kb.data.llm import create_llm_provider, OllamaLLMProvider
    config = LLMConfig(provider="ollama", model="qwen2.5:7b")
    provider = create_llm_provider(config)
    assert isinstance(provider, OllamaLLMProvider)
    assert provider.model_name == "qwen2.5:7b"


def test_create_provider_openai_requires_key(monkeypatch: pytest.MonkeyPatch):
    """OpenAI provider raises if API key not set."""
    from kb.data.llm import create_llm_provider
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    config = LLMConfig(provider="openai", model="gpt-4o-mini")
    with pytest.raises(ValueError, match="OpenAI API key"):
        create_llm_provider(config)


def test_create_provider_openai_with_key(monkeypatch: pytest.MonkeyPatch):
    """OpenAI provider created when key is in env."""
    from kb.data.llm import create_llm_provider, OpenAILLMProvider
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
    config = LLMConfig(provider="openai", model="gpt-4o-mini")
    provider = create_llm_provider(config)
    assert isinstance(provider, OpenAILLMProvider)


def test_create_provider_anthropic_requires_key(monkeypatch: pytest.MonkeyPatch):
    """Anthropic provider raises if API key not set."""
    from kb.data.llm import create_llm_provider
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    config = LLMConfig(provider="anthropic", model="claude-haiku-4-5-20251001")
    with pytest.raises(ValueError, match="Anthropic API key"):
        create_llm_provider(config)


def test_create_provider_anthropic_with_key(monkeypatch: pytest.MonkeyPatch):
    """Anthropic provider created when key is in env."""
    from kb.data.llm import create_llm_provider, AnthropicLLMProvider
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-test")
    config = LLMConfig(provider="anthropic", model="claude-haiku-4-5-20251001")
    provider = create_llm_provider(config)
    assert isinstance(provider, AnthropicLLMProvider)


def test_create_provider_unknown_raises():
    """Factory raises ValueError for unknown provider."""
    from kb.data.llm import create_llm_provider
    config = LLMConfig(provider="unknown", model="x")
    with pytest.raises(ValueError, match="Unknown LLM provider"):
        create_llm_provider(config)


def test_ollama_generate_mocked(monkeypatch: pytest.MonkeyPatch):
    """Ollama provider sends correct request body and returns LLMResponse."""
    import httpx
    from kb.data.llm import OllamaLLMProvider

    provider = OllamaLLMProvider(model="qwen2.5:7b")

    class MockResp:
        def raise_for_status(self): pass
        def json(self):
            return {"message": {"content": "你好"}, "eval_count": 3}

    monkeypatch.setattr(httpx.Client, "post", lambda self, url, json: MockResp())
    result = provider.generate("测试问题")
    assert result.text == "你好"
    assert result.tokens_used == 3
