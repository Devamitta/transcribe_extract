from pathlib import Path
from google import genai
from google.genai import types
from tenacity import (
    retry,
    wait_exponential,
    stop_after_attempt,
    retry_if_exception_type,
)
from dotenv import load_dotenv

load_dotenv()
client = genai.Client()


def test_api_key() -> bool:
    """Test the API key with a simple request."""
    try:
        response = client.models.generate_content(
            model="gemini-2.0-flash",
            contents="test",
            config=types.GenerateContentConfig(
                temperature=0.0,
                max_output_tokens=5,
            ),
        )
        if response.text is not None:
            print("[OK] API key is working.")
            return True
    except Exception as e:
        print(f"[ERROR] API key test failed: {e}")
    return False


PALI_GLOSSARY = (
    "Dhamma, Sangha, Buddha, kamma, nibbāna, saṃsāra, dukkha, samudaya, nirodha, magga, ariya, aṭṭhaṅgika, "
    "sammā, diṭṭhi, saṅkappa, vācā, kammanta, ājīva, vāyāma, sati, samādhi, bhāvanā, samatha, vipassanā, "
    "jhāna, vitakka, vicāra, pīti, sukha, ekaggatā, nimitta, upacāra, appanā, satipaṭṭhāna, ānāpānasati, "
    "mettā, karuṇā, muditā, upekkhā, brahmavihāra, rupa, vedanā, saññā, saṅkhāra, viññāṇa, khandha, kilesa, "
    "āsava, nīvaraṇa, lobha, dosa, moha, rāga, paṭigha, māna, avijjā, taṇhā, upādāna, anicca, anattā, "
    "suññatā, tilakkhaṇa, paṭiccasamuppāda, idappaccayatā, sīla, vinaya, pāṭimokkha, bhikkhu, bhikkhunī, "
    "upāsaka, upāsikā, dāna, puñña, pāramī, adhiṭṭhāna, bhante, āyasmā, thera, mahāthera, tathāgata, arahant, "
    "anāgāmī, sakadāgāmī, sotāpanna, sutta, abhidhamma, nikāya, āgama, pāli, vīriya, khantī, sacca, paññā, "
    "saddhā, hiri, ottappa, bojjhaṅga, indriya, bala, padhāna, upādāya, āyatana."
)


def chunk_text_no_overlap(text: str, chunk_size=2000) -> list[str]:
    """Splits text cleanly without overlap to prevent duplication during reassembly."""
    words = text.split()
    return [
        " ".join(words[i : i + chunk_size]) for i in range(0, len(words), chunk_size)
    ]


@retry(
    wait=wait_exponential(multiplier=2, min=4, max=60),
    stop=stop_after_attempt(5),
    retry=retry_if_exception_type(Exception),
)
def correct_pali_transcription(chunk: str) -> str:
    system_instruction = (
        "You are a strict text correction engine. The input is a raw, automated transcript of a Buddhist talk. "
        f"Correct phonetic misspellings of these terms: [{PALI_GLOSSARY}]. "
        "CRITICAL RULES: Output ONLY the corrected text. Do NOT summarize. Do NOT format with markdown. Do NOT change English words unless they are corrupted Pāli terms."
    )

    response = client.models.generate_content(
        model="gemini-2.0-flash",
        contents=chunk,
        config=types.GenerateContentConfig(
            system_instruction=system_instruction,
            temperature=0.0,
        ),
    )
    if response.text is None:
        raise ValueError("Empty response from Gemini API")
    return response.text


def main():
    input_dir = Path("output")
    output_dir = Path("corrected")
    output_dir.mkdir(exist_ok=True)

    if not test_api_key():
        print("Exiting due to API key test failure.")
        return

    md_files = list(input_dir.glob("*.md"))
    if not md_files:
        print("No files found in 'output/'.")
        return

    for file_path in md_files:
        final_output_path = output_dir / file_path.name
        if final_output_path.exists():
            print(f"Skipping '{file_path.name}', already corrected.")
            continue

        print(f"Correcting '{file_path.name}'...")
        with open(file_path, "r", encoding="utf-8") as f:
            text = f.read()

        chunks = chunk_text_no_overlap(text)
        corrected_chunks = []

        for i, chunk in enumerate(chunks):
            print(f"  Chunk {i + 1}/{len(chunks)}...")
            try:
                result = correct_pali_transcription(chunk)
                corrected_chunks.append(result.strip())
            except Exception as e:
                print(f"  Failed on chunk {i + 1}: {e}")

        if corrected_chunks:
            with open(final_output_path, "w", encoding="utf-8") as f:
                f.write(" ".join(corrected_chunks))
            print(f"Saved corrected text to '{final_output_path.name}'.\n")


if __name__ == "__main__":
    main()
