"""Tests for the controlled sparse-accelerator paper evidence package."""

from __future__ import annotations

import numpy as np
import yaml

from src.hardware.analyze_sparse_accelerator_paper import (
    DEFAULT_CONFIG,
    analyze,
    count_row_spans,
    decode_tile_mask,
    make_shape_grid,
    mask_metrics,
    tile_grid_to_pixel_mask,
)


def test_tile_mask_decoder_rejects_out_of_grid_bits() -> None:
    """The paper mask decoder must retain the exact bounded 6-by-10 contract."""

    grid = decode_tile_mask("0x21", rows=2, columns=3)
    assert grid.tolist() == [[True, False, False], [False, False, True]]
    with np.testing.assert_raises_regex(ValueError, "outside"):
        decode_tile_mask("0x40", rows=2, columns=3)


def test_tile_expansion_and_span_count_preserve_geometry() -> None:
    """Macro-tile expansion and row-span counting must remain deterministic."""

    grid = np.asarray([[True, True, False], [False, True, True]], dtype=bool)
    pixels = tile_grid_to_pixel_mask(grid, tile_width=4, tile_height=3)
    assert pixels.shape == (6, 12)
    assert int(pixels.sum()) == 4 * 4 * 3
    assert count_row_spans(grid) == 2


def test_shape_generators_hold_density_but_change_fragmentation() -> None:
    """Controlled masks must isolate shape while retaining selected tile count."""

    clustered = make_shape_grid(
        "clustered", rows=6, columns=10, count=15, rng=np.random.default_rng(7)
    )
    checker = make_shape_grid(
        "checker", rows=6, columns=10, count=15, rng=np.random.default_rng(7)
    )
    assert int(clustered.sum()) == 15
    assert int(checker.sum()) == 15
    assert count_row_spans(checker) > count_row_spans(clustered)


def test_mask_metrics_include_exact_three_layer_dependency_closure() -> None:
    """A selected tile must expand monotonically through the CNN dependencies."""

    grid = np.zeros((6, 10), dtype=bool)
    grid[2, 4] = True
    metrics = mask_metrics(
        grid,
        tile_width=64,
        tile_height=60,
        scale=2,
        layer_radii=[2, 1, 0],
        input_radius=3,
    )
    active = metrics["layer_active_positions"]
    assert active[0] > active[1] > active[2]
    assert metrics["input_dependency_positions"] > active[0]
    assert metrics["axis_bytes"] > 0
    assert metrics["bitmap_mask_bytes"] == 8
    assert metrics["row_span_mask_bytes"] == 4


def test_tracked_physical_evidence_retains_mechanism_but_not_realtime() -> None:
    """The architecture gate must pass without rewriting the failed FPS result."""

    config = yaml.safe_load(DEFAULT_CONFIG.read_text(encoding="utf-8"))
    result = analyze(config)
    assert result["decision"] == "retain_hierarchical_mask_dataflow_as_hardware_paper_candidate"
    assert result["gates"]["mechanism_pass"] is True
    assert result["gates"]["realtime_720p"] is False
    assert result["gates"]["selected_output_exact"] is True
    assert result["gates"]["bounded_decoder_resource_and_timing"] is True
    assert result["gates"]["independent_worklist_scaling"] is True
    assert result["gates"]["independent_selector_generalization"] is False
    assert len(result["shape_density_sweep"]) == 25
    assert result["mask_encoding"]["decision"].startswith("retain_fixed")
    assert len(result["moving_mask_sweep"]) == 8
    assert result["claim_boundary"]["selector_generalization_claimed"] is False
    assert result["independent_worklists"]["decision"] == (
        "accept_independent_architecture_scaling_not_selector"
    )
    assert result["optimization_ablation"]["decision"].startswith("reject_")
    bounds = result["independent_tile_bounds"]
    assert bounds["selected_tiles"] == 17
    assert bounds["independent_active_layer_positions"] > bounds[
        "persistent_active_layer_positions"
    ]
    assert bounds["physical_single_tile_serial_projection_cycles"] == 8_447_674
    assert bounds["physical_full_frame_capture_available"] is True
    assert bounds["physical_full_frame_cycles"] == 9_857_730
    assert bounds["physical_full_frame_axis_bytes"] == 2_399_952
    assert result["claim_boundary"]["independent_tile_full_frame_is_physical"] is True
    independent = next(
        row
        for row in result["canonical_comparison"]
        if row["organization"] == "independent_halo_tiles"
    )
    rectangle = next(
        row
        for row in result["canonical_comparison"]
        if row["organization"] == "rectangle_compaction"
    )
    assert independent["evidence"] == "physical_balanced_independent_job_engine"
    assert independent["cycles"] > rectangle["cycles"]
    assert independent["accepted_descriptors"] == rectangle["accepted_descriptors"] == 15
    assert independent["selected_tile_equivalents"] == 17
    control = result["control_overhead"]
    assert control["isolated_bounded_decoder"]["logic_lut_delta"] == -424
    assert control["complete_commit_instrumentation_upper_bound"]["dsp_delta"] == 0
    assert control["bitmap_percent_of_canonical_axis_bytes"] < 0.001
