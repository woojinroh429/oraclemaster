#!/bin/bash
# Make 82,180 reproduce.  On P3 a small objective difference moves the ranking a lot, so a run
# that sometimes returns 82,180 and sometimes 91,670 is worth less than one that always returns
# 84,000.
#
# WHERE THE SPREAD COMES FROM, measured.  Every random draw in the worker loop is seeded, so two
# runs of one arm differ only in TIMING -- which operator gets which slice, decided by wall clock
# through gain/spent.  harness/brknoise.py then found a specific timing effect with a large
# amplitude: the SAME dispatch order, evaluated six times with nothing changed, gives
#
#     edd        [191128, 165295, 165295, 165295, 165295, 165295]
#     lst        [148650, 148650, 148650, 160775, 157315, 166500]
#     big_first  [188260, 188260, 188260, 166605, 188260, 188260]
#     defer_big  [164970 x 6]
#
# The first call is 15.6% worse than the five that follow it.  The beam sizes its width from
# MEASURED cost, so a cold first call over-estimates what a level costs, narrows the width, and
# returns a worse solution; every warm call afterwards agrees to the digit.
#
# In a 240 s run each worker's OPENING beam is that cold call, and what it returns becomes the
# pool everything else builds on.  A bad opening is not one bad slice, it is a bad starting point
# for the remaining 230 seconds.
#
# So throw one short beam away first.  Cost: 6 s of a 199 s worker budget, 3%.  If the mechanism
# is right the opening solution stops being a coin flip; if it is wrong this is 3% of the budget
# for nothing and the arm loses, which is also worth knowing.
#
# Six pairs, interleaved in one queue -- more than the usual three, because the question is about
# the SPREAD and three samples cannot answer it.  This session has already retracted four claims
# made on two or three.
set -u
cd "$(dirname "$0")/.." || exit 1
mkdir -p results
exec 9>/tmp/ogc_experiment.lock
flock 9 || exit 1

OGC_DK=0 OGC_FASTOBJ=1 OGC_BRK=1 OGC_WARMUP=6 \
    python3.12 harness/mkbase.py 0.3 myalg_brkw.py 0 "" 0 1.0 "" 0 "" >/dev/null || exit 1
OGC_DK=0 OGC_FASTOBJ=1 OGC_BRK=1 \
    python3.12 harness/mkbase.py 0.3 myalg_brk.py  0 "" 0 1.0 "" 0 "" >/dev/null || exit 1
python3.12 -c "
import inspect, myalg_brkw as A, myalg_brk as B
a, b = inspect.getsource(A), inspect.getsource(B)
assert 'WARM-UP: see OGC_WARMUP above' in a and '_beam_once(prob_info, 6.0,' in a
assert 'WARM-UP' not in b, 'control must not carry the warm-up'
for nm, s in (('warm', a), ('ctl', b)):
    assert 'import bayrepack as _brk' in s and 'hard=budget - (time.time() - t0)' in s, nm
print('warm-up arm and its control verified')" || exit 1

run () {  # module tag outfile
    [ -s "results/$3" ] && return
    echo "=== $3  ($2)  $(date -u +%H:%M:%S)"
    python3.12 harness/run1.py "$1" 3 240 "$2" > "results/$3" 2>&1
    tail -1 "results/$3"
    ( cd ../../.. && git add -f "research/exact_packer/session2/recon/results/$3" >/dev/null 2>&1 \
      && git commit -q -m "result: $2" >/dev/null 2>&1 )
}

for rep in 1 2 3 4 5 6; do
    run myalg_brkw "warmup r$rep" "q23_warm_r${rep}.log"
    run myalg_brk  "nowarm r$rep" "q23_cold_r${rep}.log"
done
echo "queue23done  $(date -u +%H:%M:%S)"
