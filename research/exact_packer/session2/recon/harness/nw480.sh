#!/bin/bash
# THE ONE GAP IN THE SHIPPED CHANGE: IT WAS NEVER MEASURED AT THE BUDGET THAT CARRIES THE SCORE.
#
# nw = cpu - 1 shipped on 23 pairs at 60 / 120 / 240 s.  The worst draw improved in 6 of 6 cells
# and that is why it went out.  But friend_ref/README.md records the reference submission running
# "close to the full ~500 s budget", so the instances worth the most points are solved at roughly
# twice the longest budget any of this covers.
#
# WHY THE EXTRAPOLATION IS NOT FREE, even though the mechanism is instance-independent.  The
# parent being a fifth runnable process on four cores does not depend on the budget either, so
# the direction should hold.  What can change with budget is the SIZE of the other term: three
# workers is a minimum over three draws instead of four, and that cost is paid once per run
# regardless of length, while the depth benefit is bounded by how much depth the budget can
# absorb.  prob_16 at 240 s already showed the mean crossing to w4 (+0.96%) while the worst draw
# still improved (-6.1%).  If that crossing widens at 480 s the shipped default is wrong for the
# late instances, which are exactly the expensive ones.
#
# WHAT WOULD CHANGE THE DECISION.  The worst draw is the quantity the tier is set by, so:
#
#     worst still better at 480 s      -> shipped default stands, gap closed
#     worst worse at 480 s             -> gate on timelimit, which is an argument to algorithm()
#                                         and needs nothing predicted
#
# COST.  A pair is 16 minutes.  Three pairs on prob_1 then two on prob_16 is about 80 minutes.
# prob_1 first: it carries the wider control band at long budgets (33.5% at 240 s) and so is the
# cell where a difference is hardest to claim -- if it survives there it survives.
set -u
cd /home/user/oraclemaster/research/exact_packer/session2/recon || exit 1
echo nw480 > harness/CURRENT
L=results/audit/nw480.log
mkdir -p results/audit; touch $L
ci(){ ( cd "$(git rev-parse --show-toplevel)" \
        && git add research/exact_packer/session2/recon/results/audit/nw480.log \
                  research/exact_packer/session2/recon/harness/CURRENT \
                  research/exact_packer/session2/recon/harness/nw480.sh \
        && git commit -q -m "in-flight: nw480 $1" \
        && git push -q origin claude/repair-plan-model-1ig6it ) >/dev/null 2>&1; }

run(){ # tag prob limit env
    local tag="$1"
    grep -vE '^# ' $L 2>/dev/null | grep -q "\[$tag\]" && return
    echo "# [$tag]" >> $L
    env $4 OGC_WSTAT=1 timeout $(( $3 * 2 + 120 )) /usr/bin/python3.12 harness/run1.py myalgorithm $2 $3 \
        "[$tag]" --data data/stage2 >> $L 2>&1 || echo "P$2 [$tag] CRASH rc=$?" >> $L
    ci "$tag"
}

for rep in 1 2 3; do
  run "b480.r$rep.p1.w4" 1 480 "WORKERS=4"
  run "b480.r$rep.p1.w3" 1 480 "WORKERS=3"
done
echo "== NW480 prob_1 done ==" >> $L
for rep in 1 2; do
  run "b480.r$rep.p16.w4" 16 480 "WORKERS=4"
  run "b480.r$rep.p16.w3" 16 480 "WORKERS=3"
done
echo "NW480DONE" >> $L
echo idle > harness/CURRENT
