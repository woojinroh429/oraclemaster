# Deterministic measurement, and the six prescriptions it killed

## The tool

`OGC_WORKCAP=<state expansions>` replaces `elapsed()` with the engine's own `work` counter in the
beam's stop test and in both width controllers.  Nothing in the search then reads a clock.

    three runs, prob_16, work=4000, B=96, K=4, axis 0
      obj=6,684,986  digest=00e0c6a4b5d1da5e   wall 18.3s
      obj=6,684,986  digest=00e0c6a4b5d1da5e   wall 18.5s
      obj=6,684,986  digest=00e0c6a4b5d1da5e   wall 18.5s

Identical objective and identical placement.  For comparison, the shipped clock-driven build
returns 3,061,389 .. 3,661,692 on that instance at one budget -- a 19.6% band against arm effects
of 2-5%, which is why every A/B this session was unreadable.

NOT A SHIPPING MODE.  The competition budget is wall-clock.  What it buys is a two-part evaluation:

    1. equal-work A/B    does the arm search better per unit of work?    (no noise)
    2. throughput        how much work does it get done per second?      (average over ~250 levels)
    3. combine           quality at work = throughput x seconds

Those two were confounded in every comparison made before it existed.

    harness/beam1.py     one beam, one config, one work budget; prints objective + placement digest
    harness/axwork.sh    quality(axis, work);   harness/axworkread.py scores allocation policies
    harness/axwidth.sh   axis's own width vs B=96 at equal work; harness/axwidthread.py

## What it killed, and why each died

**OGC_ORORD (orientation scan order).**  Built on the argument that reordering cannot change the
answer because `bestsc` spans the orientation loop and the cell bound is exact.  True at fixed
work, false in production, where the time-adaptive width reacts to any speed change: prob_1 read
-14.1% then +7.1% on consecutive draws.  At equal work, `ORORD=0` and `ORORD=1` return the same
objective AND the same digest, and the wall times match -- no quality gain, no throughput gain.
Settled in four cells; the noisy method would have needed about a hundred per arm.

**OGC_BEAMCAP (cap the seconds one draw may ask for).**  Four wall-clock cells gave +2.73%,
-1.55%, -5.02%, +1.32% -- unreadable.  The work table explains it: prob_16's productive axis reads
3,159,373 at 3,000 work and 2,477,998 at 6,000, so that instance wants LARGER draws and the cap
makes them smaller.  The cap was pointing the wrong way on the instance it was tested against.

**OGC_BCAP (raise the beam width ceiling).**  The obvious follow-up -- if draws want more work,
widen them -- and it is wrong.  Pairing each axis at its own Bmul-derived width against B=96 at
equal work, 16 of 18 cells at w=3000 are identical to the last digit across B=48/67/96; the two
exceptions are prob_16 axis 2 (+0.98%) and axis 3 (-2.40%).  Once work is the budget the adaptive
controller makes a width ceiling inert: narrowing the beam leaves work unspent and `Bcur` grows
back.  Work is the currency, width is only how it is spent.

**Splitting a budget into more than six draws.**  With no clock in the search, one (axis, work)
pair has exactly one answer.  `_worker` draws `axes[gen % 6]`, so a worker can produce at most six
distinct results per work level; the seventh draw re-derives one it already holds.  In production
they differ only because the clock perturbs them.  Structural, not empirical.

**Adaptive axis selection.**  The margins looked enormous -- prob_16 axis 2 beats the runner-up by
2.05x/2.13x/2.51x/2.22x across four work levels.  But two of three instances change their best axis
at the largest budget: prob_4 goes axis 2 -> axis 1, prob_24 goes axis 0 -> axis 5.  So a cheap
probe picks the axis that wins AT PROBE SIZE, and then concentrating budget on it changes which
axis wins.  The probe is trustworthy only where the margin is large, and where the margin is large
there is nothing to decide.

**The mono ladder, OGC_AXJIT, OGC_ADAPTB=0.**  Measured in wall-clock earlier the same day; all
inside the noise or clearly worse.  The ladder's idea -- keep a narrow answer and replace it only
when beaten -- is not refuted by that, only unmeasurable through the clock.

## What survived

One thing: **the work per draw matters, and production may be spending too little.**  Minimum over
all axes at each work level, which is what a worker returns whichever axis produced it:

    work        1500        3000        6000       12000
    P16      3,247,623   3,159,373   2,477,998*  2,816,901
    P4       2,916,374*  3,028,676   2,945,225   2,953,661
    P24      3,168,404   3,080,029   2,949,426   2,856,697*

prob_16 wants 6,000, prob_24 is still improving at 12,000, prob_4 is flat within 3.9%.  No common
optimum, so no constant to set -- but the direction is consistent in a way axis choice is not.

## The open question, and an estimate that has to be replaced

The prescription rests on production spending ~3,000 work per draw, and that figure is an ESTIMATE:
14 s of measured draw time at ~220 expansions/s from beam1.  It has never been measured.

It also does not currently have a mechanism.  A draw is handed 47.2 s by the operator loop and
returns in 14 s, so seconds are not binding; and width is now shown not to matter at fixed work.
If both are true, something else stops a draw at 3,000, and the prescription has no handle until
that is known.

`beam_work()` is added to the engine for exactly this -- the loop already accumulates the number.
Rebuild and read it from a real 240 s run before designing anything further.  Note that if the true
figure is near 6,000 rather than 3,000, prob_16 is already at its optimum and this entire direction
closes.
