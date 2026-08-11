#!/bin/bash
# ONE QUESTION LEFT: WHY DOES A 248,467 PLAN REALISE AS 657,000?
#
# The de-rating axis is dead and took two readings with it.  planq.sh solved the plan alone, no
# beam, same 20 s budget the grid gave it:
#
#     cap    Z1(plan)  Z3(plan)  moved-off-top   w1Z1+w3Z3
#     1.00       1       403       16              248,467
#     0.90     278         0        0            1,853,426
#     0.85      74       995       23            1,090,358
#     0.80     446         0        0            2,973,482
#     0.70     631         0        0            4,206,877
#
# Below 1.00 CP-SAT cannot leave the trivial solution inside the budget -- Z3 = 0 with nothing
# moved is "everyone takes their first choice and waits".  OGC_CPCAP was measuring solver
# difficulty, not packing realism.
#
# So ca.c0.85's realised Z3 = 1118 was the PLAN's 995, not the beam deviating; and ca.c0.70.t300's
# Z3 = 212 had no CP-SAT content at all -- with a trivial plan the rewrite is just "+300 on your
# own top bay", i.e. a flat toll on the COUNT of displaced blocks.  The earlier reading that the
# beam had realised a good assignment there is withdrawn.
#
# That accidental arm is worth one number, so it is kept here as a reference: at the same toll the
# trivial top-choice target beat the real plan on Z3 (493 against 641), because the CP-SAT plan
# displaces sixteen blocks up front and the beam then adds its own forced displacements on top.
# And the toll axis by itself is monotonically bad on the total: 515,188 -> 703,795 -> 1,849,481
# at tolls 0, 100, 300.
#
# WHAT IS ACTUALLY BEING ASKED HERE.  At cap 1.00 the plan is Z1 = 1, Z3 = 403 and the beam
# realises Z1 = 41, Z3 = 641.  The plan reaches Z1 = 1 by making 37 blocks WAIT up to nine units
# past their release; the beam never sees those times, dispatches in its axis's own order, and has
# to rediscover the same seating by luck.  OGC_CPORD hands the schedule over in the only form that
# does not pin anything: dispatch in planned-start order, every entry time still the beam's choice.
#
# Dispatch order is the largest single effect measured this session (2.03x between orders on one
# worker), which is why it is priced on its own, paired against the identical cell with the order
# off so nothing else moves.
#
# WHAT WOULD MAKE IT FAIL, named first.  Planned-start order is close to release order, and
# release-then-due dispatch is the arm _bayplan accidentally shipped when it measured +34%.  If
# planned-start is release order with noise, this reproduces that loss and the direction is closed.
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

B="WORKERS=4 OGC_CPANCH=20 OGC_CPCAP=1.00"
for rep in 1 2 3; do
  run "co.off.r$rep"       "WORKERS=4"
  run "co.t100.no.r$rep"   "$B OGC_CPANCHW=100"
  run "co.t100.ord.r$rep"  "$B OGC_CPANCHW=100 OGC_CPORD=1"
  run "co.t300.no.r$rep"   "$B OGC_CPANCHW=300"
  run "co.t300.ord.r$rep"  "$B OGC_CPANCHW=300 OGC_CPORD=1"
done
echo "CPORDDONE" >> $L
echo idle > harness/CURRENT
