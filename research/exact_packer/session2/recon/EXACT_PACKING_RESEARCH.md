# Exact geometric packing (Gurobi/MIQCP) for the crane problem — research & verdict

Prompted by Gurobi 13's "What's New" (Circle Packing: v13 2.6360 beats AlphaEvolve
2.63586, v12 only 2.4137).  Question: can Gurobi 13's improved global/nonconvex
solver do our congested bay-window packing exactly and beat the heuristic?

## What the literature says

Two exact-model families for geometric packing:

1. **Separating-hyperplane / distance (MIQCP, nonconvex)** — circles/ellipses/convex
   bodies.  Two convex bodies are disjoint iff a separating hyperplane exists; with
   variable positions the hyperplane test is bilinear -> **nonconvex MIQCP**, exactly
   what Gurobi 13 improved (Nonconvex MIQCP 2.68x; circle packing SOTA).
   - "Out-of-the-Box Global Optimization for Packing Problems" (arXiv 2605.04850) —
     circles-in-squares/ellipses, **regular polygons via Farkas-lemma non-overlap**,
     Platonic solids; off-the-shelf global solvers beat AlphaEvolve heuristics.

2. **NFP-based MILP (discrete orientations)** — irregular polygons.  Non-overlap =
   relative position outside the No-Fit-Polygon; the NFP-complement is decomposed into
   convex regions with mutually-exclusive big-M binaries.  This is a **linear** MIP
   (Gurobi handled it pre-13; v13's *nonconvex* leap does NOT specifically apply).
   - Lastra-Díaz & Ortuño NFP-CM-VS = SOTA exact continuous model, no rotation.
   - **Solvability limit: ~17 convex pieces of simple geometry.**  (arXiv 2206.00032;
     "MIP models ... new symmetry breaking".)

## Why this does NOT fit our problem

Our blocks are **irregular (often non-convex) polygons with 8 discrete orientations**,
so the relevant family is **NFP-MILP**, not the v13-nonconvex circle style.  But:

| factor | ours | exact limit |
|--------|------|-------------|
| convex pieces | 12-block window x (2-4 convex parts each) = **30-60** | **~17** |
| orientations | 8 (binary select) | usually 1 (no rotation) |
| extra constraints | crane j>=k layer-pair non-overlap (per co-present pair, per layer pair) | none |
| time dimension | entry/exit scheduling + tardiness objective | none (pure packing) |
| budget | 15 s grader | minutes for ~17 pieces |

Even a *small* window blows past the ~17-convex-piece exact frontier before the crane
and time constraints are added.  The Gurobi-13 circle-packing headline is misleading
for us: circles are convex with a single simple quadratic per pair; our problem is
non-convex NFP + crane + time + ~100-block bays.

## Cross-check with our own experiments

- Concurrency-relaxation LBBD PoC (gurobi_poc.py): master 526 looked like -60% but
  realizing it under real crane packability gave 2195 > heuristic 1319 — relaxation
  illusory, heuristic near the achievable frontier.
- Tasks #19 (Gurobi exact packing MIP) and #20 (LBBD packing cuts) were tried before
  and did not ship — same scale wall.

## Verdict

**Exact geometric packing (even with Gurobi 13) is not tractable at our scale.**  The
~17-convex-piece exact frontier, our non-convex shapes, 8 orientations, crane j>=k,
time dimension, and 15 s budget together put a useful-size window well out of reach.
The recon+RASTER heuristic is the right answer; it already sits near the achievable
frontier on the congested bays.

**Only marginal exact use:** a <=8-block, convex-ish, fixed-orientation, fixed-schedule
feasibility repack as an occasional operator — likely still too slow for 15 s and, per
the concurrency PoC, unlikely to beat the heuristic.  Not recommended.

## Sources
- arXiv 2605.04850 — Out-of-the-Box Global Optimization for Packing Problems
- arXiv 2206.00032 — A new MIP model for irregular strip packing
- Lastra-Díaz & Ortuño — NFP-CM-VS exact models (irregular strip packing)
- Gurobi 13 release notes; Gurobi Non-Convex Quadratic Optimization; MIQCP FAQ
