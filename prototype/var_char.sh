#!/bin/bash
cd /tmp/claude-0/-home-user-oraclemaster/55043662-747d-5eda-b837-388adc057292/scratchpad/fr2
export ENGINE_DIR=.
OUT=../../tasks/varchar.out; : > $OUT
for P in prob_30 prob_20; do
  for r in 1 2 3 4 5 6; do
    rm -f /dev/shm/psm_* /dev/shm/sem.* 2>/dev/null
    PP=../data/train/$P.json; [ -f "$PP" ] || PP=../data/training_instances/train/$P.json
    taskset -c 0-3 python3.12 ab_full.py $PP 60 >> $OUT 2>&1
  done
  echo "--- $P done ---" >> $OUT
done
echo ALLDONE >> $OUT
