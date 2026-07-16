#!/bin/bash
cd /tmp/claude-0/-home-user-oraclemaster/55043662-747d-5eda-b837-388adc057292/scratchpad/fr2
export ENGINE_DIR=.
OUT=../../tasks/cppgate.out; : > $OUT
run() { rm -f /dev/shm/psm_* /dev/shm/sem.* 2>/dev/null; echo -n "$1 " >> $OUT; env $2 taskset -c 0-3 python3.12 ab_full.py $3 60 >> $OUT 2>&1; }
for P in ../data/train/prob_22.json ../data/training_instances/train/prob_20.json ../data/train/prob_28.json; do
  N=$(basename $P .json)
  run "$N v58(gate0)" "CPPGATE=0" $P    # v58 = CPPPOLISH always on
  run "$N FIX(gate1)" "CPPGATE=1" $P    # new = CPPPOLISH gated off on low-density
done
echo ALLDONE >> $OUT
