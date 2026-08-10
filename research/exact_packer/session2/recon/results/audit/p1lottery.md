# WHY THE HIDDEN P1 IS STILL AT 3.05M, AND WHAT ACTUALLY CONTROLS IT

    entry     P1          P3
    7th       2,685,759   5,569,691
    8th       3,009,531   5,972,740
    10th      3,185,928   5,886,815
    11th (D)  3,051,204   5,581,976

D moved P1 -4.23% against the 10th and P3 -5.18%, and P3 is now within 0.22% of the 7th's best.
P1 is still 13.6% above the 7th's 2,685,759, and the four entries span 18.6% with no monotone
relationship to anything shipped between them.

## THAT BAND IS NOT A CODE QUALITY DIFFERENCE.  IT IS THE DRAW.

Twenty-four round-0 worker draws on training prob_1, pooled over the brkcal queue:

    min 422,629   p25 489,878   median 571,400   p75 722,186   max 866,567
    P(one worker draw <= 450,000) = 0.25          P(<= 500,000) = 0.46

The answer is the MINIMUM over the draws.  So:

    4 draws   P(some draw <= 450,000) = 1 - 0.75^4 = 68%
    8 draws                            = 1 - 0.75^8 = 90%

The median is worth nothing here and the count is worth everything.  This is the same fact from
three directions, and only now stated as a number:

  - brk lifts prob_1's median worker 4.7% and leaves the minimum at 422,629 in BOTH arms;
  - the tail cut worked by adding a second round, i.e. by adding draws, and its measured effect
    was on the run-to-run RANGE (19.4% -> 8.0%) rather than on the mean;
  - twelve branches that moved seconds between round 0, a second round, the polish and the probe
    all closed as trades, because moving seconds between phases does not change the ticket count.

The 7th's 2,685,759 was a good ticket.  Nothing shipped since has been worse; the entries have
been resampling an 18.6% band.

## THE LEVER THAT HAS NEVER BEEN SWEPT

OGC_ROUNDS cuts the budget into R worker rounds, so R*4 draws each about 1/R as long.  It exists
in the code and has only ever been used at 2, in an unrelated determinism check.  Shorter draws
are worse -- fillpower measured 486,096 from a 99 s round 0 against 438,791 from a 199 s one -- so
this is a genuine trade, and 240 s could be on either side of it.

harness/p1draws.sh sweeps R = 1,2,3,4 on prob_1 with four replicates and reads the DRAW
DISTRIBUTION out of WSTAT rather than the run objective.  R=4 yields 16 samples per run, so four
replicates give 64 draws where the entire brkcal queue produced 24.  The decision quantity is
P(min over a run's draws <= T), computed from the pooled distribution.

prob_16 is the veto and runs first: its best worker reaches 2,671,848 with a 199 s round and only
2,879,376 with 155 s, so four short rounds should hurt it badly.  If it does not, that finding was
a draw too.

## WHAT WOULD REFUSE THE WHOLE IDEA

If the draw distribution degrades faster than the count grows -- if R=4's p25 is worse than R=1's
median -- long rounds are right, P1's band is not reachable by scheduling, and the only remaining
lever is the beam's own left tail rather than how the budget is cut.
