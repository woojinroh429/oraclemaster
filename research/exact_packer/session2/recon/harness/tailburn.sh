#!/bin/bash
# THE NON-DIRGATE INSTANCES RETURN AT 38-45 SECONDS OF A 60 SECOND LIMIT.
#
# HOW THIS SURFACED.  idlegap was measuring the single-threaded windows BETWEEN worker rounds
# (~14-29 idle core-seconds).  Its traces carried a bigger number in a column I had not been
# reading -- the wall time of the whole run:
#
#     DIRGATE fires        P1 47.8s   P3 51.2s   P7 49.8s   P16 51.0s
#     DIRGATE does not     P20 38.5s  P26 38.5s  P13 45.5s  P5 43.2s
#
# The deadline is timelimit - endpad = 60 - 5 = 55 s.  The second group stops 10-17 s early.  At
# ~3 cores that is 30-50 core-seconds thrown away, against the 14-29 core-seconds idlegap was
# chasing -- the thing I was measuring was the smaller of the two.
#
# WHY IT HAPPENS, read off the trace and the code together.  The per-5s CPU profile of P20 is
# 300/312/315/312/313/311/169/104 and then the process exits: one worker round of ~31 s, a
# single-threaded polish of ~7 s, return.  reserve = RESFRAC * timelimit = 0.35 * 60 = 21 s is
# held back for the polish; the polish uses about 7 s of it because z3_reassign breaks on
# `nofuel` once ruin_recreate has nothing left to tear up.  The remaining ~16.5 s then meets
#
#     if left < _need + 8.0 or min(_rb, left - 8.0) < _ff: break
#
# with left = 16.5 and _ff = 10, so left - 8.0 = 8.5 < 10 and the loop breaks.  The time is not
# spent on anything -- it is discarded.
#
# THIS IS THE HALF OF TASK #29 THAT WAS NEVER FIXED, and the code says so in its own words.  The
# FILLFLOOR gate lowered to 10 at 60 s moved prob_1 from wall 35.5 to 57.1.  Its own measurement
# table records prob_16 and prob_13 as "IDENTICAL, gate never opens", and the note calls that
# safety: "provably inert everywhere else, so this cannot cost an instance it does not help."
# True -- and it does not help them either.  Those are exactly the instances still returning early.
#
# ARMS.  The lever is the reserve, because that is what decides how much of the limit round 0 gets
# and therefore how much is left stranded behind the gate.
#     A  stock            RESFRAC 0.35   reserve 21 s
#     B                   RESFRAC 0.20   reserve 12 s
#     C                   RESFRAC 0.10   reserve  6 s
#     D  stock reserve, but let the stranded tail buy a round: FILLFLOOR 8
#
# D is carried because it is the cheaper fix if it works, and because it tests the opposite
# hypothesis: that the tail is worth spending on a SHORT extra draw rather than on a longer
# round 0.  The 240 s measurement says short fill rounds move nothing (eight rounds under 35 s,
# eight times nothing), but there the incumbent came from a 47 s round; here round 0 is ~31 s and
# an 8.5 s draw is still a quarter of it, so D is expected to be the weaker of the two ideas.
#
# WHAT WOULD MAKE THIS FAIL, named first.  Shrinking the reserve is not free: the polish is the
# pass that repairs Z3 and it is given whatever the reserve holds.  On instances where the polish
# DOES have work, cutting the reserve from 21 s to 6 s can cut it off mid-repair, and the loss
# would land on precisely the instances this arm cannot help. The wall time is reported for every
# cell so a run that overruns 60 s is visible immediately -- an overrun is a disqualification-class
# failure and vetoes the arm regardless of objective.
#
# INSTANCES: the non-DIRGATE set only, since DIRGATE instances already run to ~50 s and this
# changes nothing for them -- P20, P26, P13, P5, P2, P30.  DIRGATE's P3 and P16 are carried as a
# CONTROL: if an arm moves them, the change is not doing what this file claims.
#
# JUDGED, fixed before the run.  Three replicates, paired within replicate.
#   * WALL > 59.0 s on any cell vetoes that arm outright.
#   * An arm is adopted only if it wins the population ratio-mean on the six non-DIRGATE
#     instances AND does not lose on the two DIRGATE controls.
#   * Report the wall alongside the objective every time: an arm that extends the wall without
#     improving the objective has proved the time was worthless, which is itself a result and
#     closes this branch rather than inviting another attempt.
set -u
cd /home/user/oraclemaster/research/exact_packer/session2/recon || exit 1
. harness/lock.sh
lock_acquire tailburn
L=results/audit/tailburn.log
mkdir -p results/audit; touch $L
ci(){ ( cd "$(git rev-parse --show-toplevel)" \
        && git add research/exact_packer/session2/recon/results/audit/tailburn.log \
                  research/exact_packer/session2/recon/harness/CURRENT \
                  research/exact_packer/session2/recon/harness/tailburn.sh \
        && git commit -q -m "in-flight: tailburn $1" \
        && git push -q origin claude/repair-plan-model-1ig6it ) >/dev/null 2>&1; }
run(){ local tag="$1" p="$2" ev="$3"
    local _s _e
    grep -vE '^# ' $L 2>/dev/null | grep -q "\[$tag\]" && return
    echo "# [$tag] $ev" >> $L
    _s=$(date +%s.%N)
    env $ev timeout 200 /usr/bin/python3.12 \
        harness/run1.py myalgorithm $p 60 "[$tag]" --data data/stage2 >> $L 2>&1 \
        || echo "P$p [$tag] CRASH rc=$?" >> $L
    _e=$(date +%s.%N)
    echo "# WALL [$tag] $(awk -v a="$_s" -v b="$_e" 'BEGIN{printf "%.2f", b-a}')" >> $L
    ci "$tag"; }
for rep in 1 2 3; do
  for p in 20 26 13 5 2 30 3 16; do
    run "A.p$p.r$rep" $p "OGC_DUMMY=0"
    run "B.p$p.r$rep" $p "OGC_RESFRAC=0.20"
    run "C.p$p.r$rep" $p "OGC_RESFRAC=0.10"
    run "D.p$p.r$rep" $p "OGC_FILLFLOOR=8"
  done
done
echo "TAILBURNDONE" >> $L
lock_release tailburn
