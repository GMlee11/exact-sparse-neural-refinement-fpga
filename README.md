# Resource and Service Trade-offs in Exact Sparse Neural Upscaling on a Zynq FPGA

Grant Lee, University of Central Florida — gr811059@ucf.edu

ORCID: https://orcid.org/0009-0009-9377-8412

Code and experimental evidence for the current design study. The repository
contains the completed region, buffering, network-width, zero-skipping and
output-suppression comparisons, together with their numerical references,
author-written RTL, routed reports and acquisition protocols.

The expanded measurement and RTL snapshot is pinned at
[449ca75](https://github.com/GMlee11/exact-sparse-neural-refinement-fpga/tree/449ca759603cbff0580826322624136915d45916).
`results/interpretation_v1` adds offline geometry/sparsity characterization of
that retained evidence and compact, checkpoint-bound model provenance.

Start with `EVIDENCE_GUIDE.md` for the manuscript-to-data mapping or
`REPOSITORY_MAP.txt` for the directory layout.

## Reproduce without hardware

Use Python 3.12. Create the environment outside this repository:

```powershell
py -3.12 -m venv ..\artifact-review-env
..\artifact-review-env\Scripts\python.exe -m pip install -r requirements.txt
..\artifact-review-env\Scripts\python.exe -B reproduce.py
```

The same Python commands work on other platforms with the appropriate virtual
environment executable. The complete replay verifies inventory and hashes,
regenerates integer reference pixels, checks the archived selected outputs and
request records, recomputes study aggregates, and runs the publication-table
tests. It needs neither hardware nor a vendor toolchain, downloads no weights,
and leaves the release files unchanged. Temporary decompressed captures are
created outside the repository. The simulation probe's default check verifies
retained logs; its optional `--xilinx-bin` argument reruns RTL with Vivado 2020.2.

Individual replay commands are listed in `EVIDENCE_GUIDE.md`. The previous
`artifact/paper2_arc/reproduce.ps1` entry point remains as a thin compatibility
wrapper around the same current-study workflow.

## What the studies establish

- Region organization: 306 W24 requests and 51 output archives compare raster,
  outer-box and merged execution on one shared image; a separate eleven-case
  fault/reuse campaign checks publication behavior.
- Buffering and skipping: the paired campaigns distinguish BRAM resource savings
  from service-time effects and retain both skipping-off and buffer-only controls.
- Network width: W16 and W12 comparisons each include their own W24 controls.
- Organization by skipping: all three widths cross execution organization with
  reference, skipping-off and skipping-on conditions.
- Stronger output baseline: the W24 physical comparison measures how early
  suppression changes service savings after a separate RTL probe.

All current-study outcomes remain, including regressions, empty/dense controls,
qualification failures and checker corrections. Older experimental campaigns
not used by this manuscript are outside this release. The W12 historical quality
record remains because the manuscript uses it as model context.

## Provenance and files

`release_manifest.json` hashes every distributed file except itself; `FILES.txt`
lists the release. Original study export/acquisition manifests are unchanged.
Byte-identical large archives share one stored payload via `payload_aliases.json`;
the replay scripts resolve the original paths automatically. No Git LFS or
manual decompression is required. `.gitattributes` preserves exact file bytes.

The original region evidence is identified by snapshot `34c46d4`; `449ca75`
contains the expanded measurements and RTL. Study export manifests and the
release manifest bind the data and derived analysis files.
The repository distributes offline replay and author RTL, not vendor IP,
bitstreams or a complete vendor-tool build environment. It contains no manuscript
or submission correspondence.

Original code is Apache-2.0; original data/documentation is CC BY 4.0. See
`LICENSE`, `LICENSE-CODE` and `THIRD_PARTY_NOTICES.md` for attribution and exceptions.
