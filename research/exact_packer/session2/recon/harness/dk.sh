#!/bin/bash
# THE DRAWS ARE BEING REPEATED RATHER THAN SAMPLED.
#
# This is the answer to "how do we reach the good end more often", and it is a one-line gate that
# has never been open.
#
# A worker takes 14-55 beam draws in a 240 s run and picks its config as axes[gen % 6].  Six
# deterministic configs, so the number of DISTINCT constructions a worker can reach is six, however
# many draws it takes.  The WSTAT lines show exactly that: w0 returned 612,635 in three consecutive
# runs of prob_1, spending the entire budget without ever moving off its first answer.  The score is
# a minimum over draws; repeating a draw contributes nothing to a minimum.
#
# _beam_once already carries the fix.  On the second and later visit to an axis it can replace the
# fixed dispatch order with a uniform pick from the top-k of what remains -- so a repeat visit
# builds something new instead of re-deriving the first answer.  It is gated on cfg["dk"] > 1, and
# all six axes ship dk=0.  It has never run.
#
# NOT OGC_AXJIT.  That jittered the axis PARAMETERS per draw and measured +6.5%; it perturbs the
# ranking function, which is the part the axis was tuned for.  dk perturbs the dispatch ORDER, which
# the file calls the largest lever on this problem -- 32-210% construction spread across orders
# against about 2% for the combined range of everything else -- and it stays inside the axis's own
# priority by drawing from its top-k.
#
# WHAT TO EXPECT AND WHAT WOULD REFUTE IT.  If draw repetition is the binding constraint, dk should
# lower the MEAN and, more importantly, raise the frequency of landing in the good cluster.  If the
# instances are already at their floor, dk will spend draws on worse constructions and the mean will
# rise.  prob_1 and prob_16 get four replicates each because both span more run to run (prob_16
# 2.47M-3.50M, 42%) than any arm difference measured tonight.
set -u
cd /home/user/oraclemaster/research/exact_packer/session2/recon || exit 1
echo dk > harness/CURRENT
( cd "$(git rev-parse --show-toplevel)" \
  && git add research/exact_packer/session2/recon/harness/CURRENT \
  && git commit -q -m "queue: CURRENT=dk" \
  && git push -q origin claude/repair-plan-model-1ig6it ) >/dev/null 2>&1
L=results/audit/dk.log
mkdir -p results/audit; touch $L
ci(){ ( cd "$(git rev-parse --show-toplevel)" \
        && git add research/exact_packer/session2/recon/results/audit/dk.log \
                  research/exact_packer/session2/recon/harness/CURRENT \
        && git commit -q -m "in-flight: dk $1" \
        && git push -q origin claude/repair-plan-model-1ig6it ) >/dev/null 2>&1; }

run(){ # tag prob limit env
    local tag="$1"
    grep -vE '^# ' $L 2>/dev/null | grep -q "\[$tag\]" && return
    echo "# [$tag]" >> $L
    env $4 OGC_WSTAT=1 timeout $(( $3 * 4 )) /usr/bin/python3.12 harness/run1.py myalgorithm $2 $3 \
        "[$tag]" --data data/stage2 >> $L 2>&1 || echo "P$2 [$tag] CRASH rc=$?" >> $L
    ci "$tag"
}

for rep in 1 2 3 4; do
  for p in 1 16; do
    run "r$rep.p$p.off" $p 240 ""
    run "r$rep.p$p.dk2" $p 240 "OGC_DK=2"
    run "r$rep.p$p.dk3" $p 240 "OGC_DK=3"
  done
done
echo "== DK prob_1/prob_16 done ==" >> $L

for p in 36 20 6 24 4; do
  run "g.p$p.off" $p 240 ""
  run "g.p$p.dk2" $p 240 "OGC_DK=2"
done
echo "DKDONE" >> $L

# then throughput, then the SHARE rate study.
exec bash harness/speed.sh
