#!/bin/bash
# P5 AND P6 CARRY THE SCORE AND HAVE NEVER BEEN MEASURED AT THEIR OWN BUDGETS.
#
# Reference scores from friend_ref/README.md give the scale of each hidden problem:
#
#     P1     11,280      P2     31,368      P3      93,395
#     P4  2,460,584      P5 10,128,108      P6  32,366,596
#
# P5 and P6 are three orders of magnitude above P1-P3.  Whatever the score is summed or ranked on,
# these two dominate the arithmetic, and neither has been run at 600 s or 900 s in this session.
# Everything measured tonight was 60-480 s on two instances that stand in for P4's shape and for
# nothing at all.
#
# THE GATE DOES NOT REACH THESE ANYWAY.  nw = cpu-1 fires only at timelimit <= 240, so P4/P5/P6 run
# exactly as the previous submission did.  That is precisely why they are worth measuring: they are
# the part of the score this session has never touched, and the first question is not whether the
# worker count helps there -- it is whether the run-to-run spread that this whole night was spent
# chasing even EXISTS there.
#
# WHAT THE ANALOGUES ALREADY SHOW.  P1 and P2 came back byte-identical over six draws each, Z1
# already 0, finishing at ~60% of their budget.  If P5 and P6 behave the same way, then the spread
# measured all night on stage-2 prob_1 and prob_16 is a property of those two instances and not of
# the hidden set, and no variance-reduction arm could ever have paid.  If instead they DO vary,
# that is the first honest sighting of the problem the user reported, at the budgets where it
# costs the most.
#
#     prob_10  600 s   P5   4 bays 200 blocks   3 draws w4 only   ~ 30 min
#     prob_37  900 s   P6   3 bays 250 blocks   3 draws w4 only   ~ 45 min
#
# w4 ONLY, DELIBERATELY.  The gate is off at these budgets, so w4 IS the shipped behaviour; three
# draws of it measure the spread of what will actually run.  Pairing against w3 here would answer a
# question nobody is asking and double the cost of the one that matters.
set -u
cd /home/user/oraclemaster/research/exact_packer/session2/recon || exit 1
echo nwbig > harness/CURRENT
L=results/audit/nwbig.log
mkdir -p results/audit; touch $L
ci(){ ( cd "$(git rev-parse --show-toplevel)" \
        && git add research/exact_packer/session2/recon/results/audit/nwbig.log \
                  research/exact_packer/session2/recon/harness/CURRENT \
                  research/exact_packer/session2/recon/harness/nwbig.sh \
        && git commit -q -m "in-flight: nwbig $1" \
        && git push -q origin claude/repair-plan-model-1ig6it ) >/dev/null 2>&1; }

run(){ # tag prob limit env
    local tag="$1"
    grep -vE '^# ' $L 2>/dev/null | grep -q "\[$tag\]" && return
    echo "# [$tag]" >> $L
    env $4 OGC_WSTAT=1 timeout $(( $3 * 2 + 180 )) /usr/bin/python3.12 harness/run1.py myalgorithm $2 $3 \
        "[$tag]" --data data/train >> $L 2>&1 || echo "P$2 [$tag] CRASH rc=$?" >> $L
    ci "$tag"
}

for rep in 1 2 3; do
  run "P5.r$rep.p10.w4" 10 600 "WORKERS=4"
done
echo "== NWBIG P5 (prob_10 600s) done ==" >> $L
for rep in 1 2 3; do
  run "P6.r$rep.p37.w4" 37 900 "WORKERS=4"
done
echo "NWBIGDONE" >> $L
echo idle > harness/CURRENT
