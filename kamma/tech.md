# Tech Notes

## Tools & Platforms
- **Language:** Python 3.12
- **Package Manager:** uv
- **Transcription:** MLX Whisper (Apple Silicon local inference)
- **Extraction:** Google Gemini API (real-time) or OpenAI Batch API (cost-efficient batch processing)
- **Configuration:** python-dotenv

## Who This Is For
- A single developer running the pipeline locally
- No collaboration features needed

## Constraints
- **Hardware:** Requires Apple Silicon (M-series chip) for MLX Whisper
- **API:** Requires Google Gemini API key and/or OpenAI API key in .env file
- **Time:** Transcription is slow on CPU; recommended to use `caffeinate -i nice -n 10` for background processing

## Resources
- MLX Whisper: https://github.com/mlx-audio/mlx-whisper
- Gemini API: https://ai.google.dev/
- The project uses a Pāli glossary to bias transcription accuracy

## What the Output Looks Like
- **Transcripts:** Raw markdown in `/output/`
- **Extracted Points:** Structured markdown with tags/categories in `/extracted/`
- **YouTube Metadata:** Review file at `output/tims_review_YYYY-MM-DD.md`
- **YouTube Export:** Renamed MP3s and `summary.md` in `output/audio_youtube/`
- **Polished Files:** Readable prose version of extracted text in `output/polished/`
- **Reports:** Evaluation and error reports in `/reports/`
- **File Format:** Markdown (.md)at:** Markdown (.md)