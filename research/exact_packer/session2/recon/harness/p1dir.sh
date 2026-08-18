#!/bin/bash
# WHICH HALF OF THE DIRECTION IS WORTH THE 2x?
#
# The failed 3+1 arm isolated something by accident.  A worker with config A's aim and config A's m
# but WITHOUT the direction drew a median of 993,027, against 482,866 and 489,878 for the two real
# config-A slots -- 2.03x, larger than anything else measured this session by an order of magnitude.
#
# The direction is two settings at once (line 2940, under OGC_DIRSET=2):
#
#     os.environ.setdefault("OGC_ORDER", "lst")     dispatch order, against the axis's own order
#     os.environ.setdefault("OGC_W3MUL", "0.5")     Z3 weight, against the axis's own 1.0 to 6.0
#
# _AXES gives order defer_big / lst / edd / big_first and w3mul 1.0 / 1.5 / 3.0 / 6.0, so on most
# axes the direction changes BOTH the ordering rule and cuts the preference weight to half the
# smallest value the table ever uses.  Nobody has separated them.  Every sweep tonight -- workers,
# rounds, axes, brk, cross -- moved a draw by single digits; this moves it by 103%.
#
# FOUR CELLS, DIRSET=0 THROUGHOUT so no worker gets the pair override and the environment alone
# decides:
#
#     none      OGC_DIRSET=0                                   axis order, axis w3mul
#     order     OGC_DIRSET=0 OGC_ORDER=lst                     lst, axis w3mul
#     w3mul     OGC_DIRSET=0 OGC_W3MUL=0.5                     axis order, 0.5
#     both      OGC_DIRSET=0 OGC_ORDER=lst OGC_W3MUL=0.5       should reproduce the shipped draws
#
# `both` is the control that proves the setup: it must land near the 486,000 the shipped config-A
# slots produce.  If it does not, the decomposition is measuring something else and the other three
# cells mean nothing.
#
# WHAT EACH OUTCOME WOULD MEAN.  If `order` alone recovers most of the 2x, the ordering rule is the
# lever and w3mul=0.5 is decoration -- and the other orders in _AXES have never been tried against
# it.  If `w3mul` alone recovers it, the Z3 weight is the lever, 0.5 is the smallest value ever
# used, and nothing below it has been tried at all.  If neither alone does much, the pair is
# interacting and has to stay a pair.
#
#
# THE FIRST DESIGN WAS CONFOUNDED AND ITS ONE RUN IS KEPT AS d.both.r1.  Setting the direction
# globally gives it to the config-B workers too, and B is exactly the worker whose cost the 3+1
# result says matters: replacing the cheap early-finishing worker with a heavy one is what dropped
# p from 0.273 to 0.200 there.  The control cell proved it -- config-A slots came back at 589,116
# and 542,037 against stock's 492,458 median, on settings that were supposed to be identical.
# Contention differed between cells, so the cells differed by more than the thing under test.
#
# UNIFORM WORKERS FIX IT.  Single-element AIMSET and MSET make every wid (aim 0.90, m=1), so all
# four workers are the same configuration in every cell, contention is identical across cells, and
# the only thing that varies is the order/w3mul pair under test.  It also doubles the sample: four
# config-A draws per run instead of two.
#
# READ ALL FOUR SLOTS.  Every wid is now (aim 0.90, m=1) on the same order/w3mul, so all four
# draws belong to one population and there is no config B to exclude.
#
# NOTE THAT `both` IS NO LONGER A REPLICA OF THE SHIPPED RUN, and is not meant to be.  The shipped
# run has two config-A workers and two cheap config-B ones; this has four heavy ones.  What the
# four cells give is the CONTRAST between order and w3mul under identical contention -- the
# absolute level will sit above the shipped draws because every worker here is heavy.
set -u
cd /home/user/oraclemaster/research/exact_packer/session2/recon || exit 1
echo p1dir > harness/CURRENT
L=results/audit/p1dir.log
mkdir -p results/audit; touch $L
ci(){ ( cd "$(git rev-parse --show-toplevel)" \
        && git add research/exact_packer/session2/recon/results/audit/p1dir.log \
                  research/exact_packer/session2/recon/harness/CURRENT \
                  research/exact_packer/session2/recon/harness/p1dir.sh \
        && git commit -q -m "in-flight: p1dir $1" \
        && git push -q origin claude/repair-plan-model-1ig6it ) >/dev/null 2>&1; }

run(){ # tag env
    local tag="$1"
    grep -vE '^# ' $L 2>/dev/null | grep -q "\[$tag\]" && return
    echo "# [$tag]" >> $L
    env $2 OGC_WSTAT=1 timeout 560 /usr/bin/python3.12 harness/run1.py myalgorithm 1 240 \
        "[$tag]" --data data/stage2 >> $L 2>&1 || echo "P1 [$tag] CRASH rc=$?" >> $L
    ci "$tag"
}

U="WORKERS=4 OGC_DIRSET=0 OGC_AIMSET=0.90 OGC_MSET=1"
for rep in 1 2 3; do
  run "u.both.r$rep"  "$U OGC_ORDER=lst OGC_W3MUL=0.5"
  run "u.order.r$rep" "$U OGC_ORDER=lst"
  run "u.w3m.r$rep"   "$U OGC_W3MUL=0.5"
  run "u.none.r$rep"  "$U"
done
echo "P1DIRDONE" >> $L
echo idle > harness/CURRENT
