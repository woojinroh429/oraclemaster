# WIDENING AXIS 2 ON ONE WORKER DOES NOTHING.  THE GAIN NEEDS THE WHOLE POOL.

prob_16 at 240 s, OGC_BMULSET=1.0,1.0,1.0,0.7,1.4,0.5 (axis 2's Bmul 0.7 -> 1.0, so that one
worker draws at B=96 instead of B=67; the other five axes untouched), paired against stock:

    rep         stock          bm2      delta
    r1      2,979,743    2,995,191     +0.52%
    r2      2,895,137    3,186,941    +10.08%
    r3      3,069,049    2,834,903     -7.63%
    r4      2,898,517    2,898,055     -0.02%
    r5      2,801,955    2,933,188     +4.68%

    mean    2,928,880    2,969,656     +1.39%
    worst   3,069,049    3,186,941     +3.84%
    span         9.5%        12.4%

    2 wins, 3 losses, mean of paired deltas +1.53%

Dead.  Slightly worse on the mean, worse at the worst draw, and wider.

## WHICH LOCATES THE GAIN PRECISELY

    OGC_AXIS=2 + OGC_BCAP=137   all four workers on axis 2 at B=96    -10.4%, 3 draws, no overlap
    OGC_BMULSET                 one worker  on axis 2 at B=96          +1.4%, 5 pairs

The -10.4% is not "axis 2 wants width".  It is "four workers all searching axis 2 at B=96", and one
such worker inside a rotating portfolio contributes nothing measurable.  That is consistent with
the run being a MINIMUM over workers: one better draw out of four moves the minimum only when it
happens to be the winner, and the other three are unchanged.

## SO THE PORTFOLIO IS THE PRICE, AND ONE NUMBER DECIDES

Pinning gives up rotation entirely.  axis_work.md measured axis 2's dominance as unique to prob_16
-- margin 2.05x to 2.51x there, under 1.2x on prob_4 and prob_24, and at the largest budget
prob_4's winner becomes axis 1 while prob_24's becomes axis 0 or 5.  Nobody has measured what
pinning to axis 2 costs on those.

    small cost   pin globally, no gate, no predictor
    large cost   a gate is needed, and it would have to name the dominant axis before round 0 --
                 exactly what the brk gate and the axis gate needed and never got

harness/axrisk.sh runs prob_4 first at five pairs, then prob_1.  prob_4 is the same objective scale
as prob_16 and is the instance where axis 2 is NOT the answer, so it prices the insurance the
portfolio is currently buying.
