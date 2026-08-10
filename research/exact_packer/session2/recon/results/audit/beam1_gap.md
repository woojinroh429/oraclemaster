# beam1 IS NOT THE PRODUCTION SEED GENERATOR, AND THAT EXPLAINS THE CONTRADICTION

## The contradiction

    deterministic table, axis 2, prob_1     w1500  686,238    w3000  684,687   (saturated)
    production, axis 2 pinned, best seed                      587,906

Production's axis-2 seed is 14% BETTER than the deterministic table's best at any work tested,
which is impossible if the deterministic curve is saturated.  Both cannot be measuring the same
thing.

## They are not.  `_beam_once` has a two-rung structure that beam1 bypasses

    def _beam_once(prob_info, budget, cfg, share=1.0):
        """One beam run, with a coarser position grid held in reserve. ...
        The budget is split, so a slice too small for step 1 still buys a step-2 answer
        instead of nothing."""

Production calls `_beam_once`, which splits the budget between a FINE rung (step 1) and a COARSE
rung (step 2) held in reserve, and it also redraws the block order on repeat visits when the
axis carries dk > 1.  beam1.py calls `_contact_beam` directly with `step=1` hardcoded and no
share, so it is the fine rung alone, once, with no reserve and no order redraw.

So the deterministic table is internally valid -- equal work, one harness, digests to prove
identity -- and it ranks a search PRODUCTION DOES NOT RUN.  Every axis ordering read off it is a
statement about the fine rung in isolation.

I reported "the deterministic table clearly points at axis 2" one message before finding this.
Withdrawn.  The wall-clock evidence is the one closer to production, and it puts pinned axis 2 at
515,465, sixth of seven.

## AND THE GAP IS MORE INTERESTING THAN THE THING IT BROKE

The claim in the file that a single beam draw on prob_16 at work 6,000 axis 2 returns 2,477,998 --
against 2,795,643 for the best full run this project has ever recorded there, and 3.28M-3.66M for
today's 240 s runs -- was measured with THIS beam.  That does not make it wrong: beam1 scores its
output with the same `_total` and reports feas=y, so 2,477,998 is a real feasible solution.

What it makes it is a statement that a configuration production never runs beats everything
production does run, by 11.4%, on one instance.  If that survives the prob_16 section of this
table, the question stops being "which axis" and becomes "why is the fine rung alone, at a work
level production never gives it, better than the whole pipeline".

## A SECOND THING: WORK IS NOT MONOTONE ON THE BAD AXES -- AND IS STILL PAYING ON THE BEST ONE

    prob_1 axis 0    w1500  1,569,183    w3000  1,174,681    w6000  1,243,617

More work made it WORSE from 3,000 to 6,000.  The file predicts exactly this -- a bigger budget
produces a WIDER beam, not a longer one, and "a wider beam ranks more states by the same myopic
proxy ... so more width can systematically prefer states that look better early and finish worse".
So "buy more work per draw" is not even monotone, let alone a lever.


## CORRECTION, ONE CELL AFTER I WROTE THE SECTION ABOVE

I concluded from axis 0 that "buy more work per draw is not even monotone, let alone a lever".
The next cell refuted it:

    axis 0    w1500  1,569,183   w3000  1,174,681   w6000  1,243,617     non-monotone
    axis 1    w1500  1,323,041   w3000  1,323,041   w6000  1,323,041     flat, one digest throughout
    axis 2    w1500    686,238   w3000    684,687   w6000    573,634     -16.2% at 6,000

Axis 2 was not saturated.  It has a PLATEAU between 1,500 and 3,000 and then falls 16.2% at 6,000,
and 573,634 is better than the best axis-2 seed production has ever produced (587,906).

So the shape is per-axis and reading it off one axis was wrong twice in a row -- first "axis 1 is
flat therefore the lever is dead", then "axis 0 is non-monotone therefore the lever is dead".  The
honest statement is that the best axis is still improving at 6,000 work, which is about 32 s, and
production gives a draw 7-8 s.

A plateau followed by a drop also explains why a coarse ladder misleads: 1,500 -> 3,000 reads
-0.2% and would have been called saturation by any two-point test.
