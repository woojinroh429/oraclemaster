# bk67: NOT ADOPTED.  SEVEN PAIRS, MEAN +1.50%, SIGNS SPLIT ON EVERY INSTANCE.

              r1        r2        r3
    prob_1   -4.18%   -3.40%   +18.12%
    prob_16  +5.50%   -5.06%
    prob_20  -0.45%    0.00%
                                mean +1.50%

prob_20 r2 returned 8,850,352 in both arms, IDENTICAL TO THE DIGIT, after changing the beam width
and branching factor on all six axes.  The operators and the attractors absorbed the entire
change.

## WHAT WAS BET AND WHAT WAS LOST

The deterministic (axis, work) table is the cleanest measurement in this project: one answer per
cell, placement digests, three values reproduced exactly from an earlier session on a different
build.  It says Bmul 0.7 / K 5 is worth 2.3x on prob_1 and 2.6x on prob_16, at every work level,
across two objective families.  bk67 moved production onto that setting while keeping all six
orders and weights, so the portfolio stayed intact.

The score did not move in any readable way.

## THE READING IS STILL NOT DETERMINED, AND THAT IS THE POINT OF WHAT RUNS NEXT

Two explanations remain open and this experiment does not separate them:

    (a) 0.7/5 improves production's seed and the score is insensitive to seed quality
    (b) 0.7/5 does not improve production's seed at all, so bk67 never tested (a)

(b) is live because the deterministic table measures `_contact_beam` at step 1 -- the FINE RUNG
ALONE -- while production runs `_beam_once`, two rungs with a reserve and an order redraw.  And
OGC_DRAWSTAT was not set on this queue, so there is no record of what bk67 did to production's
constructions.

harness/bprod.sh runs `_beam_once` itself under OGC_WORKCAP.  Its FIRST cell repeats one
configuration three times and prints three placement digests:

    digests match     the production seed generator is measurable without noise, the axis ranking
                      below it is valid, and (a) vs (b) gets decided
    digests differ    `_beam_once` cannot be measured deterministically, every axis conclusion
                      reached tonight was never a statement about production, and this project's
                      axis comparisons have to go back to replicated A/B

The second outcome would be worth more than the ranking it denies, because it would explain the
pattern the whole night has had: clean measurements that do not transfer.
