# The improvement pass only ever chased Z3, and w1*Z1 is up to 85% of the objective

## The gap, from the code

`z3_reassign` is the pass that runs at the end of every solve.  Its single-block move loop opens:

    for(int b: ord){
        auto& r=recs[b]; int cur_bay=r[1]; double cur_pen=mxp[b]-prefv(b,cur_bay);
        if(cur_pen<=0) continue;                          // already in its best bay -> skipped
        ...
        for(int tb=0;tb<n_bays;tb++){
            if(prefv(b,tb)<=prefv(b,cur_bay)) continue;   // only MORE-preferred bays considered

Two consequences, both invisible from the acceptance test:

  - a block that is LATE but already sits in its most-preferred bay is never touched at all;
  - a move that gives up a little preference to remove a lot of tardiness is never generated,

even though the rule that decides whether to keep a move is `w1*dtardy + w3*dpen < 0` and would
take exactly that trade.  The pass can only walk toward preference; it cannot walk toward time.

What that costs, from the objective split measured on our own solutions:

    prob_20  85.4% w1*Z1     prob_6  85.3%     prob_16  67.2%
    prob_24  63.4%           prob_4  46.4%     prob_1   22.6%

## The pass that aims there existed and was never called

`Engine::ruin_tardy` is implemented in ogc_fast.cpp, bound into the module at `.def("ruin_tardy",
...)`, and `grep -c ruin_tardy myalgorithm.py` returns 0.  It scores the FULL objective internally
(w1*Z1 + w3*Z3, plus w2 when workloads are passed) and keeps a separate incumbent, so it cannot
return something worse than it was handed.

Its own comment records why it was shelved:

    PLATEAU WALK.  Strict improvement never fires here: measured on the real P6, 102 of
    102 completed rounds were rejected and the BEST of them came in at a relative delta
    of exactly 0.0 ... That is what a saturated yard means; throughput is fixed and Z1 is
    conserved under rearrangement.

## Measured, at the budget the hidden set gives

60 s, one cell per arm, the flag alone on top of otherwise-default settings:

    inst   w1*Z1 share      off            on          delta      Z1
    P1        22.6%      751,509       679,647      -9.56%     42 -> 3
    P6        85.3%    5,428,374     5,097,026      -6.10%    341 -> 312
    P20       85.4%    9,250,517     8,924,228      -3.53%   1177 -> 1110

Three of three, at both ends of the objective mix, on the budget that matters.

**prob_6 is the instance the shelving note was written about.**  The observation was not wrong; it
was narrow.  The pass now runs ahead of `z3_reassign` rather than alone, so it receives a different
layout than the one it was measured on -- the same structure as `w3mul`, which reads +0.5% by
itself and carries weight inside a combination.

## What is not established

  - one cell per arm; prob_1's own 60 s spread is not yet known
  - prob_4 and prob_24 have not reported
  - 120 s and 240 s have not reported, and every earlier finding in this project reversed sign
    between 240 s and 60 s
  - the two passes now split the tail half and half, and that split has never been swept

## Wiring

Both passes run in the tail, Z1 first so the Z3 pass trades against a lower tardiness baseline,
each given half of what remains, each adopted only when it strictly improves the full objective.
`OGC_Z1PASS=0` restores the single-pass tail exactly.
