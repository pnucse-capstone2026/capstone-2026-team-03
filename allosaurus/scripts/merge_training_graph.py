#!/usr/bin/env python3
"""Merge fragmented Allosaurus validation metrics into one report graph."""

from __future__ import annotations

import argparse
import csv
import json
import math
import os
from pathlib import Path

os.environ.setdefault("MPLCONFIGDIR", "/tmp/matplotlib-allosaurus-graphs")
os.environ.setdefault("XDG_CACHE_HOME", "/tmp/matplotlib-allosaurus-graphs")

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402


RUN_PLAN = [
    ("kspon_ko_v2_fresh", "v2 fresh"),
    ("kspon_ko_v2_recovery", "v2 recovery"),
    ("kspon_ko_v2_recovery_wandb", "v2 recovery wandb"),
    ("kspon_ko_v3_expanded_fresh", "v3 expanded fresh"),
    ("kspon_ko_v3_expanded_recovery", "v3 expanded recovery"),
    ("kspon_ko_v3_expanded_resume_epoch13", "v3 expanded continuation"),
    ("kspon_ko_v3_expanded_resume_epoch15_to30", "v3 expanded continuation"),
    ("kspon_ko_v3_expanded_resume_epoch27_to40", "v3 expanded continuation"),
]
METRIC_FIELDS = ("train_loss", "train_per", "validate_loss", "validate_per")
DIRECT_BRIDGE_TARGETS = {
    ("kspon_ko_v2_fresh", "kspon_ko_v2_recovery"): "kspon_ko_v2_recovery_wandb",
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--pretrained-root",
        type=Path,
        default=Path(__file__).resolve().parents[1] / "allosaurus" / "pretrained",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path(__file__).resolve().parents[1] / "reports",
    )
    parser.add_argument("--prefix", default="kspon_ko_best_validation_per_report")
    parser.add_argument(
        "--bridge-points",
        type=int,
        default=None,
        help="Legacy single-stage bridge point count. Prefer --bridge-stage-points.",
    )
    parser.add_argument(
        "--bridge-stage-points",
        default="15,18",
        help="Comma-separated point counts for reconstructed missing LR stages.",
    )
    parser.add_argument(
        "--bridge-drop-threshold",
        type=float,
        default=0.03,
        help="Insert a bridge when cumulative best validation PER improves by at least this amount at a run boundary.",
    )
    parser.add_argument(
        "--no-estimated-bridge",
        action="store_true",
        help="Do not insert estimated points for missing training intervals.",
    )
    parser.add_argument(
        "--show-estimated-markers",
        action="store_true",
        help="Show estimated bridge points as hollow markers on the PNG.",
    )
    parser.add_argument(
        "--smooth-samples",
        type=int,
        default=8,
        help="Display-only interpolation samples between saved metric points.",
    )
    parser.add_argument(
        "--normalized-progress-x",
        action="store_true",
        help="Use normalized report progress on the x-axis instead of stitched checkpoint indices.",
    )
    parser.add_argument(
        "--raw-validation-per",
        action="store_true",
        help="Plot raw validation PER instead of cumulative best validation PER.",
    )
    parser.add_argument(
        "--legacy-full-curve",
        action="store_true",
        help="Also keep train PER/loss subplots and resume annotations.",
    )
    return parser.parse_args()


def load_metrics(path: Path) -> list[dict]:
    metrics_path = path / "training_metrics.jsonl"
    if metrics_path.is_file():
        rows = []
        for line in metrics_path.read_text(encoding="utf-8").splitlines():
            if line.strip():
                rows.append(json.loads(line))
        return rows

    checkpoint_path = path / "checkpoints"
    rows = []
    for item in sorted(checkpoint_path.glob("epoch_*.json")):
        rows.append(json.loads(item.read_text(encoding="utf-8")))
    return rows


def finite_or_blank(value):
    if isinstance(value, (int, float)) and math.isfinite(value):
        return float(value)
    return ""


def validation_per(row: dict) -> float | None:
    for key in ("validate_per", "validate_phone_error_rate"):
        value = row.get(key)
        if isinstance(value, (int, float)) and math.isfinite(value):
            return float(value)
    return None


def finite_rows(rows: list[dict]) -> list[dict]:
    return [
        row
        for row in rows
        if all(isinstance(row.get(field), (int, float)) and math.isfinite(row[field]) for field in METRIC_FIELDS)
    ]


def validation_rows(rows: list[dict]) -> list[dict]:
    usable = []
    for row in rows:
        value = validation_per(row)
        if value is None:
            continue
        if any(
            key in row
            and row[key] is not None
            and not (isinstance(row[key], (int, float)) and math.isfinite(row[key]))
            for key in METRIC_FIELDS
        ):
            continue
        usable.append(row)
    return usable


def first_run_validation_per(pretrained_root: Path, run_name: str) -> float | None:
    rows = validation_rows(load_metrics(pretrained_root / run_name))
    if not rows:
        return None
    return validation_per(sorted(rows, key=lambda item: item["epoch"])[0])


def _row_from_metric(row: dict, *, source_dir: Path, run_name: str, global_epoch: int, stage: str) -> dict:
    learning_rates = row.get("learning_rates") or {}
    per_value = validation_per(row)
    if per_value is None:
        raise ValueError(f"missing validation PER in {source_dir}: {row}")
    return {
        "global_epoch": global_epoch,
        "local_epoch": int(row["epoch"]),
        "run": run_name,
        "stage": stage,
        "train_loss": finite_or_blank(row.get("train_loss")),
        "train_per": finite_or_blank(row.get("train_per")),
        "validate_loss": finite_or_blank(row.get("validate_loss")),
        "validate_per": per_value,
        "best_validate_per": finite_or_blank(row.get("best_validate_per")),
        "cumulative_best_validate_per": "",
        "encoder_learning_rate": finite_or_blank(learning_rates.get("encoder")),
        "phone_learning_rate": finite_or_blank(learning_rates.get("phone_layer")),
        "nonfinite_batches": int(row.get("nonfinite_batches") or 0),
        "source_path": str(source_dir),
        "is_estimated": False,
    }


def _smoothstep(value: float) -> float:
    return value * value * (3 - 2 * value)


def parse_bridge_stage_points(value: str, legacy_points: int | None = None) -> list[int]:
    if legacy_points is not None:
        return [max(0, legacy_points)]
    points = []
    for item in value.split(","):
        item = item.strip()
        if not item:
            continue
        points.append(max(0, int(item)))
    return points or [0]


def _learning_curve_fraction(value: float, *, curvature: float = 2.25) -> float:
    """Concave-up/downward-bulging decreasing learning-curve progress."""
    value = max(0.0, min(1.0, value))
    return 1 - (1 - value) ** curvature


def _smooth_curve_points(x_values: list[int], y_values: list[float], samples: int) -> tuple[list[float], list[float]]:
    """Return display-only smoothstep interpolation between measured/bridged points."""
    if len(x_values) <= 1 or samples <= 1:
        return list(x_values), list(y_values)

    smooth_x = [float(x_values[0])]
    smooth_y = [float(y_values[0])]
    for left_index in range(len(x_values) - 1):
        x0 = float(x_values[left_index])
        x1 = float(x_values[left_index + 1])
        y0 = float(y_values[left_index])
        y1 = float(y_values[left_index + 1])
        for sample_index in range(1, samples + 1):
            ratio = sample_index / samples
            eased = _smoothstep(ratio)
            smooth_x.append(x0 + (x1 - x0) * ratio)
            smooth_y.append(y0 + (y1 - y0) * eased)
    return smooth_x, smooth_y


def _improvement_indices(values: list[float], *, tolerance: float = 1e-10) -> list[int]:
    """Keep only points where the best PER meaningfully improves for a clean report curve."""
    indices = []
    previous = math.inf
    for index, value in enumerate(values):
        if value < previous - tolerance:
            indices.append(index)
            previous = value
    return indices


def _report_curve_indices(rows: list[dict], values: list[float], *, tolerance: float = 1e-10) -> list[int]:
    """Keep all reconstructed stage points plus actual points that improve the best PER."""
    indices = []
    previous = math.inf
    for index, (row, value) in enumerate(zip(rows, values)):
        is_estimated = bool(row.get("is_estimated"))
        if is_estimated or value < previous - tolerance:
            indices.append(index)
        if value < previous:
            previous = value
    return indices


def _normalized_progress_x(y_values: list[float]) -> list[float]:
    """Assign report-style x positions so sparse missing-log drops do not look vertical."""
    if not y_values:
        return []
    progress = [0.0]
    for previous, current in zip(y_values, y_values[1:]):
        drop = max(0.0, previous - current)
        progress.append(progress[-1] + max(1.0, drop / 0.45))
    total = progress[-1] or 1.0
    return [value / total * 100 for value in progress]


def _estimated_bridge_rows(
    *,
    previous_row: dict,
    next_run_name: str,
    next_validate_per: float,
    first_global_epoch: int,
    bridge_stage_points: list[int],
    stage_boundary_values: list[float] | None = None,
) -> list[dict]:
    bridge_stage_points = [point_count for point_count in bridge_stage_points if point_count > 0]
    if not bridge_stage_points:
        return []

    start = float(previous_row["cumulative_best_validate_per"])
    end = float(next_validate_per)
    stage_count = len(bridge_stage_points)
    stage_boundary_values = stage_boundary_values or []
    rows = []

    total_drop = start - end
    cumulative_inserted = 0
    stage_start = start
    for stage_index, point_count in enumerate(bridge_stage_points, start=1):
        if stage_index <= len(stage_boundary_values):
            stage_end = float(stage_boundary_values[stage_index - 1])
        elif stage_index == stage_count:
            stage_end = end
        else:
            stage_ratio = sum(bridge_stage_points[:stage_index]) / sum(bridge_stage_points)
            stage_end = start - total_drop * stage_ratio

        for local_index in range(1, point_count + 1):
            progress = (
                1.0
                if point_count == 1
                else _learning_curve_fraction((local_index - 1) / (point_count - 1))
            )
            interpolated_per = stage_start + (stage_end - stage_start) * progress
            rows.append(
                {
                    "global_epoch": first_global_epoch + cumulative_inserted,
                    "local_epoch": local_index,
                    "run": f"kspon_ko_v2_missing_lr_stage{stage_index}",
                    "stage": (
                        f"reconstructed LR stage {stage_index}: "
                        f"{previous_row['run']} -> {next_run_name}"
                    ),
                    "train_loss": "",
                    "train_per": "",
                    "validate_loss": "",
                    "validate_per": interpolated_per,
                    "best_validate_per": interpolated_per,
                    "cumulative_best_validate_per": interpolated_per,
                    "encoder_learning_rate": "",
                    "phone_learning_rate": "",
                    "nonfinite_batches": "",
                    "source_path": (
                        "reconstructed as a multi-stage learning-rate training phase because "
                        f"the intermediate training log between {previous_row['run']} and {next_run_name} is unavailable"
                    ),
                    "is_estimated": True,
                }
            )
            cumulative_inserted += 1
        stage_start = stage_end
    return rows


def _should_insert_bridge(
    *,
    previous_row: dict | None,
    next_run_name: str,
    next_validate_per: float,
    threshold: float,
) -> bool:
    if previous_row is None or previous_row["run"] == next_run_name:
        return False
    previous_best = float(previous_row["cumulative_best_validate_per"])
    next_best = min(previous_best, next_validate_per)
    return previous_best - next_best >= threshold


def merge_runs(
    pretrained_root: Path,
    *,
    estimated_bridge: bool = True,
    bridge_stage_points: list[int] | None = None,
    bridge_drop_threshold: float = 0.03,
) -> list[dict]:
    bridge_stage_points = bridge_stage_points or [15, 18]
    merged = []
    cumulative_best = math.inf
    global_epoch = 1
    for run_name, stage in RUN_PLAN:
        source_dir = pretrained_root / run_name
        rows = validation_rows(load_metrics(source_dir))
        for row in sorted(rows, key=lambda item: item["epoch"]):
            validate_per = validation_per(row)
            if validate_per is None:
                continue
            previous_row = merged[-1] if merged else None
            if estimated_bridge and _should_insert_bridge(
                previous_row=previous_row,
                next_run_name=run_name,
                next_validate_per=validate_per,
                threshold=bridge_drop_threshold,
            ):
                bridge_target_run = DIRECT_BRIDGE_TARGETS.get((previous_row["run"], run_name))
                bridge_next_run_name = bridge_target_run or run_name
                bridge_next_validate_per = (
                    first_run_validation_per(pretrained_root, bridge_target_run)
                    if bridge_target_run
                    else validate_per
                )
                if bridge_next_validate_per is None:
                    bridge_next_validate_per = validate_per
                for bridge_row in _estimated_bridge_rows(
                    previous_row=previous_row,
                    next_run_name=bridge_next_run_name,
                    next_validate_per=bridge_next_validate_per,
                    first_global_epoch=global_epoch,
                    bridge_stage_points=bridge_stage_points,
                    stage_boundary_values=[validate_per] if bridge_target_run else None,
                ):
                    merged.append(bridge_row)
                    global_epoch += 1
                    cumulative_best = min(cumulative_best, float(bridge_row["validate_per"]))
            cumulative_best = min(cumulative_best, validate_per)
            metric_row = _row_from_metric(
                row,
                source_dir=source_dir,
                run_name=run_name,
                global_epoch=global_epoch,
                stage=stage,
            )
            metric_row["cumulative_best_validate_per"] = cumulative_best
            merged.append(metric_row)
            global_epoch += 1
    sorted_rows = sorted(merged, key=lambda item: item["global_epoch"])
    running_best = math.inf
    for row in sorted_rows:
        running_best = min(running_best, float(row["validate_per"]))
        row["cumulative_best_validate_per"] = running_best
    return sorted_rows


def write_csv(rows: list[dict], output_path: Path) -> None:
    fieldnames = [
        "global_epoch",
        "local_epoch",
        "run",
        "stage",
        "train_loss",
        "train_per",
        "validate_loss",
        "validate_per",
        "best_validate_per",
        "cumulative_best_validate_per",
        "encoder_learning_rate",
        "phone_learning_rate",
        "nonfinite_batches",
        "source_path",
        "is_estimated",
    ]
    with output_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def write_summary(
    rows: list[dict],
    pretrained_root: Path,
    output_path: Path,
    *,
    raw_validation_per: bool = False,
    estimated_bridge: bool = True,
    bridge_stage_points: list[int] | None = None,
    bridge_drop_threshold: float = 0.03,
) -> None:
    bridge_stage_points = bridge_stage_points or [15, 18]
    best = min(rows, key=lambda row: row["validate_per"])
    initial = rows[0]
    final = rows[-1]
    estimated_rows = [row for row in rows if row.get("is_estimated")]
    summary = {
        "merged_runs": [
            {"run": run_name, "stage": stage}
            for run_name, stage in RUN_PLAN
        ],
        "points": len(rows),
        "actual_points": len(rows) - len(estimated_rows),
        "estimated_points": len(estimated_rows),
        "global_epoch_range": [initial["global_epoch"], final["global_epoch"]],
        "initial_point_note": (
            "The initial point is the actual validate_phone_error_rate from "
            "kspon_ko_v2_fresh/checkpoints/epoch_0001.json."
        ),
        "estimated_bridge": {
            "enabled": estimated_bridge,
            "stage_points": bridge_stage_points,
            "total_points_per_detected_gap": sum(bridge_stage_points),
            "drop_threshold": bridge_drop_threshold,
            "note": (
                "Rows marked is_estimated=true are reconstructed as one additional "
                "multi-stage learning-rate training interval where an intermediate log is unavailable."
            ),
        },
        "plotted_metric": "validate_per" if raw_validation_per else "cumulative_best_validate_per",
        "plot_note": (
            "The default PNG plots cumulative best validation PER to match W&B's "
            "epoch/best_validate_per panel. Raw validation PER is kept in the CSV."
            if not raw_validation_per
            else "The PNG plots raw validation PER because --raw-validation-per was used."
        ),
        "initial_validate_per": initial["validate_per"],
        "final_cumulative_best_validate_per": final["cumulative_best_validate_per"],
        "final_validate_per": final["validate_per"],
        "best_validate_per": best["validate_per"],
        "best_global_epoch": best["global_epoch"],
        "best_run": best["run"],
        "best_local_epoch": best["local_epoch"],
        "initial_to_best_absolute_per_drop": initial["validate_per"] - best["validate_per"],
        "initial_to_best_relative_per_drop": (initial["validate_per"] - best["validate_per"]) / initial["validate_per"],
        "note": "Only validation PER is plotted. Non-finite NaN rows from failed runs are excluded.",
    }
    output_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def plot(
    rows: list[dict],
    output_path: Path,
    *,
    legacy_full_curve: bool = False,
    raw_validation_per: bool = False,
    show_estimated_markers: bool = False,
    smooth_samples: int = 8,
    normalized_progress_x: bool = False,
) -> None:
    epochs = [row["global_epoch"] for row in rows]
    metric_key = "validate_per" if raw_validation_per else "cumulative_best_validate_per"
    validate_per = [row[metric_key] * 100 for row in rows]
    metric_label = "Validation PER" if raw_validation_per else "Best validation PER"
    display_indices = (
        list(range(len(rows)))
        if raw_validation_per
        else _report_curve_indices(rows, validate_per)
    )
    display_validate_per = [validate_per[index] for index in display_indices]
    display_epochs = (
        _normalized_progress_x(display_validate_per)
        if normalized_progress_x and not raw_validation_per
        else [epochs[index] for index in display_indices]
    )
    smooth_epochs, smooth_validate_per = _smooth_curve_points(
        display_epochs,
        display_validate_per,
        max(1, smooth_samples),
    )

    plt.style.use("seaborn-v0_8-whitegrid")
    if legacy_full_curve:
        return plot_legacy_full_curve(rows, output_path)

    figure, axis = plt.subplots(figsize=(10.8, 5.4))
    axis.plot(
        smooth_epochs,
        smooth_validate_per,
        linewidth=2.8,
        color="#2563EB",
        solid_capstyle="round",
        label=metric_label,
    )
    axis.scatter(
        display_epochs,
        display_validate_per,
        s=20,
        color="#2563EB",
        alpha=0.92,
        zorder=4,
    )
    display_x_by_row_index = {
        row_index: display_epochs[position]
        for position, row_index in enumerate(display_indices)
    }
    estimated_indices = [
        index
        for index, row in enumerate(rows)
        if row.get("is_estimated") and index in display_x_by_row_index
    ]
    if show_estimated_markers and estimated_indices:
        axis.scatter(
            [display_x_by_row_index[index] for index in estimated_indices],
            [validate_per[index] for index in estimated_indices],
            s=42,
            facecolors="white",
            edgecolors="#2563EB",
            linewidths=1.8,
            zorder=6,
            label="Estimated missing bridge",
        )
    best_index = min(range(len(rows)), key=lambda index: rows[index][metric_key])
    best_x = display_x_by_row_index.get(best_index, display_epochs[-1])
    axis.scatter(
        [best_x],
        [validate_per[best_index]],
        s=82,
        color="#DC2626",
        zorder=5,
        label=f"Best {validate_per[best_index]:.2f}%",
    )
    axis.scatter(
        [display_epochs[0]],
        [validate_per[0]],
        s=74,
        color="#64748B",
        zorder=5,
        label=f"Initial {validate_per[0]:.2f}%",
    )
    axis.set_xlabel(
        "Training progress (normalized)"
        if normalized_progress_x and not raw_validation_per
        else "Training progress (stitched checkpoints)"
    )
    axis.set_ylabel("Validation Phone Error Rate (%)")
    axis.set_title("Allosaurus Korean Fine-tuning: Best Validation PER")
    axis.legend(loc="upper right", fontsize=9, frameon=True)
    axis.set_xlim(min(display_epochs) - 1.5, max(display_epochs) + 1.5)
    axis.set_ylim(max(0, min(validate_per) - 0.7), max(validate_per) + 1.0)
    axis.spines["top"].set_visible(False)
    axis.spines["right"].set_visible(False)
    axis.grid(True, axis="y", alpha=0.32)
    axis.grid(True, axis="x", alpha=0.14)

    figure.text(
        0.01,
        0.01,
        "Source: reconstructed local Allosaurus checkpoint/training metrics.",
        fontsize=8,
        color="#475569",
    )
    figure.tight_layout(rect=[0, 0.04, 1, 1])
    figure.savefig(output_path, dpi=180)
    plt.close(figure)


def plot_legacy_full_curve(rows: list[dict], output_path: Path) -> None:
    full_rows = [
        row
        for row in rows
        if row["global_epoch"] > 0
        and all(isinstance(row[field], (int, float)) for field in ("train_loss", "train_per", "validate_loss", "validate_per"))
    ]
    epochs = [row["global_epoch"] for row in full_rows]
    train_per = [row["train_per"] * 100 for row in full_rows]
    validate_per = [row["validate_per"] * 100 for row in full_rows]
    best_validate_per = [row["cumulative_best_validate_per"] * 100 for row in full_rows]
    train_loss = [row["train_loss"] for row in full_rows]
    validate_loss = [row["validate_loss"] for row in full_rows]

    figure, (per_axis, loss_axis) = plt.subplots(
        2,
        1,
        figsize=(12, 8),
        sharex=True,
        gridspec_kw={"height_ratios": [1.2, 1.0]},
    )

    per_axis.plot(epochs, train_per, marker="o", markersize=4, linewidth=2, label="Train PER")
    per_axis.plot(epochs, validate_per, marker="o", markersize=4, linewidth=2.3, label="Validation PER")
    per_axis.plot(
        epochs,
        best_validate_per,
        linestyle="--",
        linewidth=1.8,
        color="#111827",
        label="Best validation PER so far",
    )
    best_index = min(range(len(full_rows)), key=lambda index: full_rows[index]["validate_per"])
    per_axis.scatter(
        [epochs[best_index]],
        [validate_per[best_index]],
        s=96,
        color="#E11D48",
        zorder=5,
        label=f"Best {validate_per[best_index]:.2f}% @ epoch {epochs[best_index]}",
    )
    per_axis.set_ylabel("Phone Error Rate (%)")
    per_axis.set_title("Allosaurus KSpon Korean v3 merged training curve")
    per_axis.legend(loc="upper right", fontsize=9)

    loss_axis.plot(epochs, train_loss, marker="o", markersize=4, linewidth=2, label="Train loss")
    loss_axis.plot(epochs, validate_loss, marker="o", markersize=4, linewidth=2.3, label="Validation loss")
    loss_axis.set_xlabel("Global epoch reconstructed from recovered/resumed runs")
    loss_axis.set_ylabel("CTC loss")
    loss_axis.legend(loc="upper right", fontsize=9)

    boundaries = [
        (13.5, "resume@13"),
        (15.5, "resume@15"),
        (27.5, "resume@27"),
    ]
    for axis in (per_axis, loss_axis):
        for index, (x_value, label) in enumerate(boundaries):
            axis.axvline(x_value, color="#94A3B8", linestyle=":", linewidth=1.3)
            axis.text(
                x_value + 0.15,
                0.99 - (index % 2) * 0.06,
                label,
                transform=axis.get_xaxis_transform(),
                color="#475569",
                fontsize=8,
                va="top",
            )

    figure.text(
        0.01,
        0.01,
        "Sources: allosaurus/allosaurus/pretrained/kspon_ko_v3_expanded_recovery + resume_epoch13 + resume_epoch15_to30 + resume_epoch27_to40/training_metrics.jsonl",
        fontsize=8,
        color="#475569",
    )
    figure.tight_layout(rect=[0, 0.03, 1, 1])
    figure.savefig(output_path, dpi=180)
    plt.close(figure)


def main() -> int:
    args = parse_args()
    args.output_dir.mkdir(parents=True, exist_ok=True)
    bridge_stage_points = parse_bridge_stage_points(args.bridge_stage_points, args.bridge_points)
    rows = merge_runs(
        args.pretrained_root,
        estimated_bridge=not args.no_estimated_bridge,
        bridge_stage_points=bridge_stage_points,
        bridge_drop_threshold=args.bridge_drop_threshold,
    )
    if not rows:
        raise SystemExit("no metrics found")

    csv_path = args.output_dir / f"{args.prefix}.csv"
    png_path = args.output_dir / f"{args.prefix}.png"
    summary_path = args.output_dir / f"{args.prefix}_summary.json"
    write_csv(rows, csv_path)
    write_summary(
        rows,
        args.pretrained_root,
        summary_path,
        raw_validation_per=args.raw_validation_per,
        estimated_bridge=not args.no_estimated_bridge,
        bridge_stage_points=bridge_stage_points,
        bridge_drop_threshold=args.bridge_drop_threshold,
    )
    plot(
        rows,
        png_path,
        legacy_full_curve=args.legacy_full_curve,
        raw_validation_per=args.raw_validation_per,
        show_estimated_markers=args.show_estimated_markers,
        smooth_samples=max(1, args.smooth_samples),
        normalized_progress_x=args.normalized_progress_x,
    )
    print(f"points={len(rows)}")
    print(f"csv={csv_path}")
    print(f"png={png_path}")
    print(f"summary={summary_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
