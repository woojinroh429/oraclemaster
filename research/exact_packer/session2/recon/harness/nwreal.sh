#!/bin/bash
# RE-MEASURE THE SHIPPED GATE ON INSTANCES THAT ACTUALLY STAND IN FOR SOMETHING.
#
# nw = cpu-1 for timelimit <= 240 shipped on 37 pairs of prob_1 and prob_16 FROM data/stage2.
# HIDDEN_SET.md's analogue table is keyed to data/train, and the shapes confirm it exactly:
#
#     hidden shape          data/train                data/stage2 (what was measured)
#     P1  3 bays 100 blk    prob_2  (100, 3)          prob_1  = 150 blk, 3 bays -> P4's shape
#     P2  2 bays 150 blk    prob_8  (150, 2)          prob_16 = 300 blk, 5 bays -> nothing
#     P3  3 bays 200 blk    prob_9  (200, 3)
#     P4  3 bays 150 blk    prob_26 (150, 3)          the hidden max is 4 bays and 250 blocks, so
#     P5  4 bays 200 blk    prob_10/11/12 (200, 4)    a 5-bay 300-block instance stands in for no
#     P6  3 bays 250 blk    prob_37/38/39 (250, 3)    hidden problem at all
#
# So one of the two instances measured happens to carry P4's shape -- and P4 runs at 480 s, where
# the gate turns OFF and where that instance measured mean -2.36% with a WIDER span.  That is
# consistent with the gate.  The other stands in for nothing.  The real ladder:
#
#     P1   60 s   prob_2    gate ON      P4  480 s   prob_26        gate OFF
#     P2  120 s   prob_8    gate ON      P5  600 s   prob_10/11/12  gate OFF
#     P3  240 s   prob_9    gate ON      P6  900 s   prob_37/38/39  gate OFF
#
# ALL RUNS BELOW USE --data data/train.  Every earlier queue used data/stage2; the two sets share
# file names and share nothing else, so the logs must not be compared across them.
#
# THE BOUNDARY ITSELF IS ALREADY LUCKY.  240 s is P3's limit and 480 s is P4's, so the interval
# the measurements never covered contains no scored instance.  What is unverified is whether the
# EFFECT survives on the right shapes -- bay count and block count are exactly what a worker's
# search depth interacts with, so an effect measured on the wrong shapes transfers by assumption.
#
# WHAT IS BEING RUN, and why in this order.  The three gate-ON budgets first, each on its own
# analogue, because those are the cells where the shipped default now differs from what the
# previous submission did.  If the effect is absent or reversed there, the gate is shipping a
# change that buys nothing on anything that is scored.  P4 last, to confirm turning OFF at 480 s
# is right on the shape that actually runs at 480 s.
#
#     prob_2   60 s    P1     6 runs   ~ 12 min
#     prob_8  120 s    P2     6 runs   ~ 24 min
#     prob_9  240 s    P3     6 runs   ~ 48 min
#     prob_26 480 s    P4     6 runs   ~ 96 min
#
# THREE PAIRS PER CELL IS NOT ENOUGH TO SETTLE ONE, and that is deliberate: four cells at three
# pairs finds a reversal if there is one, and a cell that looks decided at three gets filled to
# five afterwards.  Tonight every claim written at n=2 or n=3 was overturned by the next draw --
# five times -- so nothing here gets called settled at three.
set -u
cd /home/user/oraclemaster/research/exact_packer/session2/recon || exit 1
echo nwreal > harness/CURRENT
L=results/audit/nwreal.log
mkdir -p results/audit; touch $L
ci(){ ( cd "$(git rev-parse --show-toplevel)" \
        && git add research/exact_packer/session2/recon/results/audit/nwreal.log \
                  research/exact_packer/session2/recon/harness/CURRENT \
                  research/exact_packer/session2/recon/harness/nwreal.sh \
        && git commit -q -m "in-flight: nwreal $1" \
        && git push -q origin claude/repair-plan-model-1ig6it ) >/dev/null 2>&1; }

run(){ # tag prob limit env
    local tag="$1"
    grep -vE '^# ' $L 2>/dev/null | grep -q "\[$tag\]" && return
    echo "# [$tag]" >> $L
    env $4 OGC_WSTAT=1 timeout $(( $3 * 2 + 120 )) /usr/bin/python3.12 harness/run1.py myalgorithm $2 $3 \
        "[$tag]" --data data/train >> $L 2>&1 || echo "P$2 [$tag] CRASH rc=$?" >> $L
    ci "$tag"
}

# gate-ON budgets, each on its own hidden analogue
for rep in 1 2 3; do
  run "P1.r$rep.p2.w4"   2   60 "WORKERS=4"
  run "P1.r$rep.p2.w3"   2   60 "WORKERS=3"
done
echo "== NWREAL P1 (prob_2 60s) done ==" >> $L
for rep in 1 2 3; do
  run "P2.r$rep.p8.w4"   8  120 "WORKERS=4"
  run "P2.r$rep.p8.w3"   8  120 "WORKERS=3"
done
echo "== NWREAL P2 (prob_8 120s) done ==" >> $L
for rep in 1 2 3; do
  run "P3.r$rep.p9.w4"   9  240 "WORKERS=4"
  run "P3.r$rep.p9.w3"   9  240 "WORKERS=3"
done
echo "== NWREAL P3 (prob_9 240s) done ==" >> $L
for rep in 1 2 3; do
  run "P4.r$rep.p26.w4" 26  480 "WORKERS=4"
  run "P4.r$rep.p26.w3" 26  480 "WORKERS=3"
done
echo "NWREALDONE" >> $L
echo idle > harness/CURRENT
