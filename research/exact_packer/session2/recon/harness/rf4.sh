#!/bin/bash
# THE HARM CHECK FOR RESFRAC 0.05 ON THE FOUR IN-BAND INSTANCES NOBODY HAS RUN IT ON.
#
# gaterf settled P1 and P3, two of two each, against the pre-registered bar:
#
#                 P1                          P3
#     0.50 ship  556,718 (deterministic)   4,837,017 / 4,776,637
#     0.05 r1    537,403   -3.5%           4,721,428   -1.8%
#     0.05 r2    518,803   -6.8%           4,661,917   -3.0%
#
# and 0.05 is the only setting whose two P1 draws DIFFER -- every other value returns
# its own frozen number.  With a 3 s reserve the workers get 57 s instead of 29 and the
# search stops terminating early, which is why it reaches points the attractor set does
# not contain.
#
# But DIRGATE fires on six instances, and this has only been measured on two.  P7, P16,
# P27 and P33 would take the change unmeasured, and seven settings have failed to
# transfer between instances today -- including inside this very sweep, where P3's best
# value (0.15) is the one that costs P1 13.4%.
#
# WHAT WOULD MAKE IT FAIL, named first.  Cutting the reserve to 3 s starves the polish,
# and oppay measured pref returning between 16,669 and 874,532 depending on instance
# with nothing predicting which.  On P1 and P3 at 60 s the polish takes about a second,
# so there is nothing to starve; on P16 it took 18.5 s and returned 236,944, and on P27
# 22.6 s for 824,607.  Those two are the real risk and they are in this queue.
#
# JUDGED as the dirgate validation was: anything inside +-3% on one draw is no evidence
# either way; a firing instance moving several per cent the wrong way means the change
# does not ship.
set -u
cd /home/user/oraclemaster/research/exact_packer/session2/recon || exit 1
while [ "$(cat harness/CURRENT 2>/dev/null)" != "idle" ]; do sleep 15; done
echo rf4 > harness/CURRENT
L=results/audit/rf4.log
mkdir -p results/audit; touch $L
ci(){ ( cd "$(git rev-parse --show-toplevel)" \
        && git add research/exact_packer/session2/recon/results/audit/rf4.log \
                  research/exact_packer/session2/recon/harness/CURRENT \
                  research/exact_packer/session2/recon/harness/rf4.sh \
        && git commit -q -m "in-flight: rf4 $1" \
        && git push -q origin claude/repair-plan-model-1ig6it ) >/dev/null 2>&1; }
run(){ local tag="$1"
    grep -vE '^# ' $L 2>/dev/null | grep -q "\[$tag\]" && return
    echo "# [$tag]" >> $L
    env $3 timeout 220 /usr/bin/python3.12 harness/run1.py myalgorithm $2 60 \
        "[$tag]" --data data/stage2 >> $L 2>&1 || echo "P$2 [$tag] CRASH rc=$?" >> $L
    ci "$tag"; }
# P16 and P27 first: oppay says their polish actually works, so they carry the risk.
for p in 16 27 33 7; do
  run "r4.p$p.50" $p "WORKERS=4"
  run "r4.p$p.05" $p "WORKERS=4 OGC_RESFRAC=0.05"
done
echo "RF4DONE" >> $L
echo idle > harness/CURRENT
