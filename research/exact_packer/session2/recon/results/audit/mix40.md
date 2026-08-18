# The beam's aim as a portfolio axis: 37 of 40 paired instances, 180 s

Odd workers run OGC_BEAMAIM=0.10, even workers 0.90 (today's behaviour); algorithm() returns the
minimum over the four.  Control forces 0.90 everywhere.

    group          n   better  worse   mean      median    losses over 10%
    small <250    18     14      4    -0.38%    -1.84%    P7 +38%, P22 +30%
    large >=250   19     17      2    -5.99%    -4.33%    none
    all           37     31      6    -3.26%    -3.44%    P7 +38%, P22 +30%

Sign test on the 37: p < 0.0001.

## The prediction I got wrong

I expected the small instances to lose, on the reasoning that their beam finishes, the salvage
never fires, and two of four workers are therefore wasted.  Measured at a single constant that
was true -- prob_1 was +25.09% with ALL workers at 0.10.  As a portfolio axis it is not: the
small group is 14-4 with a median of -1.84%, and its mean improved monotonically as the sample
grew, +3.06% -> +2.30% -> +0.72% -> -0.38%.  The low-aim workers earn their place as diversity
rather than as a rescue, and the minimum absorbs the ones that lose.

## What is still open

P7 (+38%) and P22 (+30%) are the only losses above 10% and both are small.  Two is not one, so
they are not obviously outliers -- but no small instance after them lost more than 10% in the six
that followed.  They need replicates before this ships: prob_20's -17.37% became -0.9% under
three replicates earlier today, and every single draw checked so far has shrunk.

## Data loss

results/audit/mix40.log was untracked when the container restarted at 08:57 and the rewind took
it -- 74 of 80 runs, three pairs from completion, the third such loss today.  The tallies above
survive only because they were read and reported as they landed.
