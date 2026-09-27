# Bounded common-image ROI integration

Engineering authorization: parent orchestrator, 2026-09-25. Route and physical
confirmation remain gated on numerical/ownership/failure qualification and
review. This is a narrow implementation improvement, not a claim that cropping
or sparse iteration was invented here.

## Why host-only is not sufficient

`espcn_hierarchical_mask_harness.sv` hardcodes 640x360 active geometry and the
accepted board wrapper exposes no origin or runtime-size registers. The older
variable-region engine accepts bounded horizontal runs but has a different
classical-frame-transfer and BRAM organization. Running that binary would not
produce a same-bitstream traversal comparison.

## Smallest useful new common image

1. Keep the trained 24-channel, 2/12/6-lane arithmetic and full-width allocated
   line buffers. Add only global origin to the existing three mask lookups;
   activate the existing runtime width/height feature.
2. Generalize sparse input injection to a configured cropped rectangle. Query
   global radius-3 support of **that region's owned requested mask**, ingest
   only real dependency pixels, and synthesize inactive positions inside the
   crop. Validate expected count and packet termination.
3. Generalize output compaction to local-to-global coordinates and the region
   mask. Internally drain all other outputs without downstream AXI stalls.
   Emit only the owned selected words; maintain a result count/checksum.
4. Keep one request-level identity, mask, deadline and private result lifetime
   while launching several regions. Region masks must be nonempty, disjoint,
   subsets of the captured request mask. A region's input rectangle must contain
   the complete clipped radius-3 support of its selected tiles.
5. Only the final completed region, with exact mask coverage and total selected
   count, can assert request completion. Cancellation, expiry, protocol error or
   incomplete coverage cannot authorize publication. The deadline starts once
   for the request and **continues during host/DMA gaps between regions**.
6. Full raster is a single region with the complete request mask and 640x360
   traversal. Merged ROI is the same image with conventional merged-rectangle
   descriptors. A bounding crop is another documented conventional control,
   not a post-hoc claimed algorithm.

## Cost expectations and honesty boundaries

- No change in DSP lane count, trained weights or arithmetic; origin adders,
  descriptor latches, coverage checks, coordinate counters and front-end muxes
  add logic and routing. Actual LUT/FF/BRAM use and Fmax are unknown until route.
- Full-width allocation is shared by all runtime modes; do not claim per-mode
  area savings from smaller active rectangles.
- Xilinx weights already remain resident. The simulator charges no reload.
- Three engineering cases are deliberately diagnostic, not a held-out claim.
  The compact case has 84.89% fewer core cycles, but complete host/DMA/service
  benefit is unmeasured. Input words count internal positions, not DRAM bytes.
- ROI may lose on dense/fragmented masks due to repeated fill/drain, duplicated
  dependency pixels and host setup. Preserve every case and regression.
- A conventional private buffer with software-only publication must remain a
  permitted comparator. Any hardware-publication benefit needs measurement;
  it cannot be inferred from the existence of a hardware commit register.

## Qualification before route

- Byte/coordinate equality with independent dense INT8 reference for global
  corners, interior, adjacent/overlapping halos, compact, scattered and dense.
- Full raster and merged modes produce exactly the same selected output set.
- Empty, malformed descriptor, unsupported mask bits, duplicate/foreign region,
  short/long packet, early/late TLAST, cancellation before/after private output,
  expiry between regions, incomplete final coverage and clean slot reuse.
- No external output permission before request-level commit; expected selected
  count includes every region once, and elapsed deadline is not reset.
- Source closure and exact pre-route test hashes; independently reviewed board
  protocol includes request-to-selected-residual-publication timing: planning,
  dependency packing, setup/DMA, private residual scatter and token publication,
  not only accelerator cycles. Classical upscaling, residual addition, rendering
  and display are excluded. Hardware deadline completion occurs before host
  scatter; no later CPU-token freshness guarantee follows from that budget.

Use a single declared 50-MHz route strategy for the common image after
qualification. No route has yet been launched, and the selected target is not
a measured frequency advantage over older builds. Preserve old images and
avoid copying large archives into C:. Build output must have a new validated
owned path and refuse destructive reuse.
