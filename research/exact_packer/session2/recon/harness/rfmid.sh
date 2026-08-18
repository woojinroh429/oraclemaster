#!/bin/bash
# FIND THE RESERVE THAT KEEPS THE WINS AND COSTS P27 LESS.
#
# rf4 left the band at 6-1: five instances gain 2.4-14.7% at RESFRAC 0.05 and P27 loses 30.6%.
# Net over the practice band is -671,490 absolute, but a 30% loss on any instance is worth trying
# to avoid, and the middle of the range was never measured on P27.
#
#     P1    0.50  556,718   0.30  631,046 (+13.4%)  0.15  631,046 (+13.4%)  0.05  537,403 (-3.5%)
#     P27   0.50  729,804   0.30      ?             0.15      ?             0.05  953,406 (+30.6%)
#
# P1's win is a CLIFF at 0.05 -- 0.15 and 0.30 both return the same frozen 631,046.  P27 has only
# been seen at the two ends.  So the open question is whether there is a value where P1 is still
# past its cliff and P27 has not yet fallen off its own.
#
# WHY THE CLIFF EXISTS, and why an absolute floor might be the better shape.  At a 60 s limit the
# reserve is 30 s at 0.50 and 3 s at 0.05, and oppay measured what the polish actually spends:
# about a second on P1 and P3, 18.5 s on P16, 22.6 s on P27.  A FRACTION cannot express that -- it
# gives the instances that need nothing the same share as the one that needs twenty seconds.  A
# floor can: reserve = max(F seconds, 0.05 * limit) hands the workers everything above F and still
# leaves P27 something to polish with.
#
# ARMS.  OGC_RESFRAC alone cannot express a floor, so the floor is emulated by picking the fraction
# that yields F seconds at this budget: at 60 s, 0.10 = 6 s, 0.15 = 9 s, 0.20 = 12 s.  If a floor
# is what works, the winning fraction here converts directly into `reserve = max(F, 0.05*limit)`
# in the gate, which is budget-independent and is what would actually ship.
#
# WHAT WOULD MAKE IT FAIL, named first.  P1's 0.15 and 0.30 cells returned the identical frozen
# 631,046, so its cliff may be very close to 0.05 -- in which case any reserve big enough to help
# P27 is big enough to lose P1, and the two cannot be satisfied at once.  That is a real possible
# answer and it means shipping 0.05 and accepting P27, or shipping nothing.
set -u
cd /home/user/oraclemaster/research/exact_packer/session2/recon || exit 1
while [ "$(cat harness/CURRENT 2>/dev/null)" != "idle" ]; do sleep 15; done
echo rfmid > harness/CURRENT
L=results/audit/rfmid.log
mkdir -p results/audit; touch $L
ci(){ ( cd "$(git rev-parse --show-toplevel)" \
        && git add research/exact_packer/session2/recon/results/audit/rfmid.log \
                  research/exact_packer/session2/recon/harness/CURRENT \
                  research/exact_packer/session2/recon/harness/rfmid.sh \
        && git commit -q -m "in-flight: rfmid $1" \
        && git push -q origin claude/repair-plan-model-1ig6it ) >/dev/null 2>&1; }
run(){ local tag="$1"
    grep -vE '^# ' $L 2>/dev/null | grep -q "\[$tag\]" && return
    echo "# [$tag]" >> $L
    env $3 timeout 220 /usr/bin/python3.12 harness/run1.py myalgorithm $2 60 \
        "[$tag]" --data data/stage2 >> $L 2>&1 || echo "P$2 [$tag] CRASH rc=$?" >> $L
    ci "$tag"; }

# P27 first: it is the instance being rescued, and if it does not recover at any of these
# the arm is over before P1 needs re-running.
for v in 0.20 0.15 0.10; do
  run "m.p27.$v" 27 "WORKERS=4 OGC_RESFRAC=$v"
done
# then P1 at the two that could still clear its cliff
for v in 0.10 0.08; do
  run "m.p1.$v" 1 "WORKERS=4 OGC_RESFRAC=$v"
done
# and P16 / P33 / P7 at whichever value P27 liked, to confirm the wins survive
for v in 0.10; do
  for p in 16 33 7 3; do
    run "m.p$p.$v" $p "WORKERS=4 OGC_RESFRAC=$v"
  done
done
echo "RFMIDDONE" >> $L
echo idle > harness/CURRENT
