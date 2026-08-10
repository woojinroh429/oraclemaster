# WORKER DISPERSION PREDICTS THE MINIMUM AS STRONGLY AS WORKER QUALITY, AND NOTHING TONIGHT TOUCHED IT

## The measurement, built to avoid the spread artifact

spread_artifact.md warns that `(max-min)/min` is mechanically anti-correlated with the minimum,
because the minimum is both its denominator and the score, and that eight conclusions were once
withdrawn on it.  So the minimum is EXCLUDED from both regressors here: for each run's four
round-0 worker objectives, take the three non-minimum workers and compute

    level        their mean
    dispersion   their stdev / their mean

Neither uses the minimum, so neither is arithmetically tied to it.

    prob      runs   r(level, min)   r(dispersion, min)
    prob_1     297      +0.826            -0.771
    prob_3      71      +0.896            -0.709
    prob_24     45      +0.202            -0.635
    prob_12     53      +0.635            -0.465
    prob_6     137      +0.713            -0.340
    prob_16    233      +0.724            -0.314
    prob_20    176      +0.672            -0.171
    prob_30     57      +0.934            +0.114

On prob_1 the two forces are almost equal in magnitude: raising the level by one standard
deviation and raising the dispersion by one standard deviation move the minimum about as far, in
opposite directions.

## EVERY ARM TONIGHT AIMED AT THE LEVEL

brk, bk67, the axis director, axis pinning, round count, RESFRAC, POLCAP, PARFILL, PARROUND,
BRKPAR, FINEFRAC -- all of them try to make workers BETTER.  None tries to make them DIFFERENT.
And the level is the hard half: nine arms, nine failures.

Three results from tonight point the same way once read this way round:

    the attractor table   20 values cover 34% of 1,176 prob_1 worker results -- workers are
                          converging on each other
    config B on prob_1    540 draws, never below 516,577.  Not "half the cores are wasted" but
                          "half the cores contribute no diversity"
    bk67                  gave all six axes ONE width and ONE branching factor.  That is a
                          diversity-REDUCING change, and it lost
    BRKPAR=half           I described it as keeping one pure worker per configuration.  It did not
                          add diversity; it halved brk.  It lost worst of all.

## WHAT IS UNTRIED

The four workers hold only TWO configurations: the beam aim, the m split and DIRSET all index
`wid % 2`.  `OGC_CROSS=1` indexes m by `(wid // 2) % 2` instead, making the two splits a 2x2 and
the pool FOUR distinct configurations.  The code is in the file and its own comment says whether
widening beats deepening here "is exactly what has never been measured".

That is a direct, already-implemented increase in dispersion, and it has never been run.
