# Friend `submission_v20.2` — methodology analysis (living doc)

Built up over the overnight deep-dive. Goal: understand WHY the friend wins P1–P5
(esp. P5 high-density, Z1-dominated) and port the winning levers into our pipeline.

## Environment note
Friend code needs `scipy` (`scipy.signal.fftconvolve` in gridsolver/beamsolver) +
`numba` (0.66.0, present) + `ogc_core.so` (loads fine here). Installed scipy 1.18.0
with `--break-system-packages`. After that it runs (prob_30 @40s → obj 2,566,846
feasible; the fallback path returns ~8e8, so a huge obj means an import/spawn failure).

`ogc_core.so` exports: `bay_pass, build_grid_test, ct_rc_l_test, init_ctx, krn_reset,
krn_stat, register_geo, score_bay, select_dense, select_words`.

## Architecture (from myalgorithm.py — CONFIRMED)
**Gate-free, single engine, NO instance classification.** All 4 workers race on
EVERY instance; best FINAL objective wins ("adaptation by observation, not
classification"). This is the opposite of our density-gated routing.

### The 4 workers (order, rank, pos_div, beam_mult, schedule, pos_lam, tight, beta, esh)
- **W1** `edd_big, v0, 1.0×width, flat, pos_lam .01, TIGHT=0, beta 1.5` — conservative generalist, auto beam width
- **W2** `lst, v0, 1.0×, flat, .01, TIGHT=0, beta 1.5` — (small-width peak per docs)
- **W3** `edd_at, gh, 0.5×?, flat, pos_lam .5, TIGHT=1, beta 0.5` — **TIGHT raster, "congested winner"** ← P5 lever
- **W4** `lst, v0, 0.6×, flat, .5, TIGHT=1, beta 1.5` — TIGHT, mid width, skyline-mix

Diversification axes: ORDER (largest measured effect: lst −50% on prob_21) ×
TIGHT/conservative raster × future-value beta × in-worker width ladder. Deterministic
(no random noise — reproducible). `esh` (E2 layer-accounting) runs as ladder rung 3 on
leftover time (instance-dependent sign, zero-sum as a slot).

### Beam construction (solve_beam)
Beam over ALL bays × orientations × integer positions. numba raster + fused sweep.
Candidates ranked by TRUE objective delta. Beam kept diverse by per-parent quota,
pruned by an admissible obj2 bound. `auto_beam_width(n, area, budget)`. [details ← Agent A]

### Improvement LADDER (deterministic, fixed slices — key design)
`[justify 2s, repair 25s, lns k14 45s, rebalance 4s, rung_g 44s, lns k20 45s, rebalance 4s]`
then EXTRA cycle `[justify, lns k20, rebalance]`. Fixed slice sizes + fixed operator order
+ iteration-cooled LNS → trajectory independent of wall-clock jitter (they explicitly fixed
an oscillation bug from adaptive slices). Time decides only HOW FAR down the ladder.
- **justify** = FBI forward-backward (monotone Z1 reducer, seconds-cheap via pairwise
  time-invariant collision matrix)
- **repair** = time_repair (cheap monotone)
- **lns** = time_repair mode=lns, single + batch-ruin, adaptive operator weights,
  disagree-guided ruin (blocks where the 4 lenses DISAGREE on bay = the hard decisions)
- **rung_g** = guided reconstruction: rebuild incumbent as ONE beam path (entry-ascending
  order is reconstructible), SOFT bay anchor, incumbent pruning → searches a neighbourhood
  K~20 LNS provably can't reach. Fired once when the loop stalls.
- **rebalance** = bay-flip rebalance

### Time budget waterfall
- `< 25s`: sequential (spawn+JIT fixed cost too big)
- canary `spawn_works()` before betting budget on parallel; else sequential full budget
- factors: construct then improve to `timelimit*0.96 - 2s`; final validate at `*0.995`
- Safety: spawn canary, tail guard, always-feasible O(n) fallback, final exact validation

### S=2 (OGC_S=2) — CONFIRMED: raster super-sampling, NOT sub-unit placement [Agent C]
`S = raster cells per grid unit` (gridsolver.py:44). Positions emitted are ALWAYS
integers (positions sampled only at integer bay coords, gridsolver.py:479-489), so the
grader's `int(round(x))` is a **no-op** — S=2 gives ZERO sub-unit placement freedom.
What S=2 DOES buy: a **conservative raster that hugs the true polygon ~2× tighter** than
S=1, so legal tight-nesting integer slots that a coarse raster would spuriously reject are
recovered → **feasible-position recall gain → denser legal integer packs**. Cost O(S²).
Our earlier "S=2 dead-end" conclusion was right about placement; we MISSED the recall
benefit — a tighter feasibility raster finds more legal integer positions.

## gridsolver.py — crane feasibility & density levers [Agent C, CONFIRMED]
### TIGHT raster (W3's "congested winner")
- conservative (`TIGHT=0`): `m = (areas > 1e-9)` — any touched cell blocked (superset →
  raster-feasible ⟹ polygon-feasible, commit without re-verify)
- **TIGHT (`TIGHT=1`)**: `m = (areas >= 0.5*cell_area)` (majority rule) — masks stop
  inflating → admits TIGHTER candidates → denser pack → more on-time → **lower Z1**. But
  raster-feasible no longer ⟹ polygon-feasible, so it MUST exact-verify the committed
  position (beamsolver side).
### Directional crane-shadow masks (the density edge over naive BL)
- Per orientation: `masks_ge[k]` = union of layers ≥ k (descent shadow), `masks_le[k]` =
  union of layers ≤ k. Prefix-unions → O(1) per placed block, vectorised over all positions.
- For each already-placed block P, stamp ONLY `masks_ge` OR `masks_le` (not full footprint)
  depending on the TEMPORAL ordering of P's vs our crane events (entry/exit windows +
  same-time EXIT-before-ENTRY / block_id tie-break) — replicates grader's asymmetric j≥k
  rule EXACTLY. Lets a block legally sit directly above/around a shorter neighbour's upper
  layers whenever the descent path is clear — nesting a footprint-blocking BL packer forbids.
- Feasibility per (bay,entry,orient): `fftconvolve` (whole-grid, one FFT evaluates ALL
  integer positions per layer) in gridsolver; native_kernel replaces it with a fused numba
  word-AND sweep (Morton bit-packing, OGC_MORTON default ON).
### Spatial scoring (gridsolver, tie-break under the real-objective gscore)
- `gscore = w1*tardiness + w2*new_obj2 + w3*(s_max - pref[bay])` — myopic grader replica,
  picks bay+position by TRUE objective delta; spatial score only tie-breaks.
- spatial: `score_contact_wall` (contact perimeter + wall bonus, exact S-cell wall test),
  `score_contact_time` (**contact weighted by remaining co-presence time → prefer nesting
  against LONG-STAYING blocks**), profile rings for true adjacency. ← time-weighted contact
  is a lever we don't have.

## Head-to-head (friend @300s on OUR train set) — [filling in from _friendsweep.log]
(pending)

## PORT LIST (prioritized) — [synthesized after agent reports]
(pending)
