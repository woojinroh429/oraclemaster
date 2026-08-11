# BOTH IMPROVEMENT PASSES RETURN THEIR INPUT, AND THE REASON IS THAT SINGLE-BLOCK MOVES CANNOT WORK

stage2/prob_1, weights w1=6667 w2=3 w3=600, so obj = 6667*Z1 + 3*Z2 + 600*Z3 and Z2 is 4%.

    a 60 s beam solution        obj 626,023   Z1 = 13 (86,671)   Z3 = 864 (518,400)

    _z3_improve, 60 s budget    returns the input unchanged
    _z1_improve, 10 s and 30 s  returns the input unchanged, spending the whole budget

ruin_tardy's own counters explain its half:

    rt_rounds 151    rt_kept 0    rt_nocand 0    rt_seated 1    rt_unplaceable 0    rt_worse 95

151 complete ruin-and-recreate rounds, nothing unplaceable, nothing accepted, 95 strictly worse.
The pass is not blocked; its recreate simply never beats the incumbent.

## THE MOVE GENERATOR WAS TOO NARROW, AND WIDENING IT CHANGED NOTHING

z3_reassign's acceptance test already prices the full trade -- w1*(nt-cur_tardy) + w3*(npen-cur_pen)
+ dz2 -- but three filters stopped the moves that would use it from being generated: blocks already
in their best bay were skipped, only more-preferred target bays were considered, and earlier entry
windows were scanned only when the current window did not fit.  OGC_Z3WIDE=1 (added here, default
off, byte-identical when absent) removes all three for tardy blocks.

    Z3WIDE=0   626,023
    Z3WIDE=1   626,023      every bay, 64 entry windows each, still nothing accepted

So it is not that the good moves were being filtered out.  There are no good SINGLE-BLOCK moves.

## WHICH IS WHAT _regroup ALREADY FOUND

_regroup's recorded conclusion on this instance is that the obstruction is the blocks that STAY.
A tardy block cannot enter earlier because other blocks occupy the space it would need, and no
single-block move can clear them -- the blocker has to move in the same step.  Three passes say the
same thing from three directions:

    z3_reassign   one block at a time          inert
    ruin_tardy    ruin and recreate            151 rounds, 0 kept, 95 worse
    _regroup      obstruction is what stays

## WHAT THIS MEANS FOR THE SESSION

Everything measured tonight -- worker count, round count, axis choice, beam width, config slots,
the direction pair -- changes WHICH SOLUTION THE BEAM PRODUCES.  None of them touches the fact that
the produced solution is then never improved.  The instance sits at a median of 470,530 against a
target of 278,767 that is arithmetically reachable from values already on record (Z1 = 1 and
Z3 = 441 have both been achieved, in different runs, and they are uncorrelated: r = -0.009 over
458 runs).

The next piece of work is a multi-block move: relocate a tardy block together with whatever is
blocking its earlier window.  ruin_tardy is the existing scaffold for it -- the ruin and the
acceptance test are already right, and it is the recreate that never aims at tardiness.
