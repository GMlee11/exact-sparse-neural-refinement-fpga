# Physical fault/reuse qualification after P003

P003's frozen performance capture is complete and byte-verified. This separate
bounded engineering check does not alter it, rerun performance, or change RTL.
The same fixed-50-MHz B002 image runs the F008 safety firmware. Its helpers are
included directly from the byte-identical qualified performance source.

Predeclared sequence: publish the six-tile `clustered_rectangles_10` fixture,
then five injected failures, each followed by a successful real-output reuse:

1. Cancel after the first nonfinal region has produced 15,360 private words.
2. Expire between regions at a 50,000,000-cycle request budget, despite changing
   the live budget to UINT32_MAX and clearing live deadline enable afterward.
3. Submit a region without its required three-pixel halo.
4. Submit the same owned region twice within one request.
5. Restart an active request while changing the configured source identity.

For each failure, require the expected hardware terminal outcome, inactive and
noncommitted state, unchanged last committed hardware source, unchanged public
software frame/bank token, and word-for-word preservation of the published
selected residual. Normal PREPARE, not FPGA reset, must permit each subsequent
real-output request. Every successful reuse must clear error state, commit its
new source and preserve the numerical result.

Failing requests invert the original input bytes. The first private region
overlaps the seed's tile24, is scattered into the opposite private bank as in
production, and must contain at least one different word from the published
tile. This prevents equal-value writes from making preservation checks vacuous.
The original input is restored before each clean reuse. F007/P004 were prepared
but never launched; F008 uses this stronger fixture without changing RTL.

Archive all 11 public-output snapshots (seed, five failures and five reuses)
and compare every word offline against the independent dense integer oracle.
Record all outcomes and terminate on the first failed assertion; no automatic
retry. This corroborates selected physical failure paths; it is not exhaustive
formal verification or a complete display-deadline test. The failure token
check is a synchronous-consumer host integration check, not a claim about
arbitrarily many outstanding readers.
