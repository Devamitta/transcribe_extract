# Thumbnail Subjects Format

Defines the schema for `output/thumbnail_subjects.json`.

## Purpose

This file is a rolling log of the main visual subject used in each generated YouTube thumbnail. It is injected into the image-prompt LLM call to prevent repeating the same objects or scenes across thumbnails.

## File Location

`output/thumbnail_subjects.json`

## Schema

```json
{
  "subjects": [
    {
      "file": "basename-of-image.jpg",
      "subject": "3-6 word description of the main visual element"
    }
  ]
}
```

## Field Definitions

| Field | Type | Description |
|-------|------|-------------|
| `file` | string | Image filename, basename only (no path). Example: `2024-01-15-talk-title.jpg` |
| `subject` | string | 3–6 words identifying the dominant visual object or scene element |

## Guidelines for Subject Extraction

**Focus only on the main visual subject** — the single dominant object or scene the image is built around.

**Ignore:** lighting quality, colour palette, mood, style words (photorealistic, cinematic, 8K), background details, time of day.

**Include:** the concrete object, landscape element, or scene type that gives the image its identity.

**Length:** 3–6 words. If you cannot describe it in 6 words, you are including too much.

### Examples

| Image content | Correct subject | Incorrect (too long / too vague) |
|---------------|----------------|----------------------------------|
| Close-up of a cracked clay water pot in jungle undergrowth | `cracked clay pot in jungle` | `photorealistic image of a cracked ancient clay water vessel sitting in lush jungle undergrowth with soft morning light` |
| Autumn leaves floating on a still pond | `autumn leaves on still pond` | `peaceful Buddhist nature scene` |
| Ancient stone bridge over a forest stream | `stone bridge over forest stream` | `bridge` |
| Rows of oil lamps on a temple shelf | `oil lamps on temple shelf` | `candles and lamps in a monastery` |
| Single lotus bud at dawn | `lotus bud at dawn` | `lotus flower` |

## Notes

- The file is maintained automatically by `scripts/yt_image_gen.py` for new generations (rolling window of 50 entries).
- For **existing images**, populate this file manually or via a vision agent scanning the `output/thumbnails/` folder.
- Entries do not need to be in any particular order; only the most recent 30 are injected as "avoid" context.
- If an entry for a filename already exists it will be replaced, not duplicated.
