#!/bin/bash
# Does the ask fix hold the budget?  P6 first, then P3, then P4.
#
# THE BUG.  A call costs BUILD + ASK and only the ask is ours to set, but the old form took a
# MINIMUM against a term computed from the slice:
#
#     _ask = max(_MINASK, min(_left / _RATIO, room - predicted_build))
#
# The first term is unrelated to room, so it passed through whenever it was smaller.  Traced on
# P6, against a 172 s slice:
#
#     build 112.2 s + ask 171.8 s = 286.3 s
#     build 213.3 s + ask 171.8 s = 386.0 s
#
# One call spending 2.2x its share.  The run finished in 1014 s against a 900 s budget -- real,
# though not the 3.7x I first reported: that measurement had three of my own profiling jobs
# competing for the same four cores, and the number was mine, not the algorithm's.
#
# THE FIX.  Subtract instead of taking a minimum, and cap on the SLICE:
#
#     cap  = min(slice, hard * 0.85)
#     ask  = cap - predicted_build
#
# so build + search <= cap holds structurally.  The tier chooser uses the same cap, or it picks
# a tier the ask can no longer pay for.  hard stays as an upper bound -- a call late in the run
# must not overrun the run -- but the allocator's share is what stops one operator eating the
# others' budget.
#
# ORDER.  P6 first because it is the one that broke, and because budget failure outranks score:
# an answer past the limit is not scored at all.  Then P3, which is what brk is FOR and where
# the tighter ask may cost the 80,795.  Then P4, which was passing at 455 s and must stay there.
#
# WHAT WOULD MAKE brk NOT WORTH SHIPPING ON P6 REGARDLESS: it already scores worse there.
#
#     brk on    30,471,333  @ 1014 s
#     brk off   30,297,335  @  899 s      (yesterday's calibration, clean)
#
# More time and a worse answer.  If the fix only brings it inside the budget without fixing
# that, the honest conclusion is that brk should decline on P6 entirely.
set -u
cd "$(dirname "$0")/.." || exit 1
mkdir -p results
exec 8>"/tmp/ogc_$(basename "$0").lock"
flock -n 8 || { echo "another $(basename "$0") is already running"; exit 0; }
exec 9>/tmp/ogc_experiment.lock
flock 9 || exit 1

python3.12 -c "
import inspect, bayrepack as R
r = inspect.getsource(R)
assert '_cap = min(SL,' in r and '_ask = max(_MINASK, _cap -' in r, 'ask fix not wired'
assert '_room = min(SL,' in r, 'tier chooser still uses the run-level room'
print('ask fix verified: cap is the slice, ask is a subtraction')" || exit 1

run () {  # prob secs tag outfile
    [ -s "results/$4" ] && return
    echo "=== $4 ($3) $(date -u +%H:%M:%S)"
    BRK_DEBUG=1 timeout $(( $2 * 5 + 300 )) \
        python3.12 harness/run1.py myalg_brk "$1" "$2" "$3" > "results/$4" 2>&1
    tail -1 "results/$4"
    ( cd ../../.. && git add -f "research/exact_packer/session2/recon/results/$4" >/dev/null 2>&1 \
      && git commit -q -m "askfix: $3" >/dev/null 2>&1 \
      && git push -q origin claude/repair-plan-model-1ig6it >/dev/null 2>&1 )
}

run 6 900 "askfix P6" "af_p6.log"
run 3 240 "askfix P3" "af_p3_r1.log"
run 3 240 "askfix P3 r2" "af_p3_r2.log"
run 4 480 "askfix P4" "af_p4.log"
echo "askfix done $(date -u +%H:%M:%S)"
