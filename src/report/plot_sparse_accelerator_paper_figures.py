"""Generate the architecture and physical-scaling figures for Paper 2.

The plots intentionally consume tracked JSON evidence rather than embedding
paper numbers by hand. This keeps every visual synchronized with the physical
Zybo captures and makes the submission artifact straightforward to replay.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Sequence

import matplotlib


matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import FancyArrowPatch, FancyBboxPatch


matplotlib.rcParams["pdf.fonttype"] = 42


ROOT = Path(__file__).resolve().parents[2]
DEFAULT_CONTROLLED = (
    ROOT / "results/tables/sparse_hierarchical_commit_controlled_masks_physical.json"
)
DEFAULT_ARCHITECTURE = ROOT / "results/plots/sparse_accelerator_architecture.pdf"
DEFAULT_SCALING = ROOT / "results/plots/sparse_accelerator_physical_scaling.pdf"
PDF_METADATA = {
    "Creator": "neural-upscaling-hw-sw-codesign",
    "CreationDate": None,
    "ModDate": None,
}
PAPER_FIGURE_WIDTH_IN = 4.80
MIN_INTERNAL_FONT_PT = 8.0


# Load one controlled-mask report and reject incomplete physical evidence.
def load_controlled_report(path: Path) -> dict[str, object]:
    """Return a physical controlled-mask report that passed all mechanism gates."""

    report = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(report, dict) or not report.get("gates", {}).get("mechanism_pass"):
        raise ValueError(f"controlled-mask evidence is missing or failed: {path}")
    return report


# Add one rounded dataflow block with a consistent publication color scheme.
def add_block(
    axis: plt.Axes,
    x: float,
    y: float,
    width: float,
    height: float,
    title: str,
    detail: str,
    color: str,
) -> None:
    """Draw one labeled accelerator stage in normalized figure coordinates."""

    patch = FancyBboxPatch(
        (x, y),
        width,
        height,
        boxstyle="round,pad=0.012,rounding_size=0.018",
        linewidth=1.1,
        edgecolor="#263238",
        facecolor=color,
    )
    axis.add_patch(patch)
    axis.text(
        x + width / 2,
        y + height * 0.74,
        title,
        ha="center",
        va="center",
        fontsize=8.2,
        fontweight="bold",
        linespacing=1.05,
    )
    axis.text(
        x + width / 2,
        y + height * 0.24,
        detail,
        ha="center",
        va="center",
        fontsize=MIN_INTERNAL_FONT_PT,
        linespacing=1.15,
    )


# Connect two stages with a compact arrow that remains legible in two columns.
def add_arrow(
    axis: plt.Axes,
    start: tuple[float, float],
    end: tuple[float, float],
    label: str = "",
) -> None:
    """Draw one directional dataflow edge and an optional short label."""

    arrow = FancyArrowPatch(
        start,
        end,
        arrowstyle="-|>",
        mutation_scale=11,
        linewidth=1.0,
        color="#37474f",
    )
    axis.add_patch(arrow)
    if label:
        axis.text(
            (start[0] + end[0]) / 2,
            (start[1] + end[1]) / 2 + 0.035,
            label,
            ha="center",
            va="bottom",
            fontsize=MIN_INTERNAL_FONT_PT,
            color="#37474f",
        )


# Draw the complete sparse-refinement path and its safe classical fallback.
def plot_architecture(output_path: Path) -> None:
    """Write a final-size vector architecture diagram for the ARC manuscript."""

    figure, axis = plt.subplots(figsize=(PAPER_FIGURE_WIDTH_IN, 3.12))
    axis.set_xlim(0.0, 1.0)
    axis.set_ylim(0.0, 1.0)
    axis.axis("off")

    add_block(axis, 0.01, 0.52, 0.16, 0.32, "Output\nmask", "60 tiles\nframe ID\ndeadline", "#dbeafe")
    add_block(axis, 0.205, 0.52, 0.16, 0.32, "Exact\nclosure", "layer masks\nbounded\n3x3 decode", "#dcfce7")
    add_block(axis, 0.40, 0.52, 0.16, 0.32, "Persistent\nCNN", "resident\nINT8 weights\nshared state", "#fef3c7")
    add_block(axis, 0.595, 0.52, 0.16, 0.32, "Residual\nreconstruct", "shuffle\nclamp\nand pack", "#ffedd5")
    add_block(axis, 0.79, 0.52, 0.19, 0.32, "Private\ncommit", "frame ID\ndeadline\nauth + publish", "#fce7f3")

    add_arrow(axis, (0.17, 0.68), (0.205, 0.68))
    add_arrow(axis, (0.365, 0.68), (0.40, 0.68))
    add_arrow(axis, (0.56, 0.68), (0.595, 0.68))
    add_arrow(axis, (0.755, 0.68), (0.79, 0.68))

    add_block(axis, 0.39, 0.06, 0.21, 0.28, "Classical\nfallback", "bicubic or\nLanczos\nalways valid", "#e5e7eb")
    add_arrow(axis, (0.495, 0.34), (0.495, 0.52), "base")
    add_arrow(axis, (0.60, 0.20), (0.885, 0.52), "fallback")

    axis.text(
        0.02,
        0.94,
        "Exact mask-driven sparse refinement with commit-safe fallback",
        fontsize=9.2,
        fontweight="bold",
        ha="left",
    )
    axis.text(
        0.02,
        0.02,
        "Counters: accepted bytes, active positions, stalls, cycles, skipped work, and terminal outcome",
        fontsize=MIN_INTERNAL_FONT_PT,
        color="#455a64",
        ha="left",
    )
    output_path.parent.mkdir(parents=True, exist_ok=True)
    figure.savefig(
        output_path,
        bbox_inches="tight",
        pad_inches=0.03,
        metadata=PDF_METADATA,
    )
    plt.close(figure)


# Plot normalized physical work so geometry sensitivity is visible at a glance.
def plot_physical_scaling(report: dict[str, object], output_path: Path) -> None:
    """Write two physical scaling panels for cycles and AXI traffic."""

    sparse_rows = [row for row in report["patterns"] if row["engine_id"] != "control"]
    family_order = [
        "clustered_rectangles",
        "scattered_random",
        "adversarial_checkerboard",
        "deadline_truncated_prefix",
        "moving_disocclusion_band",
    ]
    family_labels = {
        "clustered_rectangles": "Clustered",
        "scattered_random": "Scattered",
        "adversarial_checkerboard": "Checkerboard",
        "deadline_truncated_prefix": "Deadline prefix",
        "moving_disocclusion_band": "Motion band",
    }
    colors = ["#2563eb", "#16a34a", "#dc2626", "#9333ea", "#ea580c"]

    figure, axes = plt.subplots(1, 2, figsize=(PAPER_FIGURE_WIDTH_IN, 3.25), sharex=True)
    for family, color in zip(family_order, colors, strict=True):
        rows = [row for row in sparse_rows if row["sequence_id"] == family]
        x_values = [int(row["selected_tiles"]) for row in rows]
        axes[0].scatter(
            x_values,
            [100.0 - float(row["cycle_reduction_percent"]) for row in rows],
            label=family_labels[family],
            color=color,
            s=25,
            edgecolors="white",
            linewidths=0.45,
        )
        axes[1].scatter(
            x_values,
            [100.0 - float(row["axis_byte_reduction_percent"]) for row in rows],
            color=color,
            s=25,
            edgecolors="white",
            linewidths=0.45,
        )

    for axis, ylabel, title in [
        (axes[0], "Dense cycles retained (%)", "Physical compute scaling"),
        (axes[1], "Dense AXI bytes retained (%)", "Physical traffic scaling"),
    ]:
        axis.set_title(title, fontsize=8.8)
        axis.set_xlabel("Selected macro-tiles (of 60)", fontsize=MIN_INTERNAL_FONT_PT)
        axis.set_ylabel(ylabel, fontsize=MIN_INTERNAL_FONT_PT)
        axis.set_xlim(0, 62)
        axis.set_ylim(0, 105)
        axis.grid(True, linestyle=":", linewidth=0.6, alpha=0.7)
        axis.tick_params(labelsize=MIN_INTERNAL_FONT_PT)

    figure.legend(
        loc="lower center",
        bbox_to_anchor=(0.5, -0.005),
        ncol=3,
        fontsize=MIN_INTERNAL_FONT_PT,
        frameon=False,
    )
    figure.subplots_adjust(left=0.12, right=0.985, top=0.88, bottom=0.32, wspace=0.34)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    figure.savefig(
        output_path,
        bbox_inches="tight",
        pad_inches=0.03,
        metadata=PDF_METADATA,
    )
    plt.close(figure)


# Expose stable paths for reproducible paper builds and test fixtures.
def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    """Parse the physical input and vector figure destinations."""

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--controlled", type=Path, default=DEFAULT_CONTROLLED)
    parser.add_argument("--architecture-output", type=Path, default=DEFAULT_ARCHITECTURE)
    parser.add_argument("--scaling-output", type=Path, default=DEFAULT_SCALING)
    return parser.parse_args(argv)


# Generate both figures in one deterministic command.
def main(argv: Sequence[str] | None = None) -> int:
    """Write the paper figures and print their stable repository paths."""

    args = parse_args(argv)
    report = load_controlled_report(args.controlled)
    plot_architecture(args.architecture_output)
    plot_physical_scaling(report, args.scaling_output)
    print(f"SPARSE_PAPER_FIGURES_PASS architecture={args.architecture_output}")
    print(f"SPARSE_PAPER_FIGURES_PASS scaling={args.scaling_output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
