#!/bin/bash
# BCAP HAS TO BE MEASURED ON THE CLOCK, BECAUSE THE DETERMINISTIC MODE CANNOT SEE IT.
#
# p1hunt ran BCAP 96 / 137 / 192 under OGC_WORKCAP and all three returned 492,458 to the digit.
# That is not "the knob does nothing": under a work cap the width controller is
# Bcur = (cap - work) / rem with per = 1, so the width is set by the CAP and never approaches the
# Bmax ceiling at all.  The one instrument that removed the noise is blind to this particular knob.
#
# So it goes back on the clock, where the noise is.  Six draws per arm rather than three, because
# prob_1's wall-clock value moved from 508k-518k this afternoon to 622k-680k tonight on an
# unchanged build -- the box slowed and the beam takes its width from elapsed().  Anything smaller
# than that drift needs the extra draws to show through.
#
# WHY IT IS WORTH THE CELLS.  The file records B=137 alone at -2.5% on prob_16 and -8.9% combined
# with axis 2, and notes separately that on prob_1 "the beam FINISHES: the salvage never runs and
# the lower aim only takes width away."  An instance whose beam completes is limited by width, not
# by time, which is exactly the shape where a higher ceiling buys search instead of costing draws.
#
# JUDGED: median of six, at the shipped worker count, against the shipped BCAP=96.  An arm ships
# only if it also holds on prob_3 and prob_16 -- prob_1 alone has produced four settings this study
# that reversed elsewhere.
set -u
cd /home/user/oraclemaster/research/exact_packer/session2/recon || exit 1
while [ "$(cat harness/CURRENT 2>/dev/null)" != "idle" ]; do sleep 15; done
echo bcapwall > harness/CURRENT
L=results/audit/bcapwall.log
mkdir -p results/audit; touch $L
ci(){ ( cd "$(git rev-parse --show-toplevel)" \
        && git add research/exact_packer/session2/recon/results/audit/bcapwall.log \
                  research/exact_packer/session2/recon/harness/CURRENT \
                  research/exact_packer/session2/recon/harness/bcapwall.sh \
        && git commit -q -m "in-flight: bcapwall $1" \
        && git push -q origin claude/repair-plan-model-1ig6it ) >/dev/null 2>&1; }
run(){ local tag="$1" p="$2" b="$3"
    grep -vE '^# ' $L 2>/dev/null | grep -q "\[$tag\]" && return
    echo "# [$tag]" >> $L
    env OGC_BCAP=$b timeout 200 /usr/bin/python3.12 harness/run1.py myalgorithm $p 60 \
        "[$tag]" --data data/stage2 >> $L 2>&1 || echo "P$p [$tag] CRASH rc=$?" >> $L
    ci "$tag"; }
# prob_1 six deep across the range
for rep in 1 2 3 4 5 6; do
  for b in 96 137 192 64; do
    run "b.p1.$b.r$rep" 1 $b
  done
done
# then the two that have to agree before anything ships
for rep in 1 2 3; do
  for b in 96 137 192; do
    run "b.p3.$b.r$rep" 3 $b
    run "b.p16.$b.r$rep" 16 $b
  done
done
echo "BCAPWALLDONE" >> $L
echo idle > harness/CURRENT
