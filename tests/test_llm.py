"""Tests for LLM provider abstraction."""
import json
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


def test_openai_generate_mocked(monkeypatch: pytest.MonkeyPatch):
    """OpenAI provider correctly parses the chat completion response."""
    import httpx
    from kb.data.llm import OpenAILLMProvider

    provider = OpenAILLMProvider(api_key="sk-test")

    class MockResp:
        def raise_for_status(self):
            pass
        def json(self):
            return {
                "choices": [{"message": {"content": "Mocked reply"}}],
                "usage": {"total_tokens": 42},
            }

    monkeypatch.setattr(
        httpx.Client, "post",
        lambda self, url, headers=None, json=None, timeout=None: MockResp(),
    )
    result = provider.generate("test")
    assert result.text == "Mocked reply"
    assert result.tokens_used == 42


def test_ollama_generate_stream_mocked(monkeypatch: pytest.MonkeyPatch):
    """Ollama streaming correctly joins chunk texts from iter_lines."""
    import httpx
    from kb.data.llm import OllamaLLMProvider

    provider = OllamaLLMProvider(model="qwen2.5:7b")

    class MockStreamResp:
        def __enter__(self):
            return self
        def __exit__(self, *args):
            pass
        def raise_for_status(self):
            pass
        def iter_lines(self):
            yield '{"message": {"content": "Hello"}, "done": false}'
            yield '{"message": {"content": " World"}, "done": false}'
            yield '{"message": {"content": ""}, "done": true}'

    class MockClient:
        def __init__(self, timeout=None):
            pass
        def __enter__(self):
            return self
        def __exit__(self, *args):
            pass
        def stream(self, method, url, headers=None, json=None):
            return MockStreamResp()

    monkeypatch.setattr(httpx, "Client", MockClient)
    chunks = list(provider.generate_stream("Hello"))
    joined = "".join(r.text for r in chunks)
    assert joined == "Hello World"


def test_anthropic_generate_mocked(monkeypatch: pytest.MonkeyPatch):
    """Anthropic provider parses response and sums input+output tokens."""
    import httpx
    from kb.data.llm import AnthropicLLMProvider

    provider = AnthropicLLMProvider(api_key="sk-ant-test")

    class MockResp:
        def raise_for_status(self):
            pass
        def json(self):
            return {
                "content": [{"type": "text", "text": "Claude response"}],
                "usage": {"input_tokens": 10, "output_tokens": 20},
            }

    monkeypatch.setattr(
        httpx.Client, "post",
        lambda self, url, headers=None, json=None, timeout=None: MockResp(),
    )
    result = provider.generate("Hello", system_prompt="Be helpful")
    assert result.text == "Claude response"
    assert result.tokens_used == 30


def test_anthropic_generate_stream_mocked(monkeypatch: pytest.MonkeyPatch):
    """Anthropic streaming parses SSE content_block_delta lines."""
    import httpx
    from kb.data.llm import AnthropicLLMProvider

    provider = AnthropicLLMProvider(api_key="sk-ant-test")

    class MockStreamResp:
        def __enter__(self):
            return self
        def __exit__(self, *args):
            pass
        def raise_for_status(self):
            pass
        def iter_lines(self):
            yield 'data: {"type":"content_block_delta","delta":{"text":"Part1"}}'
            yield 'data: {"type":"content_block_delta","delta":{"text":"Part2"}}'

    class MockClient:
        def __init__(self, timeout=None):
            pass
        def __enter__(self):
            return self
        def __exit__(self, *args):
            pass
        def stream(self, method, url, headers=None, json=None):
            return MockStreamResp()

    monkeypatch.setattr(httpx, "Client", MockClient)
    chunks = list(provider.generate_stream("Hello"))
    assert len(chunks) == 2
    assert chunks[0].text == "Part1"
    assert chunks[1].text == "Part2"


def test_openai_generate_timeout(monkeypatch: pytest.MonkeyPatch):
    """OpenAI generate propagates httpx.ReadTimeout."""
    import httpx
    from kb.data.llm import OpenAILLMProvider

    provider = OpenAILLMProvider(api_key="sk-test")

    monkeypatch.setattr(
        httpx.Client, "post",
        lambda self, url, headers=None, json=None, timeout=None: (
            _ for _ in ()
        ).throw(httpx.ReadTimeout("timeout")),
    )

    with pytest.raises(httpx.ReadTimeout):
        provider.generate("test")


def test_openai_generate_http_error(monkeypatch: pytest.MonkeyPatch):
    """OpenAI generate propagates httpx.HTTPStatusError."""
    import httpx
    from kb.data.llm import OpenAILLMProvider

    provider = OpenAILLMProvider(api_key="sk-test")

    class MockErrorResp:
        def json(self):
            return {"error": {"message": "Unauthorized"}}
        def raise_for_status(self):
            raise httpx.HTTPStatusError("401", request=None, response=None)

    monkeypatch.setattr(
        httpx.Client, "post",
        lambda self, url, headers=None, json=None, timeout=None: MockErrorResp(),
    )

    with pytest.raises(httpx.HTTPStatusError):
        provider.generate("test")
