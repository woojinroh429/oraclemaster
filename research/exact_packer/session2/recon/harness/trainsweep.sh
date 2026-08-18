#!/bin/bash
# THE FULL TRAINING SET, which the technical report requires and which has never been run on the
# current algorithm.  The report's results section asks for Z1, Z2 and Z3 on the training data;
# until now the only numbers on disk were the six final instances.
#
# 60 s per instance, uniform.  A uniform budget is the only comparable one -- the hidden limits
# vary per instance and are not disclosed, so any per-instance budget here would be invented.
# 60 s is also what the earlier training sweeps in this project used, so the numbers line up with
# the history rather than starting a new scale.
#
# Sets of ten, committed as each set finishes, so an interrupted run leaves usable results
# instead of nothing.
set -u
cd "$(dirname "$0")/.." || exit 1
mkdir -p results/train
exec 8>"/tmp/ogc_$(basename "$0").lock"
flock -n 8 || { echo "another $(basename "$0") is already running"; exit 0; }
exec 9>/tmp/ogc_experiment.lock
flock 9 || exit 1

SECS=${SECS:-60}
for p in $(seq 1 40); do
    f="results/train/t${p}.log"
    [ -s "$f" ] && continue
    timeout $(( SECS * 5 + 180 )) python3.12 harness/run1.py myalgorithm "$p" "$SECS" "train $p" \
        --data data/train > "$f" 2>&1
    printf "%s\n" "$(tail -1 "$f")"
    if [ $(( p % 10 )) -eq 0 ]; then
        ( cd ../../.. && git add -f research/exact_packer/session2/recon/results/train >/dev/null 2>&1 \
          && git commit -q -m "training sweep: through prob_$p" >/dev/null 2>&1 \
          && git push -q origin claude/repair-plan-model-1ig6it >/dev/null 2>&1 )
    fi
done
( cd ../../.. && git add -f research/exact_packer/session2/recon/results/train >/dev/null 2>&1 \
  && git commit -q -m "training sweep: all 40" >/dev/null 2>&1 \
  && git push -q origin claude/repair-plan-model-1ig6it >/dev/null 2>&1 )
echo "trainsweep done $(date -u +%H:%M:%S)"
