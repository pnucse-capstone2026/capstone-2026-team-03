import sys
from functools import lru_cache

from django.conf import settings

from .ipa_variants import build_ipa_variants


class SentenceIpaError(Exception):
    pass


@lru_cache(maxsize=1)
def _converter():
    allosaurus_root = settings.ALLOSAURUS_ROOT
    if not allosaurus_root.exists():
        raise SentenceIpaError(f"Allosaurus 경로를 찾을 수 없습니다: {allosaurus_root}")
    root = str(allosaurus_root)
    if root not in sys.path:
        sys.path.insert(0, root)
    try:
        from scripts.preprocess_kspon_pcm import (  # noqa: PLC0415
            INVENTORY_PATH,
            get_g2p,
            normalize_transcript,
            pronunciation_to_ipa,
        )
    except Exception as exc:
        raise SentenceIpaError("문장 IPA 변환기를 불러오지 못했습니다.") from exc
    inventory = set(INVENTORY_PATH.read_text(encoding="utf-8").split())
    return {
        "g2p": get_g2p(),
        "inventory": inventory,
        "normalize_transcript": normalize_transcript,
        "pronunciation_to_ipa": pronunciation_to_ipa,
    }


def build_sentence_ipa(text):
    cleaned = " ".join(str(text or "").strip().split())
    if not cleaned:
        raise SentenceIpaError("문장을 입력해 주세요.")

    converter = _converter()
    normalize_transcript = converter["normalize_transcript"]
    pronunciation_to_ipa = converter["pronunciation_to_ipa"]
    normalized = normalize_transcript(cleaned)
    pronunciation = converter["g2p"](normalized)
    phones = pronunciation_to_ipa(pronunciation)
    unsupported = sorted(set(phones) - converter["inventory"])
    if unsupported:
        raise SentenceIpaError(f"지원하지 않는 IPA 기호가 포함되어 있습니다: {', '.join(unsupported)}")

    source_words = normalized.split()
    pronunciation_words = pronunciation.split()
    if len(source_words) != len(pronunciation_words):
        raise SentenceIpaError("문장 단어와 발음 단어 수가 달라 IPA 위치를 만들 수 없습니다.")

    rebuilt = []
    word_spans = []
    for source_word, pronunciation_word in zip(source_words, pronunciation_words, strict=True):
        word_phones = pronunciation_to_ipa(pronunciation_word)
        start = len(rebuilt)
        rebuilt.extend(word_phones)
        word_spans.append(
            _build_word_span(
                source_word=source_word,
                pronunciation_word=pronunciation_word,
                word_phones=word_phones,
                start=start,
                pronunciation_to_ipa=pronunciation_to_ipa,
            )
        )
    if rebuilt != phones:
        raise SentenceIpaError("문장 IPA와 단어별 IPA 위치가 일치하지 않습니다.")

    ipa_variants = build_ipa_variants(
        normalized_text=normalized,
        standard_pronunciation=pronunciation,
        pronunciation_to_ipa=pronunciation_to_ipa,
        inventory=converter["inventory"],
    )

    return {
        "normalized_text": normalized,
        "g2p_pronunciation": pronunciation,
        "cached_ipa": phones,
        "cached_ipa_variants": ipa_variants,
        "word_spans": word_spans,
    }


def enrich_word_spans(text, cached_ipa=None, word_spans=None):
    """Return word spans with per-syllable IPA ranges.

    Older DB rows only have word-level spans.  The frontend needs syllable-level
    ranges so an error at a target IPA position can highlight the exact Hangul
    syllable, e.g. 좋/네/요 rather than the whole word.
    """
    fallback = word_spans or []
    try:
        converter = _converter()
        normalize_transcript = converter["normalize_transcript"]
        pronunciation_to_ipa = converter["pronunciation_to_ipa"]
        normalized = normalize_transcript(text)
        pronunciation = converter["g2p"](normalized)
        source_words = normalized.split()
        pronunciation_words = pronunciation.split()
        if len(source_words) != len(pronunciation_words):
            return fallback

        rebuilt = []
        enriched = []
        for source_word, pronunciation_word in zip(source_words, pronunciation_words, strict=True):
            word_phones = pronunciation_to_ipa(pronunciation_word)
            start = len(rebuilt)
            rebuilt.extend(word_phones)
            enriched.append(
                _build_word_span(
                    source_word=source_word,
                    pronunciation_word=pronunciation_word,
                    word_phones=word_phones,
                    start=start,
                    pronunciation_to_ipa=pronunciation_to_ipa,
                )
            )
        if cached_ipa and list(cached_ipa) != rebuilt:
            return _merge_syllables_into_existing_spans(
                existing_spans=fallback,
                enriched_spans=enriched,
            )
        return enriched
    except Exception:
        return fallback


def _build_word_span(*, source_word, pronunciation_word, word_phones, start, pronunciation_to_ipa):
    syllables = _build_syllable_spans(
        source_word=source_word,
        pronunciation_word=pronunciation_word,
        word_phones=word_phones,
        word_start=start,
        pronunciation_to_ipa=pronunciation_to_ipa,
    )
    return {
        "word": source_word,
        "pronunciation": pronunciation_word,
        "ipa": word_phones,
        "start": start,
        "end": start + len(word_phones),
        "syllables": syllables,
    }


def _build_syllable_spans(
    *, source_word, pronunciation_word, word_phones, word_start, pronunciation_to_ipa
):
    source_chars = list(source_word)
    pronunciation_chars = list(pronunciation_word)
    if not source_chars:
        return []

    if len(source_chars) == len(pronunciation_chars):
        syllables = []
        cursor = word_start
        for source_char, pronunciation_char in zip(
            source_chars, pronunciation_chars, strict=True
        ):
            phones = pronunciation_to_ipa(pronunciation_char)
            syllables.append(
                {
                    "text": source_char,
                    "pronunciation": pronunciation_char,
                    "ipa": phones,
                    "start": cursor,
                    "end": cursor + len(phones),
                }
            )
            cursor += len(phones)
        if cursor == word_start + len(word_phones):
            return syllables

    return _fallback_syllable_spans(source_chars, word_phones, word_start)


def _fallback_syllable_spans(source_chars, word_phones, word_start):
    syllables = []
    count = len(source_chars)
    total = len(word_phones)
    for index, source_char in enumerate(source_chars):
        start = word_start + round(total * index / count)
        end = word_start + round(total * (index + 1) / count)
        syllables.append(
            {
                "text": source_char,
                "pronunciation": "",
                "ipa": word_phones[start - word_start : end - word_start],
                "start": start,
                "end": end,
            }
        )
    return syllables


def _merge_syllables_into_existing_spans(*, existing_spans, enriched_spans):
    if not existing_spans:
        return enriched_spans
    by_word = {}
    for span in enriched_spans:
        by_word.setdefault(span.get("word"), []).append(span)
    merged = []
    for index, span in enumerate(existing_spans):
        candidates = by_word.get(span.get("word"), [])
        enriched = candidates.pop(0) if candidates else None
        if not enriched:
            merged.append(span)
            continue
        offset = int(span.get("start", 0)) - int(enriched.get("start", 0))
        syllables = [
            {
                **syllable,
                "start": int(syllable.get("start", 0)) + offset,
                "end": int(syllable.get("end", 0)) + offset,
            }
            for syllable in enriched.get("syllables", [])
        ]
        merged.append({**span, "pronunciation": enriched.get("pronunciation", ""), "syllables": syllables})
    return merged
