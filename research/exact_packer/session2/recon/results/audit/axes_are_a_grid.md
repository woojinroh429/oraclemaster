# Correction: the axis list is a grid over three parameters, not a list of dispatch orders

axes_structure.md counted the `order` column, found three distinct values across six entries, and
concluded that three of the slots were duplicates.  The comment directly above _AXES says what the
list actually is, and it is not that:

    order   : the largest single effect (selective defer-big)
    w3mul   : how hard the rank routes toward preferred bays.  prob_39 gave up Z1 +6 for
              Z2 -2431 and Z3 -3107 and the objective improved.
    fut_beta: pushes long-stay blocks to the walls, keeping the bay centre free for later
              crane descents.

Three parameters with measured independent effect.  `order` is one of them.  The three defer_big
entries hold order at its best-measured value and sample the other two:

    axis 0   defer_big   w3mul 1.0   fut_beta 1.0   Bmul 1.0
    axis 1   defer_big   w3mul 3.0   fut_beta 1.0   Bmul 1.0
    axis 5   defer_big   w3mul 1.5   fut_beta 0.0   Bmul 0.5

Not duplicates.  A grid, read one column at a time.

## Which explains the prob_20 loss better than axis count did

    base w3mul   1.0  3.0  3.0  1.0  6.0  1.5     four values, 1.0 to 6.0
    o4   w3mul   1.0  3.0  1.0  3.0               two values, 1.0 to 3.0

o4 dropped w3mul 6.0 and 1.5 entirely and fut_beta 0.5 with them.  ortho_p20.md read the damage as
tracking axis COUNT (6 -> 5 -> 4 mapping to 0, +12.0%, +14.8%/+17.7%); the count and the w3mul
range fell together, so that log cannot separate them, but w3mul has the mechanism behind it and
count does not.

## And w3mul is the parameter whose right value provably varies by instance

exchange.md measured w1/w3 across the forty stage-2 instances at 4.2x to 106.7x -- a 25-fold range
in how expensive tardiness is against bay preference.  w3mul is the knob that answers exactly that
question inside the beam.  So a portfolio that spreads w3mul is covering a quantity known to vary,
with no threshold to choose and nothing fitted: the minimum over workers picks, and a worker on the
wrong setting simply loses its draw.

That is the overfit-safe form from overfit_rule.md, and unlike the aim-split rule it does not
require deciding anything per instance.

## Open, and answerable from the instance files alone

The current grid {1.0, 1.5, 3.0, 6.0} was fitted on the PRELIMINARY set -- _AXES has not changed
since 08-02, and the final set was identified as a different problem on 08-03 (1.8x median density,
ten instances over capacity).  Whether that grid covers the final set's exchange-rate distribution
has never been checked.
