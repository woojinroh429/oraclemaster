#!/bin/bash
# PUT THE 7TH SUBMISSION BACK AS AN AXIS, AND FIND THE Z1 PASS'S SHARE.
#
# WHY THE 7TH LOST.  order=lst + w3mul=0.5 + reserve 50% shipped as a GLOBAL override.  _axis_env
# rewrites EVERY axis, so the six-config portfolio became six copies of one direction.  Hidden set,
# against the 6th entry:
#
#     P1 -6.86%  P3 -2.55%  P6 -7.06%   |   P2 +14.23%  P5 +19.03%  P8 +14.00%   total +9.50%
#
# P1 and P3 are this project's best-ever scores on those instances.  The direction is right
# somewhere and wrong elsewhere -- which is the definition of an AXIS, not of a default.  A best-of
# over the true objective cannot lose to a member it still contains; it loses when the member that
# would have won was deleted.
#
# NOT APPENDED.  Seven axes measured 10.8% worse than six on P1, and the six-way choice already
# costs 1-9% against spending everything on one.  So the count stays at six and a defer_big slot
# pays: slots 0, 1 and 5 all sort on due as their second key and won nothing in axis attribution.
# No axis has ever carried w3mul < 1.0, so this direction is not under-weighted in the portfolio,
# it is unreachable.
#
#     p1a   slot 5 -> lst + w3mul 0.5      narrow-deep shape (Bmul 0.5, K 6)
#     p1b   slot 0 -> lst + w3mul 0.5      wide-shallow shape (Bmul 1.0, K 4)
#     p1c   both slots                     twice the draws for the direction
#
# reserve is NOT part of this.  It is a pipeline-level split, not a per-axis field, so it cannot be
# integrated the same way and is left at the shipped default until swept at 60-120 s on its own.
#
# THE Z1 PASS SHARE.  ruin_tardy was wired into the tail at a guessed half-and-half against
# z3_reassign.  Paired, off vs on:
#
#      60 s   P1 -9.56%  P6 -6.10%  P20 -3.53%  P4 -4.10%  P24 -3.01%      5 of 5
#     120 s   P1 +28.78%  P6 +2.28%  P20 +0.39%  P4 -0.60%                 1 of 4
#
# The pass keeps a separate incumbent and is adopted only on strict improvement, so it cannot make
# the answer worse by itself.  What it can do is take half the tail from z3_reassign.  At 60 s z3
# has converged and that half was idle time; at 120 s it was still collecting preference -- P1 ends
# at Z3=608 with the pass off and Z3=910 with it on.  So the share is the knob.  OGC_Z1FRAC=0 is
# identical to the pass being off, which makes the sweep self-baselining.
#
# ONE CELL AT A TIME, NOTHING ELSE ON THE MACHINE.  This engine sizes its beam from measured
# seconds; two contaminated cells earlier read 524,295 and 438,791 where an idle box returns
# 422,629.
set -u
cd "$(dirname "$0")/.." || exit 1
echo integ > harness/CURRENT
( cd "$(git rev-parse --show-toplevel)" \
  && git add research/exact_packer/session2/recon/harness/CURRENT \
  && git commit -q -m "queue: CURRENT=integ" \
  && git push -q origin claude/repair-plan-model-1ig6it ) >/dev/null 2>&1
L=results/audit/integ.log
mkdir -p results/audit; touch $L
ci(){ ( cd "$(git rev-parse --show-toplevel)" \
        && git add research/exact_packer/session2/recon/results/audit/integ.log \
                  research/exact_packer/session2/recon/harness/CURRENT \
        && git commit -q -m "in-flight: integ $1" \
        && git push -q origin claude/repair-plan-model-1ig6it ) >/dev/null 2>&1; }

run(){ # tag prob limit env
    local tag="$1"
    grep -vE '^# ' $L 2>/dev/null | grep -q "\[$tag\]" && return
    echo "# [$tag]" >> $L
    env $4 timeout $(( $3 * 5 )) /usr/bin/python3.12 harness/run1.py myalgorithm $2 $3 \
        "[$tag]" --data data/stage2 >> $L 2>&1 || echo "P$2 [$tag] CRASH rc=$?" >> $L
    ci "$tag"
}

# Phase 1 -- the axis integration at 60 s, on all five.  60 s is the budget the hidden set gives its
# early instances and it is a quarter the cost of a 240 s cell, so the decisive question is also the
# cheap one.  Z1 pass held OFF throughout so the axis reading is the axis alone.
for p in 1 20 6 4 24; do
  for a in base p1a p1b p1c; do
    if [ "$a" = base ]; then E="OGC_Z1PASS=0"; else E="OGC_Z1PASS=0 OGC_AXSET=$a"; fi
    run "a60.p$p.$a" $p 60 "$E"
  done
done
echo "== AXSET 60 done ==" >> $L

# Phase 2 -- THE AXIS DIRECTOR, and the tardiness pass as a scheduled operator instead of a
# constant share.  Both replace a hand-set number with a measured one, which is why they are in the
# same phase: the Z1 fraction sweep this phase used to hold is superseded by registering the pass in
# the gain/spent roster, and a sweep would only have found the constant that the roster does not
# need.
#
#     base   round-robin axes, tail pass off          the thing to beat
#     dir    OGC_AXDIR=1                              deficit-ranked axis choice, full first draws
#     dir5   OGC_AXDIR=1 OGC_AXSCAN=0.5               survey the six on half slices first
#     z1op   OGC_Z1OP=1                               ruin_tardy scheduled by gain/spent
#     both   dir5 + z1op
#
# Every arm carries OGC_Z1PASS=0 so the tail is the same in all of them and the reading is the
# mechanism under test rather than the tail pass it replaces.
D5="OGC_AXDIR=1 OGC_AXSCAN=0.5"
for p in 1 20 6 4 24; do
  run "d60.p$p.base" $p 60 "OGC_Z1PASS=0"
  run "d60.p$p.dir"  $p 60 "OGC_Z1PASS=0 OGC_AXDIR=1"
  run "d60.p$p.dir5" $p 60 "OGC_Z1PASS=0 $D5"
  run "d60.p$p.z1op" $p 60 "OGC_Z1PASS=0 OGC_Z1OP=1"
  run "d60.p$p.both" $p 60 "OGC_Z1PASS=0 $D5 OGC_Z1OP=1"
done
echo "== DIR 60 done ==" >> $L

# Phase 2b -- ROUNDS, RE-ASKED, because the measurement that retired it could not have worked.
#
# OGC_ROUNDS trades round LENGTH for round COUNT: R rounds of nw workers at wbudget/R each is the
# same wall clock for R times the draws.  Under a scoring rule that is a MINIMUM over draws that is
# the direct lever, and the file's own numbers say the length is not what is binding -- prob_20 on
# unchanged code returned 12,746,324 / 10,628,401 / 10,531,622, two of three finding the same
# solution and one missing it by 20%, while 240 s and 360 s return the SAME answer on prob_1.
#
# It was measured once, at 60 s, and retired.  But the round loop then demanded a FULL round plus
# the polish reserve before starting another, and at 60 s wbudget ~ 47, _rb ~ 23, reserve ~ 12 --
# the second round was unaffordable by that arithmetic, so R=2 ran ONE round and the arm measured
# nothing.  That bug is fixed (a short last round now runs instead of being discarded) and the
# knob has never been read since.
#
# Each round gets a fresh round index, so seeds and axis rotations differ and a later round cannot
# re-derive the earlier one.  R=1 is the shipped default and its own baseline here.
for p in 1 20 6 4 24; do
  for r in 1 2 3; do
    run "r60.p$p.R$r" $p 60 "OGC_ROUNDS=$r"
  done
done
echo "== ROUNDS 60 done ==" >> $L

# Phase 3 -- the axis integration at 120 s.  Every finding in this project that was read at one
# budget reversed at another, so the 60 s answer is not shipped until 120 s has seen it.
for p in 1 20 6 4 24; do
  for a in base p1a p1b p1c; do
    if [ "$a" = base ]; then E="OGC_Z1PASS=0"; else E="OGC_Z1PASS=0 OGC_AXSET=$a"; fi
    run "a120.p$p.$a" $p 120 "$E"
  done
done
echo "== AXSET 120 done ==" >> $L

# Phase 4 -- the director and the scheduled pass at 120 s.  Same reason phase 3 exists: nothing in
# this project has held its sign across budgets, and 60-120 s is the range the hidden set gives.
for p in 1 20 6 4 24; do
  run "d120.p$p.base" $p 120 "OGC_Z1PASS=0"
  run "d120.p$p.dir"  $p 120 "OGC_Z1PASS=0 OGC_AXDIR=1"
  run "d120.p$p.dir5" $p 120 "OGC_Z1PASS=0 $D5"
  run "d120.p$p.z1op" $p 120 "OGC_Z1PASS=0 OGC_Z1OP=1"
  run "d120.p$p.both" $p 120 "OGC_Z1PASS=0 $D5 OGC_Z1OP=1"
done
echo "== DIR 120 done ==" >> $L

for p in 1 20 6 4 24; do
  for r in 1 2 3; do
    run "r120.p$p.R$r" $p 120 "OGC_ROUNDS=$r"
  done
done
echo "== ROUNDS 120 done ==" >> $L

# d60.pX.base repeats a60.pX.base exactly -- same env, same budget, same build.  That is deliberate
# and it is the only repeatability estimate this queue produces: every conclusion below is a
# difference between single cells, and the size of the base-to-base gap is what says whether a
# difference of that size means anything at all.

echo "INTEGDONE" >> $L
echo idle > harness/CURRENT
