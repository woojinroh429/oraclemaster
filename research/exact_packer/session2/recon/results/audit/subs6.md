# Sixth submission: the aim spread, and the hidden set cannot see it either way

Submitted 2026-08-07 17:14:12 UTC, `OGC_AIMSET` defaulting to `0.90,0.60,0.30,0.10` instead of the
shipped `0.90,0.10`.  Everything else identical to the fifth.

    inst           4차          5차          6차        6v5      6v4    best-ever   6 vs best
    P1        2875074     3062061     2883654     -5.83%   +0.30%     2847060      +1.29%
    P2       20164596    19944390    19785239     -0.80%   -1.88%    19829534      -0.22%
    P3        5856298     5781273     5715679     -1.13%   -2.40%     5613271      +1.82%
    P4        4439801     4428834     4372076     -1.28%   -1.53%     4283430      +2.07%
    P5        6109330     6187757     6059733     -2.07%   -0.81%     6104015      -0.73%
    P6        1052516      968674     1049207     +8.31%   -0.31%      968674      +8.31%
    P7       15807529    16344347    16074005     -1.65%   +1.69%    15807529      +1.69%
    P8       16695656    16592165    17337659     +4.49%   +3.85%    16023014      +8.20%

    total    73000800    73309501    73277252     -0.04%   +0.38%

    6 vs 5: better 6 / worse 2, median -1.21%, range -5.83% .. +8.31%

## It reads as a small win and it is not readable at all

The third and fourth submissions were the SAME BUILD, verified by hash.  That pair is this
project's measured submission noise floor:

    3 -> 4  (identical code)   median -0.07%   range -5.16% .. +8.66%
    6 -> 5  (aim spread)       median -1.21%   range -5.83% .. +8.31%

The spread row sits inside the identical-code row on every statistic.  Six-better-two-worse and a
-1.21% median are what re-running one build produces.

## And it disagrees with the training set, which DOES have resolution

Paired inside one queue at 240 s, spread against 0.90,0.10:

    P4    +5.66%     base repeats to the digit, four times today
    P20  +10.90%     cross-queue base spread 1.7%
    P1   +21.50%     base repeats to the digit, four times across two queues
    P16  -13.85% / -6.36%   the only win, and the least stable arm
    P6    +0.36%

The two measurements are not equally informative:

    training, same-queue pairs   noise 0.00% on P1/P4    effect +5.7% .. +21.5%   RESOLVED
    hidden, submission-to-submission   noise +-5..8%     effect ~1%               NOT RESOLVED

The hidden set did not say the spread is fine.  It said nothing, because its noise is several
times the effect.  A measurement without resolution does not overturn one with it, so the revert
stands.

## Why the spread loses, from the training queue

Each end of the aim range previously had TWO workers and the answer is a minimum over the draws at
each depth.  Spreading gives each depth ONE.  Measured stability, same build, same instance:

    P1    base 501,758 four times to the digit    spread 609,812 then 516,577   18.0% apart
    P16   base 0.11% between reps                 spread 8.8% apart

So the failure is variance, not mean.  This does not contradict the min-of-N argument made earlier
the same day -- variance in the DRAWS pushes the minimum into the left tail and is good; variance
in the ANSWER is luck and is bad.  The spread bought draw diversity by cutting the sample count at
each diversity point to one, and that trade lost.

The structural consequence: on four cores, two depths with a pair each is the maximum.  The
remaining freedom is WHICH two depths, and 0.90/0.10 has never been compared with anything --
it is simply the value that was set.

## P6 is two attractors, again

    968,674 (3rd, 5th)   1,024,046   1,049,207 (6th)   1,052,516   1,053,770

Six submissions and P6 lands near one of two values.  The +8.31% on this submission is which basin
it fell into, not a quality difference.  Same structure as the stage2 attractor table.

## Six submissions, totals still inside 1.4%

    74,003,416 / 73,283,064 / 73,981,407 / 73,000,800 / 73,309,501 / 73,277,252

The identical-code pair alone accounts for 1.33% of that band.  Reading the submitted total as a
scoreboard remains a mistake: eight instances cannot resolve the size of effect this work produces,
and the only way to learn anything at this scale has been same-queue paired measurement on
instances whose baseline repeats to the digit.
