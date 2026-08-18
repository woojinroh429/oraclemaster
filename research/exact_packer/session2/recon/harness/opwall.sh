#!/bin/bash
# THE OPERATOR KNOBS ON THE CLOCK, BECAUSE THE DETERMINISTIC MODE CANNOT SEE THEM EITHER.
#
# p1hunt ran BCAP 64/96/137/192/256, PREFSEARCH and FINEFRAC under OGC_WORKCAP=5000 and every one
# returned 492,458 to the digit.  The reason is in ogc_fast.cpp's level loop: at that cap the beam
# runs out of work early, takes the salvage path -- greedy_contact_from on the best partial -- and
# the answer is that rollout.  The rollout does not read these knobs, so the whole sweep measured
# the salvage rather than the search.
#
# The mode is not useless: OGC_MCAND moved it 42.6% because `work += nbeam*M` changes work
# consumption directly, which is exactly the trade M makes.  Knobs that do not change work
# accumulation are invisible to it by construction.  That is a limit of the instrument, and the
# only way past it is the clock.
#
# ARMS, all previously untried on prob_1: PREFSEARCH (the roster argues for it and never measured
# it; opstat puts pref second in gain here), FINEFRAC 0.85 and 0.40 (task 13, open all study),
# Z1OP (an operator that is built, registered and then filtered out), BMULSET (per-axis width, the
# "third way" the BCAP note proposes and never measures).
#
# Six draws because prob_1 moved 508k -> 680k tonight on an unchanged build; three would not clear
# that.  prob_3 and prob_16 gate anything that wins, since four settings this study looked good on
# prob_1 and reversed elsewhere.
set -u
cd /home/user/oraclemaster/research/exact_packer/session2/recon || exit 1
while [ "$(cat harness/CURRENT 2>/dev/null)" != "idle" ]; do sleep 15; done
echo opwall > harness/CURRENT
L=results/audit/opwall.log
mkdir -p results/audit; touch $L
ci(){ ( cd "$(git rev-parse --show-toplevel)" \
        && git add research/exact_packer/session2/recon/results/audit/opwall.log \
                  research/exact_packer/session2/recon/harness/CURRENT \
                  research/exact_packer/session2/recon/harness/opwall.sh \
        && git commit -q -m "in-flight: opwall $1" \
        && git push -q origin claude/repair-plan-model-1ig6it ) >/dev/null 2>&1; }
run(){ local tag="$1" p="$2" envs="$3"
    grep -vE '^# ' $L 2>/dev/null | grep -q "\[$tag\]" && return
    echo "# [$tag]" >> $L
    env $envs timeout 200 /usr/bin/python3.12 harness/run1.py myalgorithm $p 60 \
        "[$tag]" --data data/stage2 >> $L 2>&1 || echo "P$p [$tag] CRASH rc=$?" >> $L
    ci "$tag"; }
for rep in 1 2 3 4 5 6; do
  run "o.p1.ctl.r$rep"   1 "OGC_DEBUG=0"
  run "o.p1.pref.r$rep"  1 "OGC_PREFSEARCH=1"
  run "o.p1.ff85.r$rep"  1 "OGC_FINEFRAC=0.85"
  run "o.p1.z1.r$rep"    1 "OGC_Z1OP=1"
done
for rep in 1 2 3; do
  for p in 3 16; do
    run "o.p$p.ctl.r$rep"  $p "OGC_DEBUG=0"
    run "o.p$p.pref.r$rep" $p "OGC_PREFSEARCH=1"
  done
done
echo "OPWALLDONE" >> $L
echo idle > harness/CURRENT
