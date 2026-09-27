# Exact Output-Driven Neural Refinement on FPGAs - reviewer artifact

Grant Lee, University of Central Florida, gr811059@ucf.edu
ORCID: https://orcid.org/0009-0009-9377-8412
Prepared for Microprocessors and Microsystems. Version review-v1, 2026-09-25.

This is an artifact-only repository: measurements, evidence, analysis code and
tests, with no manuscript, preprint or submission correspondence. Publication
preparation is not a claim that the paper has been accepted. Legacy `paper2_arc`
path names are stable experiment/replay identifiers, not the current venue.

## Review without hardware

Use Python 3.12 and Windows PowerShell 5.1 (the replay entry point is PowerShell).
Do not run deployment scripts on a board for this review. No hardware, FPGA
toolchain, neural-network compiler, external model weights or LaTeX is needed. Paper 2 includes the own-trained integer weights required for raw-byte replay.

```powershell
py -3.12 -m venv ..\artifact-review-env
..\artifact-review-env\Scripts\python.exe -m pip install -r artifact/paper2_arc/requirements.txt
..\artifact-review-env\Scripts\python.exe -B verify_release.py
powershell -NoProfile -ExecutionPolicy Bypass -File artifact/paper2_arc/reproduce.ps1 -Python (Resolve-Path ..\artifact-review-env\Scripts\python.exe)
```

The environment is intentionally outside this exact-inventory release. Replay
uses a disposable external copy and preserves the released evidence. On another
OS, install PowerShell or execute the documented Python analysis commands; the
full convenience script is validated on Windows. Standard-library hash verification
does not require installing any packages. `.gitattributes` preserves byte identities
through Git; do not enable automatic line-ending conversion for this snapshot.

## Evidence and limitations

Historical board evidence verifies checksums, lengths, counters and terminal outcomes, without raw output archives; B030 retains zero mandatory aggregate contrasts. Separately, P003 adds all 306 same-image ROI service records and 51 first-repeat selected-output byte archives, and P005 adds 11 physical failure/reuse publication-preservation archives. Portable NumPy-only replay checks those bytes against the included own-trained integer weights. See artifact/paper2_arc/ROI_REPLAY.md. Merged regions reduce equal-mask mean residual-publication time 16.29% versus full raster and 7.07% versus outer box, with 5/15 sparse-mask regressions against outer box. Cropping is conventional; this is not an area, energy, display, or unseen-mask claim. Complete bitstreams, vendor IP and synthesis environments are not distributed.

See EVIDENCE_GUIDE.md for table-to-evidence mapping. Generated `.tex` files are
table fragments, not manuscript sources. The archive preserves unsuccessful and
null outcomes. Do not combine historical diagnostic and confirmatory campaigns.

Only original code is Apache-2.0; original data/documentation is CC BY 4.0.
See LICENSE and THIRD_PARTY_NOTICES.md. `release_manifest.json` hashes every
distributed file other than itself. FILES.txt includes the manifest. Extra files
other than root `.git` metadata cause verification failure deliberately.

## Publishing this repository

Initialize Git HERE, not in the parent Paper 2 folder. Push this folder's
contents, retain its manifest, and create a `review-v1` tag or release. Send the
public repository URL and commit identifier back for verification and insertion
into the journal's data-repository field. The companion ZIP supplied for journal
upload contains the same files, so reviewers can replay without relying on GitHub.
No repository has been created or uploaded by this preparation script.
