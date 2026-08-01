#!/bin/bash
# The same bigger-tier question, but with the clock taken off the answer.
#
# bigtier.sh runs the real 240 s budget, so a tier that needs 180 s of build gets one call and
# starves the rest of the loop.  That measures whether the bigger tier is affordable TODAY; it
# cannot measure whether it is worth restructuring for, because at 240 s there is no
# arrangement of the budget under which it breathes.
#
# So run the same configurations at 900 s.  brk's slice and its `hard` both scale with the run,
# so the large tiers get called repeatedly instead of once, which is the condition under which
# brk's gain is known to compound (repeated application from its own output).
#
# What the two queues answer together:
#
#   bigtier   at 240 s   does a bigger tier fit, and what does it cost when it does not
#   this one  at 900 s   does a bigger tier find better repacks when time is not the binding
#                        constraint -- if it does not, today's tier is the ceiling
#
# The 900 s numbers are NOT comparable to the 240 s ones as scores; P3's real limit is 240 s.
# They are comparable to each other, which is the only comparison being made here.
set -u
cd "$(dirname "$0")/.." || exit 1
mkdir -p results
exec 8>"/tmp/ogc_$(basename "$0").lock"
flock -n 8 || { echo "another $(basename "$0") is already running"; exit 0; }
exec 9>/tmp/ogc_experiment.lock
flock 9 || exit 1

for cfg in "4 40 3" "4 40 6" "3 40 3" "2 40 3"; do
    set -- $cfg
    f="results/bt900_${1}_${2}_${3}.log"
    [ -s "$f" ] && continue
    echo "=== 900s step=$1 nout=$2 nent=$3   $(date -u +%H:%M:%S)"
    BRK_STEP=$1 BRK_NOUT=$2 BRK_NENT=$3 timeout 3000 \
        python3.12 harness/run1.py myalg_brk 3 900 "bt900 s$1 n$2 e$3" > "$f" 2>&1
    tail -1 "$f"
    ( cd ../../.. && git add -f "research/exact_packer/session2/recon/$f" >/dev/null 2>&1 \
      && git commit -q -m "bigtier900: step=$1 nout=$2 nent=$3" >/dev/null 2>&1 \
      && git push -q origin claude/repair-plan-model-1ig6it >/dev/null 2>&1 )
done
echo "bigtier2 done $(date -u +%H:%M:%S)"
