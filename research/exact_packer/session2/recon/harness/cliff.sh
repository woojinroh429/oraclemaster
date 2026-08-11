#!/bin/bash
# THREE INSTANCES RETURN THE SAFETY NET INSTEAD OF A SOLUTION, AND NOTHING WARNS.
#
# bugcheck ran the submission zip over all 40 practice instances at 20 s.  No crash, no infeasible
# cell -- and three answers are the _safe_sequential FLOOR:
#
#     P13  4,027,473,504   Z1 604,088   Z3 0
#     P23  4,109,379,277   Z1 616,369   Z3 0
#     P25  4,255,755,887   Z1 638,329   Z3 0
#
# Z3=0 with a vast Z1 is the floor's signature: every block takes its first-choice bay and the
# sequencing pays for it.  Real answers on these are in the tens of millions -- P13 returns
# 84,962,422 at 180 s -- so this is a ~50x loss on the instance, reported as feas=y with no signal.
#
# IT IS NOT CAUSED BY ANYTHING SHIPPED TODAY.  All three sit far outside the gate's [1.00, 1.30]
# peak_util window (P13 4.09, P23 2.79, P25 6.26), so RESFRAC never changes for them.  The archive
# shows the same floor at 180 s on one worker -- "beam wall=140.5s over 7 calls" and still the
# floor -- so the beam can burn an entire budget on these without ever completing a draw.
#
# WHAT THIS IS WORTH.  Everything measured today moves the band by single-digit per cent.  One
# hidden instance landing below this cliff costs about 4,700% on that instance.  Finding where the
# cliff is, is worth more than the rest of the day put together.
#
# ARM 1 -- WHERE IS THE CLIFF.  The three floor instances at 20 / 30 / 45 / 60 / 90 s.  If they
# clear at 30 s the exposure is small; if P25 still floors at 90 s it is not.
#
# ARM 2 -- DOES THE CPU CAP MAKE IT WORSE.  The beam's aim is split by worker parity: even wids run
# today's high aim, odd wids the low aim, and the roster note measures the low aim as worth -24.3%
# to -11.9% on exactly these large instances while costing +25.09% on prob_1.  Worker count
# therefore sets how many low-aim draws a big instance gets:
#
#     nw=7 (grader today, cores visible)   ->  3 low-aim workers
#     nw=3 (after the cap)                 ->  1 low-aim worker
#
# So the cap, which was justified on per-worker depth, may cut the sampling of the axis that
# carries these instances.  WORKERS=1/3/4/7 at 30 s on P13 and P25 measures it directly.  If nw=7
# clears the cliff where nw=3 does not, the cap is wrong and must come out of the submission.
set -u
cd /home/user/oraclemaster/research/exact_packer/session2/recon || exit 1
while [ "$(cat harness/CURRENT 2>/dev/null)" != "idle" ]; do sleep 15; done
echo cliff > harness/CURRENT
L=results/audit/cliff.log
S=/tmp/claude-0/-home-user-oraclemaster/55043662-747d-5eda-b837-388adc057292/scratchpad
mkdir -p results/audit; touch $L
ci(){ ( cd "$(git rev-parse --show-toplevel)" \
        && git add research/exact_packer/session2/recon/results/audit/cliff.log \
                  research/exact_packer/session2/recon/harness/CURRENT \
                  research/exact_packer/session2/recon/harness/cliff.sh \
        && git commit -q -m "in-flight: cliff $1" \
        && git push -q origin claude/repair-plan-model-1ig6it ) >/dev/null 2>&1; }
run(){ local tag="$1" p="$2" tl="$3" envs="$4"
    grep -vE '^# ' $L 2>/dev/null | grep -q "\[$tag\]" && return
    echo "# [$tag]" >> $L
    ( cd "$S/zt" && env $envs timeout $((tl+160)) /usr/bin/python3.12 harness/run1.py myalgorithm $p $tl \
        "[$tag]" --data data/stage2 ) >> $L 2>&1 || echo "P$p [$tag] CRASH rc=$?" >> $L
    ci "$tag"; }
# ARM 2 first: it can invalidate the submission, so it is the one that must not wait.
for w in 3 7 4 1; do
  run "w.p13.$w" 13 30 "WORKERS=$w"
  run "w.p25.$w" 25 30 "WORKERS=$w"
done
# ARM 1: where the cliff is, at the shipped worker count
for tl in 30 45 60 90; do
  for p in 13 23 25; do
    run "c.p$p.$tl" $p $tl ""
  done
done
echo "CLIFFDONE" >> $L
echo idle > harness/CURRENT
