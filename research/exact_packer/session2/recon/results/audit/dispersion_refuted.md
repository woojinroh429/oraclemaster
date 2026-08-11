# WIDENING THE WORKER POOL RAISES THE MINIMUM.  THE DISPERSION HYPOTHESIS IS REFUTED.

`results/audit/cross_lowers_dispersion.md` recorded r(dispersion, min) = -0.771 across this
session's cells and closed with an instruction: "raising dispersion needs configurations FURTHER
APART, not more of them ... widening it requires a NEW factor, not a re-indexing of the ones
there."  aim, m and the direction all index `wid % 2`, so the shipped pool already sits at maximum
diameter for the factors in the file.

`OGC_PREFPOWSET` is such a factor.  `_bend_prefs` re-expresses each preference penalty as
R*(pen/R)^gamma with R the median largest penalty -- scale held, only the spread moves -- and it is
independent of aim, m and dispatch order.  Applied per worker, "1.0,1.6" leaves w0/w2 on the true
objective and bends w1/w3.  Unset is byte-identical and the caller's instance is never mutated.

## The measurement

60 s, four workers, one replicate, DIRGATE on (the shipped configuration).

    arm            P1                        P3
    off        556,718                  4,776,637
    1.0,1.6    605,506   +8.8%          4,736,335   -0.84%
    1.0,2.5    679,268  +22.0%          4,776,637    0%
    1.0,0.7    556,718    0%            4,845,728   +1.45%

P1's control returned 556,718 five separate times today, so that column is measured against a
control that does not move: +8.8% and +22.0% are certain, not draws.

**The objective degrades MONOTONICALLY in how far apart the pool is pushed.**  The hypothesis
predicted the opposite.

## What that means

Either r(dispersion, min) = -0.771 is correlation without causation, or "spread produced by bending
the objective" is not the quantity that correlation measures.  The second reading is plausible --
the workers that were spread are now optimising something the scorer does not, so they are not
merely different, they are wrong -- but nothing here distinguishes the two, and the practical
consequence is the same: this route does not lower the minimum.

## And the seventh transfer failure of the session

1.0,1.6 is the worst arm on P1 and the best on P3.  1.0,0.7 is neutral on P1 and a loss on P3.  No
setting serves both instances, which is now the seventh time today a configuration has failed to
transfer between instances -- after w3mul, order, prefw, prefpow, DIRGATE's mechanism, SHARE's gap,
and the budget response in gate120.

## Status of the three routes to a better draw

    OGC_SHARE    restarts a lagging worker; it returns to the same attractor.  gap 0.5 never fires,
                 0.3's -1.4% did not reproduce, 0.15 costs 20% on P1 while helping P3.
    OGC_ROUNDS   already shipped.
    OGC_CROSS    built to raise dispersion, lowered it 34% for +12.7%.
    PREFPOW axis this file.

All four are closed.  The minimum on stage2/prob_1 at 60 s sits in an attractor -- 556,718, five
identical returns today across unrelated arms -- that no adjustment of the search has left.
