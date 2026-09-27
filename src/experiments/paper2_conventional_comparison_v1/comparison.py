"""Fair conventional fusion/halo baselines for Paper 2's frozen integer graph.

Counts are logical requirements, NOT cycle or FPGA resource predictions.
All organizations may keep weights and inter-layer activations on chip. The
cached-union envelope prices a legal full-width line-buffer payload, but does
not assert free sparse discovery, banking, control, or zero-latency traversal.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import hashlib
import json
import math

import numpy as np


ROOT = Path(__file__).resolve().parents[3]
WEIGHTS = ROOT / "fpga/generated/sparse_refinement_accelerator_v1/student_npu_w24/espcn_fpga_student_weights_pkg.sv"
MASKS = ROOT / "configs/sparse_controlled_mask_suite_v1.jsonl"
CHANNELS = (3, 24, 24, 12)
LANES = (2, 12, 6)


@dataclass(frozen=True, order=True)
class Rect:
    y0: int
    x0: int
    y1: int
    x1: int

    @property
    def area(self) -> int:
        return max(0, self.y1 - self.y0) * max(0, self.x1 - self.x0)

    def expand(self, radius: int, height: int, width: int) -> "Rect":
        return Rect(max(0, self.y0-radius), max(0, self.x0-radius),
                    min(height, self.y1+radius), min(width, self.x1+radius))


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def rectangles(indices: list[int], *, tile_h: int = 60, tile_w: int = 64,
               rows: int = 6, cols: int = 10, mode: str = "tiles") -> list[Rect]:
    if len(indices) != len(set(indices)) or any(i < 0 or i >= rows*cols for i in indices):
        raise ValueError("indices must be distinct valid tiles")
    enabled = set(indices)
    if mode == "tiles":
        spans = [(i//cols, i%cols, i%cols+1) for i in sorted(enabled)]
    else:
        spans = []
        for y in range(rows):
            x = 0
            while x < cols:
                if y*cols+x not in enabled:
                    x += 1
                    continue
                start = x
                while x < cols and y*cols+x in enabled:
                    x += 1
                spans.append((y, start, x))
        if mode not in ("row_runs", "merged_rectangles"):
            raise ValueError("unknown rectangular organization")
    result: list[Rect] = []
    for y, x0, x1 in spans:
        rect = Rect(y*tile_h, x0*tile_w, (y+1)*tile_h, x1*tile_w)
        merge = next((j for j, p in enumerate(result)
                      if p.y1 == rect.y0 and p.x0 == rect.x0 and p.x1 == rect.x1), None)
        if mode == "merged_rectangles" and merge is not None:
            p = result[merge]
            result[merge] = Rect(p.y0, p.x0, rect.y1, p.x1)
        else:
            result.append(rect)
    return result


def union_mask(rects: list[Rect], radius: int, height: int, width: int) -> np.ndarray:
    result = np.zeros((height, width), dtype=bool)
    for rect in rects:
        r = rect.expand(radius, height, width)
        result[r.y0:r.y1, r.x0:r.x1] = True
    return result


def line_buffer_payload(widths: tuple[int, int, int]) -> dict:
    # Two retained rows per convolution input; 3x3 registered window included.
    # Extra FIFOs, banking replication, weights, accumulators and metadata excluded.
    rows = sum(2*w*c for w, c in zip(widths, CHANNELS[:3], strict=True))
    windows = 9 * sum(CHANNELS[:3])
    return {"row_payload_bytes": rows, "window_payload_bytes": windows,
            "activation_payload_bytes": rows+windows,
            "not_physical_bram_or_lut_estimate": True}


def organization_cost(rects: list[Rect], *, height: int, width: int,
                      shared_halos: bool = False) -> dict:
    areas = [int(union_mask(rects, r, height, width).sum()) if shared_halos
             else sum(rect.expand(r, height, width).area for rect in rects)
             for r in (3, 2, 1, 0)]
    macs = sum(areas[layer+1]*CHANNELS[layer]*CHANNELS[layer+1]*9 for layer in range(3))
    # Lower bounds on arithmetic issue by each independently pipelined stage.
    stage_issue = [areas[l+1]*CHANNELS[l]*math.ceil(CHANNELS[l+1]/LANES[l]) for l in range(3)]
    if shared_halos:
        widths = (width, width, width) if rects else (0, 0, 0)
    else:
        widths = tuple(max((r.expand(3-l, height, width).x1-r.expand(3-l, height, width).x0
                            for r in rects), default=0) for l in range(3))
    store = line_buffer_payload(widths)
    if not rects:
        store = {k: (v if isinstance(v, bool) else 0) for k, v in store.items()}
    selected = int(union_mask(rects, 0, height, width).sum())
    return {
        "regions": len(rects), "layer_positions_input_conv1_conv2_conv3": areas,
        "macs": macs, "arithmetic_issue_cycles_per_stage_lower_bound": stage_issue,
        "pipeline_arithmetic_lower_bound_cycles": max(stage_issue),
        "input_axi_bytes_logical": areas[0]*4,
        "selected_private_output_axi_bytes_logical": selected*16,
        "intermediate_feature_ddr_bytes_required": 0,
        "cold_weight_payload_bytes_common": 936*9+60*4,
        "private_residual_buffer_bytes_common": selected*16,
        "software_publication_permitted": True,
        "full_frame_input_positions_current_persistent": height*width if rects else 0,
        "full_frame_layer_positions_current_persistent": [height*width]*3 if rects else [0]*3,
        **store,
    }


def compile_cases() -> list[dict]:
    frozen = [json.loads(line) for line in MASKS.read_text().splitlines() if line.strip()]
    cases = [{"sequence_id": "empty_control", "frame_id": 0, "selected_tile_indices": []},
             {"sequence_id": "dense_control", "frame_id": 0, "selected_tile_indices": list(range(60))}]+frozen
    output = []
    for item in cases:
        indices = item["selected_tile_indices"]
        organizations = {}
        for mode in ("tiles", "row_runs", "merged_rectangles"):
            regs = rectangles(indices, mode=mode)
            organizations[mode] = organization_cost(regs, height=360, width=640)
            organizations[mode]["rectangles_y0_x0_y1_x1"] = [[r.y0, r.x0, r.y1, r.x1] for r in regs]
        regions = rectangles(indices)
        union = organization_cost(regions, height=360, width=640, shared_halos=True)
        organizations["cached_union_envelope"] = union
        tile = organizations["tiles"]
        merged = organizations["merged_rectangles"]
        def savings(base, target):
            return 100*(base-target)/base if base else 0.0
        output.append({
            "name": f"{item['sequence_id']}_{item['frame_id']}", "selected_tiles": len(indices),
            "selected_tile_indices": indices, "organizations": organizations,
            "union_macs_reduction_vs_tiles_percent": savings(tile["macs"], union["macs"]),
            "union_macs_reduction_vs_merged_percent": savings(merged["macs"], union["macs"]),
            "union_input_reduction_vs_merged_percent": savings(merged["input_axi_bytes_logical"], union["input_axi_bytes_logical"]),
            "input_scan_positions_skippable_if_exact_sparse_traversal": 360*640-union["layer_positions_input_conv1_conv2_conv3"][0],
            "scan_position_reduction_is_not_elapsed_time_speedup": True,
        })
    return output


def dense_layers(image: np.ndarray, model) -> list[np.ndarray]:
    from src.hardware.experiment133.reference_sparse_distilled_same_bitstream_133 import conv3x3
    layers = [np.asarray(image, dtype=np.int8)]
    for layer in range(3):
        layers.append(conv3x3(layers[-1], model.weights[layer], model.biases[layer], layer < 2))
    return layers


def fused_region(image: np.ndarray, model, target: Rect) -> np.ndarray:
    """Conventional halo-fused execution with proper global image boundaries.

    Each layer trims the no-longer-needed outer halo before the next. Thus no
    intermediate is written off chip in the architecture being modeled. This
    software oracle still materializes arrays and does not model cycle timing.
    """
    from src.hardware.experiment133.reference_sparse_distilled_same_bitstream_133 import conv3x3
    height, width = image.shape[:2]
    current_box = target.expand(3, height, width)
    current = image[current_box.y0:current_box.y1, current_box.x0:current_box.x1].copy()
    for layer in range(3):
        full = conv3x3(current, model.weights[layer], model.biases[layer], layer < 2)
        next_box = target.expand(2-layer, height, width)
        current = full[next_box.y0-current_box.y0:next_box.y1-current_box.y0,
                       next_box.x0-current_box.x0:next_box.x1-current_box.x0].copy()
        current_box = next_box
    return current


class PrivatePublication:
    """Conventional software-owned private slot reference, not board validation."""
    def __init__(self, public: np.ndarray):
        self.public = public.copy()
        self.private = None
        self.identity = None

    def begin(self, identity: tuple[int, int]) -> None:
        self.private = None
        self.identity = identity

    def complete(self, identity: tuple[int, int], result: np.ndarray, *, now: int,
                 deadline: int, canceled: bool, selected: np.ndarray) -> bool:
        if identity != self.identity or canceled or now > deadline:
            self.private = None
            return False
        if result.shape != self.public.shape or selected.shape != result.shape[:2]:
            raise ValueError("malformed result/selection")
        self.private = result.copy()
        replacement = self.public.copy()
        replacement[selected] = self.private[selected]
        self.public = replacement
        self.private = None
        self.identity = None
        return True


def report() -> dict:
    rows = compile_cases()
    cases = [r for r in rows if r["name"] not in ("empty_control_0", "dense_control_0")]
    return {
        "schema_version": 1, "evidence_scope": "engineering_analytical_costs_not_physical_performance",
        "frozen_input_hashes": {str(p.relative_to(ROOT)).replace("\\", "/"): digest(p) for p in (MASKS, WEIGHTS)},
        "model": {"channels": CHANNELS, "kernel": [3, 3], "scale": 2, "layer_issue_lanes": LANES,
                  "halo_radii_input_conv1_conv2_conv3": [3, 2, 1, 0]},
        "fairness": ["identical trained integer network and selected outputs", "fusion and legal halo reuse allowed",
                     "zero mandatory intermediate DDR for conventional comparator", "same private output and publication semantics",
                     "weights and result payloads common", "no CPU/GPU timing used as FPGA performance"],
        "excluded_costs": ["planner and mask discovery", "extra control/metadata", "banking/port replication",
                           "pipeline bubbles and reset", "host/DMA setup and publication time", "routing and achieved clock"],
        "summary": {
            "cases": len(rows), "controlled_frozen_cases": len(cases),
            "median_union_macs_reduction_vs_tiles_percent": float(np.median([r["union_macs_reduction_vs_tiles_percent"] for r in cases])),
            "median_union_macs_reduction_vs_merged_percent": float(np.median([r["union_macs_reduction_vs_merged_percent"] for r in cases])),
            "max_union_macs_reduction_vs_merged_percent": max(r["union_macs_reduction_vs_merged_percent"] for r in cases),
            "cached_union_is_lower_envelope_not_measured_implementation": True,
        },
        "cases": rows,
    }
