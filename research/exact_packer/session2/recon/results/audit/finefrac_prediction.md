# SEALED PREDICTION — FINEFRAC 0.85, written before the remaining 28 pairs exist

Written at scan40 = 12 of 40 pairs complete.  The rule below is fixed from those 12 and is
evaluated on the 28 that have not been run.  This is the step both gates rejected yesterday
skipped: Z3-share and mean-layer-count were each read off four instances' outcomes and then judged
on those same four, so one instance changing sign destroyed them.

## The rule

    R1:  FINEFRAC 0.85 beats 0.60  <=>  the A-arm's beam salvage rate is <= 55%

Salvage rate = fraction of BEAMSTAT lines in the shipped-default run reporting salv=1, i.e. the
share of beam calls that ran out of time and finished by greedy rollout instead of completing.

## Why this and not block count

Block count was the first candidate and it is dead: n=250 averages -4.15% while n=200-249 averages
+0.38%, so the response is not monotone in n, and prob_1 (n=150, -23.24%) and prob_10 (n=150,
+7.60%) sit at the same size with opposite signs.

## Mechanism, which is why R1 is not just a correlation

FINEFRAC moves the split between two rungs of one beam call: the fine rung (step 1) gets FINEFRAC
of the slice, the coarse rung (step 2) gets the rest, and the loop returns on the first feasible
answer — so the coarse rung runs only when the fine one fails.

  * Low salvage means the fine rung usually finishes inside its slice.  Extra time then buys deeper
    search directly, and the coarse reserve it is taken from was not being spent anyway.
  * High salvage means the fine rung is already starved.  42% more slice does not make it finish,
    while cutting the reserve from 40% to 15% removes the cheaper fallback that could have.

## The fit on the 12 observed pairs

    salv <= 50%   P1 19% (-23.24), P7 23% (-2.52), P8 31% (-2.90), P12 36% (-1.68), P4 50% (-7.32)
                  5 of 5 predicted WIN, 5 of 5 actual WIN
    salv 56-99%   P3 64% (+0.63), P9 71% (+3.42), P10 71% (+7.60)
                  3 of 3 predicted LOSE, 3 of 3 actual LOSE

    8 of 8 correct on instances whose salvage rate is not 100%.

## What R1 gets wrong, stated now rather than after the fact

    salv = 100%   P2 (-5.14 WIN), P5 (-0.89), P6 (0.00), P11 (0.00)

R1 predicts LOSE for all four.  P2 wins by 5.14%, the other three are neutral.  These four are
visibly a different regime: six beam calls each against 8-26 elsewhere, and a used-fraction of
exactly 0.54 in all four.  I cannot explain them yet and am not going to invent a reason to cover
them — the sealed rule is R1 as written, including this known failure.

## How this gets judged

On the 28 unseen pairs, for each instance with salvage rate below 100%: does the sign of the
FINEFRAC 0.85 outcome match R1's prediction?

  * >= 80% sign agreement — R1 stands and becomes a candidate gate, with the caveat that a gate on
    salvage rate needs the rate measured at RUN TIME, which the engine already reports.
  * 60-80% — weak; the mechanism may be right but the threshold is not usable.
  * < 60% — R1 is rejected outright and joins the other two gates.

Nothing ships on this before the winners are re-measured with replicates; one paired draw per
instance is a sign, not a magnitude.
