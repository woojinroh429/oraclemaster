#!/bin/bash
# m=3 ON prob_1, WHICH IS THE INSTANCE THE PORTFOLIO HAS TO SURVIVE.
#
# m=2 costs 27.78% on prob_1 alone and the 2:2 split absorbed all of it -- mix returned m1's answer
# to the digit.  m=3 is the next question, and the file's own note leaves it open:
#
#     m=3   prob_24 +2.40%   prob_4 +10.89%    lost both
#     "raising the ceiling is the direct test of whether m=3 lost to the branching or to the slot
#      shortage"
#
# Each state expanding m blocks means m times as many children compete for the same B survivor
# slots, and B is capped at OGC_BCAP=96.  So m=3 has two possible failure modes -- too much
# branching for the search to be worth it, or enough branching that the survivor set is the binding
# constraint -- and they have opposite prescriptions.  BCAP=192 separates them.
#
# Four arms on prob_1:
#
#     m3       m=3 on every worker, against the m1 470,530 / m2 601,265 already measured
#     m3cap    the same with twice the survivor ceiling
#     mix13    2:2 split of m=1 and m=3 -- the shipped shape, with 3 in place of 2
#     mix123   1,2,3 across four workers: m=1 twice, m=2 and m=3 once each
#
# mix123 is the interesting one and also the thin one: with four workers three values leave one
# worker at two of them, and this project has already measured what happens when a portfolio
# position drops to a single worker -- spreading the beam aim across four values instead of
# stacking 2:2 lost, because what breaks is the guarantee of a PAIR at each end.
set -u
cd /home/user/oraclemaster/research/exact_packer/session2/recon || exit 1
echo m3 > harness/CURRENT
( cd "$(git rev-parse --show-toplevel)" \
  && git add research/exact_packer/session2/recon/harness/CURRENT \
  && git commit -q -m "queue: CURRENT=m3" \
  && git push -q origin claude/repair-plan-model-1ig6it ) >/dev/null 2>&1
L=results/audit/m3.log
mkdir -p results/audit; touch $L
ci(){ ( cd "$(git rev-parse --show-toplevel)" \
        && git add research/exact_packer/session2/recon/results/audit/m3.log \
                  research/exact_packer/session2/recon/harness/CURRENT \
        && git commit -q -m "in-flight: m3 $1" \
        && git push -q origin claude/repair-plan-model-1ig6it ) >/dev/null 2>&1; }

run(){ # tag prob limit env
    local tag="$1"
    grep -vE '^# ' $L 2>/dev/null | grep -q "\[$tag\]" && return
    echo "# [$tag]" >> $L
    env $4 timeout $(( $3 * 4 )) /usr/bin/python3.12 harness/run1.py myalgorithm $2 $3 \
        "[$tag]" --data data/stage2 >> $L 2>&1 || echo "P$2 [$tag] CRASH rc=$?" >> $L
    ci "$tag"
}

# prob_1 first and complete, because it is the instance that decides whether a value is shippable:
# every arm that has failed tonight failed there.  m1 and m2 are re-run so the whole comparison
# sits on one build.
run "p1.m1"     1 240 "OGC_MCAND=1"
run "p1.m2"     1 240 "OGC_MCAND=2"
run "p1.m3"     1 240 "OGC_MCAND=3"
run "p1.m3cap"  1 240 "OGC_MCAND=3 OGC_BCAP=192"
run "p1.mix13"  1 240 "OGC_MSET=1,3"
run "p1.mix123" 1 240 "OGC_MSET=1,2,3"
echo "== M3 prob_1 done ==" >> $L

# then the two instances where more branching has paid, to see whether m=3 is simply m=2 further
# along the same curve or a different regime
for p in 24 20 4; do
  run "p$p.m3"     $p 240 "OGC_MCAND=3"
  run "p$p.mix13"  $p 240 "OGC_MSET=1,3"
  run "p$p.mix123" $p 240 "OGC_MSET=1,2,3"
done
echo "M3DONE" >> $L

# hand the machine back to the pass-2 validation of the change that is already shipped
exec bash harness/mset.sh
