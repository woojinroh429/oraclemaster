# Where the variance lives: the four workers, measured directly

`OGC_WSTAT=1` prints each worker's objective before the minimum is taken. Eight instances, both
arms, 180 s. Workers 0 and 2 run aim 0.90, workers 1 and 3 run 0.10, and the answer is the minimum
of the four.

    inst  blk  mix vs ctl  ctl spread  mix spread     best HIGH     best LOW  winner   gap
    P7    150       +3.2%      217.6%      49.5%       953,242    1,316,192  HIGH   38.1%
    P22   150       +3.2%       26.9%      99.5%         4,929        5,875  HIGH   19.2%
    P1    150       -2.0%       81.0%      58.8%       552,772      774,104  HIGH   40.0%
    P5    150       -5.6%        7.3%      14.4%     8,294,075    7,688,772  LOW     7.9%
    P20   250      -16.0%       11.4%      26.4%    10,682,209    9,212,489  LOW    16.0%
    P25   300      -15.5%        2.2%      20.6%    82,766,802   70,194,618  LOW    17.9%
    P13   300      -12.8%       13.0%      21.5%    80,056,743   66,421,226  LOW    20.5%
    P36   300      -11.2%        8.6%      16.6%    86,391,001   76,712,212  LOW    12.6%

Six better, two worse, which is the same picture the 37-instance paired run gave at 31-6.

## Half the machine is 8% to 40% behind on every instance

The two halves of the portfolio do not split the work; one half produces the answer and the other
trails it by 7.9% to 40.0%. Inside the winning pair the two workers land within 1.4-6.4% of each
other, so the answer is effectively a best-of-two, not a best-of-four. Two of four cores are
searching in the regime that cannot win on that instance.

## Which half wins is not block count

This is the part that matters, and it corrects what I said from the first four runs. P5 is 150
blocks and the low aim wins there; P7, P22 and P1 are also 150 blocks and the high aim wins. The
separator is visible in results/audit/instances.md: P5 is the only 150-block instance here with
layered blocks, 64% of them at three or more layers, while P7, P22 and P1 are flat.

Layers make the crane-descent test expensive, so a layered 150-block instance gives the beam as
much work as a flat 300-block one. The low aim helps exactly when the beam cannot finish inside
its slice, and what decides that is total work -- blocks times layers times orientations -- not the
block count. A gate on instance size would have put P5 on the wrong side.

## What this points at

The beam already knows whether it finished or had to be salvaged; that is the signal, and it is
the worker's own behaviour rather than a property of the instance. A worker that overran should
lower its aim and one that finished comfortably should raise it, so the four converge on the
regime the instance actually needs instead of two of them being wrong by construction. The upper
bound from the earlier sweep is roughly 1.7% on the large instances (P25 reached 68.97M at a
constant 0.10 against 70.19M for the portfolio) plus the removal of the 3.2% losses on P7 and P22.

The C++ change is small: AIM is a function-local static read from the environment once, so it
becomes an Engine member with a setter, plus a flag reporting whether the salvage fired.

## The adaptive-aim attempt, and a retraction

I built the machinery -- the aim is an Engine member with a setter, and the beam reports back
whether it was salvaged, what fraction of its slice it spent, what fraction of its levels it
reached and whether it finished at full width -- then tried three rules on it and reported all
three as falsified. One of those falsifications was wrong and I withdraw it.

What holds:

    used_frac saturates by construction.  ADAPTB widens the beam until it fills whatever the aim
    allows, so a beam that finishes always reports spending almost exactly its aim.
    salvaged works in one direction only.  prob_7 at 0.90 salvages 0 of 6, but from 0.10 it
    salvages 6 of 6, so a worker that starts low is pinned at the floor by its own signal.

What does not hold: I claimed level_frac points the wrong way, comparing prob_25 at 0.90 against
prob_7 at 0.10. Those were different budgets and the comparison was not fair. Measured properly:

    prob_25  60s 1w   aim 0.90  84,317,000  level 0.84
                      aim 0.60  83,768,159  level 0.76
                      aim 0.10  77,495,807  level 0.37     lower aim better
    prob_7  180s 1w   aim 0.90   1,017,364  level 0.99  salvaged 3/8
                      aim 0.10     916,107  level 0.99  salvaged 11/23   lower aim better

## Why none of this can settle the question

Every controlled run above is single-worker, and every one of them prefers the low aim -- there is
no counterexample in the whole set. The only evidence that a high aim ever wins is the four-worker
measurement at the top of this file, where P7, P22 and P1 go the other way.

So the right aim is not a property of the instance alone; it depends on how large a slice each
beam call actually gets, which depends on the worker count and the budget as well. Single-worker
runs are the wrong instrument for designing a rule that has to work in the four-worker product,
and I used them as if they were.

The honest position: the fixed 0.90/0.10 portfolio is what has been validated (31 better, 6 worse
over 37 paired instances, p < 0.0001) and it is what shipped. The adaptive variant is unresolved
rather than refuted, and settling it needs per-worker telemetry from the four-worker
configuration, which is what harness/adaptaim.sh collects.
