# THE SEED ADVANTAGE DOES NOT REACH THE SCORE.  THAT IS THE NIGHT'S ANSWER.

## bk67 on prob_1, three pairs

    r1   base 464,757   bk67 445,311    -4.18%
    r2   base 437,484   bk67 422,629    -3.40%
    r3   base 422,629   bk67 499,210   +18.12%
                                       --------
                                mean    +3.51%

Unpaired the two arms are indistinguishable:

    base  {464,757  437,484  422,629}   median 437,484   min 422,629
    bk67  {445,311  422,629  499,210}   median 445,311   min 422,629

## WHAT WAS BEING TESTED, AND WHAT IT MEANS THAT IT FAILED

The deterministic (axis, work) table is the cleanest measurement this project has: one answer per
cell, placement digests, and three values reproduced EXACTLY from an earlier session on a
different build.  It says the two Bmul 0.7 / K 5 axes are first and second on prob_1 and prob_16 --
two instances from two objective families -- at every work level tested, ahead of third place by
1.7x to 2.6x.

OGC_AXSET=bk67 gave every axis that width and branching factor and changed nothing else, keeping
all six orders and weights so the portfolio stayed intact.  The seed advantage it delivers is
real and large.  The score does not move.

So: a 2.3x improvement in seed quality is worth zero at the finish.  The operators plus the
minimum-over-workers are very nearly invariant to the quality of what they are given.

That is not a disappointing result to route around.  It is the most important structural fact
established tonight, and it retires an entire class of ideas -- every "make the beam construct
better" proposal -- on evidence rather than on failure to find one.

## IT ALSO EXPLAINS THE 0.4%

    one construction, prob_16 axis 2, work 6,000, 32 s, one core   2,477,998
    the full run, 240 s x 4 workers, 960 core-seconds              2,469,078

The pipeline is worth 0.4% over a single good seed AND it erases a 2.3x seed advantage.  Both
statements are the same statement: the back half of this algorithm dominates its front half, and
it dominates it by flattening it.

## THE PATTERN I KEPT FALLING FOR

Four times tonight a two-replicate result reversed on the third: ax5, brk on prob_1, prob_20, and
now bk67.  In every case the reversal came when the CONTROL drew 422,629 -- prob_1's floor basin.
Any arm that perturbs the search resamples away from a control that already landed on the floor,
so paired comparison on this instance is decided by which arm's control drew well.

Two replicates is not a small sample here.  It is a systematically misleading one.
