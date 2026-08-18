# The 8th submission: two all-time bests, and the two instances the priority is about got worse

    inst          6th          7th          8th        7v6      8v6   8 vs best
    P1        2883654      2685759      3009531     -6.86%   +4.37%    +12.06%
    P2       19785239     22600214     18973288    +14.23%   -4.10%     -4.10%  NEW BEST
    P3        5715679      5569691      5972740     -2.55%   +4.50%     +7.24%
    P4        4372076      4488812      4753731     +2.67%   +8.73%    +10.98%
    P5        6059733      7213113      6163858    +19.03%   +1.72%     +1.72%
    P6        1049207       975094       941132     -7.06%  -10.30%     -2.84%  NEW BEST
    P7       16074005     16943723     16537717     +5.41%   +2.88%     +4.62%
    P8       17337659     19765033     16683601    +14.00%   -3.77%     +4.12%

    total     73277252     80241439     73035598     +9.50%   -0.33%
    3 better / 5 worse, median +2.30%

What shipped: adaptive beam aim, and the m=1/m=2 worker portfolio.  The 7th's three global
overrides were reverted.

## What is outside the noise

Identical code resubmitted (3rd vs 4th entry) reads median -0.07%, range -5.16% .. +8.66%.  Against
that floor:

  - P6 at -10.30% is a real gain and an all-time best.
  - P2 at -4.10% is an all-time best but sits inside the floor.
  - P4 at +8.73% is at the edge of it, and P4 has now gone backwards in both the 7th and the 8th.
  - the -0.33% total is the first time any entry has come in under the 6th, and it means nothing on
    its own.

## The part that matters for the stated priority

The priority is to cut the hidden set's early instances hard and accept 2-4% elsewhere.  On exactly
those three the 7th and the 8th are mirror images:

    inst    7th       8th
    P1    -6.86%    +4.37%
    P2   +14.23%    -4.10%
    P3    -2.55%    +4.50%

DO NOT over-read this.  Across all eight instances the two submissions' deltas correlate at
r = -0.064 -- no relationship at all.  P4, P5, P6 and P7 do not follow the pattern, and three
points is not a trend.  What the data does support is narrower and still useful: on P1 and P3 the
7th's direction is better and on P2 it is worse, and the 8th's is the reverse.

## Why that is an argument for the portfolio rather than for either entry

A default has to be right in advance.  A minimum over four worker processes does not: half can
construct in the 7th's direction (order=lst, w3mul=0.5) and half in the current one, and the min
keeps whichever the instance prefers.

The slot cost is zero.  The beam aim and m splits both index by `wid % 2`, so they are correlated
rather than crossed -- four workers hold two configurations, two workers each.  Hanging the
direction on the same parity does not create a third configuration; it moves the two that exist
further apart, and the pair-at-each-end guarantee that this project has already measured as
load-bearing is untouched.

resfrac stays out.  It is decided once in `algorithm()` and cannot be split per worker, and halving
the beam's budget on every instance is the part of the 7th with no upside anywhere.

`OGC_DIRSET=1` is that split, and harness/dirset.sh prices it.
