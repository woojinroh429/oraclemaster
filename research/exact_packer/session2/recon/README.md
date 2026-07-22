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
