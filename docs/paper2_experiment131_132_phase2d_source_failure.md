# Paper 2 Experiments 131/132 Phase 2D terminal source-only failure

Status: `TERMINAL_SOURCE_FAILURE_BUILD_UNAUTHORIZED`.

Phase 2D added a candidate actual-top path around the one trained integration,
owner-only output stream, six-band packet sequencing, persistent observability,
and the common ARM driver. These candidate sources are preserved for audit; they
are not an accepted executable closure and establish no scientific result.

The only Phase 2D actual-top XSim run elaborated and opened the snapshot, then
stalled after `run -all`. It emitted no PASS marker, `$finish`, or assertion
tail before the 1016.8-second supervisor stop. At the stop boundary the XSim
process had accumulated only 2.625 CPU seconds, which is consistent with a
simulated wait/deadlock rather than progressing computation. The exact bounded
run record is retained at
`results/preflight/transcripts/sparse_same_bitstream_studies_131_132_phase2d_actual_top.txt`.

The active mixed source/static suite also remained non-green: 15 tests passed
and six historical Phase 2C string/count assertions failed against the Phase 2D
candidate interfaces/reference expansion. Those failures were not hidden or
rewritten.

Per the bounded-stop instruction, the run was not repeated and the semantic
gate was not weakened. Experiments 131/132 are terminal at source-only failure:
build authorization is false, and no later metadata record may authorize this
checkpoint. No synthesis, implementation, route, package, XSA, ELF, bitstream,
timing/resource result, Zybo contact, board row, performance estimate, or
publication claim was created. Any future work would require a new experiment
identity and a new preregistration; it cannot repair or continue these studies.
