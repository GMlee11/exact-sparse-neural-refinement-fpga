# Experiment 126b Post-Failure Result Disposition

Status: **COMPLETE / ADVERSE / BOARD PHASE PERMANENTLY BLOCKED**

Experiment ID: `sparse_same_clock_organization_control_postfailure_126b_v1`

Authorization checkout:
`2253ba5f8779e171c541ffec1f74b2fe7f3dcbfd`

Sealed evidence commit:
`5ffde49b7c0cda9b29bf34a0ecb6d0fa7e822fd6`

Experiment 126b is disclosed post-failure remediation informed by sealed
Experiment 126. It is not blinded confirmation, independent confirmation, a
fresh replication, or a replacement for Experiment 126. No result below
reopens or relabels the predecessor.

## Side-by-Side Disposition

| Experiment | Route/fairness disposition | Packaging disposition | Board/performance disposition |
|---|---|---|---|
| 126 | Independent and rectangle routed with 185 DSP48E1 cells against the frozen 180-DSP gate; global used 180. The matched fairness gate therefore failed. | The frozen flow did not produce a usable packaged image; the global failure was an XSA extraction/search-path defect. | No organization was accepted and no matched board comparison was run. |
| 126b | All three one-shot routes closed at exactly 50 MHz with 180 post-synthesis and 180 routed DSP48E1 cells. Every DSP path was in the trained-convolution allowlist and no bookkeeping DSP remained. | All three same-XSA application builds failed before an ELF was discoverable. The complete 17-file failure archives are hash-bound. | No board contact, programming, raw capture, service row, or performance-gate evaluation occurred. The board phase is permanently prohibited. |

Experiment 126b therefore closes one narrower question: the disclosed
bookkeeping-only LUT mapping produces three timing-clean, same-clock routes
with exactly matched convolution DSP allocation. It does not produce an
executable board image and does not close the paper's equal-build performance
attribution question.

## Frozen Route Facts

| Organization | WNS (ns) | WHS (ns) | LUT | Registers | BRAM | DSP48E1 |
|---|---:|---:|---:|---:|---:|---:|
| Independent halo tiles | +2.712 | +0.016 | 39,151 | 29,257 | 52 | 180 |
| Rectangle compaction | +2.845 | +0.020 | 39,155 | 29,261 | 52 | 180 |
| Global closure + persistent | +3.318 | +0.016 | 46,015 | 28,123 | 4.5 | 180 |

The resource totals are architecture outcomes, not an equal-total-area claim.
The global organization uses more LUTs and much less BRAM than either region
organization. No seed, strategy, clock, lane, interface, threshold, or source
alternative was selected after observing a result.

## Packaging Failure and Evidence Boundary

Each XSA contains exactly one root `ps7_init.tcl` and one bitstream matching
the separately staged files. None contains an application ELF, and the
hash-bound failure summary for every organization states
`Experiment 126b same-XSA application build failed`. The launch transcript
also showed missing BSP-export members such as `translation_table.d` or
`mblaze_nt_types.h`; those warnings are useful root-cause context, but no
separate transcript was promoted into the sealed claim evidence.

This distinction is mandatory: route attribution succeeded; executable
software packaging failed. The earlier restricted-sandbox launcher hang
created no synthesis log or evidence and is infrastructure history only, not
an experimental result.

## Performance Gates Not Evaluated

The original six thresholds remain unchanged: at least 25% reduction in FPGA
cycles, service time, and AXI bytes versus both independent halo tiles and
rectangle compaction. All six are recorded as **not evaluated**, with zero
physical rows and zero timed iterations. An absent capture is not a failed or
passing performance measurement.

No packaging repair, retry, route, programming step, or capture is authorized.
The paper must retain its original physical cross-route cycle/AXI evidence and
the explicit limitation that Experiment 126b did not establish equal-build
performance attribution.

## Reproduction

The non-proprietary audit is:

```powershell
$env:PYTHONDONTWRITEBYTECODE = "1"
.\.venv\Scripts\python.exe -m src.hardware.analyze_sparse_same_clock_organization_control_126b_adverse --check
```

It verifies the three exact 17-file inventories and hashes, authorization
lineage, route reports, resource facts, complete DSP inventories, XSA members,
blocked board status, absent raw capture, and unevaluated performance gates.
It performs no proprietary build and writes nothing in `--check` mode.
