# WHAT THIS SESSION ESTABLISHED, AND WHY FIFTEEN ARMS PRODUCED ONE SHIPPED CHANGE

The goal was stage2/prob_1 from a median of 470,530 to the 300,000s.  It was not reached and the
useful output is the three walls that were mapped, each with a measurement behind it.

## WALL 1 -- THE REPAIR STAGE CANNOT WIN, STRUCTURALLY

Both improvement passes return their input unchanged on this instance.  Three fixes were written
and all three failed, and the counters say why:

    OGC_Z3WIDE   widen z3_reassign to every bay and 64 entry windows     no change
    OGC_RTBAY    price the clearing cost in ruin_tardy's bay choice      no change
    OGC_RTFIT    clear blocks until the tardy one fits, not a fixed K    seatings doubled, kept 1

ruin_tardy seats its pivot block in 118 of 145 rounds and 117 of those are still rejected.  The
weights force it: the pivot sheds one or two tardiness units at 6,667 each while one to five
displaced blocks re-seat no better, and any one of them slipping costs the same 6,667.  That is
ruin_tardy's own P6 shelving note generalised -- Z1 is conserved under rearrangement, and the
relevant saturation is of the pivot's release WINDOW, not of the yard, which is only 59.3% full.

## WALL 2 -- SCORING KNOBS DO NOT LEAVE THE ATTRACTOR

Across 27 runs of two sweeps, w3mul 0.5 and w3mul 4.0 -- an eight-fold change in the weight on the
term carrying 70-87% of the objective -- returned a byte-identical solution (obj 745,782, Z1 42,
Z2 739).  Another solution (674,831) was returned by edd, by lst, and by w3mul=1.0.

Every arm measured this session re-weights how the beam ranks states: worker count, round count,
axis, beam width, config slots, the direction pair, w3mul, dispatch order.  None changes what it
searches over.  When the re-weighting cannot leave the basin the answer is identical; when it can,
the difference lands inside a run-to-run spread of 13-54%.

## WALL 3 -- WIDTH IS A U AND PRODUCTION SITS NEAR ITS TOP

axis_work.md's 22% was read here as a lever production could not express.  It is not.  The work
cap IS the width control (Bcur = min(Bmax, left/(per*rem))), prob_16 needs ~28,800 expansions for
one pass at B=96, and the table's work values of 1500-12000 correspond to effective widths of
about 5 / 10 / 20 / 40.  The 22% cell is B~20; a 240 s production draw is already B~33, past the
optimum.  Narrowing is therefore implied, and that is OGC_BEAMCAP, recorded at +2.73% -- worse.

## THE METHOD FAULT, AND THE COUNT

Fifteen claims were published in this session and overturned by the next measurement.  Twelve were
the same error -- a directional reading at two or three draws against spreads of 11-54%.  Three
were worse: reading the preliminary hidden set as current and discarding correct data for an hour;
proposing a structural direction that turned out already measured from the other side; and naming
an 'area-first is bad' mechanism that aspect refuted immediately.

The pattern behind all of them is that a run objective on this instance is a minimum over four
draws and therefore ONE sample.  Reading the WSTAT draws instead gives four per run, and even that
inverted between eight and twelve draws per cell on w3mul.

## WHAT SHIPPED

`nw = cpu - 1` when `cpu >= 4` and `timelimit <= 240`; `WORKERS=4` restores the previous behaviour
byte for byte.  37 pairs on two instances at four budgets, worst draw better in 6 of 6 cells below
the gate.  Two instances is below the tech report's own convention of forty, so it is plausible
rather than established, and the 40-pair sign count at 180 s is what would settle it.

Three C++ knobs were added and left default-off: OGC_Z3WIDE, OGC_RTBAY, OGC_RTFIT.  Each closes a
hypothesis that would otherwise be retried.  The .so was not rebuilt, so the shipped zip is
unaffected.

## WHAT THE TARGET ACTUALLY REQUIRES

300,000 is 27% below the best value this project has ever recorded on stage2/prob_1 (413,954) and
36% below its median.  Walls 1-3 say it is not reachable by repairing a finished solution, by
re-weighting the beam's ranking, or by resizing its draws.  That leaves the construction itself --
a different search, not a different setting -- and saying so plainly is more useful than a
sixteenth arm.
