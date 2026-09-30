#!/usr/bin/env python3
"""Convert raw KsponSpeech CP949 transcripts into the project's 34-phone IPA.

Audio remains in its original 16 kHz, mono, signed 16-bit little-endian PCM
form. Allosaurus reads the PCM directly, avoiding a second copy of the audio.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import unicodedata
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
NLTK_DATA_DIR = PROJECT_ROOT / ".nltk_data"
INVENTORY_PATH = PROJECT_ROOT / "configs/inventories/kspon_korean_ipa.txt"

DUAL_TRANSCRIPTION = re.compile(r"\(([^()]*)\)/\(([^()]*)\)")
NOISE_MARKER = re.compile(r"(?<!\S)[obnlu]/(?=\s|$)", re.IGNORECASE)
ASCII_LETTERS = re.compile(r"[A-Za-z]+")

LETTER_NAMES = {
    "A": "에이", "B": "비", "C": "씨", "D": "디", "E": "이",
    "F": "에프", "G": "지", "H": "에이치", "I": "아이", "J": "제이",
    "K": "케이", "L": "엘", "M": "엠", "N": "엔", "O": "오",
    "P": "피", "Q": "큐", "R": "알", "S": "에스", "T": "티",
    "U": "유", "V": "브이", "W": "더블유", "X": "엑스", "Y": "와이",
    "Z": "제트",
}

ONSET_TO_IPA = {
    "ᄀ": ("k",), "ᄁ": ("k͈",), "ᄂ": ("n",), "ᄃ": ("t",),
    "ᄄ": ("t͈",), "ᄅ": ("ɾ",), "ᄆ": ("m",), "ᄇ": ("p",),
    "ᄈ": ("p͈",), "ᄉ": ("s",), "ᄊ": ("s͈",), "ᄋ": (),
    "ᄌ": ("tɕ",), "ᄍ": ("tɕ͈",), "ᄎ": ("tɕʰ",),
    "ᄏ": ("kʰ",), "ᄐ": ("tʰ",), "ᄑ": ("pʰ",), "ᄒ": ("h",),
}
VOWEL_TO_IPA = {
    "ᅡ": ("a",), "ᅢ": ("e",), "ᅣ": ("j", "a"),
    "ᅤ": ("j", "e"), "ᅥ": ("ʌ",), "ᅦ": ("e",),
    "ᅧ": ("j", "ʌ"), "ᅨ": ("j", "e"), "ᅩ": ("o",),
    "ᅪ": ("w", "a"), "ᅫ": ("w", "e"), "ᅬ": ("w", "e"),
    "ᅭ": ("j", "o"), "ᅮ": ("u",), "ᅯ": ("w", "ʌ"),
    "ᅰ": ("w", "e"), "ᅱ": ("w", "i"), "ᅲ": ("j", "u"),
    "ᅳ": ("ɯ",), "ᅴ": ("ɯ", "i"), "ᅵ": ("i",),
}
CODA_TO_IPA = {
    "ᆨ": ("k̚",), "ᆩ": ("k̚",), "ᆪ": ("k̚",), "ᆫ": ("n",),
    "ᆬ": ("n",), "ᆭ": ("n",), "ᆮ": ("t̚",), "ᆯ": ("l",),
    "ᆰ": ("k̚",), "ᆱ": ("m",), "ᆲ": ("l",), "ᆳ": ("l",),
    "ᆴ": ("l",), "ᆵ": ("p̚",), "ᆶ": ("l",), "ᆷ": ("m",),
    "ᆸ": ("p̚",), "ᆹ": ("p̚",), "ᆺ": ("t̚",), "ᆻ": ("t̚",),
    "ᆼ": ("ŋ",), "ᆽ": ("t̚",), "ᆾ": ("t̚",), "ᆿ": ("k̚",),
    "ᇀ": ("t̚",), "ᇁ": ("p̚",), "ᇂ": ("t̚",),
}
PALATAL_VOWELS = {"ᅵ", "ᅣ", "ᅤ", "ᅧ", "ᅨ", "ᅭ", "ᅲ"}

_G2P = None


def normalize_transcript(text: str) -> str:
    """Remove KsponSpeech annotation while retaining the spoken alternative."""
    text = unicodedata.normalize("NFC", text.replace("\r", " ").replace("\n", " "))
    previous = None
    while previous != text:
        previous = text
        text = DUAL_TRANSCRIPTION.sub(lambda match: match.group(2) or match.group(1), text)
    text = NOISE_MARKER.sub(" ", text)
    text = text.replace("/", " ").replace("+", " ").replace("*", " ")
    # g2pK leaves ASCII initialisms such as KFC, SKT, VIP and DC untouched.
    # Spell them as Korean letter names so the Hangul-only IPA conversion can
    # retain their spoken content instead of dropping the entire utterance.
    text = ASCII_LETTERS.sub(
        lambda match: " " + " ".join(LETTER_NAMES[letter] for letter in match.group().upper()) + " ",
        text,
    )

    cleaned = []
    for character in text:
        category = unicodedata.category(character)
        if character.isspace() or character.isalnum() or "HANGUL" in unicodedata.name(character, ""):
            cleaned.append(character)
        elif category.startswith(("P", "S")):
            cleaned.append(" ")
        else:
            cleaned.append(" ")
    return " ".join("".join(cleaned).split())


def _decompose_syllable(character: str) -> tuple[str, str, str | None]:
    offset = ord(character) - 0xAC00
    if offset < 0 or offset >= 11172:
        raise ValueError(f"not a modern Hangul syllable: {character!r}")
    onset_index = offset // 588
    vowel_index = (offset % 588) // 28
    coda_index = offset % 28
    onset = chr(0x1100 + onset_index)
    vowel = chr(0x1161 + vowel_index)
    coda = chr(0x11A7 + coda_index) if coda_index else None
    return onset, vowel, coda


def pronunciation_to_ipa(pronunciation: str) -> list[str]:
    phones: list[str] = []
    for character in pronunciation:
        if character.isspace():
            continue
        onset, vowel, coda = _decompose_syllable(character)
        if onset == "ᄉ" and vowel in PALATAL_VOWELS:
            phones.append("ɕ")
        elif onset == "ᄊ" and vowel in PALATAL_VOWELS:
            phones.append("ɕ͈")
        else:
            phones.extend(ONSET_TO_IPA[onset])
        phones.extend(VOWEL_TO_IPA[vowel])
        if coda:
            phones.extend(CODA_TO_IPA[coda])
    return phones


def get_g2p():
    global _G2P
    if _G2P is None:
        import nltk

        nltk.data.path.insert(0, str(NLTK_DATA_DIR))
        from g2pk import G2p

        _G2P = G2p()
    return _G2P


def process_one(task: tuple[str, str, bool]) -> dict[str, str]:
    source_string, output_string, overwrite = task
    source = Path(source_string)
    output = Path(output_string)
    if output.exists() and not overwrite:
        return {"status": "skipped", "source": source_string}
    try:
        transcript = source.read_text(encoding="cp949")
        normalized = normalize_transcript(transcript)
        if not normalized:
            raise ValueError("transcript is empty after annotation normalization")
        pronunciation = get_g2p()(normalized)
        phones = pronunciation_to_ipa(pronunciation)
        inventory = set(INVENTORY_PATH.read_text(encoding="utf-8").split())
        unsupported = sorted(set(phones) - inventory)
        if unsupported:
            raise ValueError(f"unsupported IPA phones: {unsupported}")
        if not phones:
            raise ValueError("G2P produced an empty phone sequence")

        output.parent.mkdir(parents=True, exist_ok=True)
        temporary = output.with_name(f".{output.name}.tmp-{os.getpid()}")
        temporary.write_text(" ".join(phones) + "\n", encoding="utf-8")
        temporary.replace(output)
        return {"status": "processed", "source": source_string}
    except Exception as exc:  # Keep a complete failure report for a large run.
        return {"status": "error", "source": source_string, "error": str(exc)}


def collect_tasks(roots: list[Path], output_root: Path, overwrite: bool) -> list[tuple[str, str, bool]]:
    tasks = []
    for root in roots:
        pcm_paths = sorted(path for path in root.rglob("*.pcm") if path.is_file())
        txt_paths = {path.relative_to(root).with_suffix(""): path for path in root.rglob("*.txt") if path.is_file()}
        for pcm_path in pcm_paths:
            key = pcm_path.relative_to(root).with_suffix("")
            source = txt_paths.get(key)
            if source is None:
                raise ValueError(f"missing transcript for {pcm_path}")
            output = output_root / root.name / key.with_suffix(".txt")
            tasks.append((str(source), str(output), overwrite))
        pcm_keys = {path.relative_to(root).with_suffix("") for path in pcm_paths}
        extra_labels = sorted(set(txt_paths) - pcm_keys)
        if extra_labels:
            raise ValueError(f"{root}: transcript without PCM: {extra_labels[0]}")
    return tasks


def main() -> int:
    parser = argparse.ArgumentParser(description="Preprocess raw KsponSpeech PCM/CP949 pairs into UTF-8 IPA labels")
    parser.add_argument("roots", nargs="+", type=Path)
    parser.add_argument("--output-root", required=True, type=Path)
    parser.add_argument("--workers", type=int, default=min(8, os.cpu_count() or 1))
    parser.add_argument("--limit", type=int, default=0, help="process only the first N pairs for smoke testing")
    parser.add_argument("--overwrite", action="store_true")
    args = parser.parse_args()

    try:
        tasks = collect_tasks(args.roots, args.output_root, args.overwrite)
    except ValueError as exc:
        parser.error(str(exc))
    if args.limit:
        tasks = tasks[: args.limit]

    counts = {"processed": 0, "skipped": 0, "error": 0}
    errors = []
    with ProcessPoolExecutor(max_workers=args.workers) as executor:
        for index, result in enumerate(executor.map(process_one, tasks, chunksize=16), start=1):
            counts[result["status"]] += 1
            if result["status"] == "error":
                errors.append(result)
            if index % 1000 == 0 or index == len(tasks):
                print(f"{index}/{len(tasks)} processed={counts['processed']} skipped={counts['skipped']} errors={counts['error']}", flush=True)

    summary = {"roots": [str(path.resolve()) for path in args.roots], "total": len(tasks), "counts": counts, "errors": errors}
    args.output_root.mkdir(parents=True, exist_ok=True)
    (args.output_root / "preprocess_summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
