ORGANIZATION BY ZERO SKIPPING, THREE WIDTHS

Run from the repository root:
    python -B scripts/organization_skipping_v1/replay.py
Requires NumPy and Python 3.12, not FPGA tools or hardware. Read-only replay
regenerates exact dense outputs for the six used width/image combinations;
independent INT64 patches check edges, corners and a tile boundary. Captured
selected outputs are byte-compared and every timing record is parsed afresh.

W24, W12 and W16 were acquired in that order, each with A-B-B-A programming
order, three repetitions per leg and six per cell. A is the 2/12/6 buffer-only
reference; B uses 4/12/4 lanes with skipping off/on in the same image. Thus B1
versus A compares configurations, whereas B1/B0 isolates the runtime switch.
W12/W16 changed the trained model package, not the C07 mechanism. Inputs are
archived development renders; masks are supplied synthetic requests.

Primary: 1,944 records and 324 full selected-output samples.
Separate qualification: 216 records and 216 full samples.
Separate W24 profile: 72 records, no full-output samples.
Sparse aggregate: eight image/mask cells per width, equal cell weighting.
Empty/dense controls remain in captures and summaries but not sparse means.
The original merged-only 17-mask study and original three-width study are
separate cohorts. Their aggregates are not overwritten or pooled here.

Only frames 0 and 2 are used. The W24 arrays and shared input bank already
exist in design_study_v1; trained model packages already exist in width_study_v1
and design_study_v1. This extension reuses them instead of duplicating them.
Manifests retain the original four-frame reference metadata for provenance;
unused W16/W12 frame arrays are not required for this replay.

W24 qualification Q001 initially failed a host-side geometry check that used
individual tiles instead of merged rectangles. Its original failed analysis,
checker sources, and corrected replay remain. The correction preceded every
primary capture and changed no firmware, hardware, goldens or board output.
W16 build B001-B003 failed in vendor startup before synthesis; B004 rebuilt
the qualified RTL through a copied working platform. Reports and source hash
bindings identify the successfully measured build; no failed build is treated
as physical evidence.

The original manifests retain author-machine paths. Portable replay resolves
only paths within this repository. Bitstreams, XSA/vendor IP, binaries and tool
caches are not distributed. Existing third-party input notices apply unchanged.
Files are hashed in export_manifest.json; compressed captures expand to the
original recorded bytes. All manuscript percentages are reproducible from
comparison.json and the underlying raw captures.
