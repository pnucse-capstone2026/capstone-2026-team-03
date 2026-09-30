#!/usr/bin/env python3
"""Build KsponSpeech processed_data trees from raw PCM and generated IPA labels."""

from __future__ import annotations

import argparse
import os
import wave
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path


def convert_one(task: tuple[str, str, str, bool]) -> dict[str, str]:
    pcm_string, label_string, output_dir_string, overwrite = task
    pcm = Path(pcm_string)
    label = Path(label_string)
    output_dir = Path(output_dir_string)
    wav_output = output_dir / f"{pcm.stem}.wav"
    txt_output = output_dir / f"{pcm.stem}.txt"

    if wav_output.exists() and txt_output.exists() and not overwrite:
        return {"status": "skipped", "source": pcm_string}

    try:
        if not label.is_file():
            raise FileNotFoundError(f"missing IPA label: {label}")
        if pcm.stat().st_size % 2:
            raise ValueError(f"PCM byte count is not divisible by 2: {pcm}")

        output_dir.mkdir(parents=True, exist_ok=True)
        pid = os.getpid()

        if overwrite or not wav_output.exists():
            wav_temporary = wav_output.with_name(f".{wav_output.name}.tmp-{pid}")
            with pcm.open("rb") as source, wave.open(str(wav_temporary), "wb") as destination:
                destination.setnchannels(1)
                destination.setsampwidth(2)
                destination.setframerate(16000)
                while chunk := source.read(1024 * 1024):
                    destination.writeframesraw(chunk)
            wav_temporary.replace(wav_output)

        if overwrite or not txt_output.exists():
            phones = label.read_text(encoding="utf-8").strip()
            if not phones:
                raise ValueError(f"empty IPA label: {label}")
            txt_temporary = txt_output.with_name(f".{txt_output.name}.tmp-{pid}")
            txt_temporary.write_text(phones + "\n", encoding="utf-8")
            txt_temporary.replace(txt_output)

        return {"status": "processed", "source": pcm_string}
    except Exception as exc:
        return {"status": "error", "source": pcm_string, "error": str(exc)}


def collect_tasks(
    roots: list[Path], label_root: Path, output_root: Path, overwrite: bool
) -> list[tuple[str, str, str, bool]]:
    tasks: list[tuple[str, str, str, bool]] = []
    for root in roots:
        seen_names: set[str] = set()
        dataset_output = output_root / root.name / "preprocessed" / "ipa"
        for pcm in sorted(path for path in root.rglob("*.pcm") if path.is_file()):
            if pcm.stem in seen_names:
                raise ValueError(f"duplicate basename in {root}: {pcm.stem}")
            seen_names.add(pcm.stem)
            relative_label = pcm.relative_to(root).with_suffix(".txt")
            label = label_root / root.name / relative_label
            tasks.append((str(pcm), str(label), str(dataset_output), overwrite))
    return tasks


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Convert KsponSpeech PCM to WAV and copy IPA labels into processed_data"
    )
    parser.add_argument("roots", nargs="+", type=Path)
    parser.add_argument("--label-root", required=True, type=Path)
    parser.add_argument("--output-root", required=True, type=Path)
    parser.add_argument("--workers", type=int, default=min(8, os.cpu_count() or 1))
    parser.add_argument("--limit", type=int, default=0)
    parser.add_argument("--overwrite", action="store_true")
    args = parser.parse_args()

    try:
        tasks = collect_tasks(args.roots, args.label_root, args.output_root, args.overwrite)
    except ValueError as exc:
        parser.error(str(exc))
    if args.limit:
        tasks = tasks[: args.limit]

    counts = {"processed": 0, "skipped": 0, "error": 0}
    errors: list[dict[str, str]] = []
    with ProcessPoolExecutor(max_workers=args.workers) as executor:
        for index, result in enumerate(executor.map(convert_one, tasks, chunksize=16), start=1):
            counts[result["status"]] += 1
            if result["status"] == "error":
                errors.append(result)
            if index % 1000 == 0 or index == len(tasks):
                print(
                    f"{index}/{len(tasks)} processed={counts['processed']} "
                    f"skipped={counts['skipped']} errors={counts['error']}",
                    flush=True,
                )

    if errors:
        print("First errors:")
        for error in errors[:10]:
            print(f"  {error['source']}: {error['error']}")
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
