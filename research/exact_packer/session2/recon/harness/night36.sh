#!/bin/bash
# Ejection chain across P3/P4/P5, sequentially so each seed build gets all four cores.
#
# The operator is safe everywhere by construction: entry and exit times never change, so Z1 is
# fixed, and the best-of floor means the result is never worse than the seed.  What it can win
# is w2*dZ2 + w3*dZ3, so the first thing each run prints -- the seed's own Z1/Z2/Z3 split -- is
# also the answer to whether it is worth running there at all.
cd "$(dirname "$0")/.." || exit 1
mkdir -p results
for spec in "5 300 500" "4 240 400" "3 120 400"; do
    set -- $spec
    p=$1; seed=$2; ej=$3
    for K in 3 6; do
        out="results/eject_p${p}_k${K}.log"
        [ -s "$out" ] && grep -q "eject obj=" "$out" && continue
        echo "=== P$p K=$K seed=${seed}s eject=${ej}s  $(date -u +%H:%M:%S)"
        python3.12 harness/ejecthid.py "$p" "$seed" "$ej" "$K" > "$out" 2>&1
        tail -3 "$out"
    done
done
