# THE BEAM RETURNS THE SAME SOLUTION FOR SETTINGS THAT DIFFER BY 8x, WHICH EXPLAINS THIRTEEN ARMS

stage2/prob_1 at 120 s, 27 runs across the w3mul and order sweeps, 24 distinct (obj, Z1, Z2, Z3):

    obj = 674,831   Z1 17  Z3 927    x3    ord.edd.r1, ord.lst.r2, w3.1.0.r1
    obj = 745,782   Z1 42  Z3 739    x2    w3.0.5.r2, w3.4.0.r3

The second pair is the one that matters.  w3mul 0.5 and w3mul 4.0 -- an eight-fold difference in
the weight the beam puts on the term carrying 70-87% of the objective -- returned a byte-identical
solution.  The first is three settings with two different dispatch orders AND two different w3mul
values landing on one solution.

## SO THE KNOBS OFTEN DO NOT MOVE THE ANSWER AT ALL

Every arm measured in this session changes how the beam SCORES its states: worker count, round
count, axis, beam width, config slots, the direction pair, w3mul, dispatch order.  None of them
changes what the beam is searching over.  When the scoring change is not enough to leave the
basin, the run returns the same solution; when it is, the difference lands inside a run-to-run
spread of 13-46%.  That is the whole failure pattern:

    thirteen arms, twelve reversed sign on the next draw, one shipped and unverified

It is not that each knob was measured badly.  It is that re-weighting a ranking does not escape
the attractor, and the attractor is what sets the objective.

## WHAT WOULD HAVE TO CHANGE INSTEAD

axis_work.md already found the one thing that moved a draw by more than noise -- 22% on prob_16 --
and it was NOT a weight.  It was work-space: B fixed at 96 and the work per draw doubled.  The
production path cannot express that combination, because it converts time into width:

    Bcur = min(Bmax, left / (per * rem))

More seconds become a wider beam rather than a deeper one, and the file's own OGC_BEAMCAP note
measured wider draws as better on average and worse at the minimum -- "and the minimum is what
gets reported".  Decoupling width from remaining time is a structural change to the search, not a
knob on its scoring, and it is the only untested direction left that has a measured 22% behind it.
