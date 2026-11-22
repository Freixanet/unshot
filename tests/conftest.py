import pytest

from unshot.config import Settings
from unshot.schemas import EscenaPrompt, PlanFotografico


@pytest.fixture
def settings() -> Settings:
    return Settings(
        prompt_provider="gemini",
        prompt_model="any-vision-model",
        image_model="any-image-model",
        gemini_api_key="test-gemini",
        openai_api_key="test-openai",
    )


@pytest.fixture
def plan() -> PlanFotografico:
    return PlanFotografico(
        escala="pequena",
        aviso_etiqueta="",
        escenas=[
            EscenaPrompt(tipo="catalogo", nombre="Catálogo / Hero Shot", prompt_en="hero prompt"),
            EscenaPrompt(tipo="lifestyle", nombre="Lifestyle", prompt_en="lifestyle prompt"),
        ],
    )
