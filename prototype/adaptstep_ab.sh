#!/bin/bash
cd /tmp/claude-0/-home-user-oraclemaster/55043662-747d-5eda-b837-388adc057292/scratchpad/fr2
export ENGINE_DIR=.
OUT=../../tasks/adaptstep.out; : > $OUT
for r in 1 2 3 4 5 6; do
  rm -f /dev/shm/psm_* /dev/shm/sem.* 2>/dev/null
  echo -n "BASE  r$r: " >> $OUT; ADAPTSTEP=0 taskset -c 0-3 python3.12 ab_full.py ../data/train/prob_38.json 60 >> $OUT 2>&1
  rm -f /dev/shm/psm_* /dev/shm/sem.* 2>/dev/null
  echo -n "ADAPT r$r: " >> $OUT; ADAPTSTEP=1 taskset -c 0-3 python3.12 ab_full.py ../data/train/prob_38.json 60 >> $OUT 2>&1
done
echo ALLDONE >> $OUT
