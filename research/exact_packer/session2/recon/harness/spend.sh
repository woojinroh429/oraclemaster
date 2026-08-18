#!/bin/bash
# THE GATE THROWS AWAY HALF THE CLOCK, AND SPENDING IT ON A LONGER SEARCH MAKES P1 WORSE.
#
# final.log, on the corrected engine:
#     P1  A (RESFRAC 0.50)  508,193 / 510,450 / 681,869   ran 30-31 s of 60
#     P1  B (RESFRAC 0.05)  571,668 / 571,668 / 571,668   ran 58 s of 60
#
# A leaves 29 of its 60 seconds unused -- reserve is 30 s, the workers get 29, and _z3_improve
# returns almost at once.  B hands those seconds to the workers and P1 gets WORSE, deterministically:
# three draws, identical objective and identical components.  A longer search on this instance walks
# into a worse basin, so the wasted time cannot be spent that way.
#
# THE OTHER WAY TO SPEND IT HAS NEVER BEEN TRIED.  The answer is a MINIMUM over draws, so a second
# independent attempt cannot lose -- `best` spans the rounds and a round only replaces the answer by
# beating it.  OGC_ROUNDS=2 at RESFRAC 0.50 splits a 29 s worker budget into two ~14 s rounds and
# takes the better.
#
# THE COMBINATION IS A GAP IN THE RECORD.  rounds05 swept ROUNDS on top of RESFRAC 0.05.  wdef's arm
# C was 0.05 + ROUNDS 2.  Neither touched 0.50 + ROUNDS 2, and both ran the stale engine that
# final.log has since shown moved the P1 baseline ~30%.
#
# WHAT WOULD MAKE IT FAIL, named first.  Two 14 s rounds are each half the depth of one 29 s round,
# and depth is what A's 29 s buys.  If P1's good A draws need the full 29 s to reach 508 k, halving
# it costs more than the second draw returns -- which is exactly what killed ROUNDS at 0.05, where
# the losses GREW as each worker got better.  The difference here is that A is not using the clock
# it already has, so the second round is funded from waste rather than from depth.
#
# JUDGED: three draws, paired against final.log's A cells on the same engine.  D ships over A only
# if it wins the ratio-mean AND does not lose P1.  E (three rounds) is a probe on P1 and P27 only.
set -u
cd /home/user/oraclemaster/research/exact_packer/session2/recon || exit 1
while [ "$(cat harness/CURRENT 2>/dev/null)" != "idle" ]; do sleep 15; done
echo spend > harness/CURRENT
L=results/audit/spend.log
mkdir -p results/audit; touch $L
ci(){ ( cd "$(git rev-parse --show-toplevel)" \
        && git add research/exact_packer/session2/recon/results/audit/spend.log \
                  research/exact_packer/session2/recon/harness/CURRENT \
                  research/exact_packer/session2/recon/harness/spend.sh \
        && git commit -q -m "in-flight: spend $1" \
        && git push -q origin claude/repair-plan-model-1ig6it ) >/dev/null 2>&1; }
run(){ local tag="$1"
    grep -vE '^# ' $L 2>/dev/null | grep -q "\[$tag\]" && return
    echo "# [$tag]" >> $L
    env $3 timeout 220 /usr/bin/python3.12 harness/run1.py myalgorithm $2 60 \
        "[$tag]" --data data/stage2 >> $L 2>&1 || echo "P$2 [$tag] CRASH rc=$?" >> $L
    ci "$tag"; }
for rep in 1 2 3; do
  for p in 1 3 27 16 7 33; do
    run "D.p$p.r$rep" $p "OGC_RESFRAC=0.50 OGC_ROUNDS=2"
  done
done
for rep in 1 2; do
  for p in 1 27; do
    run "E.p$p.r$rep" $p "OGC_RESFRAC=0.50 OGC_ROUNDS=3"
  done
done
echo "SPENDDONE" >> $L
echo idle > harness/CURRENT
