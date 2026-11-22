# unshot

[![CI](https://github.com/Freixanet/unshot/actions/workflows/ci.yml/badge.svg)](https://github.com/Freixanet/unshot/actions/workflows/ci.yml)
![Python](https://img.shields.io/badge/python-3.11%20%7C%203.12%20%7C%203.13-blue)
[![License: MIT](https://img.shields.io/badge/license-MIT-green)](LICENSE)

**Send a phone photo of your product. Get back studio-grade catalog and lifestyle shots — of the exact same product.**

unshot is a model-agnostic, scale-aware engine for commercial product photography. A vision model acts as the *art director* (analyses the product, classifies its scale, reads the label and writes two precise prompts); an image model acts as the *photographer* (edits the original photo into each scene). You can run it for free inside ChatGPT / Claude / Gemini, or fully automated through a CLI and a Telegram bot.

```
Phone photo ──► 1. Art director (Gemini or OpenAI vision, JSON output)
                     • scale class: tabletop · standalone · architectural
                     • conditional OCR of labels, warns about blurry small print
                     • 2 English prompts
              ──► 2. Photographer (OpenAI Images Edit, 2 calls in parallel)
                     ├─► Catalog / Hero Shot  → delivered as soon as it's ready
                     └─► Lifestyle            → delivered as soon as it's ready
```

## Before / After

| Before (phone photo) | Catalog / Hero Shot | Lifestyle |
|:---:|:---:|:---:|
| _add `assets/before.jpg`_ | _add `assets/after-catalog.jpg`_ | _add `assets/after-lifestyle.jpg`_ |

> Placeholder — see [`assets/README.md`](assets/README.md) for the expected files. Replace each cell with `![](assets/<file>)` once real examples are added.

## Why it doesn't look like AI slop

- **3-scale classifier → no "miniature" effect.** Lenses, camera height and set design change with the size of the object:

  | Scale | Examples | Hero lens | Lifestyle lens |
  |---|---|---|---|
  | Small / tabletop | cosmetics, bottles, food, jewelry | 85mm f/2.8 | 50mm f/2.2 |
  | Medium / standalone | appliances, lamps, chairs, bikes | 50mm f/4 | 35-50mm f/2.8 |
  | Large / architectural | saunas, jacuzzis, sofas, furniture | 24-35mm f/5.6-f/8 | 24-35mm f/5.6-f/8 |

  Large products are shot at 1:1 scale against real architecture, at eye height, never on small pedestals.
- **Strict product preservation.** Geometry, proportions, materials, colors, closures and logos are locked; contact shadows, light wrap, refraction, caustics and liquid levels must be physically plausible.
- **Conditional OCR.** Only when the product has text: every legible line is quoted literally with its alignment and typography is reinforced. Blurry small print is **never invented** — you get a warning instead (`aviso_etiqueta`).

## Mode 1 — Zero cost (no API keys)

All the know-how lives in [`prompts/`](prompts/), the single source of truth used by the code too:

| File | Use it in | What it does |
|---|---|---|
| [`prompts/chatgpt-gpt.md`](prompts/chatgpt-gpt.md) | ChatGPT **Custom GPT** or **Project** with image generation | Upload a photo → ChatGPT directly generates the 2 images. Prompts are never printed. |
| [`prompts/unshot-skill.md`](prompts/unshot-skill.md) | **Claude** (Skill / Project), **Gemini** (Gem), any vision LLM | Generates the 2 copy-ready prompts, and audits generated results against the original with a correction prompt. |
| [`prompts/api-system.md`](prompts/api-system.md) | The automated pipeline | Compact system prompt for structured JSON output. |

## Mode 2 — Automated (CLI + Telegram bot)

### Install

```bash
git clone https://github.com/Freixanet/unshot.git && cd unshot
python3.11 -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
cp .env.example .env   # then fill in models and keys
```

### CLI

```bash
unshot generate photo.jpg                          # → output/photo-catalogo.png, output/photo-lifestyle.png
unshot generate photo.jpg --note "dark elegant background" --quality medium
unshot generate photo.jpg --prompts-only           # step 1 only: print prompts, no image cost
unshot generate photo.jpg --prompt-model <id> --image-model <id> --size 1024x1280 --out shots/
```

Every flag overrides the matching `.env` value. The JSON plan is saved next to the images (`<name>-plan.json`).

### Telegram bot

1. Create a bot with [@BotFather](https://t.me/BotFather) (`/newbot`) and put the token in `TELEGRAM_BOT_TOKEN`.
2. Run `unshot-bot` (long polling, no server or webhook needed).
3. Send a product photo — ideally **as a file** so Telegram doesn't compress it. Add a caption for extra art direction.

The bot answers instantly, shows the detected scale and any label warning, and delivers each scene as a lossless PNG the moment it is ready. If one scene fails, the other is still delivered. Several users are served concurrently. Restrict access with `TELEGRAM_ALLOWED_USERS`.

## Configuration (`.env`)

No model names are hard-coded: whatever id you set is passed straight to the provider. The models below are **examples only** — use whatever your account has access to.

| Variable | Required | Description | Example (illustrative) |
|---|---|---|---|
| `PROMPT_PROVIDER` | no (default `gemini`) | Step-1 provider: `gemini` or `openai` | `gemini` |
| `PROMPT_MODEL` | **yes** | Vision model that writes the prompts | `gemini-4-hydrogen` |
| `PROMPT_THINKING` | no | Gemini `thinking_level` (or numeric budget) / OpenAI reasoning effort | `LOW` |
| `IMAGE_MODEL` | **yes** | OpenAI image-editing model | `gpt-image-2.6-sunburst` |
| `IMAGE_QUALITY` | no | Image quality (empty = provider default) | `high` |
| `IMAGE_SIZE` | no | Output size (empty = provider default) | `1024x1280` (4:5) |
| `IMAGE_INPUT_FIDELITY` | no | Higher fidelity to the input image, if the model supports it | `high` |
| `GEMINI_API_KEY` | if provider is `gemini` | Google AI Studio key | |
| `OPENAI_API_KEY` | **yes** | OpenAI key (image step, and prompt step if provider is `openai`) | |
| `TELEGRAM_BOT_TOKEN` | for the bot | Token from @BotFather | |
| `TELEGRAM_ALLOWED_USERS` | no | Comma-separated Telegram user ids allowed to use the bot | `123456789,987654321` |

## Project layout

```
prompts/            single source of truth (shipped in the package as unshot.prompts)
src/unshot/
  config.py         flat, model-agnostic settings from .env / environment
  schemas.py        Pydantic structured output (scale, label warning, 2 scenes)
  engine.py         preprocessing, provider dispatch + retries, parallel scene rendering
  cli.py            `unshot` command (Typer)
  bot.py            `unshot-bot` Telegram bot
tests/              unit tests with mocks — no real API calls
```

```bash
pytest                                  # offline, no API calls
ruff check src tests && ruff format --check src tests
```

## Known limitations

- **Tiny or blurry label text.** Image models can't reliably reproduce microscopic text they can't read. unshot never invents words: it asks the model to preserve the existing block and flags it in `aviso_etiqueta`. Expect to retouch dense small print (ingredients, legal text) or shoot a sharper original.
- **Input quality caps output quality.** Very dark, blurry or heavily compressed photos degrade preservation. On Telegram, send photos as files.
- **Image step is OpenAI-only for now.** The prompt step supports Gemini and OpenAI; the image step uses the OpenAI Images Edit API.
- **Latency and cost depend on your models and tier.** Free tiers can be slow or have zero quota for some models; high-quality image edits cost money per image.
- **Generated images are not guaranteed identical.** Always review shots before publishing them commercially.

## License

[MIT](LICENSE)
