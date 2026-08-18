#!/bin/bash
# Re-measure on a CLEAN engine, with every arm from the same generator.
#
# Two contaminations invalidated last night's absolute numbers, both found by the user asking
# why a control did not match a baseline:
#
#   1. the rejected anchor term (ganch) was left in ogc_fast.cpp after the rejection, so every
#      sweep since ran on an engine that costs P4 11.3%.  P4's control read 1,981,906 where the
#      real baseline is 1,780,253.  Now reverted.
#   2. myalg_base.py on disk predates dk, while every arm generated last night carries dk=3.  On
#      P3 that is worth ~3%, which was the whole of a claimed shadow win.
#
# The A/B comparisons themselves survive -- both arms of each sweep shared an engine -- but the
# absolute numbers do not, so the levers that looked real have to be re-read against the true
# baseline before anything is adopted.
#
# Every arm here is built by the SAME mkbase.py invocation pattern and differs only in the knob
# under test, and dk is pinned explicitly rather than inherited from a default.
set -u
cd "$(dirname "$0")/.." || exit 1
mkdir -p results
python3.12 - <<'PY'
import myalg_base as M
a = M._AXES[1]
assert "dk" not in a or not a["dk"], "myalg_base carries dk -- baseline is not the historical one: %s" % a
print("baseline verified dk-free:", a)
PY
# arms: dk pinned to 0 everywhere so the only difference is shadow
for SH in 0.0 1.5; do
    OGC_DK=0 python3.12 harness/mkbase.py 0.3 "myalg_n${SH/./_}.py" "$SH" > /dev/null || exit 1
done
python3.12 - <<'PY'
import myalg_n0_0 as A, myalg_n1_5 as B
assert not A._AXES[1].get("shadow"), A._AXES[1]
assert B._AXES[1].get("shadow") == 1.5, B._AXES[1]
assert not A._AXES[1].get("dk") and not B._AXES[1].get("dk"), "dk leaked in"
print("arms verified: shadow 0.0 vs 1.5, dk off in both")
PY
declare -A LIM=([3]=240 [4]=480 [5]=600)
for p in 3 5 4; do
  for SH in 0.0 1.5; do
    out="results/clean_p${p}_sh${SH}.log"
    [ -s "$out" ] && continue
    echo "=== P$p shadow=$SH (${LIM[$p]}s)  $(date -u +%H:%M:%S)"
    python3.12 harness/run1.py "myalg_n${SH/./_}" "$p" "${LIM[$p]}" "clean sh=$SH" > "$out" 2>&1
    tail -1 "$out"
    ( cd .. && git add -f "session2/recon/$out" >/dev/null 2>&1 )
  done
done
echo "done  $(date -u +%H:%M:%S)"
