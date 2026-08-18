#!/bin/bash
set -u
cd /home/user/oraclemaster/research/exact_packer/session2/recon || exit 1
while pgrep -f 'run1[.]py myalgorithm' >/dev/null 2>&1; do sleep 15; done
echo build > harness/CURRENT
bash build_submission.sh > results/audit/shipgate.log 2>&1
{ echo "== gate verify (60s -> expect n=3) =="
  timeout 200 env OGC_WSTAT=1 /usr/bin/python3.12 harness/run1.py myalgorithm 1 60 "[gate.v60]" --data data/stage2 2>&1 | grep -E 'WSTAT round=0|^P1'
  echo "== gate verify (480s path, 20s probe -> expect n=3; 300s -> expect n=4) =="
  timeout 120 env OGC_WSTAT=1 /usr/bin/python3.12 -c "
import sys,os,json; sys.path.insert(0,'.')
import myalgorithm
p=json.load(open('data/stage2/prob_1.json'))
import multiprocessing as mp
print('cpu', os.cpu_count())
" 2>&1 | tail -2
} >> results/audit/shipgate.log 2>&1
echo SHIPGATEDONE >> results/audit/shipgate.log
echo idle > harness/CURRENT
