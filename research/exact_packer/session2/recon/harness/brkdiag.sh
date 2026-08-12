#!/bin/bash
# brk IS THE MULTI-BLOCK REASSIGNER WE ALREADY HAVE, AND ON prob_1 IT RETURNS NOTHING.
#
# bayrepack.py's own opening names the wall every other operator hits: "_balance moves ONE block to
# a bay that lowers the objective ... _z3_improve reassigns without re-placing.  The beam places
# greedily in dispatch order and never revisits.  Every one of them treats the existing arrangement
# as given, and the arrangement is the problem."  What brk does instead: "Take the bay under most
# pressure, lift EVERY block out of it, add the outsiders that would most improve the objective by
# entering, and hand the whole set to cranepack" -- a weighted set-packing search with the descent
# rule enforced pairwise, validated against Gurobi.
#
# That is exactly the move class p1_anatomy.md says prob_1 needs, and it is registered by default.
# OGC_OPSTAT on prob_1, single worker:
#
#     op     tried  seconds  %budget   gain
#     brk        1     13.3    24.3%      0
#
# A quarter of the budget, one call, nothing returned.  Two explanations and they lead opposite
# ways: the set-packing search does not FINISH in the slice it is given, or it finishes and the
# contested bay is already locally optimal.  If it is the first, prob_1's answer is here and the
# fix is budget, not a new operator.
#
# ARMS.  OGC_OPS restricts the roster, so "beam,brk" hands brk everything the beam does not take
# instead of the fifth it gets in a six-operator rotation; that is the direct test of whether more
# time changes its answer.  OGC_BRKFLOOR raises the smallest slice it will accept.  OGC_OPSTAT
# prints tried/seconds/gain per operator so the answer is read off the profile rather than inferred
# from the objective.
#
# WORKERS=1 so the profile is one worker's and not an average, and single draws because what is
# being read is the operator table, not a 2% difference in the total.
set -u
cd /home/user/oraclemaster/research/exact_packer/session2/recon || exit 1
while [ "$(cat harness/CURRENT 2>/dev/null)" != "idle" ]; do sleep 15; done
echo brkdiag > harness/CURRENT
L=results/audit/brkdiag.log
mkdir -p results/audit; touch $L
ci(){ ( cd "$(git rev-parse --show-toplevel)" \
        && git add research/exact_packer/session2/recon/results/audit/brkdiag.log \
                  research/exact_packer/session2/recon/harness/CURRENT \
                  research/exact_packer/session2/recon/harness/brkdiag.sh \
        && git commit -q -m "in-flight: brkdiag $1" \
        && git push -q origin claude/repair-plan-model-1ig6it ) >/dev/null 2>&1; }
run(){ local tag="$1" p="$2" tl="$3" envs="$4"
    grep -vE '^# ' $L 2>/dev/null | grep -q "\[$tag\]" && return
    echo "# [$tag]" >> $L
    env OGC_OPSTAT=1 WORKERS=1 $envs timeout 400 /usr/bin/python3.12 \
        harness/run1.py myalgorithm $p $tl "[$tag]" --data data/stage2 >> $L 2>&1 \
        || echo "P$p [$tag] CRASH rc=$?" >> $L
    ci "$tag"; }
run "d.p1.stock.60"    1 60  "OGC_DEBUG=0"
run "d.p1.brkonly.60"  1 60  "OGC_OPS=beam,brk"
run "d.p1.brkonly.120" 1 120 "OGC_OPS=beam,brk"
run "d.p1.brkonly.240" 1 240 "OGC_OPS=beam,brk"
run "d.p1.brkfloor.60" 1 60  "OGC_OPS=beam,brk OGC_BRKFLOOR=25"
run "d.p3.brkonly.60"  3 60  "OGC_OPS=beam,brk"
run "d.p3.stock.60"    3 60  "OGC_DEBUG=0"
echo "BRKDIAGDONE" >> $L
echo idle > harness/CURRENT
