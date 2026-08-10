#!/bin/bash
# Does OGC_PARROUND actually fire, pick the winning parity, and produce distinct wids?
# Read from WSTAT: with ROUNDS=3 there must be three round lines, and on prob_1 rounds 1 and 2
# must be 3+1 on the parity round 0 preferred.  A no-op or a crash here would make every p1draws
# cell measure nothing, which is why this runs before the sweep and not after it.
set -u
cd /home/user/oraclemaster/research/exact_packer/session2/recon || exit 1
L=results/audit/smoke_parround.log
: > $L
for arm in "OGC_ROUNDS=3 OGC_PARROUND=3" "OGC_ROUNDS=3 OGC_PARROUND=0"; do
  echo "# [$arm]" >> $L
  env $arm OGC_WSTAT=1 timeout 300 /usr/bin/python3.12 harness/run1.py myalgorithm 1 120 \
      "[smoke]" --data data/stage2 >> $L 2>&1 || echo "CRASH rc=$?" >> $L
done
echo SMOKEDONE >> $L
