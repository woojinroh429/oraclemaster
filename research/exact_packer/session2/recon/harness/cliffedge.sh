#!/bin/bash
# IS THE 40x FLOOR REACHABLE ON A SLOWER OR BUSIER GRADER THAN THIS BOX?
#
# THE MECHANISM, from myalgorithm.py's own comment at the MGATE injection:
#
#     "Each beam draw expands M times the states, so a draw costs multiples of what it did and an
#      instance that finished comfortably at M=1 may not finish at all.  When no worker completes,
#      the run returns _safe_sequential and the answer is roughly forty times worse -- silently,
#      with feas=y."
#
# and the table it was written from, prob_36 (peak_util 4.66), default against MSET=8:
#
#     20 s   100,393,761  ->  4,023,023,953   FLOOR
#     30 s    97,465,037  ->  4,023,023,953   FLOOR
#     45 s    86,052,164  ->     76,324,079   -11.3%
#     60 s    97,247,964  ->     76,886,831   -20.9%
#
# The gate therefore carries a budget floor, `float(timelimit) >= OGC_MGATET` with MGATET = 60.
# THAT FLOOR SITS ON THE EDGE OF WHAT WAS MEASURED, not clear of it: 45 s survived at -11.3% and
# 30 s was a catastrophe, so 60 s is the far end of the surviving range rather than a margin.
#
# WHY THAT MATTERS NOW.  "60 s is enough" was measured on THIS box: 4 cores, quiet, nw = 3.  The
# quantity that decides the cliff is not the budget, it is how much WORK the budget buys, and that
# depends on the grader's cores, its per-core speed, and whether other submissions share it.  The
# finals' per-instance time limits are unpublished (results/audit/wrong_budget.md: "I do not know
# the final's per-instance budget"), so a hidden instance sitting at exactly 60 s on a slower or
# contended machine is inside the failure mode, and the failure is SILENT -- feas=y, no warning,
# objective 40x.
#
# AND THE GATE IS NOT RARE.  peak_util computed over the 40 practice instances: 16 of 40 are at or
# above the 2.0 cutoff (prob_25 6.26, prob_36 4.66, prob_13 4.09, prob_39 3.79, prob_2 3.29,
# prob_5 3.15, prob_37 3.06, prob_18 2.83, prob_23 2.79, prob_28 2.38, prob_26 2.22, prob_14 2.16,
# prob_32 2.16, prob_11 2.14, prob_40 2.12, prob_6 2.05).  Forty percent of the practice set fires
# it, so several hidden instances should be expected to.
#
# WHAT THIS RUNS.  The extracted submission zip, at 60 s, on the five highest-peak_util instances,
# under increasing CPU contention, which is the closest available proxy for "a slower or busier
# machine".  Arms:
#
#     L0   no background load                          the shipped condition on a quiet box
#     L2   2 busy processes                            the box is oversubscribed by half
#     L4   4 busy processes                            every core contended
#     N4   4 busy processes, OGC_MGATE=0               the same contention with the gate OFF
#
# N4 is the one that turns a scare into a decision.  If the floor appears in L4 and NOT in N4, the
# cliff is MGATE's and raising OGC_MGATET is the fix.  If it appears in both, the cliff is the
# budget itself and MGATE is not the lever.  If it appears in neither, the floor is not reachable
# by contention at 60 s and this closes.
#
# WHAT WOULD MAKE THIS MISLEAD, named first.  CPU contention is not the same thing as a slower
# core: the scheduler still gives our processes a share, so heavy contention stretches wall time
# rather than shrinking the work done per second in the way a genuinely slower CPU would.  It is a
# proxy and it can only produce a LOWER bound on the risk -- if the floor appears under contention
# the risk is real, but not seeing it does not prove a slow grader is safe.  Second: the runs are
# timed out at 200 s, and under L4 a run may hit that timeout rather than the floor; a timeout is
# recorded as CRASH and read as a different failure, not as a pass.
#
# JUDGED, fixed before the run.  This queue adopts nothing; it looks for a catastrophe.
#   * A cell whose objective is more than 5x its L0 counterpart IS the floor.  Report it.
#   * The decision that follows a floor in L4-but-not-N4 is to raise OGC_MGATET, and that would
#     then need its own measurement -- it is not applied from this queue.
#   * No floor anywhere at 60 s under 4-way contention is reported as "not reachable this way",
#     never as "safe".
set -u
cd /home/user/oraclemaster/research/exact_packer/session2/recon || exit 1
. harness/lock.sh
lock_acquire cliffedge
S=/tmp/claude-0/-home-user-oraclemaster/55043662-747d-5eda-b837-388adc057292/scratchpad/subcheck
D="$PWD/data/stage2"
L=results/audit/cliffedge.log
mkdir -p results/audit; touch $L
BP=/tmp/cliffedge_burners.pid
burn_start(){ : > $BP
    local i; for i in $(seq 1 "$1"); do
        /usr/bin/python3.12 -c '
while True:
    pass' & echo $! >> $BP
    done; }
burn_stop(){ [ -f $BP ] && while read -r pid; do kill "$pid" 2>/dev/null; done < $BP; rm -f $BP; }
trap 'burn_stop' EXIT INT TERM
ci(){ ( cd "$(git rev-parse --show-toplevel)" \
        && git add research/exact_packer/session2/recon/results/audit/cliffedge.log \
                  research/exact_packer/session2/recon/harness/cliffedge.sh \
                  research/exact_packer/session2/recon/harness/CURRENT \
        && git commit -q -m "in-flight: cliffedge $1" \
        && git push -q origin claude/repair-plan-model-1ig6it ) >/dev/null 2>&1; }
run(){ local tag="$1" p="$2" nb="$3" ev="$4"
    grep -q "^# \[$tag\]" $L 2>/dev/null && return
    echo "# [$tag] burners=$nb $ev" >> $L
    burn_start "$nb"
    ( cd "$S" && env $ev timeout 200 /usr/bin/python3.12 grader2.py "$D/prob_$p.json" 60 ) \
        >> $L 2>&1 || echo "P$p [$tag] CRASH rc=$?" >> $L
    burn_stop
    ci "$tag"; }
for rep in 1 2; do
  for p in 25 36 13 39 2; do
    run "L0.p$p.r$rep" $p 0 "OGC_DUMMY=0"
    run "L2.p$p.r$rep" $p 2 "OGC_DUMMY=0"
    run "L4.p$p.r$rep" $p 4 "OGC_DUMMY=0"
    run "N4.p$p.r$rep" $p 4 "OGC_MGATE=0"
  done
done
echo "CLIFFEDGEDONE" >> $L
burn_stop
lock_release cliffedge
