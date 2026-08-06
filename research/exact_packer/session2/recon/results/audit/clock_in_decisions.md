# Step 3: taking the clock out of the decisions

Companion to `variance_source.md`, which established that every RNG in `myalgorithm.py` is
constant-seeded and therefore that 100% of the run-to-run spread (2.5-16%) is `time.time()`.

## Every site where the clock decides something, and what kind of decision it is

Verified by grep against `myalgorithm.py`, not from memory.

| line | site | kind |
|---|---|---|
| `left = budget - (time.time()-t0)`; `if left < 2.0: break` | loop termination | **STOPPING** -- must stay on the clock |
| `wbudget = timelimit - reserve - elapsed - 1.0` | how long workers get | **STOPPING** |
| `_contact_beam`: `if _t.time()-t0 > deadline_s` / C++ `elapsed() > time_budget_s*AIM` | when the beam bails and salvages | STOPPING in form, **SELECTION in effect** -- it decides which construction gets completed |
| `k = max(elig, key=lambda i: gain[i]/spent[i])` | which operator runs next; `spent` is measured **seconds** | **SELECTION** |
| `slot[k] = min(budget*0.25, max(1.0, 1.3*el))` | repair-pass slice, from the last call's measured **seconds** | **SIZING** -- and it compounds across calls |
| `if s is None and (not _SLICEFIX or el >= 0.6*slot[k])` | whether an empty search call counts as starved | SIZING |
| `elig = [... if left - 1.0 >= ops[i][4]]` | whether an operator runs **at all** | discrete -- step 2's territory |
| `_frac = elapsed/budget`, gated `0.30 <= _frac <= 0.60` | lagging-worker restart | SELECTION, but `_SHARE` is **off by default**, so not live |

Machine speed currently changes two things at once: how much work each operator gets done, and
the entire schedule of which operators run and for how long. Only the first is unavoidable.

## What full determinism would actually cost

Every operator consumes **seconds**: `beam`/`_fresh`, `grow`, `bal`, `pref` (`Engine.z3_reassign`,
whose body is `while(elapsed()<budget){ruin_recreate(); hillclimb();}`), `brk` (`bayrepack.repack`),
and `bay` (`_assign`, a CP-SAT call). Making the run reproducible means converting all six from a
time budget to a work budget -- two of them in C++, and **CP-SAT's only budget is wall time**, so
`bay` cannot be made deterministic at all short of a branch/conf limit.

That is a redesign, not an edit, and it carries real quality risk. So it is not the first thing to
do; it is what step 3 escalates to if the cheap version does not shrink the spread.

## What is in `myalg_det.py` now

A copy of `myalgorithm.py` with two default-off arms, so the module is behaviourally identical
until an env var is set and an A/B against `myalgorithm` is unconfounded by anything else.

- **`OGC_DETQ=<b>`** -- quantise the measured duration onto a log grid of ratio `b` before it feeds
  `spent` or the slice sizing. Jitter smaller than one bucket changes no decision, so the schedule
  repeats; only a genuinely different machine speed flips a bucket. `1.25` is the first value to
  try: wider than the jitter between repeat runs, far narrower than the ~2x that separates
  operator classes. The true elapsed is still recorded -- only what the *scheduler* sees is
  rounded.
- **`OGC_DETV=1`** -- virtual clock: charge each operator the slice it was **given** rather than
  the time it took, making the schedule depend only on `gain`. Known cost, stated up front: a
  repair pass finishing in 0.1 s of a 5 s slice is billed 5 s and so priced too low. The real
  clock still governs termination, so this can never truncate a run. Under DETV the repair-pass
  slice is left alone rather than pinned to the request, which would ratchet a 0.1 s pass up to a
  quarter of the budget.

- **`OGC_SCHED=1`** -- prints the actual sequence of picks and slice sizes per worker. This is the
  test, and it makes "did the clock stop steering?" a **diff** rather than an opinion: two runs of
  one instance, two SCHED lines. `OGC_OPSTAT` reports per-operator totals, which are sums and hide
  the ordering.

## How it gets judged

1. Same instance, two runs, `OGC_SCHED=1`. Baseline schedules will differ; the arm's should match.
   That is the mechanism check and it is cheap.
2. Only if the schedule stabilises does quality get measured, paired over the 40 final-training
   instances -- because a stable schedule that is stably *worse* is not the goal.

Nothing has been run yet: `cliff40` owns all four cores, and a concurrent run would corrupt the
very timings it is measuring.
