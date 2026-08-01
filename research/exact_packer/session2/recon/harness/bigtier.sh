#!/bin/bash
# Does a BIGGER tier buy a better repack on P3?
#
# WHAT "BIGGER" CAN EVEN MEAN HERE.  A tier is (step, nout, nent): the position grid, how many
# outsiders to offer, and how many entry times per block.  On P3 the nout dimension is already
# saturated -- the trace shows 15 to 17 profitable outsiders, so tier 0's nout=40 and tier 1's
# nout=20 both take every one of them, and both use step=4.  The ONLY thing separating those
# two tiers on this instance is nent, 3 against 2.  Raising nout further does nothing at all.
#
# So the live dimensions are step and nent.  Predicted build from the measured 6.4e-8 s/col^2,
# against the ~95 s of room a 240 s run leaves brk:
#
#     (4,40,3)  today    1.00x columns    56.5 s   fits
#     (4,40,6)           1.50x           ~127 s    does not
#     (3,40,3)           1.78x           ~180 s    does not
#
# That is arithmetic and it only says they do not fit at brk's CURRENT share of the run.  If a
# bigger tier finds materially better repacks, restructuring that share becomes a real option;
# if it does not, today's tier is the ceiling and that is worth knowing too.
#
# MEASURED INSIDE A REAL RUN, deliberately.  The offline version of this test started from the
# saved converged incumbent and every tier returned None -- that point is settled, so it cannot
# tell tiers apart.  Same trap wishprobe fell into this morning.  Forced knobs are read at
# runtime, so the comparison belongs where brk is called from states it has not settled.
#
# Runs that overrun 240 s answer the cost question by themselves; the objective answers whether
# the extra search was worth it.
set -u
cd "$(dirname "$0")/.." || exit 1
mkdir -p results
exec 8>"/tmp/ogc_$(basename "$0").lock"
flock -n 8 || { echo "another $(basename "$0") is already running"; exit 0; }
exec 9>/tmp/ogc_experiment.lock
flock 9 || exit 1

for cfg in "4 40 3" "4 40 6" "3 40 3"; do
    set -- $cfg
    f="results/bt_${1}_${2}_${3}.log"
    [ -s "$f" ] && continue
    echo "=== step=$1 nout=$2 nent=$3   $(date -u +%H:%M:%S)"
    BRK_STEP=$1 BRK_NOUT=$2 BRK_NENT=$3 timeout 1500 \
        python3.12 harness/run1.py myalg_brk 3 240 "bt s$1 n$2 e$3" > "$f" 2>&1
    tail -1 "$f"
    ( cd ../../.. && git add -f "research/exact_packer/session2/recon/$f" >/dev/null 2>&1 \
      && git commit -q -m "bigtier: step=$1 nout=$2 nent=$3" >/dev/null 2>&1 \
      && git push -q origin claude/repair-plan-model-1ig6it >/dev/null 2>&1 )
done
echo "bigtier done $(date -u +%H:%M:%S)"
