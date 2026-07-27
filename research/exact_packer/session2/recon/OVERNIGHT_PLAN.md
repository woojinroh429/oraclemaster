# Overnight plan — the Z1/Z3 needle, low density, and full-set validation

Written to a tracked file so it survives a container reset (`engt/` is gitignored).
Status is updated in place as each phase finishes.

## Overnight result, in one table

| change | status | measured |
|---|---|---|
| `prefmid` on `dr >= .95` | shipped | prob_38 **-2.32%**, prob_27 **-1.56%** |
| `prefbkt` k2+k5 on `dr [.72,.85)` | shipped, now pipeline-validated | prob_39 **-2.30%**, prob_37/33 identical |
| band widened to `[.55,.85)` | **reverted** | 3 identical, prob_31 +0.18% |
| `trueobj` (greedy `d(obj2)`) | refuted, kept as record | worse on both, Z2 3x worse on prob_26 |
| iterated hint-beam | refuted | fails at n=250 |
| iterated `_z3_improve` | refuted | converged, 0 gain |
| `tri2` dispatch order | built, unwired | -- |
| `OGCWIN` attribution + tracked `harness/` | tooling | -- |

The two shipped gates together move three instances by ~2%, and the band gate is now
validated on **every instance it can reach** (the band contains exactly prob_33/37/39).
That is well short of the 10-20% asked for, and the reason is documented rather than
guessed: the construction frontier offers 4-45%, and outside the top of the band the
polish absorbs all of it. See Phase 1d.

## Where the day ended

Confirmed and committed:

| change | effect |
|---|---|
| mode-zoo refactor -> `_SWEEP` table | none (78 block-for-block checks, scores identical) |
| `prefmid` on `dr >= 0.95` | **prob_38 -2.32%, prob_27 -1.56%** at 300s |
| `prioN` order | none (never selected; measured worse, kept as a record) |

Gate verified on the full A/B, 300s, all four arms:

| instance | dr | OFF | ON | |
|---|---|---|---|---|
| prob_38 | .993 | 34,167,259 | **33,375,985** | **-2.32%** |
| prob_27 | 1.041 | 22,829,843 | **22,474,515** | **-1.56%** |
| prob_40 | .933 | 1,732,271 | 1,732,271 | identical (outside band) |
| prob_33 | .840 | 6,392,540 | 6,392,540 | identical (outside band) |

Both instances outside the band come back byte-identical, so the gate does what it
claims and the change cannot regress anything below dr .95.

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

## Phase 1 — RESULT: the preference tails own the whole mid band, not a slice

Swept the construction frontier (`harness/run.py front`, 240s cap, nine modes) across
every density point available. Best preference tail vs the best of `bigleft`/`coreperi`:

| instance | n | dr | w3/w1 | baseline | best pref tail | |
|---|---|---|---|---|---|---|
| prob_29 | 150 | .415 | .0113 | 2,015,058 | `preflate` 1,172,874 | **-41.8%** |
| prob_36 | 250 | .541 | .0195 | 251,355 | `prefaware` 164,352 | **-34.6%** |
| prob_35 | 200 | .567 | .0113 | 1,765,883 | `prefbkt` k2 978,273 | **-44.6%** |
| prob_31 | 200 | .597 | .0200 | 7,621,517 | `prefbkt` k2 7,295,684 | **-4.3%** |
| prob_26 | 150 | .621 | .0113 | 8,754,437 | `prefbkt` k2 7,893,060 | **-9.8%** |
| prob_37 | 250 | .722 | .1800 | 6,812,264 | `prefbkt` k2 5,234,510 | **-23.2%** |
| prob_39 | 250 | .790 | .0113 | 7,977,140 | `prefbkt` k5 7,581,364 | **-5.0%** |
| prob_33 | 200 | .840 | .0225 | 6,509,360 | `prefbkt` k8 6,677,490 | +2.6% |
| prob_40 | 250 | .933 | .0195 | 1,738,953 | `preflate` 1,799,209 | +3.5% |

The sign flips at dr ~ .80, cleanly. `prefbkt` k2 dominates `preflate`/`prefaware` on
every instance the hybrid worker actually runs on, so only the two `prefbkt` widths are
carried. Three changes shipped from this (commit "prefbkt: widen band"):

* band `[.72,.85)` -> `[.55,.85)`, matching the hybrid worker's own `OGC_LOBEAM` gate --
  below .55 this construction never runs at all
* tails **prepended**, not appended. On the 250-block class construction consumes the
  whole window and an appended tail is simply never reached, which is why the earlier
  narrow gate showed nothing at the pipeline level.
* no single bucket width wins (p35/p31/p26/p37 want k=2, p39 wants k=5), so both run as
  best-of tails; `OGC_PREFBKT` default 5 -> 2

Scale check on how much room is left: prob_35's **construction alone** at k=2 lands
978,273, and the full 300s pipeline from the old baseline reaches 904,355. One
construction is within 8% of everything the pipeline does in five minutes.

## Phase 1b — REFUTED: greedy `d(obj2)` is not a construction signal

The friend ranks candidates by the true objective delta
`w1*tardy + w2*d(obj2) + w3*pref - mu*contact`. At a fixed entry time every candidate
out of one `place_custom` call shares an exit time, so `w1*d(Z1)` is constant and cannot
discriminate; the discriminating part is exactly `w2*d(obj2) + w3*pref`. `prefbkt` sees
the second term and is blind to the first, and the `prefbkt` win demonstrably runs
*through* obj2 (p39 Z2 3655 -> 1224) -- so adding the missing term looked free.

Built it as mode `trueobj`: `pre = pref_pen + (w2/w3)*d(obj2)`, same bucket width, with
`d(obj2)` the exact change in the range of `u_j*load_j`. Measured, step=1, vs `prefbkt`:

| instance | `prefbkt` | `trueobj` | Z2 (bkt -> obj) |
|---|---|---|---|
| prob_26 | 7,893,060 | 8,764,133 | 1,060 -> **3,138** |
| prob_35 | 978,273 | 1,464,289 | 3,541 -> 3,323 |

It loses, and on prob_26 it makes **Z2 itself nearly 3x worse** while explicitly
minimising `d(obj2)` at every step. obj2 is the range of the *final* loads -- an endpoint
statistic, not a path statistic -- so greedily flattening the running range just sends
each block to whichever bay is momentarily lightest, scattering the layout and destroying
the packing coherence, while the final range is set by the totals regardless. The friend
gets away with the term because it sits inside a beam ranked on cumulative exact objective
with an admissible waterfill bound, never a greedy commit.

A first attempt used a *level* term (distance above the least-loaded bay) instead of the
delta; that is worse still and for a second reason -- its magnitude (~200-950 objective
units) is 3-14x the mean preference gap (~65-80), so it drowns Z3 entirely.

`trueobj` stays in `_SWEEP` as the record but is wired into no tail list. Shipped modes
verified byte-identical after the change (prob_26 bigleft/coreperi/prefbkt all exact).

## Phase 1d — WHY the construction win did not reach the pipeline (the real finding)

The widened band was A/B'd at 300s and came back **byte-identical on both instances**:

| instance | dr | OFF | ON |
|---|---|---|---|
| prob_35 | .567 | 904,355 | 904,355 |
| prob_37 | .722 | 3,941,154 | 3,941,154 |

A 44.6% and a 23.2% construction improvement, and the pipeline did not move by one unit.
That is not noise, it is a structural fact, and finding out why took an attribution
probe (`OGCWIN=1`, added in this session: stamps which worker/stage last lowered the
cross-worker best, plus a per-tail trace). Without it a change that improves one worker
by 45% is indistinguishable from a change that does nothing.

**prob_35 (n=200, dr .567)** — the mode zoo is not even in the race:

```
W3 blfull     1,765,883      <- raw bigleft construction
W0 eng_final    907,600      <- the engine worker owns the instance
final           904,355      <- hint-beam post-pass, -0.36%
```

The hybrid workers (W1, W2 -- every `_SWEEP` mode lives there) never lowered the shared
best at all. Best prefbkt construction is 978,273, still above the engine's 907,600, so
improving the zoo here cannot matter however good it gets.

**prob_37 (n=250, dr .722)** — the zoo does win, and the tails all ran:

```
TAIL w1 prefbkt    s2=5,499,123  s1=5,234,510   <- prefbkt WINS W1's construction best-of
TAIL w1 prefbkt5   s2=5,678,597  s1=5,575,736
TAIL w1 diagonal   s2=7,492,373  s1=7,331,012
TAIL w1 leftbottom s2=7,729,569  s1=6,995,762
TAIL w1 bigleft    s2=7,473,356  s1=6,812,264
TAIL w1 coreperi   s2=7,869,471  s1=7,164,209
W3 blfull     6,812,264
W0 eng_final  6,313,129
W2 hybrid     4,158,580        <- W2 takes the instance
final         3,941,154
```

So prefbkt beat bigleft by 23% *inside W1*, W1 polished it, and W1 still lost to W2 by
20%. **Construction objective does not predict polished objective across basins.** W2 won
because it leads with `prefaware` and surfaces it as `_pref_sol`, which gets its own
dedicated polish slice instead of having to win the raw-construction best-of first.

That mechanism already existed -- and it is gated on `w3/w1 >= 0.10`, which is true for
prob_37 and **no other instance in the set**. Everywhere else the preference basin was
built, entered the raw best-of, lost it on Z2, and was never polished on its own. Fixed:
the best preference tail is now routed into `_pref_sol` when nothing else claims it.

Two rules to carry forward:

* **Construction quality only converts where the polish cannot move Z1** -- the ultra
  band, which is exactly where `prefmid` did convert (-2.32% / -1.56%). In the mid band
  the polish takes 7M -> 4.16M and owns the answer.
* **A candidate must be judged after polish, not before.** This is the same trap the
  `lane` experiment fell into (construction -0.5% -> pipeline +0.31%); best-of on a
  construction proxy discards the basin that would have won.

## Phase 1e — the band, settled by paired pipeline A/B at 300s

OFF arm = `OGC_PREFBKT_LO=9` (no preference tail at all), ON = `prefbkt` k2 + k5
prepended. Same process, same budget, arms run back to back.

| instance | dr | OFF | ON | |
|---|---|---|---|---|
| prob_35 | .567 | 904,355 | 904,355 | identical |
| prob_31 | .597 | 4,579,446 | 4,587,645 | **+0.18%** |
| prob_26 | .621 | 7,633,871 | 7,633,871 | identical |
| prob_37 | .722 | 3,941,154 | 3,941,154 | identical |
| prob_39 | .790 | 7,758,932 | **7,580,722** | **-2.30%** |
| prob_33 | .840 | 6,392,540 | 6,392,540 | identical |

One instance converts, and on that one the mechanism is exactly the predicted one:
Z2 3403 -> 1101, Z3 8081 -> 6421, Z1 +6. Everything below .72 gives back nothing and
costs a little budget, so the gate is back at the measured **[.72, .85)** -- which is
where it started the night. What is new is that the band is now pipeline-validated
rather than construction-validated (the shipped k=5 gate had never been A/B'd at all),
and that both bucket widths ride it.

Net honest position on this line: **-2.30% on one instance, never-worse on five.** The
construction frontier promised 4-45% and the pipeline delivered 2.3% on one instance.
The gap between those two numbers is the finding, not the failure.

## Phase 1f — coverage: the band contains exactly three instances

`0.72 <= demand_ratio_phys < 0.85` over prob_1..40 selects **prob_33 (.840), prob_37
(.722), prob_39 (.790)** and nothing else. All three were A/B'd at 300s tonight, so the
shipped change is validated on every instance it can reach -- not sampled, complete.
Everything outside the band is byte-identical by construction (the gate is the only
entry point), which is why a full 40-instance sweep would add no information here.

## Phase 1g — REFUTED: the post-passes have no headroom left

The attribution trace on prob_37 showed the pooled worker best at 4,158,580 and the
returned answer at 3,941,154, a -5.2% step after the worker pool closes -- by far the
largest single-step gain measured anywhere in the pipeline. Two post-passes run there
(the hint-beam, then `_z3_improve`) and neither is iterated, so both were tested:

* **hint-beam fed its own output back**: FAILS outright on prob_37 (250 blocks, 101s,
  returns an incomplete assignment). It completes inside the pipeline only because it
  anchors on the pooled best; re-anchored on its own output it does not finish in budget.
* **`_z3_improve` re-run at 15s**: returns the identical objective on the first extra
  pass. Converged, zero headroom.

So the -5.2% is not repeatable by re-running either pass, and the pipeline's endpoint is
a genuine fixed point of both tools. Note this also means the -5.2% is not yet
attributed -- the `OGCWIN` stamps cover the four cross-worker write sites, so a stage
between the last stamp and the return is unaccounted for. Worth finding, not chased.

## Phase 1c — the Z1/Z3 needle above the gate

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
