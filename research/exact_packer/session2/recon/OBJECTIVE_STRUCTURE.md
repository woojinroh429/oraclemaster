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

## Where the beam's time actually goes (measured, not guessed)

Two ideas for widening the beam were refuted before this profile, both by measurement:

**Objective-key dedup -- refuted.**  x, y and orientation appear nowhere in the objective, so
states agreeing on (block, bay, entry) score identically forever and deduping them looked
like free width.  The duplicate rate is exactly 0%: capping at one representative per key
left every state standing (prob_38 11478/11478, prob_20 16153/16153, prob_30 6884/6884,
prob_29 12846/12846).  Collisions are structurally impossible -- the dispatch order is
fixed, so distinct parents hand distinct keys to their children by induction, and
best_cell_contact returns at most one position per (bay, entry).

The finding worth keeping is its inverse: the beam does not waste width on geometric
variants, **it never explores geometry at all**.  Every (bay, entry) choice carries exactly
one contact-greedy position, so a state whose packing turns out badly has no sibling with
the same assignment and a different layout.

**Interval-indexed timeline -- refuted.**  Only 10.6% of prob_17's blocks and 26.8% of
prob_20's share time with an average block, so the linear timeline walk looked like 90%
waste.  Keeping every timeline sorted by entry time makes the conflicting blocks a
contiguous run (te.en < ex above, and te.ex <= te.en + max_pt puts te.en > en - max_pt
below), and the beam output was byte-identical -- the window is exact.  It was also not
faster: prob_20 55.0 -> 56.8s, prob_38 25.8 -> 26.4s, prob_29 8.4 -> 8.3s.  The interval
test is two integer comparisons; rejecting 90% of blocks that cheaply already costs
nothing, and the binary searches give back what they save.  Reverted.

**The profile (OGC_CBPROF=1, B=16 K=6):**

  prob_20  n=300  wall 56.2s  scan 55.6s  cells 202M    hard-reject 46.8%  exact 8.97% (17.7s)
  prob_38  n=250  wall 26.9s  scan  8.9s  cells 1060M   hard-reject 98.3%  exact 0.48% ( 4.5s)

They are bottlenecked in different places.

*prob_20 is the scan, and the scan is candidate volume.*  202M cells examined; the bitmap
prefilter is working (exact is down to 9%), but a bay of 40500 cells is swept in full for
every orientation, every state, every level.  The lever is not a faster cell test, it is
fewer cells: this beam ranks by CONTACT, so a position touching nothing can never win, yet
we compute hundreds of millions of them.  Restricting candidates to contact-generating
positions -- corner combinations against placed blocks, plus the walls -- is O(placed)
instead of O(bay area) and is nearly lossless *for this scorer specifically*.

*prob_38 is not the scan.*  8.9s of scanning inside a 26.9s call leaves 18s unaccounted for,
and rebuild measures 0.0, so it is in the rollout or the per-state bookkeeping.  Needs its
own instrumentation before anything is changed.

## Two speedups that were real speedups and still lost

**Contact-candidate positions (OGC_CPOS) -- 14-36x faster, NET WORSE, default off.**

The premise: the beam ranks by contact, so a position touching nothing can never win, and a
full grid sweep evaluates hundreds of millions of them.  Restricting candidates to corner
positions against present blocks and walls made prob_17 61.3s -> 1.7s and prob_20 57.1s ->
4.1s at a pinned width.

Paired at 60s through the whole pipeline it lost 5 of 6:

  prob_17    63651 ->   61394   -3.5%
  prob_29   394344 ->  405753   +2.9%
  prob_38 34654116 -> 35561003  +2.6%
  prob_40  1876603 -> 1951522   +4.0%
  prob_20    96670 ->  110518  +14.3%
  prob_30  1342417 -> 1677835  +25.0%

The premise was wrong, and the scoring function says why: the position score is
`-contact + (iy+od.y1)*pos_lam + ix*pos_lam*0.01 + prefw*pen`, plus a `fut_beta*dwall` wall
term.  A zero-contact position CAN win on the height and wall terms alone -- especially where
the yard is loose, which is exactly prob_20 (density 0.389) and prob_30.  Deleting every
non-touching position deletes real winners.  Speed that costs candidates is not free.

**Area precheck for the retry path (OGC_ARPRE) -- faster, unsound, default off.**

The retry is the dense-instance bottleneck: 58707 calls / 29.6s of 33.3s on prob_38, 54503 /
47.0s of 52.3s on prob_40.  Each failed entry time costs a full multi-bay,
multi-orientation scan, and a bay with less free area than the block's footprint looked
provably hopeless.

Two genuine bugs were found and fixed along the way -- `areas[]` arrives scaled by SC while
`bw*bh` is raw (a tenfold over-count of occupancy), and occupancy has to be the MAX over
instants in the window rather than the sum across it, since [0,10) and [12,22) both meet
[5,15) yet never coexist.  Neither was sufficient.

Auditing it directly (OGC_ARAUDIT=1 skips as usual but runs the scan anyway and counts the
skips that would have succeeded) settles it:

  prob_38  18081 skips, 14333 wrong (79.3%)
  prob_40  21227 skips, 15446 wrong (72.8%)

so prob_38 went 41.1M -> 104.4M and prob_40 1.99M -> 4.38M.  Off until the audit reads zero.

Both are env-gated and default off; with defaults the beam reproduces its previous output
hash exactly (prob_38 8685be467eb9ec59, obj 41064551).

**Still standing: the retry really is the dense bottleneck.**  Nothing above changes that
89% of prob_38's and prob_40's time is one scan repeated tens of thousands of times.  What
is now known is that the shortcut cannot come from discarding candidate positions (CPOS) or
from an area argument (ARPRE) -- it has to come from not repeating work that was already
done, which is a caching question, not a pruning one.

## What contact actually measures

Worth stating because it constrains every scoring idea: `footprint()` flattens ALL layers of
an orientation into a single 2D mask, and `contact_at` counts the perimeter cells of that
mask that touch either a bay wall or an occupied cell of `occ`, itself a flattened union of
the present blocks.  Layers are not distinguished anywhere in the hot path.  A per-layer
variant exists (`contact_at_layered` / `footprintL` / `occL`) but only inside
`scan_bay_contact`, and only under OGC_PERLAYER, which is off.

So the beam treats a one-layer block and a two-layer block as identical neighbours, while
the crane descends vertically and a tall block obstructs everything at its height and above.
That is the gap a layer-aware contact would close.
