#!/bin/bash
# dk=0 vs dk=3, paired.  It has been on by default and never measured.
#
# dk draws an axis's dispatch order from the top-k of what remains on every visit AFTER the
# first.  Its rationale in mkbase.py: the first visit stays byte-identical, later visits would
# otherwise be exact repeats whose budget is discarded, and best-of makes the whole thing
# never-worse.
#
# The never-worse claim is false.  P3 at 240s: dk=0 gives 96,990, dk=3 gives 99,910.
#
# The flaw is in the premise, not the mechanism.  A repeat visit is not necessarily wasted -- it
# can be the same axis given more time and converging further.  Replacing it with a random draw
# spends that budget on a fresh start instead, and best-of keeps the minimum of a worse set.
#
# It was found by accident: myalg_base.py on disk predates dk, every arm generated last night
# carries dk=3, so a "shadow=0.0 control" read 99,910 where the baseline reads 96,990 and about
# 3% of a claimed win was really dk being switched off by the shadow term's reshuffling.
#
# Three instances, both settings, real limits, sequential.  If dk=0 is never worse, it should be
# the default and P3 gains 3% for free.
set -u
cd "$(dirname "$0")/.." || exit 1
mkdir -p results
EXT="cpython-312-x86_64-linux-gnu.so"
# the shadoww engine is a superset (shadoww defaults to 0.0, its branch is dead when unset)
cp "/tmp/ogc_shadw.$EXT" "/tmp/st7.$EXT" && mv "/tmp/st7.$EXT" "ogc_fast.$EXT"
for D in 0 3; do
    OGC_DK=$D python3.12 harness/mkbase.py 0.3 "myalg_dk${D}.py" > /dev/null || exit 1
done
python3.12 - <<'PY'
import myalg_dk0 as A, myalg_dk3 as B
assert A._AXES[1].get("dk", 0) in (0, None), A._AXES[1]
assert B._AXES[1].get("dk") == 3, B._AXES[1]
print("arms verified: dk0 has no draw, dk3 draws from top-3")
PY
declare -A LIM=([3]=240 [4]=480 [5]=600)
for p in 3 4 5; do
  for D in 0 3; do
    out="results/dk_p${p}_${D}.log"
    [ -s "$out" ] && continue
    echo "=== P$p dk=$D (${LIM[$p]}s)  $(date -u +%H:%M:%S)"
    python3.12 harness/run1.py "myalg_dk${D}" "$p" "${LIM[$p]}" "dk=$D" > "$out" 2>&1
    tail -1 "$out"
    ( cd .. && git add -f "session2/recon/$out" >/dev/null 2>&1 )
  done
done
echo "done  $(date -u +%H:%M:%S)"
