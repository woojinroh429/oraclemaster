#!/bin/bash
# SOLVE THE ASSIGNMENT FIRST, THEN LET THE BEAM BUILD GEOMETRY UNDER IT.
#
# The instance analysis that produced this (results/audit/p1_anatomy.md):
#
#   Z1's floor is 0 -- no block on stage2/prob_1 has release + processing > due, so every
#   tardiness unit we pay is a packing failure, not a property of the data.
#   Z2 is worth 1.28 displaced blocks over its ENTIRE range, so the objective is w1*Z1 + w3*Z3.
#   Z3 > 0 is forced: at a first-choice assignment the peak simultaneous bounding-box area is
#   56% / 147% / 201% of the three bays, so ~983 area units must be displaced at the peak.
#   The only question is WHICH blocks -- and a real incumbent answers it badly, displacing 22
#   blocks for Z3 = 1009 whose worst payers give up 98, 96, 90 and 84 preference units each
#   while blocks with regret 6, 7, 10 and 16 and MORE area keep their first choice.
#
# The cause is sequential, not weighted.  mu = 1e-3*min(w1,w3) = 0.6 against 600*pen, so the
# cross-bay rank already treats contact as noise beside preference -- but it decides one block at
# a time, and a block arriving at a full bay cannot propose that a cheaper block behind it should
# be displaced instead.  Deciding all 150 at once is the missing operator.
#
# Under an area relaxation (per-bay cumulative, times free, minimise w1*Z1 + w3*Z3) CP-SAT returns
# Z1 = 0-1 with Z3 = 217-484 depending on budget, against the incumbent's Z1 = 19, Z3 = 1009 --
# 136,867 to 303,134 against 732,073.  OGC_CPANCH turns that plan into a preference rewrite, which
# is the one channel that reaches drank, the beam's state rank and the rollout at once (the anchor
# argument cannot: ogc_fast.cpp records that it never binds and that making it bind lost).
#
# WHAT THE FIRST TWO MEASUREMENTS ALREADY SAID, so this sweep does not re-ask them:
#
#   toll 60, alternatives flattened to 0   Z1 17  Z3 964   12 deviations carrying 609 of it
#   toll 100, real preferences kept        Z1 41  Z3 641    5 deviations carrying 264 of it
#
# Flattening the alternatives was wrong -- a block forced out of its plan had nothing left to tell
# it which bay to take.  Keeping them and raising the toll cut deviations to five, and the beam
# paid for its obedience in TARDINESS (17 -> 41), which is the second thing to fix: the model is
# optimistic about time because bounding boxes do not tile a bay.
#
# SO THE GRID IS TOLL x CAPACITY DE-RATING.  OGC_CPCAP shrinks every bay in the model so the plan
# leaves room for the packing loss; OGC_CPANCHW is what leaving the plan costs.  The control is
# CPANCH unset, which is byte-identical to the shipped code.
#
# WHAT WOULD MAKE IT FAIL, named first.  De-rate too hard and the plan displaces blocks that did
# not need displacing, which is exactly the failure the aggregate-row _bayplan died of; toll too
# high and the beam waits for a bay it should have abandoned, at 6,667 a unit.  Both show up as a
# Z1/Z3 split, so all three components are reported and neither is read alone.
set -u
cd /home/user/oraclemaster/research/exact_packer/session2/recon || exit 1
echo cpanch > harness/CURRENT
L=results/audit/cpanch.log
mkdir -p results/audit; touch $L
ci(){ ( cd "$(git rev-parse --show-toplevel)" \
        && git add research/exact_packer/session2/recon/results/audit/cpanch.log \
                  research/exact_packer/session2/recon/harness/CURRENT \
                  research/exact_packer/session2/recon/harness/cpanch.sh \
        && git commit -q -m "in-flight: cpanch $1" \
        && git push -q origin claude/repair-plan-model-1ig6it ) >/dev/null 2>&1; }

run(){ # tag env
    local tag="$1"
    grep -vE '^# ' $L 2>/dev/null | grep -q "\[$tag\]" && return
    echo "# [$tag]" >> $L
    env $2 OGC_WSTAT=1 timeout 400 /usr/bin/python3.12 harness/run1.py myalgorithm 1 120 \
        "[$tag]" --data data/stage2 >> $L 2>&1 || echo "P1 [$tag] CRASH rc=$?" >> $L
    ci "$tag"
}

for rep in 1 2 3; do
  run "ca.off.r$rep" "WORKERS=4"
  for C in 1.00 0.85 0.70; do
    for T in 100 300; do
      run "ca.c$C.t$T.r$rep" "WORKERS=4 OGC_CPANCH=20 OGC_CPCAP=$C OGC_CPANCHW=$T"
    done
  done
done
echo "CPANCHDONE" >> $L
echo idle > harness/CURRENT
