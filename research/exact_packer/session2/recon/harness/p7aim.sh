#!/bin/bash
# prob_7 LEAVES 46% OF ITS BEAM SLICE UNUSED, AND NOTHING IN THE BUILD NOTICES.
#
# BEAMSTAT, shipped defaults, one run each -- the beam's own report:
#
#     instance  blocks  level   salv  used
#     prob_1     150    1.00     0    0.86-0.87
#     prob_3     200    1.00     0    0.89-0.90
#     prob_16    300    1.00     0    0.87-0.90
#     prob_7     150    1.00     0    0.54-0.55      <-- alone
#     prob_13    300    0.18     1    0.91
#
# prob_7 COMPLETES every beam (level=1.00, salv=0) and finishes having spent barely half its
# slice, on an instance with the same 150 blocks and 3 bays as prob_1.  capped=0 everywhere, so
# the width ceiling OGC_BCAP is not what bounds it -- the per-level controller
# Bcur = min(Bmax, left/(per*rem)) is sizing the beam too narrow, it runs out of levels early, and
# the remaining 46% goes to repair operators that OPSTAT has repeatedly measured returning zero.
#
# NOTHING IN THE BUILD CAN CATCH THIS.  _adapt_aim raises the aim only on beam_width_capped() and
# lowers it only on beam_salvaged(); prob_7 is 0 on both, so neither branch fires and the aim never
# moves.  Its docstring explains why the used-fraction test was rejected -- "a beam that finishes
# always reports having spent almost exactly its aim, at 0.10 as much as at 0.90" -- and prob_7 is
# the counterexample: it finishes and reports 0.54 while prob_1 reports 0.87 on the same defaults.
#
# WHY THIS INSTANCE.  A competitor reports that reducing prob_7 moved their hidden P1 a long way.
# p7gate then found our prob_7 is dominated by draw luck -- its A arm spans 18.6%, 763,997 to
# 906,265 -- which is what an under-powered beam followed by a lottery of repairs looks like.  If
# the beam is running at half strength there, that is both the explanation and the fix.
#
# THE KNOB.  OGC_AIMSET is the per-worker beam aim, default "0.90,0.10" indexed by wid%2 -- half
# the pool aims to spend 90% of its slice on the beam and half aims for 10%.  On prob_7 neither
# half lands anywhere near its aim.
#
# ARMS:
#     A  0.90,0.10   shipped
#     B  0.90,0.90   both halves aim high -- costs the portfolio's low-aim diversity
#     C  0.99,0.50   raise the ceiling and lift the floor, keeping the two halves distinct
#
# WHAT WOULD MAKE IT FAIL, named first.  The 0.10 aim is not waste by default -- it is the cheap
# half of a portfolio whose whole value is spread, and results/audit/workers.md records that one
# half supplies 92-100% of the minima with WHICH half being instance-dependent.  If prob_7's
# minima come from the low-aim workers, B and C destroy the thing that was winning.  prob_1 is
# carried as the control precisely because its beam already spends 0.87 and should therefore be
# unaffected -- if prob_1 MOVES, the arm is changing something other than what this is about.
#
# JUDGED, fixed before the run: paired ratio within replicate, three replicates, four instances.
# prob_7 decides it; prob_1 must not regress; prob_27 and prob_33 are the rest of DIRGATE's set.
set -u
cd /home/user/oraclemaster/research/exact_packer/session2/recon || exit 1
. harness/lock.sh
lock_acquire p7aim
L=results/audit/p7aim.log
mkdir -p results/audit; touch $L
ci(){ ( cd "$(git rev-parse --show-toplevel)" \
        && git add research/exact_packer/session2/recon/results/audit/p7aim.log \
                  research/exact_packer/session2/recon/harness/CURRENT \
                  research/exact_packer/session2/recon/harness/p7aim.sh \
        && git commit -q -m "in-flight: p7aim $1" \
        && git push -q origin claude/repair-plan-model-1ig6it ) >/dev/null 2>&1; }
run(){ local tag="$1" p="$2" aim="$3" _s _e
    grep -vE '^# ' $L 2>/dev/null | grep -q "\[$tag\]" && return
    echo "# [$tag]" >> $L
    _s=$(date +%s.%N)
    env OGC_AIMSET="$aim" OGC_BEAMSTAT=1 OGC_WSTAT=1 timeout 200 /usr/bin/python3.12 \
        harness/run1.py myalgorithm $p 60 "[$tag]" --data data/stage2 >> $L 2>&1 \
        || echo "P$p [$tag] CRASH rc=$?" >> $L
    _e=$(date +%s.%N)
    echo "# WALL [$tag] $(awk -v a="$_s" -v b="$_e" 'BEGIN{printf "%.2f", b-a}')" >> $L
    ci "$tag"; }
for rep in 1 2 3; do
  for p in 7 1 27 33; do
    run "A.p$p.r$rep" $p "0.90,0.10"
    run "B.p$p.r$rep" $p "0.90,0.90"
    run "C.p$p.r$rep" $p "0.99,0.50"
  done
done
echo "P7AIMDONE" >> $L
lock_release p7aim
