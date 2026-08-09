#!/bin/bash
# THE RESERVE IS NOT POLISH BUDGET.  IT IS SECOND-ROUND BUDGET.
#
# Every RESFRAC=0.35 cell this project has logged runs 232 s and every base cell runs 200 s, and
# the 32 s is not the polish.  Raising the reserve lowers `wbudget`, which lowers `_rb`, which
# lowers the fill gate `_need = 0.25*_rb` below the leftover -- so a SECOND WORKER ROUND runs.
# Caught directly:
#
#     OGC_RESFRAC=0.35   WSTAT round=0 best 457,938
#                        FILL round=1 budget=75 moved=1 best=437,697      -4.4%
#
# That retires ax1z1's conclusion, which read "what moved prob_1 from 438,791 to 422,629 is the
# polish getting more budget, full stop".  It was the second round.  rf35 = rf50 to the digit is
# the same fact: both open the gate and both get a round of about the same length.
#
# AND IT EXPLAINS WHY `ROUNDS` FAILED.  R=2 and R=4 split the budget EVENLY and measured +45%.
# The structure that wins here is ASYMMETRIC -- 155 s then 75 s -- one round long enough to reach
# a good solution and a second that is an independent draw with a new seed and a new axis rotation.
#
# AND WHY OGC_FILLMIN BOUGHT NOTHING.  It opens the gate without raising the reserve, so the second
# round gets 31 s instead of 75 s, and a 31 s round returns moved=0: 199+31 is not 155+75.
#
# THE ARMS.  Two knobs, crossed, because the reasoning says they compose and the reasoning has been
# wrong twice tonight.
#
#     base      one round of 199 s, 40 s discarded            the shipped behaviour
#     rf35      155 + 75, both rounds on the 2+2 split
#     parfill   199 + 31, the short round on the winning half
#     both      155 + 75, the long second round on the winning half
#
# WHAT WOULD REFUTE IT.  If `both` does not beat `rf35`, the parity direction is worth nothing and
# only the round length mattered.  If `rf35` does not beat `base` on prob_16 / 20 / 24, the second
# round is a prob_1 fact and the reserve default stays where it is -- prob_16 already read
# base 2,469,078 against rf35 2,927,238, an 18.6% LOSS, so this is a real possibility and the
# instance is in the queue first for that reason.
set -u
cd /home/user/oraclemaster/research/exact_packer/session2/recon || exit 1
echo round2 > harness/CURRENT
( cd "$(git rev-parse --show-toplevel)" \
  && git add research/exact_packer/session2/recon/harness/CURRENT \
  && git commit -q -m "queue: CURRENT=round2" \
  && git push -q origin claude/repair-plan-model-1ig6it ) >/dev/null 2>&1
L=results/audit/round2.log
mkdir -p results/audit; touch $L
ci(){ ( cd "$(git rev-parse --show-toplevel)" \
        && git add research/exact_packer/session2/recon/results/audit/round2.log \
                  research/exact_packer/session2/recon/harness/CURRENT \
        && git commit -q -m "in-flight: round2 $1" \
        && git push -q origin claude/repair-plan-model-1ig6it ) >/dev/null 2>&1; }

run(){ # tag prob limit env
    local tag="$1"
    grep -vE '^# ' $L 2>/dev/null | grep -q "\[$tag\]" && return
    echo "# [$tag]" >> $L
    env $4 OGC_WSTAT=1 timeout $(( $3 * 4 )) /usr/bin/python3.12 harness/run1.py myalgorithm $2 $3 \
        "[$tag]" --data data/stage2 >> $L 2>&1 || echo "P$2 [$tag] CRASH rc=$?" >> $L
    ci "$tag"
}

RF="OGC_RESFRAC=0.35"
PF="OGC_PARFILL=1"

# prob_16 FIRST.  It is the instance that already said no to a bigger reserve, so if the idea is
# wrong this is where it dies, and it dies before four replicates of prob_1 are spent on it.
for rep in 1 2; do
  run "r$rep.p16.base"    16 240 ""
  run "r$rep.p16.rf35"    16 240 "$RF"
  run "r$rep.p16.parfill" 16 240 "$PF"
  run "r$rep.p16.both"    16 240 "$RF $PF"
done
echo "== ROUND2 prob_16 done ==" >> $L

for rep in 1 2 3; do
  run "r$rep.p1.base"    1 240 ""
  run "r$rep.p1.rf35"    1 240 "$RF"
  run "r$rep.p1.parfill" 1 240 "$PF"
  run "r$rep.p1.both"    1 240 "$RF $PF"
done
echo "== ROUND2 prob_1 done ==" >> $L

for p in 20 24 36 6; do
  run "g.p$p.base"    $p 240 ""
  run "g.p$p.rf35"    $p 240 "$RF"
  run "g.p$p.both"    $p 240 "$RF $PF"
done
echo "ROUND2DONE" >> $L
echo idle > harness/CURRENT
