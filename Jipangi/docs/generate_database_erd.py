#!/usr/bin/env python3
"""Generate a report-friendly ERD image for the Jipangi database."""

from __future__ import annotations

import os
from pathlib import Path

os.environ.setdefault("MPLCONFIGDIR", "/tmp/matplotlib-jipangi-erd")
os.environ.setdefault("XDG_CACHE_HOME", "/tmp/matplotlib-jipangi-erd")

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib import patches  # noqa: E402
from matplotlib.font_manager import FontProperties  # noqa: E402


DOCS_DIR = Path(__file__).resolve().parent
FONT_REGULAR = FontProperties(fname="/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc")
FONT_BOLD = FontProperties(fname="/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc")
FONT_MONO = FontProperties(fname="/usr/share/fonts/truetype/nanum/NanumGothicCoding.ttf")


ENTITIES = {
    "user": {
        "title": "USER_ACCOUNT",
        "subtitle": "사용자",
        "x": 0.7,
        "y": 4.55,
        "w": 3.8,
        "h": 2.25,
        "color": "#E0F2FE",
        "edge": "#0284C7",
        "fields": [
            "PK id",
            "username UNIQUE",
            "email, phone_number",
            "age",
            "is_active",
        ],
    },
    "baseline": {
        "title": "BASELINE_ASSESSMENT",
        "subtitle": "초기 평가",
        "x": 0.7,
        "y": 0.8,
        "w": 3.8,
        "h": 2.55,
        "color": "#F0F9FF",
        "edge": "#38BDF8",
        "fields": [
            "PK id",
            "FK user_id UNIQUE",
            "status",
            "self_report_score",
            "discomfort_level",
            "answers JSON",
        ],
    },
    "category": {
        "title": "CATEGORY",
        "subtitle": "발음/생활 분류",
        "x": 5.55,
        "y": 7.1,
        "w": 4.5,
        "h": 1.9,
        "color": "#FEF3C7",
        "edge": "#F59E0B",
        "fields": [
            "PK id",
            "code UNIQUE",
            "name UNIQUE",
            "description",
        ],
    },
    "sentence": {
        "title": "PRACTICE_SENTENCE",
        "subtitle": "연습 항목",
        "x": 5.35,
        "y": 3.7,
        "w": 4.85,
        "h": 3.0,
        "color": "#FFFBEB",
        "edge": "#D97706",
        "fields": [
            "PK id",
            "text, difficulty(1~4)",
            "FK category_id NULL",
            "FK created_by_id NULL",
            "cached_ipa_variants JSON",
            "word_spans JSON",
            "is_active",
        ],
    },
    "analysis": {
        "title": "PRONUNCIATION_ANALYSIS",
        "subtitle": "발음 분석",
        "x": 11.35,
        "y": 3.9,
        "w": 4.65,
        "h": 3.2,
        "color": "#EEF2FF",
        "edge": "#4F46E5",
        "fields": [
            "PK id UUID",
            "FK user_id NULL, sentence_id",
            "score, status",
            "target_ipa/recognized_ipa JSON",
            "alignment JSON",
            "analyzer_metadata JSON",
        ],
    },
    "error": {
        "title": "PRONUNCIATION_ERROR",
        "subtitle": "세부 오류",
        "x": 16.95,
        "y": 6.15,
        "w": 4.3,
        "h": 2.65,
        "color": "#FEE2E2",
        "edge": "#DC2626",
        "fields": [
            "PK id",
            "FK analysis_id",
            "sequence UNIQUE per analysis",
            "target/recognized_phone",
            "operation, confidence",
            "specific_feedback JSON",
        ],
    },
    "feedback": {
        "title": "CORRECTION_FEEDBACK",
        "subtitle": "LLM 피드백",
        "x": 16.95,
        "y": 2.15,
        "w": 4.3,
        "h": 2.55,
        "color": "#F3E8FF",
        "edge": "#9333EA",
        "fields": [
            "PK id",
            "FK analysis_id UNIQUE",
            "summary, content",
            "priority_items/structured_output JSON",
            "model_name/version",
            "is_validated",
        ],
    },
}


RELATIONSHIPS = [
    ("user", "baseline", "1", "0..1", "초기평가"),
    ("user", "sentence", "0..1", "0..N", "개인 문장 생성"),
    ("category", "sentence", "0..1", "0..N", "문장 분류"),
    ("user", "analysis", "0..1", "0..N", "분석 요청"),
    ("sentence", "analysis", "1", "0..N", "분석 대상"),
    ("analysis", "error", "1", "0..N", "오류 목록"),
    ("analysis", "feedback", "1", "0..1", "교정 피드백"),
]


def entity_anchor(entity: dict, side: str) -> tuple[float, float]:
    x, y, w, h = entity["x"], entity["y"], entity["w"], entity["h"]
    if side == "left":
        return x, y + h / 2
    if side == "right":
        return x + w, y + h / 2
    if side == "top":
        return x + w / 2, y + h
    if side == "bottom":
        return x + w / 2, y
    raise ValueError(side)


def side_between(source: dict, target: dict) -> tuple[str, str, float]:
    source_center = (source["x"] + source["w"] / 2, source["y"] + source["h"] / 2)
    target_center = (target["x"] + target["w"] / 2, target["y"] + target["h"] / 2)
    dx = target_center[0] - source_center[0]
    dy = target_center[1] - source_center[1]
    if abs(dx) >= abs(dy):
        return ("right", "left", 0.08 if dy >= 0 else -0.08) if dx >= 0 else ("left", "right", -0.08)
    return ("top", "bottom", 0.0) if dy >= 0 else ("bottom", "top", 0.0)


def draw_entity(axis, entity: dict) -> None:
    x, y, w, h = entity["x"], entity["y"], entity["w"], entity["h"]
    body = patches.FancyBboxPatch(
        (x, y),
        w,
        h,
        boxstyle="round,pad=0.025,rounding_size=0.11",
        linewidth=1.9,
        edgecolor=entity["edge"],
        facecolor=entity["color"],
        zorder=2,
    )
    axis.add_patch(body)

    header_h = 0.58
    header = patches.FancyBboxPatch(
        (x, y + h - header_h),
        w,
        header_h,
        boxstyle="round,pad=0.025,rounding_size=0.11",
        linewidth=0,
        facecolor=entity["edge"],
        zorder=3,
    )
    axis.add_patch(header)
    axis.add_patch(
        patches.Rectangle((x, y + h - header_h), w, header_h / 2, linewidth=0, facecolor=entity["edge"], zorder=3)
    )

    axis.text(
        x + 0.16,
        y + h - 0.22,
        entity["title"],
        ha="left",
        va="top",
        color="white",
        fontsize=10.0,
        fontproperties=FONT_BOLD,
        zorder=4,
    )
    axis.text(
        x + w - 0.16,
        y + h - 0.28,
        entity["subtitle"],
        ha="right",
        va="top",
        color="white",
        fontsize=7.8,
        fontproperties=FONT_REGULAR,
        zorder=4,
    )

    field_y = y + h - header_h - 0.25
    for field in entity["fields"]:
        is_key = field.startswith(("PK", "FK"))
        axis.text(
            x + 0.18,
            field_y,
            field,
            ha="left",
            va="top",
            color="#0F172A",
            fontsize=8.15,
            fontproperties=FONT_MONO if is_key else FONT_REGULAR,
            zorder=4,
        )
        field_y -= 0.31


def draw_relationship(axis, source_key: str, target_key: str, left_card: str, right_card: str, label: str) -> None:
    source = ENTITIES[source_key]
    target = ENTITIES[target_key]
    source_side, target_side, curve = side_between(source, target)
    x1, y1 = entity_anchor(source, source_side)
    x2, y2 = entity_anchor(target, target_side)

    line = patches.FancyArrowPatch(
        (x1, y1),
        (x2, y2),
        arrowstyle="-",
        connectionstyle=f"arc3,rad={curve}",
        linewidth=1.55,
        color="#475569",
        zorder=1,
    )
    axis.add_patch(line)

    label_x = (x1 + x2) / 2
    label_y = (y1 + y2) / 2
    axis.text(
        label_x,
        label_y + 0.12,
        label,
        ha="center",
        va="bottom",
        fontsize=7.6,
        color="#334155",
        fontproperties=FONT_REGULAR,
        bbox={"boxstyle": "round,pad=0.16", "facecolor": "white", "edgecolor": "none", "alpha": 0.88},
        zorder=5,
    )
    axis.text(
        x1 + (0.12 if x2 >= x1 else -0.12),
        y1 + (0.12 if y2 >= y1 else -0.12),
        left_card,
        ha="center",
        va="center",
        fontsize=7.7,
        color="#0F172A",
        fontproperties=FONT_BOLD,
        bbox={"boxstyle": "round,pad=0.12", "facecolor": "white", "edgecolor": "#CBD5E1"},
        zorder=5,
    )
    axis.text(
        x2 + (-0.12 if x2 >= x1 else 0.12),
        y2 + (-0.12 if y2 >= y1 else 0.12),
        right_card,
        ha="center",
        va="center",
        fontsize=7.7,
        color="#0F172A",
        fontproperties=FONT_BOLD,
        bbox={"boxstyle": "round,pad=0.12", "facecolor": "white", "edgecolor": "#CBD5E1"},
        zorder=5,
    )


def main() -> int:
    figure, axis = plt.subplots(figsize=(21.5, 10.7), dpi=180)
    axis.set_xlim(0, 21.9)
    axis.set_ylim(0, 10.35)
    axis.axis("off")
    figure.patch.set_facecolor("white")
    axis.set_facecolor("white")

    axis.text(
        0.65,
        9.95,
        "Jipangi Database ERD",
        ha="left",
        va="top",
        fontsize=20,
        color="#111827",
        fontproperties=FONT_BOLD,
    )
    axis.text(
        0.67,
        9.36,
        "사용자 → 연습 항목 → 발음 분석 → 오류/피드백 흐름 중심의 보고서용 요약 ERD",
        ha="left",
        va="top",
        fontsize=10.5,
        color="#475569",
        fontproperties=FONT_REGULAR,
    )

    for relationship in RELATIONSHIPS:
        draw_relationship(axis, *relationship)

    for entity in ENTITIES.values():
        draw_entity(axis, entity)

    axis.text(
        0.67,
        0.22,
        "PK=Primary Key · FK=Foreign Key · UNIQUE=고유 제약 · NULL=선택 관계 · JSON=분석/IPA/피드백 구조화 데이터",
        ha="left",
        va="bottom",
        fontsize=8.7,
        color="#475569",
        fontproperties=FONT_REGULAR,
    )

    for extension in ("png", "svg"):
        output_path = DOCS_DIR / f"database-erd-report.{extension}"
        figure.savefig(output_path, bbox_inches="tight", facecolor="white")
        print(output_path)
    plt.close(figure)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
