# CROSSING TWO FACTORS REDUCES DISPERSION.  THE SHIPPED PAIR IS ALREADY THE MAXIMUM.

    cell             final        round-0 workers                          dispersion of losers
    r1.p1.off       518,660    518,660  594,521  743,665  855,092                0.1460
    r1.p1.cross     584,609    584,609  667,717  811,242  836,872                0.0964

OGC_CROSS was meant to RAISE dispersion by turning two configurations into four.  It lowered it by
34%, and the objective rose 12.7%.

## THE GEOMETRY I HAD BACKWARDS

Two binary factors crossed give a 2x2 grid, and the four grid points are CLOSER to one another
than the two diagonal corners are:

    shipped     (aim 0.90, m=1)  and  (aim 0.10, m=2)          the two opposite corners
    CROSS       (0.90,1) (0.10,1) (0.90,2) (0.10,2)            the corners plus the two middles

The beam aim, the m split and DIRSET all index `wid % 2`, which I read all night as "the splits
are correlated, so the pool is only two configurations".  That is true and it is also what makes
those two configurations maximally far apart -- three factors flipped together.  Crossing any of
them fills in intermediate points and shrinks the pool's diameter.

Count is not distance.  I proposed CROSS on the count.

## AND IT IS EVIDENCE FOR THE DISPERSION READING, NOT AGAINST IT

    dispersion -34%   ->   objective +12.7%

which is the direction r(dispersion, min) = -0.771 predicts.  This is the first arm tonight where
the prediction was written down before the cell ran and the cell agreed.

One pair.  Five two-pair readings reversed on their third today, so this is a hypothesis with one
supporting observation, not a result.  The remaining five pairs decide it.

## WHAT IT MEANS FOR THE NEXT STEP

If the correlation is causal, raising dispersion needs configurations FURTHER APART, not more of
them -- and the three factors that exist are already flipped together, so the pool's diameter is
already maximal for what is in the file.  Widening it requires a NEW factor, not a re-indexing of
the ones there.
