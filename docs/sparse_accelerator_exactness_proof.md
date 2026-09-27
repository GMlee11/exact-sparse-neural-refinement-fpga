# Exactness Argument for Hierarchical Sparse Residual Execution

## Scope

This document explains why the selected residual pixels produced by the sparse
engine equal the same pixels produced by dense integer inference. It is a
mathematical argument backed by exhaustive and randomized tests; it is not a
machine-checked formal proof.

## Definitions

Let `S3` be the set of low-resolution positions whose final Conv3 residuals are
requested. For a same-padded, stride-one 3x3 convolution, define `D1(S)` as the
set containing every position in `S` plus all valid image positions at Chebyshev
distance one. The exact dependency sets are:

```text
Conv3 outputs required: S3
Conv2 outputs required: S2 = D1(S3)
Conv1 outputs required: S1 = D1(S2) = D2(S3)
LR input required:      S0 = D1(S1) = D3(S3)
```

Image-boundary coordinates are clipped to the valid LR domain, matching zero
padding in the dense model.

## Selected-Output Closure Lemma

Consider a feed-forward graph whose operators are deterministic and have finite
spatial support.  Starting from a requested sink set `T`, define the required
set at each predecessor by taking the union of the support preimages of every
required successor position.  If sparse execution evaluates the same operator,
boundary rule, accumulation order, requantization, and nonlinearity as dense
execution at every required position, then every output in `T` equals dense
execution.

The argument is induction in topological order: graph inputs agree on the
computed preimage; each required internal value reads only predecessor values
already covered by that preimage; therefore every required successor agrees,
including `T`.  The closure is also structurally minimal: every included
position lies on at least one operator-support path to `T`.  Removing it cannot
guarantee equality for all legal inputs and parameters unless an additional
zero-weight or data-independence fact is proved.  This is a model-independent
minimality statement, not a claim that every concrete input activates every
arithmetic path.

## Inductive Argument

1. Every Conv1 value in `S1` depends only on LR samples in `S0`. The sparse
   engine injects every member of `S0`, so its integer multiply, accumulate,
   bias, requantization, ReLU, and saturation produce the dense Conv1 value at
   every position in `S1`.
2. Assume Conv1 is exact on `S1`. Every Conv2 value in `S2` depends only on the
   3x3 Conv1 neighborhood contained in `S1`; therefore Conv2 is exact on `S2`.
3. Assume Conv2 is exact on `S2`. Every requested Conv3 value in `S3` depends
   only on the corresponding 3x3 Conv2 neighborhood contained in `S2`;
   therefore Conv3 is exact on `S3`.
4. PixelShuffle is a permutation of Conv3 channels into HR coordinates. It does
   not combine requested values with uncomputed positions.
5. Bicubic residual addition, clamp, and output packing are pointwise after the
   matching base pixel is available. They preserve equality at each selected
   output coordinate.

Thus, computing exactly `S0`, `S1`, `S2`, and `S3` is sufficient for selected
outputs to match dense inference. Unselected outputs are intentionally not part
of the sparse result and retain the classical fallback.

## Bitmap Decoder Equivalence

The largest closure radius checked by the hardware decoder is three pixels,
and each macro-tile is 64x60 pixels. A coordinate can therefore be inside the
dilated rectangle of only its containing tile or one of the eight immediately
adjacent tiles. The bounded 3x3-neighborhood lookup is equivalent to testing
all 60 tile rectangles, provided the radius is smaller than both tile
dimensions. RTL elaboration rejects configurations that violate this
condition.

## Executable Evidence

- `tb_sparse_hierarchical_mask_lookup.sv` checks eight mask patterns, every
  pixel of a 40x24 image, and radii zero through three against an independent
  all-tile reference: 30,720 comparisons.
- `verify_hierarchical_exactness_suite()` checks randomized fragmented masks,
  integer convolutions, nonlinearities, and all selected outputs.
- Experiment 127 applies the same reverse-support construction to a synthetic
  branched residual graph with a dilated convolution and skip-add path. It
  checks closure sets against exhaustive support-path enumeration, verifies
  dense/sparse equality, records an exact input/output coordinate and edge-
  offset support-path witness attaining Chebyshev displacement four, and
  constructs a removal witness for every required input position. This is a
  deterministic software/RTL-contract test, not a routed second accelerator.
- The physical Zybo suite checks 16 masks from three sources and reports
  matching expected output checksums and selected lengths plus the frozen
  active/bypass/traffic counters. Full board output byte streams are not in the
  archive, so physical bytewise replay is not claimed.
- The commit-controller RTL suite covers dense, sparse, empty, canceled, and
  expired transactions. The board suite additionally observes prelaunch skip,
  in-flight cancellation, late discard, and useful commit through independent
  counters and a monotonically increasing commit sequence.

## Atomic Publication Invariant

Let public state be the tuple `(commit_sequence, committed_frame_id,
published_buffer)`. Private DMA writes never change that tuple. Its only
transition is an atomic commit after all required output words are complete,
the active and prepared frame IDs match, cancellation is clear, and the
deadline remains valid. Prelaunch skip, in-flight cancel, expiry, protocol
error, and partial private output leave public state unchanged. Induction over
controller transitions therefore guarantees that no partial, canceled, stale,
or late residual becomes visible.

The controller and board suites exercise the terminal transitions and check
the monotonically increasing commit sequence. They support the invariant but
do not constitute machine-checked formal verification. This control property
is orthogonal to convolution exactness and is tested independently.

## Claim Limit

Exactness says the sparse engine does not change requested integer residuals.
Software and RTL tests establish that statement by comparing retained bytes;
the physical suite supplies the narrower checksum/length/counter evidence
described above.
It does not say the neural model reconstructs ground truth perfectly, that the
mask chooses the right regions, or that the implementation meets a real-time or
energy target. Those are separate quality, policy, timing, and power questions.
