# Experiment 130 Matched-Control Feasibility Disposition

Status: **TERMINAL NO-GO BEFORE IMPLEMENTATION OR HARDWARE**

Experiment ID: `sparse_matched_control_130_feasibility_v1`

Experiment 127 is already the deterministic second-topology closure check,
Experiment 128 belongs to Paper 1, and Experiment 129 belongs to Paper 3. The
next unused numeric identity is therefore 130.

## Decision

Do not implement or run Experiment 130. The proposed measurement cannot be
made scientifically independent of sealed Experiment 126c under the requested
scope. Building the same three 50-MHz, 180-convolution-DSP organizations after
correcting the progressive evidence lifecycle would finish the exact physical
question that 126c was frozen before completing. New directories and a new
label would make the evidence append-only, but would not turn the work into an
independent control; it would be a disclosed infrastructure repair and retry.

The resource requirement also has a causal ambiguity. Clock, convolution
lanes/DSPs, AXI ports, packet format, counters, workload, software, board, and
tool strategies can be held fixed. Exact LUT/FF/BRAM equality cannot be made
scientifically neutral, however: the persistent design's line-state memory
organization is one of the structures under test. Artificial padding would
match totals without matching useful capacity or access behavior; redesigning
the memories would change the mechanism. Such a run could compare three
realized organizations under common ceilings, but it still could not isolate
closure geometry, traversal, state retention, and commit individually.

## Frozen Counterfactual Controls

Had an independent experiment been possible, the protocol would have frozen
one route and one board launch per organization, in independent/rectangle/global
order, at 50.000 MHz (plus or minus 1 kHz), width-24 INT8 arithmetic, 2/12/6
convolution lanes, exactly 180 trained-convolution DSP48E1 cells, one context,
32-bit AXI through the same HP0/GP0 ports, the same atomic commit and counters,
one common workload, ten post-initialization repetitions, default Vivado/Vitis
2020.2 strategies, and no seed/strategy sweep, tuning, retry, or rescue. Actual
LUT/FF/BRAM would have been reported under common device ceilings, not padded
and not described as equal total area.

Those controls remain a counterfactual protocol description only. No source,
synthesis, implementation, route, package, JTAG, UART, programming, capture,
timed row, or performance gate was authorized or produced for Experiment 130.
The reserved build, evidence, capture, result, and manifest paths remain absent.

## Publication Consequence

The paper must retain its strongest supported statement: the reported cycle,
AXI-byte, correctness, and resource values are direct physical measurements of
realized organizations. Because those organizations use unmatched routed
points, the differences do not establish matched-build wall time and do not
identify an individual causal effect for dependency closure, traversal,
persistent state, sparse admission, or atomic publication. The defensible
contribution is the combined exact-output execution and publication contract,
its concrete FPGA realization, and the measured operating points and
evaluation methodology.

Experiment 130 is not a physical negative result. It is a governance and
identifiability NO-GO made before implementation so that sealed 126c is not
quietly repaired under another name. Changing only the experiment label or
repairing the progressive preflight would not turn the work into an independent
control.
