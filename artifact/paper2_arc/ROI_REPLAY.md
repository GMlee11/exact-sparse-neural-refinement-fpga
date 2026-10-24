# Region and publication replay

The current entry point is `python -B reproduce.py` at the repository root.
This directory retains the previous PowerShell entry point for compatibility.

For the original region experiment alone:

```text
python -B scripts/paper2_conventional_comparison_v1/replay_physical.py
python -B scripts/paper2_conventional_comparison_v1/replay_safety.py
```

P003 retains 306 requests over 17 masks, three organizations and six balanced
repetitions. Its 51 first-repeat selected-output archives contain 14,929,920
words. P005 retains eleven fault/reuse checks and 1,013,760 public-output words.
Portable replay checks those words against the included W24 integer weights.

In `results/paper2_conventional_comparison_v1/`, B002_route holds routed reports,
E013 the origin-aware core, F006 the timing campaign sources/cases, and F008 the
safety campaign sources/cases. P003 includes its freeze, protocol and numerical
summary. The safety protocol is under `docs/paper2_conventional_comparison_v1/`.
Common author RTL and model parameters are under `fpga/`; the ROI wrappers are
under `src/experiments/paper2_conventional_comparison_v1/`.

See the root `EVIDENCE_GUIDE.md` for the later studies and manuscript mapping.
