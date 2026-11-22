"""Telegram bot (long polling): send a product photo, receive two pro shots."""

from __future__ import annotations

import argparse
import asyncio
import io
import logging
import sys

from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes, MessageHandler, filters

from .config import ConfigError, Settings, load_settings
from .engine import describe_error, plan_scenes, prepare_image, start_scene_tasks
from .schemas import ESCALA_LABELS

log = logging.getLogger("unshot.bot")

WELCOME = (
    "📸 Envíame una foto de tu producto y te devuelvo 2 fotos profesionales: "
    "Catálogo / Hero Shot y Lifestyle.\n\n"
    "Consejo: envíala como *Archivo* para que Telegram no la comprima. "
    "Puedes añadir un pie de foto con indicaciones (ej.: 'fondo oscuro elegante')."
)


def _is_allowed(settings: Settings, update: Update) -> bool:
    if not settings.telegram_allowed_users:
        return True
    user = update.effective_user
    return user is not None and user.id in settings.telegram_allowed_users


async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.effective_message.reply_text(WELCOME, parse_mode="Markdown")


async def handle_image(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    settings: Settings = context.bot_data["settings"]
    msg = update.effective_message

    if not _is_allowed(settings, update):
        uid = update.effective_user.id if update.effective_user else "?"
        await msg.reply_text(f"⛔ No tienes acceso a este bot. Tu ID de Telegram es {uid}.")
        return

    if msg.document and (msg.document.mime_type or "").startswith("image/"):
        tg_file = await msg.document.get_file()
    elif msg.photo:
        tg_file = await msg.photo[-1].get_file()
    else:
        return

    status = await msg.reply_text("⏳ Analizando producto, escala y etiqueta…")
    try:
        raw = bytes(await tg_file.download_as_bytearray())
        img_png = await asyncio.to_thread(prepare_image, raw)
        plan = await plan_scenes(img_png, settings, (msg.caption or "").strip())
    except Exception as exc:
        log.exception("Prompt step failed")
        await status.edit_text(f"❌ No he podido analizar la foto: {describe_error(exc)}")
        return

    aviso = f"\n⚠️ {plan.aviso_etiqueta}" if plan.aviso_etiqueta else ""
    await status.edit_text(f"🎨 Escala: {ESCALA_LABELS[plan.escala]}. Generando 2 escenas en paralelo…{aviso}")

    failures = 0
    for finished in asyncio.as_completed(start_scene_tasks(img_png, plan, settings)):
        result = await finished
        try:
            if result.ok:
                buf = io.BytesIO(result.image)
                buf.name = f"unshot-{result.escena.tipo}.png"
                # Sent as document: lossless PNG, Telegram still shows a preview.
                await msg.reply_document(document=buf, caption=f"✅ {result.escena.nombre}")
            else:
                failures += 1
                await msg.reply_text(f"❌ {result.escena.nombre}: {describe_error(result.error)}")
        except Exception:
            failures += 1
            log.exception("Could not deliver scene %r", result.escena.nombre)

    final = "✅ Listo." if not failures else f"⚠️ Terminado con {failures} escena(s) fallida(s)."
    await status.edit_text(final + aviso)


async def on_error(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
    log.error("Unhandled error", exc_info=context.error)


def build_application(settings: Settings) -> Application:
    app = (
        Application.builder()
        .token(settings.telegram_bot_token)
        .concurrent_updates(True)  # several customers can be served at once
        .build()
    )
    app.bot_data["settings"] = settings
    app.add_handler(CommandHandler(["start", "help"], cmd_start))
    app.add_handler(MessageHandler(filters.PHOTO | filters.Document.IMAGE, handle_image))
    app.add_error_handler(on_error)
    return app


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(
        prog="unshot-bot",
        description="Run the unshot Telegram bot (long polling). Configuration is read from .env.",
    )
    parser.add_argument("--env-file", default=".env", help="Path to the .env file (default: .env)")
    parser.add_argument("--log-level", default="INFO", help="Logging level (default: INFO)")
    args = parser.parse_args(argv)

    logging.basicConfig(level=args.log_level.upper(), format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    logging.getLogger("httpx").setLevel(logging.WARNING)

    try:
        settings = load_settings(args.env_file)
        settings.require("telegram_bot_token")
        settings.require_for_generation()
    except ConfigError as exc:
        print(f"Config error: {exc}", file=sys.stderr)
        raise SystemExit(2) from None

    log.info(
        "unshot bot running · prompts=%s:%s · images=%s",
        settings.prompt_provider,
        settings.prompt_model,
        settings.image_model,
    )
    build_application(settings).run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":  # pragma: no cover
    main()
