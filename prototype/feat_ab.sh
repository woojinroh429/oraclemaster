#!/bin/bash
cd /tmp/claude-0/-home-user-oraclemaster/55043662-747d-5eda-b837-388adc057292/scratchpad/fr2
export ENGINE_DIR=.
OUT=../../tasks/featab.out; : > $OUT
run() { rm -f /dev/shm/psm_* /dev/shm/sem.* 2>/dev/null; echo -n "$1 " >> $OUT; env $2 taskset -c 0-3 python3.12 ab_full.py $3 60 >> $OUT 2>&1; }
# P4-proxy prob_28, P3-proxy prob_22, plus prob_20 (grader-P3-like low density)
for P in ../data/train/prob_28.json ../data/train/prob_22.json ../data/training_instances/train/prob_20.json; do
  N=$(basename $P .json)
  run "$N v56(D0C0)" "DEOVERFIT=0 CPPPOLISH=0" $P
  run "$N v57(D1C0)" "DEOVERFIT=1 CPPPOLISH=0" $P
  run "$N v58(D1C1)" "DEOVERFIT=1 CPPPOLISH=1" $P
done
echo ALLDONE >> $OUT
