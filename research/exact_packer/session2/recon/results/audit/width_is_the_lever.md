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

## CORRECTION: IT IS THE INTERACTION, NOT THE WIDTH

The width-only cell landed and it changes the reading above.  prob_16 at 240 s:

    stock                     3,094,741   (two draws, span 5.6%)
    OGC_AXIS=2 alone          2,932,602    -2.6%
    OGC_BCAP=137 alone        3,018,252    -2.5%
    both                      2,725,778   -11.9%

Singly they are worth 2.6% and 2.5%; together they are worth 11.9%, more than twice their sum.
The heading written a few minutes ago -- "the 22% is the beam width" -- is wrong.  Axis 2's
scoring only pays when it is given the wider beam: at Bmul 0.7 it runs at B=67 and is starved, and
a wider beam given to the rotating portfolio mostly widens axes that were not starved.

## WHICH MAKES THE OBVIOUS DEPLOYMENT THE WRONG ONE

    raise OGC_BCAP globally           -2.5%    portfolio intact, safe, small
    pin axis 2 and raise OGC_BCAP    -11.9%    portfolio gone

Pinning puts every worker on one axis, and axis_work.md measured that axis 2's dominance is unique
to prob_16: on prob_4 the winner flips from axis 2 to axis 1 at the largest budget, and prob_24
answers axis 0 or axis 5.  Concentrating on axis 2 everywhere would lose badly on exactly the
instances where the margin is small -- which is most of them.

## THE FORM THAT KEEPS BOTH

Give axis 2 the width without taking the portfolio away.  `_beam_width(mul)` returns
`max(8, min(_BCAP, int(mul * _BCAP)))`, so raising axis 2's own Bmul from 0.7 to 1.0 puts that one
worker at B=96 and leaves every other axis exactly where it is:

    _AXES[2]: Bmul=0.7 -> 1.0     one line, one axis, no gate, no prediction

The rotation still covers the other five axes, so an instance whose best axis is not 2 is unharmed,
and an instance like prob_16 gets a worker that is no longer starved.  What this cannot do is give
axis 2 three workers' worth of budget -- so it should land between the -2.5% and the -11.9%, and
where it lands is the measurement that decides whether it ships.

## SECOND CORRECTION: THE INTERACTION CLAIM WAS ALSO A ONE-DRAW READING

The width-only arm's second draw came in at 2,714,034 against its first at 3,018,252.  Two draws
per arm now:

    stock                     3,010,278  3,179,204    mean 3,094,741   span  5.6%
    OGC_BCAP=137 alone        3,018,252  2,714,034    mean 2,866,143   span 11.2%   -7.4%
    OGC_AXIS=2 + BCAP=137     2,725,778  2,913,538    mean 2,819,658   span  6.9%   -8.9%

Width alone is -7.4%, not the -2.5% its first draw suggested, and pinning the axis on top adds
1.5 points.  The "the gain is the interaction" paragraph above was written on a single width-only
cell and does not survive its second.  At two draws per arm against spans of 7-11% these two arms
are not distinguishable from each other at all -- only from stock.

THAT IS THE SEVENTH CLAIM THIS SESSION MADE AT ONE OR TWO DRAWS AND OVERTURNED BY THE NEXT.  The
pattern is not incidental: prob_16's draws span 11% within an arm, so any two-cell comparison is
reading noise, and every time an interesting first cell appeared it got written up before the
second arrived.

## WHICH MAKES THE SIMPLE DEPLOYMENT THE LIVE ONE AGAIN

    OGC_BCAP=137            portfolio intact, one constant, -7.4% at two draws
    plus pinning axis 2     portfolio gone, +1.5 points, and axis 2 dominates only prob_16

The risky half is buying almost nothing.  Raising the ceiling alone keeps rotation, needs no
prediction, and takes most of what is there -- if it holds at five pairs, which is the measurement
that has to happen before any of this is believed.

OGC_BMULSET (axis 2's own Bmul to 1.0) was built for the case where the axis pin was carrying the
gain.  It is now the second question, not the first.
