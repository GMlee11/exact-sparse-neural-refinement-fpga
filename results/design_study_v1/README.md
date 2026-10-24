# Completed design-study evidence

This exports completed 21 October 2026 measurements, not new runs.
export_manifest.json binds each export to its original workspace path,
uncompressed SHA-256 and distributed SHA-256. Absolute historical paths are
provenance; portable replay does not execute them.

## Comparisons

1. Buffer: distributed-memory engine versus packed synchronous BRAM storage,
   same 2/12/6 lanes and 180 DSPs. P002/P003/P004/P005 are reference, candidate,
   candidate, reference. All three organizations, 17 masks, six repeats per
   launch. Four programming launches are not independent physical sessions.
   The integrated buffer/controller change lowers LUT use but not service time.
2. Skipping: buffer-only A (2/12/6) versus skipping-capable B0/B1 (4/12/4),
   both 180 DSPs, only merged regions. B0 and B1 share a bitstream; A does not.
   Four development renders, 17 masks, six total repetitions per condition.
   The primary aggregate averages per-cell percentage changes, not the ratio
   of means. Do not multiply it with region savings.

Original region evidence remains in ../paper2_conventional_comparison_v1.
These studies do not establish factorial interactions or a novel primitive.

## Replay

From the repository root:

    python -B verify_release.py
    python -B scripts/design_study_v1/replay.py

Replay checks export hashes, decompresses into a temporary directory outside
the repository, checks 2,448 request records and 408 archived samples,
regenerates four dense references with original integer weights, and recomputes
the frozen summaries. NumPy float64 calculations are exact for these bounded
integer accumulators; independent INT64 halo calculations check borders and an
interior region. Existing P003/P005 commands remain separately documented.

## Scope and redistribution

Build/source snapshots, routed reports, host source, prospective schedules and
immutable captures support source inspection and offline replay, not a
one-command Vivado rebuild. Vendor IP and bitstreams are not redistributed.
Read INPUT_NOTICES.txt before reusing input/reference data. Frames were
development stimuli, not independent evaluation data. Historical protocol
checkpoint wording remains verbatim; completed captures and replay establish
the outcomes. This export does not turn unsuccessful early-prediction designs
into claims or discard failures from the full research archive.
