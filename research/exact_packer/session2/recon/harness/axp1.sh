#!/bin/bash
# WHICH AXIS IS prob_1 ACTUALLY WINNING ON, AND CAN THE OTHER THREE WORKERS BE MOVED THERE.
#
# The WSTAT lines are what makes this the next question.  prob_1 at 240 s, printed in wid order:
#
#     w0        w1        w2        w3
#     612,635   689,851   470,530   738,538
#     612,635   704,888   537,482   738,497
#     612,635   791,945   544,247   693,845
#     542,500   739,970   544,247   623,321
#
# w0 and w2 hold the SAME configuration -- aim 0.90, m=1, both even -- and differ only in their
# seed and in where their axis rotation starts, w0 at _AXES[0] and w2 at _AXES[2].  That one
# difference separates a worker frozen at 612,635 for three runs running from the worker that
# supplies the minimum every time.  The file has always said the axis config IS the spread (32-210%
# across configs against 0-12.6% repeating one); this is that statement at the level of a single
# worker, on the instance the priority is about.
#
# So: read every axis on prob_1 directly.  OGC_AXIS=k pins all four workers to _AXES[k] -- they
# still differ in aim, m and seed, so this measures "axis k with the rest of the portfolio", which
# is the quantity that matters rather than a lone beam.
#
#     _AXES[0]  Bmul 1.0  K4  pos_lam 0.10  defer_big  fut_beta 1.0  w3mul 1.0
#     _AXES[1]  Bmul 1.0  K4  pos_lam 0.12  defer_big  fut_beta 1.0  w3mul 3.0  cohort 0.3
#     _AXES[2]  Bmul 0.7  K5  pos_lam 0.15  lst        fut_beta 0.0  w3mul 3.0  cohort 0.3
#     _AXES[3]  Bmul 0.7  K5  pos_lam 0.05  edd        fut_beta 1.5  w3mul 1.0  cohort 0.3
#     _AXES[4]  Bmul 1.4  K3  pos_lam 0.10  big_first  fut_beta 0.5  w3mul 6.0  cohort 0.3
#     _AXES[5]  Bmul 0.5  K6  pos_lam 0.20  defer_big  fut_beta 0.0  w3mul 1.5
#
# base is the rotation as shipped, and dir is the runtime director -- it ranks axes by the relative
# deficit of their draws and spends the remaining ones on what is working.  Its earlier reading was
# neutral, but that was taken before the discarded-draw bug was found and before the m portfolio
# existed, so it is re-read here rather than carried over.
#
# WHAT A PINNED WIN WOULD AND WOULD NOT MEAN.  If one axis beats the rotation on prob_1, that is
# not a licence to ship it: nothing readable off an instance says which axis it wants, and this
# project has already measured that the best axis flips with the budget on two of three instances.
# It would be an argument for the DIRECTOR, which discovers the same thing at runtime without being
# told, and for how the rotation is seeded.
set -u
cd /home/user/oraclemaster/research/exact_packer/session2/recon || exit 1
echo axp1 > harness/CURRENT
( cd "$(git rev-parse --show-toplevel)" \
  && git add research/exact_packer/session2/recon/harness/CURRENT \
  && git commit -q -m "queue: CURRENT=axp1" \
  && git push -q origin claude/repair-plan-model-1ig6it ) >/dev/null 2>&1
L=results/audit/axp1.log
mkdir -p results/audit; touch $L
ci(){ ( cd "$(git rev-parse --show-toplevel)" \
        && git add research/exact_packer/session2/recon/results/audit/axp1.log \
                  research/exact_packer/session2/recon/harness/CURRENT \
        && git commit -q -m "in-flight: axp1 $1" \
        && git push -q origin claude/repair-plan-model-1ig6it ) >/dev/null 2>&1; }

run(){ # tag prob limit env
    local tag="$1"
    grep -vE '^# ' $L 2>/dev/null | grep -q "\[$tag\]" && return
    echo "# [$tag]" >> $L
    env $4 OGC_WSTAT=1 timeout $(( $3 * 4 )) /usr/bin/python3.12 harness/run1.py myalgorithm $2 $3 \
        "[$tag]" --data data/stage2 >> $L 2>&1 || echo "P$2 [$tag] CRASH rc=$?" >> $L
    ci "$tag"
}

# FIRST: DOES dir2 SURVIVE THE INSTANCES THE 7TH SUBMISSION LOST ON.  This is the shipping
# decision and it comes before the study.
#
#     prob_1, three replicates per arm, 240 s
#         base   470,530  537,482  537,698     mean 515,237
#         dir    544,247  542,500  544,247     mean 543,665
#         dir2   457,938  439,374  437,484     mean 444,932    -13.65%
#
# Three of three under every base cell, and the WSTAT line on the last one says why:
#
#     438,791   719,868   437,484   738,497
#
# BOTH even workers now produce ~437-439k.  w0 had been frozen at 612,635 for three consecutive
# runs; the direction unstuck it.  The odd pair is still useless here, so the instance is now
# decided by two good draws instead of one -- which is the whole mechanism, and it is also the
# warning: dir2 rewrites the pair that wins on prob_1, and on a saturated instance that same pair
# may be winning with the OPPOSITE direction.  The 7th shipped this direction globally and cost
# +14.23% on P2, +14.00% on P8 and +19.03% on P5.  If dir2 reproduces that on prob_6, prob_20 or
# prob_36 it does not ship, however good prob_1 looks.
for p in 6 20 36 16 24 4; do
  run "g240.p$p.base" $p 240 ""
  run "g240.p$p.dir2" $p 240 "OGC_DIRSET=2"
done
echo "== DIR2 generalisation done ==" >> $L

for rep in 1 2; do
  run "r$rep.base" 1 240 ""
  for k in 0 1 2 3 4 5; do
    run "r$rep.ax$k" 1 240 "OGC_AXIS=$k"
  done
  run "r$rep.dir"  1 240 "OGC_AXDIR=1 OGC_AXSCAN=0.5"
  # THREE OF FOUR WORKERS ARE WASTED ON THIS INSTANCE, AND THERE IS ALREADY A MECHANISM FOR THAT.
  #
  # The WSTAT lines read 612,635 / 689,851 / 470,530 / 738,538: one worker supplies the answer and
  # the other three spend the entire budget 30-57% behind it.  The minimum hides that -- the run
  # still scores 470,530 -- but three cores bought nothing, and on an instance decided by whether
  # ANY draw reaches a good basin, three wasted cores is three draws not taken.
  #
  # OGC_SHARE is exactly this: a worker that is more than OGC_SHAREGAP behind the best other worker
  # restarts from a fresh seed instead of finishing a basin the minimum will discard.  It is
  # implemented, it has a published rationale in the file ("P7's control returned 937,453 /
  # 923,531 / 1,196,169 / 2,932,676: one core spent the entire budget on something 3.2x behind the
  # winner"), and it has been off by default and never measured.  At the shipped gap of 0.5, w3 at
  # +57% would restart here and w1 at +47% would not.
  run "r$rep.share"     1 240 "OGC_SHARE=1"
  run "r$rep.dir2share" 1 240 "OGC_DIRSET=2 OGC_SHARE=1"
  run "r$rep.dir2"      1 240 "OGC_DIRSET=2"
  echo "== AXP1 rep $rep done ==" >> $L
done
echo "AXP1DONE" >> $L

# _AXES[1] reaches Z1=1 on prob_1, which is a different instance floor than anything shipped has
# seen.  Chase it.
exec bash harness/ax1z1.sh
