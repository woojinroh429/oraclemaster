# Reconstructed / recovered C++ engine sources

All five compiled `.so` modules the algorithm ships now have source here, so the
submission is source-complete.

| module | source | provenance |
|--------|--------|------------|
| ogc_geom  | ogc_geom.cpp  | recovered upload — byte-identical .so + 30k classify_pair hash match |
| ogc_state | ogc_state.cpp | recovered upload — byte-identical .so, deterministic unit-test hash match |
| cranepack | cranepack.cpp | already in repo |
| st3dtcs   | st3dtcs.cpp   | already in repo |
| ogc_fast  | ogc_fast.cpp  | **RECONSTRUCTED** (original source was lost) |

## ogc_fast reconstruction

The shipped `ogc_fast.so` had no surviving source.  Reconstructed on the verified
`ogc_state` geometry (segment-cross + point-in-poly `classify`; c==1 == positive-area
overlap matching shapely `area>0`; c==0 boundary-touch == feasible), plus:

- **find_best_placement** (bid, bay_list, entry_times) -> (ok,bay,orient,x,y,en,ex):
  tardiness-first / earliest-feasible-entry, then bay-preference, then bottom-left.
- **RASTER** conservative integer-cell bitmask (default on): fast disjoint-proof
  pre-filter before the exact `classify` — never under-marks, so feasibility is
  identical to exact (validated: 3000-case hash match RASTER on vs off), ~3x fewer
  classify calls -> ~2.8x more ALNS iterations at the 15s budget.
- env: `RASTER` (default 1), `GRIDDIV` (default 4).

### Full-40 paired validation (reconstructed+RASTER vs shipped ogc_fast, 15s)
- 0 infeasible, 1 minor regression (prob_20 +2.8%), total objective -81%.
- graded high-density wins: prob_30 234->161 (-31%), prob_39 620->490 (-18%),
  prob_31 -9%, prob_26 -9%, prob_25 -13%; prob_38/prob_40 tail-starvation crushed
  (Z1 38961->2629, 60800->2751).

## Build
    INC=$(python3.12 -m pybind11 --includes)
    for m in ogc_fast ogc_geom ogc_state; do
      g++ -O3 -shared -std=c++17 -fPIC $INC $m.cpp -o $m.cpython-312-x86_64-linux-gnu.so
    done

## forbidden-bitmap sweep (SWEEP env, default OFF)

A per-(bay,entry_time) forbidden bay-grid bitmap F[k] per new-layer index (built from
the crane j>=k rule over present blocks) lets a candidate be accepted without the
per-present-block loop when its layers are disjoint from F[k] (exact confirm otherwise
-> feasibility identical, validated SWEEP on==off).  Measured NOT faster in this regime:
rebuilding F each call costs more than it saves at the moderate candidate/present-block
counts here (microbench prob_27: 4.79 -> 4.96 ms/find).  Kept, gated off; the per-pair
RASTER fast-reject is already the sweet spot.  prob_27 is iteration-bound (recon reaches
1564 at 60s vs 1798 at 15s) so it needs a genuine feasibility speedup or an exact
(Gurobi/CP-SAT) bay-window repair, not this sweep.

## Gurobi exact-repair PoC (gurobi_poc.py) — NEGATIVE

Q: can an exact (Gurobi) entry-time re-schedule of the most-congested bay beat the
heuristic?  bay1 of prob_27 (112 blk, heur bay-Z1=1319):
- concurrency-capped (<= heuristic Cmax=34) exact min-tardiness => 526 (looks like -60%).
- BUT realizing that schedule under REAL crane packability (place every block at its
  Gurobi entry or the earliest feasible time after) => 2195, WORSE than the heuristic.
  The concurrency relaxation is illusory: the ~30 blocks that don't crane-pack at the
  relaxed schedule cascade into large delays.
Conclusion: the heuristic (recon reaches 1564 total at 60s) is already near the
achievable frontier under real packability; crane packability does not relax into a
useful MIP (loose => illusory, tight => geometric intractability — same wall task #20
hit).  prob_27's 15s(1796)->60s(1564) gap is packing-search TIME, not schedule
sub-optimality.  Do NOT port this to C++.

## Recovering this working tree after a container reset

Everything is on the branch; only the untracked scaffolding is lost.

    git fetch origin claude/repair-plan-model-1ig6it
    git checkout claude/repair-plan-model-1ig6it
    git reset --hard origin/claude/repair-plan-model-1ig6it
    for m in ogc_fast ogc_geom ogc_state cranepack st3dtcs; do
      g++ -O3 -shared -std=c++17 -fPIC -w $(python3.12 -m pybind11 --includes) \
          $m.cpp -o $m.cpython-312-x86_64-linux-gnu.so
    done

The instances live in the session scratchpad, split across two directories, and the harness
wants them as data/set1 (prob_1..20) and data/train (prob_21..40):

    SP=/tmp/claude-0/-home-user-oraclemaster/*/scratchpad/data
    mkdir -p /tmp/ds
    ln -sfn "$(readlink -f $SP/training_instances/train)" /tmp/ds/set1
    ln -sfn "$(readlink -f $SP/train)" /tmp/ds/train
    ln -sfn /tmp/ds data

Check it took:  python3.12 -c "import myalg_v2,json,utils; ..."  -> prob_3 solves to ~44400.
