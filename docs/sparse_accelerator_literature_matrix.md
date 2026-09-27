# Sparse Super-Resolution Accelerator Literature Matrix

Last primary-source refresh: **2026-08-17** (Reviewer-3 expansion; final-day delta check pending)

## Purpose

Focused update, September 21, 2026: [SBNet](https://arxiv.org/abs/1801.02108)
uses masks, overlapping blocks, and gather/scatter for sparse convolution;
its local overlap-save equivalence is relevant even though its evaluated
batch-normalization network is retrained. [SIGE](https://arxiv.org/abs/2211.02048v4)
caches features and recomputes edited image regions. Along with fused-layer
CNN processing, these rule out masked tiling, sufficient halos and retained
intermediates as individual novelty. Our request/commit contract differs in
scope but is not proof that a straightforward combination cannot provide it.
An equally safe software-managed publication baseline remains unmeasured.

This matrix defines the prior-art boundary for the proposed sparse-refinement
accelerator. It is not evidence that the mechanism is novel by itself. The
matrix does not convert the constituent mechanisms into individual novelty or
make unmatched physical routes a causal control.

## Closest Work

| Work | What it observes | What it selects or predicts | What work is skipped | Architectural mechanism | Reported measurements | Direct overlap | Remaining distinction to test |
|---|---|---|---|---|---|---|---|
| ClassSR (CVPR 2021) | LR patch characteristics | One of several SR networks per patch | Execution of unnecessarily large networks | Patch classifier and network dispatch | PSNR and runtime on GPU | Spatially varying SR effort | It does not define exact receptive-field closure or a streaming sparse-output accelerator. |
| SMSR (CVPR 2021) | Learned SR features | Spatial and channel masks | Masked spatial/channel operations | Learned sparse masks inside an SR network | 27--41% FLOP reduction across scales | Fine-grained sparse SR | Its masks are learned internal activations; our candidate accepts an external output mask and must preserve exact selected outputs. |
| MobiSR (MobiCom 2019) | Patch difficulty and processor capability | Patch/model/processor assignment | Expensive model use on easy patches | Heterogeneous mobile scheduling | Latency, energy, and quality | Heterogeneous patch SR | It is a runtime mapping result rather than a receptive-field-aware sparse streaming dataflow. |
| TileSR (INFOCOM 2024) | Per-tile upscaling difficulty and device reward | Top-K tiles, packing, and target mobile device | Unselected local tiles and serialized single-device work | Multi-device tile offloading with multi-agent bandit scheduling | 17.77--82.2% response-latency reduction on COTS mobile devices | Tile selection, packing, and distributed scheduling | It rules out tile packing/offloading as novelty. It does not implement an FPGA dependency-closure engine or atomic residual publication. |
| SRNPU (JETCAS 2020) | Tile texture/complexity | Properly sized CNN per tile | Larger CNNs on simpler tiles | Tile-selective SR and selective feature caching | 31.1% compute and 78.8% bandwidth reductions | The closest tile-selective SR accelerator | We cannot claim tile selection itself. The remaining question is whether arbitrary output masks plus exact backward dependency closure and persistent cross-tile state provide a distinct measured advantage. |
| Selective SR (AAAI 2024) | Multi-scale LR tile features | Tiles of interest at several pyramid scales | Deep reconstruction for unselected background tiles | Transformer tile selector and selective deep-feature reconstruction | Three datasets; 40% computation reduction and lower FID on BDD100K | Direct algorithmic precedent for reconstructing only selected tiles | We cannot claim selective tile reconstruction. The paper does not report an FPGA dependency-closure engine with direct selected-byte software/RTL comparison, cross-region line-buffer reuse, or deadline-safe commit. |
| AdaFormer (AAAI 2024) | Texture-relevant transformer tokens and learned confidence | Tokens that may halt early | Later transformer work for low-value tokens | Adaptive token sparsification and uncertainty-guided early exit | Nearly 90% lower latency than SwinIR on Test8K with comparable reported quality | Strong precedent for learned spatial early exit in SR | We cannot claim early exit or adaptive token sparsification. It does not provide the externally requested FPGA closure and publication contract evaluated here. |
| BranchyNet (ICPR 2016) | Intermediate classifier confidence | Early-exit branch | Later network layers after a confident prediction | Jointly trained exit branches | Accuracy and latency tradeoff | General early-exit precedent | Early exit is not a Paper 2 mechanism. The supplied request mask is an interface assumption, not an internally learned exit policy. |
| FAST (CVPRW 2017) | Compressed-video block motion | Transfer versus recompute | Repeated SR on reusable regions | Temporal transfer and partial recomputation | Runtime and quality | Avoiding SR work in selected regions | It uses temporal codec information, not a same-frame exact sparse residual dataflow. |
| ESSR (TCAS-I 2024) | Simple input edge criterion | Patch-specific subnet | Full subnet execution on simple patches | Edge-selective dynamic processing, configurable layer mapping, and fusion | 50% MAC reduction for 0.1 dB PSNR loss; ASIC throughput, power, and SRAM access | Dynamic patch SR in dedicated hardware | We cannot claim edge-selective execution. Our mechanism must show exact selected residuals, explicit dependency closure, and deadline-safe commit under external masks. |
| SkipSR (ICLR 2026 desk-rejected disclosure) | LR latent-space detail | Patch tokens requiring refinement | Transformer/diffusion processing for simple patches | Lightweight mask predictor, mask-aware RoPE, token bypass, and output composition | Up to 60% lower end-to-end latency on 720p video | Recent disclosed precedent for LR-predicted patch skipping | Its publication status is adverse, but it still narrows novelty. It does not report an FPGA streaming dependency engine, physical traffic counters, or atomic deadline commit. |
| SkipVSR (ACM MM 2024) | Inter-frame aggregation confidence | Patches and recurrent blocks to execute | Low-value recurrent VSR blocks | Confidence estimator and adaptive patch/block routing | Video SR quality and practical speedup | Dynamic patch routing in temporal SR | It reinforces that patch routing is prior art; our hardware claim must remain independent of selector novelty. |
| Pseudo-FP6 SR processor (ISSCC 2025) | Quantized operand sparsity in an SR graph | Pseudo-FP6 sparse arithmetic | Ineffectual low-precision products and avoidable reconstruction work | Dedicated mobile SR processor with SR-specific low-precision datapaths | Silicon FPS and energy/frame | Low-precision sparse SR hardware | Precision and value sparsity are not our distinction; the request-mask dependency and commit contract must stand independently. |
| UASR-A (Electronics Letters 2026) | Static UASR graph and block geometry | Hardware mapping, not dynamic semantic regions | Off-chip feature movement through row-buffer and block-local reuse | ConvFormer/SR co-design, compact operators, PixelShuffle, row-buffer pipeline, block storage | ZCU102 PSNR, throughput, and FPGA resources | Recent SR-specific FPGA co-design and block reuse | It raises the quality/efficiency bar, but does not report arbitrary output masks, exact per-layer mask closure, or cancel-safe private residual commit. |
| Binary SR FPGA co-design (Integration 2026) | Static binary SR graph | Binary model/data path | Most full-precision arithmetic | DS-BConv/DGABA algorithm plus deeply pipelined streaming FPGA accelerator | Quality, throughput, resources, and power | Recent low-precision SR-specific FPGA accelerator | Binary arithmetic is a separate optimization axis. Our claim cannot be merely low precision or a streaming ESPCN pipeline. |
| DeSpa (JSA 2026) | Runtime tile-level operand sparsity | Dense versus sparse core and queue | Metadata/index overhead when dense; zero work when sparse | Heterogeneous dense/sparse cores, tile stealing, and networked accumulation | Latency, energy, and EDP versus homogeneous cores | Recent tile-sparse accelerator and hardware scheduler | It handles value sparsity in tiled MMA, not semantic output requests, exact SR receptive-field closure, or classical-frame commit safety. |
| Cnvlutin (ISCA 2016) | Zero input activations | Effectual neurons | Ineffectual-neuron products | Zero-skipping activation lanes | Performance and energy versus DaDianNao | Early numerical activation-sparsity accelerator | It skips numerical zeros; it does not consume requested outputs or enumerate their unchanged-graph support preimage. |
| SparseNN (DATE 2018) | Predicted zero output activations | Numerical nonzero outputs | Products leading to predicted zero outputs | Input/output activation-sparsity engine | Energy-efficiency and throughput | Direct prior use of “output sparsity” for numerical zeros | Paper 2 must say **requested-output sparsity**: its mask is semantic demand and may require dense-valued predecessors. |
| SCNN (ISCA 2017) | Zero weights and activations | Nonzero products | Zero-valued MACs and transfers | Compressed sparse dataflow and accumulator array | Performance and energy versus dense accelerator | Sparse CNN arithmetic | It exploits numerical value sparsity, whereas our candidate consumes requested-output sparsity and enumerates convolution dependencies. |
| NullHop (TNNLS 2019) | Zero activations | Nonzero activation stream | Zero-activation work and storage | Sparse feature-map encoding and decode | FPGA/ASIC throughput, utilization, and efficiency | Sparse activation hardware | It does not use an externally requested output region or prove selected-output equivalence. |
| Eyeriss v2 (JETCAS 2019) | Layer shape and compressed sparsity | Flexible mapping and compressed execution | Sparse operations and inefficient fixed mappings | Hierarchical mesh and sparse processing elements | Throughput and energy across compact DNNs | General sparse/flexible NPU architecture | Our candidate is SR-specific and must justify that specialization with less traffic or better deadlines. |
| Fused-Layer CNN Accelerators (MICRO 2016) | Static adjacent-layer graph | Fused layer groups | Round trips of intermediate feature maps | On-chip inter-layer caching and fused execution | DRAM access, performance, and energy estimates | Persistent intermediate reuse | Caching and fusion are prior art. Paper 2's narrower mechanism couples exact requested-output closure to persistent cross-region frontier state. |
| AoCStream (Sensors 2023) | Static CNN topology | Fixed streaming layer pipeline | Frame-sized intermediate storage | Layer-dedicated line buffers and accelerator-aware pruning | Memory, resources, and throughput | Persistent line-buffered inter-layer execution | Streaming line buffers are prior art. Only their mask-aware exact dependency handling and commit contract can remain part of our claim. |
| Block Convolution (TCAD 2022) | Static spatial block partition | Independent convolution blocks | Off-chip intermediate feature transfers | Retrained block-local convolution and multi-layer fusion | VDSR and classification quality plus FPGA memory efficiency | Direct treatment of spatial tile dependencies on FPGA | It changes convolution semantics to remove cross-block dependencies. Our mechanism retains the frozen dense graph and computes the exact operator-support preimage for requested outputs. |
| SIF-NPU (ESSCIRC 2022) | Adjacent-layer opportunities | Spatial fusion and precision modes | Intermediate movement and excess precision | Spatially fused NPU dataflow | TOPS/W and area efficiency | Layer fusion and reduced feature traffic | Fusion and quantization are supporting mechanisms, not novelty by themselves. |
| PREMA (HPCA 2020) | Request priority and predicted execution | Preemption and task order | Low-priority work that blocks urgent inference | Preemptible NPU plus predictive scheduler | Latency, throughput, and SLA satisfaction | Hardware/runtime support for interruptible DNN work | Deadline-aware preemption is established. Our narrower distinction is private SR residual publication: skipped, canceled, stale, or late work never corrupts the classical frame. |
| ART (GLSVLSI 2025) | Real-time task set and deadlines | GEDF schedule and preemption points | Work that would violate schedulability | HLS transformation, save/resume state, and hardware scheduling | FPGA schedulability and throughput | FPGA deadline and preemption support | Save/resume and real-time scheduling are established. We must demonstrate an SR-specific atomic residual commit and sparse dependency benefit, not generic preemption. |

## What This Review Rules Out

The paper must not claim any of the following as individually novel:

- selecting difficult image patches or tiles;
- using edges or learned masks to reduce SR work;
- heterogeneous CPU/GPU/NPU scheduling;
- sparse activation execution;
- line-buffered CNN streaming;
- layer fusion, PixelShuffle fusion, or low-precision arithmetic;
- temporal reuse or deadline-aware fallback by itself.

## Candidate Gap

The narrow candidate is the **combined unchanged-graph requested-output and
publication contract**, its bounded FPGA implementation, and an evaluation
method that separates direct physical counters from analytical geometry and
deterministic replay. An external renderer, oracle, or future selector supplies a
macro-tile output mask. Hardware propagates that request backward through each
convolution's receptive field, preserves inter-layer line-buffer state across
adjacent selected regions, computes only the required dependency closure, and
commits refinements only when the complete selected result is available before
its deadline. Classical output remains valid when work is skipped or late.

SRNPU, ESSR, UASR-A, Block Convolution, fused streaming/dataflow accelerators,
PREMA, and ART rule out novelty for selective SR, cached boundaries, row
buffers, block reuse, fusion, deadlines, preemption, or state retention alone.
The remaining combination is credible but narrow. The physical organizations
use different clocks, resource envelopes, and memory organizations, so their
cycle/AXI rows are measured operating points rather than matched-build causal
effects. A final-day backward/forward/patent refresh remains required.

## Feature-Level Novelty Table

| Work | Mask/source | Granularity | Dependency closure and exactness | State reuse | Commit behavior | Hardware evidence | Traffic and quality evidence |
|---|---|---|---|---|---|---|---|
| SRNPU | Tile classifier chooses a proper-sized CNN | Image tile and model size | Tile-local model choice; arbitrary output-mask closure is not reported | SC2LF caches short-reuse feature maps; cyclic ring amortizes reload | No stale/deadline publication contract reported | 65-nm ASIC | 78.8% lower external bandwidth; 31.1% lower compute while maintaining reported restoration performance |
| ESSR | LR luminance Laplacian score with two thresholds | Overlapping 32x32 patch and C27/C54/bilinear subnet | Overlap/boundary processing; allows 0.1-dB quality loss | Entire model/features on chip; boundary SRAM; group-of-layer fusion | Resource-adaptive model selection, not atomic frame commit | 28-nm ASIC evaluation | 50% MAC reduction at 0.1 dB; up to 79% lower feature-SRAM access |
| Selective SR | Learned pyramid selector | Multi-scale non-overlapping tile | Reconstructs selected tiles with deep features; hardware dependency proof not reported | Transformer feature processing | No real-time commit contract | Algorithm/GPU evaluation | 40% compute reduction on BDD100K with reported FID improvement |
| AdaFormer | Learned token confidence | Transformer token | Early exit with comparable reported quality; no hardware dependency proof | Transformer features | No real-time commit contract | Algorithm/GPU evaluation | Nearly 90% lower latency than SwinIR on Test8K |
| SkipSR | LR latent mask predictor | 4x16x16 pixel-equivalent video patches | Mask-aware attention composes skipped/refined patches; perceptual rather than bit-exact contract | Transformer latent state | No hardware deadline commit | Algorithm/GPU evaluation; desk-rejected disclosure | Up to 60% latency reduction with no reported perceptible loss |
| DeSpa | Runtime operand sparsity | MMA tile | Exact sparse arithmetic through indexed dense/sparse cores | Unified tiling and networked partial-sum accumulation | Queue scheduling and tile stealing; no SR frame publication | Modeled heterogeneous accelerator | Energy/EDP/latency across generic sparse DNN tiles |
| UASR-A | Static graph/block schedule | Streamed image block | Full graph; zero-padding and patch overlap handled in hardware | Cascaded row buffers and block-local storage | No cancel/expiry commit contract | ZCU102 FPGA | 88.9% bandwidth reduction versus naive receptive-field retrieval; PSNR/resources reported |
| This work | External 60-bit renderer/oracle output request | 64x60 LR output macro-tile | Exact Conv3/Conv2/Conv1/LR radii 0/1/2/3 closure; software/RTL selected bytes equal the dense integer reference | One persistent traversal shares halo and line-buffer state | Private output, frame ID, prelaunch skip, cancel, late discard, atomic commit | Zybo physical; Tang control-contract portability | Physical cycle/AXI counters plus checksum/selected-length/terminal checks; full physical output bytes are not archived; no measured energy claim |

## Full-Text and Figure-Level Threat Review

### SRNPU

SRNPU is the closest prior ASIC because it combines tile-based selective SR
with selective feature caching. Its TSSR mechanism chooses a CNN size per tile,
while SC2LF caches only short-reuse intermediate maps and the cyclic-ring core
amortizes reload across layer configurations. The official record reports
31.1% compute reduction, 78.8% external-bandwidth reduction, a 93.2% smaller
on-chip cache than prior layer fusion, and real-time FHD silicon. These results
prevent claims around tile-wise effort selection, feature caching, or real-time
mobile SR as a category. Our comparison is narrower: a request denotes output
locations rather than subnet size, exact CNN dependency closure is generated
for that mask, overlapping regions share one persistent traversal, and an
expired private residual cannot alter the classical frame.

### ESSR

ESSR Figure 1 segments LR input into overlapping patches, applies a luminance
Laplacian edge score, and chooses bilinear, C27, or C54. Figures 12--17 map
groups of fused layers onto 27x9 PE blocks; the design stores weights and
features on chip and retains patch-boundary state in dedicated SRAM. Its 32x32
patch study, edge thresholds 8/40, boundary processing, and 50% MAC reduction
at 0.1 dB make edge-selective patch execution, overlap handling, model
switching, and fused group-of-layer mapping unavailable as novelty claims.
Unlike our mechanism, ESSR selects subnet capacity rather than arbitrary output
positions and does not specify direct selected-byte support-closure validation or private
deadline-safe residual publication.

### Selective SR and SkipSR

Selective SR explicitly reconstructs only selected multi-scale tiles with deep
features. SkipSR predicts low-detail video patches from LR latent input and
bypasses expensive transformer computation. SkipSR was desk rejected at ICLR
2026, so it is not peer-reviewed evidence of effectiveness, but its public
disclosure still occupies the idea of learned patch skipping. Together these
works rule out "compute only difficult regions" as our contribution. The paper
must instead demonstrate the hardware mechanisms needed to execute an external
semantic mask exactly and safely.

## Backward, Forward, and Patent Search Log

Search refreshed on **2026-08-05** using exact titles, DOIs, author pages,
official proceedings, arXiv/OpenReview records, citing-paper searches, and
Google Patents. Backward references from SRNPU and ESSR were checked for
tile-selective SR, layer fusion, boundary handling, and dynamic subnet mapping.
Forward searches surfaced ESSR, UASR-A, Selective SR, AdaFormer, SkipVSR,
SkipSR, DeSpa, TileSR, Block Convolution, SparHiXcel-v2, and recent integer/LUT
SR accelerators. TileSR narrows selection/packing claims, while Block
Convolution is a direct dependency-handling threat that changes the underlying
operator. The July 2026 SparHiXcel-v2 preprint remains value/weight-sparsity
hardware rather than semantic output demand. None located so far reports the
complete combination of an unchanged dense SR graph, arbitrary output-mask
closure, persistent cross-region state, and atomic deadline-safe residual
commit.

The patent search found important claim-narrowing disclosures:

- Sony GB2617145B / US20230325977A1 selects image tiles for different
  upscaling processes using metadata, saliency, or edge information;
- US11308582B2 combines conventional scaling, neural residual enhancement,
  feature detection, and blending;
- US20240289911A1 applies tile/window-based machine learning to graphics
  enhancement;
- US20240085908A1 generates sparse image masks and sends relevant portions to
  a CNN; and
- US20230376733A1 skips sparse rows/columns in CNN accelerator hardware.
- CN115131212A predicts a spatial mask and sends selected feature blocks
  through later SR refinement networks;
- CN116468088B describes a configurable SR neural accelerator with compressed
  feature storage and convolution routing; and
- US20260127028A1 schedules and preempts NPU work using priorities, deadlines,
  available tiles, and thermal conditions.

These records further rule out generic masked refinement, compressed SR
acceleration, and deadline-aware NPU scheduling. The remaining architectural
distinction is the narrower exact-closure/persistent-state/atomic-publication
combination measured against equally sparse physical organizations.

This is a research novelty review, not a legal freedom-to-operate opinion. It
must be rerun immediately before submission because 2026 work is still moving.

## Current Evidence

The frozen 17-tile workload shows that the persistent hierarchical engine uses
4.923 million cycles and 1.322 MB of AXI traffic. Relative to the physically
measured independent-tile engine, this is 50.06% fewer cycles and 44.91% less
traffic. Relative to the physically
measured rectangle-compacted engine, this is 33.77% fewer cycles and 44.58%
less traffic. Relative to the dense control in the same bitstream, it is 65.09%
fewer cycles and 71.31% less traffic. Sixteen physical patterns from three
sources were freshly replayed after the bounded-decoder replacement and match
their frozen checksum/selected-length/counter records; cycle count tracks active
layer positions with R-squared 0.99499. The
canonical 17-tile worklist completes at 9.739 services/s on its 50-MHz image.
This is a sparse-worklist service rate, not dense full-frame FPS. The newer
58.824-MHz commit-safe image reaches 4.171 dense services/s. Neither establishes
real-time 720p operation, and the two values describe different workloads
rather than conflicting measurements.

A second one-shot physical suite uses 15 sparse masks drawn from five unseen
300-frame temporal sequences, plus a dense control. All 16 worklists preserve
the expected checksums, selected lengths, counters, and commit behavior at
58.824 MHz. Sparse cycle
reduction ranges from 15.73% to 88.46% with a 57.41% median; AXI-byte reduction
ranges from 18.13% to 98.28%. Cycles track active layer positions with
R-squared 0.99990. This supports architecture scaling on independent worklists,
not selector generalization: the frozen policy still violates its per-scene
quality gate.

A preregistered two-context issue engine is also retained as a negative result.
It is exact, closes timing, and adds no DSP or BRAM, but changes complete-system
dense and median-sparse cycles by 0.0%. Isolated layer latency hiding therefore
does not belong to the accepted architecture.

## Primary Sources

- Hsu and Chang, "ESSR: An 8K@30FPS Super-Resolution Accelerator With Edge Selective Network," IEEE TCAS-I 2024, DOI 10.1109/TCSI.2024.3349581 (later author deposit arXiv:2503.20245).
- Duan et al., "A 0.52mJ/Frame 107fps Super-Resolution Processor Exploiting Pseudo-FP6 Sparsity for Mobile Applications," ISSCC 2025, DOI 10.1109/ISSCC49661.2025.10904517.
- Huang et al., "UASR-A: An Efficient Edge Super-Resolution Accelerator With Hardware-Algorithm Co-Design Techniques," Electronics Letters 2026, DOI 10.1049/ell2.70584.
- Su et al., "Algorithm-Hardware Co-Design of Binary Neural Network for Efficient Super Resolution on FPGA," Integration 2026, DOI 10.1016/j.vlsi.2026.102674.
- Wang et al., "Exploring Sparsity in Image Super-Resolution for Efficient Inference," CVPR 2021.
- Lee et al., "SRNPU," IEEE JETCAS 2020, DOI 10.1109/JETCAS.2020.3014454.
- Kong et al., "ClassSR," CVPR 2021.
- Lee et al., "MobiSR," MobiCom 2019, DOI 10.1145/3300061.3345455.
- Zhang and Sze, "FAST," CVPR Workshops 2017.
- Parashar et al., "SCNN," ISCA 2017, DOI 10.1145/3079856.3080254.
- Albericio et al., "Cnvlutin," ISCA 2016, DOI 10.1145/3007787.3001138.
- Zhu et al., "SparseNN," DATE 2018, DOI 10.23919/DATE.2018.8342010.
- Alwani et al., "Fused-Layer CNN Accelerators," MICRO 2016, DOI 10.1109/MICRO.2016.7783725.
- Teerapittayanon et al., "BranchyNet," ICPR 2016, DOI 10.1109/ICPR.2016.7900006.
- Li et al., "Block Convolution," IEEE TCAD 2022, DOI 10.1109/TCAD.2021.3082868.
- Aimar et al., "NullHop," IEEE TNNLS 2019, DOI 10.1109/TNNLS.2018.2852335.
- Chen et al., "Eyeriss v2," IEEE JETCAS 2019, DOI 10.1109/JETCAS.2019.2910232.
- Kang and Yang, "AoCStream," Sensors 2023, DOI 10.3390/s23198104.
- Lee et al., "SIF-NPU," ESSCIRC 2022, DOI 10.1109/ESSCIRC55480.2022.9911509.
- Choi and Rhu, "PREMA," HPCA 2020, DOI 10.1109/HPCA47549.2020.00027.
- Zhou et al., "ART: Customizing Accelerators for DNN-Enabled Real-Time Safety-Critical Systems," GLSVLSI 2025.
- Zhang et al., "Transformer-Based Selective Super-Resolution for Efficient Image Refinement," AAAI 2024, DOI 10.1609/aaai.v38i7.28560.
- Luo et al., "AdaFormer: Efficient Transformer with Adaptive Token Sparsification for Image Super-Resolution," AAAI 2024, DOI 10.1609/aaai.v38i5.28194.
- Choudhury et al., "SkipSR: Faster Super Resolution with Token Skipping," ICLR 2026 desk-rejected OpenReview disclosure, arXiv:2510.08799.
- Ai et al., "SkipVSR: Adaptive Patch Routing for Video Super-Resolution with Inter-Frame Mask," ACM MM 2024.
- Jang et al., "DeSpa: Heterogeneous Multi-Core Accelerators for Energy-Efficient Dense and Sparse Computation at the Tile Level in DNNs," JSA 2026, DOI 10.1016/j.sysarc.2025.103650.

Primary-source links used for the refresh:

- https://arxiv.org/abs/2503.20245
- https://doi.org/10.1145/3007787.3001138
- https://researchportal.hkust.edu.hk/en/publications/sparsenn-an-energy-efficient-neural-network-accelerator-exploitin/
- https://researchconnect.suny.edu/en/publications/fused-layer-cnn-accelerators/
- https://www.eecs.harvard.edu/~htk/publication/2016-icpr-teerapittayanon-mcdanel-kung.pdf
- https://arxiv.org/abs/2105.08937
- https://pure.kaist.ac.kr/en/publications/srnpu-an-energy-efficient-cnn-based-super-resolution-processor-wi/
- https://people.csail.mit.edu/emer/media/papers/2017.06.isca.scnn.pdf
- https://pure.kaist.ac.kr/en/publications/prema-a-predictive-multi-task-scheduling-algorithm-for-preemptibl/
- https://peipeizhou-eecs.github.io/publication/2025_glsvlsi_art/
- https://ietresearch.onlinelibrary.wiley.com/doi/10.1049/ell2.70584
- https://doi.org/10.1016/j.vlsi.2026.102674
- https://ojs.aaai.org/index.php/AAAI/article/view/28560
- https://ojs.aaai.org/index.php/AAAI/article/view/28194
- https://openreview.net/forum?id=avo6hGnPAT
- https://openreview.net/forum?id=g4hMFNvhUs
- https://www.sciencedirect.com/science/article/pii/S1383762125003224
- https://patents.google.com/patent/GB2617145B/en
- https://patents.google.com/patent/US11308582B2/en
- https://patents.google.com/patent/US20240289911A1/en
- https://patents.google.com/patent/US20240085908A1/en
- https://patents.google.com/patent/US20230376733A1/en
- https://patents.google.com/patent/CN115131212A/en
- https://patents.google.com/patent/CN116468088B/en
- https://patents.google.com/patent/US20260127028A1/en
