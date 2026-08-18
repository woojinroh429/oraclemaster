# 76.8% OF prob_1's OBJECTIVE IS A PREFERENCE PENALTY THAT CAPACITY DOES NOT REQUIRE

    prob_1   150 blocks, 3 bays, w1=6667 w2=3 w3=600
    bay_preferences are per-block scores over the three bays, e.g. [1, 28, 71]
    Z3 = sum over blocks of (max preference - preference of the bay it got)

## The relaxation says zero

Give every block its single most preferred bay and count area x processing against bay area x
horizon:

    bay 0   demand  39,391   capacity 139,503   utilisation 0.28
    bay 1   demand  34,043   capacity  53,728   utilisation 0.63
    bay 2   demand  36,896   capacity  45,917   utilisation 0.80

No bay is over capacity, so the aggregate relaxation admits Z3 = 0.  What actually binds is time
windows and 2D geometry, not room.

## What that is worth

    best known      422,629 = 6667*7  + 3*3720 + 600*608
    best known Z3   437,484 = 6667*15 + 3*4293 + 600*541
    both at once            ~382,000     -9.5%
    Z3 halved              ~260,000     -38%

600 * 541 = 324,600, which is 76.8% of the best objective this project has recorded on the
instance.  The median cost of moving a block off its first choice is 41 preference units, so 541 is
about thirteen blocks displaced.

## The operator that should be collecting this

`_assign` (myalgorithm.py:2193) pins every entry time, hands all 150 bay decisions to CP-SAT at
once, and tightens the bounding-box capacity row by Benders feedback when a realisation has to
spill.  Times pinned means Z1 cannot move, so anything it finds is pure Z3 and Z2.  It is exactly
the right tool for a Z3-dominated instance and nothing has ever measured what budget it receives or
what it returns.

Two solutions bracket the frontier -- Z1=7/Z3=608 and Z1=15/Z3=541 -- which says the search is
trading the two rather than collecting both, and `_assign` starting from the Z1=7 solution should
not have to trade at all.

## Next

OGC_OPSTAT=1 and OGC_BEAMSTAT=1 on prob_1: seconds given to `bay`, gain returned, and where it
stops.  Then, if it is starved, price giving it more; if it runs and returns nothing, the binding
constraint is geometric and the question becomes which blocks it cannot move and why.

## THE ANSWER: THE BOUND IS AN AREA RELAXATION AND 2D PACKING DOES NOT ALLOW IT

`_regroup` (myalgorithm.py) was built to collect it and the measurement closes the direction.

Take a real prob_1 incumbent, ask CP-SAT for a bay plan at capf = 1.00 (the exact per-time-slice
area capacity, no over-subscription), empty EVERY block the plan wants to move so the interlock is
gone, then re-place each one in its wanted bay at its own pinned entry time:

    capf 1.00   plan moves 15   realised  1   obj 691,480 against a base of 683,809
    capf 1.15   plan moves 18   realised  2   INFEASIBLE
    capf 1.30   plan moves 15   realised  0   identical to base

One to two of fifteen.  The blocks are not blocked by each other -- this routine removed all of
them first -- they are blocked by the blocks that are NOT moving.  Time-slice area feasibility is
a necessary condition and nowhere near a sufficient one, so the Z3 = 387 the plan promises is a
relaxation bound, not a reachable solution.  Reassignment alone cannot collect it; the packing
itself would have to be rebuilt, which is what the beam already does.

TWO ENGINE FACTS FOUND ON THE WAY, both worth keeping.

  - `find_best_placement` misses placements that provably exist.  Remove a block and ask it to put
    that same block back in the same bay at the same time: found=False on 2 of 12 sampled prob_1
    blocks whose own slot `placement_feasible` confirms is free.  GRIDDIV 4 -> 16 -> 64 does not
    change the count, so it is the candidate set and not the grid resolution.  `feasible_scan` with
    step=1 finds the single legal position in those cases.

  - `feasible_scan` is a static-overlap test and does not model the entry/exit path, so a solution
    assembled purely from its positions can come back infeasible -- the capf 1.15 row above.
    `_total` returns inf for that and the caller rejects it, so nothing unsafe ships, but the scan
    cannot be used as a placement oracle on its own.

`_regroup` stays in the file, unwired and unreferenced, because the measurement is the point: the
largest single term in the objective on the Z3-dominated instances is not sitting behind a missing
operator.
