# Second submission, 2026-08-04 05:18 UTC

    inst      previous       this run     change          rival    vs rival
    P1      3,068,862      3,328,237     +8.45%      2,768,562     +20.22%  LOSE
    P2     19,829,534     20,337,489     +2.56%     19,557,271      +3.99%  LOSE
    P3      5,886,589      5,867,652     -0.32%      6,107,141      -3.92%  win
    P4      4,421,375      4,283,430     -3.12%      5,457,719     -21.52%  win
    P5      6,308,099      6,104,015     -3.24%      6,287,901      -2.92%  win
    P6      1,024,046      1,053,770     +2.90%      1,017,678      +3.55%  LOSE
    P7     16,385,030     16,285,457     -0.61%     17,749,103      -8.25%  win
    P8     17,079,881     16,023,014     -6.19%     18,145,932     -11.70%  win

    total  74,003,416 -> 73,283,064  (-0.97%)      5 better / 3 worse
    vs rival  73,283,064 vs 77,091,307  (-4.94%, was -4.0%)

## What this does and does not establish

It is NOT a controlled comparison.  Two changes shipped together -- per-seat pricing and the
parallel conflict-graph build -- and the second alters how much search happens inside the same
wall clock, which moves answers on its own.  Nothing here attributes P1's regression to either.

The claim that per-seat pricing gains 6.30% on P1 came from PRACTICE prob_1 and was quoted in the
report as the largest single gain.  Hidden P1 is a different instance and went the other way, by
8.45%.  Practice results were never evidence about hidden instances and should not have been
phrased as if they were.

## The pattern worth chasing

P1, P2 and P6 are the three we already lost, and all three got worse; the five we already won all
improved.  The same shape appears in the practice sweep: of the instances where per-seat pricing
lost -- P38 +9.09%, P14 +5.54%, P20 +2.90%, P19 +2.37%, P29 +2.04%, P36 +0.92% -- every one has
Z3 moving the WRONG way, while the winners mostly have Z3 falling.  Whatever separates those two
groups is the next thing to find, and it is the only lead that both data sets agree on.
