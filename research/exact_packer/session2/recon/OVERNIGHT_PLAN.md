# Overnight plan — the Z1/Z3 needle, low density, and full-set validation

Written to a tracked file so it survives a container reset (`engt/` is gitignored).
Status is updated in place as each phase finishes.

## Where the day ended

Confirmed and committed:

| change | effect |
|---|---|
| mode-zoo refactor -> `_SWEEP` table | none (78 block-for-block checks, scores identical) |
| `prefmid` on `dr >= 0.95` | **prob_38 -2.32%, prob_27 -1.56%** at 300s |
| `prioN` order | none (never selected; measured worse, kept as a record) |

Gate verified: prob_40 (dr .933, outside the band) is byte-identical ON vs OFF
(1,732,271 both).

The one measured win came from *where*, not *when*:

| | what it changed | Z3 | Z1 | result |
|---|---|---|---|---|
| `prefmid` | which bay, same dispatch instant | down | **down** | -2.32% |
| `prioN` | who is dispatched first | down | **up hard** | +2.3 to +12.9% |

`prioN` did lower Z3 (prob_38 8789 -> 7560) but paid 252 tardiness units for it --
9x more than the Z3 gain was worth. Dispatch order is owned by tardiness and cannot be
traded; bay choice can. That is the constraint every overnight idea has to respect.

Why `prefmid` wins is also not what it was designed for: routing toward preferred bays
spreads blocks across bays, so Z2 collapses (prob_38 1506->796, prob_27 514->313) and
the reduced crowding takes Z1 down as well. Preference-aware placement is a
load-balancing device.

## Phase 1 — the Z1/Z3 needle above the gate

`prefmid` is one fixed point on the frontier: `(h, pref, wx, wy, j)`. The frontier
between `bigleft` (preference ignored) and `prefaware` (preference absolute) has not
been swept.

* `prefmid` variants: preference bucketed (`pen // k`) so only large gaps outrank
  position; preference after `wy`; preference weighted rather than lexicographic.
* Sweep the gate: 0.90 / 0.93 / 0.95 / 1.00. prob_40 sits at .933 and currently loses
  by 11% in construction, so the boundary matters.
* Re-check that best-of min() really protects the losing instances inside any wider band.

## Phase 2 — low density (P1-P3), tardiness-for-Z2/Z3 trades

Measured today: on prob_5 every mode reaches Z1 = 0 and the objective is 95-99% Z3, and
on prob_24 the pipeline converges by 200s (200s and 300s give the identical answer), so
the last third of the budget is idle.

* The idle tail is free: the exact set-packing repair took prob_22 779,518 -> 758,017
  (-2.76%) and prob_24 209,165 -> 207,125 (-0.98%), each reproduced 3/3.
* Deliberately admit tardiness where Z1 is 0 and Z3 dominates -- with w1*Z1 at zero,
  a few tardy units can buy a large Z3 cut. Untested.
* LBBD is NOT the tool here: the area relaxation is 89-285x loose and its plan is
  unrealizable (freezing its bay assignment gave Z1 0 -> 51 on prob_5, 0 -> 400 on
  prob_24). Any low-density work goes through the packer, not a relaxation.

## Phase 3 — read the friend's solver again with today's findings

`friend_ref/beamsolver.py` (3024 lines), `native_kernel.py`, `parallel_multi.py`.
Specifically: how it splits budget across bands, whether it has anything like the
preference-stake idea, and how it decides bay assignment.

## Phase 4 — budget allocation

Question raised by the prob_24 finding (pipeline converged at 200s of 300s): which
instance classes finish early, and can that budget move to the classes that do not?
Measure per-class convergence time before changing any split.

## Phase 5 — full prob_1..40 validation

Small instances get short paired runs, the 250-block class gets the long ones. Nothing
ships without this. Note the measured pipeline variance (prob_24 ran 306,871 at 90s and
425,971 at 120s), so single runs per arm cannot decide anything.

## Speed levers already measured (reuse, do not re-derive)

* candidates per (bay, TIME) not per (bay, ORIENT): 1936 -> 482 candidates,
  505,157 -> 19,547 edges, round 17.6s -> 1.06s, same round optimum
* `feasible_scan` step 2: identical final objective on prob_22, 3.3x more rounds
* K cap 60: letting K reach n/2 cut throughput 0.94 -> 0.32 rounds/s
* clique rows only pay once the graph is small (solve 0.57s -> 0.05s at 19.5k edges;
  a full cover costs 127s at 505k)

## Dead ends — do not retry (all measured, see OBJECTIVE_STRUCTURE.md)

LBBD on the area relaxation; full-instance bbox MIP (our own solutions violate it on
13-18% of co-present pairs); rectangle-decomposition MIP (recovers only a third to a
half); column generation (3 bays leaves the master no freedom); lazy conflict rows (65-68%
density, one round exceeded 15 min); ruin & recreate with a greedy recreate (57 rounds,
zero accepted); rollout-based beam scoring (1051 ms per rollout at depth 10% on
prob_38); `chain` selector (0/45); `prioN` dispatch order (1 win in 16).
