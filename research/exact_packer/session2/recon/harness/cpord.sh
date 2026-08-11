#!/bin/bash
# GIVE THE BEAM THE PLAN'S SCHEDULE, NOT JUST ITS BAYS.
#
# The cpanch grid's first replicate ended on the cell that matters:
#
#     ca.off.r1          515,188   Z1  25   Z3  543
#     ca.c1.00.t100.r1   (crash; measured separately at 90 s: Z1 41, Z3 641)
#     ca.c1.00.t300.r1 1,614,813   Z1 192   Z3  524
#     ca.c0.85.t100.r1   899,486   Z1  32   Z3 1118
#     ca.c0.85.t300.r1 1,580,588   Z1 137   Z3 1085
#     ca.c0.70.t100.r1   703,795   Z1  58   Z3  493
#     ca.c0.70.t300.r1 1,849,481   Z1 254   Z3  212     <-- Z3 = 212
#
# 212 against a project record of 441 and a plan that promised 217, so the BEAM CAN REALISE THE
# ASSIGNMENT.  600*212 = 127,200, which means Z1 near zero would put this instance at roughly
# 214,000 -- the target.  Everything that is wrong is now in Z1.
#
# And the toll cannot buy it back.  From t100 to t300 at the same de-rating, Z3 falls 281 (worth
# 168,600) and Z1 rises 196 (worth 1,306,732): an exchange rate of about eight tardiness units per
# preference unit.  So the toll axis is closed and the question is why obeying the plan's BAYS
# costs 254 units of tardiness when the plan itself schedules the same bays at Z1 = 0-1.
#
# THE PLAN'S TIMES ARE THROWN AWAY.  It reaches Z1 = 1 by making 37 blocks WAIT up to 9 units past
# their release; the beam never sees that, dispatches in its axis's own order, and has to discover
# the same seating by luck.  OGC_CPORD hands the schedule over in the only form the beam can use
# without being pinned: dispatch in planned-start order, every entry time still the beam's own
# choice.
#
# Dispatch order is the largest single effect measured in this session (2.03x between orders on
# one worker), which is exactly why it was held back from the first grid and is priced on its own
# here.
#
# WHAT WOULD MAKE IT FAIL, named first.  Planned-start order is close to release order, and
# release-then-due dispatch is the arm that was measured at +34% when _bayplan accidentally shipped
# it.  If planned-start is just release order with noise, this reproduces that loss.  The control
# arms are therefore the SAME toll and de-rating with CPORD off, so the order is the only variable.
set -u
cd /home/user/oraclemaster/research/exact_packer/session2/recon || exit 1
while [ "$(cat harness/CURRENT 2>/dev/null)" != "idle" ]; do sleep 20; done
echo cpord > harness/CURRENT
L=results/audit/cpord.log
mkdir -p results/audit; touch $L
ci(){ ( cd "$(git rev-parse --show-toplevel)" \
        && git add research/exact_packer/session2/recon/results/audit/cpord.log \
                  research/exact_packer/session2/recon/harness/CURRENT \
                  research/exact_packer/session2/recon/harness/cpord.sh \
        && git commit -q -m "in-flight: cpord $1" \
        && git push -q origin claude/repair-plan-model-1ig6it ) >/dev/null 2>&1; }

run(){ # tag env
    local tag="$1"
    grep -vE '^# ' $L 2>/dev/null | grep -q "\[$tag\]" && return
    echo "# [$tag]" >> $L
    env $2 OGC_WSTAT=1 timeout 400 /usr/bin/python3.12 harness/run1.py myalgorithm 1 120 \
        "[$tag]" --data data/stage2 >> $L 2>&1 || echo "P1 [$tag] CRASH rc=$?" >> $L
    ci "$tag"
}

BASE="WORKERS=4 OGC_CPANCH=20"
for rep in 1 2 3; do
  run "co.off.r$rep"          "WORKERS=4"
  # the Z3 = 212 cell, with and without the plan's order
  run "co.c70.t300.no.r$rep"  "$BASE OGC_CPCAP=0.70 OGC_CPANCHW=300"
  run "co.c70.t300.ord.r$rep" "$BASE OGC_CPCAP=0.70 OGC_CPANCHW=300 OGC_CPORD=1"
  # and the cheap-toll cell, where Z1 was only 58 to begin with
  run "co.c70.t100.no.r$rep"  "$BASE OGC_CPCAP=0.70 OGC_CPANCHW=100"
  run "co.c70.t100.ord.r$rep" "$BASE OGC_CPCAP=0.70 OGC_CPANCHW=100 OGC_CPORD=1"
done
echo "CPORDDONE" >> $L
echo idle > harness/CURRENT
