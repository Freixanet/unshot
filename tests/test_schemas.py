import pytest
from pydantic import ValidationError

from unshot.schemas import PlanFotografico


def _scene(tipo):
    return {"tipo": tipo, "nombre": tipo.title(), "prompt_en": f"{tipo} prompt"}


def test_valid_plan_puts_catalog_first():
    plan = PlanFotografico.model_validate(
        {"escala": "gran_formato", "aviso_etiqueta": "", "escenas": [_scene("lifestyle"), _scene("catalogo")]}
    )
    assert [e.tipo for e in plan.escenas] == ["catalogo", "lifestyle"]


def test_valid_plan_from_json():
    raw = (
        '{"escala":"mediana","aviso_etiqueta":"El párrafo inferior es borroso.",'
        '"escenas":[{"tipo":"catalogo","nombre":"Catálogo / Hero Shot","prompt_en":"a"},'
        '{"tipo":"lifestyle","nombre":"Lifestyle","prompt_en":"b"}]}'
    )
    plan = PlanFotografico.model_validate_json(raw)
    assert plan.aviso_etiqueta.startswith("El párrafo")


@pytest.mark.parametrize("n", [1, 3])
def test_requires_exactly_two_scenes(n):
    scenes = [_scene("catalogo"), _scene("lifestyle"), _scene("catalogo")][:n]
    with pytest.raises(ValidationError):
        PlanFotografico.model_validate({"escala": "pequena", "aviso_etiqueta": "", "escenas": scenes})


def test_requires_one_catalog_and_one_lifestyle():
    with pytest.raises(ValidationError, match="exactly one"):
        PlanFotografico.model_validate(
            {"escala": "pequena", "aviso_etiqueta": "", "escenas": [_scene("catalogo"), _scene("catalogo")]}
        )


def test_rejects_unknown_scale_and_empty_prompt():
    with pytest.raises(ValidationError):
        PlanFotografico.model_validate(
            {"escala": "huge", "aviso_etiqueta": "", "escenas": [_scene("catalogo"), _scene("lifestyle")]}
        )
    bad = _scene("lifestyle") | {"prompt_en": ""}
    with pytest.raises(ValidationError):
        PlanFotografico.model_validate(
            {"escala": "pequena", "aviso_etiqueta": "", "escenas": [_scene("catalogo"), bad]}
        )
