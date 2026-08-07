# Where the objective actually is, how much of it is provably forced, and what that implies

## The decomposition, on six stage2 instances with same-queue base solutions

    prob      w1*Z1      w2*Z2      w3*Z3      %Z1    %Z2    %Z3    proven-forced w1*Z1
    P1       113,339    21,219    367,200    22.6%   4.2%  73.2%          0
    P4     1,213,212     6,180  1,395,927    46.4%   0.2%  53.4%          0
    P16    2,426,606     6,423  1,179,500    67.2%   0.2%  32.7%          0
    P24    1,763,157    17,206    999,600    63.4%   0.6%  36.0%          0
    P6     4,453,222    15,740    749,455    85.3%   0.3%  14.4%          0
    P20    7,713,719    14,712  1,306,200    85.4%   0.2%  14.5%          0

Each row reconstructs the reported objective exactly, so the split is the real one.

## w2*Z2 is 0.2-4.2% of the score

The load-balance term is worth a fifth of a percent on five of six instances.  It is threaded
through the search anyway -- `dobj2_of`, the `loads` argument carried down into
`best_cell_contact_tl`, the w2 term in the state rank.  That is search complexity and runtime spent
on 0.2% of the objective.

## Nothing in the tardiness is provably unavoidable

Two valid lower bounds, both computed:

  - PER BLOCK: a block cannot start before its release, so its tardiness is at least
    max(0, release + processing - due).  Summed over blocks this is **0 on all 40 instances** --
    no block is forced late by its own window.

  - ENERGETIC: for any deadline d, blocks with due <= d need D(d) = sum(area*processing) of
    area-time, and the yard can supply at most capacity*(d - min_release) before d.  Any excess
    must run after d, so some block with due <= d finishes at least (D-S)/capacity late, and total
    tardiness is at least that.  **Nonzero on 4 of 40 instances**, and small where it fires
    (prob_2 w1*Z1_lb = 64,946; prob_13 270,014; prob_25 154,990; prob_36 276,824).

So on prob_20, 85.4% of the score is tardiness and none of it can be shown to be necessary.  The
bounds are weak -- they ignore geometry, bays, crane rules and integrality -- so this is not proof
of headroom.  It is the absence of any evidence that the largest term in the score is near its
floor, which after six submissions is the more useful fact.

## The structural mismatch

The objective reads only (bay, entry_time).  Geometry is a feasibility constraint and contributes
nothing to the score.  The beam ranks states by CONTACT -- a packing-density surrogate.

And most instances are loose.  Peak concurrent area over total bay area, under an earliest-start
profile: median 76.9% for the 12-orientation instances, 119.3% for the 8-orientation ones, with
prob_1 at 59.3%.  Where the yard is not full, packing density is not what the score pays for; the
problem reduces to choosing a bay and a time per block to minimise w1*tardiness + w3*preference
subject to capacity.

That is a scheduling and assignment problem being solved with a packing heuristic.

The axis table is the symptom.  On prob_16 at identical work, the six axes return 2,477,998 to
9,543,435 -- a factor of 3.8 from changing the ranking's parameters.  A surrogate closely aligned
with the objective does not move the answer by 3.8x when its coefficients are nudged.

## What follows

1.  **Compute a real lower bound per instance.**  Right now nobody knows whether prob_20's
    9,034,631 is 3% or 60% above optimal, and that is why a whole day can go into 2% effects.  The
    relaxation is natural: drop exact geometry, keep per-bay area capacity over time, and solve
    block -> (bay, entry_time) for w1*tardiness + w3*preference with CP-SAT.  ortools is already a
    dependency and `_assign` already uses it.  Cost: no algorithm change, so a failed attempt loses
    nothing but time.

2.  **If the relaxation solves, make it the constructor on loose instances**, with geometry repair
    afterwards and the present beam as the fallback where repair fails.  It would attack the 85%
    of the objective that the contact surrogate only reaches indirectly.

3.  **Consider removing w2 from the search.**  0.2% of the objective, non-zero cost in the ranking.

## The honest frame

Six submissions span 73.0M-74.0M, a 1.4% band, and the identical-code pair accounts for 1.33% of
it.  Every parameter-level change measured this session came in at 1-3%, which the submission noise
floor (+-5-8% per instance) cannot see.  Getting 10% out of this needs a structural change, and
before choosing one it is worth knowing which instances have room -- which is what the bound is
for.
