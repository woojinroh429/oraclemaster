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
