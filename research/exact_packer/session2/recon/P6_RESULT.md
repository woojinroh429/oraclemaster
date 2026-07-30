# P6: 27,556,165

    deployed build (900s)               28,373,827   Z1 4049
    beam family, best all session       29,387,514   Z1 4276
    fixed sac3 construction + polish    28,138,113   Z1 4023
    GRASP k=6 + polish                  27,556,165   Z1 3903    <- reproducible, feasible

2.9% past the deployed build.  Target was 27,000,000, so 2.0% short of it.

Reproduce with:

    python3.12 harness/grasp.py 6 600 300 6 flatbl 4242 sac3

## Why the beam was the wrong machine here

P6 is the only hidden instance above a demand ratio of 1 -- 1.137, against P5's
0.730 and P3's 0.327 -- and it is the only one where the deployed build turns
its contact beam off entirely.  At that ratio the yard cannot hold the demand,
so the binding decision is who waits and in what order, not where a block sits.

Three attempts to close the gap by changing the beam's placement score all
failed, and they failed the same way:

  pos_lam raised to make flatness primary   monotone worse; x40 cost 6.4%
  floor-span charged inside the sum         negligible
  the construction's lexicographic key,     Z1 5411 against the construction's
  with h and the small-block branch fixed   4052 -- far too much to be position

A weighted sum cannot express what a sort key does.  Raising h's weight does not
promote h to first place, it deletes contact: blocks stop needing to touch
anything as long as they sit shallow, they spread, the free space fragments, and
Z1 follows the fragmentation down.

## What actually won

**The dispatch order.**  `order=sac3` exiles the three largest area*pt blocks to
the back of the dispatch, so those three absorb the tardiness and the other 247
land on time -- three blocks very late costs less than 247 blocks slightly late.
That one change built 28,261,134 in fifteen seconds, past the deployed build's
own 900-second answer.

**Our polish, unmodified.**  z3_reassign takes Z2 and Z3 and leaves Z1 alone,
which is exactly how the deployed answer decomposes: its Z1 equals the diagonal
construction's to the digit, and the 137,292 between them is Z2 and Z3
arithmetic.  Nothing was ported; the operator was written for the beam.

**GRASP.**  The fixed construction returns the same answer at 900s as at 120s,
so 585 of the 900 seconds were idle on the instance whose construction settles
97% of the objective.  Drawing the order from the top-k of what remains -- k=1
being sac3 exactly -- converts budget into quality and produced the last 2%.  It
adds no constant.

## Negative results, kept because they cost real time

  GRASP with elite memory and reactive k    lost to plain GRASP in four runs.
                                            Incumbents are too rare (1-3 per run)
                                            to learn a k from, and every elite is
                                            a near-greedy order, so biasing
                                            toward their agreement reinforces the
                                            greedy instead of departing from it.
  reactive rule on the running median       backwards for a best-of: it rewards
                                            consistency, and a best-of keeps the
                                            maximum, so variance is the asset.
  k past 6                                  k=10 improved on the pure greedy zero
                                            times in 43 draws.
  840/60 draws-to-polish vs 600/300         ties.  The draw distribution is
                                            heavy-tailed, not steadily improving:
                                            seed 777 found its incumbent at draw
                                            34 and 17 further draws found nothing,
                                            while seed 4242 found a better one at
                                            draw 11.
  scheduling and packing do not separate    fixing (bay, entry time) and re-packing
                                            from scratch displaced 181 of 250
                                            blocks and cost 23%.  x,y are absent
                                            from the objective but they decide
                                            which schedules stay feasible.

## What is left on the table

The polish converges by 300s and more budget does not move it.  The construction
is deterministic per order.  So the only budget-responsive part is the number of
draws, and draws are i.i.d. from a heavy-tailed distribution -- which means the
untouched multiplier is parallelism: every measurement here ran ONE stream on a
four-core box.
