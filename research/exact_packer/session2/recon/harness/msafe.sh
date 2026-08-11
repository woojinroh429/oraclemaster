#!/bin/bash
# THE GATE FIRES ON 16 OF 40 AND FIVE WERE MEASURED.  CHECK THE OTHER ELEVEN FOR FLOORS.
#
# MGATE sets OGC_MSET=8 wherever peak_util >= 2.0 at timelimit >= 60.  On the practice set that is
# P2 P5 P6 P11 P13 P14 P18 P23 P25 P26 P28 P32 P36 P37 P39 P40.  mfinal covered P2, P11, P13, P23
# and P36 at 60 s; the remaining eleven would take the change unmeasured.
#
# THE FAILURE MODE IS NOT A SMALLER GAIN, IT IS A CLIFF.  M=8 multiplies the states a beam draw
# expands, so a draw that finished at M=1 may not finish at all -- and when no worker finishes the
# run returns _safe_sequential with feas=y and nothing in the output says so.  prob_36 at 30 s:
# 97,465,037 at the default, 4,023,023,953 with MSET=8.  That is the shape being checked for here,
# at the budget the gate actually fires in.
#
# JUDGED: any instance whose MSET=8 objective jumps to the floor -- an order of magnitude, Z3 at or
# near 0 -- kills the rule outright regardless of what the others do.  A merely worse number is
# weighed against the band; a floor is not.
set -u
cd /home/user/oraclemaster/research/exact_packer/session2/recon || exit 1
while [ "$(cat harness/CURRENT 2>/dev/null)" != "idle" ]; do sleep 15; done
echo msafe > harness/CURRENT
L=results/audit/msafe.log
mkdir -p results/audit; touch $L
ci(){ ( cd "$(git rev-parse --show-toplevel)" \
        && git add research/exact_packer/session2/recon/results/audit/msafe.log \
                  research/exact_packer/session2/recon/harness/CURRENT \
                  research/exact_packer/session2/recon/harness/msafe.sh \
        && git commit -q -m "in-flight: msafe $1" \
        && git push -q origin claude/repair-plan-model-1ig6it ) >/dev/null 2>&1; }
run(){ local tag="$1" p="$2" envs="$3"
    grep -vE '^# ' $L 2>/dev/null | grep -q "\[$tag\]" && return
    echo "# [$tag]" >> $L
    env $envs timeout 200 /usr/bin/python3.12 harness/run1.py myalgorithm $p 60 \
        "[$tag]" --data data/stage2 >> $L 2>&1 || echo "P$p [$tag] CRASH rc=$?" >> $L
    ci "$tag"; }
# the eleven unmeasured firing instances, largest peak_util first
for rep in 1 2; do
  for p in 25 39 37 5 18 28 26 32 14 40 6; do
    run "s.p$p.c.r$rep" $p "OGC_MGATE=0"
    run "s.p$p.m.r$rep" $p "OGC_MSET=8"
  done
done
echo "MSAFEDONE" >> $L
echo idle > harness/CURRENT
