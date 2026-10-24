# C07 prospective physical comparison — not yet launched or frozen

Purpose: qualify a stronger **conventional** implementation baseline. No novelty,
held-out generalization, rendering/display, reconstructed-frame, energy or Fmax
claim. Clock remains 50 MHz. Original accepted weights, graph, global boundaries,
ownership and residual-publication endpoint remain unchanged.

## Gates and comparisons

Module, configuration and compact original/natural graph qualification must pass.
Matched B001 natural replay must pass. Isolated route must meet setup/hold and
DRC, with actual resource costs reviewed by the parent. Sources, inputs, common
ELF, images, protocol, launch commands and analysis must be pinned before board
access. No physical launch without explicit parent review/authorization.

Compare three conditions: A = previous B001 BRAM image, original 2/12/6 lanes;
B0 = C07 4/12/4 with zero skipping disabled; B1 = same C07 image enabled.
A remains the strong previous implementation reference. B0 is intentionally
not the best universal disabled allocation, so B1/B0 alone is not the primary
improvement claim. Primary organization is conventional merged regions only.

Input catalog is the four first-C002-per-stratum N001 development frames, native
centered 640×360 crops, RGB bytes minus128. All 17 old masks remain: empty, dense,
and 15 sparse. No new scenes/masks are selected after observed results.

Before timing, candidate guards/fault reuse must pass, and all four enabled dense
outputs must be physically byte-checked against independent exact goldens. These
are separate untimed qualification launches, not samples in the ABBA analysis.

## Prospective fixed schedule

Four timed programming launches: A, B, B, A. Each launch has three measured
repeats per available condition and every one of 68 frame/mask cases. Global
repeats are 0–2 in each condition's first launch, 3–5 in its second.

New-image condition order for each case/repeat is `(global_repeat+case_index)%2`
then its complement. Original image runs one condition. Warmup is one request
per case/available condition, with all counts retained. Warmup failures terminate.

Only global repeat0 is archived byte-for-byte. All six repeats retain checksums,
counts, ownership, published-bank tokens, actual enable readback and stage/service
times. Counts: A204 + B408 + B408 + A204 = **1,224 timed records**, and **204 byte
archives**, approximately239 MB. Repeats3–5 do not overwrite/create duplicate
first-repeat archives. Every regression/failure remains in the report.

Primary aggregation is the arithmetic mean of per-cell percentage service
reduction B1/A over 15 sparse masks, with equal weight for each of four frames
(60 cells). Report every frame, mask/cell and launch/session regression. Empty
and dense controls are separate, as is same-image B1/B0. Six paired-repeat
descriptives supplement rather than replace the predeclared cell aggregation.
No outcome-based case or launch exclusions.

Original first/final launches initialize the published empty bank token to bank
0/1 respectively; both new-image launches initialize bank0. Both private banks
are initialized outside timing before warmups. Each warmup batch has even request
count. With 68 cases and six global repeats, this gives exactly three measured
requests per condition/case/private bank. No padding request is needed. Initial
tokens represent initialized blank consumer slots, not an original running OS.

## Measurement and preparation

One common timed ELF for both images. Inputs are host-loaded before CPU execution,
outside the service boundary, and checked once by the CPU against pinned input
hash/checksum metadata. Frame selection and experimental enable selection occur
outside the per-request timer, as arm setup, with identical cached input banks.
The existing timed boundary remains planning → dependency packing → DMA/engine →
private selected-residual scatter → metadata-validated publication/cache flush.
Numerical archival and UART/JTAG are outside timed work. This is not input-loading
or end-to-end frame/display throughput. Arithmetic zero detection and channel
selection inside the FPGA are fully included in engine/service time.

The old image must read zero at undefined 0x31. The new image must accept/read
configured bit0, latch bit1 at request start, and report exact requested mode at
completion. Writes while active must not change an accepted request.

Proposed exclusive RAM ranges, validated against actual HWH DDR and linker map
before launch (ends exclusive):

| Range | Purpose |
|---|---|
| 0x00000000–0x00030000 | Existing OCM program/data/stack/heap |
| 0x01000000–0x010e1000 | Dependency TX |
| 0x02000000–0x02384000 | Private DMA RX |
| 0x04000000–0x04384000 | Public/private slot0 |
| 0x04400000–0x04784000 | Public/private slot1 |
| 0x05000000–0x05100000 | Uncached results mailbox |
| 0x05100000–0x05101000 | Uncached host launch configuration |
| 0x06000000–0x16000000 | First-global-repeat selected-byte archives |
| 0x17000000–0x17e10000 | Separate four-dense-output qualification archive |
| 0x18000000–0x18384000 | Four pinned signed-RGB input word banks |

RAM-only FPGA programming; exact Zybo serial and UART identity. No flash,
electrical or clock changes, service changes, destructive cleanup or restoration
claim. Last timed launch loads original B001. Record actual CPU running/halted
state and release serial/JTAG clients at completion; do not imply OS restoration.
