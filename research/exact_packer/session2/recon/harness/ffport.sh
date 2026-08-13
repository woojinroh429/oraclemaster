#!/bin/bash
# STOP CHOOSING PER INSTANCE.  PUT BOTH RUNG SPLITS IN THE POOL AND LET THE MINIMUM DECIDE.
#
# WHERE THIS COMES FROM.  FINEFRAC 0.85 against the shipped 0.60 is worth -22.15% on prob_1 (three
# replicates of three, the largest reproducible effect this study has produced) and costs +3.39% on
# prob_16.  Three attempts to decide per instance which of the two an instance wants were all
# rejected on measurement:
#
#     Z3 share            fitted on 4 instances, judged on the same 4, collapsed when one flipped
#     mean layer count    clean bimodal split that predicted nothing
#     beam salvage rate   SEALED before its holdout existed, then scored 3 of 7 = 43%
#
# Across 21 paired instances the population median is exactly +0.00%.  On a typical instance the
# setting does nothing; the mean is carried by prob_1 alone.  There is no rule to find.
#
# THE POOL DOES NOT NEED A RULE.  The answer is a MINIMUM over the workers, so a configuration that
# loses costs nothing but its own draw -- it is simply not the one taken.  A gate has to be right in
# advance.  A portfolio position does not have to be right at all.
#
# AND THE SPLIT ALREADY EXISTS, POINTING THE RIGHT WAY.  results/audit/workers.md, from every WSTAT
# line this project has logged:
#
#     inst       even (w0,w2) wins    odd (w1,w3) wins
#     prob_1          92%                   8%
#     prob_16         20%                  80%
#     prob_20          6%                  94%
#     prob_36          0%                 100%
#
# with its own conclusion: "The even configuration exists for prob_1 and essentially nothing else."
# prob_1 reads its answer off the even half; prob_16 and the rest read theirs off the odd half.  So
# 0.85 on the even half alone reaches the instance it helps and leaves the instances it hurts
# reading a worker that never saw it.
#
# ARMS:
#     A  shipped                    FINEFRAC 0.60 everywhere
#     B  portfolio                  OGC_FFSET=0.85,0.6   even 0.85, odd 0.60
#     C  global, for reference       OGC_FINEFRAC=0.85    every worker, the arm scan40 measured
#
# C IS CARRIED BECAUSE B WITHOUT IT PROVES NOTHING.  If B beats A on prob_1 and ties on prob_16
# while C beats A on prob_1 and LOSES on prob_16, the portfolio did its job.  If B and C are
# indistinguishable, then the parity split is not isolating anything and B is just C with extra
# machinery.
#
# WHAT WOULD MAKE IT FAIL, named first, and it is specific.  The even half is prob_1's ONLY winning
# half -- 92% against 8% -- so a change that makes even WORSE costs prob_1 twice, with no odd worker
# to fall back on.  That is the opposite risk from the gates: not that it fires on the wrong
# instance, but that it damages the one configuration prob_1 depends on.  prob_1 therefore carries
# four replicates and its result is read before anything else.
#
# The second failure mode is dilution.  With nw=3 the parities are 0,1,0 -- two even workers and one
# odd -- so on prob_16, whose minimum comes from odd 80% of the time, the pool now has ONE worker
# producing that minimum instead of relying on a full half.  If prob_16 degrades under B even though
# its odd workers are untouched, that is the mechanism and it kills the arm.
#
# JUDGED, fixed before the run: prob_1 first (B must beat A), then prob_16 and prob_20 must not
# regress against A by more than 1%, then B against C to confirm the split is doing the work.
set -u
cd /home/user/oraclemaster/research/exact_packer/session2/recon || exit 1
. harness/lock.sh
lock_acquire ffport
L=results/audit/ffport.log
mkdir -p results/audit; touch $L
ci(){ ( cd "$(git rev-parse --show-toplevel)" \
        && git add research/exact_packer/session2/recon/results/audit/ffport.log \
                  research/exact_packer/session2/recon/harness/CURRENT \
                  research/exact_packer/session2/recon/harness/ffport.sh \
        && git commit -q -m "in-flight: ffport $1" \
        && git push -q origin claude/repair-plan-model-1ig6it ) >/dev/null 2>&1; }
run(){ local tag="$1" p="$2" env0="$3" _s _e
    grep -vE '^# ' $L 2>/dev/null | grep -q "\[$tag\]" && return
    echo "# [$tag]" >> $L
    _s=$(date +%s.%N)
    env $env0 OGC_WSTAT=1 timeout 200 /usr/bin/python3.12 \
        harness/run1.py myalgorithm $p 60 "[$tag]" --data data/stage2 >> $L 2>&1 \
        || echo "P$p [$tag] CRASH rc=$?" >> $L
    _e=$(date +%s.%N)
    echo "# WALL [$tag] $(awk -v a="$_s" -v b="$_e" 'BEGIN{printf "%.2f", b-a}')" >> $L
    ci "$tag"; }
# prob_1 first and at every replicate: it decides the arm.
for rep in 1 2 3 4; do
  run "A.p1.r$rep" 1 ""
  run "B.p1.r$rep" 1 "OGC_FFSET=0.85,0.6"
  run "C.p1.r$rep" 1 "OGC_FINEFRAC=0.85"
done
for rep in 1 2 3; do
  for p in 16 20 3; do
    run "A.p$p.r$rep" $p ""
    run "B.p$p.r$rep" $p "OGC_FFSET=0.85,0.6"
    run "C.p$p.r$rep" $p "OGC_FINEFRAC=0.85"
  done
done
echo "FFPORTDONE" >> $L
lock_release ffport
