# brk's GAIN TRACKS THE Z3 SHARE, WHICH IS THE FIRST NON-CIRCULAR PREDICTOR THIS SESSION FOUND

    instance   Z3 share   brk delta   replicates
    prob_3        89.4%      +0.34%   3
    prob_1        86.3%      -6.52%   3 (worst-case -11.2%; spread 16.5% -> 2.0%)
    prob_16       48.7%      -2.51%   1
    prob_24       23.2%      +1.84%   1
    prob_20       15.1%      +3.97%   1

Monotone in Z3 share apart from prob_3, and the crossover sits between 23% and 49%.

## Why it has to be this way

brk lifts a whole bay and repacks it exactly, and what a repack buys is PREFERENCE: blocks that
could not enter a bay because its descent columns were fragmented get seats.  On an instance
carrying 15% of its objective in Z3 there is nothing there to collect, and the 34-36 s the
operator takes comes straight out of the beam, which OGC_OPSTAT prices at 8.1M objective units
per second against the next operator's 17.5K.

prob_20 shows it directly: Z3 went UP, 9,293 to 9,694, while the objective rose 3.97%.

## prob_3 is not an exception, it is the same effect at small amplitude

Its controls span 4,304,599 - 4,363,763 and its brk cells return 4,356,312 three times, to the
digit.  brk beats the WORST control and loses to the best -- exactly prob_1's profile, where
controls span 422,629 - 492,458 and brk returns 428,809 / 437,484 / 437,484.  The operator
collapses the distribution onto a point near the middle.  Where the distribution is wide and the
Z3 term is large (prob_1) that point sits well below the mean; where it is narrow (prob_3) it
sits on top of it.

## Why this predictor is usable where four others were not

  _demand_ratio_phys   r = -0.607 against the outcome, with outliers in both directions
  hz1_est on empty     identically 0 on all thirteen instances -- nothing is placed, so the
                       whole yard is free and the estimate carries no instance information
  _safe_sequential     Z3 share 0.0% on all forty; the floor solution is 100% Z1 by construction
  a 15 s probe round   both prob_1 and prob_16 deterministic there, worker spreads overlapping
                       at 30-67% and 29-41%

Z3 share is different on three counts.  It is NOT circular -- w3 comes from the instance and the
Z-vector comes from round 0's incumbent, both known before brk would fire.  It has a mechanism
rather than a correlation: it is the share of the objective the operator is aimed at.  And it is
monotone over five instances rather than fitted to them.

## What is still open

Five points, and one of them (prob_3) sits off the line.  The crossover is bracketed only as
"between 23% and 49%".  Before this becomes a gate rather than a description, brkfast has to say
whether the cost can be removed instead: brk's 34-36 s is dominated by cranepack's O(ncol^2)
conflict build, that build is parallel in the engine and has never run that way, and
OGC_BRKTHREADS now raises OpenMP around CP.pack only.  If the build drops to ten seconds the
crossover moves down and the gate may not be needed at all.
