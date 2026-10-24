# Paired window implementation evaluation

This is a bounded engineering evaluation on existing development workloads,
not an unseen-workload validation. All previous experiments remain separate.
This protocol is prospective; a launch manifest must pin actual sources,
bitstreams, firmware, weights, fixture and masks before the physical comparison.

## Question and attribution

Can a channel-packed synchronous window implementation relieve the accepted
accelerator's logic-memory bottleneck while preserving exact selected outputs,
publication safety and useful service performance at the same 50 MHz?

The historical and replacement implementations differ in channel organization,
control sharing, memory mapping and one elastic read stage. Their full-system
comparison measures that combined implementation change. A separate module
synthesis comparison changes only the replacement's memory-style parameter,
distributed versus block, to isolate primitive allocation. Do not attribute
the full integrated difference to BRAM alone.

## Qualification before physical evaluation

- Check padded windows against an independent byte oracle for 3 and 24 channels,
  widths including 1, 2, 3, 7, 31, 64, 127, 639 and 640, variable heights,
  dense and zero-hole inputs, burst stalls and slow convolution-like consumers.
- Check output stability under backpressure and reset with a demonstrated live,
  stalled output and pending memory read. Distinguish reset-separated region
  reuse from continuous frames without reset.
- Run the unchanged trained integer graph through the actual stream and guard
  integration. Check every selected output against the independent dense oracle.
  Include corners, interior, multiple regions and overlapping input halos.
- Retain malformed-packet, cancellation, expiration and clean-reuse checks.
- Accept a physical candidate only after 50 MHz route timing and DRC checks.
  Report synthesis and routed resource counts separately.

## Physical comparison

Use the accepted 50 MHz reference and the newly qualified 50 MHz candidate,
identical ARM firmware and launch configuration, weights, lane counts, DMA
boundary, input fixture, mask requests and private-publication rules. Do not
change board voltage, clock settings or persistent boot media.

The reference workload is the complete existing 15-mask suite plus empty and
dense controls. Run all three organizations: full raster, outer bounding box
and vertically merged row runs. Use the existing six-repeat counterbalanced
campaign, with its 51 warmups and 306 measured requests per launch. Preserve
first-repeat selected bytes for all 51 cells; all repeats retain checksums,
counts, identities and terminal status. Numerical validation and JTAG archival
remain outside the service timer.

To reduce a single image-order confound, use four launches in fixed order:
reference, candidate, candidate, reference. No launch is selected or repeated
because its timing is unfavorable. Stop at the first numerical, protocol,
timing-configuration or capture-integrity failure and preserve that failure.
Engineering repairs require a new recorded identity and a separately declared
comparison; they cannot erase an unsuccessful launch.

If the bounded time or an equipment issue prevents the full four-launch
comparison, label the work as incomplete engineering qualification. Do not
silently substitute one convenient run as confirmation.

## Outcomes

Primary architectural outcomes are complete routed LUT, LUTRAM, FF, DSP, BRAM
and slice use at the accepted clock. Primary timing outcome is equal-mask mean
request-to-selected-residual-publication time for merged execution, paired by
mask and reported for each launch as well as both launches per implementation.
Report all organizations, dense and empty controls separately, every per-mask
regression, and changes in transferred words and phase timings. Do not pool
empty masks into a sparse-performance average.

The hardware request-completion timer does not end at the later CPU publication
token. Performance deadlines remain disabled exactly as in the reference.
This is not reconstructed-image delivery, physical display, measured energy,
or an Fmax comparison. A smaller resource footprint at equal or slightly worse
latency is a valid engineering outcome; it does not establish architectural
novelty or publication acceptance.

## Research decision

After the measurements, assess whether the change establishes an informative
resource/service trade-off or changes which organization is preferable. If the
result only confirms that ordinary BRAM mapping saves LUTs, describe it as an
implementation improvement. Do not manufacture a new algorithm or reopen a
larger redesign to obtain a desired publication verdict.
