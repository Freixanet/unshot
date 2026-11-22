---
name: unshot-product-photo
description: Turns a phone photo of a physical product into two copy-ready, scale-aware English prompts (Catalog/Hero Shot + Lifestyle) for an image-editing model, and audits generated results against the original. Use when the user uploads a product photo and wants professional e-commerce or social shots, or uploads a generated image to check it.
---

# unshot — Product photo prompt generator & result auditor

Use this skill in a chat assistant with vision (Claude, Gemini Gems, any LLM with image input). It works in two modes:

- **Mode A — Generate prompts**: the user uploads one product photo (optionally with a note such as "dark elegant background").
- **Mode B — Audit a result**: the user uploads the original photo AND an image generated from it.

Answer in the user's language. Prompts are always in English.

---

## Mode A — Generate prompts

### A1. Classify the scale (always first — prevents the miniature/toy effect)

| Scale | Typical products | Catalog / Hero lens | Lifestyle lens |
|---|---|---|---|
| **Small / tabletop** | cosmetics, bottles, jars, food packs, jewelry, gadgets | 85mm f/2.8 | 50mm f/2.2 |
| **Medium / standalone** | appliances, lamps, chairs, planters, bikes, luggage | 50mm f/4 | 35-50mm f/2.8 |
| **Large / architectural** | saunas, jacuzzis, hot tubs, sofas, beds, wardrobes, pergolas, furniture sets | 24-35mm f/5.6-f/8 | 24-35mm f/5.6-f/8 |

Large / architectural rules: real 1:1 scale against architecture (floors, walls, doors, human-sized context), camera at eye height (~1.5-1.7 m), deep focus, **no small pedestals, plinths, tabletops or studio sweeps** that shrink the object; the product stands on a real ground plane with correct perspective.

State the chosen scale in one line before the prompts.

### A2. Read the product

- Materials and finishes of every visible part, proportions, closure/hardware, brand positioning.
- **Conditional OCR**:
  - No text or logo → skip OCR and don't mention text.
  - Legible text → transcribe each line literally, in double quotes, keeping language, capitalization, accents, line breaks and alignment (left / centered / right).
  - Tiny blurry text → **never invent words**. Refer to it as "the existing small-print block, preserved exactly as in the reference" and warn the user (⚠️) that it should be checked or retouched.

### A3. Write the two prompts

Output exactly two fenced code blocks, each preceded by its title:

1. **Catálogo / Hero Shot** — clean hero shot on a surface/set suited to the scale (stone, travertine, microcement, slate or fine wood for small; seamless set or minimal interior for medium; real architectural setting for large). Directional light, max 1 supporting element that never covers the product.
2. **Lifestyle** — realistic everyday environment matching the brand (bathroom counter, bright kitchen, Mediterranean table, living room, garden, spa terrace…), max 1-2 plausible props, shallow depth of field where the lens allows.

Each prompt must contain these labelled blocks, in order:

- **FORMAT** — 4:5 vertical commercial photograph using the exact product from the reference image.
- **STRICT PRODUCT PRESERVATION** — 100% of shape, geometry, proportions, materials, colors, finishes, closure/hardware, logo placement; quoted text lines with alignment and crisp typography reinforcement; forbid altering, translating or adding text.
- **SCENE & COMPOSITION** — setting, placement, props that never block the product, the scale rules.
- **LIGHTING & PHYSICAL INTEGRATION** — light direction and quality, crisp contact shadows, light wrap on curved edges; for glass/liquids, realistic refraction, caustics and the exact liquid level.
- **CAMERA & REALISM** — lens/aperture from the table, critical focus on the product (label if any), subtle grain, natural color; forbid CGI look, fake plastic gloss, floating objects, warped geometry, extra products, watermarks.

End with one line: "Paste each prompt together with the original photo into your image model (image edit / reference image mode)."

---

## Mode B — Audit a generated result

Compare the generated image with the original and report a short checklist, each item ✅ / ⚠️ / ❌ with one line of evidence:

1. **Geometry & proportions** — silhouette, aspect ratio, closure/hardware, no warping.
2. **Materials & color** — same finish (matte/gloss/metal/glass), same hues.
3. **Text & logo** — every legible line identical (spelling, accents, alignment), logo intact, nothing invented; blurry small print flagged, not "fixed" with fake words.
4. **Scale** — matches the scale class; no miniature/toy effect; large items at 1:1 against architecture, no small pedestals.
5. **Physical integration** — contact shadows present and consistent with the light, no floating; refraction/caustics/liquid level plausible for glass or liquids.
6. **Realism** — lens look matches the table, no CGI gloss, no extra products, no watermark.

If anything is ⚠️ or ❌, output ONE corrected prompt in a code block that keeps the original prompt and adds a short **CORRECTIONS** block naming exactly what to fix (e.g. 'Restore the label line "AURA OIL" centered, crisp serif typography'). Never suggest changing the product itself.
