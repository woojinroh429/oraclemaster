#!/bin/bash
# SEPARATE THE 7TH SUBMISSION'S TWO HALVES: THE DIRECTION, AND THE RESERVE THAT RODE WITH IT.
#
# WHY THIS IS THE LAST QUESTION WORTH ASKING.  The scoreboard the user reposted is the 7th entry
# (total 80,241,439, matching results/audit/subs8.md).  It carries the best hidden P1 ever
# recorded, 2,685,759, across thirteen entries spanning 23.9%.  What it shipped was three GLOBAL
# overrides: ORDER=lst, W3MUL=0.5 and RESFRAC=0.50.  It was reverted in the 8th because the same
# entry cost P2 +14.23%, P5 +19.03% and P8 +14.00% and produced the worst total on record.
#
# The revert bundled three settings, and subs8.md said at the time which one it blamed:
#
#     "resfrac stays out.  It is decided once in algorithm() and cannot be split per worker, and
#      halving the beam's budget on every instance is the part of the 7th with no upside anywhere."
#
# That sentence has never been tested.  The direction and the reserve went out together and came
# back apart -- the direction as OGC_DIRSET=2 (half the workers, shipped) and the pair
# direction+reserve as DIRGATE (all workers, only when 1.00 <= peak_util <= 1.30 and timelimit
# <= 60).  Nothing has ever measured the direction GLOBAL with the reserve LEFT ALONE.
#
# AND THE DIRECTION IS THE ONLY EFFECT OF ITS SIZE IN THIS PROJECT.  results/audit/
# direction_is_the_lever.md isolated it by accident on four worker slots:
#
#     same aim, same m, direction present    median ~486,000
#     same aim, same m, direction absent     median  993,027      2.03x
#
# Everything measured today -- LNSEQ, -fopenmp, RESFRAC, FILLFLOOR, the conflict graph -- was
# single digits or zero.  This is a different order of magnitude, and DIRSET=2 currently gives it
# to only half the workers.
#
# ARMS.
#     A  stock                                   DIRSET=2: direction on the even pair
#     B  OGC_ORDER=lst OGC_W3MUL=0.5             direction on EVERY worker, reserve untouched
#     C  OGC_DIRSET=0                            direction on NO worker
#
# C is not a candidate.  It is the scale check: if the 2.03x generalises, C should be far worse
# than A on the instances where the direction is load-bearing, and indistinguishable where it is
# not.  Without it, a null result for B cannot be told apart from "the direction does nothing on
# this instance anyway", which is the confusion that has wasted several queues today.
#
# INSTANCES.  DIRGATE already forces ORDER and W3MUL globally on the instances it fires on
# (practice P1, P3, P7, P16, P27, P33), so arm B is a NO-OP there and those instances carry no
# information.  The set is therefore the non-firing ones: P2, P5, P13, P20, P26, P36, P24, P30.
# P16 is included precisely because it must come back BYTE-IDENTICAL across all three arms -- it is
# a harness self-check, and if it moves, the arms are not doing what this file says.
#
# WHAT WOULD MAKE THIS FAIL, named first.  The 7th's damage was on hidden P2, P5 and P8, and if
# that damage was the direction rather than the reserve then B loses here too, on the practice
# instances of the same shape.  That is the expected outcome on the evidence as it stands -- the
# 7th is one draw per instance and its P1 gain, -6.86%, sits inside this project's measured
# submission noise floor of -5.16% .. +8.66% from resubmitting identical code.  What makes the
# question worth an hour anyway is that the alternative explanation was written down at the time,
# names a specific mechanism (halving every beam's budget), and was never checked.
#
# JUDGED, fixed before the run.  Two replicates, paired within replicate, 60 s.
#   * P16 must be identical across A, B and C.  If it is not, the run is void and nothing else in
#     it may be read.
#   * B is adopted only if it wins the population ratio-mean on the eight non-firing instances AND
#     does not lose on more than two of them.  A mean inside +/-0.5% is reported as no effect.
#   * C is reported but never adopted; its role is to say, per instance, whether the direction is
#     load-bearing there at all.
#   * If B and C are both near zero on an instance, that instance is direction-insensitive and its
#     B cell carries no evidence either way -- it will be excluded from the mean and the exclusion
#     stated, not applied silently.
set -u
cd /home/user/oraclemaster/research/exact_packer/session2/recon || exit 1
. harness/lock.sh
lock_acquire dirglob
L=results/audit/dirglob.log
mkdir -p results/audit; touch $L
ci(){ ( cd "$(git rev-parse --show-toplevel)" \
        && git add research/exact_packer/session2/recon/results/audit/dirglob.log \
                  research/exact_packer/session2/recon/harness/dirglob.sh \
                  research/exact_packer/session2/recon/harness/CURRENT \
        && git commit -q -m "in-flight: dirglob $1" \
        && git push -q origin claude/repair-plan-model-1ig6it ) >/dev/null 2>&1; }
run(){ local tag="$1" p="$2" ev="$3"
    grep -vE '^# ' $L 2>/dev/null | grep -q "\[$tag\]" && return
    echo "# [$tag] $ev" >> $L
    env $ev OGC_WSTAT=1 timeout 200 /usr/bin/python3.12 \
        harness/run1.py myalgorithm $p 60 "[$tag]" --data data/stage2 2>/dev/null >> $L \
        || echo "P$p [$tag] CRASH rc=$?" >> $L
    ci "$tag"; }
for rep in 1 2; do
  for p in 16 2 5 13 20 26 36 24 30; do
    run "A.p$p.r$rep" $p "OGC_DUMMY=0"
    run "B.p$p.r$rep" $p "OGC_ORDER=lst OGC_W3MUL=0.5"
    run "C.p$p.r$rep" $p "OGC_DIRSET=0"
  done
done
echo "DIRGLOBDONE" >> $L
lock_release dirglob
