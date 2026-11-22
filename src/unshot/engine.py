"""Provider-agnostic engine.

Pipeline:
    raw photo ──► prepare_image()          (Pillow: RGB PNG, long side ≤ 1800 px)
              ──► plan_scenes()            (step 1: Gemini or OpenAI → PlanFotografico JSON)
              ──► start_scene_tasks()      (step 2: 2 parallel OpenAI image edits)

Interfaces (CLI, Telegram bot, future WhatsApp) only orchestrate these calls.
"""

from __future__ import annotations

import asyncio
import base64
import io
import logging
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from functools import lru_cache
from importlib import resources
from pathlib import Path
from typing import TypeVar

from PIL import Image, ImageOps

from .config import Settings
from .schemas import EscenaPrompt, PlanFotografico

log = logging.getLogger(__name__)

MAX_SIDE = 1800
RETRYABLE_STATUS = {408, 429, 500, 502, 503, 504}
# Errors that will never succeed on retry (no credits / zero quota tier).
NON_RETRYABLE_MARKERS = ("insufficient_quota", "no credits", "limit: 0")

T = TypeVar("T")


# --------------------------------------------------------------------------- #
# Image preprocessing
# --------------------------------------------------------------------------- #
def prepare_image(raw: bytes, max_side: int = MAX_SIDE) -> bytes:
    """Normalise any input image to an RGB PNG whose long side is ≤ ``max_side``.

    - honours EXIF orientation (phone photos),
    - flattens transparency onto white instead of black,
    - never upscales.
    """
    with Image.open(io.BytesIO(raw)) as src:
        img = ImageOps.exif_transpose(src)
        if img.mode in ("RGBA", "LA") or (img.mode == "P" and "transparency" in img.info):
            rgba = img.convert("RGBA")
            background = Image.new("RGB", rgba.size, (255, 255, 255))
            background.paste(rgba, mask=rgba.getchannel("A"))
            img = background
        else:
            img = img.convert("RGB")
        if max(img.size) > max_side:
            img.thumbnail((max_side, max_side), Image.Resampling.LANCZOS)
        buf = io.BytesIO()
        img.save(buf, format="PNG", optimize=True)
        return buf.getvalue()


# --------------------------------------------------------------------------- #
# Prompts
# --------------------------------------------------------------------------- #
_REPO_PROMPTS = Path(__file__).resolve().parents[2] / "prompts"


@lru_cache(maxsize=None)
def load_prompt(name: str = "api-system.md") -> str:
    """Load a prompt from the single source of truth (repo ``prompts/`` folder).

    Installed wheels ship that folder as the ``unshot.prompts`` package; source
    checkouts and editable installs read it straight from the repo.
    """
    try:
        return resources.files("unshot.prompts").joinpath(name).read_text(encoding="utf-8")
    except (ModuleNotFoundError, FileNotFoundError):
        return (_REPO_PROMPTS / name).read_text(encoding="utf-8")


def build_request_text(note: str = "") -> str:
    text = "Analyse this product photo, classify its scale and write the 2 scenes."
    note = (note or "").strip()
    if note:
        text += f" Additional instruction from the user: {note}"
    return text


# --------------------------------------------------------------------------- #
# Retries
# --------------------------------------------------------------------------- #
def _status_of(exc: BaseException) -> int | None:
    for attr in ("status_code", "code"):
        value = getattr(exc, attr, None)
        if isinstance(value, int):
            return value
    return None


def is_retryable(exc: BaseException) -> bool:
    text = f"{getattr(exc, 'code', '')} {exc}".lower()
    if any(marker in text for marker in NON_RETRYABLE_MARKERS):
        return False
    if _status_of(exc) in RETRYABLE_STATUS:
        return True
    name = type(exc).__name__
    return isinstance(exc, (asyncio.TimeoutError, ConnectionError)) or name in {
        "APIConnectionError",
        "APITimeoutError",
    }


async def with_retries(
    factory: Callable[[], Awaitable[T]],
    *,
    attempts: int = 3,
    base_delay: float = 2.0,
    sleep: Callable[[float], Awaitable[object]] = asyncio.sleep,
) -> T:
    """Run ``factory()`` retrying transient failures (503 / rate limits) with backoff."""
    for attempt in range(1, attempts + 1):
        try:
            return await factory()
        except Exception as exc:
            if attempt == attempts or not is_retryable(exc):
                raise
            delay = base_delay * 2 ** (attempt - 1)
            log.warning("Transient error (%s); retry %d/%d in %.1fs", exc, attempt, attempts - 1, delay)
            await sleep(delay)
    raise AssertionError("unreachable")


# --------------------------------------------------------------------------- #
# Step 1 — prompt providers
# --------------------------------------------------------------------------- #
async def plan_with_gemini(img_png: bytes, settings: Settings, note: str = "") -> PlanFotografico:
    from google import genai
    from google.genai import types

    client = genai.Client(api_key=settings.gemini_api_key)
    config: dict = {
        "system_instruction": load_prompt(),
        "response_mime_type": "application/json",
        "response_schema": PlanFotografico,
    }
    if settings.prompt_thinking:
        level = settings.prompt_thinking
        config["thinking_config"] = (
            types.ThinkingConfig(thinking_budget=int(level))
            if level.lstrip("-").isdigit()
            else types.ThinkingConfig(thinking_level=level.upper())
        )

    response = await client.aio.models.generate_content(
        model=settings.prompt_model,
        contents=[types.Part.from_bytes(data=img_png, mime_type="image/png"), build_request_text(note)],
        config=types.GenerateContentConfig(**config),
    )
    return PlanFotografico.model_validate_json(response.text)


async def plan_with_openai(img_png: bytes, settings: Settings, note: str = "") -> PlanFotografico:
    from openai import AsyncOpenAI

    data_url = "data:image/png;base64," + base64.b64encode(img_png).decode()
    kwargs: dict = {}
    if settings.prompt_thinking:
        kwargs["reasoning"] = {"effort": settings.prompt_thinking.lower()}

    async with AsyncOpenAI(api_key=settings.openai_api_key) as client:
        response = await client.responses.parse(
            model=settings.prompt_model,
            instructions=load_prompt(),
            input=[
                {
                    "role": "user",
                    "content": [
                        {"type": "input_text", "text": build_request_text(note)},
                        {"type": "input_image", "image_url": data_url},
                    ],
                }
            ],
            text_format=PlanFotografico,
            **kwargs,
        )
    if response.output_parsed is None:
        raise RuntimeError("The prompt model returned no structured output")
    return PlanFotografico.model_validate(response.output_parsed.model_dump())


PROMPT_PROVIDERS: dict[str, Callable[[bytes, Settings, str], Awaitable[PlanFotografico]]] = {
    "gemini": plan_with_gemini,
    "openai": plan_with_openai,
}


async def plan_scenes(img_png: bytes, settings: Settings, note: str = "") -> PlanFotografico:
    """Step 1: analyse the product and return the 2-scene plan (with retries)."""
    provider = PROMPT_PROVIDERS[settings.prompt_provider]
    return await with_retries(lambda: provider(img_png, settings, note))


# --------------------------------------------------------------------------- #
# Step 2 — image generation
# --------------------------------------------------------------------------- #
async def render_scene(img_png: bytes, escena: EscenaPrompt, settings: Settings) -> bytes:
    """Edit the original photo into one scene via the OpenAI Images Edit API."""
    from openai import AsyncOpenAI

    optional = {
        "size": settings.image_size,
        "quality": settings.image_quality,
        "input_fidelity": settings.image_input_fidelity,
    }
    kwargs = {k: v for k, v in optional.items() if v}

    async with AsyncOpenAI(api_key=settings.openai_api_key) as client:

        async def call():
            image = io.BytesIO(img_png)  # fresh buffer on every retry
            image.name = "product.png"
            return await client.images.edit(
                model=settings.image_model, image=image, prompt=escena.prompt_en, **kwargs
            )

        result = await with_retries(call)

    b64 = result.data[0].b64_json if result.data else None
    if not b64:
        raise RuntimeError("The image model returned no image data")
    return base64.b64decode(b64)


@dataclass
class SceneResult:
    escena: EscenaPrompt
    image: bytes | None = None
    error: BaseException | None = None

    @property
    def ok(self) -> bool:
        return self.image is not None


Renderer = Callable[[bytes, EscenaPrompt, Settings], Awaitable[bytes]]


def start_scene_tasks(
    img_png: bytes,
    plan: PlanFotografico,
    settings: Settings,
    renderer: Renderer | None = None,
) -> list[asyncio.Task[SceneResult]]:
    """Step 2: launch one task per scene in parallel.

    Each task resolves to a SceneResult and never raises, so a failure in one
    scene does not cancel or hide the other. Consume with ``asyncio.as_completed``
    to deliver each image the moment it is ready.
    """
    render = renderer or render_scene

    async def safe(escena: EscenaPrompt) -> SceneResult:
        try:
            return SceneResult(escena, image=await render(img_png, escena, settings))
        except Exception as exc:
            log.exception("Scene %r failed", escena.nombre)
            return SceneResult(escena, error=exc)

    return [asyncio.create_task(safe(e)) for e in plan.escenas]


def describe_error(exc: BaseException, limit: int = 300) -> str:
    """Short, user-facing description of an exception."""
    text = str(exc).lower()
    if "insufficient_quota" in text or "no credits" in text:
        return "The image/prompt provider account has no credits left."
    if "limit: 0" in text:
        return "This model is not available on your current API tier (quota 0)."
    message = f"{type(exc).__name__}: {exc}"
    return message if len(message) <= limit else message[: limit - 1] + "…"
