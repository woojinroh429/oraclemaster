#!/bin/bash
# THE NOISE IS THE PROJECT'S BIGGEST PROBLEM, SO MEASURE IT DIRECTLY -- REPLICATES, NOT ARMS.
#
# Every conclusion in this project is a difference between single cells, and today the same
# configuration returned 8,876,985 and 9,162,795 on P20 at 60 s -- 3.2% apart, same code, same env,
# nothing else on the machine.  The file's own note says why: every RNG here is constant-seeded, so
# two runs differ in exactly one input, time.time(), and they land 2.5-25% apart.  The beam derives
# its width from elapsed()/work at every one of ~250 levels, and that feedback loop turns a
# microsecond of drift into a different attractor.
#
# OGC_WRATE=1 breaks the loop without giving up the wall clock: the slice is converted into a work
# cap ONCE per beam, from the expansion rate the previous beam measured, and the width controllers
# then run in the work arm that reads no clock.  How much search the slice buys still tracks the
# machine; which trajectory it takes to get there stops being re-decided 250 times.  Wall clock
# stays as a backstop at a looser aim, because an overrun is disqualification rather than a bad
# score.
#
# WHAT THIS QUEUE HAS TO SHOW, AND THE ORDER MATTERS:
#
#   1. SPREAD.  Three replicates per arm.  If rate mode does not visibly tighten the spread it has
#      failed at the only thing it was built for, whatever it does to the mean.
#   2. THE MEAN.  Determinism is worth nothing if it converges somewhere worse.  Under min-of-N
#      scoring, narrowing the spread at equal centre can even be the wrong trade -- prob_16's best
#      result ever came from the widest-spread arm tried -- so the mean has to hold.
#   3. NO OVERRUN.  ran= must stay inside the limit on every cell.  This is the only change here
#      that can produce an infeasible answer rather than a worse one.
#
# BOTH ARMS RUN AGAINST THE SAME FRESH BINARY, in build_wrate.  OGC_WRATE unset is a no-op in the
# source and NOT in the binary: this project has measured a proved bit-identical speedup move an
# objective 7.7%, because code layout changes timing and the beam derives its width from timing.
# Comparing the new .so against the tree's shipped one would confound the patch with the rebuild.
set -u
cd /home/user/oraclemaster/research/exact_packer/session2/recon/build_wrate || exit 1
echo wrate > harness/CURRENT
( cd "$(git rev-parse --show-toplevel)" \
  && git add research/exact_packer/session2/recon/harness/CURRENT \
  && git commit -q -m "queue: CURRENT=wrate" \
  && git push -q origin claude/repair-plan-model-1ig6it ) >/dev/null 2>&1
L=results/audit/wrate.log
mkdir -p results/audit; touch $L
ci(){ ( cd "$(git rev-parse --show-toplevel)" \
        && git add research/exact_packer/session2/recon/build_wrate/results/audit/wrate.log \
                  research/exact_packer/session2/recon/harness/CURRENT \
        && git commit -q -m "in-flight: wrate $1" \
        && git push -q origin claude/repair-plan-model-1ig6it ) >/dev/null 2>&1; }

run(){ # tag prob limit env
    local tag="$1"
    grep -vE '^# ' $L 2>/dev/null | grep -q "\[$tag\]" && return
    echo "# [$tag]" >> $L
    env $4 timeout $(( $3 * 5 )) /usr/bin/python3.12 harness/run1.py myalgorithm $2 $3 \
        "[$tag]" --data data/stage2 >> $L 2>&1 || echo "P$2 [$tag] CRASH rc=$?" >> $L
    ci "$tag"
}

# Replicates are the point, so they are the INNER loop -- three off and three on for one instance
# land next to each other in time.  Machine speed drifts across an hour (measured 8.4% within one),
# and interleaving the arms is what stops that drift being read as an arm difference.
for BUD in 60 120; do
  for p in 1 20 4; do
    for rep in 1 2 3; do
      run "b$BUD.p$p.off.r$rep" $p $BUD ""
      run "b$BUD.p$p.on.r$rep"  $p $BUD "OGC_WRATE=1"
    done
  done
  echo "== WRATE $BUD done ==" >> $L
done
echo "WRATEDONE" >> $L
echo idle > harness/CURRENT
