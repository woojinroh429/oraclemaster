#!/bin/bash
# prob_1 GAINS 30% FROM THREE TIMES THE CLOCK.  BUY WHAT WE CAN OF THAT AT SIXTY SECONDS.
#
# flatctl separated time from configuration on the two instances we lose to the competitor:
#
#     effect                       prob_1            prob_3
#     time  60 -> 180 s          -30.7% / -26.3%   -4.06% / -7.48%
#     gate  ON -> OFF at 60 s     +4.10%            +0.56%
#
# prob_1 is nowhere near converged at 60 s, and 455,298 at 180 s sits BELOW the entire attractor
# set every 60 s approach this session has landed in (473,456 / 489,878 / 515,621 / 605,585 /
# 683,809 / 712,652).  The gate is not the problem -- turning DIRGATE off costs at both budgets.
#
# WHERE THE EXTRA TIME GOES, by the budget arithmetic rather than by guess:
#
#                 round 0     fill round    search total
#      60 s        28 s          18 s        46 of 60
#     180 s        85 s          81 s       166 of 180
#
# The round is three times longer, and at 60 s it is 28 s because DIRGATE's RESFRAC=0.50 reserves
# 30 s for a polish that returns in about a second on this instance.  That reserve is the thing
# standing between prob_1 and a longer round.
#
# WHY THIS IS NOT THE RESFRAC 0.05 THAT WAS ALREADY REJECTED.  It was rejected for OVERRUNNING --
# 8 of 8 cells past a 60 s wall at nw=7, worst 65.75 s -- because a 3 s reserve cannot bound
# z3_reassign.  That was measured before OGC_ENDPAD existed; the build now holds 5 s of end margin
# and 0 of 12 cells reached 60 s on the heavy instances.  The failure mode is guarded now, so the
# question is open again -- but it is the SAME failure mode, so the wall is read first and any arm
# with a cell at or past 60 s is disqualified whatever it scores.  0.05 itself is deliberately not
# an arm; the range tested stops at 0.15, which still leaves 9 s of reserve.
#
# ARMS at 60 s, no WORKERS in the environment:
#     A  stock                     RESFRAC 0.50 via DIRGATE, ROUNDS 1   round 0 ~28 s
#     B  longer round              RESFRAC 0.30                          round 0 ~37 s
#     C  longer still              RESFRAC 0.15                          round 0 ~46 s
#     D  more rounds instead       RESFRAC 0.50, ROUNDS 2                two rounds ~14 s
#
# D IS THE CONTROL THAT MAKES THIS A TEST RATHER THAN A TUNE.  If prob_1 wants LENGTH, B and C
# improve and D is worse; if it wants DRAWS, D improves and B and C do not.  The 180 s cell cannot
# distinguish those -- it got both a longer round and a second one -- and the two answers lead to
# opposite settings at 60 s.
#
# WHAT WOULD MAKE IT FAIL, named first.  The reserve is not idle time: it is what the fill round
# spends, and shrinking it shortens the fill round by the same seconds it lends to round 0, so B
# and C may simply move time between two searches and net nothing.  And prob_1 spans ~30% between
# draws, so three replicates is the minimum for reading anything under 10%.  prob_3 and prob_16 are
# carried because RESFRAC is a global default reached through DIRGATE, and prob_3's own time
# response is only -4% -- it has little to gain and something to lose.
#
# JUDGED, fixed before the run: wall first (any cell >= 60.0 s disqualifies its arm), then paired
# ratio against A within replicate, median over three, prob_1 deciding and prob_3/prob_16 vetoing.
set -u
cd /home/user/oraclemaster/research/exact_packer/session2/recon || exit 1
. harness/lock.sh
lock_acquire roundlen
L=results/audit/roundlen.log
mkdir -p results/audit; touch $L
ci(){ ( cd "$(git rev-parse --show-toplevel)" \
        && git add research/exact_packer/session2/recon/results/audit/roundlen.log \
                  research/exact_packer/session2/recon/harness/CURRENT \
                  research/exact_packer/session2/recon/harness/roundlen.sh \
        && git commit -q -m "in-flight: roundlen $1" \
        && git push -q origin claude/repair-plan-model-1ig6it ) >/dev/null 2>&1; }
run(){ local tag="$1" p="$2" env0="$3" _s _e
    grep -vE '^# ' $L 2>/dev/null | grep -q "\[$tag\]" && return
    echo "# [$tag]" >> $L
    _s=$(date +%s.%N)
    env $env0 OGC_WSTAT=1 timeout 200 /usr/bin/python3.12 \
        harness/run1.py myalgorithm $p 60 "[$tag]" --data data/stage2 >> $L 2>&1 \
        || echo "P$p [$tag] CRASH rc=$?" >> $L
    _e=$(date +%s.%N)
    echo "# WALL [$tag] $(awk -v a="$_s" -v b="$_e" 'BEGIN{printf "%.2f", b-a}')" >> $L
    ci "$tag"; }
for rep in 1 2 3; do
  for p in 1 3 16; do
    run "A.p$p.r$rep" $p "OGC_ROUNDS=1"
    run "B.p$p.r$rep" $p "OGC_RESFRAC=0.30 OGC_ROUNDS=1"
    run "C.p$p.r$rep" $p "OGC_RESFRAC=0.15 OGC_ROUNDS=1"
    run "D.p$p.r$rep" $p "OGC_ROUNDS=2"
  done
done
echo "ROUNDLENDONE" >> $L
lock_release roundlen
