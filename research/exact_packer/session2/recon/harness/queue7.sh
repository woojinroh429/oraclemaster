#!/bin/bash
# conw as a per-WORKER regime, after the per-axis version failed.
#
# WHAT queue5 SETTLED.  Spreading conw across the six axes gave 96,235 twice against a 96,990
# base, while the same knob held at 0.0 everywhere reaches 87,560.  Two of those six axes
# carried conw=0.0, so if one flat beam were enough to produce 87,560, best-of over the true
# objective would have returned it.  It did not.
#
# So conw=0.0 is not a candidate score that pays off on a good beam.  It is a REGIME the whole
# search has to stay in: a beam builds a flat layout, _grow breeds from the pool and repairs
# it, and any axis carrying conw=1.0 pulls that layout back toward contact packing.  Axes
# rotate within a worker by design -- they are the one unit that cannot hold a regime steady.
#
# queue5 also killed the idea that conw and span2 are two levers.  Both flatten; held together
# at conw=0.0 span2=1.0 the result was 103,795, worse than either alone.  One mechanism.
#
# Workers hold a regime.  Each keeps its own pool for the whole budget and they meet only at
# the closing best-of, so worker 0 can spend 240s flat while worker 2 packs tight and the
# instance keeps whichever won -- no threshold, no density test.  Three splits, because the
# question is not only whether it works but how much of the pool the losing regime may have:
#
#   half   2 flat / 2 tight -- the honest 50/50, and what a saturated instance would pay
#   three  3 flat / 1 tight -- nearest the P3 optimum while keeping one worker on contact
#   four   0.0 / 0.25 / 1.0 / 4.0 -- every regime once, no majority anywhere
#
# If `half` reaches the 87,560 class then a P4 arm is worth running, because P4 keeps two full
# workers packing tight and pays only the two it spent flat.  If none of them do, the regime
# needs the whole pool and this direction cannot be made safe.
set -u
cd "$(dirname "$0")/.." || exit 1
mkdir -p results
exec 9>/tmp/ogc_experiment.lock
flock 9 || exit 1

run () {  # module tag outfile
    [ -s "results/$3" ] && return
    echo "=== $3  ($2)  $(date -u +%H:%M:%S)"
    python3.12 harness/run1.py "$1" 3 240 "$2" > "results/$3" 2>&1
    tail -1 "results/$3"
    ( cd ../../.. && git add -f "research/exact_packer/session2/recon/results/$3" >/dev/null 2>&1 \
      && git commit -q -m "result: $2" >/dev/null 2>&1 )
}

for S in "half:0.0,0.0,1.0,1.0" "three:0.0,0.0,0.0,1.0" "four:0.0,0.25,1.0,4.0"; do
    nm="${S%%:*}"; vs="${S##*:}"
    OGC_DK=0 OGC_WDIV="conw:$vs" \
        python3.12 harness/mkbase.py 0.3 "myalg_wd${nm}.py" 0 "" 0 1.0 "" 0 "" >/dev/null || exit 1
done
python3.12 -c "
import re
for nm, want in (('half','[0.0, 0.0, 1.0, 1.0]'), ('three','[0.0, 0.0, 0.0, 1.0]'),
                 ('four','[0.0, 0.25, 1.0, 4.0]')):
    s = open('myalg_wd%s.py' % nm).read()
    m = re.search(r\"_wov = \[\('conw', (\[[^]]*\])\)\]\", s)
    assert m and m.group(1) == want, (nm, m and m.group(1))
    assert s.count('for k, v in _wov') == 1
print('per-worker conw arms verified: half / three / four')" || exit 1

for rep in 1 2 3; do
    for nm in half three four; do
        run "myalg_wd${nm}" "wconw=$nm r$rep" "q7_${nm}_r${rep}.log"
    done
done
echo "queue7done  $(date -u +%H:%M:%S)"
