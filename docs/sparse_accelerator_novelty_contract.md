# Sparse-Refinement Accelerator Novelty Contract

Status: **candidate · not submitted · decision pending; final venue conformance pending**

## Research Question

September 21 scope clarification: this is an applied architecture study of an
integrated contract, not proof that the combination is uniquely necessary.
SBNet establishes overlapping masked blocks; fused-layer CNN processing
establishes retained intermediate reuse; SIGE establishes spatial updates with
cached features. A fused/tiled engine with private buffers and correctly
synchronized software publication is a credible alternative. No direct
complete-latency, CPU-overhead or publication-bound comparison against it has
been measured. Do not infer hardware necessity or superiority from its absence.
The E010 queue comparison and H002 host diagnostic add no new speedup claim;
see `docs/paper/PAPER2_SUCCESSOR_DIAGNOSTICS_20260921.md`.

Can a specialized accelerator turn externally supplied sparse super-resolution
requests into exact selected neural residuals, and what cycle/traffic operating
points do realized dense, independent-tile, rectangle-compacted, and persistent
organizations exhibit under a common model and request?

## Candidate Contribution

An arbitrary macro-tile **output request mask** is the accelerator's supplied
interface input. Its source may be a renderer, fixed workload, oracle, or
future selector; producing that mask is not an owned mechanism. Given the
mask, the proposed architecture combines three implementation responsibilities:

1. Exact backward **receptive-field closure** for every convolutional layer, so
   selected output pixels match dense execution rather than approximating it.
2. A persistent line-buffered traversal that shares halo and intermediate state
   across neighboring requests instead of restarting one CNN job per tile.
3. Deadline-safe residual commit: skipped or late refinement never invalidates
   the already available classical frame.

The current hierarchical implementation proves all three mechanisms in one
routed subsystem. The complete physical suite passes the frozen checksum,
selected-length, counter, and terminal checks for all 16 request masks and
separately observes prelaunch expiry, in-flight cancellation, late discard,
and one useful atomic commit. Only the useful frame advances the commit
sequence; no canceled or expired private result becomes visible.

The novelty claim is the combined unchanged-graph execution/publication
contract, its bounded implementation, and the evaluation method separating
direct physical counters from analytical geometry and deterministic replay.
Sparse admission, dependency skipping, persistent line state, and guarded
commit are not individually novel. Because the organizations occupy different
clocks, resource envelopes, and memory structures, the physical deltas are
measured operating-point differences, not isolated causal effects or matched
wall-time estimates.

## Excluded Claims

- The mask source is not claimed to generalize. Fixed, renderer, and HR-oracle
  masks are valid architecture workloads; the rejected learned selectors remain
  frozen adverse results.
- Tile-selective SR, dynamic SR, sparse convolution, line buffers, and classical
  fallback are not individually novel.
- The current implementation is not real-time at 720p and has no measured
  energy result.
- Selective SR and SkipSR make selective tile/patch reconstruction explicit
  prior art, regardless of SkipSR's desk-rejected publication status.
- Analytical shape sweeps are not physical measurements.
- A speedup from fewer selected tiles is not enough. The proposed organization
  must beat equally sparse baselines that receive the same output mask.

## Required Baselines

- Dense execution in the same bitstream.
- Independent halo tiles using the same trained model and selected output set.
- Rectangle/worklist compaction using the same selected output set.
- Persistent hierarchical-mask execution.
- SCNN-like value sparsity and SRNPU/ESSR-style tile selection are discussed as
  literature baselines; they are not falsely reconstructed from unavailable RTL.

## Locked Mechanism Gates

| Gate | Required result |
|---|---:|
| Selected output correctness | Bytewise equality against the dense integer reference in software/RTL; expected checksum, selected length, counters, and terminal conditions on the board |
| Cycles versus rectangle-compacted baseline | At least 25% reduction |
| AXI bytes versus rectangle-compacted baseline | At least 25% reduction |
| Physical workload breadth | At least 16 masks from at least 3 sources |
| Mask-decoder resource improvement | At least 1% fewer logic LUTs without timing or exactness regression |
| Deadline-safe commit | No partial neural frame becomes visible after cancellation or expiry |
| Energy | Pending external wall-power equipment; no claim before measurement |

The existing architecture passes every non-energy gate at its realized routed
operating points; the cycle/AXI gates are not a matched-resource control. The bounded decoder
passes with 1.64% fewer logic LUTs and +0.005 ns routed slack at 100 MHz. The
complete commit-safe 50-MHz PS/AXI-DMA bitstream passes all 16 masks, expected
checksums/lengths/counters, and every deadline outcome. Full physical output
byte streams are not retained, so the physical rows are not independently
bytewise replayable. A separate 58.824-MHz route
adds 17.65% measured throughput without additional DSP or BRAM. Energy remains
pending because external wall power has not been measured.

For the conference version, physical energy is deliberately deferred rather
than estimated as measured fact. A medium-confidence routed Vivado report and
a workload-duty sensitivity analysis may be shown only as provisional design
estimates. Physical wall power, joules/frame, and regulator losses remain a
journal-extension measurement.

The one-shot independent-worklist suite strengthens the workload-breadth gate:
15 sparse masks from five unseen temporal sequences, plus a dense control, pass
their checksum/selected-length/counter physical replay at 58.824 MHz. Every sparse mask reduces cycles and
AXI traffic; median reductions are 57.41% and 64.67%, respectively. This is an
architecture result only. The frozen selector that supplied the masks remains
rejected because its worst scene loses 0.1434 dB versus always-neural output,
above the 0.10-dB limit.

The two-context grouped-convolution trial is rejected. Although its isolated
layer test reduced cycles, the complete physical accelerator changed neither
dense nor sparse service cycles. The accepted design therefore remains the
one-context persistent hierarchy; no failed throughput optimization is folded
into the headline claim.

The independent-tile baseline is a physical full-frame capture rather than a
calibrated projection. It executes the same 15 accepted descriptors and 17
selected-tile equivalents as rectangle compaction, but launches each halo tile
independently. Its routed point records 9,857,730 cycles at 100.000 MHz
(98.57730 ms by cycles/clock), 2,399,952 AXI bytes, 38,274 LUTs, 28,681 FFs,
52.0 BRAMs, and 193 DSPs. The persistent point records 4,922,897 cycles at
50.000 MHz (98.45794 ms), 1,322,256 AXI bytes, 44,408 LUTs, 26,056 FFs,
3.5 BRAMs, and 180 DSPs. Thus 50.06% fewer cycles is not an elapsed-time
speedup; 44.90% lower recorded AXI traffic is supported, while the BRAM change
belongs to a different coupled memory organization rather than an area claim.
Earlier optimistic and serialized analytical bounds remain historical
diagnostics and are not used as the final baseline.

Five 300-frame arrival traces reuse physical per-mask service times to stress
steady, jittered, bursty, overloaded, and service-mispredicted operation. They
confirm temporal outcome accounting and commit safety in replay. The four
terminal outcomes remain separately validated on the board.

Experiments 126, 126b, and 126c are sealed adverse matched-control attempts.
Experiment 130: **Not run — pre-build governance stop (not a publication
decision).** Its defensible controls repeat the exact sealed 126c question,
while exact
LUT/FF/BRAM equality requires padding or changes the memory organization.
It produced no physical result and does not close the causal-attribution gap.

## Evidence Sufficiency Rule

Keep the hardware-paper direction only if the complete accelerator demonstrates
a meaningful advantage over equally sparse alternatives. A reasonable minimum
is one of the following while retaining exact output:

- at least 25% fewer external bytes;
- at least 25% fewer cycles or avoided MAC positions;
- materially higher deadline success at equal resources;
- a demonstrably smaller scheduler/decoder implementation at equal dataflow.

If those advantages disappear after controlled comparison or close prior art
already implements the full same mechanism, the work becomes supporting
architecture evidence for the broader co-design boundary paper rather than a
standalone architecture claim.

## Encoding Decision

The 10x6 request grid fits in a 64-bit bitmap, so it costs only eight bytes.
A row-run descriptor needs at least a row/start/length record for every span;
at four bytes per span it exceeds the bitmap as soon as more than two spans are
present. Run-length mask transport is therefore rejected as a default
compression mechanism. The implemented improvement instead performs bounded
local bitmap lookup: each queried coordinate checks at most its own tile and
eight neighbors, replacing three replicated 60-rectangle searches.
