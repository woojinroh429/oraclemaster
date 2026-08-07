#!/bin/bash
# OVERNIGHT CAMPAIGN.  Five phases, cheapest and most-informative first, each chained from the last.
#
# WHAT TODAY ESTABLISHED, which is what the phases are built on:
#
#   - OGC_WORKCAP removes the clock from the beam, so a (config, work) pair returns the same
#     objective AND the same placement digest every time.  prob_16's noise went 19.6% -> 0%.
#     Sweeps that were unaffordable are now one cell each.
#   - prob_1 and prob_4 repeat their baseline to the digit, so a same-queue paired arm can be
#     judged there from ONE cell.
#   - Raising the polish reserve from 40 s to 120 s is -6.2% on prob_1 (501,758 -> 470,530,
#     Z3 612 -> 536), and 240 s is +11.7% -- there is an optimum near half the budget and the
#     shipped default sits at 17%.  This is the only real gain measured today.
#   - _AXES varies six knobs and leaves the rest of _contact_beam's signature at defaults.  prefw
#     is 0.0 on ALL SIX AXES, and it weights the PREFERENCE term on a problem where w3*Z3 is
#     14-73% of the objective.  shadow, span, conw, hmatch, stay_w, lex are likewise untouched.
#   - The competitor's prob_1 figure (~370k) is reachable by combining components our own solutions
#     already produce separately -- Z1=5 and Z3=536 would score ~373k.  The gap is search, not
#     structure.
#   - Geometry binds even at 40% area slack: forcing best-bay assignment multiplies prob_1's
#     tardiness by 43.  Relaxation-and-repair ideas are therefore discounted here.
#
# NOTE ON THE HIDDEN SET: the early hidden instances reportedly get a SHORTER time limit than the
# rest, so phase 4 re-measures the winners at 60 s and 120 s.  A reserve fraction tuned at 240 s
# does not automatically transfer -- min(0.20*limit, 40) is 40 s at 240 s but 12 s at 60 s, a
# different regime entirely, and today's polish result showed the regime matters.
#
# PHASES
#   1  reserve fraction        the live lead, real budgets, six instances          ~2.0 h
#   2  prefw                   work-budgeted, noise-free, the untouched knob       ~1.5 h
#   3  dispatch order          work-budgeted, seven orders vs the four in use      ~2.0 h
#   4  short-budget transfer   winners from 1-3 at 60 s and 120 s                  ~1.5 h
#   5  untouched knobs         shadow / span / conw / hmatch, work-budgeted        ~2.0 h
#
# Every cell commits its log, and harness/CURRENT is committed and pushed when the queue claims it,
# so a container restart resumes the phase that was live rather than the last one committed.
set -u
cd "$(dirname "$0")/.." || exit 1
echo night > harness/CURRENT
( cd "$(git rev-parse --show-toplevel)" \
  && git add research/exact_packer/session2/recon/harness/CURRENT \
  && git commit -q -m "queue: CURRENT=night" \
  && git push -q origin claude/repair-plan-model-1ig6it ) >/dev/null 2>&1
L=results/audit/night.log
mkdir -p results/audit; touch $L
say(){ echo "== $* ==" >> $L; }
ci(){ ( cd "$(git rev-parse --show-toplevel)" \
        && git add research/exact_packer/session2/recon/results/audit/night.log \
                  research/exact_packer/session2/recon/harness/CURRENT \
        && git commit -q -m "in-flight: night $1" ) >/dev/null 2>&1; }

# full-pipeline cell (real budget, four workers, polish)
run(){ # tag prob limit env
    local tag="$1"
    grep -vE '^# |^== ' $L 2>/dev/null | grep -q "\[$tag\]" && return
    echo "# [$tag]" >> $L
    env $4 OGC_WSTAT=1 timeout $(( $3 * 4 )) /usr/bin/python3.12 harness/run1.py myalgorithm \
        $2 $3 "[$tag]" --data data/stage2 >> $L 2>&1 || echo "P$2 [$tag] CRASH rc=$?" >> $L
    ci "$tag"
}
# single work-budgeted beam draw (no clock in the search)
b1(){ # tag prob axis extra...
    local tag="$1"; shift; local p="$1"; shift; local ax="$1"; shift
    grep -vE '^# |^== ' $L 2>/dev/null | grep -q "\[$tag\]" && return
    echo "# [$tag]" >> $L
    timeout 1800 /usr/bin/python3.12 harness/beam1.py $p --work 3000 --axis $ax "$@" \
        --tag "[$tag]" >> $L 2>&1 || echo "P$p [$tag] CRASH rc=$?" >> $L
    ci "$tag"
}

# ---------------- phase 1: polish reserve fraction, real budgets ----------------
say "PHASE 1 reserve"
for rep in 1 2; do
  for p in 1 4 24 16 20 6; do
    run "p1.r40.$p.$rep"  $p 240 "OGC_RESERVE=40"
    run "p1.r80.$p.$rep"  $p 240 "OGC_RESERVE=80"
    run "p1.r120.$p.$rep" $p 240 "OGC_RESERVE=120"
    run "p1.r160.$p.$rep" $p 240 "OGC_RESERVE=160"
  done
done
say "PHASE1DONE"

# ---------------- phase 2: prefw, work-budgeted ----------------
say "PHASE 2 prefw"
for p in 1 4 24 16 20 6; do
  for ax in 0 2 4; do
    for pw in 0.0 0.25 0.5 1.0 2.0 4.0; do
      b1 "p2.pw$pw.a$ax.$p" $p $ax --prefw $pw
    done
  done
done
say "PHASE2DONE"

# ---------------- phase 3: dispatch order, work-budgeted ----------------
say "PHASE 3 order"
for p in 1 4 24 16 20 6; do
  for od in edd lst defer_big big_first rank sac3 aspect boxfill cohort; do
    b1 "p3.$od.$p" $p 0 --order $od
  done
done
say "PHASE3DONE"

# ---------------- phase 4: does any of it survive a short budget ----------------
say "PHASE 4 short"
for p in 1 4 24 16; do
  for lim in 60 120; do
    run "p4.base.$p.$lim"  $p $lim ""
    run "p4.rhalf.$p.$lim" $p $lim "OGC_RESERVE=$(( lim / 2 ))"
    run "p4.rthird.$p.$lim" $p $lim "OGC_RESERVE=$(( lim / 3 ))"
  done
done
say "PHASE4DONE"

# ---------------- phase 5: the knobs no axis has ever set ----------------
say "PHASE 5 knobs"
for p in 1 4 24 16; do
  for v in 0.25 1.0; do
    b1 "p5.shadow$v.$p" $p 0 --shadow $v
    b1 "p5.span$v.$p"   $p 0 --span $v
    b1 "p5.hmatch$v.$p" $p 0 --hmatch $v
  done
  b1 "p5.conw0.5.$p" $p 0 --conw 0.5
  b1 "p5.conw2.0.$p" $p 0 --conw 2.0
done
say "PHASE5DONE"

say "NIGHTDONE"
echo idle > harness/CURRENT
