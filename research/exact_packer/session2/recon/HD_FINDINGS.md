# High-density investigation findings (2026-07-22)

Diagnosis + measured results from the high-density (`_temporal_os >= 0.30`) deep-dive.
All numbers are single-machine, 4-worker, paired A/B unless noted; instances prob_21..40.

## Objective composition (where each instance actually loses)
Per-instance weighted share of the objective (measured at 15s):

| inst | w1 | w2 | w3 | Z1% | Z2% | Z3% | regime |
|------|----|----|----|-----|-----|-----|--------|
| prob_38 | 13333 | 2 | 300 | 92.7 | 0.0 | 7.3 | Z1 (tardiness) |
| prob_27 | 13333 | 2 | 400 | 91.5 | 0.0 | 8.4 | Z1 |
| prob_40 | 667 | 1 | 13 | 92.3 | 0.2 | 7.6 | Z1 |
| prob_39 | 13333 | 4 | 150 | 81.9 | 0.2 | 17.9 | Z1 |
| prob_33 | 6667 | 10 | 150 | 85.9 | 0.0 | 14.1 | Z1 |
| prob_30 | 13333 | 4 | 200 | 70.5 | 0.5 | 29.0 | Z1/Z3 |
| **prob_37** | 3333 | 4 | 600 | 23.9 | 0.3 | **75.8** | **Z3 (preference)** |

- Z2 (load imbalance) is universally negligible in high-density.
- **w3/w1** cleanly separates the Z3-dominated regime: prob_32/34/37 have w3/w1 = 0.16-0.18;
  every other instance <= 0.03.

## Convergence, not ceiling (15s -> 60s headroom)
| inst | Z1 15s->60s | obj 15s->60s |
|------|-------------|--------------|
| prob_38 | 2629 -> 2359 (-10.3%) | -8.8% |
| prob_27 | 1798 -> 1564 (-13.0%) | -10.6% |
| prob_40 | 2751 -> 2380 (-13.5%) | -12.6% |
| prob_33 | 990 -> 958 (-3.2%) | -1.0% (near ceiling) |
| prob_37 | 488 -> 493 (flat) | obj -23% (all Z3: 8609->5983, Z2 5090->1818) |

Root cause for the Z1-heavy instances: **step=1 (fine-grid) construction does not complete
in the ~9s hybrid window at the 15s budget on 250-block instances** (step=1 needs ~21-23s;
step=2 completes in ~7.5s but at worse Z1: prob_38 2654 vs 2494, prob_40 2981 vs 2564).
So at 15s the winner starts from the step=2 basin; more time lets step=1 modes complete.

## SHIPPED fix: preference-lead worker (commit on this branch)
prob_37's Z3 lever is a full-budget `prefaware` step=1 construction (seats each block in its
most-preferred feasible bay). It reaches the 60s Z3 floor in ~9s but the shipped path only ran
it LAST with a ~45% cap, so it never completed at 15s. Fix: gate on `w3/w1 >= 0.10` (pure
weight property) and have hybrid worker i=2 LEAD with full-window prefaware step=1.
- Paired 15s: **prob_37 -23.1%, prob_32 -20.2%**, prob_34 tie, total -2.07%, **0 regressions**
  (off-gate the added block is skipped -> provably the shipped code path). Inert at 60s.

## What did NOT work (measured, do not re-try without a new idea)
- **Python construction speedups** (interval-union rescan replacing the 21M set.add; left-first
  early-exit on bigleft/leftbottom big blocks): both **byte-identical but ~1.0x wall time**.
  cProfile inflated set.add to 63%; real cost is the `placement_feasible` calls on infeasible
  positions, not Python overhead. Reverted.
- **C++ `feasible_scan` (offload the full-grid scan loop)** prototype: byte-identical in
  isolation, **~1.9x on the scan** (pure pybind-round-trip savings; `placement_feasible` itself
  is the residual, and SWEEP-bitmap pruning helps little in dense bays). BUT (a) the 250-block
  targets use the FREE-REGION *windows* rescan path, which this did not accelerate -> only
  **1.05x** end-to-end on prob_38/40; (b) a state-dependent integration identity bug surfaced.
  Reverted. A *windowed* feasible_scan variant is the only way to reach the targets, ceiling
  still ~1.9x -> step=1 ~22s -> ~12s, a thin/fragile fit in the 15s budget.
- Earlier sessions (kept here for the record): NFP contact-optimal placement (removed: 95% of
  construction time, no quality gain -- real-coord vertices make integer edge-contact rare),
  C++ `find_best_placement` for the whole construction (degrades downstream swaps), crane-shadow
  lookahead rollout/beam (prob_27 Z1 1867->42259), TAO descent-shadow scorer (built, did not win).

## Bitmask engine status (measured)
- **RASTER (layer-pair fast-reject in `placement_feasible`): default ON, load-bearing.**
  End-to-end RASTER=0: prob_38 +2772% (28x), prob_40 +5350% (53x); low-density unaffected.
  Its value flows through the engine/`find_best_placement` + feasibility-heavy ALNS paths, NOT
  through `place_custom` (which is RASTER-neutral -- Python-loop bound, identical time on/off).
- **SWEEP (bay-grid forbidden bitmap in `find_best_placement`): default OFF, dormant** -- and
  the winning HD construction (`place_custom`) never calls `find_best_placement` anyway. Enabling
  it gave no speedup in tests.

## Remaining HD Z1 lever (deferred)
The only untapped lever for the Z1-dominated 250-block instances is making step=1 construction
fit 15s. `place_custom` is Python-loop bound and RASTER-neutral, so the path is a *windowed*
C++ scan offload -- modest (~1.9x ceiling), thin 15s margin, and delicate to keep byte-identical.
Not pursued; the shipped Z3 fix is the safe, validated win.

## BRKGA / anytime-metaheuristic vs greedy -- decode-speed investigation (2026-07-23)
Goal: replace the hand-designed direction heuristics (flatbl/bigleft/leftbottom) with a
population search over a contact-maximizing decoder (the "friend's approach" = decoder-based
BRKGA), which the literature says beats greedy on packing IF the decoder is cheap enough for
many generations (anytime convergence).  We already HAVE this: `st3dtcs.st_best` scores each
placement by (tard, pref, load, -contact, y, x) -- no hand-coded direction -- and `_brkga_st`
runs a BRKGA over block orders decoded by it.  It WINS on mid-density (prob_35 -29%) but is
gated off on high-density.

MEASURED (the key numbers):
- **BRKGA does only ~2 generations in 15s** on 150-200 block instances (prob_35/34/28):
  per-decode 5-7s, first decode 6.3s.  A real GA needs hundreds -- so it is not searching,
  just picking the best of ~2 seed orders.  This is the whole reason it loses to greedy.
- Target to make BRKGA viable: decode ~6s -> ~50-70ms (~100x) for 200+ generations.

ATTEMPTS (all reverted -- none shippable):
- **Extreme-Point candidate decoder** (`st_best_ep`, bbox-flush + wall corners instead of the
  full grid): 9-12x faster decode (0.5-0.6s mid-density; prob_38 60s->6.9s and it COMPLETES
  250/250 where the grid times out at 219/250).  BUT single-decode quality is 2.8-3.3x WORSE,
  and BRKGA-EP with 13-21 generations STILL loses to grid-BRKGA's 2 generations (prob_35 EP
  3.66M vs grid 1.13M).
- Coarse grid (step=2/3/4): same story -- 2-6x faster, 2x worse obj.
- Spatial-index fix (CELL 1e6 -> 16; the shipped index is inert, one cell per bay): decode
  UNCHANGED (6.13->6.15s) and obj byte-identical -> neighbor-gathering is NOT the bottleneck.

ROOT BARRIER (why coarsening fails): the first key (tard,pref,load) is POSITION-INDEPENDENT,
so the (x,y) scan only decides the contact tie-break AND feasibility.  In a dense bay a block
fits only at specific cells, so any sparse/coarse candidate set MISSES the feasible position
and pushes the block to a later entry_time -> Z1 spikes.  Quality (low Z1) therefore REQUIRES
a fine step=1 feasibility scan, which is inherently ~14M cheap cell-checks per decode.  There
is no free lunch via candidate reduction; greedy and BRKGA hit the same wall.

REMAINING PATHS (not yet attempted):
1. A free-space / NFP-vertex decoder that answers "earliest-feasible position for this shape"
   sub-linearly (maintained skyline or free-polygon per bay; contact-optimal positions lie on
   NFP boundary vertices -> a finite candidate set).  The principled fast-AND-accurate decoder;
   large, uncertain.
2. Parallelize the BRKGA population across the 4 cores (2 -> ~8 generations).  Modest.
3. Keep greedy for high-density (it wins), BRKGA for mid-density only.  Pragmatic.

## Path-1 (free-space decoder) diagnostic (2026-07-23)
Profiled WHERE the 3DTCS decode's time goes, to target the right structure:
- Contact scoring OFF (STNOC): prob_35 6.26->6.37s, prob_38 77.6->74.4s -> contact is ~4%,
  NOT the cost.
- Spatial-index neighbor count (CELL 1e6->16): decode unchanged, obj byte-identical -> the
  per-cell neighbor loop is NOT the cost.
- Hoisting the neighbor gather to once-per-(bay,entry) instead of per-cell (STHOIST): decode
  unchanged (6.17->6.04s), obj byte-identical -> gather overhead is NOT the cost.
CONCLUSION: the cost is the RAW CELL COUNT of the step=1 full-grid scan itself
(~2880 cells x 8 orients x entry_times x n_blocks ~ 9M cheap iterations on a 200-block
mid-density instance), with irreducibly-small per-cell work.  Coarsening the grid reduces
the count but loses feasibility coverage (Z1 quality).  The ONLY quality-preserving way to
cut it is to STOP scanning cells: represent per-bay free space as a bitmap and find feasible
positions by BIT-PARALLEL 2D erosion (block-layer bitmap slid across the forbidden bitmap,
64 x-positions per word-AND), per crane layer k against forbidden map F[k].  This is a large,
intricate build (per-layer bit-parallel erosion + exact crane j>=k logic, must stay
quality-identical) and, even at ~10-30x, likely only rescues MID-density (150-200 block):
prob_38's 77s decode would still be ~3-8s -> ~2-3 generations, still decode-bound on the
250-block class.  Payoff is therefore bounded to the mid-density regime where BRKGA is
already close; the 250-block P5/P6 class stays greedy-territory.
