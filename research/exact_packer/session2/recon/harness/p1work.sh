#!/bin/bash
# prob_1's (AXIS, WORK) TABLE, MEASURED WITHOUT A CLOCK.
#
# WHY THIS REPLACES THE WALL-CLOCK SWEEP.  The axis sweep in p1draws spent fourteen 240 s cells to
# rank six axes and could not: ax0 alone read 630,785 and 469,650, a 25% span, which is most of
# the 44% gap being ranked.  OGC_WORKCAP removes the clock from the beam's stop test and both
# width controllers, and then one (axis, work) pair has exactly one answer -- prob_16 at work 4000
# returned obj=6,684,986 digest=00e0c6a4b5d1da5e on three consecutive runs.  The question is
# answerable exactly, and I have been paying noise for it.
#
# WHAT IT ANSWERS AND WHAT IT DOES NOT.  This is quality per unit of WORK.  It does not say what a
# 240 s run scores, because an axis that searches better per unit of work can still lose by
# costing more per unit.  Throughput is the second half and is measured separately from the wall
# times printed here.
#
# THE HYPOTHESIS IT TESTS.  Nine wall-clock cells gave r(best seed, final) = +0.846 against
# r(median seed, final) = -0.328, i.e. the run's answer tracks the LEFT TAIL of the seed
# distribution.  The seed-count half of that story is refuted -- work_mode.md shows a worker has
# at most six distinct answers per work level, the rest being clock perturbation -- so the only
# live lever is WORK PER DRAW.  On prob_16 the productive axis goes 3,159,373 -> 2,477,998 for
# doubling work, 21.6%.  Nobody has ever measured that curve on prob_1.
#
# --useaxis is the production reading: each axis at its OWN Bmul-derived width and K, which is
# what _worker actually runs.  The fixed-B table in the file measured axes at a width they never
# get, and that ambiguity is what this flag exists to remove.
#
# WHAT WOULD REFUSE THE WHOLE DIRECTION.  If prob_1's curve is flat in work -- if 12,000 is no
# better than 3,000 on every axis -- then the seed tail cannot be deepened by spending more on a
# draw, and the +0.846 correlation is describing something the search cannot control.  That would
# close the last open lever on P1 and the honest report is that its band is irreducible.
set -u
cd /home/user/oraclemaster/research/exact_packer/session2/recon || exit 1
echo p1work > harness/CURRENT
L=results/audit/p1work.log
mkdir -p results/audit; touch $L
ci(){ ( cd "$(git rev-parse --show-toplevel)" \
        && git add research/exact_packer/session2/recon/results/audit/p1work.log \
                  research/exact_packer/session2/recon/harness/CURRENT \
        && git commit -q -m "in-flight: p1work $1" \
        && git push -q origin claude/repair-plan-model-1ig6it ) >/dev/null 2>&1; }

cell(){ # prob axis work
    local tag="p$1.ax$2.w$3"
    grep -q "$tag" $L 2>/dev/null && return
    OGC_WORKCAP=$3 timeout 900 /usr/bin/python3.12 harness/beam1.py $1 --work $3 --axis $2 \
        --useaxis --data data/stage2 --tag "$tag" >> $L 2>&1 || echo "$tag CRASH rc=$?" >> $L
    ci "$tag"
}

# prob_1 first: six axes across a work ladder.  Production gives a draw ~7-8 s which at the
# measured ~220 expansions/s is roughly 1,700 work, so the ladder brackets it on both sides.
for w in 1500 3000 6000 12000; do
  for a in 0 1 2 3 4 5; do
    cell 1 $a $w
  done
done
echo "== P1WORK prob_1 done ==" >> $L

# prob_3 and prob_16: prob_3 is the other Z3-family instance and the one brk pays on; prob_16 is
# where a single draw at work 6000 already beats every full run ever recorded, which nothing has
# explained and which this table can confirm or kill in six cells.
for w in 3000 6000 12000; do
  for a in 0 1 2 3 4 5; do
    cell 16 $a $w
  done
done
echo "== P1WORK prob_16 done ==" >> $L

for w in 3000 6000 12000; do
  for a in 0 1 2 3 4 5; do
    cell 3 $a $w
  done
done
echo "P1WORKDONE" >> $L
echo idle > harness/CURRENT
