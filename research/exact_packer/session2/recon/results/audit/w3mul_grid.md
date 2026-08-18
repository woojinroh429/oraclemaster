# The final set prices bay preference 3.6x higher than the preliminary set, and w3mul never moved

The exchange rate w1/w3 is how many units of bay preference one unit of tardiness costs.  Measured
over both forty-instance sets from the instance files alone:

                       min    p25   median    p75     max
    preliminary  5.6   44.4   84.5    113.2   213.3
    final        4.2   10.4   23.3     50.9   106.7

The median falls by a factor of 3.6 and the lower quartile by 4.3.  Twenty of the forty final
instances sit below 20x, where the preliminary set had its lower quartile at 44x.  Preference was
close to a tiebreak in the preliminary set; in the final set it carries real value.

## The knob for it is frozen at preliminary values

w3mul is how hard the beam's rank routes toward preferred bays.  The beam already receives the
instance's true w1 and w3 -- w3mul is a bias multiplier on top, correcting the greedy lookahead's
undervaluation of preference (a non-preferred bay is a permanent loss; tardiness can sometimes be
recovered later).  The cost of that myopia scales with how valuable preference is, so a set whose
preference is 3.6x more valuable wants a higher multiplier.

    shipped grid   {1.0, 1.5, 3.0, 6.0}   span 6x

_AXES has not changed since 08-02 10:18.  The final set was identified as a different problem on
08-03 02:21 (1.8x median density, ten instances over capacity), and on 08-03 04:05 a commit titled
"The biggest opening in the final set is Z3, and no operator targets it" recorded the same gap from
the other direction.  The grid was never revisited.

## Why this is the safe form of the finding

No threshold and no per-instance decision.  Widening the grid upward -- {1.0, 3.0, 6.0, 12.0}, say
-- puts different multipliers on different workers and lets the minimum choose.  A worker whose
multiplier is wrong for the instance loses its draw and costs nothing else, which is the shape
overfit_rule.md allows.  The evidence base is both forty-instance sets in full, not a per-band n=3.

## What this does not say

That a higher multiplier helps.  The direction is argued from the weight distributions and the
knob's stated mechanism; it has not been run.  It also does not explain the prob_20 ortho loss on
its own -- axes_are_a_grid.md notes that o4 cut the w3mul range from four values to two at the same
time as it cut the axis count, and that log cannot separate the two.
