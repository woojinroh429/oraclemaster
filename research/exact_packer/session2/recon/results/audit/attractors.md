# The reachable answer set is a small discrete set per instance

The variance this project has been chasing all session is not a continuous spread.  Independent
configurations -- different worker ids, seeds, axis rotations, per-worker budgets, and in some
cases different arms of different experiments run hours apart -- return objectives that are equal
to the digit.  That only happens if the search is landing on the same solutions.

## Exact repeats observed

prob_16, 240 s limit:

    3,262,325   det2 r1.base.16          and r2fix r1.R1.16
    3,656,247   r2fix r1.R1.16 worker 3  and r2fix r1.R2.16 round 1 worker  (different wid, seed,
                                          axis rotation AND per-worker budget: ~200 s vs ~99 s)
    3,813,686   b240 r1.base.16 final    and r2fix r1.R2.16 round 1 worker
    3,271,186   race r1.base.16 final    and det r1.rdrw.16 final

prob_20, 240 s limit:

    9,217,158   r2fix r1.R2.20 round 0 worker  and round 1 worker
    9,552,359   race phase-2 worker            and another phase-2 worker
    9,162,795   race r1.race.20 final          and rr240 r1.R4.20 final

prob_26, 120 s: the redrawn worker 0 came back with its pre-redraw value, 4,345,449, twice.

## What follows

The seven draws of prob_16 at 240 s sort as

    3,043,376 | 3,262,325  3,262,325  3,271,186  3,281,165  3,286,759 | 3,813,686

-- five of seven inside 0.8%, with one escape 6.7% below and one 16% above.  That is an attractor
with occasional escapes, not a distribution with a standard deviation.  The min-of-N arithmetic
used earlier in the session (E[min of 12] = -1.63 sigma, so 4 -> 12 draws buys 4.7%) assumed iid
Gaussian draws and is therefore void: extra draws re-hit the attractor rather than sampling a tail.

This is why every reallocation experiment came back as noise.  OGC_ROUNDS, the relative redraw,
the two-phase aim race, the axis sets, multi-bay repacking and the feasibility ridge all move
budget around inside a search whose reachable set they do not change.

The one change that ever clearly won -- beam salvage -- did change it: completing a partial beam
by rollout made solutions reachable that were previously discarded outright.

So the next experiment has to widen the reachable set, not redistribute the budget.  The escape
below the attractor (prob_16 at 3,043,376, 6.7% under) is direct evidence that better solutions
sit within reach of the current search and are almost always missed.
