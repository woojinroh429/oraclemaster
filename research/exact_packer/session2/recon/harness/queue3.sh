#!/bin/bash
# The allocator fix, paired, on every instance -- this one is not P3-specific.
#
# Shipped: gain[k] += before - pool[0][0], selected by gain/spent.  The incumbent starts at the
# _safe_sequential floor (2,488,362,823 on P3, against a final answer near 90,000), so the first
# operator to return a real solution banks 2.49e9 and everything after it competes for thousands.
# A millionfold head start that the 15% random pick cannot overcome.  The rate measures which
# operator went first, and that ordering moves with timing -- which is where the spread lives.
#
# RELGAIN credits (before - after)/before instead: the floor jump is worth ~1.0 and a later 1%
# improvement 0.01.  A hundredfold range instead of a millionfold one, so operators stay
# comparable and the budget follows performance rather than arrival order.
#
# Paired on the SAME base (conw=0.25, w3mul=6, dk off) and run on all four instances, because a
# change to how budget is spent affects every one of them.  P3 three times for the spread, the
# others once each to check the score does not move the wrong way.
set -u
cd "$(dirname "$0")/.." || exit 1
mkdir -p results
exec 9>/tmp/ogc_experiment.lock
flock 9 || exit 1
for G in 0 1; do
    env $( [ "$G" = 1 ] && echo OGC_RELGAIN=1 ) OGC_DK=0 \
        python3.12 harness/mkbase.py 0.3 "myalg_rg${G}.py" 0 "" 0 1.0 "" 0 0.25 "" 6 >/dev/null || exit 1
done
python3.12 - <<'PY'
import re
a = open("myalg_rg0.py").read(); b = open("myalg_rg1.py").read()
assert "gain[k] += before - pool[0][0]" in a, "control lost the shipped allocator"
assert "gain[k] += _d / max(1e-9, abs(before))" in b, "treatment did not get relative gain"
assert "gain[k] += before - pool[0][0]" not in b, "treatment still has the absolute credit"
print("arms verified: absolute gain vs relative gain, identical otherwise")
PY
run () {  # module prob limit tag outfile
    [ -s "results/$5" ] && return
    echo "=== $5  ($4)  $(date -u +%H:%M:%S)"
    python3.12 harness/run1.py "$1" "$2" "$3" "$4" > "results/$5" 2>&1
    tail -1 "results/$5"
    ( cd .. && git add -f "session2/recon/results/$5" >/dev/null 2>&1 )
}
for rep in 1 2 3; do
  for G in 0 1; do run "myalg_rg${G}" 3 240 "relgain=$G r$rep" "rg_p3_${G}_r${rep}.log"; done
done
for p in 4 5 6; do
  case $p in 4) L=480;; 5) L=600;; 6) L=900;; esac
  for G in 0 1; do run "myalg_rg${G}" $p $L "relgain=$G" "rg_p${p}_${G}.log"; done
done
echo "queue3done  $(date -u +%H:%M:%S)"
