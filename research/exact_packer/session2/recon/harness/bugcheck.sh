#!/bin/bash
# DOES THE SUBMISSION ZIP EVER RETURN AN INFEASIBLE OR MISSING ANSWER.
#
# Runs the ZIP'S OWN extracted contents -- its myalgorithm.py and its five compiled engines -- over
# all 40 practice instances, plus timelimit edges on the instance the gate fires on.  This is not a
# quality measurement; the only questions are "feasible" and "returns at all".
#
# WHY 20 s.  The gate fires at timelimit <= 60, so 20 s exercises the SAME branch the finals will,
# and 40 instances fit in a sitting.  The edges then cover what 20 s cannot: 5 s is below anything
# this study has ever run and is where a reserve of max(2.0, 0.05*5)=2.0 leaves the workers about
# two seconds; 300 s is above the gate's cut, so it also confirms the gate stays shut there.
set -u
cd /home/user/oraclemaster/research/exact_packer/session2/recon || exit 1
while [ "$(cat harness/CURRENT 2>/dev/null)" != "idle" ]; do sleep 15; done
echo bugcheck > harness/CURRENT
L=results/audit/bugcheck.log
S=/tmp/claude-0/-home-user-oraclemaster/55043662-747d-5eda-b837-388adc057292/scratchpad
mkdir -p results/audit; touch $L
ci(){ ( cd "$(git rev-parse --show-toplevel)" \
        && git add research/exact_packer/session2/recon/results/audit/bugcheck.log \
                  research/exact_packer/session2/recon/harness/CURRENT \
                  research/exact_packer/session2/recon/harness/bugcheck.sh \
        && git commit -q -m "in-flight: bugcheck $1" \
        && git push -q origin claude/repair-plan-model-1ig6it ) >/dev/null 2>&1; }
run(){ local tag="$1" p="$2" tl="$3"
    grep -vE '^# ' $L 2>/dev/null | grep -q "\[$tag\]" && return
    echo "# [$tag]" >> $L
    ( cd "$S/zt" && timeout $((tl+160)) /usr/bin/python3.12 harness/run1.py myalgorithm $p $tl \
        "[$tag]" --data data/stage2 ) >> $L 2>&1 || echo "P$p [$tag] CRASH rc=$?" >> $L
    ci "$tag"; }
# every instance, at a budget inside the gate's window
for p in $(seq 1 40); do run "all.p$p" $p 20; done
# timelimit edges on a firing instance and a non-firing one
for tl in 5 10 30 120 300; do
  run "tl.p1.$tl" 1 $tl
  run "tl.p2.$tl" 2 $tl
done
echo "BUGCHECKDONE" >> $L
echo idle > harness/CURRENT
