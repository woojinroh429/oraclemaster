#!/bin/bash
# brk COSTS 34.7 s AND ITS PARALLEL BUILD HAS NEVER RUN.
#
# On prob_1 brk returned obj 428,809 against 492,458 for the control, Z3 785 -> 445 -- the lowest
# Z3 this project has recorded -- and OPSTAT prices it at 34.7 s for a gain of 72,919, plus it
# revives `bay`, which returned gain 0 in the control and 72,673 with brk in the roster.  So the
# operator pays, and what it costs is worth attacking.
#
# WHERE THE 34.7 s GOES.  cranepack's own note: the conflict graph is an O(ncol^2) pair loop, and
# the file's calibration reads 6.4e-8 seconds per squared column -- ncol 11,580 costs 8.3 s and
# ncol 24,318 costs 39.1 s, a measured ratio of 4.71 against the predicted 4.41.  The search runs
# in whatever is left after that.
#
# TWO LEVERS, NEITHER NEEDING A CODE CHANGE.
#
#   THREADS.  cranepack.cpp already carries a parallel build -- per-thread edge buffers and memos
#   merged afterwards, with CRANEPACK_SERIAL=1 kept specifically so the two paths can be shown to
#   produce the same edge set.  It picks min(omp_get_max_threads(), 8).  myalgorithm.py sets
#   OMP_NUM_THREADS=1 at module load, for a good reason -- four workers times N threads
#   oversubscribes four cores under a 400% cap -- so omp_get_max_threads() is 1 and NTH is 1.  The
#   parallel build has never executed.  brk runs about once per worker, so the windows rarely
#   overlap, but "rarely" is a claim and this measures it.
#
#   COLUMNS.  OGC_TIERNOUT scales how many outsiders a tier offers.  The build is quadratic in
#   ncol, so half the outsiders is about a quarter of the build.  The risk is the opposite of the
#   thread arm's: fewer candidates is a weaker repack, and the gain is what is being bought.
#
# READ BOTH THE OBJECTIVE AND OPSTAT.  A faster brk that stops paying is not an acceleration.
set -u
cd /home/user/oraclemaster/research/exact_packer/session2/recon || exit 1
echo brkfast > harness/CURRENT
L=results/audit/brkfast.log
mkdir -p results/audit; touch $L
ci(){ ( cd "$(git rev-parse --show-toplevel)" \
        && git add research/exact_packer/session2/recon/results/audit/brkfast.log \
                  research/exact_packer/session2/recon/harness/CURRENT \
        && git commit -q -m "in-flight: brkfast $1" \
        && git push -q origin claude/repair-plan-model-1ig6it ) >/dev/null 2>&1; }
run(){ local tag="$1"
    grep -vE '^# ' $L 2>/dev/null | grep -q "\[$tag\]" && return
    echo "# [$tag]" >> $L
    env $4 OGC_WSTAT=1 OGC_OPSTAT=1 timeout $(( $3 * 4 )) /usr/bin/python3.12 harness/run1.py myalgorithm $2 $3 \
        "[$tag]" --data data/stage2 >> $L 2>&1 || echo "P$2 [$tag] CRASH rc=$?" >> $L
    ci "$tag"
}
B="OGC_BRK=1"
for rep in 1 2; do
  for p in 1 3; do
    run "r$rep.p$p.brk"    $p 240 "$B"
    run "r$rep.p$p.omp2"   $p 240 "$B OMP_NUM_THREADS=2 OGC_TPCTL=0"
    run "r$rep.p$p.omp4"   $p 240 "$B OMP_NUM_THREADS=4 OGC_TPCTL=0"
    run "r$rep.p$p.nout50" $p 240 "$B OGC_TIERNOUT=0.5"
    run "r$rep.p$p.nout25" $p 240 "$B OGC_TIERNOUT=0.25"
  done
done
echo "BRKFASTDONE" >> $L
echo idle > harness/CURRENT
