# The run-to-run variance is wall-clock, and nothing else

Found 2026-08-06, by reading the code rather than running another experiment.

## The deduction

Every random number generator in `myalgorithm.py` is seeded from a constant:

    1306:  _DRAW_RNG = random.Random(20260731)
    1981:  rng = random.Random(1234 + wid)
    2263:  rng = random.Random(90001 + 7919 * wid)

There is no `os.urandom`, no `getpid()`, no time-derived seed anywhere.  `wid` is
deterministic, the beam aim per worker is deterministic (`_aims[wid % len(_aims)]`), and the
axis rotation is deterministic (`_AXES[(wid + i) % len(_AXES)]`).

So two runs of the same build, on the same instance, at the same budget, differ in exactly one
input: `time.time()`.

They do differ:

    P16 [r1.base.16]  240s  obj=3,813,686   ran 239s
    P16 [r2.base.16]  240s  obj=3,281,165   ran 239s      16.2% apart
    P20 [r1.base.20]  240s  obj=9,478,709   ran 215s
    P20 [r2.base.20]  240s  obj=9,249,368   ran 239s      the runs did not even use the same time

Therefore **100% of the run-to-run variance is timing**.  Not seeds, not dispatch order, not the
axis portfolio.

## Where the clock enters the DECISIONS

Time is not merely a stopping condition here; it selects what the algorithm does:

| site | what the clock decides |
|---|---|
| `_contact_beam` deadline, and C++ `elapsed() > time_budget_s*AIM` | which construction gets completed -- a discrete jump |
| `max(elig, key=lambda i: gain[i] / spent[i])` | which operator runs next; `spent` is **seconds** |
| `slot[k] = min(budget*0.25, max(1.0, 1.3*el))` | how much that operator gets; `el` is **seconds** |
| `elig = [... if left - 1.0 >= ops[i][4] ...]` | whether an operator runs **at all** |
| `_frac = (time.time()-t0)/budget`, gated to 0.30-0.60 | whether a lagging worker restarts |
| `reserve`, `wbudget` | how much is left for the final polish |

Four workers plus a parent on four cores: the timing is noise, and the noise is steering.

## What this explains

- **b240 / axcount / bandit / orders / newaxis / rounds / mbay / ridge all read as noise.**
  Arm-to-arm differences were 2-5%; the same arm re-run moved 2.5-16%.  Every one of those
  studies was measuring a deterministic knob against a variance source that knob does not touch.
- **"Is dispatch order the sensitive thing?"** -- it is sensitive in CONSTRUCTION (cdecomp: 32-210%
  against a 0-12.6% control) and it cannot be the cause of run-to-run jumps, because it is
  deterministic.  Two different questions that were being conflated.
- **Why the three submitted score sets move so much per instance.**  Our machine's speed is not
  the grader's, and the hidden per-instance time limits are not disclosed.  The effective budget
  at scoring time differs from ours, and that changes every decision in the table above.  Three
  submissions on three machine-moments is close to three different algorithms.

## What follows, in order of value

1. **Find the remaining cliffs.**  Timing noise is equivalent to effective-budget noise, so plot
   obj(T) per instance (120/150/180/210/240/270/300 s).  Smooth curve, noise is nearly free;
   a jump, and that instance is fatally exposed.  Each jump is a discrete decision that throws
   completed work away.  The one change that ever clearly won here -- beam salvage -- was exactly
   this, and the ladder has not been re-run since salvage landed.
2. **Take the clock out of SELECTION, leave it in STOPPING.**  Replace `spent[i]` (seconds) with a
   deterministic work counter, so *what to do* stops depending on machine speed while *when to
   stop* still depends on the clock, as it must.  Cheap to validate: two runs of one instance
   should become byte-identical.  Today they are 16% apart.
3. **Make the incumbent monotone everywhere.**  Stopping early should cost a little quality, never
   a category.  Salvage gave the beam this property; the operator-eligibility gate
   (`left - 1.0 >= ops[i][4]`) has not got it -- a slightly slow run silently drops an operator.

The score is per instance, so raising a good instance a little is worth almost nothing and one
cliff loses that instance outright.  The value is entirely in the tail, which is what was asked
for from the start.
