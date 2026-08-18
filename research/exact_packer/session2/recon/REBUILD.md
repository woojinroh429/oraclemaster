# Total retrospective, root causes, and a design that does not repeat them

Written after the measurement campaign in `OVERNIGHT_PLAN.md` / `OBJECTIVE_STRUCTURE.md`.
Everything below is a measured number, not an impression.

## 1. What the problem actually is

    minimise  w1*Z1(tardiness) + w2*Z2(bay imbalance) + w3*Z3(preference)

`x`, `y` and `orientation` **appear nowhere in it**. Z1 depends only on entry times; Z2 and
Z3 depend only on the bay assignment. So the decision is a pair of vectors -- *which bay*
and *when* -- and the entire 2D-plus-crane packing exists only as a **feasibility
certificate** for that pair.

That single sentence explains most of what follows.

## 2. What worked, and why

| lever | measured | why it worked |
|---|---|---|
| `prefmid`, dr >= .95 | prob_38 **-2.32%**, prob_27 **-1.56%** | at ultra density the polish cannot move Z1, so a construction change survives to the end |
| `prefbkt` k2+k5, dr [.72,.85) | prob_39 **-2.30%** (Z2 3403->1101, Z3 8081->6421, Z1 +6) | same mechanism; preference routing is really *load balancing* |
| eject-and-insert | prob_29 **-3.75%** at 300s, 2 moves | the only operator that can reallocate a saturated bay |
| C++ engine, `scored_scan`, 3DTCS, BRKGA, cranepack | large throughput gains | engineering, not modelling |

Every modelling win has the *same shape*: **change which bay, at unchanged times, in the
regime where the local search is powerless.** Nothing else has ever converted.

## 3. What failed, grouped by root cause

### RC1 -- the objective ignores geometry, so position heuristics optimise a proxy

The mode zoo, the contact beam, every position rule: all of them score `x`/`y`, which the
objective cannot see. The link to the real objective is weak and measurably non-monotone.

* construction frontier promised **-4% to -44.6%**; paired 300s pipeline delivered
  **-2.30% on one instance and 0 on five**
* prob_37: `prefbkt` wins its worker's construction best-of by **23%** and the worker still
  **loses the instance by 20%**
* prob_35: the workers holding the entire mode zoo **never once lower the shared best**
* the `lane` experiment: construction -0.5% -> pipeline +0.31%

### RC2 -- blocks NEST, so no compact capacity relaxation is valid

This is the one that kills the whole solver family. Tested against real, verified solutions:

| bound | prob_22 | prob_24 | prob_28 | prob_29 | prob_30 | prob_32 | verdict |
|---|---|---|---|---|---|---|---|
| bbox area | 81.8% | **100.8%** | **104.3%** | 96.0% | **107.9%** | 91.4% | **INVALID** |
| tall-item width | 83.2% | **130.0%** | 52.7% | 98.7% | 91.9% | **117.3%** | **INVALID** |
| true polygon area | 53.2% | 54.1% | 65.0% | 55.6% | 68.4% | 50.3% | valid, **50-68% loose** |

Blocks are polygons that interlock, so bounding boxes overlap where the shapes do not.
A real solution therefore *violates* the bbox bound, and the "tall items cannot stack"
argument fails too because an L-shaped block accepts a neighbour into its notch.

Consequences, all previously measured and now explained:
* LBBD on area -- master infeasible at round 0 on prob_30/prob_32; where it runs it claims
  Z3 1930->1538 (p22) and 2105->546 (p28) and **not one is realisable**; 88 and 160
  logic-based Benders cuts move the master but never far enough
* full-instance bbox MIP -- our own solutions violate it on 13-18% of co-present pairs
* rectangle-decomposition MIP -- recovers 33-49%
* only the exact conflict-graph formulation is *correct*, and it is 65-68% dense with
  one round exceeding 15 minutes

**A bound that is neither an upper nor a lower bound cannot support Benders, branch-and-
bound, or column generation.** Every solver attempt so far was built on one.

### RC3 -- all tardiness is congestion

The rigorous bound `sum max(0, rel + pt - due)` is **0 on every instance**. No block is
late because of its own data; lateness is entirely an artefact of queueing for space. So
Z1 cannot be attacked block-by-block -- it is a property of the whole schedule.

### RC4 -- the scarce resource is saturated, so local search cannot reallocate it

On the preference-dominated class the popular bay is full at every instant:
* a misplaced block has **0 feasible cells** in its preferred bay at its own entry time,
  **910-5428** once the bay is empty, and only **0-7 units of slack**
* single-block moves: **0 fixable** on prob_22/29/21/32
* pairwise swaps: of 443 improving candidates on prob_22, **all 443 fail on exactly one
  side** -- the partner's window does not overlap, so evicting it frees nothing
* stake-ordered bay rebuild: seats **42** where the incumbent packs **52**

Yet the prize is real -- reallocating the seats by regret is worth **-22% (p22), -43%
(p29), -56% (p24), -25% (p21)**. The neighbourhood graph is simply disconnected in the
only direction that pays.

### RC5 -- we selected components by proxy, not by the objective

Best-of over *construction* objective throws away the basin that would win after polish;
`_pref_sol` exists precisely because of this and was gated to `w3/w1 >= 0.10`, true for
prob_37 and no other instance. `_z3_improve` scores `w1*Z1 + w3*Z3` and ignores Z2 -- on
prob_24 it trades Z3 877->844 for Z2 716->3216, so the all-or-nothing caller discards the
whole pass including every good move in it.

## 4. The design that follows from RC1-RC5

Constraints the new algorithm must satisfy:

1. search in **(bay, entry time)** space -- the only space the objective can see (RC1)
2. **never use an aggregate capacity bound** -- none is valid (RC2)
3. reason about the schedule **globally**, not block-by-block (RC3)
4. be able to **reallocate a saturated bay wholesale**, not by single moves (RC4)
5. select on the **true objective**, always (RC5)

### Bay-schedule column generation with an exact pricing DP

**Column** = a complete feasible schedule for ONE bay: which blocks it accepts, each with
an entry time, plus a certified packing produced by the existing C++ oracle.

**Master (LP)** = choose one column per bay so that every block is covered exactly once.
A column's cost is exactly `w1*(its tardiness) + w3*(its preference penalty)`; Z2 is the
range of `u_j * load_j`, which is linear given two extra variables. So the master's
objective **is** the true objective -- no proxy (satisfies 1 and 5).

**Pricing (per bay)** = an exact labeling DP over event times. State = (time, resident
set); transitions add a block whose release has passed or drop one whose processing has
finished; a transition is legal only if the C++ oracle certifies the resident set packs.
Reduced cost = column cost minus the duals. **The oracle is exact, so no relaxation
appears anywhere** (satisfies 2). A column is a whole-bay schedule, so pricing naturally
proposes wholesale reallocations (satisfies 4), and the DP reasons over the entire time
axis at once (satisfies 3).

**Integrality** = Ryan-Foster branching on "block b in bay j".

Why this is not the column generation we already tried and killed: those columns were bay
*assignments* with no time dimension, so with 3 bays the master had no freedom and the LP
sat flat for 69 iterations. A column here is a schedule, so the column space is
exponential and the LP has real room. And unlike LBBD, its bound is a true lower bound,
because it is an LP over exact columns rather than over a fictitious capacity.

### Feasibility of the pricing DP -- measured

| | prob_22 | prob_24 | prob_28 | prob_29 | prob_30 | prob_32 |
|---|---|---|---|---|---|---|
| max co-resident in one bay | 16 | 17 | 26 | 22 | 27 | 23 |
| mean co-resident | 9.3 | 8.7 | 12.7 | 9.2 | 13.8 | 11.2 |
| distinct event times | 57 | 63 | 68 | 61 | 62 | 69 |

A bay carries ~9-14 blocks and the time axis has ~60 events. The state space is
exponential in principle; whether dominance prunes it to something workable is the single
open question, and it is the **first thing to test** -- not the last.

### Kill-test before any of it is built

Implement pricing for ONE bay of prob_22 (2 bays, 16 max co-resident) against the C++
oracle, with zero duals, and ask two questions:

* does the DP reproduce or beat the incumbent's own bay schedule?
* does it finish in seconds?

If either answer is no, the design dies there and costs a day, not a week. If both are
yes, the master and branching are standard machinery.

## Speed, measured rather than ported (ideas 6 and 7)

The reference's own notes name the incremental grid cache as "THE lever", pointing at
`load_flat_into` rebuilding the timeline per state per level.  Before porting it, the beam
was instrumented (`OGC_CBPROF=1`, timers around the rebuild and around the position scan):

| instance | total | rebuild | position scan | other |
|---|---|---|---|---|
| prob_30 (n=150) | 48.2s | **0%** | 60% | 40% |
| prob_35 (n=200) | 46.8s | **0%** | **87%** | 13% |
| prob_39 (n=250) | 46.3s | **0%** | 53% | 47% |

**The named bottleneck does not exist in our code.** `load_flat_into` is already cheap;
building the incremental grid would have optimised 0% of the runtime.  Idea 6 is closed --
not because the reference is wrong about its own engine, but because a profile of OUR
engine says something different.  This is the second time a reference claim had to be
re-measured locally before acting on it.

The real cost is the position scan (53-87%).  A first guess that its bitmap pre-filter was
disabled turned out to be wrong as well: `SWEEP` (the env flag, default off) is read at
exactly one call site, and the beam's hot loop does not consult it --

    bool use_sweep = RASTER && maxLb>0 && bayH>0 && bayH<20000;   // no SWEEP term

so the pre-filter is already always on inside the beam.  Measured `SWEEP=0` vs `SWEEP=1`:
identical objective and identical runtime on prob_30/35/39/22.  (The one place it IS
hardcoded off, `feasible_scan_win`, carries its own measurement in the source: net-neutral
on small windowed rescans, with the bitmap build as pure overhead.)

What remains for scan cost is the exact `placement_feasible_tl` call made on every cell the
bitmap cannot clear -- the same function idea 7 (layer-aware contact) touches, so the two
belong in one pass.

