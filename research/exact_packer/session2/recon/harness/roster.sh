#!/bin/bash
# THE BEAM IS 464x MORE PRODUCTIVE PER SECOND THAN ANYTHING ELSE, AND PROBES TAKE A THIRD OF THE
# BUDGET.
#
# OGC_OPSTAT has never been run on this build.  prob_1, one worker, 240 s:
#
#     op     tried  seconds  %budget          gain     gain/s
#     beam       8    120.4    61.0%   979,091,983  8,129,865
#     grow       1     31.6    16.0%        28,795        910
#     bal        1      0.0     0.0%             0          0
#     pref       2      3.0     1.5%         7,814      2,642
#     z1         1     16.7     8.5%             0          0
#     bay        1     25.4    12.8%             0          0
#
# z1 and bay together burn 21.3% of the worker's budget and return zero.  bay is `_assign`, which
# this session isolated and measured: given a real prob_1 incumbent it returns Z1 12 -> 63, Z2
# 3990 -> 7486, Z3 579 -> 658, +90.56%, in ~10 s whatever budget it gets.  It is in the DEFAULT
# roster, so the shipped build spends 7-13% of every worker on it.
#
# The cost is the bandit's opening probe, not the bandit's choices.  Repair passes open on
# budget/(2n) -- 197/12 = 16.4 s each -- and there are four of them, so a third of the budget is
# spent finding out what does not pay, on every worker, on every run.
#
# WHY THIS ONE IS DIFFERENT FROM EVERYTHING ELSE TONIGHT.  Six branches closed because prob_1 and
# prob_16 want opposite things and there is no way to tell which is which in advance.  This is not
# a trade: it is time going somewhere that returns nothing.  The risk is the mirror image -- an
# operator that pays on an instance not in this list -- so the queue covers five.
#
# OGC_OPS is an existing roster filter, so no code change is needed to price it.
set -u
cd /home/user/oraclemaster/research/exact_packer/session2/recon || exit 1
echo roster > harness/CURRENT
L=results/audit/roster.log
mkdir -p results/audit; touch $L
ci(){ ( cd "$(git rev-parse --show-toplevel)" \
        && git add research/exact_packer/session2/recon/results/audit/roster.log \
                  research/exact_packer/session2/recon/harness/CURRENT \
        && git commit -q -m "in-flight: roster $1" \
        && git push -q origin claude/repair-plan-model-1ig6it ) >/dev/null 2>&1; }
run(){ local tag="$1"
    grep -vE '^# ' $L 2>/dev/null | grep -q "\[$tag\]" && return
    echo "# [$tag]" >> $L
    env $4 OGC_WSTAT=1 timeout $(( $3 * 4 )) /usr/bin/python3.12 harness/run1.py myalgorithm $2 $3 \
        "[$tag]" --data data/stage2 >> $L 2>&1 || echo "P$2 [$tag] CRASH rc=$?" >> $L
    ci "$tag"
}
for rep in 1 2 3; do
  run "r$rep.p1.all"   1 240 ""
  run "r$rep.p1.nobay" 1 240 "OGC_OPS=beam,grow,bal,pref"
  run "r$rep.p1.beam"  1 240 "OGC_OPS=beam,grow"
done
echo "== ROSTER prob_1 done ==" >> $L
for rep in 1 2; do
  for p in 16 20 24 3; do
    run "r$rep.p$p.all"   $p 240 ""
    run "r$rep.p$p.nobay" $p 240 "OGC_OPS=beam,grow,bal,pref"
  done
done
echo "ROSTERDONE" >> $L
echo idle > harness/CURRENT
