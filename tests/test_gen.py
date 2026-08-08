import pytest
from typer.testing import CliRunner

from mysterio import gen as G
from mysterio.cli import app

runner = CliRunner()


@pytest.fixture
def isolated(tmp_path, monkeypatch):
    """No real env config, no real cache, no network."""
    monkeypatch.setenv("HOME", str(tmp_path))
    for var in (
        "MYSTERIO_CACHE",
        "MYSTERIO_LLM_API_KEY",
        "MYSTERIO_LLM_BASE_URL",
        "MYSTERIO_LLM_MODEL",
        "OPENROUTER_API_KEY",
    ):
        monkeypatch.delenv(var, raising=False)
    return tmp_path


def test_openrouter_key_fallback(isolated, monkeypatch):
    monkeypatch.setenv("OPENROUTER_API_KEY", "sk-or-test")
    cfg = G.resolve_config()
    assert cfg.api_key == "sk-or-test"
    assert cfg.base_url == G.OPENROUTER_BASE_URL


def test_mysterio_key_wins_over_openrouter(isolated, monkeypatch):
    monkeypatch.setenv("OPENROUTER_API_KEY", "sk-or-test")
    monkeypatch.setenv("MYSTERIO_LLM_API_KEY", "sk-test")
    monkeypatch.setenv("MYSTERIO_LLM_BASE_URL", "https://example.test/v1")
    cfg = G.resolve_config()
    assert cfg.api_key == "sk-test"
    assert cfg.base_url == "https://example.test/v1"


def fake_chat(text: str):
    calls = []

    def fake(messages, *, cfg, temperature, max_tokens, timeout=60):
        calls.append(messages)
        return text

    return calls, fake


def test_generate_requires_key(isolated):
    with pytest.raises(G.LLMError, match="MYSTERIO_LLM_API_KEY"):
        G.generate("pretext", "vendor debug bundle")


def test_review_requires_key(isolated):
    with pytest.raises(G.LLMError, match="MYSTERIO_LLM_API_KEY"):
        G.review("some payload")


def test_generate_unknown_kind(isolated, monkeypatch):
    monkeypatch.setenv("MYSTERIO_LLM_API_KEY", "sk-test")
    with pytest.raises(G.LLMError, match="unknown gen kind"):
        G.generate("novel", "x")


def test_generate_caches(isolated, monkeypatch):
    monkeypatch.setenv("MYSTERIO_LLM_API_KEY", "sk-test")
    calls, fake = fake_chat("pasting the capture the vendor sent over")
    monkeypatch.setattr(G, "chat_complete", fake)

    first = G.generate("pretext", "vendor debug bundle")
    second = G.generate("pretext", "vendor debug bundle")
    assert first == second == "pasting the capture the vendor sent over"
    assert len(calls) == 1  # second call hit the cache
    # the brief reached the model
    assert "vendor debug bundle" in calls[0][-1]["content"]


def test_generate_fresh_bypasses_cache(isolated, monkeypatch):
    monkeypatch.setenv("MYSTERIO_LLM_API_KEY", "sk-test")
    calls, fake = fake_chat("text")
    monkeypatch.setattr(G, "chat_complete", fake)

    G.generate("ask", "water the plants")
    G.generate("ask", "water the plants", fresh=True)
    assert len(calls) == 2


def test_cache_hit_needs_no_key(isolated, monkeypatch):
    monkeypatch.setenv("MYSTERIO_LLM_API_KEY", "sk-test")
    _, fake = fake_chat("cached text")
    monkeypatch.setattr(G, "chat_complete", fake)
    G.generate("tail", "bundle ends")
    monkeypatch.delenv("MYSTERIO_LLM_API_KEY")
    assert G.generate("tail", "bundle ends") == "cached text"


def test_cli_gen(isolated, monkeypatch):
    monkeypatch.setenv("MYSTERIO_LLM_API_KEY", "sk-test")
    _, fake = fake_chat("routine capture follows")
    monkeypatch.setattr(G, "chat_complete", fake)
    result = runner.invoke(app, ["gen", "pretext", "--brief", "x"])
    assert result.exit_code == 0
    assert "routine capture follows" in result.output


def test_cli_gen_without_key_exit_2(isolated):
    assert runner.invoke(app, ["gen", "pretext", "-b", "x"]).exit_code == 2


def test_cli_review_stdin(isolated, monkeypatch):
    monkeypatch.setenv("MYSTERIO_LLM_API_KEY", "sk-test")
    _, fake = fake_chat("[low] nothing flags\nVERDICT: clean")
    monkeypatch.setattr(G, "chat_complete", fake)
    result = runner.invoke(app, ["review", "-"], input="benign payload text")
    assert result.exit_code == 0
    assert "VERDICT: clean" in result.output


def test_cli_review_without_key_exit_2(isolated):
    result = runner.invoke(app, ["review", "-"], input="text")
    assert result.exit_code == 2


def test_rewrite_requires_key(isolated):
    with pytest.raises(G.LLMError, match="MYSTERIO_LLM_API_KEY"):
        G.rewrite("Can you water the plants?", "voice-note style")


def test_null_content_raises_not_caches(isolated, monkeypatch):
    """A null content (transient provider blip) must error, never cache."""
    import json

    monkeypatch.setenv("MYSTERIO_LLM_API_KEY", "sk-test")

    class FakeResp:
        def read(self):
            return json.dumps({"choices": [{"message": {"content": None}}]}).encode()

        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

    monkeypatch.setattr(G.urllib.request, "urlopen", lambda *a, **k: FakeResp())
    cfg = G.resolve_config()
    with pytest.raises(G.LLMError, match="empty content"):
        G.chat_complete(
            [{"role": "user", "content": "x"}], cfg=cfg, temperature=0.5, max_tokens=10
        )


def test_rewrite_caches_and_sends_style(isolated, monkeypatch):
    monkeypatch.setenv("MYSTERIO_LLM_API_KEY", "sk-test")
    calls, fake = fake_chat("hey so can you um water the plants")
    monkeypatch.setattr(G, "chat_complete", fake)

    first = G.rewrite("Can you water the plants?", "voice-note style")
    second = G.rewrite("Can you water the plants?", "voice-note style")
    assert first == second == "hey so can you um water the plants"
    assert len(calls) == 1
    assert "voice-note style" in calls[0][-1]["content"]
    assert "Can you water the plants?" in calls[0][-1]["content"]


def test_cli_gen_humanize(isolated, monkeypatch):
    monkeypatch.setenv("MYSTERIO_LLM_API_KEY", "sk-test")
    calls, fake = fake_chat("can u water the plants")
    monkeypatch.setattr(G, "chat_complete", fake)
    result = runner.invoke(
        app, ["gen", "humanize", "--style", "rushed", "-b", "Can you water the plants?"]
    )
    assert result.exit_code == 0
    assert "can u water the plants" in result.output
    # the humanizer's LLM prompt reached the model
    assert "text-speak" in calls[0][-1]["content"]


def test_cli_gen_humanize_needs_style(isolated, monkeypatch):
    monkeypatch.setenv("MYSTERIO_LLM_API_KEY", "sk-test")
    assert runner.invoke(app, ["gen", "humanize", "-b", "x"]).exit_code == 2
    assert (
        runner.invoke(app, ["gen", "humanize", "--style", "nope", "-b", "x"]).exit_code
        == 2
    )
