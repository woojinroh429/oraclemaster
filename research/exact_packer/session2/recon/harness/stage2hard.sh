#!/bin/bash
# THE FINAL ROUND'S HARD END, which nothing in this project has ever been run on.
#
# Density (demand over capacity) on the final practice set runs to 2.335 where hidden P6 -- the
# instance that has cost the most effort all session -- is 1.137.  The four worst are 300 blocks
# in TWO bays.  Ten of the forty are over capacity against one of forty in the preliminary set.
#
# So this is not a tuning sweep.  It is the first look at whether the algorithm produces good
# feasible solutions on the shape the final round actually contains, with the contact bound back
# on (which the set's composition decided: ten instances shaped like the one it helps, none
# shaped like the one it hurts).
#
# 300 s each: the hidden limits are undisclosed and stated to run "from a few minutes to half an
# hour", so this sits at the low end and is therefore pessimistic rather than flattering.
set -u
cd "$(dirname "$0")/.." || exit 1
mkdir -p results/stage2
exec 8>"/tmp/ogc_$(basename "$0").lock"
flock -n 8 || { echo "another $(basename "$0") is already running"; exit 0; }
exec 9>/tmp/ogc_experiment.lock
flock 9 || exit 1

for p in 36 13 25 26; do
    f="results/stage2/s2_${p}.log"
    [ -s "$f" ] && continue
    BRK_DEBUG=1 timeout 1800 python3.12 harness/run1.py myalgorithm "$p" 300 "stage2 $p" \
        --data data/stage2 > "$f" 2>&1
    tail -1 "$f"
    ( cd ../../.. && git add -f "research/exact_packer/session2/recon/$f" >/dev/null 2>&1 \
      && git commit -q -m "stage2 hard: prob_$p" >/dev/null 2>&1 \
      && git push -q origin claude/repair-plan-model-1ig6it >/dev/null 2>&1 )
done
echo "stage2hard done $(date -u +%H:%M:%S)"
