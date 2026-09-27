# Finite-Receptive-Field Closure Validation V1

Experiment 127 checks a branched residual topology with a dilated convolution and skip-add path. It uses deterministic synthetic integers only.

| Pattern | Selected outputs | Input closure | Max displacement | Closure paths | Dense/sparse | Removal witnesses |
|---|---:|---:|---:|---:|---:|---:|
| `center_singleton` | 1 | 81 | 4 | PASS | PASS | 81/81 |
| `corner_singleton` | 1 | 25 | 4 | PASS | PASS | 25/25 |
| `opposite_corners` | 2 | 50 | 4 | PASS | PASS | 50/50 |
| `fragmented_triplet` | 3 | 93 | 4 | PASS | PASS | 93/93 |
| `center_block` | 9 | 99 | 4 | PASS | PASS | 99/99 |
| `edge_band` | 6 | 55 | 4 | PASS | PASS | 55/55 |
| `checkerboard_sparse` | 25 | 99 | 4 | PASS | PASS | 99/99 |
| `full_output` | 99 | 99 | 4 | PASS | PASS | 99/99 |

## Gates

- `pattern_count_exact`: **PASS**
- `closure_matches_exhaustive_support_paths`: **PASS**
- `selected_outputs_match_dense_integer_reference`: **PASS**
- `every_required_input_has_removal_witness`: **PASS**
- `all_support_path_displacements_within_configured_radius`: **PASS**
- `radius_four_path_exercised`: **PASS**
- `no_images_or_selector_used`: **PASS**

## Exact Radius-Four Support-Path Witness

- Pattern: `center_singleton`
- Requested output: `[4, 5]`
- Required input: `[0, 1]`
- Chebyshev displacement: `4`
- Path: `input -> conv_a -> conv_b_dilated -> residual_add -> output`
- Exact preimage offsets: `input->conv_a [-1, -1]; conv_a->conv_b_dilated [-2, -2]; conv_b_dilated->residual_add [0, 0]; residual_add->output [-1, -1]`

## Boundary

The reverse-support abstraction transfers to one deterministic branched finite-receptive-field topology. This is synthetic software evidence, not RTL simulation, routing, or a second physical accelerator.
