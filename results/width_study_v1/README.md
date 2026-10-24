# Network-width study

Two completed Zybo campaigns compare exact region execution at 24, 16 and 12
feature channels. Each width uses raster, outer-box and merged-region execution
with identical outputs within that width. All builds run at 50 MHz with 180 DSPs,
synchronous BRAM buffering and 2/12/6 MAC lanes; zero skipping is disabled.

## Evidence and replay

Run from the repository root with NumPy and the existing artifact requirements:

```text
python -B scripts/width_study_v1/replay.py
```

The replay regenerates all three integer references from included SystemVerilog
weight packages, including W12's per-output-channel shifts. Six INT64 patch
checks cover corners, an interior and a tile boundary. It then checks 2,448 raw
request records and 408 first-repeat selected-output archives and recomputes
the service means. Temporary decompression occurs outside the repository.

Each campaign retains its prospective protocol, qualification/freeze records,
routed resource/timing reports and four captures:

| Campaign | Acquisition order | Sparse mean merged gain against raster |
| --- | --- | --- |
| W16 | W24, W16, W16, W24 | W16: 19.92--19.95%; W24 controls: 16.30--16.31% |
| W12 | W24, W12, W12, W24 | W12: 22.54--22.55%; W24 controls: 16.30--16.31% |

Both campaigns use the same 17 masks, including empty/full controls, six repeats
per mode/mask and deterministic input. Timing aggregates use the 15 sparse masks
with equal mask weight. Run order reverses within each campaign; all acquisitions
occurred on the same date. The ranges are two acquisition results, not confidence
bounds. The two W24 control pairs remain separate.

The main observation is similar absolute raster-relative savings of 18--19 ms
at each width, producing a larger percentage gain as total service falls. Some
masks still favor a single box. W12 fits one Conv2 output-channel group whereas
W16/W24 need two, but the experiment does not isolate that effect from network
width, trained weights and quantization. LUT use is not monotonic with width.

## File map

- `w16/comparison.json`, `w12/comparison.json`: original campaign summaries.
- `w16/P001` through `P004`, and the matching W12 directories: original analysis,
  launch/capture records and gzip-compressed raw records/output archives.
- `models/`: generated W16/W12 integer weight, bias and shift packages.
- `w16/build`, `w12/build`: compiled-source hashes and routed reports.
- `w16/qualification`, `w12/qualification`: seven-request numerical and five
  fault/reuse checks performed before physical acquisition.
- `historical_quality.json`: retained model-ablation summary. This W12 checkpoint
  previously failed the every-scene Lanczos quality guardrail. The width study
  tests execution cost and exactness, not a quality-equivalent replacement.
- `export_manifest.json`: original/distributed hashes, compression and compiled
  source mappings. Absolute original paths are provenance, not replay dependencies.

All common compiled RTL sources and W24 weights already exist under
`results/design_study_v1/buffer/build/sources`; the manifest references them by
hash. Compressed files decompress exactly to their original captures. No FPGA
toolchain, physical board, training checkpoint or vendor IP is needed for replay.
