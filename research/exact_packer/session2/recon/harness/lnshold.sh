#!/bin/bash
# LNSEQ HOLDOUT.  THE EFFECT IS CARRIED BY ONE INSTANCE AND THAT INSTANCE WAS IN THE FITTING SET.
#
# WHAT lnseq.log ESTABLISHED over 24 paired cells, 8 instances, 3 replicates: population ratio-mean
# -1.23%, 10 wins / 5 losses / 9 byte-identical.  Per instance:
#
#     P16  -6.53%  [-3.70, -11.79, -4.11]     3 of 3, and B's whole range sits below A's
#     P24  -1.72%  [-2.58,  +0.00, -2.58]     2 wins, never loses, B pinned at 3074138
#     P7   -2.85%  [+0.00,  -9.97, +1.43]     noise: B's -9.97 is A MISSING the value both
#                                             arms returned in r1, not B finding anything
#     P13  -0.22%  P5 +0.00%  P1 +0.11%  P3 +0.14%  P20 +1.20%
#
# The mechanism the value-sets show is not "finds better optima".  On P1 the two arms return the
# SAME MULTISET in a different order; on P5 they are identical in all three cells.  On P16 and P24
# B collapses onto a good attractor that A reaches only sometimes.  So the claim under test is
# narrow and specific: LNSEQ STABILISES, it does not discover.
#
# WHY A HOLDOUT AND NOT A DECISION.  The pre-registered rule is satisfied on the letter --
# population mean negative, no instance losing on all three replicates -- but essentially the whole
# effect is P16, and P16 was one of the eight instances the arm was measured on.  This session has
# fitted three gates on four-instance evidence (Z3-share, mean-layer-count, beam-salvage-rate) and
# all three died on holdout, the last after looking 8-of-8 correct.  Judging a one-instance effect
# on the set containing that instance is the same error with a new name.
#
# INSTANCES: eight that no cell of lnseq touched -- prob_2, 6, 10, 26, 27, 30, 33, 36.  prob_2/27/33
# additionally carry history: they are where OGC_FFSET lost 6.8-8.9% while winning big on prob_1,
# so they are the known home of "wins on one instance, pays for it elsewhere".
#
# WHAT WOULD MAKE THIS MISLEAD, named first.  Two replicates cannot separate a 2% effect from
# per-instance noise measured at 11-23% on the volatile instances.  What two replicates CAN support
# is the thing actually claimed: if LNSEQ stabilises, B's two values should agree with each other
# more often than A's two do, and that is a count, not a mean.  Both are reported.
#
# JUDGED, fixed before the run.
#   * ADOPT only if the holdout population ratio-mean is negative AND no holdout instance loses on
#     BOTH replicates.
#   * The stabilisation claim is scored separately: count instances where B's two runs are equal
#     against instances where A's two are.  If B is not the more stable side, the mechanism story
#     is wrong even if the mean happens to come out negative, and it will be reported that way.
#   * A holdout mean inside +/-0.5% is reported as no effect, not as a win.
set -u
cd /home/user/oraclemaster/research/exact_packer/session2/recon || exit 1
if nm -D ogc_fast.cpython-312-x86_64-linux-gnu.so 2>/dev/null | grep -q 'GOMP_\|omp_get'; then
    echo "ABORT: working .so carries OpenMP; the shipped build does not."; exit 1
fi
. harness/lock.sh
lock_acquire lnshold
L=results/audit/lnshold.log
mkdir -p results/audit; touch $L
ci(){ ( cd "$(git rev-parse --show-toplevel)" \
        && git add research/exact_packer/session2/recon/results/audit/lnshold.log \
                  research/exact_packer/session2/recon/harness/CURRENT \
                  research/exact_packer/session2/recon/harness/lnshold.sh \
        && git commit -q -m "in-flight: lnshold $1" \
        && git push -q origin claude/repair-plan-model-1ig6it ) >/dev/null 2>&1; }
run(){ local tag="$1" p="$2" ev="$3" _s _e
    grep -vE '^# ' $L 2>/dev/null | grep -q "\[$tag\]" && return
    echo "# [$tag]" >> $L
    _s=$(date +%s.%N)
    env $ev timeout 200 /usr/bin/python3.12 \
        harness/run1.py myalgorithm $p 60 "[$tag]" --data data/stage2 >> $L 2>&1 \
        || echo "P$p [$tag] CRASH rc=$?" >> $L
    _e=$(date +%s.%N)
    echo "# WALL [$tag] $(awk -v a="$_s" -v b="$_e" 'BEGIN{printf "%.2f", b-a}')" >> $L
    ci "$tag"; }
for rep in 1 2; do
  for p in 2 27 33 26 30 36 10 6; do
    run "A.p$p.r$rep" $p "OGC_LNSEQ="
    run "B.p$p.r$rep" $p "OGC_LNSEQ=1"
  done
done
echo "LNSHOLDDONE" >> $L
lock_release lnshold
