# Historical Paper 2 Physical Evidence Index

This file maps the historical campaigns below to their evidence classes, raw captures, analyzers, and canonical JSON fields. The later P003/P005 same-image ROI confirmation and physical safety checks are separately indexed in artifact/paper2_arc/ROI_REPLAY.md. Physical, replayed, exact-geometry, and provisional estimates remain separate.

**Historical physical-output boundary.** The board rows indexed below verify checksums, selected-output lengths, counters, and terminal conditions; those historical output streams are not archived for independent bytewise replay. This limitation does not describe P003/P005: their predeclared selected-output byte samples and independent numerical replay are included separately. Software and RTL tests also compare selected bytes directly against the dense integer reference.

| Claim | Evidence class | Canonical result | Raw evidence |
|---|---|---|---|
| `persistent_vs_independent` | `physical_zybo_checksum_length_counters` | `results/tables/sparse_accelerator_paper_v1.json` | `fpga/docs/captures/sparse_refinement_accelerator_v1/physical_zybo_balanced_region.txt`<br>`fpga/docs/captures/sparse_refinement_accelerator_v1/hierarchical_mask_physical/physical_zybo_sparse_hierarchical.txt` |
| `persistent_vs_rectangle` | `physical_zybo_checksum_length_counters` | `results/tables/sparse_architecture_ablation_v1.json` | `fpga/docs/captures/sparse_refinement_accelerator_v1/physical_zybo_balanced_region.txt`<br>`fpga/docs/captures/sparse_refinement_accelerator_v1/hierarchical_mask_physical/physical_zybo_sparse_hierarchical.txt` |
| `same_bitstream_closure_retention_b030` | `physical_zybo_same_routed_build_checksum_length_counters` | `results/analysis/sparse_distilled_same_bitstream_b030_execution_factorial.json` | `fpga/docs/captures/paper2/experiment134/E134-B030/physical/uart_b030_raw.bin`<br>`fpga/docs/captures/paper2/experiment134/E134-B030/failure/reports/timing_summary_post_route.rpt`<br>`fpga/docs/captures/paper2/experiment134/E134-B030/failure/reports/utilization_post_route.rpt`<br>`fpga/docs/captures/paper2/experiment134/E134-B030/failure/reports/drc_post_route.rpt` |
| `exact_dependency_closure_geometry` | `exact_geometry_not_board_cycles` | `results/tables/sparse_architecture_ablation_v1.json` | N/A |
| `controlled_mask_geometry` | `physical_zybo_checksum_length_counters` | `results/tables/sparse_hierarchical_commit_controlled_masks_physical.json` | `fpga/docs/captures/sparse_refinement_accelerator_v2/hierarchical_commit_suite_controlled_masks_physical/physical_zybo_sparse_hierarchical_commit_suite.txt`<br>`fpga/docs/captures/sparse_refinement_accelerator_v2/hierarchical_commit_suite_controlled_masks_physical/route/timing_summary.txt`<br>`fpga/docs/captures/sparse_refinement_accelerator_v2/hierarchical_commit_suite_controlled_masks_physical/route/utilization.txt` |
| `private_atomic_commit` | `physical_zybo_same_clock_counters` | `results/tables/sparse_architecture_ablation_v1.json` | `fpga/docs/captures/sparse_refinement_accelerator_v2/hierarchical_commit_suite_controlled_masks_physical/physical_zybo_sparse_hierarchical_commit_suite.txt` |
| `independent_worklist_scaling` | `physical_zybo_checksum_length_counters_architecture_only` | `results/tables/sparse_independent_worklists_joined.json` | `fpga/docs/captures/sparse_refinement_accelerator_v2/hierarchical_commit_suite_independent_holdout_v1_physical/physical_zybo_sparse_hierarchical_commit_suite.txt`<br>`fpga/docs/captures/sparse_refinement_accelerator_v2/hierarchical_commit_suite_independent_holdout_v1_physical/route/timing_summary.txt`<br>`fpga/docs/captures/sparse_refinement_accelerator_v2/hierarchical_commit_suite_independent_holdout_v1_physical/route/utilization.txt` |
| `distinct_58p824_bitstream_identities` | `physical_zybo_route_reports` | `results/tables/paper2_physical_evidence_index.json` | `fpga/docs/captures/sparse_refinement_accelerator_v2/hierarchical_commit_suite_controlled_masks_physical/route/timing_summary.txt`<br>`fpga/docs/captures/sparse_refinement_accelerator_v2/hierarchical_commit_suite_controlled_masks_physical/route/utilization.txt`<br>`fpga/docs/captures/sparse_refinement_accelerator_v2/hierarchical_commit_suite_independent_holdout_v1_physical/route/timing_summary.txt`<br>`fpga/docs/captures/sparse_refinement_accelerator_v2/hierarchical_commit_suite_independent_holdout_v1_physical/route/utilization.txt` |
| `worklist_service_rate_not_dense_fps` | `physical_zybo_distinct_work_definitions` | `results/tables/paper2_physical_evidence_index.json` | `fpga/docs/captures/sparse_refinement_accelerator_v1/hierarchical_mask_physical/physical_zybo_sparse_hierarchical.txt`<br>`fpga/docs/captures/sparse_refinement_accelerator_v2/hierarchical_commit_suite_independent_holdout_v1_physical/physical_zybo_sparse_hierarchical_commit_suite.txt` |
| `deadline_trace_safety` | `deterministic_replay_from_physical_service_times` | `results/tables/sparse_deadline_trace_analysis.json` | `fpga/docs/captures/sparse_refinement_accelerator_v2/hierarchical_commit_suite_controlled_masks_physical/physical_zybo_sparse_hierarchical_commit_suite.txt` |
| `tang_control_portability` | `physical_tang_resource_scaled_control` | `results/tables/tang_sparse_commit_candidate_v1.json` | `fpga/docs/captures/paper2/tang_sparse_commit_candidate_v1/physical_capture.json` |
| `power_boundary` | `provisional_post_route_estimate` | `results/tables/sparse_postroute_power_estimate.json` | N/A |

## Canonical Coupled Operating Points

| Organization | Cycles | Realized clock | Cycles/clock elapsed | LUT | FF | BRAM | DSP | AXI bytes |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| Independent | 9,857,730 | 100.000 MHz | 98.57730 ms | 38,274 | 28,681 | 52.0 | 193 | 2,399,952 |
| Persistent mask-only | 4,922,897 | 50.000 MHz | 98.45794 ms | 44,408 | 26,056 | 3.5 | 180 | 1,322,256 |

The persistent row has 50.06% fewer cycles and 44.90% fewer AXI bytes, but only 0.11936 ms lower cycle-derived elapsed time. Because clock, routing, resources, and memory organization differ, this is not an observed wall-time speedup, a clock-normalized comparison, an area advantage, or an isolated mechanism effect. The BRAM difference is a property of the coupled memory organizations.

## B030 Same-Bitstream Controlled Companion

B030 runs 12 masks across four policy cells with 10 repetitions per cell on one routed 10-MHz design. All 480 rows pass checksum, length, counter, completion, and terminal invariants. The preregistered raw and normalized coverage, retention, and interaction medians are all zero because closure applies to 4/12 masks and retention to 5/12. Conditional closure reductions reach 65.38% and 59.64%; full-mask retention reaches 8.16%. This is opportunity-dependent same-build evidence, not universal acceleration or an area, energy, full-scale-throughput, external-AXI, or publication-safety claim.

## Independent-Worklist Headline

The independent architecture-only suite contains 15 sparse masks. Median physical cycle and AXI-byte reductions are 57.41% and 64.67%, and cycles versus active positions have R-squared 0.999904. The supplying selector remains rejected; these values establish architecture scaling only.

## Worklist Service Rate Is Not Dense FPS

The 9.739 services/s number is the service rate of one fixed 17-tile sparse request on a 50.000-MHz image. It is not dense-frame FPS. Dense 360p-to-720p execution is 4.171 FPS on a distinct 58.824-MHz image. Because both the admitted work and routed clock differ, no ratio between these rates is an architecture claim.

## Distinct 58.824-MHz Bitstreams

The two physical suites use separate routed images and must not share one unlabeled resource row:

| Image purpose | MHz | WNS (ns) | LUT | Registers | BRAM | DSP |
|---|---:|---:|---:|---:|---:|---:|
| Controlled geometry and commit | 58.824 | 1.363 | 45048 | 26648 | 3.5 | 180 |
| Independent temporal worklists and stage counters | 58.824 | 2.368 | 45160 | 26873 | 3.5 | 180 |

## Raw Evidence Digests

- `zybo_independent_rectangle`: `83b83e62ac08a70ec99fac1266cfe73fb801deceb30393c6477dd0d4c699edef` (4057 bytes)
- `zybo_persistent`: `a7ee42e35830cb135fc590c8151873aa549e53784b95c8df5a8c631a01c32e11` (825 bytes)
- `zybo_controlled_masks_commit`: `b171de5ac1bbe3879444a9585eeb10cd829afcab68b57dffb27dd5707f93e4e9` (11464 bytes)
- `zybo_controlled_masks_timing`: `0945c399a63ad51a45123a3de08bb32b0641dec5e58b2a319e401639a121f39d` (261315 bytes)
- `zybo_controlled_masks_utilization`: `cc115a92e8db94ddfba3b3e84868248f8c702edb27bfbd439d2c067cba679a59` (10222 bytes)
- `zybo_independent_worklists_commit`: `18a8cd3711057507ff11c7302aa3ac73e48ef60df94dca9ab36c93a4f9639077` (11095 bytes)
- `zybo_independent_worklists_timing`: `bf0a1f15cb0fa9733736db7644ac26c85f1f0cb40906c202d53456bfd616256a` (254236 bytes)
- `zybo_independent_worklists_utilization`: `e5ace81bd5a9c33a413d5cb6aee86e09a5d575c2efe9e51d3c5ae8c7807802e2` (10222 bytes)
- `tang_sparse_control`: `0fc28508a1a73aa88c2e8a468fc5d58ec3ef1f5439425910a92ad9bc36f92303` (1459 bytes)
- `b030_uart`: `ee6da3a171ea6f01f55732fbbe571f78ebe48aa156c39dfb994ab25006c724b8` (94371 bytes)
- `b030_timing`: `9ab6ba836f42b9ff7313580f1267004ab5adfc97245558540374d6c7c7f35036` (80385 bytes)
- `b030_utilization`: `3c0c9a26bbdb2dd3628e3e686908956c1031d089fea213191617e13b2eece9f2` (10264 bytes)
- `b030_drc`: `24beb09a45aa6dfcda4463d1ca229ef8f580b372bce97d17dcb6aa2bbeaa2a4a` (299191 bytes)

## Audit Gates

- `canonical_physical_checksum_length_counter_records_match`: **PASS**
- `organization_operating_points_passed`: **PASS**
- `controlled_masks_checksum_length_counters_match`: **PASS**
- `physical_commit_outcomes_exact`: **PASS**
- `independent_worklists_checksum_length_counters_match`: **PASS**
- `independent_architecture_not_selector`: **PASS**
- `distinct_58p824_bitstreams_identified`: **PASS**
- `worklist_service_rate_not_dense_fps`: **PASS**
- `deadline_replay_safe`: **PASS**
- `tang_control_physically_passed`: **PASS**
- `physical_energy_not_claimed`: **PASS**
- `headline_counter_time_boundary_explicit`: **PASS**
- `b030_same_bitstream_480_rows_checksum_length_verified`: **PASS**
- `b030_zero_aggregate_and_conditional_effects_disclosed`: **PASS**
