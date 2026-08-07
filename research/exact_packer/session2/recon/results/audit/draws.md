# What the beam's own draws look like, and six things this session got wrong about them

Every claim here is from a log line.  The retractions are kept in place rather than deleted,
because most of them were stated confidently first and the pattern matters more than the
conclusions.

## The instrumentation

`OGC_OPSTAT=1` prints tried / seconds / %budget / gain / gain-per-second for each operator at the
end of a worker.  It already existed; it had never been read for the beam's own call count.

`OGC_DRAWSTAT=1` (added today) prints one line per beam draw: wid, gen, TRUE axis index, seconds
asked, seconds taken, objective.  The true axis index matters because each worker holds a ROTATED
view of `_AXES`, so position 2 in worker 3's list is `_AXES[5]`.

`OGC_AXJIT=<f>` (added today) jitters the continuous axis terms per draw, seeded on (wid, gen).

## Draw counts: the budget DOES buy draws

    prob_16   60 s    beam tried 2 / 2 / 3 / 3   (~12 s per draw)
    prob_16  240 s    beam tried 10 / 10 / 6 / 4 (~14 s per draw)

Roughly linear in the budget, and the per-draw cost barely moves.  This killed a hypothesis
formed earlier the same hour -- that the opening slice being `0.20 * budget` meant a bigger budget
bought only WIDER draws.  It buys both: more draws AND bigger ones.

## Where the budget goes

prob_16 at 240 s, summed over four workers:

    beam   500.1 s     30 draws
    bay    193.7 s     total gain 3,759          <- 19 per second
    grow   153.6 s     total gain 2,784,624      (all of it in one worker)
    pref    94.5 s     total gain 129,222
    bal      0.2 s     total gain 680

Non-beam is 442 s of 942 s, 47%.

But this is instance-specific and it would be overfitting to act on prob_16 alone.  On prob_4 at
60 s, `pref` earned 342,335 and 120,871 in two workers and `bay` earned 76,221 -- the operators
that earn nothing on prob_16.  At 240 s on prob_4 `bay` falls back to 0 / 11,726, so the honest
statement is that `bay` looks like dead weight AT LONG BUDGETS on both instances tested, not that
it is dead weight.

## The two instances run on different machinery

    prob_16  240 s   best beam draw 3,602,025   final 3,602,025    beam is the whole answer
    prob_4   240 s   best beam draw 3,160,713   final 2,763,198    12.6% comes from the operators

And correspondingly:

    prob_16   60 s 3,472,568  ->  240 s 3,528,888    the long budget LOSES by 1.6%
    prob_4    60 s 2,959,655  ->  240 s 2,763,198    the long budget wins by 6.6%

So "a bigger budget can be worse" is not a property of the algorithm.  It is what happens on an
instance whose answer is entirely the beam's, when the extra budget goes to a beam that does not
improve.

## The scoring rule is a minimum, which is not what the search is tuned for

The answer is `min` over workers.  A minimum is decided by the LEFT TAIL of the draw distribution.
`OGC_BEAMCAP=12` -- capping what one draw may ask for -- raised prob_16's draw count from 30 to 43
and produced:

    prob_16   base    min 3,479,878   median worker 3,860,013
    prob_16   cap12   min 3,574,878   median worker 3,822,046

The median worker improved and the minimum got worse.  Across four instances (one replicate, and
on the contaminated build described below) cap12 was -1.04% on the minimum and better on the
median worker in 3 of 4 -- which is the check that separates a better search from a lucky draw.
Not decided; being re-run with two replicates on a clean build.

DO NOT use the `spread` column as evidence for any of this.  `spread` is `(max-min)/min` and the
score IS `min`, so an arm that lowers the minimum raises the spread by arithmetic.  Eight
conclusions were withdrawn on exactly this in an earlier session; see `spread_artifact.md`.

## Six things this session claimed and had to withdraw

1. **"The slice is a fraction of the budget, so a bigger budget buys width, not draws."**
   Refuted by the opstat draw counts above, within the hour.  `OGC_SLICECAP` was designed and
   dropped.  Partly right in the end -- the budget buys both -- but the reasoning was wrong when
   it was stated.

2. **"Axes 4 and 5 never open at nw=4."**  They never open as a worker's FIRST axis.  The rotation
   reaches them once a worker takes five or more draws, which happens at 240 s and does not at
   60 s.

3. **"The draws are only six distinct constructions."**  Stated from 8 DRAW lines, on the strength
   of axis 4 returning 4,103,551 in two different workers.  Refuted at 30 lines: 29 of the 30
   objectives were distinct.

4. **"The pool discards its own best solution -- this is a bug."**  An unbounded `awk '/tag/,0'`
   had pulled the NEXT cell's DRAW lines into the analysis, so prob_4 draws were being compared
   against prob_16 finals.  With cell boundaries respected, the best draw equals the final.

5. **"Small slices beat large slices on every axis."**  Same extraction error as 4.

6. **"Variance must be reduced."**  Held all session, and it is backwards for a min-of-N rule.
   `OGC_ADAPTB=0` was rejected in the pin queue for "failing to reduce variance" -- and it is the
   only arm that has ever reached prob_16's best recorded 240 s answer, 2,795,643.

## And a seventh, which is the one worth remembering

**"prob_24 is a noise-free control."**  It returned 2,809,182 to the last digit in three separate
queues on the identical configuration, so several queues in this session -- including one designed
specifically around it -- treated a single prob_24 cell as a clean signal.

Then, on one build with the instrumentation present, it returned 2,838,115, and removing the
instrumentation returned it to 2,809,182.  That was reported as proof that two dead calls behind
switched-off flags had moved the answer 1.03%.

The very next cell of the next queue, same fixed build, same settings, returned **2,779,963**.

So prob_24 is not deterministic; it has a basin wide enough that it lands in the same place often.
The 1.03% causal claim rested on one draw landing back in that basin and is withdrawn.  Removing
dead calls from the hot path is still correct -- an instrument that might move the measurement has
no business shipping inside the submitted algorithm -- but the effect size is not established.

What this costs: there is no instance in this set that can be judged from a single cell.  Every
comparison needs replicates, and the arm difference has to clear the baseline's own replicate
spread before it means anything.  prob_16 moves 3.5% between identical runs; prob_24 moves 1.05%.
An arm that wins by 1% has shown nothing.
