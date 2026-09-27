# Experiment 126c Terminal Result Disposition

Status: **TERMINAL / SHARED PREFLIGHT STOP / NO MATCHED RESULT**

Experiment ID: `sparse_same_clock_organization_control_126c_v1`

Build authorization checkout:
`08728931e0b2d5221662eea3292a9338342e1350`

Immutable independent-evidence commit:
`1845727a76bd475ed0b51a04fed40f8e88916439`

Experiment 126c ended after the sole `independent_halo_tiles` result-bearing
attempt. That route closed and its same-XSA application ELF was packaged, but
the mandatory preflight before `rectangle_compaction` treated the legitimate
new success evidence as unauthorized/untracked state. This is a shared
attestation/progressive-preflight defect discovered after a result-bearing
attempt. The frozen `stop_all`, no-source-edit, and no-retry rules make 126c
terminal: the defect must not be repaired inside this experiment, and neither
later organization may be attempted.

## Frozen Organization Disposition

| Organization | Route/package disposition | Board/performance disposition |
|---|---|---|
| `independent_halo_tiles` | Complete route and same-XSA ELF success | No board launch or row |
| `rectangle_compaction` | Not attempted | Not attempted |
| `global_closure_persistent` | Not attempted | Not attempted |

The independent route is valid at exactly 50.000 MHz: WNS +2.712 ns, WHS
+0.016 ns, 39,151 LUTs, 29,257 registers, 52 BRAM tiles, and 180
post-synthesis/routed DSP48E1 cells. Every DSP path is in the trained
convolution allowlist and zero bookkeeping DSPs remain. The XSA contains one
bitstream matching the standalone `.bit`, its root `ps7_init.tcl` matches the
extracted file, and its software flow produced the frozen ELF.

The driver emitted `BUILD_COMPLETE` and published all 14 success artifacts
before its final scratch cleanup encountered a locked Eclipse `.pdom` file.
That cleanup exception did not invalidate the published route/package set and
did not cause a retry. It is infrastructure disposition, not a paper result.

## Evidence and Claim Boundary

The exact success files and SHA-256 identities are recorded in
`results/manifests/sparse_same_clock_organization_control_126c_terminal_v1.json`.
That manifest lists all 14 exact force-add paths, including the normally ignored
four build products and three tool logs. The orchestrator has already preserved
those exact bytes in evidence commit `1845727`; they must not be rewritten or
normalized, and no additional force-add is needed for this candidate.
The generated board-readiness record is permanently false. There was no board
authorization, Zybo contact or programming, raw capture, physical performance
row, or timed iteration. All six unchanged >=25% gates are **not evaluated**.

Experiment 126c therefore validates one fixed-control independent baseline
route/package only.
It is not eligible for a matched-organization result and cannot be described
as equal-build confirmation. The original Paper 2 cycle/AXI comparisons remain
cross-route evidence; their headline values and contribution boundary do not
change.

## Reproduce the Terminal Audit

```powershell
$env:PYTHONDONTWRITEBYTECODE = "1"
.\.venv\Scripts\python.exe -m src.hardware.analyze_sparse_same_clock_organization_control_126c_terminal --check
```

The command is read-only. It hashes the immutable 14-file success set, checks
the route/DSP/same-XSA facts, proves that organization-2/3 and board/result
paths are absent, and compares the deterministic terminal records byte for
byte. It does not call Vivado, Vitis, JTAG, UART, or a board.
