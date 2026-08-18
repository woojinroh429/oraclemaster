# PLANNING THE ASSIGNMENT FIRST: WHAT IS SETTLED, AND WHAT THE REMAINING CELL ASKS

Instance throughout is stage2/prob_1 (finals practice), 120 s, four workers.  Read
results/audit/p1_anatomy.md first: it establishes that Z1's floor is 0, that Z2's entire range is
worth 1.28 displaced blocks, and that Z3 > 0 is forced because a first-choice assignment leaves
the two small bays at 147% and 201% of their area at the peak.

## The operator

`_cpsat_bay_plan` solves bays and schedule together under an area relaxation -- one cumulative
resource per bay, times free, minimise w1*Z1 + w3*Z3.  `algorithm()` then rewrites each block's
bay preferences as `pref[j] + toll` on the planned bay and fans out as usual.  Preference is read
by the cross-bay rank, by the beam's state rank and by the rollout, so it is the one channel that
reaches every stage of the search; the `anchor` argument is not, and ogc_fast.cpp already records
that it never binds and that making it bind lost.  The caller's instance is never mutated, so the
grader still scores the true preferences.

`OGC_CPANCH` = seconds for the solve (capped at 25% of the budget), `OGC_CPANCHW` = the toll,
`OGC_CPCAP` = capacity de-rating, `OGC_CPORD` = also dispatch in planned-start order.  All absent
by default and byte-identical when unset.

## SETTLED: the de-rating knob was measuring the solver, not the packing

`harness/planq.sh`, plan alone, no beam, the same 20 s the grid gave it:

    cap    Z1(plan)  Z3(plan)  moved-off-top   w1*Z1 + w3*Z3
    1.00       1       403       16              248,467
    0.90     278         0        0            1,853,426
    0.85      74       995       23            1,090,358
    0.80     446         0        0            2,973,482
    0.70     631         0        0            4,206,877
    0.60     940         0        0            6,266,980

`Z3 = 0` with nothing moved is the trivial solution -- everyone takes their first choice and waits.
Below capacity 1.00 CP-SAT never leaves it inside the budget.  So `OGC_CPCAP` is dead as written,
and the fix if it is ever revisited is not a different multiplier but a HINT: seed the model with
an incumbent assignment and earliest starts so it does not have to find its way out of the trivial
corner.  That is untested.

## SETTLED: two of this session's readings were wrong and are withdrawn

**"De-rating drives Z3 up."**  It does not.  `ca.c0.85.t100` realised Z3 = 1118 because the PLAN
was 995, not because the beam deviated.  And Z3 is not monotone in the de-rating at all -- 0.85
gave 1118 and 0.70 gave 493 at the same toll.

**"The beam realised the CP-SAT assignment at Z3 = 212."**  It did not.  The 0.70 plan is the
trivial one, so at that capacity the preference rewrite reduces to "+300 on your own top bay" and
CP-SAT contributed nothing.  Z3 = 212 is what a flat toll on the COUNT of displaced blocks buys,
and it cost Z1 = 254.

## SETTLED: the toll axis alone is monotonically bad

    toll     obj         Z1    Z3
       0     515,188     25    543
     100     703,795     58    493
     300   1,849,481    254    212

Between 100 and 300 the beam buys Z3 -281 (worth 168,600) for Z1 +196 (worth 1,306,732): about
eight tardiness units per preference unit.  A toll high enough to make the plan stick is high
enough to make the beam wait for a bay it should have abandoned, at 6,667 a unit.

## SETTLED: the trivial target beat the real plan on Z3

At the same toll of 100:

    CP-SAT plan (cap 1.00)      Z1 41   Z3 641
    trivial top-choice target   Z1 58   Z3 493

The plan displaces sixteen blocks up front and the beam then adds its own forced displacements on
top of them, so the two sets compound instead of substituting.  Any future version has to give the
beam the plan's displacements INSTEAD of its own, not in addition.

## OPEN: why a 248,467 plan realises as ~660,000

    plan      Z1  1   Z3 403        248,467
    realised  Z1 44   Z3 590        667,853   (toll 100, cap 1.00, order off)

The bays are nearly obeyed -- measured separately, 145 of 150 blocks sit where the plan put them.
The gap is entirely in time.  The plan reaches Z1 = 1 by making 37 blocks WAIT up to nine units
past their release; the beam never sees those times, dispatches in its axis's own order, and has
to rediscover the same seating.

`harness/cpord.sh` hands the schedule over in the only form that pins nothing -- dispatch in
planned-start order, every entry time still the beam's own choice -- paired against the identical
cell with the order off, three replicates, at tolls 100 and 300.

Its named failure mode: planned-start order is close to release order, and release-then-due
dispatch is the arm `_bayplan` accidentally shipped when it measured +34%.  If planned-start is
release order with noise, this reproduces that loss and the direction closes.

## Standing numbers for comparison

    control draws this session     489,878   515,188   (and 700-750k on unlucky draws)
    best draw ever recorded        473,456   (Z1 11, Z3 632)
    area-relaxation floor          ~239,000  at Z1 = 0, Z3 = 387
    target                         250,000-290,000
