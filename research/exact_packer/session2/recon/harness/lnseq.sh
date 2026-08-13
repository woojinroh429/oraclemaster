#!/bin/bash
# THE LNS IS ALREADY BOLTED TO THE BEAM.  WHAT IT LACKS IS THE FIX ITS OWN SIBLING ALREADY MADE.
#
# WHAT IS ACTUALLY IN THE TREE, because the header comment on it is stale and I quoted the stale
# version earlier.  Engine::z3_reassign runs hillclimb -> ruin_recreate -> hillclimb until its
# budget is gone, and it is ALWAYS ON.  Its header says the recreate re-inserts at the FIXED
# [en,ex] "so Z1 is invariant -- only Z3 moves".  That is not what the body does:
#
#     // (b) entry-shift only into strictly-preferred bays (Z1-for-Z3 trade)
#     if(prefv(b,tb)>prefv(b,obay)){ ... }
#
# So the entry-time-freeing LNS variant I was about to call unexplored is already implemented.
# Beam + LNS is the shipped configuration, not a proposal.
#
# WHAT IS MISSING, and the evidence for it is in the sibling operator's own comment.  ruin_tardy
# measured this landscape directly:
#
#     102 of 102 completed rounds were rejected and the BEST of them came in at a relative
#     delta of exactly 0.0 -- throughput is fixed and Z1 is conserved under rearrangement.
#
# and it therefore accepts equal-scoring rounds, so the walk can cross the plateau instead of
# stopping at its edge.  ruin_recreate sits on the same saturated geometry and does NOT:
#
#     if(o<best_obj-1e-9){ best_obj=o; best_recs=recs; }
#     else { recs=best_recs; rebuild(recs); }        // equal -> thrown away
#
# OGC_LNSEQ=1 adds the plateau branch.  best_recs is still tracked separately and is still what
# leaves the function, so the pass cannot return a worse layout than it was handed.
#
# WHAT WOULD MAKE IT FAIL, named first, and it is NOT "the answer gets worse in that pass".  The
# loop currently quits early -- `if(!did){ if(++nofuel>4*n_bays+8) break; }` -- and myalgorithm.py's
# fill loop hands the remainder back to the worker pool as another ROUND, another draw of the
# attractor set.  A walk that keeps going spends that time inside one layout instead.  The measured
# price list says a draw is worth a lot: expected minimum over k draws on prob_1 is -5.9% at k=6 and
# -11.0% at k=12.  So this arm trades draws for depth, and depth has lost that trade every time it
# has been offered this session (OGC_ROUNDS 18/18 losses the other way, ratio-mean +12.14%).
# That is the honest prior: this probably loses.  It is worth one hour because the mechanism is not
# a guess -- it is the fix a sibling operator on the same geometry already needed.
#
# INSTANCES, chosen by measurement noise rather than by interest.  Baseline spread over identical
# runs, measured this session: prob_20 0.0%, prob_3 1.2%, prob_7 11.1%, prob_16 17.9%, prob_1 22.9%.
# prob_20 and prob_3 are where a real effect is readable at three replicates; prob_1/7/16 are
# carried because they are where the LOSS mechanism (fewer draws) would show, and prob_5/13/24 for
# breadth outside the set every knob this session was fitted on.
#
# JUDGED, fixed before the run.  Three replicates, paired within replicate, ratio per cell.
#   * prob_20 and prob_3 decide the SIGN -- they are the only cells where 1% is signal.
#   * LNSEQ ships only if the population ratio-mean is negative AND no instance loses more than
#     3% on all three replicates.
#   * A result inside +/-1% on prob_20/prob_3 is reported as "no effect", not dressed as a win.
# Step 0 is an identity check: the new .so with LNSEQ unset must reproduce prob_20 EXACTLY, because
# prob_20's spread is 0.0% and the patch is supposed to be inert when off.
set -u
cd /home/user/oraclemaster/research/exact_packer/session2/recon || exit 1
. harness/lock.sh
lock_acquire lnseq
L=results/audit/lnseq.log
mkdir -p results/audit; touch $L
ci(){ ( cd "$(git rev-parse --show-toplevel)" \
        && git add research/exact_packer/session2/recon/results/audit/lnseq.log \
                  research/exact_packer/session2/recon/harness/CURRENT \
                  research/exact_packer/session2/recon/harness/lnseq.sh \
        && git commit -q -m "in-flight: lnseq $1" \
        && git push -q origin claude/repair-plan-model-1ig6it ) >/dev/null 2>&1; }
run(){ local tag="$1" p="$2" ev="$3" _s _e
    grep -vE '^# ' $L 2>/dev/null | grep -q "\[$tag\]" && return
    echo "# [$tag]" >> $L
    _s=$(date +%s.%N)
    env $ev timeout 200 /usr/bin/python3.12 \
        harness/run1.py myalgorithm $p 60 "[$tag]" --data data/stage2 >> $L 2>&1 \
        || echo "P$p [$tag] CRASH rc=$?" >> $L
    _e=$(date +%s.%N)
    echo "# WALL [$tag] $(awk -v a="$_s" -v b="$_e" 'BEGIN{printf "%.2f", b-a}')" >> $L
    ci "$tag"; }
# step 0: inertness of the patch when the knob is absent (prob_20 spread is 0.0%)
run "ID.p20.r1" 20 "OGC_LNSEQ="
run "ID.p20.r2" 20 "OGC_LNSEQ="
for rep in 1 2 3; do
  for p in 20 3 7 1 16 5 13 24; do
    run "A.p$p.r$rep" $p "OGC_LNSEQ="
    run "B.p$p.r$rep" $p "OGC_LNSEQ=1"
  done
done
echo "LNSEQDONE" >> $L
lock_release lnseq
