# WHAT brk'S OWN ACCOUNTING SAYS, AND WHY prob_20 WAS NEVER EVIDENCE

Measured on the brkcal queue, i.e. WITH the calibration guard in place.

## The objective shares, computed from each run's own Z terms and the instance's own weights

    prob_3    Z1  11.0%   Z2 1.0%   Z3 88.0%
    prob_1    Z1  13.4%   Z2 0.3%   Z3 86.3%
    prob_16   Z1  51.0%   Z2 0.3%   Z3 48.7%
    prob_24   Z1  76.5%   Z2 0.3%   Z3 23.2%
    prob_20   Z1  84.7%   Z2 0.1%   Z3 15.2%

## The result on each

    prob_3    Z3 88.0%   r1 -2.55%  r2 -0.17%   BOTH brk draws below BOTH control draws
    prob_1    Z3 86.3%   -6.52% over three replicates (measured with the bug live)
    prob_16   Z3 48.7%   +2.14%
    prob_24   Z3 23.2%   +1.84%
    prob_20   Z3 15.2%   see below -- NOT a result

## prob_20 IS NOT A DATA POINT, AND I REPORTED IT AS ONE TWICE

Two things kill it.

The controls do not repeat.  r1 off = 8,850,352 and r2 off = 8,769,505, which is 0.91% apart,
and the whole claimed brk effect was 0.91% and 0.45%.  Effect over spread is about 1.  The reason
8,769,505 appeared as both r1's brk and r2's control is that this instance lands in discrete
basins, not that the instance is deterministic -- which is what I asserted when I built the queue.

And brk's own opstat says it did nothing.  Sixteen worker-rounds across the two brk cells:

    r1  5.7  13.4  0.8  7.6  1.4  2.0  1.4  1.7   gain 0 on every one   (34.0 s)
    r2  7.7   8.3 17.7 14.7  1.4  1.3  0.0  0.6   gain 0 on every one   (51.7 s)

The operator never improved its worker's incumbent once.  Whatever moved the objective, it was
not brk; it was the beam being handed a different number of seconds.  So prob_20 measures the
COST of brk (34-52 worker-seconds) and nothing else, and the cost is real.

Contrast prob_3, where the same column is non-zero:

    r1  4.6  8.5 37.0  0.3 | 7.4  0.6 18.6  0.6    gains  0  0  69,766  0 | 0  0  14,111  0
    r2 37.5 35.2  5.4 38.6                         gains 39,641 12,565  0  0

## WHAT THIS DOES TO THE Z3 GATE

The gate drafted in scratchpad/z3gate.py put the crossover in the 48.7-86.3 gap on the strength of
prob_1 alone above it.  prob_3 at 88.0% is now a second instance above the gap, measured after the
calibration fix, with a 4/4 ordering against its controls.  Three instances sit below it and all
three lose.  The threshold is still FITTED -- five labelled points cannot derive one -- but it is
no longer fitted to a single positive case.

## THE DECIDING TABLE: brk's OWN GAIN COLUMN, EVERY CELL EVER LOGGED

Not a comparison of draws.  This is what the operator reported about its own effect on its own
worker's incumbent, summed over every brk worker-round in results/audit/*.log.

    prob   Z3 share   worker-rounds   paying   pay rate   brk seconds   raw gain
    3        88.0%              40        8       20%           599.3    202,603
    1        86.3%              80       44       55%         2,005.2  1,291,476
    16       48.7%              46        0        0%           391.6          0
    24       23.2%              24        0        0%            92.2          0
    20       15.2%              48        0        0%           234.2          0

**118 worker-rounds on the three low-share instances and not one of them returned a gain.**  718
worker-seconds spent, zero collected.  Against 52 of 120 paying on the two high-share ones.

This is a different kind of evidence from everything quoted for the gate before it.  The five
end-of-run objectives were draws, and prob_1's controls alone span 437,484 to 492,458, so a
five-point ordering of draws is close to meaningless.  A 0-of-118 against a 52-of-120 is not a
draw ordering; it is the operator saying, on every single occasion, that it found nothing.

WHAT IT DOES TO THE DOWNSIDE.  The objection to any fitted threshold is that it might switch the
operator off where it would have earned.  On these three instances there is nothing to switch off:
gating them costs the microseconds of _obj_shares and the 718 seconds come back to the beam.  The
risk is entirely on the other side -- switching it off where it DOES earn -- and that is not
governed by the threshold's placement in the 48.7-86.3 gap but by whether the MID-RUN share the
gate actually reads lands on the same side as the finished run's.  Which is what brkgate measures,
and until it has, the gate stays off.

## prob_1 SPLIT BY WHETHER brk ACTUALLY RAN (opstat tried > 0, not by tag name)

    brk ON    n= 11   reached 422,629  4 (36.4%)   median 437,484   worst 538,936
    brk OFF   n=305   reached 422,629 15 ( 4.9%)   median 518,803   worst 822,149

The minimum is 422,629 in BOTH arms.  brk does not find a floor the search cannot reach; it
reaches the existing floor far more often.  The median moves 518,803 -> 437,484 (-15.7%) and the
worst case 822,149 -> 538,936, and on a per-instance score the worst case is what sets the tier.

CAVEAT, RECORDED BECAUSE I OVERSTATED IT ONCE.  I priced two consecutive 422,629 hits against a
4.3% base rate and called it p = 0.002.  r3's CONTROL then returned 422,629 on its own.  The 4.9%
figure is over 305 runs of many different builds; the current build (rf35 + POLCAP 5) reaches that
basin more often than the historical average, so the true null for THESE replicates is higher than
4.9% and the p-value is optimistic.  n = 11 on the brk side is small.  The 0-of-118 gain column
remains the stronger evidence because it is not a comparison of draws at all.
