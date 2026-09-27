# Same-image conventional ROI study: engineering protocol draft

Status: not a frozen confirmation protocol and not physical results. The initial
image/firmware runs qualify deployment, cache ownership, integer outputs and
publication. Ordinary functional debugging is allowed and recorded. A dated
source/image/firmware-hash freeze must precede the six-repeat confirmation.
No correctness failure is silently retried as a successful measurement.

## Question and comparison

How much avoidable full-raster traversal remains when the same trained integer
datapath, sparse dependency input, selected residual output and request safety
contract use conventional runtime-sized regions? Cropping and merged rectangles
are established techniques; the experiment does not claim to invent them.

Three modes in one routed image at one accepted clock:

1. Full 640x360 raster with the complete selected mask.
2. One clipped bounding rectangle around all selected tiles, with radius3 halo.
3. Conventional horizontal runs merged vertically where their column spans
   match, each with clipped radius3 halo and its own disjoint selected mask.

All modes retain the same weights, lanes, on-chip allocation, integer output,
private-output requirements, input fixture and clock. The ordinary rectangle
baseline is allowed resident weights, inter-layer fusion, legal reuse, efficient
per-row input interval merging, and software publication. It is not deliberately
handicapped with weight reload or pixel-by-pixel full-frame input filtering.

## Workloads and ordering

- All15 existing controlled masks, plus empty and dense controls; immutable
  source `configs/sparse_controlled_mask_suite_v1.jsonl`.
- A separately recorded deterministic signed input fixture, identical between
  modes: byte `(17*y +29*x +43*channel +51 -128) mod256`.
- The frozen trained W24 INT8 weights and independent dense integer oracle.
- One declared warmup per workload/mode. Warmup failures receive a full record
  (repeat99) and terminate the run; they are not hidden as warmup exclusions.
- Engineering qualification: one measured pass per mode/workload.
- Proposed confirmation: six repeats, order `(order+repeat+case_index) mod3`.
  The second three-repeat rotation reverses private-bank parity, balancing each
  mode across order and both output banks. This pre-data refinement was approved
  by the parent orchestrator on 2026-09-25; it produces 306 timed records.
  No request geometry or execution rule will be tuned against those timings.
- No claim that these already-inspected masks are unseen generalization data.

### Prespecified summaries and stopping

The primary descriptive comparison is the equal-workload arithmetic mean of
complete service time over the 15 existing nonempty sparse masks, with six
repeats per mask/mode. Report all three fixed-mode means and the ratios
`full/outer`, `full/merged`, and `outer/merged`; do not select the best mode
per mask and call it an implemented policy. The dense and empty controls are
reported separately and never improve the sparse average. Retain each mask's
mean, minimum, maximum and sample standard deviation, plus each mode's worst
individual-mask regression. Report absolute times and transferred words as
well as ratios. Six repeats assess local repetition, not independent-session
or population generality; no significance or energy claim is planned.

Confirmation stops after the fixed 306 measured records or the first retained
hardware/firmware failure. There are no outcome-dependent added repetitions,
discarded outliers, temperature exclusions, or clock/placement shopping. A
confirmation failure remains a failed confirmation; engineering fixes, if
necessary, receive a distinct disclosed successor identity.

## Measurement boundary

Primary: **request-to-selected-residual-publication service time**. Start the
Cortex-A9 timer before geometry planning, then charge input packing, MMIO/DMA
setup, NPU-independent FPGA execution, private selected-output scatter, cache
maintenance and the final metadata checks plus atomic ownership token.

This is not complete rendering, classical upscaling, residual addition, or
physical display time. The fixed input image is resident before measurement;
synthetic image generation is excluded equally. Numerical checking and evidence
archival are outside the service interval and must not be labeled production
overhead. Per-stage timers explain overhead but do not replace total time.

The hardware elapsed counter begins at request acceptance and includes gaps
between regions. Its COMMIT marks complete private DMA output, before CPU
scatter. The later CPU publication token therefore has a different endpoint.
Performance runs disable the deadline; no guarantee about end-to-end freshness
at the CPU token is inferred from the FPGA's completion budget.

## Ownership and cache discipline

- DMA input and receive regions have exclusive aligned allocations.
- In the cache-enabled configuration, flush dirty TX/RX ranges before DMA,
  invalidate RX after completion, scatter to a private bank, and flush selected
  private spans before the token. This follows the installed Xilinx AXI-DMA
  simple-poll example's cache-ownership pattern.
- Two private canonical output banks preserve the previously published bank
  while a new request is in progress. A single32-bit token encodes frame ID and
  bank, avoiding separately updated pointer/identity races.
  Both modes use the same two full-resolution residual banks, totaling 7,372,800
  payload bytes (8 MiB address reservation). This is not a minimal-storage claim.
- The benchmark consumer finishes checksum/archival before the next request;
  this is a declared synchronous consumer-release model, not arbitrary many
  outstanding readers. Failure never replaces the public token.
- Mailbox metadata is mapped uncached. Archive data is flushed before exposing
  completion to JTAG. Cache-disabled mode remains an engineering control, not
  the default claim about optimized host performance.

## Numerical evidence and data extraction

Byte-qualify the first physical deployment before confirming performance. For
every mask/mode, archive the predeclared first accepted output sample in DDR;
after measurement ends, dump it as binary through JTAG and compare every word
against the independent integer oracle. All timing repeats retain counts,
source identity and checksum. One byte archive per cell is not bytewise testing
of every repeat, and must not be described that way.

No megabyte ASCII output and no JTAG reads occur within timed intervals. The
final campaign record contains every condition, outcome and phase timing.
Raw archive allocation is `[0x06000000,0x16000000)`, non-overlapping with OCM,
DMA, input, private banks or mailbox; validate the actual XSA DDR range before
launch. Failed buffers may be archived separately when safely available.

## Interpretation

Report every nonempty frozen mask, dense regression, empty behavior, per-mode
traffic (including duplicated halos), number of regions, full service, device
cycles, actual clock and resource use. Do not combine empty controls into an
acceleration average. Do not present casewise best-mode selection as a deployable
scheduler; it is at most an explicitly labeled oracle summary.

This tests conventional traversal inside an exact, commit-safe integration. It
does not establish superiority over a separately designed cropped engine, area
savings between runtime modes, hardware-commit superiority to software
publication, energy savings, or novel sparse-iteration primitives.
