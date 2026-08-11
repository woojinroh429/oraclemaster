#!/bin/bash
# THE BEAM'S PLACEMENT STEP IS BLIND TO BAY PREFERENCE, ON EVERY AXIS.
#
# _AXES carries prefw=0.0 in all six entries, and ogc_fast.cpp says what that means:
#
#     // Z3-aware bay offset: when prefw>0, bias placement toward the block's
#     // preferred bays ... trading contact (tight packing) against Z3 (bay preference).
#     // prefw==0 -> pure leftbottom.
#     if(prefw!=0.0 && bay<(int)bs.prefs.size()) bayoff += prefw*(mxpref-bs.prefs[bay]);
#
# So the cell-choice step maximises contact and ignores preference entirely.  This is NOT what
# w3mul does: w3mul scales w3 in the ROUTING rank (which bay a block is sent to), while prefw acts
# in the PLACEMENT search (which cell it takes once there).  The beam therefore constructs geometry
# and assignment together with the assignment half switched off at the point where geometry is
# actually decided.
#
# WHY THIS IS THE RIGHT THING TO TEST NOW.  Z3 carries 70-87% of stage2/prob_1's objective, CP-SAT
# proves Z3 = 387 admissible at exact per-slice area capacity against our 785-900, and every pass
# that tries to fix assignment AFTER placement is inert -- z3_reassign, ruin_tardy and _assign all
# return their input, because geometry is fixed by then and there is no freedom left.  prefw is the
# one place preference can enter WHILE geometry is still being decided.
#
# THE TRADE IS EXPLICIT IN THE CODE.  bayoff grows with the block's preference regret, so a high
# prefw will accept a looser pack to reach a better bay.  Looser packing means blocks that do not
# fit where they should, which returns as tardiness at 6,667 a unit on this instance -- the same
# trade brk makes (Z3 785->445 for Z1 2->22).  The sweep reports all three components so the trade
# is visible rather than assumed.
#
# UNIFORM RIG, as with the other two sweeps: DIRSET=0 with single-element AIMSET and MSET makes all
# four workers identical, contention constant, four draws per run, and prefw the only free variable.
set -u
cd /home/user/oraclemaster/research/exact_packer/session2/recon || exit 1
echo prefw > harness/CURRENT
L=results/audit/prefw.log
mkdir -p results/audit; touch $L
U="WORKERS=4 OGC_DIRSET=0 OGC_AIMSET=0.90 OGC_MSET=1 OGC_ORDER=lst OGC_W3MUL=1.0"
ci(){ ( cd "$(git rev-parse --show-toplevel)" \
        && git add research/exact_packer/session2/recon/results/audit/prefw.log \
                  research/exact_packer/session2/recon/harness/CURRENT \
                  research/exact_packer/session2/recon/harness/prefw.sh \
        && git commit -q -m "in-flight: prefw $1" \
        && git push -q origin claude/repair-plan-model-1ig6it ) >/dev/null 2>&1; }

run(){ # tag env
    local tag="$1"
    grep -vE '^# ' $L 2>/dev/null | grep -q "\[$tag\]" && return
    echo "# [$tag]" >> $L
    env $2 OGC_WSTAT=1 timeout 400 /usr/bin/python3.12 harness/run1.py myalgorithm 1 120 \
        "[$tag]" --data data/stage2 >> $L 2>&1 || echo "P1 [$tag] CRASH rc=$?" >> $L
    ci "$tag"
}

for rep in 1 2 3; do
  for P in 0.0 0.5 2.0 8.0 32.0; do
    run "pw.$P.r$rep" "$U OGC_PREFW=$P"
  done
done
echo "PREFWDONE" >> $L
echo idle > harness/CURRENT
