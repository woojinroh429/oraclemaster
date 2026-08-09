#!/bin/bash
# THE 7TH SUBMISSION'S THIRD OVERRIDE WAS NOT A TUNING KNOB, AND REVERTING IT COST P1 AND P3.
#
# The hidden set, on the two instances the priority is about:
#
#     entry     P1          P3        what shipped
#     6th    2,883,654   5,715,679
#     7th    2,685,759   5,569,691   ORDER=lst + W3MUL=0.5 + RESFRAC=0.50    <- best ever, both
#     8th    3,009,531   5,972,740   all three reverted
#    10th    3,185,928   5,886,815   still reverted
#
# P1 has gone 2.69M -> 3.01M -> 3.19M since, which is +18.6% against a resubmission noise floor of
# -5.16% .. +8.66%.  That is outside the floor.  Both instances peaked at the one entry that
# carried RESFRAC and have not been back.
#
# WHY IT WAS DROPPED, AND WHY THAT REASONING WAS WRONG.  The revert note reads "resfrac stays out.
# It is decided once in algorithm() and cannot be split per worker, and halving the beam's budget on
# every instance is the part of the 7th with no upside anywhere."  Both halves of that are wrong.
# It does not halve the beam's budget -- it MOVES budget from one long round into a second round:
#
#     OGC_RESFRAC=0.35 on prob_1   WSTAT round=0 best 457,938
#                                  FILL round=1 budget=75 moved=1 best=437,697      -4.4%
#
# Raising the reserve lowers wbudget, which lowers _rb, which drops the fill gate 0.25*_rb below
# the leftover, so a SECOND WORKER ROUND runs.  That is the 232 s in every rf35 cell ever logged,
# against 200 s for every base cell, and it is why the four rf35/rf50 cells in ax1z1 all returned
# 422,629 -- this project's best number on prob_1.  ax1z1 read that as the polish getting more
# budget.  It was the second round.
#
# It also explains ROUNDS (+45%): R=2 and R=4 split the budget EVENLY, and the structure that wins
# is ASYMMETRIC, 155 then 75.  And OGC_FILLMIN (0%): it opens the gate without raising the reserve,
# so the second round gets 31 s and returns moved=0.  199+31 is not 155+75.
#
# THE OTHER TWO OVERRIDES STAY OFF, and results/audit/families.md says why: ORDER=lst + W3MUL=0.5
# is the configuration for Z3-DOMINATED instances, and forcing it globally is what blew P2 +14.23%,
# P5 +19.03% and P8 +14.00% in the 7th.  It already lives on the wid%2 split as DIRSET=2.  So the
# claim under test is that the 7th's gain and the 7th's loss came from DIFFERENT overrides.
#
# THE INSTANCES.  prob_1 and prob_3 are the two most Z3-dominated in the training set (86.3% and
# 89.4%) and stand in for the hidden P1 and P3.  prob_16 is the veto: it already read base
# 2,469,078 against rf35 2,927,238, an 18.6% LOSS, and if that reproduces the reserve cannot become
# a global default and has to go on the parity split instead.
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

# THE PRIORITY INSTANCES FIRST, and rf50 because that is the value the 7th actually shipped.
for rep in 1 2 3; do
  for p in 1 3; do
    run "r$rep.p$p.base"  $p 240 ""
    run "r$rep.p$p.rf50"  $p 240 "OGC_RESFRAC=0.50"
    run "r$rep.p$p.rf35"  $p 240 "OGC_RESFRAC=0.35"
    run "r$rep.p$p.both"  $p 240 "OGC_RESFRAC=0.50 OGC_PARFILL=1"
  done
done
echo "== ROUND2 priority instances done ==" >> $L

# THE VETO.  prob_16 said no to a bigger reserve once already.
for rep in 1 2; do
  run "r$rep.p16.base" 16 240 ""
  run "r$rep.p16.rf50" 16 240 "OGC_RESFRAC=0.50"
  run "r$rep.p16.both" 16 240 "OGC_RESFRAC=0.50 OGC_PARFILL=1"
done
echo "== ROUND2 veto done ==" >> $L

# and the rest of the set, one pair each, to price what a global default would cost elsewhere.
for p in 20 24 36 6 4 2; do
  run "g.p$p.base"  $p 240 ""
  run "g.p$p.rf50"  $p 240 "OGC_RESFRAC=0.50"
  run "g.p$p.both"  $p 240 "OGC_RESFRAC=0.50 OGC_PARFILL=1"
done
echo "ROUND2DONE" >> $L
echo idle > harness/CURRENT
