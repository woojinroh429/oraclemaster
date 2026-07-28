# What the objective actually depends on, and what that rules out

Everything here is measured, with the command that produced it. Written to a tracked
file on purpose: the `engt/` harness directory is gitignored, so notes kept there do
not survive a container reset.

## 1. The objective never mentions geometry

From `utils.py:1403-1430`:

    obj1 = sum max(0, exit_b - due_b),  exit_b = entry_b + pt_b     <- entry times only
    obj2 = floor(max_{j1!=j2} |u_j1*load_j1 - u_j2*load_j2|)        <- bay assignment only
    obj3 = sum (max(pref_b) - pref_b[j_b])                          <- bay assignment only

`x`, `y` and orientation appear nowhere. So the objective is a function of
(bay assignment, entry times) alone, and packing is a **constraint** on which of
those pairs are realizable -- not an objective term.

Consequence: at the moment a block is placed at time `cur`, every *feasible*
candidate gives the same exit time, so **obj1 for that block is identical across all
candidates**. Position can only reach the objective through the future -- whether
later blocks still fit. This is why a placement rule's whole job is keeping the free
region usable, and why search budget spent on x,y is largely wasted.

## 2. obj2's share swings by two orders of magnitude

| instance | w1·Z1 | w2·Z2 | w3·Z3 |
|---|---|---|---|
| prob_38 (ultra) | 31,452,547 (92.1%) | 2,892 (**0.008%**) | 2,703,300 (7.9%) |
| prob_5 (low) | 0 | 15,337 (**32%**) | 32,850 (68%) |

"obj2 is negligible" is true only on the high-density band. On low density it is a
third of the objective.

## 3. bbox non-overlap implies feasibility -- the crane can be eliminated

`ogc_fast.cpp:298-308`:

```cpp
for(const Placed& te : timeline[bay]){
    if(!(en < te.ex && te.en < ex)) continue;                 // no time overlap
    if(!bb_ov(nx0,ny0,nx1,ny1, te.bx0,te.by0,te.bx1,te.by1)) continue;  // no bbox overlap
    if(...) { if(desc_hit(...)) return false; }               // crane checked ONLY here
}
```

The crane test is unreachable unless bounding boxes overlap. So **bbox non-overlap =>
placement feasible**, and a model that forbids bbox overlap among co-present blocks
needs no polygons, no layers, and no crane constraint at all.

This is a *restriction*: it gives up placements where bboxes overlap but the crane
still gets through. Measured across the density range, on our own pipeline solutions:

| instance | co-present same-bay pairs | bbox-overlapping | share |
|---|---|---|---|
| prob_5 (low) | 671 | 88 | 13.1% |
| prob_24 (low) | 925 | 166 | **18.0%** |
| prob_33 (high) | 2703 | 356 | 13.2% |

**This kills the full-instance bbox MIP**, and not for the reason expected. Our own
solutions violate bbox non-overlap on 13-18% of co-present pairs, so they are
*infeasible* for that model -- there is no warm start, and the restricted optimum is
probably worse than what we already produce. The model cannot express what we do.

Confirmed empirically before that was understood: Gurobi on prob_24 (n=100, 4950
pairs, ~35k binaries) took 77s just to build, never accepted the partial warm start,
and after 300s sat at an incumbent of 2.9e7 against our 3.07e5 with a 100% gap.

### Would a finer geometric encoding fix it?  No -- measured

bbox is a crude proxy.  The footprint (union of a block's layers) is the real planar
extent, and footprint non-overlap is *also* a sufficient condition for feasibility --
`desc_hit` compares layer polygons, so disjoint unions cannot touch.  So bbox-overlapping
pairs split in two: pure bbox artefacts (shapes interlocking in the plane), which a
rectangle-decomposition model would recover, and genuine footprint overlap, which no
planar model can express.  `engt/_fpov.py`:

| instance | co-present | bbox-ov | of those, footprint-ov | recoverable by decomposition |
|---|---|---|---|---|
| prob_24 | 925 | 166 (17.9%) | **107 (11.6% of all)** | 59 (35.5% of bbox-ov) |
| prob_5 | 671 | 88 (13.1%) | **59 (8.8%)** | 29 (33.0%) |
| prob_33 | 2703 | 356 (13.2%) | **182 (6.7%)** | 174 (48.9%) |

Only 33-49% of the bbox overlaps are artefacts.  The majority is genuine planar
overlap, legal only because the crane rule permits it (new block's layer k conflicts
only with a resident's layers j >= k).  So decomposing each block into rectangles --
which costs ~9x the binaries per pair, 4 -> 36 -- still leaves 6.7-11.6% of co-present
pairs unrepresentable, our solutions still infeasible, and warm start still impossible.

**This settles the correction above.**  The overlap was earlier described as
"stacking", then flagged as unverified and possibly mostly interlocking.  Measured: it
is majority genuine overlap in the plane, resolved by the layer ordering.

Expressing it properly means modelling the crane rule itself -- for every pair, every
orientation combination, every layer pair with j >= k, a separating-axis disjunction.
Against 4950 pairs that is out of reach.

**Conclusion: the full-instance MIP route is closed, and not because Gurobi is weak.**
Gurobi has no geometry at all -- it takes variables and constraints, so the geometry
encoding is the modeller's job.  The obstacle is that this problem's feasible region
is defined by a *3-D ordering* constraint, and every planar projection of it discards
7-12% of the placements our own solutions use.  Gurobi's place here is the bay-window
subproblem, which `cranepack` already covers.

## 4. The placement-mode "zoo" was one table

`mode` affects nothing in `_smallright_construct` except the score tuple (verified by
enumerating every use of `mode` in the function). The six runtime modes are six rows
of a four-field table -- see `_SWEEP` in `myalgorithm.py`. `bigleft` and `leftbottom`
differ in one column; `flatbl` and `bigleft` differ in one column; `diagonal` and
`coreperi`'s parker branch differ only in the sign of the L1 corner term.

Verified byte-identical block-for-block (bay, orient, x, y, entry, exit) in 48 checks
before the named branches were deleted, and 30 more against the pre-deletion file
afterwards. 339 lines removed, scores unchanged.

## 5. The area relaxation is useless as a bound (kills naive LBBD)

`engt/_lb.py` -- CP-SAT over (bay assignment, entry times) with area capacity only.
This is a valid relaxation, so its optimum lower-bounds the true optimum. obj2 is
dropped (it is >= 0, so omitting it keeps the bound valid).

| instance | area only | + height-class cuts | our solution | gap |
|---|---|---|---|---|
| prob_5 | 450 | 450 | 48,187 | 107x |
| prob_24 | 4,800 | 4,800 | 425,971 | 89x |
| prob_33 | 16,800 | **30,300** | 6,392,540 | 211x |
| prob_38 | 119,997 | 119,997 | 34,158,739 | 285x |

prob_5/24/33 solve to OPTIMAL in 0-25s and claim **Z1 = 0** is achievable. prob_38's
relaxation does not even close in 300s.

Height-class inequalities (at most k blocks of height > H_j/(k+1) can stack, so their
widths behave like a 1-D strip) raise prob_33 by 1.80x and do nothing elsewhere.

**Earlier hypothesis, refuted:** "at ultra density the bays run 100-116% so area
capacity is nearly tight." That utilisation was measured on a solution whose blocks
had already been pushed late. At ideal entry times area is not binding.

## 6. The relaxation's plan is not realizable -- the gap is shape, not area

`engt/_lbreal.py` -- freeze the relaxation's bay assignment (`ext_bay`), let the
packer choose times, score for real. This is the first Benders iteration by hand.

| | prob_5 | prob_24 |
|---|---|---|
| relaxation plan | Z1=0, Z3=3 -> 450 | Z1=0, Z3=16 -> 4,800 |
| same assignment, packed for real | Z1=**51**, Z3=3 -> 860,319 | Z1=**400**, Z3=16 -> 5,366,925 |
| ours (free assignment) | Z1=0, Z3=298 -> 90,690 | Z1=9, Z3=1673 -> 634,232 |

Z3 came out exactly as planned; **Z1 exploded**. Area capacity cannot predict Z1 at
all, so an LBBD master built on it would emit plan after plan that the packer
rejects. This likely explains why `_exact_reassign` measured inert.

**Also refuted:** "we are paying ~70x too much Z3 at low density." On prob_5, cutting
Z3 from 298 to 3 saves 44,250 but costs 51 tardiness units = 816,000. The trade our
algorithm makes is right by 18:1.

## 7. Searching bay assignment with the true objective: sound but subsumed

`engt/_asearch.py`. Round-trip check first: freezing **our own** assignment reproduces
our own objective **exactly** (prob_5: 90,690 / Z1=0 / Z2=6570 / Z3=298), so the
decomposition "search assignment, delegate position to the packer" loses no
information.

Guided SA (moves toward preferred bay for Z3, off the heaviest bay for Z2; random
moves/swaps for diversification -- purely random moves accepted 2 of 50 and improved
nothing):

| | construction (start) | SA | full pipeline |
|---|---|---|---|
| prob_5 | 90,690 | 88,558 (-2.35%) | 48,187 |
| prob_24 | 634,232 | 548,305 (-13.55%) | 306,871 |

Real improvement over the construction, but the pipeline is far ahead -- the
assignment dimension is already worked by `prefaware`, `_exact_reassign` and the z3
post-pass. Evaluation costs 1.1-3.6s per construction, so ~130-150 samples fit in
150s, which is thin for a 100-150 dimensional space.

## 8. Pipeline run-to-run variance is large -- single runs cannot decide A/Bs

Same instance, same code, `engt/_full.py prob_24`:

| budget | objective |
|---|---|
| 120s | 425,971 |
| 90s | **306,871** |

The shorter budget scored 28% better. Four workers take different paths and the
best-of picks whichever got lucky. **Do not judge an A/B on one run per arm.**

## 9. Verdicts on the two experimental scorers (both removed)

* `seal` (layer-profile + contact + preference): 1 win, 4 losses on construction.
  Signature was consistently better Z2/Z3 and worse Z1 -- the fragmentation
  signature of a weighted-sum score with no global sweep direction.
* `lane` (shelf packing): 300s full pipeline -- prob_38 +0.31%, prob_39 and prob_33
  both identical (best-of rejected it). 1 loss, 2 no-ops.

Both deleted along with their parameters. The hand-fitted `_LANETH = 0.021` threshold
went with them.

## Where this leaves things

The binding constraint is packing **shape**, and no model that omits it can predict
Z1 -- that is the single common cause behind items 5, 6 and 7. Item 3 was the one
untried route and it is now closed too, at both resolutions: our own solutions are
infeasible for a bbox-non-overlap model (13-18% of co-present pairs), and refining
bbox to a rectangle decomposition recovers only a third to a half of that, leaving
6.7-11.6% still unrepresentable.  The residue is genuine planar overlap that only the
crane's layer ordering makes legal, so no planar model reaches it. A uniform
row/shelf knapsack version fails separately -- prob_24 per-block minimum heights run
3-15 against bays 20-24 tall, so a uniform row height yields one row per bay and
throws away ~40% of the vertical space.

What is left standing: the packer itself is the only accurate model of Z1 we have.
Any future search should treat it as the evaluator (item 7 showed the round-trip is
exact) rather than trying to replace it with a relaxation.

## 10. The Z1-only framing was my mistake -- multi-term trades do move the objective

Sections 5-7 above report four methods and 689 exact re-optimisations that moved Z1 by
zero, and I concluded the incumbent was effectively optimal.  **That conclusion was
wrong.**  Every one of those runs chose its neighbourhood by tardiness, so it could
only ever trade within Z1.  The objective is w1*Z1 + w2*Z2 + w3*Z3, and the lever is
trading BETWEEN the terms.

Evidence that it was reachable all along: the `lane` construction on prob_38 paid Z1
2359->2436 (+1,026,641) to buy Z3 9011->5948 (-918,900) and lost by only 0.31%.  A
nearly flat frontier, i.e. a better point on it plausibly wins.

`engt/_setpack2.py` keeps the same exact set-packing repair (oracle-built candidates,
oracle-checked conflict graph, all three terms scored exactly) and changes only the
block-selection rule, rotating: tardiest / worst preference penalty / mixed / one bay's
slice / random.  Equal-objective solutions are accepted so the search drifts sideways
instead of re-solving one neighbourhood forever.

K=25, 200s per instance, seeded from a 60s pipeline run:

| instance | w3/w1 | n | bays | seed | best | delta |
|---|---|---|---|---|---|---|
| prob_22 | .0300 | 100 | 2 | 783,112 | **731,677** | **-6.57%** |
| prob_24 | .0225 | 100 | 3 | 320,012 | **312,907** | **-2.22%** |
| prob_27 | .0300 | 150 | 2 | 22,779,813 | = | 0.00% |
| prob_28 | .0225 | 150 | 3 | 1,457,151 | = | 0.00% |
| prob_30 | .0150 | 150 | 2 | 2,402,644 | = | 0.00% |

Selector totals across all five: **tardy 0/71**, z3 2/73, mix 2/73, bayslice 1/73,
random 0/71.  Every improvement came from a selector that did not exist during the 689
failed rounds.

The moves are term trades, exactly as the flat-frontier reading predicts:

    prob_22  [z3]        Z2 3704->3884 (worse), Z3 1930->1860 (better)  -3.51%
             [mix]       Z2 3884->4159 (worse), Z3 1860->1798 (better)  -3.17%
    prob_24  [bayslice]  Z2  716-> 635 (better), Z3 877->864 (better)   -1.35%
             [mix]       Z2  635-> 306 (better), Z3 864->868 (worse)    -0.14%

These are not noise.  The operator is strictly improving: it starts from a fixed seed,
always includes each freed block's incumbent placement as a candidate (so the MIP can
reproduce the incumbent), and accepts only solutions that `check_feasibility` confirms
are both feasible and lower.

Open: the three no-change instances are all n=150 and got 43-80 rounds against 50-123
for n=100, with K fixed at 25 (17% of blocks freed vs 25%).  "No headroom" and "not
enough search" are not yet distinguished.

## The engine can emit grader-infeasible solutions (root cause found)

`myalg_v2` collapsed to the greedy floor on prob_29 and prob_35 -- not from a budget
problem: the beam PLACES all blocks and the result is rejected by the grader, at every beam
width (96/32/8) and with the raster path disabled, so it is neither speed nor the bitmap
filter.

Minimal reproduction, prob_29:

    block  90  bay 0  (40,13) orient 1  [10,22)
    block 143  bay 0  (43,16) orient 5  [5,17)
    our engine: placement_feasible -> True        grader: obstructed

Computing the true geometry with `utils.Block.layers_at_pos()` shows the two blocks DO
intersect, on every layer pair, with area below 1e-6 -- a floating-point sliver.  The block
vertices are not integers (block 90's bbox runs 31.2221 .. 41.5012) while placement offsets
are, so "just touching" is not exact: it leaves ~1e-13 of area.

The two sides then disagree by one inequality:

  * grader (`utils.py`): `if not inter.is_empty and inter.area > 0` -- a sliver is a violation
  * engine (`ogc_fast.cpp:32,44`): `static const double EPS = 1e-9`, and segment crossing
    requires the orientation determinants to EXCEED EPS, so anything within 1e-9 is treated
    as not intersecting

So the engine is tolerant in the direction the grader is strict, and any solution it builds
can be rejected.  It also explains why OUR beam is the thing that trips it: the beam scores
candidates by CONTACT and therefore drives blocks to touch on purpose.  We ask it to pack as
tightly as possible, and tight enough is illegal.

Note the tolerance is two-sided -- it can also miss a real overlap -- but only the
permissive direction produces an infeasible answer.  The safety net (scoring every candidate
with the real `check_feasibility`) catches it, which is why the failure shows up as a fall
back to the floor rather than a bad submission.

## The geometry deadzone (resolved)

prob_29 and prob_35 were returning grader-infeasible packings and falling to the greedy
floor.  Not budget, not the bitmap prefilter -- the exact predicates disagreed with the
grader in the grader's strict direction.

`utils.check_entry` rejects on `inter.area > 0` with no tolerance whatsoever.  Ours carried
`EPS = 1e-9`:

  - `proper_cross` discarded any orientation sign change smaller than EPS
  - `pip` treated a boundary point as OUTSIDE **and returned early**, skipping the ray cast
    entirely, so a vertex grazing one edge concealed that it was interior to the polygon

Why it survived so long: on random placements the old predicate is exactly right.  200k
sampled pairs on prob_29, compared against shapely -- 0 missed overlaps, 0 false ones.  The
beam is not random.  It ranks candidates by CONTACT, so it deliberately seeks the grazing
configurations the deadzone mishandles.

  prob_29 block 90 @(40,13) o1  vs  block 143 @(43,16) o5
    shapely intersection = 9.13e-16 on all four layer pairs
    old predicate        = clear on all four

Fixed by removing the deadzone, not widening it (`TOUCH=0`): any true sign change counts,
a boundary point counts as inside.  Widening only discards legal tight placements --
contacts wrongly called collisions go 1138 -> 1542 (1e-9) -> 1568 (1e-4) over the same 200k
pairs, and prob_29's objective degrades 657828 -> 1104088 at 1e-4.

`ogc_geom.cpp` and `ogc_state.cpp` carried the same pair of defects and are fixed likewise;
`ogc_state` backs the shipped pipeline, so it was exposed too.

Paired against the old engine at 60s, grader-checked, never worse on any instance:

  prob_29  1532023148 -> 394344    Z1 114902 -> 0
  prob_35  2852618295 -> 495286    Z1 213950 -> 22
  prob_39     7292426 -> 7161191   -1.80%
  prob_30     1773592 -> 1477820   -16.68%
  prob_22      724285 -> 714891    -1.30%
  prob_21      515626 -> 480434    -6.83%
  prob_26     6996565 -> 6995093   -0.02%
  prob_24      209540 -> 209540    tied

Every v2 measurement taken before this was with prob_29/prob_35 collapsing.

### Audit of the remaining tolerances

Checked in the same pass, since a tolerance pointing the wrong way is what caused this:

  - **bay containment** -- `placement_feasible` allowed `nx1 > bw[bay] + 1e-6`, while the
    grader rejects any footprint outside the bay on `outside.area > 0`.  Made exact
    (equality still passes, so flush-against-the-wall stays legal).
  - **descent-shadow layer pairing** -- `desc_hit` iterates `k` over new layers and `j` from
    `k` to `n_exist-1`, matching `check_entry`'s j >= k rule exactly.  Correct.
  - **raster prefilter** -- `LayerData::bits` marks a cell when the polygon's interior
    covers the cell centre OR any edge touches the cell, so it is a superset of the true
    footprint and `bmp_overlap` can over-report but never miss.  Sound direction.  Its
    integer-offset assumption holds: `find_best_placement` rounds every candidate with
    `std::round` before use.
