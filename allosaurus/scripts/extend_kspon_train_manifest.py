#!/usr/bin/env python3
"""Add Kspon data to train while freezing validation/test."""

from __future__ import annotations

import argparse
import json
import shutil
from pathlib import Path


FEATURE_FILES = ("feat.ark", "feat.scp", "shape", "token")


def read_manifest_lines(path: Path) -> list[str]:
    if not path.is_file():
        raise FileNotFoundError(path)
    return [line for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def manifest_ids(lines: list[str]) -> set[str]:
    return {line.split(maxsplit=1)[0] for line in lines}


def utterance_id(root_name: str, relative_stem: Path) -> str:
    key = (Path(root_name) / relative_stem).as_posix()
    return key.replace("/", "__").replace(" ", "_")


def extend_manifests(
    base_dir: Path,
    audio_roots: list[Path],
    label_root: Path,
    output_dir: Path,
    inventory_path: Path,
    overwrite: bool = False,
    allow_partial: bool = False,
    paired_roots: list[Path] | None = None,
) -> dict:
    if output_dir.exists():
        if not overwrite:
            raise FileExistsError(f"output already exists: {output_dir}")
        shutil.rmtree(output_dir)

    base = {
        split: {
            name: read_manifest_lines(base_dir / split / name)
            for name in ("wave", "text")
        }
        for split in ("train", "validate", "test")
    }
    all_base_ids = set().union(*(manifest_ids(base[split]["wave"]) for split in base))
    base_stems = {
        Path(line.split(maxsplit=1)[1]).stem
        for split in base
        for line in base[split]["wave"]
    }
    inventory = set(inventory_path.read_text(encoding="utf-8").split())

    added_wave: list[str] = []
    added_text: list[str] = []
    missing_labels: list[str] = []
    skipped_overlap: list[str] = []
    for audio_root in audio_roots:
        for pcm_path in sorted(audio_root.rglob("*.pcm")):
            relative_stem = pcm_path.relative_to(audio_root).with_suffix("")
            label_path = label_root / audio_root.name / relative_stem.with_suffix(".txt")
            if not label_path.is_file():
                missing_labels.append(str(label_path))
                continue
            if pcm_path.stem in base_stems:
                skipped_overlap.append(str(pcm_path))
                continue
            uid = utterance_id(audio_root.name, relative_stem)
            if uid in all_base_ids:
                raise ValueError(f"duplicate utterance ID: {uid}")
            phones = label_path.read_text(encoding="utf-8").strip().split()
            unsupported = sorted(set(phones) - inventory)
            if not phones or unsupported:
                raise ValueError(f"invalid IPA label {label_path}; unsupported={unsupported}")
            added_wave.append(f"{uid} {pcm_path.resolve()}")
            added_text.append(f"{uid} {' '.join(phones)}")

    for paired_root in paired_roots or []:
        for wav_path in sorted(paired_root.rglob("*.wav")):
            relative_stem = wav_path.relative_to(paired_root).with_suffix("")
            label_path = wav_path.with_suffix(".txt")
            if not label_path.is_file():
                missing_labels.append(str(label_path))
                continue
            if wav_path.stem in base_stems:
                skipped_overlap.append(str(wav_path))
                continue
            uid = utterance_id(paired_root.name, relative_stem)
            if uid in all_base_ids:
                raise ValueError(f"duplicate utterance ID: {uid}")
            phones = label_path.read_text(encoding="utf-8").strip().split()
            unsupported = sorted(set(phones) - inventory)
            if not phones or unsupported:
                raise ValueError(f"invalid IPA label {label_path}; unsupported={unsupported}")
            added_wave.append(f"{uid} {wav_path.resolve()}")
            added_text.append(f"{uid} {' '.join(phones)}")

    if missing_labels and not allow_partial:
        raise ValueError(f"missing {len(missing_labels)} IPA labels; first={missing_labels[0]}")

    for split in ("train", "validate", "test"):
        split_dir = output_dir / split
        split_dir.mkdir(parents=True, exist_ok=True)
        wave_lines = base[split]["wave"] + (added_wave if split == "train" else [])
        text_lines = base[split]["text"] + (added_text if split == "train" else [])
        (split_dir / "wave").write_text("\n".join(wave_lines) + "\n", encoding="utf-8")
        (split_dir / "text").write_text("\n".join(text_lines) + "\n", encoding="utf-8")

    # Validation features are immutable because its wave/text manifests are
    # copied byte-for-byte. Reuse them instead of spending time and disk twice.
    for name in FEATURE_FILES:
        source = (base_dir / "validate" / name).resolve()
        if source.exists():
            (output_dir / "validate" / name).symlink_to(source)

    summary = {
        "base_manifest_dir": str(base_dir.resolve()),
        "audio_roots": [str(path.resolve()) for path in audio_roots],
        "paired_roots": [str(path.resolve()) for path in (paired_roots or [])],
        "counts": {
            "base_train": len(base["train"]["wave"]),
            "added_train": len(added_wave),
            "train": len(base["train"]["wave"]) + len(added_wave),
            "validate": len(base["validate"]["wave"]),
            "test": len(base["test"]["wave"]),
        },
        "missing_labels": len(missing_labels),
        "skipped_base_overlap": len(skipped_overlap),
    }
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return summary


def main() -> int:
    parser = argparse.ArgumentParser(description="Extend Kspon train manifest while preserving validation/test")
    parser.add_argument("--base-manifest-dir", required=True, type=Path)
    parser.add_argument("--audio-root", action="append", type=Path, default=[])
    parser.add_argument("--label-root", type=Path)
    parser.add_argument(
        "--paired-root",
        action="append",
        type=Path,
        default=[],
        help="WAV directory tree whose IPA labels are adjacent .txt files",
    )
    parser.add_argument("--output-dir", required=True, type=Path)
    parser.add_argument("--inventory", required=True, type=Path)
    parser.add_argument("--allow-partial", action="store_true")
    parser.add_argument("--overwrite", action="store_true")
    args = parser.parse_args()
    if not args.audio_root and not args.paired_root:
        parser.error("at least one --audio-root or --paired-root is required")
    if args.audio_root and args.label_root is None:
        parser.error("--label-root is required with --audio-root")
    try:
        summary = extend_manifests(
            args.base_manifest_dir,
            args.audio_root,
            args.label_root,
            args.output_dir,
            args.inventory,
            args.overwrite,
            args.allow_partial,
            args.paired_root,
        )
    except (ValueError, FileExistsError, FileNotFoundError) as exc:
        parser.error(str(exc))
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
