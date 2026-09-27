# Paper 2 bounded successor: publication disposition

The completed engineering successor adds no confirmatory speedup claim. It
does not replace B030 or any predecessor. The manuscript remains a
Microprocessors and Microsystems applied-architecture candidate, not submitted.

## Simulation qualification (E010)

Two full 640x360 LR development masks compared a baseline core with a two-entry
registered Conv3 window queue. Each core emitted 921,600 HR words per mask;
byte, coordinate, ordering and work-counter checks passed. Compact cycles were
2,456,290 for both cores; opposite-corner scattered cycles were 2,688,760 and
2,688,478 (0.0104881% reduction). No synthesis/route, clock benefit, physical
candidate measurement or held-out generalization follows. E009's preceding
timeout and all earlier engineering outcomes remain in the research archive.

The compact artifact contains the original E010 simulator transcript and two
terminal summaries under `results/paper2_service_successor_v1/engineering_evidence_v1`.
It verifies their reported outcomes, not a rebuild of the excluded RTL/toolchain.
The simulator transcript retains its original machine path as inert provenance.

## Existing-bitstream host diagnostic (H002)

One warmup and three measured repetitions for each pattern (dense, compact,
scattered) produced 12 passing rows. `uart.raw` has SHA-256
`cbc76ee1fd520ef38dea5e30d51e7dba12679bb79137ff659121d656b943819e`.
Existing profile bitstream SHA-256:
`0f07958107fc1529ad1fc87291d583104cc043f70ae479656eca987d903f79e2`.
New timestamp-only host ELF SHA-256:
`5c766e0cd42b41775689a3a8a86856c455a85de2f58e8e4d2c1f41c737bdb0a9`.
These binary identities document the capture, not availability of a complete
hardware-rebuild package. Full build records remain in the research archive.

| Pattern | DMA-trigger-to-completion median ms | Clear-through-completion median ms |
|---|---:|---:|
| Dense | 239.738990 | 261.948400 |
| Compact | 27.669623 | 28.259849 |
| Scattered | 43.494926 | 46.389167 |

Both intervals exclude synthetic input construction and subsequent output
checksum verification. The shorter also excludes clearing and setup. These
are diagnostic host measurements, not renderer service or a performance
comparison between candidate accelerators. Full physical output bytes were
not archived. The verification command below reads existing evidence only:

`python -m src.hardware.verify_paper2_successor_diagnostics`

## Manuscript correction and unresolved comparison

The original mask-only/commit-safe host timers begin immediately before the
MM2S length write, after output clear, S2MM setup, and configuration/start.
They stop after observing DMA and core completion, before checksum and counter
readout. Equal 102.677-ms means from separate 50-MHz builds do not establish
zero marginal publication overhead or complete application latency. Legacy
JSON service field names are preserved with an explicit corrected scope.

SBNet (arXiv:1801.02108), fused-layer CNN accelerators (MICRO 2016), and SIGE
(arXiv:2211.02048v4) establish close precedents for masked blocks, overlapping
support and retained features. ESSR (arXiv:2503.20245) uses edge-selective subnet
processing, resource-adaptive model switching and hardware-oriented fusion;
it should not be described simply as precision-scalable.

An equally safe fused/tiled engine with private buffers and synchronized
software-managed publication is a credible alternative. Complete latency,
CPU overhead and publication-time bounds against that alternative have not
been measured. The revised claim is the evaluated integrated implementation
and its trade-offs, not that hardware enforcement is necessary or superior.
