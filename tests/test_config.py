from pathlib import Path

import pytest

from unshot.config import ConfigError, Settings, load_settings

ROOT = Path(__file__).resolve().parents[1]


def test_loads_any_model_name_untouched():
    s = load_settings(
        env_file=None,
        environ={
            "PROMPT_PROVIDER": "OpenAI",
            "PROMPT_MODEL": "some-future-model-v9",
            "IMAGE_MODEL": "totally-made-up-image-model",
            "IMAGE_SIZE": " 1024x1280 ",
            "PROMPT_THINKING": "",
        },
    )
    assert s.prompt_provider == "openai"
    assert s.prompt_model == "some-future-model-v9"
    assert s.image_model == "totally-made-up-image-model"
    assert s.image_size == "1024x1280"
    assert s.prompt_thinking is None  # empty strings become None


def test_no_hardcoded_model_defaults():
    s = load_settings(env_file=None, environ={})
    assert s.prompt_provider == "gemini"
    assert s.prompt_model is None
    assert s.image_model is None
    assert s.image_quality is None


def test_env_file_is_overridden_by_environment(tmp_path):
    env = tmp_path / ".env"
    env.write_text("PROMPT_MODEL=from-file\nIMAGE_MODEL=img-from-file\n")
    s = load_settings(env, environ={"PROMPT_MODEL": "from-env"})
    assert s.prompt_model == "from-env"
    assert s.image_model == "img-from-file"


def test_env_example_parses_with_inline_comments():
    s = load_settings(ROOT / ".env.example", environ={})
    assert s.prompt_provider == "gemini"
    assert s.prompt_model is None
    assert s.image_size == "1024x1280"
    assert s.telegram_allowed_users == frozenset()


def test_invalid_provider_rejected():
    with pytest.raises(ConfigError, match="PROMPT_PROVIDER"):
        load_settings(env_file=None, environ={"PROMPT_PROVIDER": "acme"})


def test_cli_overrides_skip_empty_values(settings):
    s = settings.with_overrides(image_size="1536x1024", image_quality=None, prompt_model="")
    assert s.image_size == "1536x1024"
    assert s.image_quality is None
    assert s.prompt_model == settings.prompt_model


def test_require_lists_all_missing():
    with pytest.raises(ConfigError) as exc:
        Settings().require_for_generation()
    for name in ("PROMPT_MODEL", "IMAGE_MODEL", "GEMINI_API_KEY", "OPENAI_API_KEY"):
        assert name in str(exc.value)


def test_allowed_users_parsing():
    s = load_settings(env_file=None, environ={"TELEGRAM_ALLOWED_USERS": "123, 456"})
    assert s.telegram_allowed_users == frozenset({123, 456})
    with pytest.raises(ConfigError):
        load_settings(env_file=None, environ={"TELEGRAM_ALLOWED_USERS": "abc"})
