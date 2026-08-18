#!/bin/bash
# THE EXCHANGE, AS A REBUILD RATHER THAN A MOVE.
#
# p1_anatomy.md found the pathology and it is an exchange: the incumbent displaces 22 blocks for
# Z3 = 1009 with the worst payers at 98, 96, 90 and 84, while blocks carrying regret 6, 7, 10 and
# 16 -- with MORE area -- keep their first choice.  The wrong blocks were displaced.
#
# _bay_swap was built for precisely that and is unregistered because it found nothing: "147
# overlapping cross-bay pairs carry a positive preference gain, and not one swap survives ... the
# destination bay simply has no room for the block's whole residency."  Three other single-move
# mechanisms hit the same wall the same night.  A rigid exchange holds both residency windows
# fixed, so it needs a block-shaped hole that does not exist.
#
# OGC_XSWAP does not move two blocks.  It reads the mismatch out of the incumbent, corrects the
# preference signal that produced it -- boost each big payer's wanted bay, penalise the cheapest
# sitters already in that bay -- and hands it back to the SAME constructor.  Every block is then
# free to land somewhere else, which is the one thing the refuted move class could never offer.
#
# WHAT WOULD MAKE IT FAIL, named first.  A rebuild pays for the whole layout to buy one exchange,
# and the beam is the operator that produced every answer this study has recorded -- spending its
# slice on a biased rerun costs a clean draw.  The bias is also only as good as the incumbent it
# was read from: if the incumbent's displacements were forced by geometry rather than by order,
# the rewrite pushes against a wall and the draw is wasted.  The smoke was 712,040 and 669,732
# against a 605,585 control, but all three were taken while another queue held the box, so they
# decide nothing.
#
# JUDGED: six draws each on prob_1, alternating so any load lands on both arms; prob_3 and prob_16
# gate anything that wins.
set -u
cd /home/user/oraclemaster/research/exact_packer/session2/recon || exit 1
while [ "$(cat harness/CURRENT 2>/dev/null)" != "idle" ]; do sleep 15; done
echo xswap > harness/CURRENT
L=results/audit/xswap.log
mkdir -p results/audit; touch $L
ci(){ ( cd "$(git rev-parse --show-toplevel)" \
        && git add research/exact_packer/session2/recon/results/audit/xswap.log \
                  research/exact_packer/session2/recon/harness/CURRENT \
                  research/exact_packer/session2/recon/harness/xswap.sh \
        && git commit -q -m "in-flight: xswap $1" \
        && git push -q origin claude/repair-plan-model-1ig6it ) >/dev/null 2>&1; }
run(){ local tag="$1" p="$2" envs="$3"
    grep -vE '^# ' $L 2>/dev/null | grep -q "\[$tag\]" && return
    echo "# [$tag]" >> $L
    env $envs timeout 200 /usr/bin/python3.12 harness/run1.py myalgorithm $p 60 \
        "[$tag]" --data data/stage2 >> $L 2>&1 || echo "P$p [$tag] CRASH rc=$?" >> $L
    ci "$tag"; }
for rep in 1 2 3 4 5 6; do
  run "x.p1.off.r$rep" 1 "OGC_DEBUG=0"
  run "x.p1.on.r$rep"  1 "OGC_XSWAP=1"
done
for rep in 1 2 3; do
  for p in 3 16; do
    run "x.p$p.off.r$rep" $p "OGC_DEBUG=0"
    run "x.p$p.on.r$rep"  $p "OGC_XSWAP=1"
  done
done
echo "XSWAPDONE" >> $L
echo idle > harness/CURRENT
