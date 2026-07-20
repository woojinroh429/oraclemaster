# Exact crane-packing research (competitor-gap investigation)

## Thesis (PROVEN)
Competitor scores (P3=81000, P4=3.1M) are ~20% below ours -> NOT a physical floor,
our pipeline is at a LOCAL optimum. The gap = PACKING DENSITY in congested bays:
our greedy st_best under-packs the peak clique; exact Gurobi set-packing fits +30-43%
more (bay1 prob_20 peak clique: greedy=7, Gurobi=10). More fit -> fewer spills ->
lower Z3 (P3) and lower Z1 (P4). One lever explains both regimes' 20% gap.

## Math model
- Master (gmaster.py): Gurobi assignment MIP min w2*Z2+w3*Z3, area-relaxed (verified
  == CP-SAT). Area capacity CANNOT represent crane feasibility (oracle.py) -> column
  generation / set-packing needed, not LBBD-over-area (lbbd.py: area LBBD too slow).
- Subproblem (the heart): per-bay crane packing = SET-PACKING over placement columns
  c=(block,x,y,orient,entry). Cover sum_{c in i} y_c <= 1; conflict pairs y_c+y_c'<=1.
  Objective max preference reward / count.
- Congested window = PEAK CLIQUE of the interval graph (congestion.py): blocks present
  at the peak instant. Small (5-18 blocks) -> tractable exact subproblem.

## Conflict rule (j>=k, VALIDATED against grader, conflictgen.py/fastconf.py)
Two placed blocks conflict iff co-present in time AND (order-dependent crane sweep):
  resting j==k always; later-entrant descends (A_k vs B_{j>k}); earlier-exiter ascends.
KEY BUG fixed: use Block.layers_at_pos() (world coords) NOT resolved_layers() (origin).
Fast conflict: numba _g_classify_pair (0.48us, 300x shapely), 0-mismatch prob_20/17.

## Status
- gpack6.py: EXACT pairwise numba + greedy warm-start + MIPFocus=1. WORKS: step6
  clique-17 gives Gurobi=10 vs greedy=7 (+3), but ~14s conf + 4-25s solve = too slow.
- Bottleneck = column count (1404 at step6). Next: FFT-correlation conflict mask
  (raster.py, O(1) lookup, conf 14s->~1s), extreme-point columns, then C++.
- raster.py: rasterize+dilate (false-neg 0, conservative) OR non-dilated + exact-verify.

## Files
gmaster oracle lbbd congestion conflictgen fastconf raster gpack{2..6}
