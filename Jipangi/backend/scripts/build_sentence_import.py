#!/usr/bin/env python3
"""Convert a sentence workbook into validated Jipangi IPA import JSON."""

from __future__ import annotations

import argparse
import json
import re
import sys
import zipfile
from collections import Counter
from pathlib import Path
from xml.etree import ElementTree as ET


XML_NAMESPACE = {"x": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}
DIFFICULTY_MAP = {"초급": 1, "중급": 2, "고급": 3, "상급": 3, "특수": 4, "심화": 4}
CATEGORY_CODES = {
    "음절 연습": "syllable-practice",
    "연음화": "liaison",
    "비음화": "nasalization",
    "유음화": "liquidization",
    "경음화": "tensification",
    "격음화": "aspiration",
    "구개음화": "palatalization",
    "ㅎ 탈락": "h-deletion",
    "인사/대화": "daily-communication",
    "요청/확인": "requests-confirmation",
    "건강/응급": "health-emergency",
    "집/가족": "home-family",
    "식사/주문": "meals-orders",
    "이동/교통": "transportation",
    "쇼핑/결제": "shopping-payment",
    "학교/직장": "school-work",
    "공공기관": "public-services",
    "감정/상태": "feelings-condition",
    "일상인사": "daily-greetings",
    "식당/주문": "dining-orders",
    "쇼핑": "shopping",
    "길찾기": "directions",
    "시간/약속": "time-appointments",
    "감정/상태": "emotions-states",
    "학교/공부": "school-study",
    "회사/업무": "work-business",
    "여행/문화": "travel-culture",
    "건강/생활": "health-daily-life",
    "음운변동": "phonological-changes",
    "취미/일상": "hobbies-daily-life",
    "날씨/계절": "weather-seasons",
    "자연/환경": "nature-environment",
    "복합발음": "complex-pronunciation",
    "사회/뉴스": "society-news",
    "철학/사상": "philosophy-thought",
    "학술/전문": "academic-professional",
    "발음훈련": "pronunciation-training",
}
TEXT_CORRECTIONS = {
    2: ("오늘 날씨가 действительно 좋네요.", "오늘 날씨가 정말 좋네요."),
}
BACKEND_ROOT = Path(__file__).resolve().parents[1]


def column_index(reference: str) -> int:
    letters = re.match(r"[A-Z]+", reference).group()
    value = 0
    for letter in letters:
        value = value * 26 + ord(letter) - ord("A") + 1
    return value - 1


def read_workbook(path: Path) -> list[dict[str, str]]:
    with zipfile.ZipFile(path) as workbook:
        root = ET.fromstring(workbook.read("xl/worksheets/sheet1.xml"))
    rows = []
    for row in root.findall(".//x:sheetData/x:row", XML_NAMESPACE):
        values = [""] * 4
        for cell in row.findall("x:c", XML_NAMESPACE):
            index = column_index(cell.attrib["r"])
            if index >= len(values):
                values.extend([""] * (index - len(values) + 1))
            inline_values = [node.text or "" for node in cell.findall(".//x:is//x:t", XML_NAMESPACE)]
            number = cell.find("x:v", XML_NAMESPACE)
            values[index] = "".join(inline_values) if inline_values else (number.text if number is not None else "")
        rows.append(values)
    if not rows or rows[0][:4] != ["번호", "난이도", "카테고리", "한국어 문장"]:
        raise ValueError(f"unexpected workbook header: {rows[0] if rows else None}")
    return [
        {"number": row[0], "difficulty": row[1], "category": row[2], "text": row[3].strip()}
        for row in rows[1:]
        if any(row[:4])
    ]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("workbook", type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument(
        "--allosaurus-root",
        type=Path,
        default=Path(__file__).resolve().parents[3] / "allosaurus",
    )
    parser.add_argument(
        "--deduplicate",
        action="store_true",
        help="Keep the first row for each sentence text and skip later duplicates.",
    )
    parser.add_argument(
        "--expected-rows",
        type=int,
        help="Optional exact row-count check after duplicate handling.",
    )
    args = parser.parse_args()

    for import_root in (BACKEND_ROOT, args.allosaurus_root):
        root = str(import_root)
        if root not in sys.path:
            sys.path.insert(0, root)
    from scripts.preprocess_kspon_pcm import (  # noqa: PLC0415
        INVENTORY_PATH,
        get_g2p,
        normalize_transcript,
        pronunciation_to_ipa,
    )
    from pronunciation.services.ipa_variants import build_ipa_variants  # noqa: PLC0415

    raw_rows = read_workbook(args.workbook)
    rows = []
    duplicate_count = 0
    seen_texts = set()
    for row in raw_rows:
        if row["text"] in seen_texts:
            duplicate_count += 1
            if not args.deduplicate:
                continue
        else:
            seen_texts.add(row["text"])
            rows.append(row)
    if args.expected_rows is not None and len(rows) != args.expected_rows:
        raise ValueError(f"expected {args.expected_rows} rows, got {len(rows)}")
    if duplicate_count and not args.deduplicate:
        raise ValueError("duplicate sentence text found")

    inventory = set(INVENTORY_PATH.read_text(encoding="utf-8").split())
    g2p = get_g2p()
    records = []
    for row in rows:
        source_number = int(row["number"])
        original_text = row["text"]
        corrected_text = original_text
        if source_number in TEXT_CORRECTIONS:
            expected, corrected_text = TEXT_CORRECTIONS[source_number]
            if original_text != expected:
                corrected_text = original_text
        if row["difficulty"] not in DIFFICULTY_MAP:
            raise ValueError(f"row {source_number}: unknown difficulty {row['difficulty']!r}")
        if row["category"] not in CATEGORY_CODES:
            raise ValueError(f"row {source_number}: unknown category {row['category']!r}")

        normalized = normalize_transcript(corrected_text)
        pronunciation = g2p(normalized)
        phones = pronunciation_to_ipa(pronunciation)
        unsupported = sorted(set(phones) - inventory)
        if unsupported:
            raise ValueError(f"row {source_number}: unsupported IPA {unsupported}")
        source_words = normalized.split()
        pronunciation_words = pronunciation.split()
        if len(source_words) != len(pronunciation_words):
            raise ValueError(
                f"row {source_number}: word count changed {source_words!r} -> {pronunciation_words!r}"
            )
        word_spans = []
        rebuilt = []
        for source_word, pronunciation_word in zip(source_words, pronunciation_words, strict=True):
            word_phones = pronunciation_to_ipa(pronunciation_word)
            start = len(rebuilt)
            rebuilt.extend(word_phones)
            word_spans.append({"word": source_word, "start": start, "end": len(rebuilt)})
        if rebuilt != phones:
            raise ValueError(f"row {source_number}: word span IPA does not match sentence IPA")
        ipa_variants = build_ipa_variants(
            normalized_text=normalized,
            standard_pronunciation=pronunciation,
            pronunciation_to_ipa=pronunciation_to_ipa,
            inventory=inventory,
        )

        records.append(
            {
                "text": corrected_text,
                "cached_ipa": phones,
                "cached_ipa_variants": ipa_variants,
                "word_spans": word_spans,
                "difficulty": DIFFICULTY_MAP[row["difficulty"]],
                "category": {
                    "code": CATEGORY_CODES[row["category"]],
                    "name": row["category"],
                    "description": f"엑셀 연습 문장 분류: {row['category']}",
                },
                "source_metadata": {
                    "source_file": args.workbook.name,
                    "source_number": source_number,
                    "source_difficulty": row["difficulty"],
                    "source_category": row["category"],
                    "original_text": original_text,
                    "normalized_text": normalized,
                    "g2p_pronunciation": pronunciation,
                    "converter": "g2pk+kspon-korean-ipa-v1",
                    "ipa_variant_strategy": "standard+rule-lenient-korean-v1",
                    "ipa_variant_count": len(ipa_variants),
                },
            }
        )

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(records, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"converted={len(records)}")
    print(f"source_rows={len(raw_rows)}")
    print(f"duplicate_rows={duplicate_count}")
    print(f"ipa_tokens={sum(len(record['cached_ipa']) for record in records)}")
    print(f"difficulties={dict(Counter(record['difficulty'] for record in records))}")
    print(f"categories={len({record['category']['code'] for record in records})}")
    print(f"output={args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
