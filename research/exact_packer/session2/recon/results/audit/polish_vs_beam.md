# The final polish contributes almost nothing, and it had been inflating this session's readings

Every run prints its four worker objectives (OGC_WSTAT) and its final objective.  The final is
min(workers) followed by _z3_improve, so the difference between them is exactly what that last
pass earned.  Across all 804 runs in results/audit that have both:

    polish gain (min-worker -> final):   median 0.00%   mean 0.33%   max 10.53%
        gained nothing (<0.01%):  419 of 804
        gained more than 5%:      3

More than half of all runs get nothing at all from a pass that is handed min(20% of budget, 40 s).

## Why this matters beyond the budget it wastes

Three runs in 804 gained over 5%, and one of them was prob_24 arm m2 in the mcand queue -- the run
this session reported as evidence that permutation search wins by 14.5%.  Splitting it:

    P24  m1   best worker 2,838,115   final 2,838,115   polish  0.00%
    P24  m2   best worker 2,712,545   final 2,427,040   polish 10.53%
    P24  m2w  best worker 2,706,978   final 2,706,978   polish  0.00%

The beam-side difference between m2 and m1 is -4.4%, not -14.5%.  And m2w, reported here as
"widening the beam made it worse by 11.5%", is 0.2% BETTER than m2 on the beam side -- the entire
gap was one arm drawing the polish outlier and the other not.

The claim built on top of that ("a wider beam converges the workers and hurts") has no support and
is withdrawn.

## What survives, and is stronger for being smaller

    beam-side, best worker, m2 against m1
        P24   2,712,545 vs 2,838,115   -4.4%
        P4    2,460,292 vs 2,551,983   -3.6%
    beam-side, m3 against m1
        P24   2,923,290 vs 2,838,115   +3.0%
        P4    2,829,562 vs 2,551,983   +10.9%

m=2 improves the construction on both instances by a consistent 3.6-4.4%, and m=3 hurts on both.
That is a smaller headline than -14.5% and a much better-behaved one.

## Read the beam, not the final

Every arm comparison in this session used the final objective.  Where the polish fires it adds up
to 10.5% of pure noise on top of the thing being measured, and it fires rarely enough that it lands
on one arm and not another.  Comparisons from here on should use min(workers).
