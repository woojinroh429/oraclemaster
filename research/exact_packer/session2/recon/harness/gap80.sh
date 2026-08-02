#!/bin/bash
# WHY DOES FORCING (4,40,6) BEAT CHOOSING IT?
#
# Under the new code the chooser takes tier 0 on every call, and the costs come out the same:
#
#     forced   build 58.1-61.5s   ask 39.8s        total  98.2-101.5s   -> 80,795
#     r1       build 58.7-61.8s   ask 35.1-38.6s   total  95.9- 99.2s   -> 85,640
#     r2       build 59.9-63.5s   ask 31.6-35.7s   total  94.9- 97.4s   -> 87,990
#
# Same tier, same column counts (30,3xx real in both), same wall time to within 5%.  So the
# 5,000 is NOT the tier and NOT the budget, and 80,795 is not a lucky tail: it is identical to
# the digit across bt_4_40_6, n6_p3_r2 and gb_p3_forced -- three runs, three different days of
# code.  Something else differs.
#
# THE ONE ASYMMETRY LEFT IN THE CODE.  _forced sets _tier = -1, so the forced path SKIPS the
# whole `if _tier >= 0` branch and keeps the old ask:
#
#     forced      _ask = max(1.0, _left / _RATIO)              -> 39.8 s, flat
#     chooser     _ask = max(_MINASK, _cap - predicted_build)  -> 31.6-38.6 s
#
# and the subtraction is now REDUNDANT: total_s already bounds build + search using cranepack's
# own measured build, so subtracting a PREDICTED build from the ask charges for the build twice.
# When the prediction is pessimistic that is search time thrown away for nothing.
#
# ARM A (nosub) removes the double charge -- ask = cap, total_s still enforces the deadline.
# If the gap is the double charge, A lands near 80,795 and the deadline still holds.
# ARM B is the current chooser, run again, because two samples that differ by 2,350 are not
# enough to call 85,640 the typical value.
# ARM C is forced, twice more: if it is 80,795 a fourth and fifth time, it is deterministic and
# the gap is a real defect rather than variance.
#
# Interleaved so that any drift in machine state hits all three arms alike.
set -u
cd "$(dirname "$0")/.." || exit 1
mkdir -p results
exec 8>"/tmp/ogc_$(basename "$0").lock"
flock -n 8 || { echo "another $(basename "$0") is already running"; exit 0; }
exec 9>/tmp/ogc_experiment.lock
flock 9 || exit 1

# Arm A needs its own module: BRK_NOSUB=1 makes the ask the cap itself.
python3.12 - <<'EOF' || exit 1
import re
s = open("bayrepack.py").read()
old = "            _ask = max(_MINASK, _cap - _PAIRRATE[0] * _NCOL * _NCOL)"
new = ("            _ask = max(_MINASK, _cap - _PAIRRATE[0] * _NCOL * _NCOL)\n"
       "            if os.environ.get(\"BRK_NOSUB\") == \"1\":\n"
       "                # total_s already bounds build + search on the MEASURED build, so\n"
       "                # subtracting a PREDICTED build here charges for it twice.\n"
       "                _ask = max(_MINASK, _cap)")
if new not in s:
    assert old in s, "ask line not found"
    open("bayrepack.py", "w").write(s.replace(old, new, 1))
    print("BRK_NOSUB added")
else:
    print("BRK_NOSUB already present")
EOF

run () {  # tag outfile [env...]
    [ -s "results/$2" ] && return
    echo "=== $2 ($1) $(date -u +%H:%M:%S)"
    env CRANEPACK_NOBITS=1 "${@:3}" BRK_DEBUG=1 timeout 1500 \
        python3.12 harness/run1.py myalg_brk 3 240 "$1" > "results/$2" 2>&1
    tail -1 "results/$2"
    ( cd ../../.. && git add -f "research/exact_packer/session2/recon/results/$2" >/dev/null 2>&1 \
      && git commit -q -m "result: $1" >/dev/null 2>&1 \
      && git push -q origin claude/repair-plan-model-1ig6it >/dev/null 2>&1 )
}

for rep in 1 2; do
    run "gap A nosub r$rep"  "gap_a_r${rep}.log" BRK_NOSUB=1
    run "gap B chooser r$rep" "gap_b_r${rep}.log"
    run "gap C forced r$rep"  "gap_c_r${rep}.log" BRK_STEP=4 BRK_NOUT=40 BRK_NENT=6
done
echo "gap80 done $(date -u +%H:%M:%S)"
