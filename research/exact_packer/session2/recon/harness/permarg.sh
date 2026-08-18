#!/bin/bash
# THE MARGINAL-COST WIDTH CONTROLLER, MEASURED BEFORE IT IS BELIEVED.
#
# THE DEFECT.  ogc_fast.cpp sets the beam width per level from
#
#     Bcur = left / (per * rem)          per = elapsed()/work
#
# `per` is meant to be the price of ONE state expansion.  At level 1 the beam holds a single state,
# so work is 1 and elapsed() is everything the call has done -- shape set-up, first grid build,
# first scan.  The controller therefore prices a state expansion at the whole fixed set-up cost,
# collapses the width, and cannot recover: a narrow beam accumulates work slowly, so the running
# average stays dominated by that same fixed term.
#
# THE EVIDENCE IT IS REAL, all measured, none of it assumed:
#   * prob_1 reports work=402 over 150 levels -- average width 2.7 -- with Bmax=96,
#     beam_width_capped()=0 and level_frac=1.00 at used=0.88.  Neither the ceiling nor the clock is
#     binding, and the beam still runs three wide.
#   * OGC_STEPS=2 is 5.6-6.3x cheaper per expansion at fixed work (OGC_WORKCAP) and yet performs
#     the SAME work in the same wall time when run free.  A stride cannot help if per is dominated
#     by a term the stride does not touch.
#   * 3x the clock is worth -30.7% on prob_1 (flatctl), because `left` is the only term in fit that
#     the budget moves -- width scales with the budget instead of with the search.
#
# THE FIX is one subtraction: price the last level by what the last level actually spent, so set-up
# is charged once to level 1 rather than to every level forever.  OGC_PERMARG=0 restores the
# average and is byte-identical to the shipped engine.
#
# THIS SCRIPT INSTALLS A PATCHED ENGINE, WHICH IS WHY IT BACKS ONE UP FIRST.  The .so in this
# directory is what harness runs import.  The original is saved to ogc_fast.orig.so before the
# patched build is copied in, and restored at the end whether the run finishes or dies -- the trap
# is not decoration, an interrupted run that left a patched engine in place would silently
# contaminate every later measurement in this directory.
#
# BOTH ARMS RUN AGAINST THE SAME PATCHED BINARY, with PERMARG=0 and PERMARG=1, so the comparison
# cannot be confounded by anything else in the rebuild -- compiler version, flags, or an unrelated
# edit.  PERMARG=0 must reproduce the shipped behaviour; if it does not, the patch changed
# something it should not have and the whole thing is void.
#
# WHAT WOULD MAKE IT FAIL, named first.  A wider beam is not automatically a better one: width is
# bought with depth per unit time, and if the extra states are near-duplicates the run pays for
# them and gets nothing -- which is what OGC_DEDUP's own "measured inert" note suggests may be the
# case here, since our dispatch order is fixed.  The second risk is the wall: a controller that
# believes states are cheap will ask for more of them, and the beam's aim is the only thing
# stopping it, so any cell reaching 60.0 s disqualifies the arm regardless of its objective.
#
# JUDGED, fixed before the run: first that PERMARG=0 matches the shipped numbers, then work and
# width from BEAMSTAT (does the fix actually widen the beam), then the objective, paired.
set -u
cd /home/user/oraclemaster/research/exact_packer/session2/recon || exit 1
. harness/lock.sh
PATCHED=/tmp/claude-0/-home-user-oraclemaster/55043662-747d-5eda-b837-388adc057292/scratchpad/permarg/ogc_fast.cpython-312-x86_64-linux-gnu.so
SO=ogc_fast.cpython-312-x86_64-linux-gnu.so
L=results/audit/permarg.log
mkdir -p results/audit; touch $L
if [ ! -f "$PATCHED" ]; then
    echo "# ABORT: patched engine missing at $PATCHED" >> $L; exit 1
fi
lock_acquire permarg
restore(){ [ -f "$SO.orig" ] && mv -f "$SO.orig" "$SO"; lock_release permarg; }
trap restore EXIT INT TERM
cp -f "$SO" "$SO.orig"
cp -f "$PATCHED" "$SO"
ci(){ ( cd "$(git rev-parse --show-toplevel)" \
        && git add research/exact_packer/session2/recon/results/audit/permarg.log \
                  research/exact_packer/session2/recon/harness/permarg.sh \
        && git commit -q -m "in-flight: permarg $1" \
        && git push -q origin claude/repair-plan-model-1ig6it ) >/dev/null 2>&1; }
run(){ local tag="$1" p="$2" env0="$3" _s _e
    grep -vE '^# ' $L 2>/dev/null | grep -q "\[$tag\]" && return
    echo "# [$tag]" >> $L
    _s=$(date +%s.%N)
    env $env0 OGC_BEAMSTAT=1 OGC_WSTAT=1 timeout 200 /usr/bin/python3.12 \
        harness/run1.py myalgorithm $p 60 "[$tag]" --data data/stage2 >> $L 2>&1 \
        || echo "P$p [$tag] CRASH rc=$?" >> $L
    _e=$(date +%s.%N)
    echo "# WALL [$tag] $(awk -v a="$_s" -v b="$_e" 'BEGIN{printf "%.2f", b-a}')" >> $L
    ci "$tag"; }
for rep in 1 2 3; do
  for p in 1 3 16 7; do
    run "off.p$p.r$rep" $p "OGC_PERMARG=0"
    run "on.p$p.r$rep"  $p "OGC_PERMARG=1"
  done
done
echo "PERMARGDONE" >> $L
