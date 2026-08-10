# WHY THREE WORKERS, ANSWERED IN THE DRAW-DISTRIBUTION LANGUAGE

The worker count was shipped on run objectives: 37 pairs on stage-2 prob_1 and prob_16, worst draw
better in 6 of 6 cells at 60-240 s.  p1lottery.md frames the same machine differently -- the answer
is a MINIMUM over worker draws, so the count of draws is what converts into probability, and going
from four workers to three throws a ticket away.  Those two readings had never been put in the same
units.  Pooling every WSTAT round-0 line on prob_1 at 240 s across all logs:

    setting     runs   draws     p25         median      P(draw <= 450,000)   1-(1-p)^k

    WORKERS=4    193    772    492,458     612,635           0.137              0.45
    WORKERS=3      5     15    469,427     489,878           0.200              0.49

Each draw is about 20% better at the median, and that gain outweighs the lost ticket: 0.49 against
0.45 on the quantity that actually decides the run.  So the reason for three workers survives
being restated in the framing that was most likely to kill it.

## TWO THINGS THAT HAVE TO TRAVEL WITH THAT NUMBER

FIFTEEN DRAWS.  Against 772.  p = 0.200 is three successes out of fifteen; the interval runs
roughly 0.04 to 0.48, which covers both "much better than w4" and "worse".  The direction is
plausible, the size is not measurable yet.  Twenty runs at WORKERS=4... at WORKERS=3 would give 60
draws and settle it cheaply, since each run yields three.

AND THE 0.071 PUBLISHED AN HOUR AGO IS WITHDRAWN.  That came from the 56 draws of the axis phase,
whose runs pin OGC_AXIS and are therefore not the shipped configuration mix.  The full 240 s pool
says 0.137.  This is the third value for the same quantity:

    p1lottery.md   0.25     24 draws
    p1draws_prior  0.071    56 draws, axis-pinned -- not representative
    this file      0.137    772 draws, heterogeneous pool

772 is a large sample but it is still every arm of the night mixed together.  A clean number for
the shipped configuration alone does not exist yet, and every P(...) computed from these should be
read as accurate to about a factor of two.

## THE TWO LEVERS ARE COMPLEMENTS, NOT RIVALS

    three workers   draw quality up, one fewer ticket
    OGC_ROUNDS=2    tickets doubled, draw length halved (quality risk)
    both            6 draws of ~120 s each, from 3 workers over 2 rounds

They pay opposite costs, so the combination can beat either alone.  The rounds sweep now running
measures what a ~120 s draw is worth; that number plus the w3 per-draw distribution is enough to
predict the combination before spending a run on it.
