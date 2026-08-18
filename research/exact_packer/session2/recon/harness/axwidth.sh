#!/bin/bash
# IS IT THE AXIS OR IS IT THE WIDTH?
#
# The axis table says axis 2 is best on prob_4 and prob_16 at every work level, by 2.5x over the
# runner-up on prob_16.  It was measured at a fixed B=96, K=4 for every axis, and production does
# not do that -- _worker sizes each draw from the axis's own Bmul and K, so axis 2 runs at
# B=int(0.7*96)=67, K=5 there.  Two readings fit the table equally well:
#
#     the SCORING of axis 2 is better        -> the lever is which axis gets the budget
#     the WIDTH 96 is better                 -> the lever is Bmul, and the axis is incidental
#
# They separate exactly, because the work budget removes the noise: run the same axis at its own
# width and at 96 with the same work, and the only difference is the width.
#
# There is a reason to expect width to matter, from the same table read down its columns.  At fixed
# axis, more work means a wider beam (Bcur = left_work/rem in work mode), and more work made some
# axes WORSE:
#
#     P16 axis 4   9,255,020 -> 9,382,627 -> 9,543,435    monotone worse over 1500/3000/6000
#     P24 axis 3   3,637,538 -> 3,637,538 -> 3,706,135
#     P24 axis 2   3,900,130 -> 3,326,701 -> 3,446,775    non-monotone
#
# Beam search is not monotone in width -- a wider beam ranks more states by the same myopic contact
# proxy and can crowd out the one that completes well.  So "wider is better" cannot be assumed in
# either direction, and this queue measures it instead.
#
# The two arms per (instance, axis, work):
#
#     b96   B=96, K=4                        what the axis table used
#     bax   B=_beam_width(Bmul), K=cfg K     what the worker actually runs
#
# Read with:  python3.12 harness/axwidthread.py results/audit/axwidth.log
set -u
cd "$(dirname "$0")/.." || exit 1
echo axwidth > harness/CURRENT
( cd "$(git rev-parse --show-toplevel)" \
  && git add research/exact_packer/session2/recon/harness/CURRENT \
  && git commit -q -m "queue: CURRENT=axwidth" \
  && git push -q origin claude/repair-plan-model-1ig6it ) >/dev/null 2>&1
L=results/audit/axwidth.log
mkdir -p results/audit; touch $L

# Only the bax arm is new: b96 for these cells is already in axwork.log and is not re-run.
for w in 3000 6000; do
  for p in 16 4 24; do
    for ax in 0 1 2 3 4 5; do
      tag="p$p.w$w.a$ax.bax"
      grep -vE '^# ' $L 2>/dev/null | grep -q "\[$tag\]" && continue
      echo "# [$tag]" >> $L
      timeout 1800 /usr/bin/python3.12 harness/beam1.py $p --work $w --axis $ax --useaxis \
          --tag "[$tag]" >> $L 2>&1 || echo "P$p [$tag] CRASH rc=$?" >> $L
    done
    ( cd "$(git rev-parse --show-toplevel)" \
      && git add research/exact_packer/session2/recon/results/audit/axwidth.log \
                research/exact_packer/session2/recon/harness/CURRENT \
      && git commit -q -m "in-flight: axwidth p$p w$w" ) >/dev/null 2>&1
  done
  echo "WIDTHDONE $w" >> $L
done
echo "AXWIDTHDONE" >> $L
echo idle > harness/CURRENT
