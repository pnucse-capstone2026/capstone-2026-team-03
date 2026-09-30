"""Rule-based Korean IPA target variants.

The primary G2P output remains the canonical target.  These helpers add a
small, reproducible set of lenient targets for pronunciations that are still
intelligible but differ from the single standard-form IPA.
"""

from __future__ import annotations

MAX_IPA_VARIANTS = 8

HANGUL_BASE = 0xAC00
HANGUL_COUNT = 11172
ONSET_COUNT = 19
VOWEL_COUNT = 21
CODA_COUNT = 28

ONSET_HIEUH_INDEX = 18
ONSET_IEUNG_INDEX = 11
CODA_NONE_INDEX = 0
CODA_NIEUN_INDEX = 4
CODA_RIEUL_INDEX = 8
CODA_HIEUH_INDEX = 27
CODA_NIEUN_HIEUH_INDEX = 6
CODA_RIEUL_HIEUH_INDEX = 15

STOP_CODAS = {"k̚", "t̚", "p̚"}
TENSE_TO_PLAIN = {
    "k͈": "k",
    "t͈": "t",
    "p͈": "p",
    "s͈": "s",
    "tɕ͈": "tɕ",
}
NASAL_TRANSITION_BY_STOP = {
    "k̚": "ŋ",
    "p̚": "m",
}


def build_ipa_variants(
    *,
    normalized_text: str,
    standard_pronunciation: str,
    pronunciation_to_ipa,
    inventory: set[str],
    max_variants: int = MAX_IPA_VARIANTS,
) -> list[dict]:
    """Build validated IPA candidates ordered from strict to lenient.

    Candidate types:
    - standard g2pK pronunciation
    - orthographic/clear-speech reading
    - retained ㅎ before vowel, e.g. 좋아요 -> 조하요
    - local leniencies around tense consonants and nasal transitions
    """

    variants: list[dict] = []
    seen: set[tuple[str, ...]] = set()

    def add(label: str, ipa: list[str], *, pronunciation: str, rules: list[str]) -> None:
        if not ipa or len(variants) >= max_variants:
            return
        key = tuple(ipa)
        if key in seen:
            return
        if set(ipa) - inventory:
            return
        seen.add(key)
        variants.append(
            {
                "label": label,
                "pronunciation": pronunciation,
                "ipa": ipa,
                "rules": rules,
            }
        )

    standard_ipa = _safe_pronunciation_to_ipa(standard_pronunciation, pronunciation_to_ipa)
    add(
        "standard",
        standard_ipa,
        pronunciation=standard_pronunciation,
        rules=["standard_g2p"],
    )

    base_items = [("standard", standard_pronunciation, standard_ipa)]
    orthographic_ipa = _safe_pronunciation_to_ipa(normalized_text, pronunciation_to_ipa)
    if orthographic_ipa:
        add(
            "orthographic",
            orthographic_ipa,
            pronunciation=normalized_text,
            rules=["orthographic_reading"],
        )
        base_items.append(("orthographic", normalized_text, orthographic_ipa))

    for pronunciation in _h_retained_pronunciations(normalized_text):
        ipa = _safe_pronunciation_to_ipa(pronunciation, pronunciation_to_ipa)
        if ipa:
            add(
                "h_retained",
                ipa,
                pronunciation=pronunciation,
                rules=["h_retention_lenient"],
            )
            base_items.append(("h_retained", pronunciation, ipa))

    for base_label, pronunciation, base_ipa in base_items:
        for label, ipa, rules in _phone_level_variants(base_ipa, base_label=base_label):
            add(label, ipa, pronunciation=pronunciation, rules=rules)

    return variants


def ipa_sequences_from_variants(
    primary_ipa: list[str] | tuple[str, ...],
    variants: list | None,
) -> list[dict]:
    """Normalize mixed variant shapes into `{label, ipa, ...}` dictionaries."""

    normalized: list[dict] = []
    seen: set[tuple[str, ...]] = set()

    def add(label: str, ipa, extra: dict | None = None):
        if not isinstance(ipa, (list, tuple)) or not ipa:
            return
        phones = [str(phone) for phone in ipa if str(phone)]
        if not phones:
            return
        key = tuple(phones)
        if key in seen:
            return
        seen.add(key)
        normalized.append({"label": label, "ipa": phones, **(extra or {})})

    for index, variant in enumerate(variants or [], start=1):
        if isinstance(variant, dict):
            label = str(variant.get("label") or f"variant_{index}")
            extra = {
                key: variant[key]
                for key in ("pronunciation", "rules")
                if key in variant
            }
            add(label, variant.get("ipa"), extra)
        else:
            add(f"variant_{index}", variant)
    add("primary", primary_ipa)
    return normalized


def _phone_level_variants(ipa: list[str], *, base_label: str):
    if not ipa:
        return

    tense_positions = [
        index
        for index in range(len(ipa) - 1)
        if ipa[index] in STOP_CODAS and ipa[index + 1] in TENSE_TO_PLAIN
    ]
    for index in tense_positions:
        yield (
            f"{base_label}_weak_coda_before_tense",
            ipa[:index] + ipa[index + 1 :],
            ["weak_coda_before_tense", "tensification_context"],
        )
        relaxed = list(ipa)
        relaxed[index + 1] = TENSE_TO_PLAIN[relaxed[index + 1]]
        yield (
            f"{base_label}_relaxed_tensification",
            relaxed,
            ["relaxed_tensification", "tensification_context"],
        )
    if len(tense_positions) > 1:
        remove_positions = set(tense_positions)
        yield (
            f"{base_label}_weak_all_codas_before_tense",
            [phone for index, phone in enumerate(ipa) if index not in remove_positions],
            ["weak_coda_before_tense", "multiple_sites"],
        )

    for index in range(len(ipa) - 1):
        replacement = NASAL_TRANSITION_BY_STOP.get(ipa[index])
        if replacement and ipa[index + 1] == "n":
            adjusted = list(ipa)
            adjusted[index + 1] = replacement
            yield (
                f"{base_label}_nasal_place_transition",
                adjusted,
                ["nasal_place_transition", "lenient_assimilation"],
            )


def _safe_pronunciation_to_ipa(pronunciation: str, pronunciation_to_ipa) -> list[str]:
    if not _is_hangul_pronunciation(pronunciation):
        return []
    try:
        return pronunciation_to_ipa(pronunciation)
    except Exception:
        return []


def _is_hangul_pronunciation(value: str) -> bool:
    if not value:
        return False
    for character in value:
        if character.isspace():
            continue
        if not _is_hangul_syllable(character):
            return False
    return True


def _h_retained_pronunciations(text: str) -> list[str]:
    """Return lenient spellings where coda ㅎ is carried to a following vowel."""

    pronunciations = []
    characters = list(text)
    for index in range(len(characters) - 1):
        current = characters[index]
        following = characters[index + 1]
        if not (_is_hangul_syllable(current) and _is_hangul_syllable(following)):
            continue
        current_parts = _decompose(current)
        following_parts = _decompose(following)
        if following_parts["onset"] != ONSET_IEUNG_INDEX:
            continue
        replacement_coda = {
            CODA_HIEUH_INDEX: CODA_NONE_INDEX,
            CODA_NIEUN_HIEUH_INDEX: CODA_NIEUN_INDEX,
            CODA_RIEUL_HIEUH_INDEX: CODA_RIEUL_INDEX,
        }.get(current_parts["coda"])
        if replacement_coda is None:
            continue
        mutated = list(characters)
        mutated[index] = _compose(
            current_parts["onset"],
            current_parts["vowel"],
            replacement_coda,
        )
        mutated[index + 1] = _compose(
            ONSET_HIEUH_INDEX,
            following_parts["vowel"],
            following_parts["coda"],
        )
        candidate = "".join(mutated)
        if candidate != text:
            pronunciations.append(candidate)
    return pronunciations[:2]


def _is_hangul_syllable(character: str) -> bool:
    offset = ord(character) - HANGUL_BASE
    return 0 <= offset < HANGUL_COUNT


def _decompose(character: str) -> dict[str, int]:
    offset = ord(character) - HANGUL_BASE
    return {
        "onset": offset // (VOWEL_COUNT * CODA_COUNT),
        "vowel": (offset % (VOWEL_COUNT * CODA_COUNT)) // CODA_COUNT,
        "coda": offset % CODA_COUNT,
    }


def _compose(onset: int, vowel: int, coda: int) -> str:
    return chr(HANGUL_BASE + ((onset * VOWEL_COUNT) + vowel) * CODA_COUNT + coda)
