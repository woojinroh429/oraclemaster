# The algorithm, as shipped

Three files. `myalgorithm.py` (1,466 lines) is the entry point and the scheduler,
`bayrepack.py` (674) is one operator, and the two C++ extensions — `ogc_fast.cpp` (the
construction engine) and `cranepack.cpp` (an exact-ish set-packing solver) — hold every hot
loop. Everything else in the directory is a harness or an archived experiment.

---

## 1. What the objective actually asks for

    minimise   w1*Z1 + w2*Z2 + w3*Z3

and the single most useful structural fact about it is this: **the objective reads only
(bay, entry time).** A block's x, y and orientation appear nowhere in it. Geometry is a
*constraint*, not a term — it decides whether a schedule is feasible, and feasibility is what
makes tight packing worth anything.

Which term binds is an instance property, and the spread across the six is not gradual:

| | Z1 share | what the instance really is |
|---|---|---|
| P3 | **0%** | Z1 pinned at zero. 87% of the objective is Z3 (preference). An assignment problem. |
| P6 | **97.4%** | the yard is saturated, times are everything. A packing problem. |

There is nothing between 0% and 96% in the measured set. This is why nothing in the algorithm
is gated on instance type: a hand-drawn density threshold would have to guess where the switch
is, and the whole range is either side of it.

## 2. Shape of the run

```
algorithm(prob_info, timelimit)
  ├── reserve = min(0.20*T, 40s) held back for a final Z3 polish
  ├── 4 workers (multiprocessing), each with a different RNG seed and a different
  │   starting offset into the diversification axes
  │     └── _worker: floor solution, then ONE measured-payoff operator loop
  ├── take the minimum of the FULL objective over the workers
  └── final _z3_improve pass on the winner
```

**The floor.** Every worker starts by producing `_safe_sequential`, a cheap always-feasible
schedule. It is the single guarantee that the algorithm never returns nothing, and it is why
every other fallback path could be deleted.

**Selection.** `_total` is the only criterion anywhere in the pipeline, and it re-runs the
*real grader* (`check_feasibility`) on anything that beats the incumbent, returning infinity on
failure. That is what bounds the risk of an over-permissive packer: an operator can be wrong
about feasibility, but it cannot get a wrong answer accepted.

## 3. The operator loop — the one design decision that matters

Six operators, no fixed shares, no instance classification:

| operator | what it does | needs an incumbent |
|---|---|---|
| `beam` | fresh contact-beam construction on a rotating diversification axis | no |
| `grow` | re-grow from a pool member, with crossover/relink between two of them | yes |
| `bal` | load balancing repair | yes |
| `pref` | Z3 (preference) repair | yes |
| `bay` | CP-SAT bay reassignment (OR-Tools, when available) | yes |
| `brk` | lift a whole pressed bay and re-pack it exactly (`bayrepack` → `cranepack`) | yes |

Each gets one short probe to establish a rate; after that the budget goes to whichever is
actually paying, **in objective units per second**, with 15% exploration so a slow starter can
recover.

**Selection and sizing are two different questions, and conflating them was a measured
failure.** Selection is by payoff (`gain/spent`). Sizing is *not*: sizing on payoff
death-spirals, because a fresh beam that returns a perfectly good solution which merely fails
to beat the incumbent scores zero, shrinks, and then cannot finish at all — measured on
prob_18, fourteen calls returning four solutions, objective 48,840 → 56,841. So size is a
**completion** question instead: a search operator that returned nothing was starved and gets
more; one that returned anything fit, so leave it alone; a repair pass always completes, so it
gets what it actually used.

The opening slices are deliberately asymmetric — search operators open on a fifth of the budget,
repair passes on `budget/(2n)`. Both directions of the symmetric version were measured and both
are worse: a flat fifth each over six operators spends 1.2× the whole budget before anything is
tried twice (real P6 at 300 s: the first beam produced the best solution of the run in 33
seconds and the other 267 went on first probes), while giving *every* operator the small derived
share starves the beams — real P6 at 900 s went 29,396,046 → 30,898,889 with Z1, Z2 and Z3 all
degrading.

## 4. The construction: contact beam (`ogc_fast.cpp`)

A beam search over dispatch order. Each state places the next block at the position minimising

    score = -con_w * contact + (iy + y1)*pos_lam*sw_y + ix*pos_lam*sw_x + prefw*penalty

Contact is counted **per layer**, not on a flattened footprint: the crane descends vertically,
so a block standing beside a shorter one has its upper layers against open air, obstructing
later descents without buying any tightness. Survivors are completed by a rollout and ranked on
the exact objective.

Six diversification axes (beam width multiplier, top-K, positional weight, dispatch order,
future-wall term, Z3 multiplier, cohort weight) rotate rather than being bandit-picked: with six
axes and only a handful of slices in a 60 s budget a bandit never leaves exploration, and
measured it cost prob_3 44,400 → 49,020. Diversity across axes is covered *between* workers
instead, which each start at a different offset.

### The contact upper bound (added today)

86% of scored cells were being evaluated after the best had already been found. An earlier
attempt bounded the **position** term and fired zero times out of 112.9 M cells — the score is
contact-dominated by more than an order of magnitude (positional range ≈ 2.3 against a contact
range ≈ 60), so a bound that only knows `iy` is always far below any real cell's score.

Bounding the **contact** inverts that. `contact_at` counts, per footprint cell, its four
neighbours — outside the bay scores 1, inside the footprint scores nothing, an occupied cell
scores its weight — so

    ct  ≤  (out-of-bay cell-directions)  +  4 · Wmax · |occupied cells in the footprint bbox dilated by 1|

because every occupied cell that can contribute lies in that rectangle and is counted at most
once per direction. An occupancy prefix sum, built beside the run tables at the same
O(bayW·bayH) the occupancy map already costs, answers the rectangle in four reads.

Verified per cell, not by A/B: `OGC_PRUNECHK=1` scores the cell the bound wanted to skip anyway
and counts it if it then becomes the best.

| | cells the bound skipped | wrong | time (fixed work) | assignment |
|---|---|---|---|---|
| P3 | 45.9 M (40.8%) | **0** | 103.52 s → 55.99 s (**1.85×**) | identical digest |
| P4 | 11.6 M (3.4%) | **0** | 27.43 s → 16.55 s (**1.66×**) | identical digest |
| P6 | 9.3 M (1.3%) | **0** | 102.72 s → 94.61 s (**1.09×**) | identical digest |

A wall-clock A/B cannot test this: both arms run a fixed budget, so the faster arm searches
further and legitimately lands elsewhere. The timings above are one `contact_beam` call with
identical arguments and the deadline lifted, and the digests hash every returned placement.

**The firing rate turned out to be the wrong predictor and it was used twice.** P6 was predicted
*negative* (1.3% cut, same prefix-sum cost) and came out +9%; P4's 3.4% was predicted marginal
and came out 1.66×. The rate counts **cells**, and most cells are thrown out by the hard-reject
bitmap after a single probe — the cells the bound removes are the ones that would have survived
to the exact geometric test and the contact sum. Cutting 3.4% of the cells cuts 40% of the
seconds.

## 5. The `brk` operator (`bayrepack.py` + `cranepack.cpp`)

Lift **every** block out of the most pressed bay, add the outsiders that might want in, and hand
the whole set to `cranepack` weighted in objective units. It is a maximum-weight set packing
over space-time columns.

A call is two phases with completely different characters:

* **BUILD** — an O(ncol²) conflict graph, uninterruptible.
* **SEARCH** — a deadline-honouring local search over the packing.

Three things make this affordable:

**The build watches its own clock.** It projects its completion every 256 rows from the most
recent chunk (not a cumulative average — a warming memo made that projection refuse a tier it
could easily afford) and aborts a tier it cannot finish. On abort the operator **steps down** a
tier and rebuilds, rather than losing the call.

**`total_s` bounds build + search against the build's own *measured* cost**, so the deadline
holds without predicting anything. The ask handed to the search is the slice, unmodified —
subtracting a predicted build from it as well was a double charge worth 7,195 on P3.

**The tier is derived, not fitted.** `_TIERS` holds *fractions* of the instance's own entry-time
ceiling, so P3's 6/3/2/1 window widths come out of the instance rather than out of a table.

Two correctness/speed results from today:

* **Offset-relative geometry.** The conflict memo initially produced +36 edges. It was blamed
  on key aliasing; dumping the mismatches showed floating-point *position dependence*. Fixed at
  the source — `crane_conflict_rel` compares origin outlines plus an offset, so the verdict is
  position-independent — which is a correctness fix that happens to also make the memo sound.
* **Build 10.5× faster with a provably identical graph.** Two columns can only conflict if they
  are co-present, so an entry-sorted sweep with a break skips ~83% of P3's pairs without visiting
  them, and the `Col` fields the filter needs were pulled into flat arrays. Neither changes which
  pairs conflict, so `n_edges` must come out identical — and that, not the clock, is what
  decided it. In production the same P3 tier now builds in 10.7–14.2 s where it cost ~90 s.

A free-column bitset was built on an assumption about which line was hot, proved identical, and
measured **1.6–1.9× slower**. It was reverted and the refutation left in the source.

## 6. What each instance's score is actually made of

This was read out of the run logs today, and it is not uniform:

**P3 — a best-of-N draw.** In a 240 s run `brk` produced exactly four solutions — 94,375 /
86,975 / 91,590 / 100,740 — and the reported score, 86,975, is their **minimum**. So P3's
objective is a min-of-4 order statistic over a distribution spanning 13,765, and the
80,795–90,225 spread that reads as instability *is that order statistic*. No amount of speed
removes it.

**P4 — deterministic, and `brk` never touches it.** Zero accepted `brk` solutions in the whole
run, never reaching tier 0. The score matched the baseline to the digit.

Same algorithm, different component holding the objective. It is the reason a scheduler policy
fitted to P3's curve would be tuned on an instance P4 is not even on.

## 7. Measurement discipline

Enough results had to be retracted today that the method is part of the algorithm's description:

* **An identity check that never executed is not an identity check.** The position bound "passed"
  identity because the branch never ran.
* **A speedup with a different answer is not a speedup.** Every acceleration here is decided by an
  invariant that must come out bit-identical — `n_edges` for the conflict graph, a placement
  digest for the beam — and the clock is only read afterwards.
* **A proxy that has never been checked against a clock is not a measurement.** The firing rate
  was wrong twice, both times in the same direction.
* **Nothing is measured on a loaded host.** Three numbers this session were taken while compiling
  or solving on the same four cores and had to be thrown away.
* **P6's run-to-run spread is ~112,000.** Anything inside that band is noise, not a result.

## 8. What is not settled

* `OGC_SLICEFIX` still ships as a branch defaulting to the old behaviour. That is a gate and it
  does not survive: it becomes unconditional or it comes out.
* P6's 442,280 regression from the slice cap — the untested hypothesis is that the bound should
  be on *cumulative* operator time rather than per call.
* Whether `brk`'s time is better spent as more attempts or longer ones. P3's score is min-of-4
  and each attempt now spends 10–14 s of its ~65 s on the build where it used to spend ~90 s, so
  the saved build is currently being spent as a *longer* search inside the same four attempts.
  `harness/minofn.py` measures the objective-against-ask curve at equal total spend to decide it.
