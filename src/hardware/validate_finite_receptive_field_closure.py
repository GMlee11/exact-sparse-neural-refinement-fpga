"""Validate reverse closure on a second finite-receptive-field graph.

Experiment 127 is deliberately synthetic. It exercises a branched residual
topology with a dilated convolution and checks the generated closure against
independent exhaustive support-path enumeration, dense integer execution, and
per-input removal witnesses. It does not simulate or route RTL.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Iterable, Mapping, Sequence

import yaml


ROOT = Path(__file__).resolve().parents[2]
DEFAULT_CONFIG = ROOT / "configs/finite_receptive_field_closure_validation_v1.yaml"

Position = tuple[int, int]

SUPPORTS: dict[str, tuple[Position, ...]] = {
    "pointwise": ((0, 0),),
    "square_3x3": tuple(
        (dy, dx) for dy in range(-1, 2) for dx in range(-1, 2)
    ),
    "dilated_3x3_d2": tuple(
        (dy, dx) for dy in (-2, 0, 2) for dx in (-2, 0, 2)
    ),
}


def sha256_file(path: Path) -> str:
    """Return a stable lowercase digest for the experiment contract."""

    return hashlib.sha256(path.read_bytes()).hexdigest()


def inside(position: Position, width: int, height: int) -> bool:
    """Return whether one `(y, x)` coordinate lies inside the test grid."""

    y, x = position
    return 0 <= y < height and 0 <= x < width


def preimage(
    successors: Iterable[Position],
    support: Sequence[Position],
    width: int,
    height: int,
) -> set[Position]:
    """Return exact predecessor coordinates consumed by successor positions."""

    return {
        (y + dy, x + dx)
        for y, x in successors
        for dy, dx in support
        if inside((y + dy, x + dx), width, height)
    }


def influence(
    predecessors: Iterable[Position],
    support: Sequence[Position],
    width: int,
    height: int,
) -> set[Position]:
    """Return successor coordinates influenced by predecessor positions."""

    return {
        (y - dy, x - dx)
        for y, x in predecessors
        for dy, dx in support
        if inside((y - dy, x - dx), width, height)
    }


def pattern_positions(label: str, width: int, height: int) -> set[Position]:
    """Construct one deterministic synthetic output request."""

    center = (height // 2, width // 2)
    patterns = {
        "center_singleton": {center},
        "corner_singleton": {(0, 0)},
        "opposite_corners": {(0, 0), (height - 1, width - 1)},
        "fragmented_triplet": {
            (1, width - 2),
            center,
            (height - 2, 1),
        },
        "center_block": {
            (y, x)
            for y in range(center[0] - 1, center[0] + 2)
            for x in range(center[1] - 1, center[1] + 2)
        },
        "edge_band": {(0, x) for x in range(0, width, 2)},
        "checkerboard_sparse": {
            (y, x)
            for y in range(height)
            for x in range(width)
            if (x + y) % 4 == 0
        },
        "full_output": {
            (y, x) for y in range(height) for x in range(width)
        },
    }
    if label not in patterns:
        raise ValueError(f"unknown deterministic pattern: {label}")
    return patterns[label]


def edge_support(edge: Mapping[str, object]) -> tuple[Position, ...]:
    """Resolve and validate one named exact operator support."""

    name = str(edge["support"])
    if name not in SUPPORTS:
        raise ValueError(f"unknown support: {name}")
    support = SUPPORTS[name]
    measured_radius = max(max(abs(dy), abs(dx)) for dy, dx in support)
    if measured_radius != int(edge["radius"]):
        raise ValueError(f"support/radius mismatch for {name}")
    return support


def reverse_closure(
    selected: set[Position],
    topology: Mapping[str, object],
    width: int,
    height: int,
) -> dict[str, set[Position]]:
    """Generate exact node requirements by reverse support propagation."""

    order = [str(node) for node in topology["topological_order"]]
    required = {node: set() for node in order}
    required["output"] = set(selected)
    incoming: dict[str, list[Mapping[str, object]]] = {node: [] for node in order}
    for edge in topology["edges"]:
        incoming[str(edge["successor"])].append(edge)

    for successor in reversed(order[1:]):
        for edge in incoming[successor]:
            predecessor = str(edge["predecessor"])
            required[predecessor].update(
                preimage(
                    required[successor],
                    edge_support(edge),
                    width,
                    height,
                )
            )
    return required


def brute_force_support_closure(
    selected: set[Position],
    topology: Mapping[str, object],
    width: int,
    height: int,
) -> dict[str, set[Position]]:
    """Enumerate every node coordinate that has a support path to selection."""

    order = [str(node) for node in topology["topological_order"]]
    outgoing: dict[str, list[Mapping[str, object]]] = {node: [] for node in order}
    for edge in topology["edges"]:
        outgoing[str(edge["predecessor"])].append(edge)

    result = {node: set() for node in order}
    grid = [(y, x) for y in range(height) for x in range(width)]
    for start_index, node in enumerate(order):
        for position in grid:
            active = {name: set() for name in order}
            active[node].add(position)
            for current in order[start_index:-1]:
                for edge in outgoing[current]:
                    successor = str(edge["successor"])
                    active[successor].update(
                        influence(
                            active[current],
                            edge_support(edge),
                            width,
                            height,
                        )
                    )
            if active["output"] & selected:
                result[node].add(position)
    return result


def enumerate_input_output_support_paths(
    selected: set[Position],
    topology: Mapping[str, object],
    width: int,
    height: int,
) -> list[dict[str, object]]:
    """Enumerate exact support-offset paths from graph input to selection."""

    order = [str(node) for node in topology["topological_order"]]
    incoming: dict[str, list[Mapping[str, object]]] = {node: [] for node in order}
    for edge in topology["edges"]:
        incoming[str(edge["successor"])].append(edge)
    for edges in incoming.values():
        edges.sort(
            key=lambda edge: (
                str(edge["predecessor"]),
                str(edge["successor"]),
                str(edge["support"]),
            )
        )

    paths: list[dict[str, object]] = []

    def visit(
        node: str,
        position: Position,
        output_position: Position,
        reverse_steps: list[dict[str, object]],
    ) -> None:
        if node == "input":
            forward_steps = list(reversed(reverse_steps))
            displacement = max(
                abs(position[0] - output_position[0]),
                abs(position[1] - output_position[1]),
            )
            paths.append(
                {
                    "input_position": list(position),
                    "output_position": list(output_position),
                    "chebyshev_displacement": displacement,
                    "path_nodes": ["input"]
                    + [str(step["successor"]) for step in forward_steps],
                    "edges": forward_steps,
                }
            )
            return

        for edge in incoming[node]:
            predecessor = str(edge["predecessor"])
            successor = str(edge["successor"])
            for dy, dx in sorted(edge_support(edge)):
                predecessor_position = (position[0] + dy, position[1] + dx)
                if not inside(predecessor_position, width, height):
                    continue
                step = {
                    "predecessor": predecessor,
                    "successor": successor,
                    "preimage_offset": [dy, dx],
                    "predecessor_position": list(predecessor_position),
                    "successor_position": list(position),
                }
                visit(
                    predecessor,
                    predecessor_position,
                    output_position,
                    reverse_steps + [step],
                )

    for output_position in sorted(selected):
        visit("output", output_position, output_position, [])
    return paths


def input_values(width: int, height: int) -> dict[Position, int]:
    """Create nonzero deterministic integers for removal-witness checks."""

    return {
        (y, x): 1 + ((y * width + x) % 17)
        for y in range(height)
        for x in range(width)
    }


def convolve(
    source: Mapping[Position, int],
    positions: Iterable[Position],
    support: Sequence[Position],
    bias: int,
) -> dict[Position, int]:
    """Evaluate a positive integer convolution with zero boundary fill."""

    return {
        position: bias
        + sum(
            source.get((position[0] + dy, position[1] + dx), 0)
            for dy, dx in support
        )
        for position in positions
    }


def execute(
    required: Mapping[str, set[Position]],
    topology: Mapping[str, object],
    values: Mapping[Position, int],
) -> dict[str, dict[Position, int]]:
    """Execute the branched integer graph only at named required positions."""

    edge_lookup = {
        (str(edge["predecessor"]), str(edge["successor"])): edge_support(edge)
        for edge in topology["edges"]
    }
    nodes: dict[str, dict[Position, int]] = {
        "input": {position: values[position] for position in required["input"] if position in values}
    }
    nodes["conv_a"] = convolve(
        nodes["input"],
        required["conv_a"],
        edge_lookup[("input", "conv_a")],
        bias=1,
    )
    nodes["conv_b_dilated"] = convolve(
        nodes["conv_a"],
        required["conv_b_dilated"],
        edge_lookup[("conv_a", "conv_b_dilated")],
        bias=2,
    )
    nodes["residual_add"] = {
        position: nodes["conv_b_dilated"].get(position, 0)
        + nodes["input"].get(position, 0)
        for position in required["residual_add"]
    }
    nodes["output"] = convolve(
        nodes["residual_add"],
        required["output"],
        edge_lookup[("residual_add", "output")],
        bias=3,
    )
    return nodes


def output_digest(values: Mapping[Position, int]) -> str:
    """Hash sorted selected integer outputs for compact reproducibility."""

    payload = [[y, x, values[(y, x)]] for y, x in sorted(values)]
    return hashlib.sha256(
        json.dumps(payload, separators=(",", ":")).encode("ascii")
    ).hexdigest()


def radius_path_exercised(
    rows: Sequence[Mapping[str, object]], expected_radius: int
) -> bool:
    """Require an enumerated coordinate witness at the exact target radius."""

    for row in rows:
        if row["maximum_input_to_output_chebyshev_displacement"] != expected_radius:
            continue
        witness = row["maximum_displacement_witness"]
        input_position = witness["input_position"]
        output_position = witness["output_position"]
        measured = max(
            abs(int(input_position[0]) - int(output_position[0])),
            abs(int(input_position[1]) - int(output_position[1])),
        )
        if (
            witness["chebyshev_displacement"] == expected_radius
            and measured == expected_radius
            and witness["edges"]
        ):
            return True
    return False


def analyze(config_path: Path = DEFAULT_CONFIG) -> dict[str, object]:
    """Run all Experiment-127 gates and return a machine-readable report."""

    config = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    width = int(config["grid"]["width"])
    height = int(config["grid"]["height"])
    topology = config["topology"]
    full_grid = {(y, x) for y in range(height) for x in range(width)}
    dense_required = {node: set(full_grid) for node in topology["nodes"]}
    values = input_values(width, height)
    dense = execute(dense_required, topology, values)

    rows: list[dict[str, object]] = []
    for label in config["patterns"]:
        selected = pattern_positions(str(label), width, height)
        required = reverse_closure(selected, topology, width, height)
        brute_force = brute_force_support_closure(
            selected, topology, width, height
        )
        support_paths = enumerate_input_output_support_paths(
            selected, topology, width, height
        )
        maximum_displacement = max(
            int(path["chebyshev_displacement"]) for path in support_paths
        )
        maximum_witness = min(
            (
                path
                for path in support_paths
                if path["chebyshev_displacement"] == maximum_displacement
            ),
            key=lambda path: json.dumps(path, sort_keys=True),
        )
        closure_exact = all(
            required[node] == brute_force[node] for node in topology["nodes"]
        )
        sparse = execute(required, topology, values)
        output_exact = all(
            sparse["output"][position] == dense["output"][position]
            for position in selected
        )

        removal_witnesses = 0
        for removed in required["input"]:
            altered_values = dict(values)
            altered_values.pop(removed)
            altered = execute(required, topology, altered_values)
            if any(
                altered["output"][position] != dense["output"][position]
                for position in selected
            ):
                removal_witnesses += 1

        rows.append(
            {
                "pattern": label,
                "selected_outputs": len(selected),
                "required_positions": {
                    node: len(required[node]) for node in topology["nodes"]
                },
                "closure_matches_support_paths": closure_exact,
                "selected_outputs_exact": output_exact,
                "required_input_positions": len(required["input"]),
                "input_removal_witnesses": removal_witnesses,
                "all_required_inputs_have_witnesses": (
                    removal_witnesses == len(required["input"])
                ),
                "enumerated_input_output_support_paths": len(support_paths),
                "maximum_input_to_output_chebyshev_displacement": (
                    maximum_displacement
                ),
                "maximum_displacement_witness": maximum_witness,
                "selected_output_sha256": output_digest(sparse["output"]),
            }
        )

    expected_count = int(config["acceptance"]["exact_pattern_count"])
    maximum_expected_radius = int(
        config["acceptance"]["maximum_expected_input_radius"]
    )
    required_attained_radius = int(
        config["acceptance"]["required_attained_input_output_radius"]
    )
    gates = {
        "pattern_count_exact": len(rows) == expected_count,
        "closure_matches_exhaustive_support_paths": all(
            bool(row["closure_matches_support_paths"]) for row in rows
        ),
        "selected_outputs_match_dense_integer_reference": all(
            bool(row["selected_outputs_exact"]) for row in rows
        ),
        "every_required_input_has_removal_witness": all(
            bool(row["all_required_inputs_have_witnesses"]) for row in rows
        ),
        "all_support_path_displacements_within_configured_radius": all(
            int(row["maximum_input_to_output_chebyshev_displacement"])
            <= maximum_expected_radius
            for row in rows
        ),
        "radius_four_path_exercised": (
            required_attained_radius == 4
            and radius_path_exercised(rows, required_attained_radius)
        ),
        "no_images_or_selector_used": bool(
            config["evidence_boundary"]["synthetic_integer_inputs_only"]
            and not config["evidence_boundary"]["sealed_or_renderer_images_used"]
            and not config["evidence_boundary"]["selector_tuned"]
        ),
    }
    if not all(gates.values()):
        failed = ", ".join(name for name, passed in gates.items() if not passed)
        raise RuntimeError(f"Experiment 127 failed: {failed}")

    attaining_rows = [
        row
        for row in rows
        if row["maximum_input_to_output_chebyshev_displacement"]
        == required_attained_radius
    ]
    radius_witness = dict(attaining_rows[0]["maximum_displacement_witness"])
    radius_witness["pattern"] = attaining_rows[0]["pattern"]

    return {
        "schema_version": 1,
        "artifact": "finite_receptive_field_closure_validation_v1",
        "experiment_id": 127,
        "decision": "accept_second_topology_software_closure_contract",
        "config_sha256": sha256_file(config_path),
        "topology": {
            "nodes": topology["nodes"],
            "edges": topology["edges"],
            "maximum_path_radius": int(
                config["acceptance"]["maximum_expected_input_radius"]
            ),
        },
        "support_path_displacement": {
            "maximum_expected_radius": maximum_expected_radius,
            "required_attained_radius": required_attained_radius,
            "maximum_observed_displacement": max(
                int(row["maximum_input_to_output_chebyshev_displacement"])
                for row in rows
            ),
            "attaining_patterns": [row["pattern"] for row in attaining_rows],
            "exact_radius_witness": radius_witness,
        },
        "patterns": rows,
        "gates": gates,
        "evidence_boundary": config["evidence_boundary"],
        "interpretation": (
            "The reverse-support abstraction transfers to one deterministic "
            "branched finite-receptive-field topology. This is synthetic "
            "software evidence, not RTL simulation, routing, or a second "
            "physical accelerator."
        ),
    }


def render_markdown(report: Mapping[str, object]) -> str:
    """Render the compact reviewer-facing Experiment-127 result."""

    lines = [
        "# Finite-Receptive-Field Closure Validation V1",
        "",
        "Experiment 127 checks a branched residual topology with a dilated convolution and skip-add path. It uses deterministic synthetic integers only.",
        "",
        "| Pattern | Selected outputs | Input closure | Max displacement | Closure paths | Dense/sparse | Removal witnesses |",
        "|---|---:|---:|---:|---:|---:|---:|",
    ]
    for row in report["patterns"]:
        lines.append(
            f"| `{row['pattern']}` | {row['selected_outputs']} | "
            f"{row['required_input_positions']} | "
            f"{row['maximum_input_to_output_chebyshev_displacement']} | "
            f"{'PASS' if row['closure_matches_support_paths'] else 'FAIL'} | "
            f"{'PASS' if row['selected_outputs_exact'] else 'FAIL'} | "
            f"{row['input_removal_witnesses']}/{row['required_input_positions']} |"
        )
    radius = report["support_path_displacement"]
    witness = radius["exact_radius_witness"]
    edge_offsets = "; ".join(
        f"{edge['predecessor']}->{edge['successor']} {edge['preimage_offset']}"
        for edge in witness["edges"]
    )
    lines.extend(
        [
            "",
            "## Gates",
            "",
            *[
                f"- `{name}`: **{'PASS' if passed else 'FAIL'}**"
                for name, passed in report["gates"].items()
            ],
            "",
            "## Exact Radius-Four Support-Path Witness",
            "",
            f"- Pattern: `{witness['pattern']}`",
            f"- Requested output: `{witness['output_position']}`",
            f"- Required input: `{witness['input_position']}`",
            f"- Chebyshev displacement: `{witness['chebyshev_displacement']}`",
            f"- Path: `{' -> '.join(witness['path_nodes'])}`",
            f"- Exact preimage offsets: `{edge_offsets}`",
            "",
            "## Boundary",
            "",
            report["interpretation"],
            "",
        ]
    )
    return "\n".join(lines)


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    """Parse deterministic config and output paths."""

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    parser.add_argument("--output-json", type=Path)
    parser.add_argument("--output-markdown", type=Path)
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    """Run Experiment 127 and write its two declared outputs."""

    args = parse_args(argv)
    config = yaml.safe_load(args.config.read_text(encoding="utf-8"))
    output_json = args.output_json or ROOT / config["outputs"]["json"]
    output_markdown = args.output_markdown or ROOT / config["outputs"]["markdown"]
    report = analyze(args.config)
    for path in (output_json, output_markdown):
        path.parent.mkdir(parents=True, exist_ok=True)
    output_json.write_text(
        json.dumps(report, indent=2) + "\n", encoding="utf-8", newline="\n"
    )
    output_markdown.write_text(
        render_markdown(report), encoding="utf-8", newline="\n"
    )
    print(
        "FINITE_RECEPTIVE_FIELD_CLOSURE_PASS "
        f"patterns={len(report['patterns'])} topology=branched_dilated_residual"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
