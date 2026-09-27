# Evidence guide

Use artifact/paper2_arc/PHYSICAL_EVIDENCE_INDEX.md for exact capture/analyzer/field
mappings. `scripts/reproduce_paper2_arc.ps1` lists all offline regeneration commands.

- Same-bitstream contrasts and applicability: results/analysis/sparse_distilled_same_bitstream_b030_execution_factorial.json, physical UART in fpga/docs/captures/paper2/experiment134/E134-B030, and results/preflight/experiment134/E134-B030_physical_result.json.
- Organization operating points: results/tables/sparse_architecture_ablation_v1.json and analyzer src/hardware/analyze_sparse_architecture_ablation.py.
- Controlled masks/scaling: sparse_hierarchical_commit_controlled_masks* records, analyze_sparse_hierarchical_commit_physical.py and plot_sparse_accelerator_paper_figures.py.
- Deadlines and power: analyze_sparse_deadline_traces.py, analyze_sparse_realtime_envelope.py and analyze_sparse_postroute_power.py. Power is a tool estimate, not measured energy.
- Tang controls: analyze_tang_sparse_commit_candidate.py; split numerical/control evidence, not integrated throughput.
- Bounded successor/host diagnostic: docs/paper/PAPER2_SUCCESSOR_DIAGNOSTICS_20260921.md and verify_paper2_successor_diagnostics.py. No new confirmatory speedup.
- Later same-image ROI confirmation: artifact/paper2_arc/ROI_REPLAY.md, all 306 P003 timing records and 51 first-repeat raw-byte archives; scripts/paper2_conventional_comparison_v1/replay_physical.py.
- Physical fault/reuse validation: all 11 P005 public-output archives and scripts/paper2_conventional_comparison_v1/replay_safety.py. These are selected fault checks, not exhaustive formal verification.
- Full 17-workload ROI table: src/report/paper2_roi_publication.py regenerates results/tables/paper2_roi_publication_v1.json and docs/paper/generated/paper2_roi_publication_v1.tex. No manuscript source is distributed.

The compact replay checks the archived B030 contrast record and mask coverage;
it is not a fresh physical capture or complete RTL/bitstream rebuild. Manuscript
wording/layout regression tests are omitted because no manuscript is distributed.
The retrospective mask grouping's data is retained, but its manuscript-string
test is excluded. Frozen expected-output hashes retain the existing text hash
normalization rules. Historical provenance may name files outside this compact
snapshot; it does not imply those files are distributed.
