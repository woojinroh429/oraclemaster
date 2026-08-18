# The final polish was retired on the wrong statistic, and it is worth 4-8% at 240 s

## What retired it

    across 804 runs the polish's median gain is 0.00% and 419 of them gained NOTHING,
    for a reservation of min(20% of budget, 40 s)

Every number in that sentence is correct.  The same measurement also recorded THREE runs gaining
over 5%, and those were set aside as outliers.

The reported answer is `min` over workers, and scoring is PER INSTANCE.  Both facts point the same
way: what pays is the tail, not the centre.  A pass that earns nothing on seven instances and 20%
on the eighth is worth its reservation on the eighth, and no median taken across all of them can
see that.  This session made exactly this argument to reject OGC_BEAMCAP -- "the median worker
improved and the minimum got worse, so the arm is going the wrong way" -- and did not apply it to
the polish.

Worse, the `mono` queue's four cells were reported as confirmation ("polish gained exactly 0.00%
on all four").  Four cells drawn from a distribution whose median is zero confirm the median.
They say nothing about the tail, which is the only part that matters here.

## How it surfaced

Not by re-examining the decision.  By a control failing.

`rounds.log` had prob_16 at 60 s returning 2,796,522 with OGC_ROUNDS=2, identical in four
replicates.  That is 23% below anything this project produces on prob_16 at 240 s, so a queue was
built to chase it -- and its positive control, the same cell on today's build, returned 3,835,016.
The old number belonged to the old build.  The largest behavioural difference between the builds
is that the polish now defaults off.

## The 2x2, prob_16 at 60 s

                    polish OFF                     polish ON
    R=1    3,472,568 / 3,574,878  (2.9% apart)     3,513,968
    R=2    3,520,718 / 3,835,016  (8.9% apart)     2,796,522   (5 of 5 identical)

Neither factor has a main effect.  Polish at R=1 lands in the middle of the polish-off range.
R=2 without the polish does nothing.  Together they are -21.8%, and the result repeats to the last
digit across five cells -- four in the old log, one today.

That is an interaction, and it is invisible to any experiment that switches one feature at a time.
Both features had been independently retired, so the combination had never been run.

## At the budget that ships: 240 s, paired inside one queue

    P16   polish ON 3,286,759   OFF 3,557,431   -7.61%
    P4    polish ON 2,615,319   OFF 2,737,344   -4.46%
    P20   polish ON 8,854,193   OFF 9,215,638   -3.92%

Three of three, same sign.  Individually each is close to that instance's own run-to-run spread
(prob_16 5.2%, prob_20 5.3%), so no single cell decides anything -- but noise does not produce
three matching signs, and the prob_16 polish-ON cell is below ALL SIX polish-off runs recorded on
that instance today (3,479,878 / 3,557,431 / 3,602,025 / 3,630,739 / 3,656,247 / 3,661,692).

## Why the budget matters, and why "it does nothing" was true at 60 s

The reserve is `min(0.20 * timelimit, 40)`: 12 s at 60 s, 40 s at 240 s.  `_z3_improve` calls
`Engine.z3_reassign`, whose body is

    hillclimb(); while (elapsed() < budget) { ruin_recreate(rng); hillclimb(); ... }

-- a loop that runs until its budget is gone.  It absorbs whatever it is given.  So 12 s buys
nothing at R=1 and 40 s buys 7.6%, and a measurement taken at one budget does not transfer to the
other.  This is in the tree's own comments and was overruled by the median anyway.

## What this implies beyond the polish

A dozen things in this repository are switched off with the note that they did not pay when tried
alone: `brk`, `pull`, `pmov`, `swap`, `cpas`, `bay`, several axis sets, higher `w3mul`.  Each
retirement should be re-read against three questions the polish failed:

  - was it judged on a mean or a median, when the score is a per-instance minimum?
  - was it measured at one budget only?  the polish is worth 0% at 60 s and 7.6% at 240 s
  - was it ever run in combination?  polish x rounds is -21.8% and neither has a main effect

Retirements compound: once two features are off, the region where they interact stops being
reachable by any experiment that toggles one at a time.
