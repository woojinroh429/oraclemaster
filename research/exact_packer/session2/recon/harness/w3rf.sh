#!/bin/bash
# THE RESERVE AND THE W3 SURROGATE HAVE NEVER BEEN CROSSED, AND THE COMPONENTS SAY THEY INTERACT.
#
# Decomposing every firing instance's 0.50 -> 0.05 move with its own weights shows one shape:
# the extra worker time buys tardiness and PAYS IN BAYS.
#
#     P27  w1=3333 w3=533   Z1 112->135  +76,659   Z2 -5,495    Z3  649-> 935  +152,438   LOSES
#     P3   w1=3333 w3=533   Z1 206->122 -279,972   Z2 -19,502   Z3 7679->8024 +183,885    wins
#     P33  w1=6667 w3=200   Z1 131-> 91 -266,680   Z2 -2,961    Z3 2204->2580  +75,200    wins
#     P16  w1=13333 w3=250  Z1 205->172 -439,989   Z2 +1,773    Z3 4413->4367  -11,500    wins
#     P7   w1=13333 w3=150  Z1  56-> 48 -106,664   Z2 +3,549    Z3 2044->1955  -13,350    wins
#     P1   w1=6667 w3=600   Z1  20-> 34  +93,338   Z2 +4,947    Z3  674-> 478 -117,600    wins
#
# Z3 rises on P27, P3 and P33 and the winners simply out-earn it on Z1.  P27 is the one instance
# where Z1 goes the WRONG WAY as well -- more search time and a worse tardiness number -- which is
# the signature of converging harder onto a surrogate that is not the objective.
#
# AND THE GATE INSTALLS EXACTLY THAT SURROGATE.  OGC_W3MUL=0.5 halves the bay term during search
# while the score charges full w3.  At the 30 s reserve the workers never got far enough for the
# bias to matter; at 3 s they get 57 s to pursue it.  So the reserve did not create this cost, it
# EXPOSED it -- and the knob that would remove it has been pinned at 0.5 through every sweep today.
#
# P3 AND P27 SHARE WEIGHTS EXACTLY (w1=3333, w2=7, w3=533, 200 blocks) and land on opposite sides,
# so the weight class is not the separator and this is not a weights story.  It is about how far
# the biased search runs before it is stopped.
#
# ARMS.  RESFRAC pinned at 0.05 -- that part is settled -- and W3MUL swept 0.75 and 1.0 against the
# shipped 0.5, on all six.  1.5 goes on P27 and P1 only, as a probe: if halving w3 hurts, over-
# weighting it may buy the bays back outright, and P1 is the instance that must not pay for it.
#
# WHAT WOULD MAKE IT FAIL, named first.  dirgate measured the three knobs as NON-INDEPENDENT --
# the parts sum to -9.4% while the combination beats -13% -- with the stated mechanism that
# w3mul=0.5 leaves preference for z3_reassign to collect.  If that is right, restoring w3 removes
# the very slack the gate's win is made of, and all six get worse together.  That is a clean
# outcome and it closes the arm.
#
# JUDGED, fixed before the run: an arm replaces the shipped 0.5 only if the band's absolute sum
# improves on it AND no instance that currently wins flips to a loss.  Rescuing P27 alone is not
# enough -- it is one instance and the five winners carry the case.
set -u
cd /home/user/oraclemaster/research/exact_packer/session2/recon || exit 1
while [ "$(cat harness/CURRENT 2>/dev/null)" != "idle" ]; do sleep 15; done
echo w3rf > harness/CURRENT
L=results/audit/w3rf.log
mkdir -p results/audit; touch $L
ci(){ ( cd "$(git rev-parse --show-toplevel)" \
        && git add research/exact_packer/session2/recon/results/audit/w3rf.log \
                  research/exact_packer/session2/recon/harness/CURRENT \
                  research/exact_packer/session2/recon/harness/w3rf.sh \
        && git commit -q -m "in-flight: w3rf $1" \
        && git push -q origin claude/repair-plan-model-1ig6it ) >/dev/null 2>&1; }
run(){ local tag="$1"
    grep -vE '^# ' $L 2>/dev/null | grep -q "\[$tag\]" && return
    echo "# [$tag]" >> $L
    env $3 timeout 220 /usr/bin/python3.12 harness/run1.py myalgorithm $2 60 \
        "[$tag]" --data data/stage2 >> $L 2>&1 || echo "P$2 [$tag] CRASH rc=$?" >> $L
    ci "$tag"; }

# P27 first -- it is the instance the hypothesis is about, and if restoring w3 does not move it
# the mechanism is wrong and the rest is only a cost check.
for m in 1.0 0.75 1.5; do
  run "w.p27.$m" 27 "WORKERS=4 OGC_RESFRAC=0.05 OGC_W3MUL=$m"
done
# then P1, which must not pay for it, including the 1.5 probe
for m in 1.0 0.75 1.5; do
  run "w.p1.$m" 1 "WORKERS=4 OGC_RESFRAC=0.05 OGC_W3MUL=$m"
done
# then the remaining four winners at the two serious values
for m in 1.0 0.75; do
  for p in 3 16 33 7; do
    run "w.p$p.$m" $p "WORKERS=4 OGC_RESFRAC=0.05 OGC_W3MUL=$m"
  done
done
echo "W3RFDONE" >> $L
echo idle > harness/CURRENT
