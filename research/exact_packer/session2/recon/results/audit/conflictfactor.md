# THE O(ncol^2) CONFLICT BUILD FACTORS EXACTLY, AND THE FACTORISATION IS NOT AN APPROXIMATION

cranepack's cost is one loop: every pair of placement columns, tested for a crane conflict.  It is
calibrated at 6.4e-8 s per squared column, so ncol 11,580 costs 8.3 s and 24,318 costs 39.1 s, and
OGC_OPSTAT prices the whole brk operator at 34-36 s -- 22-23% of a worker.  Everything cheap has
already been done to it: bay-first sort with a break, entry sort with a break, flat arrays, an
AABB pre-filter, and a memo keyed on relative offset.

What has not been done is the one thing the predicate's own algebra allows.

## The predicate

    crane_conflict_rel(LA, BA, LB, BB, ox, oy, Aen, Aex, Ben, Bex):
        if !(Aen < Bex && Ben < Aex)  return false          // time co-presence
        if whole-shape AABB separated  return false          // geometry only
        for k: if layers A_k and B_k overlap  return true     // geometry only
        AoverB = (Aen >= Ben) || (Aex <= Bex)
        BoverA = (Ben >= Aen) || (Bex <= Aex)
        if AoverB: for k, j>k: if A_k overlaps B_j  return true    // geometry only
        if BoverA: for k, j>k: if B_k overlaps A_j  return true    // geometry only

Define three booleans of the GEOMETRY alone -- (blockA, orientA, blockB, orientB, dx, dy):

    R = some resting pair of layers overlaps
    U = some A_k overlaps some B_j with j > k
    V = some B_k overlaps some A_j with j > k

Then, exactly:

    conflict(A,B) = timeoverlap(A,B) AND ( R OR (AoverB AND U) OR (BoverA AND V) )

The polygon work lives entirely in R, U, V.  Time enters only through three integer comparisons.

## What that buys

Columns are generated as (block, orient, x, y) x (entry window), so every column in a group has
identical geometry and r = ncol / geom_slots columns share one (R, U, V).  Column pairs therefore
outnumber geometry pairs by r^2.

The decisive case is R = U = V = 0: that geometry pair cannot conflict at ANY entry combination.
The loop currently visits all nA x nB of its column pairs and rejects them one at a time.  Tested
once at the geometry level it is skipped in O(1), so the non-conflicting majority costs r^2 times
less to enumerate.

The other cases collapse too rather than needing a per-pair decision:

    R = 1                  every time-overlapping pair conflicts
    U = 1 and V = 1        AoverB OR BoverA is a tautology (if Aen < Ben then BoverA holds),
                           so again every time-overlapping pair conflicts
    U = 1 only             conflict = timeoverlap AND AoverB
    V = 1 only             conflict = timeoverlap AND BoverA

so each geometry pair reduces to one of five rules over its entry cross-product, and the edges can
be emitted by a merge over sorted entry lists instead of a nested scan.

## The independent second factor

Even at geometry level most pairs die on the AABB test.  A uniform grid over the bay, each column
inserted into the cells its AABB covers, replaces the all-pairs scan within a time window by a
neighbourhood query: O(G x k^2) for k columns per cell rather than O(N^2).  This multiplies with
the factorisation rather than overlapping it -- one removes entry-variant redundancy, the other
removes spatial redundancy.

## What has to be measured before any of it is written

r.  CRANEPACK_COLSTAT=1 prints `ncol`, `geom_slots` and their ratio and has never been run.  If r
is near 1 the factorisation buys nothing and the grid is the only lever; if r is 5 the enumeration
falls by up to 25x and the rework is the largest single speedup available to this operator.

The arm is in harness/brkfast.sh.  Note it is not free -- it builds a std::set over every column --
so it prices the ratio, not the runtime.
