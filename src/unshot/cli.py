"""Command-line interface: ``unshot generate <image>``."""

from __future__ import annotations

import asyncio
import time
from pathlib import Path
from typing import Optional

import typer

from . import __version__
from .config import ConfigError, Settings, load_settings
from .engine import describe_error, plan_scenes, prepare_image, start_scene_tasks
from .schemas import ESCALA_LABELS

app = typer.Typer(
    help="unshot — turn a phone photo of a product into commercial catalog and lifestyle shots.",
    no_args_is_help=True,
    add_completion=False,
)


def _version(value: bool) -> None:
    if value:
        typer.echo(f"unshot {__version__}")
        raise typer.Exit()


@app.callback()
def _root(
    version: bool = typer.Option(False, "--version", callback=_version, is_eager=True, help="Show version and exit."),
) -> None:
    """unshot — model-agnostic commercial product photography engine."""


@app.command()
def generate(
    image: Path = typer.Argument(..., exists=True, dir_okay=False, readable=True, help="Product photo (JPG/PNG/WEBP/HEIC supported by Pillow)."),
    out: Path = typer.Option(Path("output"), "--out", "-o", help="Output folder."),
    note: str = typer.Option("", "--note", "-n", help="Extra art direction, e.g. 'dark elegant background'."),
    size: Optional[str] = typer.Option(None, "--size", help="Overrides IMAGE_SIZE (e.g. 1024x1280)."),
    quality: Optional[str] = typer.Option(None, "--quality", help="Overrides IMAGE_QUALITY (e.g. medium, high)."),
    image_model: Optional[str] = typer.Option(None, "--image-model", help="Overrides IMAGE_MODEL."),
    prompt_model: Optional[str] = typer.Option(None, "--prompt-model", help="Overrides PROMPT_MODEL."),
    prompt_provider: Optional[str] = typer.Option(None, "--prompt-provider", help="Overrides PROMPT_PROVIDER (gemini | openai)."),
    prompts_only: bool = typer.Option(False, "--prompts-only", help="Run only step 1 and print the prompts (no image API cost)."),
    env_file: Path = typer.Option(Path(".env"), "--env-file", help="Path to the .env file."),
) -> None:
    """Generate the Catalog / Hero Shot and Lifestyle scenes for IMAGE."""
    try:
        settings = load_settings(env_file).with_overrides(
            image_size=size,
            image_quality=quality,
            image_model=image_model,
            prompt_model=prompt_model,
            prompt_provider=prompt_provider.lower() if prompt_provider else None,
        )
        if prompts_only:
            key = "gemini_api_key" if settings.prompt_provider == "gemini" else "openai_api_key"
            settings.require("prompt_model", key)
        else:
            settings.require_for_generation()
    except ConfigError as exc:
        typer.secho(f"Config error: {exc}", fg=typer.colors.RED, err=True)
        raise typer.Exit(2)

    code = asyncio.run(_run(image, out, note, settings, prompts_only))
    raise typer.Exit(code)


async def _run(image: Path, out: Path, note: str, settings: Settings, prompts_only: bool) -> int:
    t0 = time.perf_counter()
    img_png = await asyncio.to_thread(prepare_image, image.read_bytes())

    typer.echo(f"⏳ Step 1/2 · {settings.prompt_provider}:{settings.prompt_model} analysing {image.name}…")
    try:
        plan = await plan_scenes(img_png, settings, note)
    except Exception as exc:
        typer.secho(f"❌ Prompt step failed: {describe_error(exc)}", fg=typer.colors.RED, err=True)
        return 1

    typer.echo(f"   scale: {ESCALA_LABELS[plan.escala]}  ({time.perf_counter() - t0:.1f}s)")
    if plan.aviso_etiqueta:
        typer.secho(f"⚠️  {plan.aviso_etiqueta}", fg=typer.colors.YELLOW)

    out.mkdir(parents=True, exist_ok=True)
    plan_path = out / f"{image.stem}-plan.json"
    plan_path.write_text(plan.model_dump_json(indent=2), encoding="utf-8")

    if prompts_only:
        for escena in plan.escenas:
            typer.secho(f"\n=== {escena.nombre} ===", bold=True)
            typer.echo(escena.prompt_en)
        typer.echo(f"\n📝 Plan saved to {plan_path}")
        return 0

    typer.echo(f"🎨 Step 2/2 · {settings.image_model} rendering 2 scenes in parallel…")
    failures = 0
    for finished in asyncio.as_completed(start_scene_tasks(img_png, plan, settings)):
        result = await finished
        if result.ok:
            path = out / f"{image.stem}-{result.escena.tipo}.png"
            path.write_bytes(result.image)
            typer.secho(f"✅ {result.escena.nombre} → {path}  ({time.perf_counter() - t0:.1f}s)", fg=typer.colors.GREEN)
        else:
            failures += 1
            typer.secho(f"❌ {result.escena.nombre}: {describe_error(result.error)}", fg=typer.colors.RED, err=True)

    return 1 if failures else 0


if __name__ == "__main__":  # pragma: no cover
    app()
