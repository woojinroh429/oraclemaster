# ON prob_1, HALF THE COMPUTE HAS NEVER PRODUCED A USABLE DRAW

1,080 round-0 worker draws on prob_1, pooled over every WSTAT line in results/audit -- 270 per
worker slot.  WSTAT prints `_ws` in wid order, and the configuration split is wid % 2, so the slot
is the configuration.

    wid      n        min       p25     median        max   P(draw <= 450,000)
    0      270    422,629   472,330    556,620    911,134        0.21
    1      270    516,577   689,851    743,988    928,145        0.00
    2      270    422,629   499,210    517,690    962,103        0.11
    3      270    532,868   706,039    763,167  1,020,924        0.00

    config A (even)  n=540   min   422,629   p25 472,330   median 530,650   P = 0.16
    config B (odd)   n=540   min   516,577   p25 698,256   median 754,739   P = 0.00

CONFIG B HAS NEVER ONCE GONE BELOW 516,577 IN 540 DRAWS.  Its best draw ever is 22% worse than
config A's median.  Two of the four cores are not buying a worse ticket on this instance -- they
are buying a blank.

## WHAT THAT DOES TO THE ARITHMETIC

The score is the minimum, so only config-A draws count, and there are two of them per round:

    2 config-A draws  P(<= 450,000) = 0.30      <- what ships today
    3                                 0.41
    4                                 0.51
    6                                 0.66
    8                                 0.76
    11                                0.86      <- OGC_ROUNDS=4 with PARROUND=3

That is the whole of P1's 18.6% band across the 7th, 8th, 10th and 11th entries, restated: the
entries have been drawing twice from a distribution whose 16th percentile is the target.

## WHY THIS IS NOT AN OVERFIT

Nothing here is a threshold fitted to prob_1.  PARROUND reads `_par` -- the best objective each
configuration actually reached in round 0 of THIS run -- and sends three of the four workers to
whichever won.  On prob_20 the same code sends them the other way; the argmin counts there are
4, 69, 4, 95, i.e. config B wins 95%.  The selection is a measurement made at runtime on the
instance being solved, not a rule about which instances are which.

The residual risk is that round 0 ranks the two on ONE draw each from a distribution whose spread
is 105%, so it can rank them wrong.  That is why one worker stays on the losing side: the wrong
call costs a third of a round instead of all of it.

## THE ONE THING HERE I CANNOT EXPLAIN

wid 0 and wid 2 are the SAME configuration and differ only in seed, and they are not the same:
P = 0.21 against 0.11, p25 472,330 against 499,210, over 270 draws each.  A pure seed difference
should not do that.  Candidates: the share directory is read in wid order, worker 0 starts first
and so sees an emptier share, or the axis rotation _AXES[(wid + i) % len(_AXES)] favours slot 0.
Unresolved, and worth its own experiment -- if slot 0's advantage is real and portable, it is
another free draw.
