"""Tests for the generated Paper 2 architecture and scaling figures."""

from __future__ import annotations

from pathlib import Path

from src.report.plot_sparse_accelerator_paper_figures import (
    DEFAULT_CONTROLLED,
    MIN_INTERNAL_FONT_PT,
    PAPER_FIGURE_WIDTH_IN,
    load_controlled_report,
    plot_architecture,
    plot_physical_scaling,
)


# Ensure both vector figures can be replayed from tracked physical evidence.
def test_sparse_paper_figures_render_as_nonempty_pdfs(tmp_path: Path) -> None:
    """The paper figure generator must emit two valid, nontrivial PDF files."""

    architecture = tmp_path / "architecture.pdf"
    scaling = tmp_path / "scaling.pdf"
    report = load_controlled_report(DEFAULT_CONTROLLED)

    plot_architecture(architecture)
    plot_physical_scaling(report, scaling)

    assert architecture.read_bytes().startswith(b"%PDF")
    assert scaling.read_bytes().startswith(b"%PDF")
    assert architecture.stat().st_size > 5_000
    assert scaling.stat().st_size > 5_000
    assert PAPER_FIGURE_WIDTH_IN <= 4.80
    assert MIN_INTERNAL_FONT_PT >= 8.0
