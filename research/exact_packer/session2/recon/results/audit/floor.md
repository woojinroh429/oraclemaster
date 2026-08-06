# The answer is at a floor, and every experiment today moved budget around above it

## What was measured

`rr240`, prob_20, 240 s, the shipped build with OGC_ROUNDS at 1 / 2 / 4:

| arm | per-worker budget | draws | objective |
|---|---|---|---|
| R=1 | ~200 s | 4 | 9,144,888 |
| R=2 | ~99 s | 4 (see the bug below) | 9,144,888 |
| R=4 | ~49 s | 12 | 9,162,795 (+0.20%) |

R=4 really did run three rounds.  Their minima, in order: **9,162,795 -> 9,224,456 -> 9,249,368**.
Tripling the draws made the answer very slightly worse, and each extra round was worse than the
one before it.

## Why the min-of-N argument was wrong

The argument assumed worker outcomes are one distribution with sigma ~ 7.8%, from which
E[min] improves by 0.74 sigma going from 4 draws to 16.  The actual per-round worker values:

    10,955,033   9,758,938  10,958,788   9,159,932     spread 19.6%
     9,696,200   9,159,932  11,529,110   9,647,965     spread 25.9%
    11,242,114   9,213,031  11,981,032   9,162,795     spread 30.8%
    11,363,037   9,224,456  11,209,407   9,270,437     spread 23.2%
    13,133,255   9,249,368  11,635,273   9,315,197     spread 42.0%

They are **bimodal**.  The good workers land in 9.16-9.32M, tightly; the bad ones scatter over
10.9-13.1M.  The 19-42% "spread" is the distance between the two modes, not the width of one.

So the minimum is already sitting on the lower mode, and the lower mode has a floor near
9.15M that more draws do not get under.  Twelve draws never beat four.

## What this explains

Every mechanism tried today changed how the budget is DIVIDED: rounds, in-place redraw of a
lagging worker, the two-phase aim race, axis sets and counts, dispatch orders, multi-bay
repacking, the feasibility ridge.  All of them reach the same floor, which is why all of them
returned noise.  It is the quantitative form of a conclusion this project reached qualitatively
long ago -- the neighbourhood is exhausted.

The one change that ever clearly won, beam salvage, was not a reallocation: it made solutions
reachable that had been thrown away.  That is the shape a real improvement has here.

## The bug that has to be fixed either way

    for _r in range(_R):
        if _r > 0 and (timelimit - (time.time() - t0)) < (_rb + reserve):
            break

`_rb` is `wbudget / _R`, so after the last affordable round the check demands a full round plus
the polish reserve and always fails.  R=2 on prob_20 ran ONE round and threw away 87 s (153 s of
a 240 s limit).  R=4 ran three of four.  The round is skipped entirely rather than run with
whatever is left, and `best` spans rounds so a short round could never lose.

This also puts the measurement that retired OGC_ROUNDS in doubt: it was run at a 60 s limit where
`wbudget ~ 47`, `_rb ~ 23`, `reserve ~ 12`, so the second round was unaffordable by the same
arithmetic.  **Rounds have never been measured actually running more than one round at R=2.**
