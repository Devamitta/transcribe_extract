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
        "10. ENGLISH BUDDHIST TERMS & OVERRIDES: Watch for phonetic mistranslations of common English Buddhist words, and unrelated English words or names forced onto Pali terms. The following English words are ALWAYS hallucinations in this corpus and MUST be corrected regardless of perceived English plausibility: 'vagina' or 'vaginas' -> 'paññā' or 'sampajañña', 'some vagina' -> 'sampajañña', 'winner' -> 'Vinaya', 'linear' -> 'Vinaya', 'the singer' or 'singers' -> 'the Sangha', 'Europa' -> 'arūpa', 'cookie' or 'cookies' -> 'kutī' or 'kutis', and 'cook' -> 'kutī' (DO NOT change 'cook' if context is explicitly about food, meals, or kitchens). Other examples: 'false janas' -> 'fourth jhāna', 'hook-up' -> 'bhikkhu', 'Potapa' -> 'phoṭṭhabba', 'red cock noise' -> 'recognition', 'polyvots' -> 'body parts', 'fire fire rivers' -> 'five aggregates', 'super-ganda' or 'upa-kanta' or 'super-cold' -> 'upādānakkhandha', 'sliver' -> 'saliva', 'Siddhippa' -> 'Satipaṭṭhāna', 'Tamanu Pasana' -> 'Dhammānupassanā', 'Anathasp' -> 'anattā aspect', 'Pesankara Dukkha' -> 'saṅkhāra dukkha', 'civilization' -> 'volition', 'jayetana' or 'Jaitana' -> 'cetanā', 'Hupa Kalapa' -> 'rūpa kalāpa', 'palanomiker' -> 'Virāgadhammika', 'he was sicko' -> 'ehipassiko', 'Pache' -> 'paccaya', 'Vyana-beta' -> 'viññāṇapeta', 'Smiley Tyson' -> 'smelling tasting', 'Indiana' -> 'viññāṇa', 'Insaniya Vedetem Nebola' -> 'saññā vedayita nirodha', 'Sadi the Fisherman' -> 'Sāti the fisherman', 'Baron Katie' or 'Bayon Katie' or 'Baranket' -> 'Byron Katie', 'Yostovicia' -> 'euthanasia', 'kailet meditation' -> 'guided meditation', 'nano loop' -> 'nāma-rūpa', 'fajra' -> 'phassa', 'bunya, apuñña and anunce' -> 'puñña, apuñña, āneñja', 'duper' -> 'Dukkha', 'noise' -> 'knowing', 'kurtis' -> 'kutis', 'minerals' -> 'monastics' or 'Vinaya rules', 'stonic' -> 'tonic', 'manoeuvres' -> 'monastics', 'chocolate model', 'Chateau Mahdra', 'Chaturmādha', 'Chaturmattu', or 'Chathumattā' -> 'catumadhura', 'John Chakras' -> 'pañcadvāra', 'handcuffs' -> 'robe', 'rape' or 'raped' -> 'robe' or 'robed', 'slave food' -> 'alms food'). DO NOT replace a less common Pali term with a more common one (e.g., don't change 'phoṭṭhabba' to 'vedanā') if the phonetic match for the less common term is strong.\n"
        "11. EXTREME PHONETIC DISTORTIONS: Whisper severely distorts foreign place names. Look for extreme phonetic matches (e.g., 'Waddenwood-Pupon' -> 'Wat Nong Pah Pong', 'Fittincau' -> 'viññāṇa', 'Bauch' -> 'Pa-Auk').\n"
        "12. THERAVADA PALI BIAS & GARBLE ABSORPTION: Prioritize common Theravada Pali terms over obscure or Sanskrit terms. If an English word is clearly part of a phonetic garble for a single Pali term (e.g., 'India Asambara'), ABSORB the English word into the correction (e.g., 'India Asambara' -> 'Indriyasaṃvara', NOT 'India Indriyasaṃvara'). Do not invent complex compounds if a simpler glossary term fits the phonetic footprint (e.g., 'samiltonica' -> 'Saṃyutta Nikāya').\n"
        "13. SURGICAL INTEGRITY: The 'original' field in your JSON response MUST NOT contain line breaks (\\n), timestamps (e.g., [12.3]), or span across multiple sentences or paragraphs. You MUST target the absolute shortest possible phrase (e.g., 1-4 words). NEVER attempt to rewrite or merge entire sentences. If you include line breaks or timestamps, the replacement script will fail, causing fatal metadata loss.\n"
        "14. HALLUCINATED NOISE (NON-ENGLISH CHARACTERS): ALL non-English characters (e.g., Chinese, Thai, Cyrillic, Russian script, or random symbols) are strict transcription errors. You MUST identify these in the 'original' field and either remove them or replace them with the intended English/Pali term.\n"
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
        "- Personal health/lifestyle interviews about weight loss, tea, diet, fitness, sleep, mother's health, depression counseling — entire context is personal, not Dhamma teaching (files with 'feedback' in filename are high probability)\n"
        "- Teaching metaphors and examples using everyday objects ('you can cling to a tree', 'walking from A to B', 'fire of lust' for rāga metaphor)\n"
        "- Non-Buddhist proper name references used as teaching examples (mentioning Nietzsche, psychologists, Chinese greetings, etc. — these are intentional analogies, not errors)\n"
        "- Teacher expressions of personal opinion or uncertainty ('I think', 'I haven't heard it', 'to me at least')\n"
        "- Valid doctrinal statements even if simply or informally phrased (e.g., 'owner of his own karma' is a Buddha teaching, 'field of merit' = puññakkhetta, 'second arrow' is established Dhamma metaphor, 'wholesome mental state' = kusala citta)\n"
        "- Pali terms being correctly used or discussed in study context (e.g., 'vaham' in Pali grammar discussion, 'yana' as yāna in Buddhist teaching, valid Pali compounds like 'kāyābhisamaya', 'bhavaṅga', 'moha samādhi', 'sense space' as āyatana)\n"
        "- Valid Theravada doctrinal compound terms and phrasings (e.g., 'pītisukha' = joy and bliss as compound in jhāna factors; 'Sutta-jhāna' = jhāna as in suttas; 'domanassa' = mental pain; 'kammaṭṭhāna' = meditation object; 'cakkhu-indriya' = eye faculty) — do not flag when used correctly\n"
        "- Asubha (corpse) meditation teaching examples mentioning attractive persons in context of contemplating impermanence and decay (valid pedagogical metaphor, not a Whisper error)\n"
        "- Speaker intentional repetition for emphasis (e.g., 'it's about effort, it's about effort' — not a Whisper error but intentional teaching emphasis)\n"
        "- Grammar imperfections by non-native speakers: missing articles, wrong verb agreement, informal syntax — these are spoken speech, not Whisper errors (e.g., 'He's more a sutta-based', 'with some of them are a bit shy')\n"
        "- Personal conversation passages: family members (mother, grandma, father, wife), holidays (Christmas, birthdays), social obligations, phone calls, relationships — especially passages with NO Pali or Dhamma-specific terms; skip the entire section\n"
        "- Teacher's dramatic analogies or vivid examples, even if shocking or unrelated to Dhamma (e.g., 'yesterday he was killing people, today he's wearing robes' [Angulimala story], analogy about trucks to illustrate defilement intensity)\n"
        "- Teacher explanations of human anatomy or physiology (heart, lungs, oxygen, blood pressure) — even if scientifically imprecise, these are intentional explanations, not Whisper substitutions\n"
        "- Valid metaphors and metonyms: 'fire of lust' (rāga-aggi), 'field of merit' (puññakkhetta), 'wholesome mental state' (kusala citta)\n"
        "- Everyday analogies and vivid metaphors (e.g., 'the sun just flows in one direction', 'throwing stone for fun')\n"
        "- Valid Dhamma concepts that sound slightly informal but are contextually correct\n"
        "- Spoken repetitions or fillers: 'old, old people', 'yeah, yeah', 'new new young people' (if intentional emphasis)\n"
        "- Quotes or phrases from other languages when explicitly discussing them (e.g., 'Ni hao ma')\n"
        "- Common software tools mentioned (e.g., 'Anki', 'GoldenDict', 'AnkiDec')\n"
        "- Teacher's teaching examples using vivid metaphors: 'throwing stone for fun', 'Buddhist fanatics', 'already those for the heart' (even if sounding slightly unusual)\n"
        "- Detailed anatomy or physiology in context: 'eye itself', 'brain and the nerves', 'oxygen and blood pressure' (standard teacher talk)\n"
        "- Teacher using common idioms even if slightly off: 'reach the bar', 'take the right view on board'\n"
        "- Informal speech errors: 'I a little bit do', 'kind of', 'like straight away'\n"
        "- Minor preposition/grammar errors: 'one of the way', 'move more on on their own'\n"
        "- Common non-Dhamma idioms or figures of speech: 'juicy', 'sign up for hell'\n"
        "- Valid statements containing unexpected analogies: 'the example with the lid', 'naked girl'\n"
        "- Garbled proper names of monastics or teachers in personal conversation "
        "(e.g., 'Bunty', 'Aspativa', 'Chipsy BD') — cannot be corrected without external knowledge; skip unless producing offensive content\n"
        "- Informal fillers and mechanical repetitions ('it's like', 'it's, it's', 'sort of', 'you know' — these are normal spoken speech)\n"
        "- Legitimate historical references to Suttas involving suicide (e.g. Godhika, Channa, Vakkali) and Sotapannas taking a life.\n"
        "- Everyday analogies and valid teaching examples using unexpected terms (e.g., 'motorbike race drivers', 'trolley problem / whole train go down', 'pierce your eyes with something sharp', 'intercourse with his wife', 'Russian girls', 'favorite dishes on the table', 'stone smell').\n"
        "- Microsoft Teams references ('in teams', 'sharing in teams') when discussing public speaking, teaching, or meetings.\n"
        "- Grammar errors characteristic of casual spoken English (e.g. 'the commentary quite is wrong', 'with 15' instead of 'at 15').\n"
        "- Valid terms spelled slightly off by the teacher or transcriber that are still fully understandable (e.g., 'ottappa', 'hiri', 'saṃsāra nirodha').\n"
        "- Stylistic preferences or phrasing you would improve\n"
        "- Any passage where the intended meaning is recoverable, even if informal\n\n"
        "CRITICAL RULE: The problematic word or phrase MUST appear verbatim in your quoted passage. "
        "Do not quote surrounding context and then describe an error that is not visible in that quote. "
        "If you cannot quote the exact wrong word, do not flag it.\n\n"
        "DO FLAG:\n"
        "- Offensive English word substitutions for Pali/Buddhist terms (HIGH PRIORITY) (e.g., 'Nigger Heater' for 'Niggahīta', 'boobies' for 'Buddhists')\n"
        "- Duplicate word errors ('the the', 'unless Unless', 'from from' — mechanical Whisper errors)\n"
        "- Adjective-noun phonetic confusions ('neural' for 'neutral', 'cleaning' for 'clinging', 'destruction' for 'distraction')\n"
        "- Common English word substituted for unrelated common word ('charter' for 'matter', 'in Guinea' for 'in general', 'marriage' for 'merit')\n"
        "- Common English phonetic confusions contextually wrong (e.g., 'chimes' where 'themes' in 'Dhamma talk is a lot of chimes', 'teeth' where 'deaf' in 'don't want to be teeth', 'in teams' where 'in temples')\n"
        "- Systematic Pali garbles in paṭicca-samuppāda (dependent origination) context: 'pasta', 'Pasa', 'Paso' all garble 'phassa' (contact)\n"
        "- Spelling garbles of Pali words: 'Nikahaya' for 'Nikaya' (collection of suttas), 'Scylla' for 'sila' (ethical conduct)\n"
        "- English idiom substitutions (e.g., 'drink of soul' for 'grain of salt', 'in teams' for 'in temples')\n"
        "- Nonsense proper nouns that are clearly garbled names or terms (e.g. 'Chipsy Biddy', 'double-dog', 'Raffole' for a bhikkhu name)\n"
        "- English words substituted for Pali terms where the mismatch is obvious (e.g. 'epidemic' for 'Abhidhamma', 'ati-sealers' for 'ati-sīla')\n"
        "- Pāṭimokkha recitation garbles: Pali chanting passages that are partially recognizable but malformed (e.g., 'Tanthavaye', 'Hichivaram', 'Equd desu')\n"
        "- A word from an unrelated domain that could not plausibly belong (e.g. 'Russian canon', 'greenhouse practice', 'police' where a practitioner was meant)\n"
        "- Specific phonetic substitutions found in recent sessions: 'Vajitya' -> 'Pācittiya', 'comedies' -> 'commentaries', 'Wollni-Rodasama-Badhi' -> 'Nirodhasamāpatti', 'sudden funny' -> 'sudden paññā', 'basic zhila' -> 'basic sīla', 'a pekha' -> 'upekkhā', 'destruction of the Danes' -> 'destruction of the taints', 'tight edition' -> 'Thai tradition', 'avi hinse and metta chitena' -> 'avihiṃsā and mettā cittena', 'bad comer' -> 'bad kamma', 'my matter is linked' -> 'my mettā is linked', 'Consume your offense' -> 'Confess your offense', 'maggapāla' -> 'magga-phala', 'viniana, plasna, marupa' -> 'viññāṇa, phassa, nāmarūpa', 'Ragado Samocha' -> 'rāga dosa moha', 'Hamanah' -> 'amoha', 'a coupon takeable' -> 'akuppa', 'world-instryment' -> 'stream-enterer', 'once eternal' -> 'once-returner', 'not eternal' -> 'non-returner', 'Samirjana' -> 'saṃyojana', 'Khochangas' -> 'bojjhaṅgas', 'vineyards' -> 'Vinaya', 'Sulta' -> 'sutta', 'sunnyabedaita new order after dance' -> 'saññāvedayitanirodha attainment', 'Banchu, Badana, Kanta' -> 'pañcupādānakkhandhā', 'firehounds' -> 'five hindrances', 'A witcher is not a jeta-seeker' -> 'avijjā is not a cetasika', 'Babanjshir' -> 'papañca', 'Brahman with Har' -> 'Brahmavihāra', 'vulnerable truth' -> 'noble truth', 'Noble Ethel Path' -> 'Noble Eightfold Path', 'Melinda-pan' -> 'Milindapañha', 'the parallel agree' -> 'the parallels agree', 'essential pleasure' -> 'sensual pleasure', 'Nikita, virāga' -> 'nibbidā, virāga', 'commonastics' -> 'co-monastics', 'Soma Nasa' -> 'somanassa', 'Pamoja or Pity' -> 'pāmojja or pīti', 'Patsambaya Chitta Sankara' -> 'paṭippassambhayaṃ cittasaṅkhāraṃ', 'saññā, anicca, samaṅkhara' -> 'saññā, anicca, saṅkhāra', 'Batshana objects' -> 'vipassanā objects', 'Angudra Nika 8' -> 'Aṅguttara Nikāya 8', 'Adjah, I'm Rupasani, Eko, Bahidha, Rupani' -> 'Ajjhattaṃ rūpasaññī eko bahiddhā rūpāni', 'Bhikkupa di Mokra' -> 'Bhikkhu Pāṭimokkha', 'elayed by' -> 'allayed by', 'comic result' -> 'karmic result', 'the reparker of' -> 'the vipāka of', 'Paṭinissaggiya Nupassā' -> 'paṭinissaggānupassanā', 'Noble Ethical Paths' -> 'Noble Eightfold Path', 'abandonment of finances' -> 'abandonment of hindrances', 'Evang Samayana' -> 'Evaṃ samaye', 'Pohanga site' -> 'bhavaṅga state', 'Bavanga' -> 'bhavaṅga', 'Maggots? The Maggots?' -> 'Maggots?', 'it's a suba' -> 'asubha', 'super class' -> 'sutta class', 'attach the car' -> 'karma', 'iron today' -> 'items today', 'patama jano' -> 'paṭhama jhāna', 'chakra and the ruba' -> 'cakkhu and the rūpa', 'dropping the ass of us' -> 'dropping the āsavas', 'domanus' -> 'domanassa', 'nature of punishing' -> 'nature of vanishing', 'the bastards' -> 'the best', 'Sisi also' -> 'CC'd', 'Dhamma gods' -> 'Dhamma talks', 'not subject to clean' -> 'clinging', 'kiryotapa' -> 'hiri-ottappa'\n"
        "- Numeric units garbled: 'five cents' for 'five senses', '5 hours' for '5 years' in monastic context\n"
        "- Preposition/word-order errors: 'on the war' for 'in the war', 'on the war actually' instead of proper phrasing\n"
        "- Multi-syllable phonetic collapse of doctrinal terms: 'completion nation' for 'complete cessation' (critical for understanding Nibbāna doctrine)\n"
        "- Person-role substitutions: 'serve the market' for 'serve the monk', commercial/retail terms replacing monastic roles\n\n"
        "KNOWN ERROR PATTERNS (examples of what Whisper does):\n"
        "- 'winner' where 'Vinaya' was intended\n"
        "- 'vagina' where 'paññā' was intended\n"
        "- 'epidemic' where 'Abhidhamma' was intended\n"
        "- 'red cock noise' where 'recognition' was intended\n"
        "- 'Russian canon' where 'Theravada canon' was intended\n"
        "- 'ati-sealers' where 'ati-sīla' was intended\n"
        "- 'greenhouse practice' where a Vinaya practice term was intended\n"
        "- 'in teams' where 'in temples' was intended\n"
        "- 'tomatok' where 'Dhamma talk' was intended\n"
        "- 'motor dummy car' where 'Moti Dhammika' (monastic name) was intended\n"
        "- 'cheetah is sauter' where 'citta is sa-uttara' was intended\n"
        "- 'sautra' where 'sa-uttara' was intended\n"
        "- 'Yana' where 'ñāṇa' was intended\n"
        "- 'chimes' where 'themes' in Dhamma talk context\n"
        "- 'teeth' where 'deaf' in sense faculty discussion\n"
        "- Duplicate word errors: 'the the eye' → 'the eye', 'unless Unless' → 'unless'\n"
        "- Adjective confusions: 'neural feeling' → 'neutral feeling', 'cleaning aggregates' → 'clinging aggregates'\n"
        "- Semantic substitutions: 'charter' → 'matter', 'in Guinea' → 'in general', 'marriage' → 'merit', 'destruction' → 'distraction'\n"
        "- Numeric garbles: 'five cents' → 'five senses', '5 hours' (monastic tenure) → '5 years', 'three performances' → 'three jhāna factors'\n"
        "- Phonetic name substitutions: 'Nigger Heater' → 'Niggāhita', 'boobies' → 'Buddhists'\n"
        "- Pali term garbles in dependent origination: 'pasta', 'Pasa', 'Paso' → 'phassa' (contact), 'Nikahaya' → 'Nikaya'\n"
        "- Pali conduct term: 'Scylla' → 'sila' (ethical conduct)\n"
        "- English idiom garbles: 'drink of soul' → 'grain of salt', 'from the storm' → 'from the store'\n"
        "- Preposition errors: 'on the war' → 'in the war'\n"
        "- Doctrine-critical multi-syllable collapse: 'completion nation' → 'complete cessation' (about Nibbāna)\n"
        "- Person-role substitution: 'serve the market' → 'serve the monk'\n"
        "  'matter' → 'merit' (puñña) in merit-sharing (anumodanā) contexts\n"
        "  'science' → 'sense' in compounds ('science base' → 'sense base', 'science space' → 'sense space')\n"
        "  'spaces' → 'sense bases' in āyatana passages\n"
        "  'sultans' → 'suttas' (collection of discourses)\n"
        "  'bowel' → 'walking' (in 'walking meditation')\n"
        "  'fall' → 'flame' (in fire-simile and tetralemma contexts)\n"
        "  'Doza' → 'Dosa' (aversion/hatred, one of the three defilements)\n"
        "  'chair-seekers' → 'cetasikas' (mental factors)\n"
        "  'pasta', 'Pasa', 'Paso' → 'phassa' (contact; already listed)\n"
        "  'Chandra' → 'chanda' (desire/intention/aspiration; Whisper confuses moon-god for Pali term)\n"
        "  'Untrius' → 'indriya' (sense faculty; Whisper garbles indriya)\n"
        "  'teams' → 'temples' (in monastery logistics/visiting contexts; phonetic swap)\n"
        "  'samica' → 'sāmīci' (proper Vinaya procedure; common garble)\n"
        "  'dogma nasa' → 'domanassa' (mental pain/grief; phonetic garble of Pali term for mental suffering)\n"
        "  'pommodra' → 'pāmojja' (gladness/delight preceding pīti in jhāna path)\n"
        "  'digam' → 'dīghaṃ', 'rasam' → 'rassaṃ' (long and short breath in ānāpānasati meditation)\n"
        "  'winner' → 'minor' (phonetic Whisper swap, especially in monastery discussion contexts)\n"
        "  'Asitta Bari word' → 'Asitta Bari, which'\n"
        "  'anti-dex' → 'Anki decks'\n"
        "  'late few people' → 'a few late people'\n"
        "  'jigong' → 'qigong'\n"
        "  'not a dumb area' → 'not a donor area' (monastic career context)\n"
        "  'Nipida' → 'Nibbida'\n"
        "  'going to the bath' → 'going to the Buddha'\n"
        "  'nomanity' → 'nominality'\n"
        "  'Pikkupati Mokka' → 'Pāṭimokkha'\n"
        "  'Taman dog' → 'Dhamma talk'\n"
        "  'eye contact' → 'eye consciousness' (sense faculty discussion)\n"
        "  'Sgt. Brahms' → 'Ajahn Brahm'\n"
        "  'Hianapanasati' → 'Anapanasati'\n"
        "  'Insara in BMC' → 'In the BMC' (reference to Buddhist Monastic Code)\n"
        "  'super junior monkey' → 'super junior monk'\n"
        "  'Melinda Banger' → 'Milindapañha'\n"
        "  'Hattiputam mantis' → 'Hatthipadopama Sutta'\n"
        "  'Sanyavede Eta Neuroda' → 'Saññāvedayitanirodha'\n"
        "  'Ganyanca' → 'Goenka'\n"
        "  'the Marlava' → 'the Mahā-vagga'\n"
        "  'khani' → 'karaṇīya'\n"
        "  'Rapola' → 'Walpola' (famous monk name)\n"
        "  'chivalry' → 'cīvara' (phonetic garble for robe)\n"
        "  'New Year's Day person' → 'layperson'\n"
        "  'Wapan Manachai' → 'Wat Pa Nanachat' (monastery name)\n"
        "  'economist' → 'equanimous' (phonetic garble for equanimity state)\n"
        "  'Barok' / 'Baok' → 'Pa-Auk' (Burmese forest monastery)\n"
        "  'Tzuta' → 'sutta' (alternative pronunciation garble)\n"
        "  'power' → 'bhava' (when bhava already appears nearby in same sentence; contextual substitution)\n"
        "  'atanham' → 'kammaṭṭhāna' (meditation base; ṭṭhāna suffix garbled)\n"
        "  'Narupa' → 'nāmarūpa' (mind-and-form)\n"
        "  'ñāṇa' → 'viññāṇa' (consciousness; vi- prefix dropped by Whisper)\n"
        "  'worse' → 'worth' (phonetic swap; 'it's worse bringing up' → 'it's worth bringing up')\n"
        "  'observed' → 'absorbed' (phonetic swap in meditation context)\n"
        "  'exhibition' → 'exposition' (phonetic swap for Dhamma teaching)\n"
        "  'report' → 'retreat' (phonetic swap in meditation context)\n"
        "  'Kilaama' → 'Kālāma' (famous Kālāma Sutta)\n"
        "  'sharing my mind' → 'sharing my merit' (anumodanā context)\n"
        "  'winner issue' → 'Vinaya issue' (monastic discipline context)\n"
        "  'terrible with the cheetah' → 'interview with the teacher' (phonetic collapse)\n"
        "  'preparation for the dog' → 'preparation for the talk' (phonetic swap)\n"
        "  'Nyad-Locus police dictionary' → 'Nyanatiloka\\'s Pali dictionary' (famous reference)\n"
        "  'touchables' → 'tangibles' (sense faculty discussion)\n"
        "  'divide our departed relatives' → 'invite our departed relatives' (sharing merit context)\n"
        "  'OPEC complete' → 'upekkhā' (equanimity; multi-syllable collapse)\n"
        "  'picky sugar' → 'pīti sukha' (joy and bliss; phonetic collapse)\n"
        "  'Untrius' → 'indriyas' (sense faculties; phonetic garble)\n"
        "  'nitchia with the chakai' → 'anicca with the cakkhu' (impermanence of the eye; phonetic collapse)\n"
        "  'sub-kirkus' → 'sabbakāya' (all-body; phonetic collapse in ānāpānasati)\n"
        "  'J.P.S.I.K.A.' → 'cetasika' (mental factors; extreme phonetic hallucination)\n"
        "  'pommodra' → 'pāmojja' (gladness; phonetic garble)\n"
        "  'white person\\'s house' → 'lay person\\'s house' (monastic context; avoids racial hallucination)\n"
        "  'mental sex' → 'mental acts' (manokamma)\n"
        "  'trendy' → 'tranquil' (passaddhi)\n"
        "  'Bodjanga', 'Pochangas', 'Bojangga', 'Bojanga', 'Bohanga', 'Bojhunga', 'Bodhanga' → 'Bojjhaṅga'\n"
        "  'immense product' → 'by-product'\n"
        "  'past life aggregation' → 'past life regression'\n"
        "  'Badaya Gacitta' → 'Bhante Aggacitta'\n"
        "  'good comma' → 'good kamma'\n"
        "  'self-matter' → 'self-mettā'\n"
        "  'star for person' → 'standard for a person'\n"
        "  'fema' → 'pema' (love/affection)\n"
        "  'Maniety' / 'Maniti' → 'maññanā' (conceit/imagining)\n"
        "  'a Miami' → 'mine'\n"
        "  'the Pekka-sams' → 'upekkhā-sambojjhaṅgas'\n"
        "  'chatur matura' → 'catumadhura'\n"
        "  'balls' → 'bowls' (alms bowls)\n"
        "  'mechopatic' → 'metaphoric'\n"
        "  'word Bara' → 'word bala'\n"
        "  'pure mocha' → 'pure moha'\n"
        "  'damage area' → 'Dhamma sharing'\n"
        "  'Amu Savada' → 'musāvāda'\n"
        "  'very Sacca' → 'vīriya, sacca'\n\n"
        "If in doubt, return []. A missed error is far better than a false positive.\n"
        "OUTPUT: Return ONLY a valid JSON array. Each item must have exactly these keys:\n"
        '  {"passage": "exact verbatim quote from the text", "issue": "why this must be a Whisper error", "suggestion": "what was probably intended"}\n'
        "Return an empty array [] if nothing is clearly wrong. No other text outside the JSON."
    )
