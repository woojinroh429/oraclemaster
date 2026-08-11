# THE 22% IS THE BEAM WIDTH, NOT THE AXIS -- AND MOST OF IT SURVIVES INTO PRODUCTION

axis_work.md measured a 21.6% gain on prob_16 offline and named its own confound in the last
paragraph: the table ran at a fixed B=96 and K=4, while `_worker` sizes every draw from the axis's
own Bmul and K, so axis 2 runs at B=67, K=5 in production.  Both halves have now been separated in
the shipped path, prob_1... prob_16 at 240 s:

    stock                          3,010,278   3,179,204     mean 3,094,741   control span 5.6%
    OGC_AXIS=2                                 2,932,602     -2.6%
    OGC_AXIS=2  OGC_BCAP=137                   2,725,778     -11.9%
    offline table, B=96 K=4                    2,477,998     -21.6%   (target)

Pinning the axis is worth 2.6%.  Widening the same axis from B=67 to B=96 is worth another 9.3%.
The effect is more than twice the control span on one cell, and the mechanism was written down in
the record months before anyone tested it.

`_beam_width` returns `max(8, min(_BCAP, int(mul * _BCAP)))`, so axis 2's Bmul of 0.7 reaches 96
only at _BCAP = 137.  That is the whole change: OGC_BCAP=137.

## WHAT IS STILL MISSING, AND WHERE IT PROBABLY IS

    achieved   -11.9%
    target     -21.6%
    unmatched  K = 5 in production against K = 4 in the table, with no environment override

K is read straight from the axis dict at four call sites.  Reaching it needs a code change, not a
knob, which is the next thing to try -- and it is now the only named candidate for the remaining
half rather than an open question.

## WHY THIS MATTERS FOR THE HIDDEN P1

prob_16's objective scale matches hidden P1 almost exactly: our median over 146 runs at 180-240 s
is 3,196,492 against the hidden P1's 3,018,944.  And our BEST ever draw on prob_16 is 2,454,368 --
the same value a competitor is reportedly getting consistently.  The capability is already in the
code; what is missing is returning it every time instead of once.

    hidden P1 today               3,018,944
    with -11.9%                 ~ 2,660,000    the best ticket we have ever drawn, every run
    with the full -21.6%        ~ 2,470,000    the level being compared against

## WHAT THIS DOES NOT YET SAY

One cell.  And prob_16 is the ONE instance in the axis table whose axis-2 margin is large and never
flips -- 2.05x to 2.51x, against under 1.2x on prob_4 and prob_24.  A width change may generalise
where axis concentration cannot, but that is an assumption until the width cell is run without the
axis pin and on the other two 3M-scale instances.  Both are queued.

The opposite result is also still live: myalgorithm.py's OGC_BEAMCAP comment measured wider draws
on this same instance as better on average and worse at the minimum.  This cell contradicts it, and
one of the two readings is about to lose.
