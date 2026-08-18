# Fifth submission: brk removed, and the hidden set says the same thing the training set did

    inst           1차          2차          3차          4차          5차        5v4      5v3
    P1        3068862     3328237     2847060     2875074     3062061     +6.50%   +7.55%
    P2       19829534    20337489    20063787    20164596    19944390     -1.09%   -0.60%
    P3        5886589     5867652     5613271     5856298     5781273     -1.28%   +2.99%
    P4        4421375     4283430     4681440     4439801     4428834     -0.25%   -5.40%
    P5        6308099     6104015     6148480     6109330     6187757     +1.28%   +0.64%
    P6        1024046     1053770      968674     1052516      968674     -7.97%   +0.00%
    P7       16385030    16285457    16310765    15807529    16344347     +3.40%   +0.21%
    P8       17079881    16023014    17347930    16695656    16592165     -0.62%   -4.36%

    total    74003416    73283064    73981407    73000800    73309501     +0.42%   -0.91%

5 vs 4: better 5 / worse 3, median -0.43%, range -7.97% .. +6.50%.

## Against the noise floor, this is nothing -- and that is the useful result

The third and fourth submissions were the SAME ALGORITHM (verified by hash: zero non-comment
differences in ogc_fast.cpp, one word inside a docstring in myalgorithm.py).  Their per-instance
moves are the measured noise floor of a submission:

    3 -> 4  (identical code)   median -0.07%   range -5.16% .. +8.66%   total -1.33%
    4 -> 5  (brk removed)      median -0.43%   range -7.97% .. +6.50%   total +0.42%

The brk-removal row is INSIDE the identical-code row on every statistic, and its per-instance
range is narrower.  Removing the most expensive operator in the roster -- an 8.0 s floor against
0.5-3.0 for the others -- is not distinguishable from re-running the same build.

## Which is exactly what the training set predicted

    stage2, 6 paired instances at 240 s, exchange rate 6.3x to 100.2x:
        median +0.00%   mean +0.18%   2 better / 2 worse / 2 tie   worst +2.21%

Training said neutral; the hidden set says neutral.  That is the first time in this project that
a prediction made on stage2 has been confirmed on the final round, and it is worth more than the
result itself: the 40-instance training set is a usable proxy when the effect is a null.

## P6 returned 968,674 -- the third submission's value, to the digit

Two builds separated by the brk change, the contact_beam segfault fix, the bounded pool wait and
the fallback-scoring fix produced the same objective on the same hidden instance.  The attractor
structure documented on stage2 (results/audit/attractors.md) is present on the grader's instances
too.  It is the cleanest confirmation available that the answer set is a small discrete set per
instance rather than a continuous distribution.

## Five submissions, and the totals have not moved

    74,003,416 / 73,283,064 / 73,981,407 / 73,000,800 / 73,309,501

A 1.4% band, and the identical-code pair alone accounts for 1.33% of it.  Every algorithmic change
shipped so far -- per-seat pricing, parallel conflict-graph build, beam salvage, the split-aim
portfolio, brk removal -- has produced a total inside the range that re-running one build produces.

That is not evidence the changes did nothing.  Beam salvage turned a 42x cliff into 1.19x, which
is real and measured.  It is evidence that EIGHT INSTANCES CANNOT RESOLVE effects of the size this
work produces, and that reading the submitted totals as a scoreboard for the algorithm has been a
mistake throughout.
