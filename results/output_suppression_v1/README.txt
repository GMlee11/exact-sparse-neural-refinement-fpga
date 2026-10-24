W24 conventional selected-output suppression: physical follow-up

Run from the artifact root:
    python -B scripts/output_suppression_v1/replay.py

The replay regenerates both used W24 dense references from the included model
and input banks, checks 864 primary timing/status records and 144 first-repeat
full-output archives, and recomputes all equal-cell service comparisons. It also
checks the separate 144 qualification records and their 144 output archives.
These counts describe the complete successful campaign, not extra replicates
of the earlier organization/skipping campaign.

Q001/Q002 qualify the original/suppressed images. P001/P004 use the original
image; P002/P003 use the suppressed image. Both use identical 4/12/4 lanes,
50-MHz fabric clock, W24 parameters and host firmware. Runtime controls cross
zero skipping off/on with raster, outer-box and merged execution. Protocol and
manifests retain exact order and bindings. Complete service ends at the CPU
residual-bank token, before numerical checking and archive collection.

The eight sparse cells are two development images crossed with four fixed masks;
empty and dense controls are retained separately. Six repetitions per cell span
two acquisitions per image within one continuous board session. Original and
suppressed results are separate routed builds, not a same-bitstream isolation.
The intervention suppresses unselected PixelShuffle expansion; it does not
eliminate all traversal or introduce a novel sparse-execution primitive.

Identical output archives share one compressed blob; export_manifest.json maps
each acquisition to that byte-identical blob. Existing W24 input banks, dense
arrays and unchanged RTL are referenced rather than duplicated.
export_manifest.json binds every added evidence file and the
complete set of author-written compiled modules, including unchanged sources.
Absolute paths in original launch/build records identify author provenance;
portable replay does not need those paths. Bitstreams, vendor IP, build caches
and tool installations are excluded. This package supports offline result replay
and source inspection, not a one-command vendor-hardware rebuild.
