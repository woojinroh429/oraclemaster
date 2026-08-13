#!/bin/bash
# 40 IS A 240-SECOND NUMBER AND 120 SECONDS IS STILL USING IT.
#
# HOW THIS SURFACED.  The pre-submission audit ran the shipped zip at 60 s and 120 s on the six
# heaviest instances.  It passed -- no overrun, no infeasibility, no crash -- but the two budgets
# side by side say something the 60 s work could not have seen:
#
#     inst        60 s            120 s          change     wall/120
#     P13    67,433,655  ->  68,679,956        +1.85%        94.75
#     P2     60,116,544  ->  61,457,557        +2.23%        90.09
#     P36    75,872,841  ->  79,484,298        +4.76%        97.68
#     P26    24,322,950  ->  24,799,567        +1.96%        79.29
#     P3      4,675,497  ->   4,536,394        -2.98%        78.68
#     P16     3,114,589  ->   2,891,641        -7.16%        83.74
#
# Four instances score WORSE with twice the time, and every cell leaves 22-41 s of the 120 s
# unused.  The four that regress are the four where DIRGATE does not fire at 60 s; the two that
# improve are the two where it does, so they are also the two whose 60 s run is the unusual one.
#
# THE SUSPECT IS NAMED IN THE FILE'S OWN COMMENT.  myalgorithm.py:
#
#     "OGC_FILLFLOOR", "40" if timelimit > 90 else "10"
#
# and directly above it: "40 IS A 240-SECOND NUMBER AND IT MADE THE 60-SECOND RUN RETURN AT 33 OF
# 60.  Closed is the defect, not the safeguard."  That diagnosis produced the timelimit>90 branch,
# which repaired 60 s and left 120 s on the 240 s constant.  The same defect, one tier up.
#
# The arithmetic matches the walls above.  The gate is
#
#     if left < _need + 8.0 or min(_rb, left - 8.0) < _ff: break
#
# so at 120 s a fill round has to be worth 40 s of round budget before it may start.  With
# reserve = 0.35 * 120 = 42 s the polish returns early, `left` lands in the 20-40 s band, and the
# round is refused -- which is exactly the 22-41 s of unused wall measured.
#
# WHY THIS IS WORTH THE LAST DAY WHEN TODAY'S OTHER ARMS WERE NOT.  results/audit/wrong_budget.md
# records, in the project's own words, "I do not know the final's per-instance budget", and closes
# with "prefer changes whose sign does not depend on it".  Every experiment this session ran at
# 60 s.  If the finals give 120 s, the four regressions above are real losses being shipped.
#
# WHAT WOULD MAKE IT FAIL, named first, and tailburn already showed the shape.  Lowering the floor
# buys a fill round, and a fill round is a fresh draw whose value is instance-signed: at 60 s the
# same family of change won -8.97/-6.00/-11.91 on P20 and lost +7.85/+7.62/+7.62 on P13, three for
# three each way.  A population mean near zero made of two large opposite effects is the expected
# outcome, not a small one, and it is not adoptable however the mean lands.  What would make this
# DIFFERENT from tailburn is a change that is one-directional because it removes a threshold that
# is provably mis-set rather than re-tuning a budget split -- so the cell to watch is whether the
# instances that regressed at 120 s recover, not whether the mean moves.
#
# ARMS: A stock (FILLFLOOR 40 at 120 s), B 10 (the value 60 s uses), C 20.
# INSTANCES: the four that regressed, plus P3/P16 which improved, plus P20/P5 for breadth.
#
# JUDGED, fixed before the run.  Two replicates, paired, at timelimit 120.
#   * wall > 118 s on any cell vetoes that arm outright.
#   * The claim under test is specifically that P13/P2/P36/P26 recover.  An arm that moves the
#     population mean without recovering those four has not done what this file predicts and will
#     be reported as such.
#   * A mean inside +/-0.5% with mixed signs is the tailburn outcome and closes the branch.
set -u
cd /home/user/oraclemaster/research/exact_packer/session2/recon || exit 1
. harness/lock.sh
lock_acquire ff120
S=/tmp/claude-0/-home-user-oraclemaster/55043662-747d-5eda-b837-388adc057292/scratchpad/subcheck
D="$PWD/data/stage2"
L=results/audit/ff120.log
mkdir -p results/audit; touch $L
for rep in 1 2; do
  for p in 13 2 36 26 3 16 20 5; do
    for a in A:40 B:10 C:20; do
      ff="${a#*:}"; arm="${a%%:*}"
      tag="$arm.p$p.r$rep"
      grep -q "^# \[$tag\]" $L 2>/dev/null && continue
      echo "# [$tag] FILLFLOOR=$ff" >> $L
      ( cd "$S" && OGC_FILLFLOOR=$ff timeout 260 /usr/bin/python3.12 grader2.py "$D/prob_$p.json" 120 ) \
          >> $L 2>&1 || echo "P$p [$tag] CRASH rc=$?" >> $L
      ( cd "$(git rev-parse --show-toplevel)" \
        && git add research/exact_packer/session2/recon/results/audit/ff120.log \
                  research/exact_packer/session2/recon/harness/ff120.sh \
                  research/exact_packer/session2/recon/harness/CURRENT \
        && git commit -q -m "in-flight: ff120 $tag" \
        && git push -q origin claude/repair-plan-model-1ig6it ) >/dev/null 2>&1
    done
  done
done
echo "FF120DONE" >> $L
lock_release ff120
