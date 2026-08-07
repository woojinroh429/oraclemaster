#!/bin/bash
# OVERNIGHT CAMPAIGN, REORDERED FOR A CONTAINER THAT RESTARTS EVERY FEW MINUTES.
#
# night.sh opened with the reserve-fraction phase: 240 s cells on the full pipeline.  Three restarts
# in ten minutes left it with two markers and zero results, because a cell that does not finish
# produces nothing and starts over.  Short cells are the only ones that accumulate under that.
#
# So the work-budgeted phases run FIRST.  A beam1 cell at work=3000 takes 10-30 s, it is
# deterministic (three repeats returned an identical objective AND an identical placement digest),
# and it needs no replicates -- so every completed cell is a permanent result even if the next
# restart lands a second later.  The long full-pipeline phases run last, when they can be resumed
# cell by cell against whatever the night produced.
#
# WHAT IS BEING SWEPT, AND WHY IT HAS NEVER BEEN SWEPT
#
# _contact_beam takes seventeen knobs.  _AXES varies seven of them and leaves TEN at their defaults
# on all six entries.  prefw is the weight on the PREFERENCE term in the cell score and it is 0.0
# everywhere, on a problem where w3*Z3 is 14-73% of the objective and 73.2% on prob_1.  shadow,
# span, conw, hmatch, swy, swx, span2, shadoww, lex and stay_w are likewise untouched.
#
# They were never swept because until today a 2% effect could not be separated from a 19.6% noise
# band.  OGC_WORKCAP removes the clock from the search and the band goes to zero, which makes a
# seventeen-knob sweep a few hours instead of impossible.
#
# THE LIVE LEAD, kept because it is the only shippable thing measured today:
#
#     prob_1  polish  40 s (beam 200 s)   501,758   Z1=17  Z3=612
#     prob_1  polish 120 s (beam 120 s)   470,530   Z1=19  Z3=536    -6.2%
#     prob_1  polish 240 s (beam  60 s)   560,224   Z1=22  Z3=663   +11.7%
#
# A U-curve on an instance whose baseline repeats to the digit five times.  The default is
# min(20% of budget, 40 s) = 17%; the measurement says 50% is worth -6.2% on prob_1.  Phase 4
# checks whether that holds on instances where Z3 is a smaller share.
#
# INSTANCES.  prob_1 and prob_4 have baselines that repeat to the last digit, so a single cell
# decides.  prob_16 and prob_20 are the Z1-dominated pair, prob_24 the middle.  The hidden set's
# early instances are the target, and prob_1 is the closest analogue in shape and in the fact that
# w3*Z3 carries it.
set -u
cd "$(dirname "$0")/.." || exit 1
echo night2 > harness/CURRENT
( cd "$(git rev-parse --show-toplevel)" \
  && git add research/exact_packer/session2/recon/harness/CURRENT \
  && git commit -q -m "queue: CURRENT=night2" \
  && git push -q origin claude/repair-plan-model-1ig6it ) >/dev/null 2>&1
L=results/audit/night2.log
mkdir -p results/audit; touch $L
say(){ echo "== $* ==" >> $L; }
ci(){ ( cd "$(git rev-parse --show-toplevel)" \
        && git add research/exact_packer/session2/recon/results/audit/night2.log \
                  research/exact_packer/session2/recon/harness/CURRENT \
        && git commit -q -m "in-flight: night2 $1" ) >/dev/null 2>&1; }

# SKIP ON A RESULT, NEVER ON THE MARKER.  The marker is written before the run, so a cell killed by
# a restart must be retried -- excluding '# ' and '== ' lines is what makes the campaign resumable.
b1(){ # tag prob axis extra...
    local tag="$1"; shift; local p="$1"; shift; local ax="$1"; shift
    grep -vE '^# |^== ' $L 2>/dev/null | grep -q "\[$tag\]" && return
    echo "# [$tag]" >> $L
    timeout 900 /usr/bin/python3.12 harness/beam1.py $p --work 3000 --axis $ax "$@" \
        --tag "[$tag]" >> $L 2>&1 || echo "P$p [$tag] CRASH rc=$?" >> $L
    ci "$tag"
}
run(){ # tag prob limit env
    local tag="$1"
    grep -vE '^# |^== ' $L 2>/dev/null | grep -q "\[$tag\]" && return
    echo "# [$tag]" >> $L
    env $4 OGC_WSTAT=1 timeout $(( $3 * 4 )) /usr/bin/python3.12 harness/run1.py myalgorithm \
        $2 $3 "[$tag]" --data data/stage2 >> $L 2>&1 || echo "P$2 [$tag] CRASH rc=$?" >> $L
    ci "$tag"
}

PZ="1 4 24 16 20"          # Z3-heavy first: prob_1 is 73.2% w3*Z3 and is the hidden-set analogue

# ---- PHASE A: prefw, the zero-everywhere weight on the preference term ----
say "PHASE A prefw"
for p in $PZ; do for ax in 0 2 3; do for pw in 0.0 0.5 1.0 2.0 4.0; do
    b1 "A.p$p.a$ax.pw$pw" $p $ax --prefw $pw
done; done; done
say "PHASE A done"

# ---- PHASE B: dispatch order.  Seven exist, four are used. ----
say "PHASE B order"
for p in $PZ; do for od in edd lst defer_big big_first rank sac3 aspect boxfill cohort; do
    b1 "B.p$p.$od" $p 0 --order $od
done; done
say "PHASE B done"

# ---- PHASE C: the other untouched knobs, one at a time off axis 0 ----
say "PHASE C untouched knobs"
for p in $PZ; do
    for v in 0.25 1.0;  do b1 "C.p$p.shadow$v" $p 0 --shadow $v; done
    for v in 0.25 1.0;  do b1 "C.p$p.span$v"   $p 0 --span   $v; done
    for v in 0.5 2.0;   do b1 "C.p$p.conw$v"   $p 0 --conw   $v; done
    for v in 0.25 1.0;  do b1 "C.p$p.hmatch$v" $p 0 --hmatch $v; done
    for v in 0.5 2.0;   do b1 "C.p$p.mum$v"    $p 0 --mum    $v; done
    for v in 0.0 0.3 0.6; do b1 "C.p$p.cohort$v" $p 0 --cohort $v; done
done
say "PHASE C done"

# ---- PHASE D: the live lead, reserve fraction, on the full pipeline ----
say "PHASE D reserve"
for rep in 1 2; do for p in 1 4 24 16 20 6; do
    run "D.r$rep.rv40.$p"  $p 240 "OGC_RESERVE=40"
    run "D.r$rep.rv80.$p"  $p 240 "OGC_RESERVE=80"
    run "D.r$rep.rv120.$p" $p 240 "OGC_RESERVE=120"
    run "D.r$rep.rv160.$p" $p 240 "OGC_RESERVE=160"
done; done
say "PHASE D done"

# ---- PHASE E: short budgets.  The hidden set appears to give prob_1 less time. ----
say "PHASE E short budgets"
for rep in 1 2; do for p in 1 4 24; do for lim in 60 120; do
    run "E.r$rep.b$lim.d.$p" $p $lim ""
    run "E.r$rep.b$lim.h.$p" $p $lim "OGC_RESERVE=$(( lim / 2 ))"
done; done; done
say "PHASE E done"

echo "NIGHT2DONE" >> $L
echo idle > harness/CURRENT
