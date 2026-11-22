"""Structured-output schema shared by every prompt provider."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field, model_validator

Escala = Literal["pequena", "mediana", "gran_formato"]
TipoEscena = Literal["catalogo", "lifestyle"]

ESCALA_LABELS: dict[str, str] = {
    "pequena": "pequeña / sobremesa",
    "mediana": "mediana / autónoma",
    "gran_formato": "gran formato / arquitectónica",
}


class EscenaPrompt(BaseModel):
    tipo: TipoEscena = Field(description="'catalogo' (Hero Shot) or 'lifestyle'")
    nombre: str = Field(description="Short Spanish name: 'Catálogo / Hero Shot' or 'Lifestyle'")
    prompt_en: str = Field(min_length=1, description="Full English prompt for the image-editing model")


class PlanFotografico(BaseModel):
    escala: Escala = Field(
        description="Scale class: pequena (tabletop), mediana (standalone), gran_formato (architectural)"
    )
    aviso_etiqueta: str = Field(
        description="Short Spanish warning if small text is blurry/illegible; empty string if all is sharp.",
    )
    escenas: list[EscenaPrompt] = Field(min_length=2, max_length=2)

    @model_validator(mode="after")
    def _one_of_each(self) -> PlanFotografico:
        tipos = sorted(e.tipo for e in self.escenas)
        if tipos != ["catalogo", "lifestyle"]:
            raise ValueError("escenas must contain exactly one 'catalogo' and one 'lifestyle' scene")
        # Always return catalog first for predictable ordering.
        self.escenas.sort(key=lambda e: e.tipo != "catalogo")
        return self
