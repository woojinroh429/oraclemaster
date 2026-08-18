#!/bin/bash
# AMPLIFYING THE CONGESTION LOOKAHEAD NEVER LOSES IN THE FIRST THREE INSTANCES.
#
#     prob_20   9,504,772 -> 9,195,833   -3.25%
#     prob_6    5,358,595 -> 5,288,127   -1.31%
#     prob_36  75,290,776 -> 75,290,776    0.00%   identical to the digit
#
# OGC_THRUBEAM's only effect is to multiply the future-tardiness term by OGC_THRUHZ (default 3.0)
# inside the level rank.  Its name predates a change its own comment records: dropping the Z3 term
# blew Z3 up for a tiny Z1 gain, so Z3 stayed.  What is left is a lookahead amplifier.
#
# prob_36 returning the identical answer is the informative half.  It is 300 blocks and slice-bound,
# so the level loop bails and greedy_contact_from produces the answer -- the ranking never decides.
# prob_6 at 150 blocks and prob_20 at 250 both finish, and both move.  That boundary explains a run
# of failures tonight: the corrected hz1 lookahead, the tardiness operator and several rank changes
# were all edits to a ranking that does not determine the answer on the largest instances.
#
# WHAT THIS QUEUE HAS TO ESTABLISH.  Three single cells with no loss is a lead, not a result.  Two
# replicates per arm on the instances that carry spread, the two instances not yet tried (prob_1 and
# prob_16), and a sweep of the amplifier itself -- 3.0 was never chosen by measurement.
set -u
cd /home/user/oraclemaster/research/exact_packer/session2/recon || exit 1
echo thru > harness/CURRENT
( cd "$(git rev-parse --show-toplevel)" \
  && git add research/exact_packer/session2/recon/harness/CURRENT \
  && git commit -q -m "queue: CURRENT=thru" \
  && git push -q origin claude/repair-plan-model-1ig6it ) >/dev/null 2>&1
L=results/audit/thru.log
mkdir -p results/audit; touch $L
ci(){ ( cd "$(git rev-parse --show-toplevel)" \
        && git add research/exact_packer/session2/recon/results/audit/thru.log \
                  research/exact_packer/session2/recon/harness/CURRENT \
        && git commit -q -m "in-flight: thru $1" \
        && git push -q origin claude/repair-plan-model-1ig6it ) >/dev/null 2>&1; }

run(){ # tag prob limit env
    local tag="$1"
    grep -vE '^# ' $L 2>/dev/null | grep -q "\[$tag\]" && return
    echo "# [$tag]" >> $L
    env $4 OGC_WSTAT=1 timeout $(( $3 * 4 )) /usr/bin/python3.12 harness/run1.py myalgorithm $2 $3 \
        "[$tag]" --data data/stage2 >> $L 2>&1 || echo "P$2 [$tag] CRASH rc=$?" >> $L
    ci "$tag"
}

# the two never tried, first: prob_1 is the priority and prob_16 is where dir2 pays most
for p in 1 16; do
  run "n.p$p.off"  $p 240 ""
  run "n.p$p.thru" $p 240 "OGC_THRUBEAM=1"
done
echo "== THRU new instances done ==" >> $L

# replicate the three that have one cell each
for p in 20 6 24 4; do
  run "r2.p$p.off"  $p 240 ""
  run "r2.p$p.thru" $p 240 "OGC_THRUBEAM=1"
done
echo "== THRU replicate done ==" >> $L

# the amplifier itself: 3.0 is the shipped constant and was never measured
for p in 20 6; do
  for h in 1.5 6.0; do
    run "h.p$p.$h" $p 240 "OGC_THRUBEAM=1 OGC_THRUHZ=$h"
  done
done
echo "THRUDONE" >> $L
exec bash harness/sharerate.sh
