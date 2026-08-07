# The axis portfolio is smaller and more redundant than it looks

    #   Bmul  K  pos_lam  order       fut_beta  w3mul  cohort
    0   1.0   4  0.10     defer_big   1.0       1.0    0.0
    1   1.0   4  0.12     defer_big   1.0       3.0    0.3
    2   0.7   5  0.15     lst         0.0       3.0    0.3
    3   0.7   5  0.05     edd         1.5       1.0    0.3
    4   1.4   3  0.10     big_first   0.5       6.0    0.3
    5   0.5   6  0.20     defer_big   0.0       1.5    0.0

Axes 0 and 1 share Bmul, K, order and fut_beta and differ by pos_lam 0.10 vs 0.12 -- a 20% change
in one position weight.  Three of the six (0, 1, 5) run defer_big.

## Two of the six can never open a run

_worker builds its rotation as

    axes = [_AXES[(wid + i) % len(_AXES)] for i in range(len(_AXES))]

so worker wid opens on _AXES[wid % 6].  With nw = 4 and OGC_ROUNDS = 1 the live wids are 0..3, so
axes 4 and 5 are never any worker's first axis.  big_first -- the only size viewpoint in the list
-- never opens.

That matters because of what the loop's own comment records: traced on the real hidden P6 at 300 s,
"the first beam produced the best solution of the entire run in 33 seconds and the other 267 went
on first probes that never beat it."  The opening axis largely decides the answer.

So the effective opening portfolio is four axes, of which two are near-duplicates: three distinct
viewpoints (defer_big, lst, edd) across four slots, with size and the second defer_big variant
sitting in reserve slots that rarely decide anything.

## Consequence for every axis experiment run so far

axcount, newaxis and the OGC_AXSET arms all changed the CONTENTS of the list.  Changing the list
also changes which entries land in the opening positions, so those arms confounded "is this axis
better" with "does this axis now get to open".  None of them measured the opening set directly.

## What a redesign has to fix

Fill the four opening slots with four distinct viewpoints rather than three plus a variant:

    slack     lst          present, opens as worker 2
    deadline  edd          present, opens as worker 3
    size      big_first    present but never opens
    blend     defer_big    holds three slots

rank and sac3 have never been in the portfolio at all and are candidates for the fourth slot.
