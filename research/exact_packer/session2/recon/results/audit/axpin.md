# PINNING AXIS 2 AT B=96 WINS BIG WHERE AXIS 2 DOMINATES AND COSTS NOTHING WHERE IT DOES NOT

    OGC_AXIS=2 OGC_BCAP=137     all four workers on axis 2, width ceiling raised so Bmul 0.7
                                reaches B=96 -- the width the offline table was measured at

## prob_16, 240 s (axis 2 dominant: margin 2.05x-2.51x, never flips)

    stock   3,010,278  3,179,204  2,979,743  2,895,137  3,069,049  2,801,955  2,898,517
            mean 2,976,269
    pin     2,725,778  2,913,538  2,577,514
            mean 2,738,943      -10.4%, and all three draws sit below every stock draw

## prob_4, 240 s (axis 2 NOT dominant: margin under 1.2x, winner flips to axis 1 at 12000 work)

    rep         stock         pin      delta
    r1      2,675,413   2,590,915    -3.16%
    r2      2,683,821   2,761,692    +2.90%
    r3      2,728,438   2,683,821    -1.64%
    r4      2,765,025   2,691,085    -2.67%
    r5      2,757,408   2,753,410    -0.14%

    mean    2,722,021   2,696,185    -0.95%      4 wins, 1 loss
    worst   2,765,025   2,761,692    -0.12%
    best    2,675,413   2,590,915    -3.16%
    span         3.3%        6.6%

The insurance the portfolio was buying turns out to cost almost nothing.  prob_4 was chosen as the
instance where pinning should hurt -- axis_work.md measured its axis-2 margin at 1.04x-1.17x with
the winner becoming axis 1 at the largest budget -- and it does not hurt.  The span doubles, but it
doubles DOWNWARD: the worst draw is unchanged (-0.12%) and the best improves 3.16%.

## WHY THE OFFLINE TABLE MISLED ON THIS

The table ranks ONE beam draw per axis.  Production takes a minimum over four workers, then runs an
operator loop and a polish on the winner.  An axis that ranks second on a single draw can still be
the better thing to spend four workers on, because what matters is the distribution the minimum is
taken over, not the median draw.  That is why "axis 2 is only dominant on prob_16" did not predict
what pinning does in production.

## WHAT IS NOT YET DONE

prob_16 is still THREE draws, and it carries the entire case for the gain.  It has to go to five
pairs before this ships -- three-draw readings have been overturned nine times in this session.
prob_1 (a different scale entirely, ~2.7M against ~450k) is running now as a third shape.

If both hold, this ships with no gate and no predictor: one environment pair, applied always.
