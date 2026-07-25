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

### Beam construction (solve_beam) [Agent A, CONFIRMED — full detail]
Beam over ALL bays × orientations × integer positions. numba raster + fused sweep.
**Design philosophy (the key discipline): "contact chooses the POSITION; the true-objective
delta chooses the CANDIDATE."** Contact scaled to `mu=1e-3*min(w1,w3)` so it NEVER outvotes
a real tardiness/pref difference.
- **State**: per-bay placed list, loads, `cum_hard = w1*Στardy + w3*Σprefpen` (EXACT hard
  obj), `cum_contact` (search guide only), order-independent `canon` XOR hash (dedup layouts).
- **Candidate score (the ranking)**: `d_rank = w1*tardy + w2*Δobj2 + w3*(s_max-pref[bay])
  - mu*contact + wait_w*(entry-e_min)`. Candidates ranked by this TRUE objective delta.
- **Position score (Phase 2, picks ONE pos per bay/orient)**: `sc = -contact +
  (pys+top_h)*pos_lam + pxs*pos_lam*0.01` (+ fut_beta term). `pos_lam` 0.01=contact-first,
  0.5=low-skyline.
- **Beam rank(st)** = `cum_hard + w2*h(loads) - mu*cum_contact`, h = admissible waterfill obj2.
- **Final pick** = min over beam of EXACT `true_obj = cum_hard + w2*floor(obj2_now)`.
- **Pruning**: per-parent diversity quota (`max(2,(B+1)//2)` children/parent), canonical dedup,
  admissible-obj2 + suffix-Z3 incumbent prune (cut child if `cum_hard + w2*(h-1) + z3_lb ≥
  incumbent`), obj3-pref guard (never cut the zero-penalty option).
- **auto_beam_width** = `2*tl*0.8 / (n*est_state_cost)`, clamp [2,192]; TIGHT costs 1.5×.
- **schedule**: flat (congested — width to the end) / decay / hybrid. **order** (biggest
  diversification axis): edd/lst/edd_big/edd_at/edd_tri/dispatch.

### ⚠️ KEY REALIZATION (ours vs theirs)
Our engine is ALREADY EXACT on feasibility (`placement_feasible` scans integer cells with
exact layer-overlap), so we do NOT have the friend's "ghost gap" problem → **TIGHT raster is
likely NOT our gap.** Our P5 gap is more likely: (1) the beam RANKING by TRUE objective delta
(Z1-aware) with a WIDE beam (up to 192) enabled by admissible pruning — vs our contact-first
beam; (2) the refined improvement ladder (FBI justify + ALNS + rung_G). This reframes the
port priority below.

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

## Orchestration & convergence [Agent B, CONFIRMED]
- **4 independent ProcessPoolExecutor workers, NO shared incumbent** (no Manager dict, no
  best-sharing). Only the FINAL objective compared. Cross-worker reuse = losers' block→bay
  maps for disagree-ruin. (Ours DOES share via Manager dict — a difference.)
- Budget waterfall: workers 0.68–0.78·T, collection cap 0.78–0.88·T, improve loop 0.96·T−2,
  validation 0.995·T. `[T5]` rung widths from NOMINAL budget shares (PHI table) so engine
  speed changes only HOW MANY rungs fire, never the trajectory (deterministic).
- **CONVERGENCE EARLY-STOP: they have NONE.** Construction = single forward beam sweep to
  completion (only a predictive TIME guard collapses beam→width 1 if predicted to overrun).
  Improvement = fixed pass LADDER + infinitely-cycled EXTRA block, bounded ONLY by the time
  deadline. No patience/plateau/stall counter — they deliberately burn the whole budget.
  ⟹ the user's "수렴하면 중지" must be BUILT by us. Reusable idea: patience counter
  (passes_since_improvement) + their monotone `min()`/`_adopt` accept-gate so stopping is
  always safe (never returns a worse solution).
- Speed levers (why their beam is affordable): (1) fused feasibility+contact sweep,
  integer-lattice only, early-exit, contact only for feasible; (2) crane clearance pre-baked
  into blocked grid via masks_ge/masks_le cumulative unions → hot kernel is plain layerwise
  AND; (3) aggressive caching (grid_cache + content-signature reuse + memoized exact-verify).

## Head-to-head (friend @300s on OUR train set) — _friendsweep.log
| inst | dr | FRIEND @300s | OURS @300s | winner |
|------|----|--------------|------------|--------|
FULL SWEEP (friend v20.2 @300s vs OUR SHIPPED config @300s), sorted by demand_ratio:
| inst | dr | FRIEND | OURS(shipped) | winner | margin |
|------|----|--------|---------------|--------|--------|
| prob_24 | .425 | **169,898** | 225,553 | FRIEND | ours +32.8% ❌ |
| prob_21 | .526 | **519,005** | 611,817 | FRIEND | ours +17.9% ❌ |
| prob_28 | .597 | 1,266,171 | **778,632** | OURS | −38.5% ✅ |
| prob_26 | .621 | 8,606,180 | **7,941,486** | OURS | −7.7% ✅ |
| prob_32 | .636 | **2,641,271** | 3,709,814 | FRIEND | ours +40.4% ❌ |
| prob_23 | .673 | 1,697,371 | **1,617,107** | OURS | −4.7% ✅ |
| prob_30 | .687 | 2,057,796 | **1,543,326** | OURS | −25.0% ✅ |
| prob_39 | .790 | 8,981,604 | **7,764,022** | OURS | −13.6% ✅ |
| prob_33 | .840 | 8,172,633 | **6,392,540** | OURS | −21.8% ✅ |
| prob_40 | .933 | 2,082,353 | **1,733,334** | OURS | −16.7% ✅ |
| prob_38 | .993 | 38,440,927 | **34,167,259** | OURS | −11.1% ✅ |
| prob_27 | 1.041 | 25,239,681 | **22,779,813** | OURS | −9.7% ✅ |

**TALLY: OURS wins 9/12, FRIEND wins 3/12 (prob_24, prob_21, prob_32).**
- We WIN all high/ultra density decisively (−10 to −22%) — our engine's strength.
- We LOSE on two LOW-density (prob_24 dr.425 +33%, prob_21 dr.526 +18%) and one MID
  (prob_32 dr.636 +40%). The friend's beam beats our contact beam there: better Z3 routing +
  competitive Z1. This is our real gap.
- Win/loss is NOT cleanly dr-separated (we win prob_28 dr.597, they win prob_32 dr.636) → a
  density router can't capture both; only a true best-of can.

### STRATEGY: best-of ensemble (proven never-worse, closes all 3 losses)
Since we HAVE the friend's working engine, running BOTH and taking min per instance
GUARANTEES ≤ friend AND ≤ ours everywhere. Data-proven ensemble result: match/beat friend on
ALL 12 (prob_24→169,898, prob_21→519,005, prob_32→2,641,271 from friend; the other 9 from us).
Open question = BUDGET: two 4-worker engines can't both get full 300s on 4 cores. Validating
whether a 2+2 core split (each engine 2 workers @300s) or a time-split retains the wins.
ALT path = port the friend's true-objective-delta beam ranking into our contact beam (make the
low/mid win OURS). Both under evaluation.

### BUDGET FINDING (ensemble @140s test) — decisive
- **Ours @140s** still beats friend@300 on ALL high/ultra (prob_33 7.51M, prob_38 34.17M,
  prob_27 22.78M) → **our engine converges by ~140s on the instances we win** (huge slack).
- **Friend @140s**: prob_24 → 312,169 (WORSE than our 225,553!), prob_21 → 560,601 (still
  beats us), prob_32 → 2,720,574 (still beats us). → friend needs near-full budget for prob_24.
- ⟹ On a **4-core / 300s** budget, a best-of ensemble must split time, which makes OUR 9 wins
  WORSE (ours@130s < ours@300s) while only partly capturing the friend's 3. **Net-negative at
  300s.** The ensemble only pays off at **~500s total** (the friend's real budget), where
  ours converges in ~160s (wins safe) and the freed ~340s funds a near-full friend run.
- **Two clean paths forward:**
  1. **500s ensemble** (if the user will run the friend's ~500s budget): our engine +
     convergence-early-stop frees time → run friend on the remainder → best-of → match/beat
     friend on ALL 12. Requires the budget decision.
  2. **Port low/mid win into our engine** (budget-robust, any T): the 3 losses are Z3-routing
     dominated (prob_24 friend Z3=482 vs ours 681; prob_32 ours Z3 much higher). Port the
     friend's true-objective-delta candidate ranking (w1·tardy + w3·pref − mu·contact) so our
     contact beam routes to preferred bays like theirs. Fixes low/mid at any budget, stays ours.

⚠️ prob_33 (our high-density P5 proxy) — OURS already beats the friend by 22%. Either the
real hidden P5 instance differs from our train proxies, or the user's tested submission was an
OLDER version than our current one. The full sweep will show WHERE we actually lose → the real
port target. Do NOT over-invest in porting before the head-to-head map is complete.

## PORT LIST (prioritized, Z1-dominated) [synthesized]
1. **FBI justify_time** ⭐ (LOW difficulty, monotone Z1 reducer, works on ANY solution):
   right pass slides on-time blocks as late as due−proc (obj-invariant, opens early space),
   left pass pulls late blocks as early as release into that space (monotone Z1↓). O(bay)
   boolean moves via a precomputed time-invariant pairwise collision matrix. Cheap → run every
   loop. We have `_shift_forward` (left-ish); need the right-open + round-trip. Clean win.
2. **True-objective-delta beam ranking + admissible obj2 waterfill pruning** (MED): rank
   candidates by `w1*tardy + w2*Δobj2 + w3*pref − mu*contact`, prune children whose provable
   LB ≥ incumbent → run a WIDER beam same budget. Our contact beam is contact-first; this is
   Z1-aware. The real structural P5 lever IF the sweep shows we lose high-density.
3. **ALNS refinements** (MED): disagree-guided ruin (ruin blocks the workers disagree on),
   SA-lite acceptance (`temp=0.002*cur*frac_left`), adaptive op weights `+1/+0.1/×0.9` [0.2,8].
4. **rung_G guided reconstruction** (MED): rebuild incumbent as ONE beam path (entry order) +
   soft bay anchor (`anchor_w=0.5*w3`) + incumbent pruning → escapes LNS-unreachable basins.
5. **fut_beta wall-push** (VERY LOW): `+fut_beta*(proc/mean_proc)*dwall` pushes long-residency
   blocks to walls. We already have this term in best_cell_contact.

## Convergence early-stop DESIGN (to build — user asked)
Add to our improvement loop / worker coordinator: track `best_cost` over time; a
`no_gain_seconds` / `passes_since_improvement` patience counter. When patience exceeded AND
the instance is NOT high-density (needs full budget), return early. Keep the monotone best-of
so early return is always safe. Only-stop-when-truly-converged; high-density always runs full.

## ✅ WIDE-BEAM RESULT (validated @300s, serial==openmp, committed)
Root-caused the 3 losses to Z3-routing under a too-narrow beam: our `best_cell_contact`
ALREADY uses the friend's true-delta ranking (`w1·tardy + w3·pen − mu·contact`), but the beam
width was capped at B=32 while the width formula wants ~90 at n=100 (friend runs up to 192).
Raising the cap 32→96 for small instances (n≤120), measured serial == openmp (identical):
| inst | friend | old B32 | **new B96** | vs friend |
|------|--------|---------|-------------|-----------|
| prob_21 | 519,005 | 611,817 | **521,912** | TIE (+0.6%) — was +18% |
| prob_24 | 169,898 | 223,378 | **209,165** | +23% (was +31%) |
| prob_32 | 2,641,271 | **2,336,940** | 2,336,940 | **WIN −11.5%** (head-to-head's 3.71M was a stale build) |
- prob_32 was NEVER a real loss — the current code beats the friend there; my head-to-head used
  a stale pre-restart number. Corrected standing vs friend: **11 win/tie, 1 loss (prob_24)**.
- Committed gated to n≤120 (byte-identical for n>120; both small runs COMPLETE in ~237s, no
  time cost). OGC_BMAX overrides. Remaining gap = prob_24 (low-density Z3 routing, +23%).
