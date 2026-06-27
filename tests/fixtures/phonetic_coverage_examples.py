# Fixtures for testing enforce_phonetic_coverage_rule().
# Each entry: (passage, suggestion, expected_result)
# expected_result: "keep" = should remain TP-fix, "downgrade" = should be TP-defer

PHONETIC_EXAMPLES: list[tuple[str, str, str]] = [
    # Clear single-word fixes — must KEEP
    ("pasta", "→ 'vassa'", "keep"),
    ("bunny", "→ 'money'", "keep"),
    ("tight edition", "→ 'Thai tradition'", "keep"),
    # Clear inventions — must DOWNGRADE
    ("going to be honest", "→ 'mano, viññāṇa'", "downgrade"),
    (
        "establishing your top one in the back car",
        "→ 'tatra-majjhattatā'",
        "downgrade",
    ),
    (
        "feature and humility knowledge rational knowledge of liberation",
        "→ 'vijjā and vimutti'",
        "downgrade",
    ),
    # Proper names — must KEEP
    ("bigger Buddha", "→ 'Bhikkhu Bodhi'", "keep"),
    ("near-the-clock police dictionary", '→ "Nyanatiloka\'s Pali dictionary"', "keep"),
    # Two-word phonetic match — must KEEP after fix
    ("Matematica 44", "→ 'Majjhima 44'", "keep"),
    # Borderline multi-word invention — must DOWNGRADE
    ("Odisha", "→ 'Vipassanā'", "downgrade"),
    ("leads to the Mali", "→ 'samadhi'", "downgrade"),
]
