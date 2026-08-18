# Third submission, 2026-08-05 10:00 UTC

Build: 09:37 package -- beam salvage (the cliff fix) plus the aim portfolio. Two changes, so this
is not a controlled comparison of either.

    inst      2nd sub        3rd sub      change         rival     vs rival
    P1      3,328,237      2,847,060    -14.46%     2,768,562      +2.84%  LOSE
    P2     20,337,489     20,063,787     -1.35%    19,557,271      +2.59%  LOSE
    P3      5,867,652      5,613,271     -4.34%     6,107,141      -8.09%  win
    P4      4,283,430      4,681,440     +9.29%     5,457,719     -14.22%  win
    P5      6,104,015      6,148,480     +0.73%     6,287,901      -2.22%  win
    P6      1,053,770        968,674     -8.08%     1,017,678      -4.82%  win
    P7     16,285,457     16,310,765     +0.16%    17,749,103      -8.10%  win
    P8     16,023,014     17,347,930     +8.27%    18,145,932      -4.40%  win

    total  73,283,064 -> 73,981,407  (+0.95%)     4 better / 4 worse
    vs rival  73,981,407 vs 77,091,307  (-4.03%, was -4.94%)   6 win / 2 lose, was 5 / 3

## Why some go up and some go down

The first answer is measurement, and today we finally have the number for it. Three replicates of
one 150-block practice instance on ONE UNCHANGED BUILD at one budget returned 1,075,322, 831,362
and 923,531 -- a spread of 29.3% with nothing changed at all. A second instance's arm spread 23.0%
the same way. Earlier the same day a single paired draw read -17.37% and came back -0.9% over three
replicates.

Set that against this table: the largest move here is 14.46% and six of the eight are under 9%.
Every one of them is inside the band the algorithm produces against itself. These eight numbers
cannot separate "the change helped" from "the dice fell differently", and no amount of staring at
them will.

The second answer is that a change does not merely make the search better or worse, it makes it
take a different path. The report's Section 2.3 result is this exact effect measured deliberately:
an optimisation that was proved exact and returned bit-identical placements at fixed work made one
instance 7.7% worse, because the operator schedule is driven by elapsed seconds, so a faster or
differently-timed search fits a different sequence of calls into the same budget, hands the
repacking operator a different incumbent, and reaches a different local optimum. The cliff fix
changes what the beam returns when it overruns; the portfolio changes what half the workers search.
Both reshuffle the trajectory on every instance, including the ones where neither was needed.

The third is sample size. Eight instances, 4-4, is not evidence in either direction. The paired
practice validation behind the aim portfolio is 37 instances, 31-6, sign test p < 0.0001 -- that is
the estimate to trust, and it predicts a median gain of a few percent, which is smaller than the
per-instance noise here and therefore invisible in a table of eight.

## The pattern I flagged last time reversed

After the second submission I wrote: "P1, P2 and P6 are the three we already lost, and all three
got worse; the five we already won all improved." This time the three we lost -- P1, P2, P6 -- all
improved, P6 by enough to flip it to a win, and three of the five we won got worse. The pattern
inverted completely on the next draw, which is the strongest evidence available that it was never a
pattern. I should not have offered it as a lead.

## What did move

Against the rival the standing went from 5-3 to 6-2, and P1 closed from 20.22% behind to 2.84%
behind. If anything in this table is signal rather than noise it is P1, since 14.46% is at the edge
of the measured band rather than inside it -- but one draw cannot establish that either, and the
honest statement is that we do not know which of the two shipped changes, if either, produced it.

## What this says to do next

Not to tune on these eight numbers. The per-instance spread is the largest single risk to a
per-instance score -- larger than any few-percent improvement we have measured -- so the thing worth
attacking is the variance itself. harness/wstat.sh measures where it comes from: the answer is a
minimum over four workers, so its stability is set by how those four are distributed, and that is
observable in two runs per instance instead of the ten that replicating the answer would need.
