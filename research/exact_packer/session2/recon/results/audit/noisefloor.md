# WHICH OF TONIGHT'S VERDICTS SURVIVE THE INSTANCE'S OWN SPREAD

prob_16 returned 3,095,477 and 2,850,396 on the IDENTICAL arm two replicates apart -- 8.6%.  That
is the yardstick every prob_16 verdict has to clear, and it was not available when most of them
were taken.

    verdict                              size     replicates   clears 8.6%?
    ROUNDS=2 costs prob_16              +26.4%    2, identical  yes
    variant B (RESFRAC) costs prob_16   +10.69%   2             barely, direction consistent
    dropping `bay` costs prob_16        +16.2%    1             outside, but a single cell
    rfsplit r1's monotone run             9.4%    1 each         NO -- retracted
    prob_3 wants `bay`                   +2.79%   1              no yardstick measured

prob_1's own floor is different in kind: its objective lands on a small set of discrete values --
422,629 / 437,484 / 437,697 / 438,791 / 472,330 / 492,458 / 504,490 -- so a single cell says which
basin was reached, not how good the arm is.  Four replicates is the minimum that separates them,
which is why the tailcut queue used four.

## Verdicts that do not depend on replicates at all

These rest on mechanism or on code, and repeating them cannot change the answer:

  - The Z3 prize is unreachable.  CP-SAT at exact per-slice area capacity plans 15-19 moves and
    `_regroup` realises 1-2 of them after emptying every mover first, so the blockers are the
    blocks that stay.  Area feasibility is necessary, not sufficient.
  - `_realise` takes no time budget, so `_assign` overruns any slot it is given: 26.2s even with
    the opening slice cut to 5s.
  - `pairw`'s per-worker win count tracks the median worker while the score is the minimum over
    workers, so it is biased for this objective in a known direction.
  - THRUHZ=1.0 is algebraically the THRUBEAM=0 ranking, and prob_1's winning workers run m=1,
    where all children at a level place the same block, so the term barely reorders them.

## What to re-run before trusting it

`bay` removal.  It was rejected on prob_16 from one cell at +16.2% against an 8.6% floor, and it is
the only rejected item worth 12.8% of every worker on prob_1.
