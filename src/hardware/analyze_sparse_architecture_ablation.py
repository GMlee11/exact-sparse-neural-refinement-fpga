"""Attribute sparse-SR benefits to closure, reuse, and safe commit.

The report joins only tracked physical Zybo captures for the canonical 17-tile
mask. Exact geometry is used once to isolate duplicate dependency work; cycle,
traffic, resource, and service claims remain tied to board measurements.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Sequence


ROOT = Path(__file__).resolve().parents[2]
DEFAULT_PAPER = ROOT / "results/tables/sparse_accelerator_paper_v1.json"
DEFAULT_HIERARCHICAL = ROOT / "results/tables/sparse_refinement_hierarchical_physical.json"
DEFAULT_BALANCED = ROOT / "results/tables/sparse_refinement_balanced_pipeline_physical.json"
DEFAULT_COMMIT = ROOT / "results/tables/sparse_hierarchical_commit_controlled_masks_50mhz_physical.json"
DEFAULT_COMMIT_MANIFEST = ROOT / "fpga/generated/sparse_refinement_accelerator_v1/hierarchical_mask_suite_controlled_shapes_50mhz_v1/manifest.json"
DEFAULT_CONTROLLED = ROOT / "results/tables/sparse_hierarchical_commit_controlled_masks_physical.json"
DEFAULT_JSON = ROOT / "results/tables/sparse_architecture_ablation_v1.json"
DEFAULT_MARKDOWN = ROOT / "results/tables/sparse_architecture_ablation_v1.md"
DEFAULT_LATEX = ROOT / "docs/paper/generated/sparse_architecture_ablation_v1.tex"
DEFAULT_GEOMETRY_LATEX = (
    ROOT / "docs/paper/generated/sparse_mask_geometry_sensitivity_v1.tex"
)


# Load a tracked JSON object and fail early on malformed evidence.
def load_report(path: Path) -> dict[str, object]:
    """Return one validated JSON evidence object."""

    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"report is not a JSON object: {path}")
    return payload


# Keep every reported delta on one explicit baseline convention.
def reduction_percent(baseline: float, candidate: float) -> float:
    """Return the percentage reduction from baseline to candidate."""

    if baseline <= 0.0 or candidate < 0.0:
        raise ValueError("ablation values must be nonnegative with a positive baseline")
    return 100.0 * (1.0 - candidate / baseline)


def cycle_derived_elapsed_ms(cycles: int, clock_mhz: float) -> float:
    """Convert a physical cycle counter and routed clock into elapsed milliseconds."""

    if cycles < 0 or clock_mhz <= 0.0:
        raise ValueError("cycles must be nonnegative and clock must be positive")
    return float(cycles) / (clock_mhz * 1_000.0)


# Join a generated request mask to its physical result by stable pattern ID.
def find_physical_mask_result(
    manifest: dict[str, object],
    physical: dict[str, object],
    mask_hex: str,
) -> dict[str, object]:
    """Return the exact physical row corresponding to one 60-bit mask."""

    patterns = manifest["patterns"]
    matches = [row for row in patterns if str(row["mask_hex"]).lower() == mask_hex.lower()]
    if len(matches) != 1:
        raise ValueError(f"expected one manifest row for mask {mask_hex}, found {len(matches)}")
    pattern_id = int(matches[0]["pattern_id"])
    physical_matches = [
        row for row in physical["patterns"] if int(row["pattern_id"]) == pattern_id
    ]
    if len(physical_matches) != 1:
        raise ValueError(f"expected one physical result for pattern {pattern_id}")
    result = physical_matches[0]
    if not bool(result["exact"]):
        raise ValueError("canonical commit-safe mask result is not exact")
    return result


# Build the causal mechanism attribution without conflating clock or counter scope.
def analyze(
    paper: dict[str, object],
    hierarchical: dict[str, object],
    balanced: dict[str, object],
    commit: dict[str, object],
    commit_manifest: dict[str, object],
    controlled: dict[str, object],
) -> dict[str, object]:
    """Return realized organization operating points and bounded controls."""

    comparison = {row["organization"]: row for row in paper["canonical_comparison"]}
    independent = comparison["independent_halo_tiles"]
    rectangle = comparison["rectangle_compaction"]
    persistent = comparison["persistent_hierarchical_mask"]
    bounds = paper["independent_tile_bounds"]
    mask_hex = str(bounds["mask_hex"])
    commit_row = find_physical_mask_result(commit_manifest, commit, mask_hex)

    mask_only_service_ms = float(hierarchical["physical_performance"]["average_service_ms"])
    commit_service_ms = float(commit_row["average_service_ms"])
    mask_only_impl = hierarchical["implementation"]
    commit_impl = commit["route"]
    balanced_impl = balanced["implementation"]

    balanced_resources = {
        "clock_mhz": float(balanced_impl["fabric_clock_hz"]) / 1_000_000.0,
        "luts": int(balanced_impl["slice_luts"]),
        "registers": int(balanced_impl["slice_registers"]),
        "bram_tiles": float(balanced_impl["bram_tiles"]),
        "dsps": int(balanced_impl["dsp48e1"]),
    }
    persistent_resources = {
        "clock_mhz": float(mask_only_impl["fabric_clock_hz"]) / 1_000_000.0,
        "luts": int(mask_only_impl["slice_luts"]),
        "registers": int(mask_only_impl["slice_registers"]),
        "bram_tiles": float(mask_only_impl["bram_tiles"]),
        "dsps": int(mask_only_impl["dsp48e1"]),
    }
    commit_resources = {
        "clock_mhz": 50.0,
        "luts": int(commit_impl["slice_luts"]),
        "registers": int(commit_impl["registers"]),
        "bram_tiles": float(commit_impl["bram_tiles"]),
        "dsps": int(commit_impl["dsps"]),
    }

    def organization_row(
        *,
        organization: str,
        dependency_scope: str,
        cross_region_reuse: str,
        private_atomic_commit: bool,
        cycles: int,
        axis_bytes: int,
        evidence: str,
        resource: dict[str, float | int],
        **extra: object,
    ) -> dict[str, object]:
        return {
            "organization": organization,
            "dependency_scope": dependency_scope,
            "cross_region_reuse": cross_region_reuse,
            "private_atomic_commit": private_atomic_commit,
            "cycles": cycles,
            "clock_mhz": resource["clock_mhz"],
            "cycle_derived_compute_ms": cycle_derived_elapsed_ms(
                cycles, float(resource["clock_mhz"])
            ),
            "axis_bytes": axis_bytes,
            "luts": resource["luts"],
            "registers": resource["registers"],
            "bram_tiles": resource["bram_tiles"],
            "dsps": resource["dsps"],
            "evidence": evidence,
            **extra,
        }

    organizations = [
        organization_row(
            organization="independent_jobs",
            dependency_scope="exact_per_job_halo",
            cross_region_reuse="none",
            private_atomic_commit=False,
            cycles=int(independent["cycles"]),
            axis_bytes=int(independent["axis_bytes"]),
            evidence=str(independent["evidence"]),
            resource=balanced_resources,
        ),
        organization_row(
            organization="rectangle_compaction",
            dependency_scope="exact_per_compacted_rectangle",
            cross_region_reuse="inside_each_rectangle",
            private_atomic_commit=False,
            cycles=int(rectangle["cycles"]),
            axis_bytes=int(rectangle["axis_bytes"]),
            evidence=str(rectangle["evidence"]),
            resource=balanced_resources,
        ),
        organization_row(
            organization="global_closure_persistent",
            dependency_scope="exact_global_layer_closure",
            cross_region_reuse="persistent_full_traversal",
            private_atomic_commit=False,
            cycles=int(persistent["cycles"]),
            axis_bytes=int(persistent["axis_bytes"]),
            evidence=str(persistent["evidence"]),
            resource=persistent_resources,
        ),
        organization_row(
            organization="complete_commit_safe",
            dependency_scope="exact_global_layer_closure",
            cross_region_reuse="persistent_full_traversal",
            private_atomic_commit=True,
            cycles=int(commit_row["average_fpga_cycles"]),
            axis_bytes=int(commit_row["axis_bytes"]),
            evidence="physical_same_clock_commit_engine",
            resource=commit_resources,
            cycle_counter_scope="includes_commit_terminal_boundary",
        ),
    ]
    independent_row = organizations[0]
    persistent_row = organizations[2]
    headline_operating_point_comparison = {
        "baseline": "independent_jobs",
        "candidate": "global_closure_persistent",
        "independent_cycles": independent_row["cycles"],
        "independent_clock_mhz": independent_row["clock_mhz"],
        "independent_cycle_derived_compute_ms": independent_row[
            "cycle_derived_compute_ms"
        ],
        "independent_axis_bytes": independent_row["axis_bytes"],
        "independent_resources": {
            key: independent_row[key]
            for key in ("luts", "registers", "bram_tiles", "dsps")
        },
        "persistent_cycles": persistent_row["cycles"],
        "persistent_clock_mhz": persistent_row["clock_mhz"],
        "persistent_cycle_derived_compute_ms": persistent_row[
            "cycle_derived_compute_ms"
        ],
        "persistent_axis_bytes": persistent_row["axis_bytes"],
        "persistent_resources": {
            key: persistent_row[key]
            for key in ("luts", "registers", "bram_tiles", "dsps")
        },
        "cycle_reduction_percent": reduction_percent(
            float(independent_row["cycles"]), float(persistent_row["cycles"])
        ),
        "axis_reduction_percent": reduction_percent(
            float(independent_row["axis_bytes"]), float(persistent_row["axis_bytes"])
        ),
        "cycle_derived_elapsed_delta_ms": float(
            persistent_row["cycle_derived_compute_ms"]
        )
        - float(independent_row["cycle_derived_compute_ms"]),
        "wall_time_speedup_claimed": False,
        "clock_normalized_acceleration_claimed": False,
        "causal_mechanism_isolated": False,
        "boundary": (
            "These are coupled routed operating points with different clocks, resource "
            "footprints, routing, and memory organizations. Their counter reduction is "
            "not an observed elapsed-time speedup or an isolated mechanism effect."
        ),
    }

    effects = {
        "rectangle_coalescing": {
            "cycle_reduction_percent": reduction_percent(
                float(independent["cycles"]), float(rectangle["cycles"])
            ),
            "axis_reduction_percent": reduction_percent(
                float(independent["axis_bytes"]), float(rectangle["axis_bytes"])
            ),
        },
        "global_closure_and_persistent_reuse": {
            "cycle_reduction_percent": reduction_percent(
                float(rectangle["cycles"]), float(persistent["cycles"])
            ),
            "axis_reduction_percent": reduction_percent(
                float(rectangle["axis_bytes"]), float(persistent["axis_bytes"])
            ),
        },
        "exact_union_geometry": {
            "independent_active_layer_positions": int(
                bounds["independent_active_layer_positions"]
            ),
            "persistent_active_layer_positions": int(
                bounds["persistent_active_layer_positions"]
            ),
            "duplicate_dependency_reduction_percent": reduction_percent(
                float(bounds["independent_active_layer_positions"]),
                float(bounds["persistent_active_layer_positions"]),
            ),
            "measurement_class": "exact_geometry_not_cycle_projection",
        },
        "private_atomic_commit": {
            "mask_only_service_ms_50mhz": mask_only_service_ms,
            "commit_safe_service_ms_50mhz": commit_service_ms,
            "service_overhead_percent": 100.0
            * (commit_service_ms / mask_only_service_ms - 1.0),
            "logic_lut_delta": int(commit_impl["slice_luts"])
            - int(mask_only_impl["slice_luts"]),
            "register_delta": int(commit_impl["registers"])
            - int(mask_only_impl["slice_registers"]),
            "bram_delta": float(commit_impl["bram_tiles"])
            - float(mask_only_impl["bram_tiles"]),
            "dsp_delta": int(commit_impl["dsps"]) - int(mask_only_impl["dsp48e1"]),
            "all_four_outcomes_exact": bool(commit["gates"]["all_commit_outcomes_exact"]),
            "cycle_counter_directly_comparable": False,
            "timer_scope": "input_dma_trigger_to_dma_and_core_completion",
            "isolated_publication_overhead_claimed": False,
            "counter_note": (
                "The commit-safe cycle counter includes the terminal commit boundary; "
                "host intervals cover input DMA trigger through DMA/core completion, "
                "excluding output clearing, setup, input construction and later validation. "
                "Separate same-clock builds do not isolate publication overhead. "
                "Legacy service field names are retained for schema compatibility."
            ),
        },
    }

    resources = {
        "independent_and_rectangle_engine": {
            **balanced_resources,
            "timing_closed": bool(balanced_impl["timing_closed"]),
        },
        "persistent_mask_only": {
            **persistent_resources,
            "timing_closed": bool(mask_only_impl["timing_closed"]),
        },
        "complete_commit_safe": {
            **commit_resources,
            "timing_closed": bool(commit_impl["timing_closed"]),
            "wns_ns": float(commit_impl["wns_ns"]),
        },
    }

    # Group controlled patterns by geometry family so the paper can report
    # clustered, fragmented, adversarial, deadline, and motion-style behavior
    # without listing all fifteen sparse rows in the main body.
    controlled_families: list[dict[str, object]] = []
    family_names = sorted(
        {
            str(row["sequence_id"])
            for row in controlled["patterns"]
            if str(row["engine_id"]) != "control"
        }
    )
    for family in family_names:
        rows = [
            row for row in controlled["patterns"] if str(row["sequence_id"]) == family
        ]
        controlled_families.append(
            {
                "family": family,
                "pattern_count": len(rows),
                "minimum_selected_tiles": min(int(row["selected_tiles"]) for row in rows),
                "maximum_selected_tiles": max(int(row["selected_tiles"]) for row in rows),
                "minimum_cycle_reduction_percent": min(
                    float(row["cycle_reduction_percent"]) for row in rows
                ),
                "maximum_cycle_reduction_percent": max(
                    float(row["cycle_reduction_percent"]) for row in rows
                ),
                "minimum_axis_reduction_percent": min(
                    float(row["axis_byte_reduction_percent"]) for row in rows
                ),
                "maximum_axis_reduction_percent": max(
                    float(row["axis_byte_reduction_percent"]) for row in rows
                ),
                "all_exact": all(bool(row["exact"]) for row in rows),
            }
        )

    gates = {
        "all_canonical_organizations_physical": all(
            str(row["evidence"]).startswith("physical") for row in organizations
        ),
        "all_canonical_outputs_exact": all(bool(row["bit_exact"]) for row in paper["canonical_comparison"]),
        "global_mechanism_reduces_cycles": effects["global_closure_and_persistent_reuse"]["cycle_reduction_percent"] > 0.0,
        "global_mechanism_reduces_traffic": effects["global_closure_and_persistent_reuse"]["axis_reduction_percent"] > 0.0,
        "commit_outcomes_exact": bool(commit["gates"]["all_commit_outcomes_exact"]),
        "commit_adds_no_dsp_or_bram": (
            effects["private_atomic_commit"]["dsp_delta"] == 0
            and effects["private_atomic_commit"]["bram_delta"] == 0.0
        ),
        "controlled_geometry_suite_exact": bool(controlled["gates"]["mechanism_pass"]),
    }
    return {
        "schema_version": 2,
        "artifact": "sparse_architecture_ablation_v1",
        "decision": "accept_descriptive_organization_operating_points_for_arc_draft",
        "canonical_mask_hex": mask_hex,
        "organizations": organizations,
        "headline_operating_point_comparison": headline_operating_point_comparison,
        "mechanism_effects": effects,
        "resources": resources,
        "controlled_geometry_summary": controlled["summary"],
        "controlled_geometry_families": controlled_families,
        "gates": {**gates, "all_pass": all(gates.values())},
        "attribution_boundary": (
            "Exact union geometry isolates duplicate dependency positions. The routed "
            "global-closure engine necessarily couples closure with persistent traversal, "
            "clock, resources, routing, and memory organization, so its physical counters "
            "describe combined operating points rather than elapsed-time acceleration or "
            "an isolated marginal mechanism effect."
        ),
    }


# Render the causal rows and claim boundary for human review.
def render_markdown(result: dict[str, object]) -> str:
    """Return realized organization operating points as a compact report."""

    rows = [
        f"| {row['organization']} | {row['cycles']:,} | {row['clock_mhz']:.3f} | "
        f"{row['cycle_derived_compute_ms']:.5f} | {row['axis_bytes']:,} | "
        f"{row['luts']:,} | {row['registers']:,} | {row['bram_tiles']:.1f} | {row['dsps']} |"
        for row in result["organizations"]
    ]
    family_rows = [
        f"| {row['family']} | {row['minimum_selected_tiles']}--{row['maximum_selected_tiles']} | "
        f"{row['minimum_cycle_reduction_percent']:.2f}--{row['maximum_cycle_reduction_percent']:.2f}% | "
        f"{row['minimum_axis_reduction_percent']:.2f}--{row['maximum_axis_reduction_percent']:.2f}% |"
        for row in result["controlled_geometry_families"]
    ]
    effects = result["mechanism_effects"]
    headline = result["headline_operating_point_comparison"]
    return "\n".join(
        [
            "# Sparse Architecture Realized Organization Operating Points",
            "",
            "| Organization | Cycles | MHz | Cycles/clock ms | AXI bytes | LUT | FF | BRAM | DSP |",
            "|---|---:|---:|---:|---:|---:|---:|---:|---:|",
            *rows,
            "",
            f"Independent and persistent operating points are {headline['independent_cycles']:,} cycles at "
            f"{headline['independent_clock_mhz']:.3f} MHz ({headline['independent_cycle_derived_compute_ms']:.5f} ms) "
            f"and {headline['persistent_cycles']:,} cycles at {headline['persistent_clock_mhz']:.3f} MHz "
            f"({headline['persistent_cycle_derived_compute_ms']:.5f} ms), respectively. The "
            f"{headline['cycle_reduction_percent']:.2f}% counter reduction is not an elapsed-time speedup.",
            f"The persistent operating point records {headline['axis_reduction_percent']:.2f}% fewer AXI bytes. "
            f"Rectangle and persistent transitions remain coupled organization comparisons.",
            f"Exact union geometry removes {effects['exact_union_geometry']['duplicate_dependency_reduction_percent']:.2f}% duplicated active positions.",
            f"Same-clock commit service overhead is {effects['private_atomic_commit']['service_overhead_percent']:.4f}% with "
            f"{effects['private_atomic_commit']['logic_lut_delta']:+d} LUTs, "
            f"{effects['private_atomic_commit']['register_delta']:+d} registers, no DSPs, and no BRAM.",
            "",
            "| Controlled family | Tiles | Cycle reduction | AXI reduction |",
            "|---|---:|---:|---:|",
            *family_rows,
            "",
            f"**Boundary:** {result['attribution_boundary']}",
            "",
        ]
    )


# Emit the two paper tables without hiding the commit counter caveat.
def render_latex(result: dict[str, object]) -> str:
    """Return publication-ready mechanism and commit-overhead tables."""

    labels = {
        "independent_jobs": "Independent",
        "rectangle_compaction": "Rectangle",
        "global_closure_persistent": "Persistent",
        "complete_commit_safe": "+ commit",
    }
    rows = [
        f"{labels[row['organization']]} & {row['cycles'] / 1e6:.3f} & "
        f"{row['clock_mhz']:.1f} & {row['cycle_derived_compute_ms']:.3f} & "
        f"{row['axis_bytes'] / 1e6:.3f} & {row['luts']:,} & "
        f"{row['registers']:,} & {row['bram_tiles']:.1f} & {row['dsps']} \\\\"
        for row in result["organizations"]
    ]
    commit = result["mechanism_effects"]["private_atomic_commit"]
    return "\n".join(
        [
            "% Generated by analyze_sparse_architecture_ablation.py.",
            "\\begin{table}[!htbp]",
            "\\centering",
            "\\caption{Coupled routed operating points for the canonical 17-tile request. Time is cycles divided by each row's realized clock; it is not a matched-build speedup. Resource and memory differences prevent isolated marginal attribution.}",
            "\\label{tab:organization-operating-points}",
            "\\small",
            "\\setlength{\\tabcolsep}{2.6pt}",
            "\\begin{tabular}{lrrrrrrrr}",
            "\\toprule",
            "Org. & Mcyc. & MHz & ms & AXI MB & LUT & FF & BRAM & DSP \\\\ \\midrule",
            *rows,
            "\\bottomrule",
            "\\end{tabular}",
            "\\end{table}",
            "\\noindent\\textbf{Separate 50-MHz builds:} Mask-only and "
            f"commit-safe DMA-trigger-to-completion means are {commit['mask_only_service_ms_50mhz']:.3f} and "
            f"{commit['commit_safe_service_ms_50mhz']:.3f} ms. The latter build uses an additional "
            f"{commit['logic_lut_delta']} LUTs and {commit['register_delta']} registers, "
            "with no additional DSP or BRAM. This is not an isolated publication-overhead "
            "measurement or complete application latency. Cycle counters use different terminal boundaries.",
            "",
        ]
    )


# Keep mask shape visible in the paper instead of reducing the controlled suite
# to one overall minimum/maximum range. These rows are generated from the same
# physical captures and exactness gates as the main mechanism table.
def render_geometry_latex(result: dict[str, object]) -> str:
    """Return a compact physical mask-family sensitivity table."""

    labels = {
        "adversarial_checkerboard": "Checkerboard",
        "clustered_rectangles": "Clustered",
        "deadline_truncated_prefix": "Deadline prefix",
        "moving_disocclusion_band": "Motion band",
        "scattered_random": "Scattered",
    }
    rows = []
    for row in result["controlled_geometry_families"]:
        rows.append(
            f"{labels[row['family']]} & "
            f"{row['minimum_selected_tiles']}--{row['maximum_selected_tiles']} & "
            f"{row['minimum_cycle_reduction_percent']:.2f}--"
            f"{row['maximum_cycle_reduction_percent']:.2f} & "
            f"{row['minimum_axis_reduction_percent']:.2f}--"
            f"{row['maximum_axis_reduction_percent']:.2f} \\\\"
        )
    return "\n".join(
        [
            "% Generated by analyze_sparse_architecture_ablation.py.",
            "\\begin{table}[t]",
            "\\centering",
            "\\caption{Physical sensitivity to sparse-mask geometry (percent saved).}",
            "\\label{tab:mask-geometry-sensitivity}",
            "\\resizebox{\\columnwidth}{!}{%",
            "\\begin{tabular}{lrrr}",
            "\\toprule",
            "Family & Tiles & Cycles & AXI bytes \\\\ \\midrule",
            *rows,
            "\\bottomrule",
            "\\end{tabular}}",
            "\\end{table}",
            "",
        ]
    )


# Expose every evidence input so the ablation remains replayable.
def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    """Parse physical inputs and report destinations."""

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--paper", type=Path, default=DEFAULT_PAPER)
    parser.add_argument("--hierarchical", type=Path, default=DEFAULT_HIERARCHICAL)
    parser.add_argument("--balanced", type=Path, default=DEFAULT_BALANCED)
    parser.add_argument("--commit", type=Path, default=DEFAULT_COMMIT)
    parser.add_argument("--commit-manifest", type=Path, default=DEFAULT_COMMIT_MANIFEST)
    parser.add_argument("--controlled", type=Path, default=DEFAULT_CONTROLLED)
    parser.add_argument("--output-json", type=Path, default=DEFAULT_JSON)
    parser.add_argument("--output-markdown", type=Path, default=DEFAULT_MARKDOWN)
    parser.add_argument("--output-latex", type=Path, default=DEFAULT_LATEX)
    parser.add_argument(
        "--output-geometry-latex", type=Path, default=DEFAULT_GEOMETRY_LATEX
    )
    return parser.parse_args(argv)


# Publish the ablation only when every physical and exactness gate passes.
def main(argv: Sequence[str] | None = None) -> int:
    """Analyze tracked evidence and write JSON, Markdown, and LaTeX together."""

    args = parse_args(argv)
    result = analyze(
        load_report(args.paper),
        load_report(args.hierarchical),
        load_report(args.balanced),
        load_report(args.commit),
        load_report(args.commit_manifest),
        load_report(args.controlled),
    )
    for path in (
        args.output_json,
        args.output_markdown,
        args.output_latex,
        args.output_geometry_latex,
    ):
        path.parent.mkdir(parents=True, exist_ok=True)
    args.output_json.write_text(json.dumps(result, indent=2) + "\n", encoding="ascii")
    args.output_markdown.write_text(render_markdown(result), encoding="ascii")
    args.output_latex.write_text(render_latex(result), encoding="ascii")
    args.output_geometry_latex.write_text(
        render_geometry_latex(result), encoding="ascii"
    )
    if not result["gates"]["all_pass"]:
        raise RuntimeError("sparse architecture ablation gate failed")
    print("SPARSE_ARCHITECTURE_ABLATION_PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
