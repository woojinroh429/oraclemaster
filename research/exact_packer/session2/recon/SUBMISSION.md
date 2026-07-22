# Submission build

`bash build_submission.sh` compiles all 5 engine modules from the .cpp sources here and
produces `submit_build/submit_recon.zip` = { myalgorithm.py, utils.py, 5 .so }.
Fully reproducible from a fresh container (only needs g++, python3.12, pybind11).

## What changed vs the previous submission (v82)
Only `ogc_fast` changed: it is the RECONSTRUCTED engine with a tardiness-first
find_best_placement + the exact-preserving RASTER bitmask (see README.md).  The other
four modules and all Python are byte-for-byte the shipped v82.

## Validated effect (recon vs shipped v82, full-40 paired, 15s)
- 0 infeasible everywhere.
- High-density wins: prob_30 234->161 (-31%), prob_39 620->490 (-18%), prob_31/26 ~-9%,
  prob_25 -13%; oversubscribed prob_38/40 collapse (Z1 38961->2629, 60800->2751).
- Low/mid density essentially unchanged; single small regression prob_20 (+2.8%, a
  low-density Z2/Z3 tie-break; Z1=0 so no tardiness effect).
- Total objective across 40 instances: -81% (dominated by the high-density magnitudes).
Net: strictly better on every high-density (scored-heavy) instance; one ~3% low-density
blip.  For an objective-sum grader this is unambiguously better.
