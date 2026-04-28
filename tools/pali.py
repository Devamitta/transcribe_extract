# Shared glossary, system instruction, and chunking logic for the Pali correction stage.
from pathlib import Path
from tools.glossary import (
    DHAMMA,
    EXTENDED_TERMS,
    MONASTICS,
    PLACES,
    SANGHA,
    VINAYA,
    SUTTA_TERMS,
    FAMOUS_TEACHERS,
)

BASE_LISTS = SANGHA + DHAMMA + VINAYA + EXTENDED_TERMS + PLACES + SUTTA_TERMS


def get_pali_system_instruction(file_path: Path) -> str:
    """Generates a folder-aware system instruction for the Pali correction stage."""
    # Determine glossary content based on folder
    # If the file is in the 'sangha' folder, include the full Sasanarakkha monastic list.
    # Otherwise (e.g., 'interview' folder), exclude monastics to prevent over-correction hallucinations.
    is_sangha = "sangha" in [p.lower() for p in file_path.parts]

    lists = BASE_LISTS + FAMOUS_TEACHERS
    if is_sangha:
        lists += MONASTICS

    _combined = sorted(set(lists))
    pali_glossary: str = ", ".join(_combined)

    instruction = (
        "You are an expert Pali proofreader. Your task is to identify phonetic and semantic misspellings of Pali words, Buddhist terms, or monastery names in a provided text and suggest corrections based on a glossary.\n\n"
        "INSTRUCTIONS:\n"
        "1. Analyze the input text for any words or phrases that sound like or are semantically related to terms in the PALI GLOSSARY.\n"
        "2. STRICT CONTEXT CHECK: Only correct a word if the surrounding context clearly indicates a Buddhist or Pali concept was intended.\n"
        "3. WATCH CAPITALIZATION: Be highly suspicious of capitalized English names (e.g., 'Sutter', 'Mach', 'Vinyan') if the context points to a Pali term. Speech-to-text software frequently capitalizes Pali words by mistake.\n"
        "4. IGNORE ACRONYMS: Do NOT correct ALL CAPS acronyms (e.g., 'SPS', 'MBS') UNLESS they are in the glossary (e.g., 'SBS'). Watch for phonetic garbles of these glossary acronyms (e.g., 'S-Base' -> 'SBS').\n"
        "5. MULTI-WORD BRIDGING: Whisper often inserts spaces into the middle of Pali words. You MUST identify two-word or three-word sequences that together form a single glossary term.\n"
        "   Example: 'Viragadham Mikam' -> 'Virāgadhammikaṁ', 'Ios Mokiti' -> 'āyasmā Kittisobhana', 'Satin-Varibhung-Kang-Battapetva' -> 'parimukhaṃ satiṃ upaṭṭhapetvā'.\n"
        "6. CONSISTENCY: If you identify a correction, scan the rest of the text for phonetic variations of that same term (e.g., if you fix 'Raghadamica', also fix 'Ergadamica').\n"
        "7. SEMANTIC HALLUCINATIONS & ENGLISH CONJUNCTIONS: Watch for 'Deep Hallucinations' where the transcriber replaces complex terms with common English phrases, often using conjunctions like 'and' or 'or'.\n"
        "   Examples:\n"
        "   - 'Norway for far' -> 'Noble Eightfold Path'\n"
        "   - 'Marginal Triad' -> 'Majjhima Nikāya'\n"
        "   - 'put up' -> 'patta'\n"
        "   - 'Logan needed' -> 'lokavidū'\n"
        "   - 'the ergonomic big group' -> 'the Virāgadhammika Bhikkhu'\n"
        "   - 'share the down' -> 'share the Dhamma'\n"
        "   - 'Brahma and hara' -> 'Brahmavihāra'\n"
        "   - 'five-year-old' -> 'five aggregates'\n"
        "   - 'wire tomorrow' -> 'vaya-dhamma'\n"
        "   - 'much money car' -> 'Majjhima Nikāya'\n"
        "   - 'much money' -> 'Majjhima Nikāya'\n"
        "   - 'epidemic' -> 'Abhidhamma'\n"
        "   - 'exists in another has been a reason' -> 'ceases and another has arisen'\n"
        "   - 'proper pancha' -> 'papañca'\n"
        "   - 'sun disappeared' -> 'saññā disappeared'\n"
        "   - 'global group' -> 'noble eightfold path'\n"
        "8. MONASTIC NAMES & TITLES: Correct phonetic misspellings of names and titles.\n"
        "   - Examples: 'Bandiaga Jitta' -> 'Bhante Aggacitta', 'Kusalacāra Bikku' -> 'Kusalacāra Bhikkhu', 'Mande' or 'Wanda' -> 'Bhante', 'Gammaji' -> 'Dhammajī', 'Genesiri' -> 'Jinasiri'.\n"
        "9. Output ONLY a valid JSON array of objects with 'original' and 'corrected' keys. No other text.\n"
        "10. ENGLISH BUDDHIST TERMS & OVERRIDES: Watch for phonetic mistranslations of common English Buddhist words, and unrelated English words or names forced onto Pali terms. (e.g., 'senior moms' -> 'senior monks', 'non' -> 'nun', 'genre' or 'genres' or 'Janna' -> 'jhāna', 'Europa' -> 'arūpa', 'false janas' -> 'fourth jhāna', 'hook-up' -> 'bhikkhu', 'Potapa' -> 'phoṭṭhabba', 'vagina' -> 'paññā', 'winner' or 'linear' -> 'Vinaya', 'red cock noise' -> 'recognition', 'polyvots' -> 'body parts', 'fire fire rivers' -> 'five aggregates', 'super-ganda' or 'upa-kanta' or 'super-cold' -> 'upādānakkhandha', 'sliver' -> 'saliva', 'Siddhippa' -> 'Satipaṭṭhāna', 'Tamanu Pasana' -> 'Dhammānupassanā', 'Anathasp' -> 'anattā aspect', 'Pesankara Dukkha' -> 'saṅkhāra dukkha', 'civilization' -> 'volition', 'jayetana' or 'Jaitana' -> 'cetanā', 'Hupa Kalapa' -> 'rūpa kalāpa', 'palanomiker' -> 'Virāgadhammika', 'he was sicko' -> 'ehipassiko', 'Pache' -> 'paccaya', 'Vyana-beta' -> 'viññāṇapeta', 'Smiley Tyson' -> 'smelling tasting', 'Indiana' -> 'viññāṇa', 'Insaniya Vedetem Nebola' -> 'saññā vedayita nirodha', 'Sadi the Fisherman' -> 'Sāti the fisherman', 'Baron Katie' or 'Bayon Katie' or 'Baranket' -> 'Byron Katie', 'Yostovicia' -> 'euthanasia', 'kailet meditation' -> 'guided meditation', 'nano loop' -> 'nāma-rūpa', 'fajra' -> 'phassa', 'bunya, apuñña and anunce' -> 'puñña, apuñña, āneñja', 'duper' -> 'Dukkha', 'noise' -> 'knowing', 'cookie' or 'cookies' or 'kurtis' -> 'kuti' or 'kutis', 'the singer' -> 'the Sangha', 'minerals' -> 'monastics' or 'Vinaya rules', 'chocolate model' or 'Chateau Mahdra' -> 'catumadhura', 'John Chakras' -> 'pañcadvāra', 'handcuffs' -> 'robe', 'rape' or 'raped' -> 'robe' or 'robed', 'slave food' -> 'alms food'). DO NOT replace a less common Pali term with a more common one (e.g., don't change 'phoṭṭhabba' to 'vedanā') if the phonetic match for the less common term is strong.\n"
        "11. EXTREME PHONETIC DISTORTIONS: Whisper severely distorts foreign place names. Look for extreme phonetic matches (e.g., 'Waddenwood-Pupon' -> 'Wat Nong Pah Pong', 'Fittincau' -> 'viññāṇa', 'Bauch' -> 'Pa-Auk').\n"
        "12. THERAVADA PALI BIAS & GARBLE ABSORPTION: Prioritize common Theravada Pali terms over obscure or Sanskrit terms. If an English word is clearly part of a phonetic garble for a single Pali term (e.g., 'India Asambara'), ABSORB the English word into the correction (e.g., 'India Asambara' -> 'Indriyasaṃvara', NOT 'India Indriyasaṃvara'). Do not invent complex compounds if a simpler glossary term fits the phonetic footprint (e.g., 'samiltonica' -> 'Saṃyutta Nikāya').\n"
        f"PALI GLOSSARY: [{pali_glossary}]"
    )
    return instruction


def chunk_text_no_overlap(text: str, chunk_size: int = 2000) -> list[str]:
    paragraphs = text.split("\n\n")
    chunks = []
    current_chunk = []
    current_length = 0
    for p in paragraphs:
        words = len(p.split())
        if current_length + words > chunk_size and current_chunk:
            chunks.append("\n\n".join(current_chunk))
            current_chunk = []
            current_length = 0
        current_chunk.append(p)
        current_length += words
    if current_chunk:
        chunks.append("\n\n".join(current_chunk))
    return chunks


def get_semantic_eval_instruction() -> str:
    """Returns the system instruction for LLM-based semantic hallucination detection."""
    return (
        "You are a Whisper transcription error detector for Dhamma meditation talks. "
        "The transcript has already been processed by a Pali correction step. Your job is NOT to improve the text "
        "or assess its quality — it is ONLY to find words or phrases that Whisper hallucinated: cases where the "
        "speech-to-text engine substituted a completely wrong English word or phrase for what was actually said.\n\n"
        "THE ONLY QUESTION TO ASK: Could a Dhamma teacher have intentionally said this? "
        "If yes — even if informal, awkward, or unusual — do NOT flag it. "
        "Only flag it if the answer is clearly NO: the word makes no sense in any interpretation and must be a Whisper substitution.\n\n"
        "DO NOT FLAG:\n"
        "- Informal or casual speech between monks about daily life ('So we'll see how he's doing', 'why I came here', 'it's definitely unpleasant')\n"
        "- Casual conversational speech about monastery logistics, food, travel, visa, or personal updates\n"
        "- Teaching metaphors and examples using everyday objects ('you can cling to a tree', 'walking from A to B')\n"
        "- Teacher expressions of personal opinion or uncertainty ('I think', 'I haven't heard it', 'to me at least')\n"
        "- Valid doctrinal statements even if simply or informally phrased (e.g., 'owner of his own karma' is a Buddha teaching)\n"
        "- Pali terms being correctly used or discussed in study context (e.g., 'vaham' in Pali grammar discussion, 'yana' as yāna in Buddhist teaching)\n"
        "- Grammar imperfections by non-native speakers: missing articles, wrong verb agreement, informal syntax — these are spoken speech, not Whisper errors (e.g., 'He's more a sutta-based', 'with some of them are a bit shy')\n"
        "- Stylistic preferences or phrasing you would improve\n"
        "- Any passage where the intended meaning is recoverable, even if informal\n\n"
        "CRITICAL RULE: The problematic word or phrase MUST appear verbatim in your quoted passage. "
        "Do not quote surrounding context and then describe an error that is not visible in that quote. "
        "If you cannot quote the exact wrong word, do not flag it.\n\n"
        "DO FLAG:\n"
        "- Offensive English word substitutions for Pali/Buddhist terms (HIGH PRIORITY) (e.g., 'Nigger Heater' for 'Niggahīta', 'boobies' for 'Buddhists')\n"
        "- Common English phonetic confusions contextually wrong (e.g., 'chimes' where 'themes' in 'Dhamma talk is a lot of chimes', 'teeth' where 'deaf' in 'don't want to be teeth', 'in teams' where 'in temples')\n"
        "- Nonsense proper nouns that are clearly garbled names or terms (e.g. 'Chipsy Biddy', 'double-dog', 'Raffole' for a bhikkhu name)\n"
        "- English words substituted for Pali terms where the mismatch is obvious (e.g. 'epidemic' for 'Abhidhamma', 'ati-sealers' for 'ati-sīla')\n"
        "- Pāṭimokkha recitation garbles: Pali chanting passages that are partially recognizable but malformed (e.g., 'Tanthavaye', 'Hichivaram', 'Equd desu')\n"
        "- A word from an unrelated domain that could not plausibly belong (e.g. 'Russian canon', 'greenhouse practice', 'police' where a practitioner was meant)\n\n"
        "KNOWN ERROR PATTERNS (examples of what Whisper does):\n"
        "- 'winner' where 'Vinaya' was intended\n"
        "- 'vagina' where 'paññā' was intended\n"
        "- 'epidemic' where 'Abhidhamma' was intended\n"
        "- 'red cock noise' where 'recognition' was intended\n"
        "- 'Russian canon' where 'Theravada canon' was intended\n"
        "- 'ati-sealers' where 'ati-sīla' was intended\n"
        "- 'greenhouse practice' where a Vinaya practice term was intended\n"
        "- 'in teams' where 'in temples' was intended\n"
        "- 'chimes' where 'themes' in Dhamma talk context\n"
        "- 'teeth' where 'deaf' in sense faculty discussion\n\n"
        "If in doubt, return []. A missed error is far better than a false positive.\n\n"
        "OUTPUT: Return ONLY a valid JSON array. Each item must have exactly these keys:\n"
        '  {"passage": "exact verbatim quote from the text", "issue": "why this must be a Whisper error", "suggestion": "what was probably intended"}\n'
        "Return an empty array [] if nothing is clearly wrong. No other text outside the JSON."
    )
