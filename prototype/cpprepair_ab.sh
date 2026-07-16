#!/bin/bash
# A/B full-solve: CPPREPAIR OFF (v58 baseline) vs ON, isolated subprocess per
# solve, shm cleanup between, interleaved OFF/ON so throttling hits both equally.
cd "$(dirname "$0")"
D=/tmp/claude-0/-home-user-oraclemaster/55043662-747d-5eda-b837-388adc057292/scratchpad/data
TL=${TL:-60}
REPEATS=${REPEATS:-2}
for spec in "$@"; do
  path="$spec"
  nm=$(basename "$path" .json)
  for r in $(seq 1 $REPEATS); do
    for mode in 0 1; do
      rm -f /dev/shm/psm_* /dev/shm/sem.* 2>/dev/null
      out=$(CPPREPAIR=$mode taskset -c 0-3 python3.12 cpprepair_solve.py "$path" "$TL" 2>&1 | tail -1)
      lbl=$([ "$mode" = "1" ] && echo "ON " || echo "OFF")
      echo "$nm r$r CPPREPAIR=$lbl  $out"
    done
  done
done
echo ALLDONE
