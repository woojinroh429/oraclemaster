# Three independent experiments, one mechanism: the spread IS the value

The answer is `min` over four workers.  Anything that makes those four converge removes draws from
the minimum, and this session measured it three separate ways without looking for it.

    experiment      manipulation        worker spread        minimum
    w3grid P4       w3mul raised        24.3 -> 12.6%        monotonically worse (0.00%, +5.69%)
    nobrk  P13      brk removed         11.9 -> 17.6%        BETTER (-0.84%)
    headroom P20    budget 240 -> 1200s 19.4 -> 10.1%        worse (+4.23%)

Every row agrees: spread up, minimum down; spread down, minimum up.  None of these was designed to
test it -- w3grid was testing a weight grid, nobrk an operator, headroom a budget.

## Why more budget narrows the spread

Give each worker longer and it descends further into its own basin.  The basins bottom out on a
small set of shared attractors (results/audit/attractors.md, now confirmed on the hidden set:
submissions 3 and 5 returned 968,674 on hidden P6 to the digit across four code changes).  So a
longer run does not produce four better draws -- it produces four draws that have converged onto
the same few floors, and a minimum over four copies of one answer is one draw.

The headroom row is the sharpest form of it: at 1200 s prob_20 returned 9,848,620, which is worse
than EVERY 240 s draw on record (8,854,193 .. 9,449,113).  Five times the budget bought a result
outside the short-budget range on the wrong side.

## What this rules out, and what it does not

Rules out: spending the remaining time on budget policy.  Every reallocation this session lost
(ROUNDS, redraw, the aim race's second phase), and this explains all of them at once -- they were
different ways of moving budget between workers or rounds, and none of them changed which
attractors were reachable.

Does NOT rule out: that the spread can be widened by construction.  nobrk is the one row where the
spread went UP and the minimum improved, and it did so by removing an operator that was pulling two
workers onto the same value.  That is the shape of a lever: not more time, not different weights,
but whatever stops the four searches from collapsing into each other.

## The number that matters

A rival reports 2.40M on hidden prob_1 against our best-of-five 2,847,060 -- 18.6%.  The combined
range of every lever measured today is about 2%.  Widening the spread is worth something, but on
this evidence it is worth single digits at best, and the gap is a different kind of solution rather
than a better-tuned version of ours.
