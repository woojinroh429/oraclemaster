#!/bin/bash
# THE ONE PART-A CELL THAT NOISE DOES NOT EXPLAIN.
#
# rfnoise ran HEAD's module three times on each non-firing instance.  Four came back with the
# edited build's answer inside HEAD's own spread:
#
#     P21   1,014,768 / 1,087,112 / 1,076,570   spread 7.13%   edit 1,087,112  inside
#     P4    2,813,285 / 2,681,096 / 2,681,096   spread 4.93%   edit 2,713,254  inside
#     P2   59,860,379 /59,860,379 /60,754,481   spread 1.49%   edit 60,602,795 inside
#     P9    5,847,680 / 5,755,343 / 5,817,115   spread 1.60%   edit 5,755,343  inside
#     P34     250,125 /  249,163 /  249,163     spread 0.39%   edit   205,205  OUTSIDE, -17.6%
#
# P34's control is the tightest of the five and the edit sits far outside it, in a solution with a
# different structure -- Z1 0 against Z1 4.
#
# THE EDIT CANNOT BE THE CAUSE AND THAT IS WHY THIS NEEDS SETTLING RATHER THAN WAVING AWAY.  P34's
# peak_util is 0.984600786705, below the gate's 1.00, so `if _lo <= _pu <= _thr` is false and the
# changed literal is never read.  Both modules execute the same bytecode with the same environment.
# If a real difference existed here, the fault would be in my model of the run rather than in the
# gate -- so the asymmetry has to be resolved, not assumed away.
#
# WHAT I NEVER RAN.  Three draws of HEAD against ONE draw of the edit.  The obvious reading is that
# P34 is bimodal -- a Z1=4 basin and a better Z1=0 basin -- and three HEAD draws happened to land in
# the same one.  That is an ordinary outcome if the split is uneven, and it predicts the EDITED
# module will also return 249,163 on some draws.
#
# WHAT WOULD MAKE IT FAIL.  If three draws of the edit all return ~205,205 while three draws of HEAD
# all return ~249,163, then two builds that provably execute identical code are producing
# systematically different answers, and nothing ships until that is understood.
set -u
cd /home/user/oraclemaster/research/exact_packer/session2/recon || exit 1
while [ "$(cat harness/CURRENT 2>/dev/null)" != "idle" ]; do sleep 15; done
echo p34 > harness/CURRENT
L=results/audit/p34.log
mkdir -p results/audit; touch $L
ci(){ ( cd "$(git rev-parse --show-toplevel)" \
        && git add research/exact_packer/session2/recon/results/audit/p34.log \
                  research/exact_packer/session2/recon/harness/CURRENT \
                  research/exact_packer/session2/recon/harness/p34.sh \
        && git commit -q -m "in-flight: p34 $1" \
        && git push -q origin claude/repair-plan-model-1ig6it ) >/dev/null 2>&1; }
run(){ local tag="$1" mod="$2"
    grep -vE '^# ' $L 2>/dev/null | grep -q "\[$tag\]" && return
    echo "# [$tag]" >> $L
    env WORKERS=4 timeout 220 /usr/bin/python3.12 harness/run1.py $mod 34 60 \
        "[$tag]" --data data/stage2 >> $L 2>&1 || echo "P34 [$tag] CRASH rc=$?" >> $L
    ci "$tag"; }
for rep in 1 2 3; do
  run "p34.new.r$rep" myalgorithm
  run "p34.prev.r$rep" myalg_prev
done
echo "P34DONE" >> $L
echo idle > harness/CURRENT
