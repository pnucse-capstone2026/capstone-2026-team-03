from decimal import Decimal, ROUND_HALF_UP


def align_ipa(target_ipa, recognized_ipa):
    target = list(target_ipa)
    recognized = list(recognized_ipa)
    rows = len(target) + 1
    columns = len(recognized) + 1
    distances = [[0] * columns for _ in range(rows)]

    for target_index in range(rows):
        distances[target_index][0] = target_index
    for recognized_index in range(columns):
        distances[0][recognized_index] = recognized_index

    for target_index in range(1, rows):
        for recognized_index in range(1, columns):
            substitution_cost = 0 if target[target_index - 1] == recognized[recognized_index - 1] else 1
            distances[target_index][recognized_index] = min(
                distances[target_index - 1][recognized_index] + 1,
                distances[target_index][recognized_index - 1] + 1,
                distances[target_index - 1][recognized_index - 1] + substitution_cost,
            )

    alignment = []
    target_index = len(target)
    recognized_index = len(recognized)
    while target_index > 0 or recognized_index > 0:
        if (
            target_index > 0
            and recognized_index > 0
            and target[target_index - 1] == recognized[recognized_index - 1]
            and distances[target_index][recognized_index]
            == distances[target_index - 1][recognized_index - 1]
        ):
            alignment.append(
                {
                    "target_index": target_index - 1,
                    "target_phone": target[target_index - 1],
                    "recognized_phone": recognized[recognized_index - 1],
                    "operation": "match",
                }
            )
            target_index -= 1
            recognized_index -= 1
        elif (
            target_index > 0
            and recognized_index > 0
            and distances[target_index][recognized_index]
            == distances[target_index - 1][recognized_index - 1] + 1
        ):
            alignment.append(
                {
                    "target_index": target_index - 1,
                    "target_phone": target[target_index - 1],
                    "recognized_phone": recognized[recognized_index - 1],
                    "operation": "substitution",
                }
            )
            target_index -= 1
            recognized_index -= 1
        elif (
            target_index > 0
            and distances[target_index][recognized_index]
            == distances[target_index - 1][recognized_index] + 1
        ):
            alignment.append(
                {
                    "target_index": target_index - 1,
                    "target_phone": target[target_index - 1],
                    "recognized_phone": None,
                    "operation": "deletion",
                }
            )
            target_index -= 1
        else:
            alignment.append(
                {
                    "target_index": target_index,
                    "target_phone": None,
                    "recognized_phone": recognized[recognized_index - 1],
                    "operation": "insertion",
                }
            )
            recognized_index -= 1

    alignment.reverse()
    return distances[-1][-1], alignment


def pronunciation_score(target_ipa, recognized_ipa):
    if not target_ipa:
        raise ValueError("목표 IPA가 비어 있습니다.")

    distance, alignment = align_ipa(target_ipa, recognized_ipa)
    raw_score = max(0, (1 - distance / len(target_ipa)) * 100)
    score = Decimal(str(raw_score)).quantize(Decimal("0.1"), rounding=ROUND_HALF_UP)
    return score, alignment


def pronunciation_score_with_variants(target_ipa_variants, recognized_ipa):
    variants = _coerce_target_variants(target_ipa_variants)
    if not variants:
        raise ValueError("목표 IPA 후보가 비어 있습니다.")

    best = None
    for index, variant in enumerate(variants):
        target_ipa = variant["ipa"]
        distance, alignment = align_ipa(target_ipa, recognized_ipa)
        raw_score = max(0, (1 - distance / len(target_ipa)) * 100)
        score = Decimal(str(raw_score)).quantize(Decimal("0.1"), rounding=ROUND_HALF_UP)
        candidate = {
            "score": score,
            "distance": distance,
            "alignment": alignment,
            "variant": {
                "index": index,
                "label": variant.get("label") or f"variant_{index}",
                "pronunciation": variant.get("pronunciation", ""),
                "rules": variant.get("rules", []),
                "ipa": target_ipa,
            },
        }
        if best is None or _is_better_candidate(candidate, best):
            best = candidate

    return best["score"], best["alignment"], best["variant"]


def error_rows(alignment, word_spans):
    rows = []
    for item in alignment:
        if item["operation"] == "match":
            continue

        word, word_index = _word_at_position(
            item["target_index"],
            word_spans,
            operation=item["operation"],
        )
        rows.append(
            {
                "sequence": len(rows),
                "phone_position": item["target_index"],
                "word": word,
                "word_index": word_index,
                "target_phone": item["target_phone"] or "",
                "recognized_phone": item["recognized_phone"] or "",
                "operation": item["operation"],
            }
        )
    return rows


def _word_at_position(position, word_spans, operation=None):
    if position is None:
        return "", None
    for index, span in enumerate(word_spans):
        if span.get("start", 0) <= position < span.get("end", 0):
            return span.get("word", ""), index
    if operation == "insertion":
        for index, span in enumerate(word_spans):
            if position == span.get("end", 0):
                return span.get("word", ""), index
        if word_spans and position >= word_spans[-1].get("end", 0):
            return word_spans[-1].get("word", ""), len(word_spans) - 1
    return "", None


def _coerce_target_variants(target_ipa_variants):
    variants = []
    seen = set()
    for index, variant in enumerate(target_ipa_variants or []):
        if isinstance(variant, dict):
            ipa = variant.get("ipa")
            label = variant.get("label") or f"variant_{index}"
            pronunciation = variant.get("pronunciation", "")
            rules = variant.get("rules", [])
        else:
            ipa = variant
            label = f"variant_{index}"
            pronunciation = ""
            rules = []
        if not isinstance(ipa, (list, tuple)) or not ipa:
            continue
        phones = [str(phone) for phone in ipa if str(phone)]
        if not phones:
            continue
        key = tuple(phones)
        if key in seen:
            continue
        seen.add(key)
        variants.append(
            {
                "label": label,
                "pronunciation": pronunciation,
                "rules": rules if isinstance(rules, list) else [],
                "ipa": phones,
            }
        )
    return variants


def _is_better_candidate(candidate, best):
    if candidate["score"] != best["score"]:
        return candidate["score"] > best["score"]
    if candidate["distance"] != best["distance"]:
        return candidate["distance"] < best["distance"]
    return candidate["variant"]["index"] < best["variant"]["index"]
