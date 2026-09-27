# Engineering ledger — 2026-09-25

No old experiment, bitstream, result, manuscript or Git commit is overwritten.
The following are development qualification, not a frozen physical claim.

| Record | Purpose | Outcome |
|---|---|---|
|E001|Strong conventional arithmetic/storage comparison|Ordinary fused merged rectangles remove nearly all supposed halo-sharing advantage; median remaining MAC gap0.04358%|
|E002|Initial traversal testbench|Watchdog constant overflowed at time0; no DUT result|
|E003|Sink stress qualification|Exact output passed; stalls wrongly charged discarded internal words, so not a performance comparison|
|E004–E006|Selected-only backpressure, same arithmetic|Corner, distant corners and clustered region pass independent byte oracle; conventional cropping reduces modeled traversal cycles|
|E007|Request guard compilation|Declaration-order issue fixed before execution|
|E008|Guard directed checks|14 passed|
|E009|Actual compact AXI+GPIO+guard integration|Full1,601,926 vsROI242,011 request cycles;15,360 identical selected words|
|E010|Adjacent regions with overlapping halos|Full1,821,136 vs2-region491,866 cycles;30,720 selected words exact; input8,253 vs8,631 words (duplicate halos charged)|
|E011|Expanded guard boundary/reuse check|Found stale wrapper protocol-error after idle PREPARE; fixed source, preserved failure|
|E012|Guard after fix|16 checks pass, including exact deadline boundary, malformed restart, queued completion collisions and reuse|
|E013|Full dense compact-AXI numerical check|All 921,600 words exact; 14,194,271 request cycles. Watchdog amended by transferring supervision of the same simulator, not restarting/source-changing|
|E014|All4global corners on current source|Full2,302,520 vs4-region992,479 cycles;61,440 exact selected words; keep/TLAST/cancel/expiry and descriptor immutability checks pass|
|E016–E018|Native-compiled exact C host functions|3,048 geometry cases/modes and150 input packing/output scatter checks pass; all17frozen/control masks plus1,000seeded random masks|
|E019|Additional real-stream failure checks|Pass: overlong packet/late TLAST, cancellation after private output, frame-ID mutation and compact full/ROI byte equality|
|F001–F005|ARM firmware compilation|Compile/link successful; F005 includes cache ownership, two private banks, retained warmup failures, terminal archive flush and explicit frame/bank/token records|
|B001|Vivado BD setup|Rejected SystemVerilog top-file extension, not RTL logic; preserved|
|B002|New same-image synthesis and route|Fixed 50 MHz route completed: setup slack +1.054 ns, hold +0.007 ns, no unconstrained endpoints; BIT/XSA exported|
|P001|Physical launch preparation|PowerShell rejected case-sensitive HWH parameter names as duplicate JSON properties before any board access; metadata representation fixed|
|P002|Initial physical engineering deployment|51 rows and all 14,929,920 archived selected words passed independent oracle. UART wrapper prematurely closed on null process ExitCode; completed run recovered without reset/reprogram. XSCT decimal mailbox parsing corrected. Capture-only issues, not DUT numerical failures|
|F006/P003|Frozen physical confirmation|306/306 rows passed; all 51 first-repeat byte archives exact; prescribed mode/order/source/bank balance verified. Same routed image and C source, only repeat define changed 1 to 6|
|F007/P004|Prepared safety smoke|Never launched; review strengthened fixture to use distinct candidate input and overlapping private/public tile before deployment|
|F008/P005|Separate physical safety/reuse qualification|All 11 seed/fault/reuse checks and 1,013,760 archived public words pass; same image, no FPGA reset between faults/reuse. Zybo stopped after final evidence extraction|

## Source closure at synthesis

Current RTL, E013 simulation snapshot and B002 synthesis source copies match:

- Guard SHA256 `0398355e122c8958726b0f6dcc4116e2384c673e1e2cc50fc527d5907a54dd71`
- Stream SHA256 `bbe161647a3373ad4f4598c7285506a0e676bb2b4cbd8dfa9e7ea0f9056df9f3`
- Board shell SHA256 `f6891ffee861e44a9496fefceb2ecf96538056f9bc520e16d2a14582da09a59c`
- The derived origin-aware core also matches byte-for-byte. Its arithmetic,
  weights and lanes remain unchanged; origin affects only mask-coordinate lookup.

B002: `D:/Research/Paper2_Engineering/roi_v1_B002` is an isolated new build.
The small source/build manifest lives there; sources and preparation scripts are
in the main repository. There was no recursive cleanup or source replacement.

Synthesis reports47,763/53,200LUTs,27,339FF,180/220DSPs and3.5BRAM tiles.
Distributed-memory resources are tight:16,622/17,400LUTs as memory. Estimated
post-synthesis setup slack4.899ns is not routed timing. Final route uses
46,754 LUTs, 27,334 registers, 180 DSPs and 3.5 BRAM tiles; setup slack is
+1.054 ns, hold slack +0.007 ns, with all constraints met. There are no DRC
errors; 520 DSP pipelining warnings, one unused-net warning and two RAM
advisories remain. Resource tightness is explicit: 95.07% of LUT-memory
capacity and 99.38% of physical slices are occupied. This is not an area win.
Physical DDR and cache-coherent byte qualification were separate gates and
subsequently passed in P002/P003. P003's frozen equal-sparse-mask mean
residual-publication service is 114.874 ms full raster, 103.476 ms outer box,
and 96.157 ms merged rectangles. Merged regions reduce mean time 16.29%
versus full and 7.07% versus outer, but regress versus outer on 5/15 sparse
masks (worst 1.084%). Dense and empty controls are separate. No novel-cropping,
area, energy, independent-session or display-speedup claim follows.

P005 physically corroborates cancellation after private output, an immutable
request deadline across regions, insufficient-halo rejection, duplicate region
rejection, malformed restart and clean reuse. A differing inverted-input
candidate was scattered into the opposite private bank; all old public bytes
and source/bank tokens survived the rejected requests. This is bounded physical
qualification, not exhaustive proof of every fault or deadline endpoint.

Read-only hardware discovery found Zybo Z7 `210351BDF8A6A`, XC7Z020 and COM3
(`210351BDF8A6B` USB-UART bridge). Both ARM cores were initially running. No reset
or programming was performed during discovery.

## Firmware/claim boundary

See `board_protocol_draft.md`. The cache-enabled program charges ownership
maintenance, efficient interval packing, DMA, private residual scatter and
metadata-validated software publication. It does not measure a display pipeline.
The hardware deadline ends before the later CPU token; performance disables
deadline checking and makes no CPU-token freshness guarantee.

The first accepted physical bytes per mask/mode will be archived separately
after timing; all repeats retain count/checksum. These are not equivalent to
bytewise checking every repeat. The applied benefit under investigation is
integrating **conventional ROI execution** into an unchanged-graph exact,
commit-safe implementation, not inventing cropping or proving70%acceptance.
