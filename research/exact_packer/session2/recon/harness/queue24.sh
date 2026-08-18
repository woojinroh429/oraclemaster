#!/bin/bash
# Take the wall clock out of the decisions, and see what the spread does.
#
# WHY NOT C++.  The spread on P3 is not a speed problem, and that is measured rather than
# assumed: FASTOBJ removed 173 ms of verification from every operator call -- a 1300x speed-up
# on that path -- and moved the answer by 0.26%.  Rewriting the surrounding Python in C++ does
# the same thing, only more so: it runs the same clock-reading decisions faster.  The hot work
# is already C++ (ogc_fast, cranepack, st3dtcs); the Python is a thin chooser.
#
# WHERE THE CLOCK ACTUALLY CHANGES BEHAVIOUR.  Two places.
#
#   1  the beam's adaptive width.  It measures cost per state-level and sizes the width to fit
#      the remaining budget.  brknoise priced the consequence exactly: the same order evaluated
#      six times gives [191128, 165295, 165295, 165295, 165295, 165295] -- the COLD first call
#      over-estimates the cost, narrows the width, and lands 15.6% worse, while the five warm
#      calls agree to the digit.
#   2  the allocator's operator choice, gain[i]/spent[i].  Which operator runs next is decided
#      by measured rate, so a run that is slightly faster takes a different branch, and every
#      branch after it differs too.
#
# OGC_DET pins both -- OGC_ADAPTB=0 / OGC_ADAPTK=0 in the engine, and a fixed rotation in place
# of the rate.  What it CANNOT pin is how many iterations fit in the budget: the loop still ends
# when the clock says so.  So this narrows the dependence, it does not remove it, and claiming
# otherwise would be a claim the design cannot support.
#
# THE WIDTH HAS TO BE CHOSEN.  The engine's own comment records that a predicted width is
# "silently catastrophic" -- the beam returns NOTHING when it overruns, and a fixed constant was
# 4x wrong the moment the beam ran one-core inside the worker pool.  So the arms sweep it: 16, 24
# and 40 against the adaptive control.  If a pinned width overruns, that arm returns the greedy
# floor and says so loudly (obj near 2.49e9), which is the failure this queue is here to find.
#
# Four reps each, interleaved, because the question is about SPREAD.
set -u
cd "$(dirname "$0")/.." || exit 1
mkdir -p results
# ONE INSTANCE PER QUEUE.  The shared experiment lock serialises DIFFERENT queues but not
# a second copy of THIS one -- two copies simply take it in turn and overwrite each
# other's result files, which is exactly what contaminated q23 (see
# results/contaminated/README.txt).
exec 8>"/tmp/ogc_$(basename "$0").lock"
flock -n 8 || { echo "another $(basename "$0") is already running"; exit 0; }
exec 9>/tmp/ogc_experiment.lock
flock 9 || exit 1

for W in 16 24 40; do
    OGC_DK=0 OGC_FASTOBJ=1 OGC_BRK=1 OGC_DET="$W" \
        python3.12 harness/mkbase.py 0.3 "myalg_det${W}.py" 0 "" 0 1.0 "" 0 "" >/dev/null || exit 1
done
OGC_DK=0 OGC_FASTOBJ=1 OGC_BRK=1 \
    python3.12 harness/mkbase.py 0.3 myalg_brk.py 0 "" 0 1.0 "" 0 "" >/dev/null || exit 1
python3.12 -c "
import inspect, myalg_det24 as D, myalg_brk as C
d, c = inspect.getsource(D), inspect.getsource(C)
assert 'OGC_ADAPTB\"] = \"0\"' in d and 'def _beam_width(mul, _det=24.0)' in d
assert 'k = elig[sum(tried) % len(elig)]' in d and 'gain[i] / spent[i]' not in d
assert 'OGC_ADAPTB' not in c and 'gain[i] / spent[i]' in c, 'control must keep both adaptive'
for nm, s in (('det', d), ('ctl', c)):
    assert 'import bayrepack as _brk' in s and 'hard=budget - (time.time() - t0)' in s, nm
print('det arms and adaptive control verified; det24 widths', [D._beam_width(a['Bmul']) for a in D._AXES])" || exit 1

run () {  # module tag outfile
    [ -s "results/$3" ] && return
    echo "=== $3  ($2)  $(date -u +%H:%M:%S)"
    python3.12 harness/run1.py "$1" 3 240 "$2" > "results/$3" 2>&1
    tail -1 "results/$3"
    ( cd ../../.. && git add -f "research/exact_packer/session2/recon/results/$3" >/dev/null 2>&1 \
      && git commit -q -m "result: $2" >/dev/null 2>&1 )
}

for rep in 1 2 3 4; do
    run myalg_brk   "adaptive r$rep" "q24_ad_r${rep}.log"
    run myalg_det16 "det B=16 r$rep" "q24_d16_r${rep}.log"
    run myalg_det24 "det B=24 r$rep" "q24_d24_r${rep}.log"
    run myalg_det40 "det B=40 r$rep" "q24_d40_r${rep}.log"
done
echo "queue24done  $(date -u +%H:%M:%S)"
