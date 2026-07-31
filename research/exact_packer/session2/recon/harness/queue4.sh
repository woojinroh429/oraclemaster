#!/bin/bash
# span2, measured where it matters: P3 (the contiguity failure) and P4 (where conw died).
#
# conw removes contact and P4 collapses -- 1,780,253 -> 2,241,556, +25.9% -- because at Z1 88
# with 150 blocks in 3 bays it needs every cell it can press together.  span2 leaves contact
# exactly as it is and only adds a penalty for splitting a row down its middle rather than
# shaving its edge, so nothing is taken away from the instances that depend on tightness.
#
# On P3 the diagnosis is precisely a contiguity failure: bay 0 refuses 23 of its 25 most valuable
# applicants while sitting at 54% area occupancy, so the space is there and simply not in one
# usable piece.  span reads only the floor line and cannot see that; span2 reads every row.
#
# 0.0 first on both, to confirm the new engine reproduces the known baselines before any other
# value is believed -- two sweeps this session measured their own control.
set -u
cd "$(dirname "$0")/.." || exit 1
mkdir -p results
# EXCLUSIVE LOCK.  Three times this session two experiment runners overlapped and both sets of
# numbers had to be thrown away -- most recently because a chained script had exec'd into another
# name, so killing by process name missed it.  Naming is not a mechanism.  Any runner that takes
# this lock is guaranteed to be the only one; a second one waits instead of corrupting both.
exec 9>/tmp/ogc_experiment.lock
flock 9 || { echo "could not take the experiment lock"; exit 1; }
echo "experiment lock held by $$"
EXT="cpython-312-x86_64-linux-gnu.so"
cp "/tmp/ogc_span2.$EXT" "/tmp/stg.$EXT" && mv "/tmp/stg.$EXT" "ogc_fast.$EXT"
echo "span2 engine installed  $(date -u +%H:%M:%S)"
for S in 0.0 1.0 4.0 16.0; do
    OGC_DK=0 python3.12 harness/mkbase.py 0.3 "myalg_sp2_${S/./_}.py" 0 "" 0 1.0 "" 0 "" "" "" "" "" "$S" >/dev/null || exit 1
done
python3.12 - <<'PY'
import myalg_sp2_0_0 as A, myalg_sp2_16_0 as B
assert not A._AXES[1].get("span2"), A._AXES[1]
assert B._AXES[1]["span2"] == 16.0, B._AXES[1]
assert A._AXES[1].get("conw", 1.0) == 1.0, "contact must be left alone"
assert not A._AXES[1].get("dk"), "dk leaked"
print("span2 arms verified: 0 vs 16, contact untouched, dk off")
PY
run () {  # module prob limit tag outfile
    [ -s "results/$5" ] && return
    echo "=== $5  ($4)  $(date -u +%H:%M:%S)"
    python3.12 harness/run1.py "$1" "$2" "$3" "$4" > "results/$5" 2>&1
    tail -1 "results/$5"
    ( cd .. && git add -f "session2/recon/results/$5" >/dev/null 2>&1 )
}
for S in 0.0 1.0 4.0 16.0; do run "myalg_sp2_${S/./_}" 3 240 "span2=$S" "s2_p3_${S}.log"; done
for S in 0.0 4.0;          do run "myalg_sp2_${S/./_}" 4 480 "span2=$S" "s2_p4_${S}.log"; done
echo "queue4done  $(date -u +%H:%M:%S)"
