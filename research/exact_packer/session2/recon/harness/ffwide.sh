#!/bin/bash
# IS OGC_FFSET SAFE AS A GLOBAL DEFAULT?  IT WAS ADOPTED ON FOUR INSTANCES.
#
# WHAT WAS MEASURED.  ffport ran prob_1, prob_16, prob_20 and prob_3 -- 12 paired cells, mean
# -5.05%, 8W/3T/1L -- and the change is already in the shipped build.  Four instances is the sample
# size this session has repeatedly shown to be too small: the Z3-share gate was fitted on four and
# died on its fifth, and the salvage gate looked 8-of-8 correct before its holdout took it to 43%.
#
# THE ARGUMENT FOR SAFETY IS STRUCTURAL, NOT STATISTICAL, and that is why this is worth checking
# rather than assuming.  The answer is a MINIMUM over the pool and only the EVEN workers change, so
# an instance that reads its minimum off an odd worker cannot be hurt -- the odd draws are
# byte-identical.  That argument is sound only to the extent the even/odd win shares in
# results/audit/workers.md generalise, and that table covers seven instances.
#
# WHERE THE RISK ACTUALLY IS.  From workers.md, the even half's win share:
#
#     prob_1   92%     prob_16  20%     prob_24  20%     prob_36   0%
#     prob_26  21%     prob_30  20%     prob_20   6%
#
# prob_1 gains.  prob_20 and prob_36 barely see the change.  The exposed group is the ~20% band --
# a fifth of their minima come from workers this arm alters -- and of those only prob_16 has been
# measured (-0.25%).  prob_24, prob_26 and prob_30 are untested and carry the same exposure.
#
# AND THE INSTANCES WITH NO workers.md ROW AT ALL ARE THE REAL HOLDOUT.  Their even share is
# unknown, so the structural argument has nothing to stand on for them.  prob_2, prob_5, prob_7,
# prob_10, prob_13, prob_27, prob_33 are carried for exactly that reason.
#
# WHAT WOULD MAKE IT FAIL, named first.  A single instance losing more than ~3% consistently across
# both replicates is enough to pull FFSET back out, because scoring is per-instance rank and prob_1
# is one instance too.  Losses in the 1% band are inside the per-instance noise measured today
# (prob_1 22.9%, prob_16 17.9%, prob_3 1.2%, prob_7 0.0%) and will be reported as undecided rather
# than dressed either way.
#
# The second failure mode is subtler and is the one I would miss: FFSET removes diversity.  Before
# it, both halves ran FINEFRAC 0.60 and differed only in MCAND/ORDER/W3MUL/aim; now they differ in
# one more dimension.  On an instance whose minimum needs TWO similar deep draws rather than one,
# that costs a draw at the good end -- which is exactly the mechanism the AIMSET note records for
# why four aims lost to two.  A loss concentrated on instances where prob_1-like behaviour was
# expected would be this, not noise.
#
# JUDGED, fixed before the run: two replicates per instance, paired.  Report per instance and as a
# population.  FFSET stays only if no instance loses more than 3% on both replicates and the
# population mean is not positive.
set -u
cd /home/user/oraclemaster/research/exact_packer/session2/recon || exit 1
. harness/lock.sh
lock_acquire ffwide
L=results/audit/ffwide.log
mkdir -p results/audit; touch $L
ci(){ ( cd "$(git rev-parse --show-toplevel)" \
        && git add research/exact_packer/session2/recon/results/audit/ffwide.log \
                  research/exact_packer/session2/recon/harness/CURRENT \
                  research/exact_packer/session2/recon/harness/ffwide.sh \
        && git commit -q -m "in-flight: ffwide $1" \
        && git push -q origin claude/repair-plan-model-1ig6it ) >/dev/null 2>&1; }
run(){ local tag="$1" p="$2" env0="$3" _s _e
    grep -vE '^# ' $L 2>/dev/null | grep -q "\[$tag\]" && return
    echo "# [$tag]" >> $L
    _s=$(date +%s.%N)
    env $env0 OGC_WSTAT=1 timeout 200 /usr/bin/python3.12 \
        harness/run1.py myalgorithm $p 60 "[$tag]" --data data/stage2 >> $L 2>&1 \
        || echo "P$p [$tag] CRASH rc=$?" >> $L
    _e=$(date +%s.%N)
    echo "# WALL [$tag] $(awk -v a="$_s" -v b="$_e" 'BEGIN{printf "%.2f", b-a}')" >> $L
    ci "$tag"; }
# exposed band first (workers.md ~20% even), then the instances with no row at all.
for rep in 1 2; do
  for p in 24 26 30 36 2 5 7 10 13 27 33; do
    run "A.p$p.r$rep" $p "OGC_FFSET="
    run "B.p$p.r$rep" $p ""
  done
done
echo "FFWIDEDONE" >> $L
lock_release ffwide
