# Paper 2 conventional-comparator engineering

Started 2026-09-25. E-series records are engineering/development qualification;
P003 is now a completed, separately frozen physical confirmation. All earlier
evidence is unchanged. The parent orchestrator owns publication integration.

## Completed physical result

The fixed-50-MHz common image passed all 306 confirmation requests: 17 workloads,
three fixed organizations, six counterbalanced repeats, with actual frame/token
and output-bank balance checked. All 51 first-repeat raw selected-output
archives (14,929,920 words) match the independent dense integer oracle.

Across the 15 existing sparse masks, equal-mask mean request-to-selected-residual
publication time was 114.874 ms for full raster, 103.476 ms for outer bounding
box, and 96.157 ms for merged rectangles. Merged regions reduce that service
time by 16.29% versus full raster and 7.07% versus outer bounding box. This
includes planning, packing, DMA, FPGA execution, private scatter, cache
maintenance and publication; it excludes rendering/reconstruction/display.

Merged regions regress against the stronger outer-box baseline on 5/15 sparse
masks, up to 1.084%; the dense merged control is 0.017% slower than full raster.
All cells and regressions are retained. This single-session result does not
claim unseen-mask generalization. Conventional ROI execution is the winning
mechanism; the contribution remains its exact, request-safe integration and
measured trade-off, not invention of cropping or proof of architectural novelty.

The mode comparison shares resource allocation: 46,754 LUTs, 27,334 registers,
180 DSPs and 3.5 BRAM tiles, with +1.054-ns setup and +0.007-ns hold slack.
Occupied slices are 99.38% and LUT-memory capacity 95.07%; no area advantage is
claimed. `P003/summary.json` contains every phase, traffic and service range.

## Question and immediate result

Does exact shared dependency closure provide a useful advantage over ordinary
fused tiled execution when the latter is allowed sufficient halos, adjacent
tile merging, no compulsory intermediate DDR spills, and software-managed
private publication?

E001 compared the frozen 15 controlled 640x360 masks plus empty/dense controls.
Global-union arithmetic savings against independent tiles were 2.4222% median.
Against conventional vertically merged row-run rectangles, the median fell
to **0.04358%**, with a maximum of **1.47865%**. Seven corner/interior/merged
regions using the actual frozen W24 INT8 weights passed bytewise equality with
the dense reference. Thirteen local tests passed.

This does not justify a new architecture based on halo arithmetic savings at
the existing 64x60 tile size. It also does not establish that a cached-union
implementation is free: its sparse discovery, lifetimes, ports and traversal
must be priced. The report labels that organization an analytical envelope.

## Strong baseline requirements

- Unchanged three-layer 3x3 network, 3/24/24/12 channels, signed INT8 values,
  INT32 accumulation bound and ties-away requantization.
- Output request unchanged. Input/Conv1/Conv2/Conv3 support radii 3/2/1/0.
- Baselines may merge contiguous output rectangles and fuse all three layers.
- All intermediate activations may remain on-chip; no invented whole-feature
  DDR traffic. Weights and selected-output storage charged equally.
- A private selected-result buffer plus software-controlled generation/source,
  completion, cancellation and deadline checks is a permitted alternative.
  The Python transaction model demonstrates these semantics, not concurrent
  hardware correctness or measured host overhead.
- Geometry counts are not latency or energy. Line-buffer payload bytes are
  not routed BRAM/LUT counts; banking, replicated ports and control are excluded.

## Follow-up simulation

The current persistent core traverses every image coordinate, synthesizing
inactive values and draining unselected output words internally. Therefore
an ordinary cropped fused schedule may be faster despite recomputing a small
number of halos. The comparison reuses one origin-aware runtime-geometry
core, same lanes (2/12/6), trained arithmetic, mask, input and sink pattern.

The only core derivation adds the region's global origin to the three mask
lookup coordinates; layer windows retain local coordinates. Mode 0 uses the
complete frame, mode 1 uses conventional merged rectangles with clipped radius-3
input halos. An optional bounding crop retains the global mask inside one
cropped traversal. Every region pays reset/weight initialization and drains
all local outputs. Only owned requested outputs enter the final result; halo
outputs are not public. Fresh region state prevents stale line-buffer reuse.

On the Xilinx path, `weight_initialization_complete` is tied high in the
existing core, so **no weight reload penalty is invented**. Weights are already
resident; the testbench charges five reset cycles per region plus actual
pipeline filling/draining. A conventional persistent-weight implementation is
therefore already respected at this interface.

The simulation's `inputs` field counts **internal core positions**, not AXI
traffic. The real `sparse_masked_lr_injector` receives only radius-3 dependency
pixels and generates other positions internally. For the compact corner tile,
both schedules need 4,221 real input words and 15,360 selected result words;
cropping removes internal traversal, not a 54-fold external-memory transfer.
The testbench supplies the deterministic dense input even at inactive sites;
those values cannot affect requested outputs under the checked exact closure.

The simulator checks every owned selected output against a dense full-frame
oracle. The oracle uses float64 integer-exact convolution and is cross-checked
at global corners/interior against a separate INT64 convolution implementation.
This is a core-cycle comparison: descriptor planning, host setup, DMA, physical
publication and achieved clock are **not measured**. The output count therefore
must not be called complete renderer service. No inference about Fmax follows
from the origin adders being combinational in simulation.

E002 is retained as an engineering testbench failure: an unsized watchdog delay
overflowed to a negative value and terminated at time zero. No DUT execution or
performance result occurred. E003 corrects that testbench constant, with no
network/architecture tuning. Ordinary engineering qualification is allowed.

E003 passed compact full-frame/cropped byte equality (15,360 selected words
each). Its artificial sink stalled unselected words as well, so its cycle
contrast is **stress qualification only**, not the fair compactor comparison.
The physical compactor discards unselected words before AXI. E004 onward apply
the same deterministic sink stalls only to requested owned words, while all
unselected words drain internally without external backpressure.

## Prior-art boundary (primary-source review)

- [SBNet, CVPR 2018](https://openaccess.thecvf.com/content_cvpr_2018/papers/Ren_SBNet_Sparse_Blocks_CVPR_2018_paper.pdf):
  overlapping sparse blocks, gather/scatter and fused residual blocks. Tiling,
  halo overlap, and packing are established techniques.
- [Fused-Layer CNN Accelerators, MICRO 2016](https://researchconnect.stonybrook.edu/en/publications/fused-layer-cnn-accelerators/):
  reordered input and inter-layer on-chip caching. Fusion and retained
  intermediates are not individually new.
- [D-SWIM, 2019](https://doi.org/10.3390/jimaging5030034): runtime-sized ROI line
  buffering means cropped/window geometry support is not novel by itself.
- [ESDA, FPGA 2024](https://doi.org/10.1145/3626202.3637558) and
  [SparsePixels, 2025 preprint](https://arxiv.org/abs/2512.06208): compact spatial
  tokens and sparse line buffers are close traversal precedents; their
  sparsity-preserving network semantics must not be conflated with our required
  dense-graph support closure.

The last three were independently identified by the review agent. This is a
focused research comparison, not an exhaustive novelty guarantee. The remaining
possible contribution is a measured exactness/storage/control trade-off under
the requested-output and publication contract, **not inventing ROI execution**.

## Reproduce

From the main repository, use its existing `.venv/Scripts/python.exe`:

```
python -m pytest tests/test_paper2_conventional_comparison_v1.py -q
python scripts/paper2_conventional_comparison_v1/replay_physical.py
python scripts/paper2_conventional_comparison_v1/run_comparison.py --run-id NEW001
python scripts/paper2_conventional_comparison_v1/run_traversal.py --run-id NEW002 --cases compact --timeout 900
```

Each result directory must be new; scripts refuse to overwrite old runs.
Numerical reports store input/model/source hashes. XSim is Vivado 2020.2 at
`C:/Xilinx/Vivado/2020.2/bin`. No board access, route, Git commit or push is
performed by these commands.
