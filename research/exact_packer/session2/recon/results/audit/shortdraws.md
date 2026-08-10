# THE DRAW-COUNT LEVER IS ALREADY WIRED, AND ON prob_1 IT DOES NOT PAY

I told the user prob_1 buys "two tickets" per run and that OGC_ROUNDS would buy more.  The first
half is wrong and the logs already contained the correction.

PARFILL has been running a fill round of FOUR workers, ALL on the configuration that won round 0,
since it was adopted.  So the shipped structure on prob_1 is not 2 config-A draws, it is

    round 0     4 workers, 2 on config A, ~155 s each
    fill  1     4 workers, ALL on config A, ~73 s each

which is six config-A draws, not two.  The extra four are already being bought.

## HOW OFTEN THEY PAY

    prob    fill rounds   moved   move rate   median budget
    1              53       2         4%        73 s
    16             20       0         0%        62 s
    3              12       0         0%        64 s
    24              9       3        33%        69 s
    20             13       6        46%        62 s

On prob_1, four fresh draws from the RIGHT configuration, 73 s each, beat the best of the four
round-0 draws twice in fifty-three runs.

That is a direct measurement of the trade OGC_ROUNDS was going to sweep, on 53 samples, and it
says the quality side wins decisively at these lengths: a 73 s draw is not a worse ticket, it is
almost never a winning one.  Cutting 240 s into three or four rounds makes every draw shorter than
73 s, so the sweep's most likely finding is now that R=1 is right on prob_1.

The two instances where short rounds DO pay -- prob_20 at 46% and prob_24 at 33% -- are both
tardiness-family.  That is worth having and it is already shipped.

## WHAT THIS LEAVES FOR P1

Not quality: brk lifts prob_1's median worker 4.7% and leaves the minimum unchanged.
Not count at reduced length: measured above, 4%.

What is left is count AT FULL LENGTH, and there is exactly one place to get it -- round 0 spends
two of its four workers on config B, which in 540 draws has never gone below 516,577 while config
A's median is 530,650.  Making round 0 3+1 instead of 2+2 would take prob_1 from 2 long config-A
draws to 3, i.e. P(<= 450,000) from 0.30 to 0.41.

That requires knowing the family BEFORE round 0, which is what _demand_ratio_phys is for:

    threshold demand < 0.60 -> even family        11 of 13 instances correct
    misses: prob_4 (0.735, actually 82.5% even) and prob_30 (0.442, actually 19.6% even)

r = -0.607.  A threshold fitted to thirteen points with two known misses, and the cost of a miss
is that round 0 spends three quarters of itself on the wrong algorithm.  PARROUND does not have
this problem -- it MEASURES which configuration won round 0 rather than predicting it -- but it
can only act from round 1 onward, and round 1 is the 73 s round that pays 4%.

So the two ideas are complements and only one of them is safe.  Recorded, not adopted.

## AND ROUND 0 IS ALREADY LONGER THAN prob_1 CAN USE

Same logs, another natural experiment: some prob_1 cells ran a fill round and so had a short round
0, others ran none and had the whole budget in one round.  Comparing the CONFIG-A round-0 draws
(slots 0 and 2), over 240 s runs only:

    round 0 length      n     min       p25       median    P(<= 450,000)
    ~228 s (no fill)   204   422,629   439,374   504,490        0.27
    ~160 s              44   413,954   437,484   486,096        0.27
    ~150 s              28   422,629   437,484   469,427        0.43
    ~200 s              16   438,791   455,218   501,850        0.25
    ~120 s               8   422,629   422,629   454,859        0.50

Between 155 s and 228 s the distribution does not move: P = 0.27 in both large buckets, 248
samples.  prob_1's beam saturates well before the round ends, so the seconds after saturation buy
nothing WHERE THEY ARE.

This also corrects fillpower, which put 99 s at 486,096 against 199 s at 438,791 and was read as
"longer is better".  Those were single cells; on 248 they are the same distribution.

THE TWO SMALL BUCKETS POINT THE OTHER WAY AND I DO NOT TRUST THEM YET.  120 s reads P = 0.50 on
n = 8 and 150 s reads 0.43 on n = 28, both better than the long rounds.  They come from specific
experiments that changed other settings too, so the length is confounded.  What they do is make
the saturation point the question: if a 120 s draw is as good as a 228 s one, then 240 s buys FOUR
config-A draws instead of two, at full effectiveness -- and that is not the 73 s fill round, which
is below saturation and pays 4%.

p1draws R=2 gives rounds of about 120 s and is now the cell that matters most in that sweep.
