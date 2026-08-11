#!/bin/bash
# THE FIRST prefw SWEEP MEASURED NOTHING.  HERE IS THE ARITHMETIC THAT SAYS SO.
#
# lb_best scores a cell like this (ogc_fast.cpp):
#
#     double bayoff = (double)bay + prefw*(mxpref - bs.prefs[bay]);
#     double sc     = ((h*1e6 + wx)*1e4 + wy)*4.0 + bayoff;
#                   =  4e10*h  +  4e4*wx  +  4*wy  +  bayoff
#
# so the placement order is LEXICOGRAPHIC in (orient height, wasted-x, wasted-y, bayoff) and bay
# preference is the LAST tiebreak -- below a one-unit difference in y.  prob_1's median gap between
# a block's first and second choice is 40 preference units, so for preference to actually outrank
# geometry prefw has to be:
#
#     beat the (double)bay tiebreak      prefw ~ 0.05
#     beat one unit of wy   (4)          prefw ~ 0.1
#     beat one unit of wx   (4e4)        prefw ~ 1e3
#     beat one unit of height (4e10)     prefw ~ 1e9
#
# prefw.sh swept 0.5 / 2 / 8 / 32.  Every one of those sits between "beats y" and "cannot beat x",
# i.e. it only ever re-ordered cells that were already equal in height and x -- which is why the
# twelve-draw result looked like noise and why four of the cells landed on the 745,782 attractor.
#
# WHY IT MATTERS ON THIS INSTANCE, from the instance itself rather than from a knob.  Give every
# block its top choice and take the peak simultaneous bounding-box area:
#
#     bay0  cap 1911   peak 1078   56%    833 spare
#     bay1  cap  736   peak 1083  147%    347 over
#     bay2  cap  629   peak 1265  201%    636 over
#
# So Z3 > 0 is forced -- about 983 area units have to leave the two small bays at the peak -- and
# the only freedom left is WHICH blocks leave.  The incumbent sheds 22 blocks for a penalty of
# 1009, and its worst payers cost 98, 96, 90 and 84 each: it is shedding the most expensive blocks
# it can find, because the score above lets preference speak only after height, x and y have.
#
# WHAT WOULD MAKE IT FAIL, named first.  At prefw large enough to beat height, the rollout will
# take a tall wasteful orientation to stay in a preferred bay, packing gets looser, blocks stop
# fitting and the loss returns as tardiness at 6,667 a unit -- the brk trade again.  The sweep
# therefore spans the whole live range rather than guessing a point, and reports Z1 and Z3
# separately so a Z3 win bought with tardiness is visible instead of hidden in the total.
#
# UNIFORM RIG, as with the other sweeps: DIRSET=0 with single-element AIMSET and MSET makes the
# four workers identical, so contention is constant and prefw is the only free variable, and
# OGC_WSTAT=1 writes four draws per run instead of one.
set -u
cd /home/user/oraclemaster/research/exact_packer/session2/recon || exit 1
echo prefwbig > harness/CURRENT
L=results/audit/prefwbig.log
mkdir -p results/audit; touch $L
U="WORKERS=4 OGC_DIRSET=0 OGC_AIMSET=0.90 OGC_MSET=1 OGC_ORDER=lst OGC_W3MUL=1.0"
ci(){ ( cd "$(git rev-parse --show-toplevel)" \
        && git add research/exact_packer/session2/recon/results/audit/prefwbig.log \
                  research/exact_packer/session2/recon/harness/CURRENT \
                  research/exact_packer/session2/recon/harness/prefwbig.sh \
        && git commit -q -m "in-flight: prefwbig $1" \
        && git push -q origin claude/repair-plan-model-1ig6it ) >/dev/null 2>&1; }

run(){ # tag env
    local tag="$1"
    grep -vE '^# ' $L 2>/dev/null | grep -q "\[$tag\]" && return
    echo "# [$tag]" >> $L
    env $2 OGC_WSTAT=1 timeout 400 /usr/bin/python3.12 harness/run1.py myalgorithm 1 120 \
        "[$tag]" --data data/stage2 >> $L 2>&1 || echo "P1 [$tag] CRASH rc=$?" >> $L
    ci "$tag"
}

# Round one is a RANGE FINDER: one draw-set at each decade, to see where the knob starts biting
# and where it starts costing tardiness.  Replication comes after, on whatever survives.
for rep in 1 2 3; do
  for P in 0.0 1e2 1e3 1e4 1e5 1e7 1e9; do
    run "pb.$P.r$rep" "$U OGC_PREFW=$P"
  done
done
echo "PREFWBIGDONE" >> $L
echo idle > harness/CURRENT
