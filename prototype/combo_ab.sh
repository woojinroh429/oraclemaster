#!/bin/bash
# baseline (v58: CPPREPAIR=0 SHAKE=0) vs combo (CPPREPAIR=1 SHAKE=1), isolated
# subprocess per solve, shm cleanup between, interleaved so throttling hits both.
cd "$(dirname "$0")"
TL=${TL:-60}
REPEATS=${REPEATS:-2}
for path in "$@"; do
  nm=$(basename "$path" .json)
  for r in $(seq 1 $REPEATS); do
    rm -f /dev/shm/psm_* /dev/shm/sem.* 2>/dev/null
    b=$(CPPREPAIR=0 SHAKE=0 taskset -c 0-3 python3.12 cpprepair_solve.py "$path" "$TL" 2>&1 | tail -1)
    echo "$nm r$r BASE            $b"
    rm -f /dev/shm/psm_* /dev/shm/sem.* 2>/dev/null
    c=$(CPPREPAIR=1 SHAKE=1 taskset -c 0-3 python3.12 cpprepair_solve.py "$path" "$TL" 2>&1 | tail -1)
    echo "$nm r$r CPPREPAIR+SHAKE $c"
  done
done
echo ALLDONE
