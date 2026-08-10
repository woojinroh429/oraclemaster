#!/bin/bash
# THE ONE OPERATOR THAT LIFTS THE BLOCKS THAT ARE IN THE WAY.
#
# Tonight's Z3 work closed on a specific obstruction.  CP-SAT plans 15-19 bay moves at exact
# per-time-slice area capacity and promises Z3 821 -> 387 on prob_1; `_regroup` empties every
# mover first, so the plan's own interlock is gone, and still realises 1 of 15.  The movers are
# blocked by the blocks that STAY.  Area feasibility is necessary and nowhere near sufficient,
# and no pass in the roster can move a block that is not itself moving:
#
#     _balance      moves ONE block, and P3 proved that neighbourhood empty there
#     _z3_improve   reassigns without re-placing; single moves and two-block swaps only
#     _assign       proposes globally, realises one block at a time, and overruns its slot
#     the beam      places greedily in dispatch order and never revisits
#
# bayrepack is the exception.  It takes the bay under most pressure, lifts EVERY block out of it,
# adds the outsiders that would most improve the objective by entering, and hands the whole set to
# cranepack -- weighted set packing over (orientation, x, y, entry) columns with the crane descent
# rule enforced pairwise, validated against Gurobi earlier in this project.  Weights are objective
# units, so a resident carries what evicting it would cost and an outsider what admitting it would
# gain.  That is exactly the move `_regroup` could not make.
#
# Its own note says the gap it was built for is not an area gap: on P3 the capacity-aware bound is
# 36,765 against a best of 87,560, bay 0's first-choice demand is 0.48 of cells x horizon, and the
# bay runs at 54% peak occupancy while the bound assumed 100%.  What refuses the blocks is
# fragmented descent columns, not room -- the same thing that refused _regroup's 14 of 15.
#
# WHY IT IS OFF.  Not because it lost.  It is the most expensive operator in the roster (floor
# 8.0 s against 0.5-3.0) and it was switched off deliberately to be measured on the hidden set,
# which never happened.  Its entire record is six instances at one cell each: P2 and P6 won, P13
# and P26 lost, P4 and P20 tied.  Six coin flips.
#
# WHAT WOULD REFUTE IT.  The 8 s floor means every probe costs 8 s of a worker, and OGC_OPSTAT
# showed what that class of probe does to prob_1 -- bay and z1 took 21.3% of the budget for zero
# gain.  If brk pays nothing here it is worse than bay, because it costs more to find out.  So
# the queue reads OPSTAT as well as the objective: seconds taken, gain returned.
set -u
cd /home/user/oraclemaster/research/exact_packer/session2/recon || exit 1
echo brk > harness/CURRENT
L=results/audit/brk.log
mkdir -p results/audit; touch $L
ci(){ ( cd "$(git rev-parse --show-toplevel)" \
        && git add research/exact_packer/session2/recon/results/audit/brk.log \
                  research/exact_packer/session2/recon/harness/CURRENT \
        && git commit -q -m "in-flight: brk $1" \
        && git push -q origin claude/repair-plan-model-1ig6it ) >/dev/null 2>&1; }
run(){ local tag="$1"
    grep -vE '^# ' $L 2>/dev/null | grep -q "\[$tag\]" && return
    echo "# [$tag]" >> $L
    env $4 OGC_WSTAT=1 OGC_OPSTAT=1 timeout $(( $3 * 4 )) /usr/bin/python3.12 harness/run1.py myalgorithm $2 $3 \
        "[$tag]" --data data/stage2 >> $L 2>&1 || echo "P$2 [$tag] CRASH rc=$?" >> $L
    ci "$tag"
}
for rep in 1 2 3; do
  for p in 1 3; do
    run "r$rep.p$p.off" $p 240 ""
    run "r$rep.p$p.brk" $p 240 "OGC_BRK=1"
  done
done
echo "== BRK priority done ==" >> $L
for rep in 1 2; do
  for p in 16 20 24; do
    run "r$rep.p$p.off" $p 240 ""
    run "r$rep.p$p.brk" $p 240 "OGC_BRK=1"
  done
done
echo "BRKDONE" >> $L
echo idle > harness/CURRENT
