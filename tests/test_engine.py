import asyncio
import io

import pytest
from PIL import Image

from unshot import engine


def _img_bytes(size, mode="RGB", fmt="JPEG", color=(200, 100, 50)):
    buf = io.BytesIO()
    Image.new(mode, size, color).save(buf, format=fmt)
    return buf.getvalue()


# ---------- preprocessing ----------
def test_large_image_is_downscaled_to_max_side_keeping_ratio():
    out = Image.open(io.BytesIO(engine.prepare_image(_img_bytes((4000, 3000)))))
    assert out.format == "PNG"
    assert out.mode == "RGB"
    assert out.size == (1800, 1350)


def test_small_image_is_not_upscaled():
    out = Image.open(io.BytesIO(engine.prepare_image(_img_bytes((640, 800)))))
    assert out.size == (640, 800)


def test_transparency_is_flattened_on_white():
    raw = _img_bytes((10, 10), mode="RGBA", fmt="PNG", color=(0, 0, 0, 0))
    out = Image.open(io.BytesIO(engine.prepare_image(raw)))
    assert out.mode == "RGB"
    assert out.getpixel((5, 5)) == (255, 255, 255)


def test_custom_max_side():
    out = Image.open(io.BytesIO(engine.prepare_image(_img_bytes((1000, 2000)), max_side=500)))
    assert max(out.size) == 500


# ---------- prompts ----------
def test_system_prompt_is_loaded_from_package():
    text = engine.load_prompt()
    assert "gran_formato" in text and "aviso_etiqueta" in text


def test_request_text_includes_note():
    assert "dark background" in engine.build_request_text("  dark background ")
    assert "Additional" not in engine.build_request_text("")


# ---------- retries ----------
class FakeAPIError(Exception):
    def __init__(self, code, message="error"):
        super().__init__(message)
        self.code = code


def test_retries_transient_503_then_succeeds():
    calls, sleeps = [], []

    async def flaky():
        calls.append(1)
        if len(calls) < 3:
            raise FakeAPIError(503, "UNAVAILABLE")
        return "ok"

    async def fake_sleep(d):
        sleeps.append(d)

    assert asyncio.run(engine.with_retries(flaky, attempts=3, base_delay=1, sleep=fake_sleep)) == "ok"
    assert len(calls) == 3
    assert sleeps == [1, 2]


@pytest.mark.parametrize(
    "exc",
    [
        FakeAPIError(400, "bad request"),
        FakeAPIError(429, "Quota exceeded ... limit: 0, model: x"),
        FakeAPIError("insufficient_quota", "You have no credits remaining"),
    ],
)
def test_does_not_retry_permanent_errors(exc):
    calls = []

    async def failing():
        calls.append(1)
        raise exc

    async def no_sleep(_):
        pass

    with pytest.raises(FakeAPIError):
        asyncio.run(engine.with_retries(failing, attempts=3, sleep=no_sleep))
    assert len(calls) == 1


def test_gives_up_after_max_attempts():
    calls = []

    async def always_503():
        calls.append(1)
        raise FakeAPIError(503)

    async def no_sleep(_):
        pass

    with pytest.raises(FakeAPIError):
        asyncio.run(engine.with_retries(always_503, attempts=2, sleep=no_sleep))
    assert len(calls) == 2


# ---------- provider dispatch (mocked, no network) ----------
@pytest.mark.parametrize("provider", ["gemini", "openai"])
def test_plan_scenes_dispatches_to_configured_provider(monkeypatch, settings, plan, provider):
    seen = {}

    async def fake(img, s, note):
        seen.update(provider=s.prompt_provider, note=note, img=img)
        return plan

    monkeypatch.setitem(engine.PROMPT_PROVIDERS, provider, fake)
    s = settings.with_overrides(prompt_provider=provider)
    result = asyncio.run(engine.plan_scenes(b"png", s, "note"))
    assert result is plan
    assert seen == {"provider": provider, "note": "note", "img": b"png"}


# ---------- parallel scenes ----------
def test_scenes_run_in_parallel_and_failures_are_isolated(settings, plan):
    started = []

    async def fake_render(img, escena, s):
        started.append(escena.tipo)
        await asyncio.sleep(0.05 if escena.tipo == "catalogo" else 0.01)
        if escena.tipo == "catalogo":
            raise RuntimeError("boom")
        return b"image-bytes"

    async def run():
        tasks = engine.start_scene_tasks(b"png", plan, settings, renderer=fake_render)
        return [await t for t in asyncio.as_completed(tasks)]

    results = asyncio.run(run())
    assert sorted(started) == ["catalogo", "lifestyle"]
    # lifestyle finishes first and is delivered even though catalog fails
    assert results[0].escena.tipo == "lifestyle" and results[0].ok
    assert results[1].escena.tipo == "catalogo" and not results[1].ok
    assert isinstance(results[1].error, RuntimeError)


def test_describe_error_is_friendly_and_bounded():
    assert "no credits" in engine.describe_error(Exception("insufficient_quota"))
    assert len(engine.describe_error(Exception("x" * 1000), limit=50)) == 50
