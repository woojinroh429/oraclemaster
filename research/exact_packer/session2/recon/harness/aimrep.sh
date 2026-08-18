#!/bin/bash
# CONFIRM THE ONE THING THAT WAS ADOPTED, INSTEAD OF LOOKING FOR A NINTH THING TO ADOPT.
#
# Eight phases have run tonight and exactly one changed a default: the adaptive beam aim.  Its
# evidence is one cell per arm on three instances --
#
#     adapt vs base:   P16 -0.17%   P36 -0.76%   P1 0.00%
#
# -- which is a tie, adopted on the argument that every FIXED aim has a large floor somewhere
# (hi is best on P16 and +15.86% on P36; lo is +57.35% on P1) and an adaptive rule cannot.
#
# That argument is only as good as the claim that adapt never loses, and "never loses" rests on
# three single cells.  This instance set spans 0.5-4.5% run to run, so a -0.76% could be a +2% and
# the adoption would be wrong.  Two replicates per arm on five instances is what settles it, and it
# is worth more than a ninth refuted hypothesis.
#
# Everything else tonight came back refuted or inside the noise:
#
#     census/roster   bay is 19% of every worker for ~0 gain, and removing it changes nothing;
#                     removing pref and bal costs 30% on prob_1
#     fill gate       recovers 32 idle seconds of 240 and returns the identical answer
#     rounds          R1 best or tied on all four, +45.13% at R=4 on prob_1
#     hz1 lookahead   the arithmetic error is real; fixing it is 2 wins and 3 losses
#     z1op            ruin_tardy in the roster: +14.82% on prob_1, +5.66% on prob_20
#     axis director   0.00% on prob_1, -0.35% on prob_20
#
# The common shape is that at 240 s these instances are at a fixed point.  prob_1 returned 470,530
# from NINE different configurations today.  Moving budget between operators does not move it.
set -u
cd /home/user/oraclemaster/research/exact_packer/session2/recon || exit 1
echo aimrep > harness/CURRENT
( cd "$(git rev-parse --show-toplevel)" \
  && git add research/exact_packer/session2/recon/harness/CURRENT \
  && git commit -q -m "queue: CURRENT=aimrep" \
  && git push -q origin claude/repair-plan-model-1ig6it ) >/dev/null 2>&1
L=results/audit/aimrep.log
mkdir -p results/audit; touch $L
ci(){ ( cd "$(git rev-parse --show-toplevel)" \
        && git add research/exact_packer/session2/recon/results/audit/aimrep.log \
                  research/exact_packer/session2/recon/harness/CURRENT \
        && git commit -q -m "in-flight: aimrep $1" \
        && git push -q origin claude/repair-plan-model-1ig6it ) >/dev/null 2>&1; }

run(){ # tag prob limit env
    local tag="$1"
    grep -vE '^# ' $L 2>/dev/null | grep -q "\[$tag\]" && return
    echo "# [$tag]" >> $L
    env $4 timeout $(( $3 * 4 )) /usr/bin/python3.12 harness/run1.py myalgorithm $2 $3 \
        "[$tag]" --data data/stage2 >> $L 2>&1 || echo "P$2 [$tag] CRASH rc=$?" >> $L
    ci "$tag"
}

# off is the 6th submission's behaviour on this knob, so this doubles as "is the tree better than
# the entry that scored best on the hidden set".  Arms interleaved within an instance against
# machine drift; replicates as the outer loop so a partial night still covers all five instances.
for rep in 1 2; do
  for p in 16 36 20 6 1; do
    run "a240.p$p.off.r$rep" $p 240 "OGC_ADAPTAIM=0"
    run "a240.p$p.on.r$rep"  $p 240 "OGC_ADAPTAIM=1"
  done
  echo "== AIMREP rep $rep done ==" >> $L
done
echo "AIMREPDONE" >> $L
echo idle > harness/CURRENT
