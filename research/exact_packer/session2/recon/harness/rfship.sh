#!/bin/bash
# VALIDATE THE SHIPPED RESFRAC 0.05 -- ON THE INSTANCES IT TOUCHES, AND ON THE ONES IT MUST NOT.
#
# The change is one string literal inside `if _lo <= _pu <= _thr and timelimit <= _tlim`, so the
# question splits cleanly in two, and peak_util over all 40 practice instances says exactly where
# the split falls:
#
#     FIRES  P1 1.016   P3 1.182   P27 1.132   P16 1.231   P33 1.236   P7 1.271
#     nearest misses    P21 0.999995 (five millionths under)   P4 1.353   P34 0.985   P12 0.939
#
# Six fire; the other thirty-four take the same code path they always did.
#
# PART A -- THE NO-HARM CLAIM, MEASURED RATHER THAN ASSERTED.  myalg_prev is HEAD's module, byte
# for byte what the delivered zip was built from.  Running it and the edited one against the same
# non-firing instance must return the same objective AND the same Z1/Z2/Z3, not merely a similar
# total.  P21 is the cell that matters most: at 0.999995 it is the closest any practice instance
# comes to the gate without entering it, so if a boundary is going to be crossed by accident it
# crosses there.  P4 covers the other side, P2 and P9 cover far outside.
#
# PART B -- THE SIX FIRING INSTANCES, WITH THE DRAWS THEY WERE DECIDED ON.  rf4 judged P7, P16,
# P27 and P33 on ONE draw each, and one draw is what has misled this study repeatedly: SHARE 0.3's
# -1.4% did not reproduce, and three of the P1 arms return frozen numbers that hide their own
# variance.  Two further replicates per cell puts each of the four on three draws, and adds a third
# to P1 and P3.
#
# WHAT WOULD MAKE IT FAIL, named first.  If the four single-draw wins were draws rather than
# effects, the replicates regress toward the control and the band goes from 5-1 to something that
# does not justify P27's 30.6%.  P16 and P33 carry most of the claimed absolute gain (-449,716 and
# -194,441 of the -671,490), so either of them collapsing takes the case with it.
#
# JUDGED, fixed before the run: 0.05 ships if it is below control on at least four of the six
# instances counting each instance by its three-draw median, and if the median absolute sum over
# the six stays negative.  Part A is judged separately and absolutely -- any non-firing instance
# whose components differ at all stops the ship regardless of Part B.
set -u
cd /home/user/oraclemaster/research/exact_packer/session2/recon || exit 1
while [ "$(cat harness/CURRENT 2>/dev/null)" != "idle" ]; do sleep 15; done
echo rfship > harness/CURRENT
L=results/audit/rfship.log
mkdir -p results/audit; touch $L
ci(){ ( cd "$(git rev-parse --show-toplevel)" \
        && git add research/exact_packer/session2/recon/results/audit/rfship.log \
                  research/exact_packer/session2/recon/harness/CURRENT \
                  research/exact_packer/session2/recon/harness/rfship.sh \
        && git commit -q -m "in-flight: rfship $1" \
        && git push -q origin claude/repair-plan-model-1ig6it ) >/dev/null 2>&1; }
run(){ local tag="$1" mod="$2" p="$3" envs="$4"
    grep -vE '^# ' $L 2>/dev/null | grep -q "\[$tag\]" && return
    echo "# [$tag]" >> $L
    env $envs timeout 220 /usr/bin/python3.12 harness/run1.py $mod $p 60 \
        "[$tag]" --data data/stage2 >> $L 2>&1 || echo "P$p [$tag] CRASH rc=$?" >> $L
    ci "$tag"; }

# PART A first: it is absolute, and if it fails nothing in part B matters.
echo "## PART A -- non-firing instances must be identical between HEAD and the edit" >> $L
for p in 21 4 2 9 34; do
  run "a.p$p.prev" myalg_prev  $p "WORKERS=4"
  run "a.p$p.new"  myalgorithm $p "WORKERS=4"
done

# PART B: the four one-draw instances first, heaviest contributor first.
echo "## PART B -- firing instances, three draws each" >> $L
for rep in 2 3; do
  for p in 16 33 7 27; do
    run "b.p$p.50.r$rep" myalgorithm $p "WORKERS=4 OGC_RESFRAC=0.50"
    run "b.p$p.05.r$rep" myalgorithm $p "WORKERS=4 OGC_RESFRAC=0.05"
  done
done
# and a third draw for the two that already have two
for p in 1 3; do
  run "b.p$p.50.r3" myalgorithm $p "WORKERS=4 OGC_RESFRAC=0.50"
  run "b.p$p.05.r3" myalgorithm $p "WORKERS=4 OGC_RESFRAC=0.05"
done
echo "RFSHIPDONE" >> $L
echo idle > harness/CURRENT
