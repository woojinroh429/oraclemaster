# w3mul is a convergence knob, not a diversity knob, and the direction argued from the weights was wrong

prob_4 (w1/w3 = 6.3x, the band where raising w3mul was predicted to pay most), 240 s, one draw per
arm, all four arms on the same six axes with only the multipliers changed.

    arm      opening w3mul     obj          vs base    worker spread
    dn       0.5 / 1 / 2 / 4   2,615,319     -0.23%     24.27%
    base     1 / 3 / 3 / 1     2,621,290        --      23.50%
    spread   1 / 3 / 6 / 12    2,621,290      0.00%     18.72%
    up       3 / 6 / 12 / 24   2,770,277     +5.69%     12.56%

Both columns are monotone in the grid and they move together: the higher the multipliers, the more
the four workers agree, and the worse the minimum.  This is the first time this session that
portfolio spread and answer quality have been seen tracking each other across four points inside a
single instance -- every earlier claim about diversity was inferred rather than measured.

The mechanism is visible in the worker rows.  Raising w3mul lifts the LOSING workers (worker 0 goes
3,042,268 -> 2,789,140 at spread) and costs the BEST one (worker 2 goes 2,621,290 -> 2,770,277 at
up).  A large preference multiplier lets that term dominate the rank, so Bmul, pos_lam and order
stop separating the workers and they converge.  The answer is a minimum, so lifting the average at
the expense of the best is a straight loss.

## The prediction in w3mul_grid.md is refuted

That file argued from the weight distributions -- the final set's median exchange rate is 3.6x
lower than the preliminary set's, so preference is worth more, so the multiplier should rise.  The
two arms that raise it return 0.00% and +5.69%.  The distributional argument lost to the search
dynamics, which it did not model.

## What is and is not established

Established: up is worse, at +5.69% against a 4.4% run-to-run spread on this instance, and the
spread/quality relationship is monotone over four points.

Not established: that dn is better.  Its -0.23% is well inside prob_4's own 4.4% band, and this is
one instance in the band most favourable to the original hypothesis.  "Lower is better" is the
mirror of the claim just refuted and needs its own evidence.
