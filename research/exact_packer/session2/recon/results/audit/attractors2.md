# HOW MUCH OF THE SEED SURVIVES THE OPERATORS

1,176 prob_1 round-0 worker results, every WSTAT line in results/audit.

    456 distinct values

    504,490   53   4.5%
    438,791   40   3.4%
    578,411   31   2.6%
    822,149   29   2.5%
    689,851   24   2.0%
    422,629   23   2.0%
    437,484   23   2.0%
    ...
    top 20 values cover 34.0% of all results
    297 values (25.3% of results) appear exactly once

Attractors are real and they are not dominant.  One value repeating 53 times out of 1,176 with 456
distinct values is far above chance, and the top twenty take a third of the mass -- but two thirds
land outside them and a quarter are singletons.  So the operators erase the seed SOMETIMES.

## WHICH IS WHAT bk67's FIRST PAIR SHOWED DIRECTLY

    base   469,427   652,268   464,757   788,492
    bk67   469,427   757,894   445,311   788,492

Two of four workers returned the same value in both arms despite the beam width changing from 96
to 67 on every axis -- and both of those values, 469,427 and 788,492, are recurring ones.  The
other two moved.  Half the pool followed the seed, half was pulled to an attractor.

## THE PATH FROM 2.6x TO A FEW PERCENT

This is the missing link between the deterministic table and the score, and it is now traceable
rather than mysterious:

    seed advantage at fixed work                     2.3x (prob_1) to 2.6x (prob_16)
    ~1/3 of workers are pulled to an attractor       that fraction keeps nothing
    the operators take 4.3% to 22.0% of what is left  (measured over nine pinned-axis cells)
    the score is the MIN over four workers            so only the best surviving worker counts

A 4% end-to-end effect is what that chain predicts, and bk67's first pair read -4.18%.  Which is
consistent, and is also under the 8% readability floor I set for this queue in advance -- so it is
an explanation looking for evidence, not evidence.
