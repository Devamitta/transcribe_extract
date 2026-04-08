import os
import sys
import time
from pathlib import Path
from dotenv import load_dotenv
from google import genai
from google.genai import types

TEST_MODE = "--test" in sys.argv or "-t" in sys.argv

load_dotenv()

API_KEYS: list[tuple[str, str]] = []
for i in range(1, 100):
    key = os.getenv(f"GEMINI_API_KEY_{i}")
    if key:
        API_KEYS.append((f"GEMINI_API_KEY_{i}", key))

if not API_KEYS:
    key = os.getenv("GEMINI_API_KEY")
    if key:
        API_KEYS.append(("GEMINI_API_KEY", key))

if not API_KEYS:
    print("[ERROR] No GEMINI_API_KEY found in .env")
    exit(1)

print(f"Loaded {len(API_KEYS)} API keys: {[k[0] for k in API_KEYS]}", flush=True)

MODEL = "gemini-2.5-flash"
RPM_LIMIT = 5
MIN_REQUEST_INTERVAL = 12
HOURS_TO_RESET = 24


class KeyManager:
    def __init__(self, keys: list[tuple[str, str]]):
        self.keys = keys
        self.current_index = 0
        self.client = genai.Client(api_key=self.keys[0][1])
        self.current_key_name = self.keys[0][0]
        self.failed_keys: dict[int, float] = {}
        self.last_request_time = 0.0

    @property
    def current_model(self) -> str:
        return MODEL

    def test_current_key(self) -> bool:
        try:
            print(f"Testing key {self.current_key_name}...", flush=True)
            response = self.client.models.generate_content(
                model=self.current_model,
                contents="hi",
                config=types.GenerateContentConfig(
                    max_output_tokens=5, temperature=0.0
                ),
            )
            if response.text:
                print(f"[OK] {self.current_key_name} works", flush=True)
                return True
            return False
        except Exception as e:
            print(f"[ERROR] {self.current_key_name} failed: {e}", flush=True)
            return False

    def switch_to_next_key(self) -> bool:
        original_index = self.current_index
        while True:
            self.current_index = (self.current_index + 1) % len(self.keys)
            failure_time = self.failed_keys.get(self.current_index)
            if failure_time:
                hours_since_failure = (time.time() - failure_time) / 3600
                if hours_since_failure >= HOURS_TO_RESET:
                    print(f"Key reset after {hours_since_failure:.1f}h", flush=True)
                    del self.failed_keys[self.current_index]
                    break
                if self.current_index == original_index:
                    print(
                        f"[ERROR] All keys failed. Wait {HOURS_TO_RESET}h", flush=True
                    )
                    return False
                continue
            break

        key_name, key_value = self.keys[self.current_index]
        self.current_key_name = key_name
        self.client = genai.Client(api_key=key_value)
        print(f"Switched to {self.current_key_name}", flush=True)
        print("Waiting 3s...", flush=True)
        time.sleep(3)
        return True

    def handle_quota_error(self) -> bool:
        print(f"{self.current_key_name} quota exceeded, switching...", flush=True)
        self.failed_keys[self.current_index] = time.time()
        return self.switch_to_next_key()

    def wait_for_rate_limit(self) -> None:
        elapsed = time.time() - self.last_request_time
        if elapsed < MIN_REQUEST_INTERVAL:
            wait = MIN_REQUEST_INTERVAL - elapsed
            print(f"Rate limiting: waiting {wait:.1f}s...", flush=True)
            time.sleep(wait)
        self.last_request_time = time.time()


key_manager = KeyManager(API_KEYS)
print(f"Starting with {key_manager.current_key_name}", flush=True)


PALI_GLOSSARY = (
    "Dhamma, Sangha, Buddha, kamma, nibbāna, saṃsāra, dukkha, samudaya, nirodha, magga, ariya, aṭṭhaṅgika, "
    "sammā, diṭṭhi, saṅkappa, vācā, kammanta, ājīva, vāyāma, sati, samādhi, bhāvanā, samatha, vipassanā, "
    "jhāna, vitakka, vicāra, pīti, sukha, ekaggatā, nimitta, upacāra, appanā, satipaṭṭhāna, ānāpānasati, "
    "mettā, karuṇā, muditā, upekkhā, brahmavihāra, rupa, vedanā, saññā, saṅkhāra, viññāṇa, khandha, kilesa, "
    "āsava, nīvaraṇa, lobha, dosa, moha, rāga, paṭigha, māna, avijjā, taṇhā, upādāna, anicca, anattā, "
    "suññatā, tilakkhaṇa, paṭiccasamuppāda, idappaccayatā, sīla, vinaya, pāṭimokkha, bhikkhu, bhikkhunī, "
    "upāsaka, upāsikā, dāna, puñña, pāramī, adhiṭṭhāna, bhante, āyasmā, thera, mahāthera, tathāgata, arahant, "
    "anāgāmī, sakadāgāmī, sotāpanna, sutta, abhidhamma, nikāya, āgama, pāli, vīriya, khantī, sacca,aññā, "
    "saddhā, hiri, ottappa, bojjhaṅga, indriya, bala, padhāna, upādāya, āyatana."
)


def chunk_text_no_overlap(text: str, chunk_size=15000) -> list[str]:
    words = text.split()
    return [
        " ".join(words[i : i + chunk_size]) for i in range(0, len(words), chunk_size)
    ]


def correct_pali_transcription(chunk: str) -> str:
    key_manager.wait_for_rate_limit()
    print(f"    -> {key_manager.current_key_name}...", flush=True)
    system_instruction = (
        "You are a strict text correction engine. "
        f"Correct phonetic misspellings: [{PALI_GLOSSARY}]. "
        "Output ONLY corrected text. No markdown."
    )
    response = key_manager.client.models.generate_content(
        model=key_manager.current_model,
        contents=chunk,
        config=types.GenerateContentConfig(
            system_instruction=system_instruction, temperature=0.0
        ),
    )
    print("    -> Got response", flush=True)
    if response.text is None:
        raise ValueError("Empty response")
    return response.text


def get_completed_chunks(fp: Path, output_dir: Path) -> int:
    status_dir = output_dir / ".status"
    status_dir.mkdir(exist_ok=True)
    sf = status_dir / f"{fp.stem}.status"
    if sf.exists():
        try:
            return int(sf.read_text().strip())
        except ValueError:
            return 0
    return 0


def mark_completed_chunks(fp: Path, output_dir: Path, completed: int) -> None:
    status_dir = output_dir / ".status"
    status_dir.mkdir(exist_ok=True)
    sf = status_dir / f"{fp.stem}.status"
    sf.write_text(str(completed))


def main():
    input_dir = Path("output/transcribed_output")
    output_dir = Path("output/corrected_pali")
    output_dir.mkdir(exist_ok=True)

    # Find working key
    working_key = False
    for _ in range(len(key_manager.keys)):
        if key_manager.test_current_key():
            working_key = True
            break
        if not key_manager.switch_to_next_key():
            break

    if not working_key:
        print("All API keys failed. Exiting.")
        return

    md_files = list(input_dir.glob("*.md"))
    if not md_files:
        print("No files in 'transcribed_output/'.")
        return

    print(f"Found {len(md_files)} files", flush=True)

    for file_path in md_files:
        final_output = output_dir / file_path.name
        temp_output = output_dir / f".{file_path.name}.tmp"

        with open(file_path, "r", encoding="utf-8") as f:
            text = f.read()

        chunks = chunk_text_no_overlap(text)
        total = len(chunks)

        completed = get_completed_chunks(file_path, output_dir)
        start = completed

        if final_output.exists() and completed >= total:
            print(f"Skipping '{file_path.name}', done.")
            continue
        elif completed > 0:
            print(
                f"Resuming '{file_path.name}' from chunk {completed + 1}/{total}",
                flush=True,
            )
        else:
            print(f"Correcting '{file_path.name}'...", flush=True)

        if TEST_MODE:
            total = min(3, total)

        # Load existing progress
        if temp_output.exists():
            corrected = temp_output.read_text().split()
        elif start > 0:
            corrected = final_output.read_text().split()
        else:
            corrected = []
        failed = []

        print(f"  {total - start} chunks to process", flush=True)

        for i in range(start, total):
            print(f"  Chunk {i + 1}/{total}...", flush=True)
            for attempt in range(3):
                try:
                    result = correct_pali_transcription(chunks[i])
                    corrected.append(result.strip())
                    temp_output.write_text(" ".join(corrected))
                    break
                except Exception as e:
                    if "429" in str(e) or "RESOURCE_EXHAUSTED" in str(e):
                        if not key_manager.handle_quota_error():
                            print("  Failed: all keys exhausted", flush=True)
                            failed.append(i + 1)
                        break
                    elif attempt == 2:
                        print(f"  Failed: {e}", flush=True)
                        failed.append(i + 1)
            time.sleep(2)

        # Save results
        temp_output.write_text(" ".join(corrected))
        if failed:
            mark_completed_chunks(
                file_path, output_dir, start + len(corrected) - len(failed)
            )
            final_output.write_text(" ".join(corrected))
            temp_output.unlink()
            print(f"Saved (partial). Failed: {failed}")
        elif not failed:
            mark_completed_chunks(file_path, output_dir, total)
            final_output.write_text(" ".join(corrected))
            temp_output.unlink()
            print(f"Saved to '{final_output.name}'.")

        print("  Waiting 5s between files...", flush=True)
        time.sleep(5)


if __name__ == "__main__":
    main()
